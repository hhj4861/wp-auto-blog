#!/usr/bin/env python3
"""One durable scheduled attempt per KST day; called under posting concurrency.

The workflow must push a claim before running any remote posting effects. A
failed/ambiguous attempt is retained, never automatically retried as a new post.
Only the standard library is used so setup failures can also be reported.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.posting_schedule import KST, CATEGORIES, category_for_date

STATE = Path('data/scheduled_post_runs.json')
CRONS = {'0 2 * * 1,3,5': {0, 2, 4}, '0 2 * * 2,4': {1, 3},
         '0 2 * * 6': {5}, '0 2 * * 0': {6}, '17,47 2-13 * * *': set(range(7))}


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timezone_required')
    return result


def read_state(path):
    if not path.exists():
        return {'schema_version': 1, 'runs': {}}
    data = json.loads(path.read_text())
    if (not isinstance(data, dict) or data.get('schema_version') != 1
            or not isinstance(data.get('runs'), dict)):
        raise ValueError('invalid_schedule_state')
    # Fail closed: a damaged existing claim must never look like an empty day.
    for key, row in data['runs'].items():
        if (not re.fullmatch(r'\d{4}-\d{2}-\d{2}', key) or not isinstance(row, dict)
                or row.get('category') not in CATEGORIES
                or not re.fullmatch(r'[1-9][0-9]*', str(row.get('run_id', '')))
                or row.get('status') not in {'started', 'success', 'failure', 'cancelled'}):
            raise ValueError('invalid_schedule_state')
        timestamp(row['claimed_at'])
    return data


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def claim(env, path=STATE, now=None):
    scheduled = env.get('GITHUB_EVENT_NAME') == 'schedule'
    recovery = env.get('SCHEDULE_RECOVERY') == 'true'
    if not scheduled and not recovery:
        return {'run': 'true', 'reason': 'explicit_manual_run'}
    if (env.get('GITHUB_REF') != 'refs/heads/main'
            or env.get('GITHUB_REPOSITORY') != 'hhj4861/wp-auto-blog'):
        raise ValueError('untrusted_schedule')
    if recovery and (env.get('BLOG_MODE') != 'queue'
                     or env.get('BLOG_PUBLISH') != 'true'
                     or env.get('BLOG_TOPIC') or env.get('BLOG_RESUME_DRAFT_ID')):
        raise ValueError('invalid_recovery_inputs')
    created = timestamp(env['SCHEDULE_RUN_CREATED_AT']).astimezone(KST)
    current = (now or datetime.now(timezone.utc)).astimezone(KST)
    day = created.date().isoformat()
    weekday = created.weekday()
    if current < created or current.date() != created.date() or current.hour < 11:
        return {'run': 'false', 'reason': 'outside_scheduled_day'}
    if scheduled and weekday not in CRONS.get(env.get('SCHEDULE_CRON'), set()):
        return {'run': 'false', 'reason': 'schedule_day_mismatch'}
    category = category_for_date(created.date())
    if recovery and env.get('BLOG_CATEGORY') not in ('', None, category):
        raise ValueError('recovery_category_mismatch')
    run_id = env.get('GITHUB_RUN_ID', '')
    if not re.fullmatch(r'[1-9][0-9]*', run_id):
        raise ValueError('invalid_run_id')
    state = read_state(path)
    if day in state['runs']:
        return {'run': 'false', 'reason': 'already_attempted', 'day': day,
                'owner_run': state['runs'][day]['run_id']}
    state['runs'][day] = {'run_id': run_id, 'category': category,
                          'claimed_at': current.isoformat(), 'status': 'started'}
    save(path, state)
    return {'run': 'true', 'reason': 'claimed', 'day': day, 'category': category}


def finish(env, path=STATE):
    state = read_state(path)
    for row in state['runs'].values():
        if row['run_id'] == env.get('GITHUB_RUN_ID') and row['status'] == 'started':
            status = env.get('SCHEDULE_JOB_STATUS')
            if status not in {'success', 'failure', 'cancelled'}:
                raise ValueError('invalid_job_status')
            row.update(status=status, completed_at=datetime.now(timezone.utc).isoformat())
            save(path, state)
            return


def failure_message(env):
    stages = {'selection': '키워드 선정·검색 수요·출처 검증',
              'generation': '본문 생성·품질 검수',
              'notification': '쿠팡 링크 요청 발송'}
    stage_path = Path(env.get('SCHEDULE_STAGE_PATH', '/nonexistent'))
    stage = stage_path.read_text().strip() if stage_path.exists() else ''
    label = stages.get(stage, '실행 준비 또는 인증')
    run_id = env.get('GITHUB_RUN_ID', '')
    if not re.fullmatch(r'[1-9][0-9]*', run_id):
        raise ValueError('invalid_run_id')
    category = env.get('SCHEDULE_CATEGORY', '')
    if category not in CATEGORIES:
        category = '예약 카테고리'
    return (f'[자동 포스팅 중단]\n카테고리: {category}\n중단 단계: {label}\n'
            '작업이 완료되지 않았습니다. 일부 초안이나 요청이 만들어졌을 수 있어 '
            '상태 확인 전에는 새 글 생성을 자동 반복하지 않습니다.\n'
            f'실행 기록: https://github.com/hhj4861/wp-auto-blog/actions/runs/{run_id}')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('telegram_redirect_rejected')


def notify_failure(env):
    token, chat = env.get('TELEGRAM_BOT_TOKEN', ''), env.get('TELEGRAM_CHAT_ID', '')
    if (not re.fullmatch(r'[0-9]{1,20}:[A-Za-z0-9_-]{20,200}', token)
            or not re.fullmatch(r'-?[1-9][0-9]{0,18}', chat)):
        raise ValueError('telegram_not_configured')
    payload = json.dumps({'chat_id': chat, 'text': failure_message(env),
                          'link_preview_options': {'is_disabled': True}}).encode()
    request = Request(f'https://api.telegram.org/bot{token}/sendMessage', data=payload,
                      headers={'Content-Type': 'application/json'}, method='POST')
    # Never retry an ambiguous send and never print token-bearing exception text.
    with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=20) as response:
        data = json.loads(response.read(1_000_001))
        if response.status != 200 or data.get('ok') is not True:
            raise ValueError('telegram_failed')
    print('Scheduled failure notification delivered')


def main():
    try:
        command = sys.argv[1]
        if command == 'claim':
            result = claim(os.environ)
            print(json.dumps(result, ensure_ascii=False))
            with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
                for key, value in result.items():
                    out.write(f'{key}={value}\n')
        elif command == 'finish':
            finish(os.environ)
        elif command == 'notify-failure':
            notify_failure(os.environ)
        else:
            raise ValueError('unknown_command')
    except Exception:
        print('Scheduled posting control failed; inspect the step and saved state.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
