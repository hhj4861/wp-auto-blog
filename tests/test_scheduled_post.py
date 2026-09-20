from datetime import datetime, date, timedelta
import json
from pathlib import Path
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import scheduled_post as schedule
from src.posting_schedule import category_for_date


def environment(day='2026-09-14', cron='0 2 * * 1,3,5', run='100'):
    return {'GITHUB_EVENT_NAME': 'schedule', 'GITHUB_REF': 'refs/heads/main',
            'GITHUB_REPOSITORY': 'hhj4861/wp-auto-blog', 'GITHUB_RUN_ID': run,
            'SCHEDULE_RUN_CREATED_AT': f'{day}T02:00:00Z', 'SCHEDULE_CRON': cron,
            'BLOG_MODE': 'queue', 'BLOG_PUBLISH': 'true', 'BLOG_CATEGORY': ''}


def at(day='2026-09-14', time='12:15'):
    return datetime.fromisoformat(f'{day}T{time}:00+09:00')


@pytest.mark.parametrize('day,category', [('2026-09-14', '생활정보'), ('2026-09-15', '취업'),
    ('2026-09-16', '생활정보'), ('2026-09-17', '취업'), ('2026-09-18', '생활정보'), ('2026-09-19', '건강')])
def test_recovery_uses_scheduled_kst_category(tmp_path, day, category):
    result = schedule.claim(environment(day, '17,47 2-13 * * *'), tmp_path/'runs.json', at(day))
    assert result['run'] == 'true'
    assert result['category'] == category


@pytest.mark.parametrize('status', ['started', 'success', 'failure', 'cancelled'])
def test_delayed_primary_catchup_and_rerun_never_duplicate(tmp_path, status):
    path = tmp_path/'runs.json'
    env = environment(cron='17,47 2-13 * * *')
    assert schedule.claim(env, path, at())['run'] == 'true'
    if status != 'started':
        schedule.finish({**env, 'SCHEDULE_JOB_STATUS': status}, path)
    before = path.read_bytes()
    for run in ('100', '101', '102'):
        assert schedule.claim(environment(run=run), path, at(time='15:00'))['run'] == 'false'
    assert path.read_bytes() == before


@pytest.mark.parametrize('day,time,cron', [
    ('2026-09-14', '10:59', '0 2 * * 1,3,5'),
    ('2026-09-15', '12:00', '0 2 * * 1,3,5'),
    ('2026-09-20', '12:00', '0 2 * * 6'),
    ('2026-09-14', '12:00', 'unknown')])
def test_invalid_schedule_time_or_day_does_not_claim(tmp_path, day, time, cron):
    path = tmp_path/'runs.json'
    assert schedule.claim(environment(day, cron), path, at(day,time))['run'] == 'false'
    assert not path.exists()


def test_job_waiting_until_next_kst_day_does_not_steal_today(tmp_path):
    path = tmp_path/'runs.json'
    assert schedule.claim(environment(), path, at('2026-09-15'))['run'] == 'false'
    assert not path.exists()


def test_manual_recovery_and_late_cron_share_claim(tmp_path):
    path = tmp_path/'runs.json'
    env = {**environment(), 'GITHUB_EVENT_NAME': 'workflow_dispatch', 'SCHEDULE_RECOVERY': 'true'}
    assert schedule.claim(env, path, at())['reason'] == 'claimed'
    assert schedule.claim(environment(run='200'), path, at())['reason'] == 'already_attempted'


@pytest.mark.parametrize('change', [{'GITHUB_REF':'refs/heads/feature'},
    {'GITHUB_REPOSITORY':'other/repo'}, {'BLOG_PUBLISH':'false'}, {'BLOG_MODE':'general'},
    {'BLOG_TOPIC':'forced topic'}, {'BLOG_RESUME_DRAFT_ID':'1754'}, {'BLOG_CATEGORY':'건강'}])
def test_recovery_cannot_override_scheduled_scope(tmp_path, change):
    env = {**environment(), 'GITHUB_EVENT_NAME': 'workflow_dispatch', 'SCHEDULE_RECOVERY': 'true', **change}
    with pytest.raises(ValueError):
        schedule.claim(env, tmp_path/'runs.json', at())


def test_regular_manual_work_does_not_consume_scheduled_day(tmp_path):
    path = tmp_path/'runs.json'
    assert schedule.claim({'GITHUB_EVENT_NAME':'workflow_dispatch'}, path, at())['run'] == 'true'
    assert not path.exists()


@pytest.mark.parametrize('value', ['bad json', '{}', '{"schema_version":1,"runs":[]}',
    '{"schema_version":1,"runs":{"2026-09-14":{}}}'])
def test_corrupt_state_fails_closed(tmp_path, value):
    path=tmp_path/'runs.json'; path.write_text(value)
    with pytest.raises((ValueError, KeyError)):
        schedule.claim(environment(),path,at())


def test_finish_cannot_change_another_run(tmp_path):
    path=tmp_path/'runs.json'
    schedule.claim(environment(),path,at())
    before=path.read_bytes()
    schedule.finish({'GITHUB_RUN_ID':'999','SCHEDULE_JOB_STATUS':'success'},path)
    assert path.read_bytes()==before


def test_error_notification_contains_stage_and_link_without_exception_text(tmp_path):
    path=tmp_path/'stage'; path.write_text('selection')
    env={**environment(), 'SCHEDULE_STAGE_PATH':str(path), 'SCHEDULE_CATEGORY':'생활정보',
         'TELEGRAM_BOT_TOKEN':'never-print-this', 'ERROR':'secret details'}
    message=schedule.failure_message(env)
    assert '키워드 선정' in message and '생활정보' in message and '/runs/100' in message
    assert 'secret' not in message and 'never-print-this' not in message


def test_workflow_claim_is_serialized_durable_and_blocks_generation():
    wf=yaml.safe_load(Path('.github/workflows/auto-post.yml').read_text())
    trigger=wf.get('on',wf.get(True))
    assert trigger['schedule'][-1]['cron']=='17,47 2-13 * * *'
    job=wf['jobs']['post-queue']; steps=job['steps']
    assert job['concurrency']['group']=='trendpulse-general-posting'
    assert steps[0]['with']['ref']=='${{ github.ref }}'
    claim=next(i for i,s in enumerate(steps) if s.get('id')=='daily')
    assert 'scheduled_post.py claim' in steps[claim]['run']
    assert 'SCHEDULE_STAGE_PATH=$RUNNER_TEMP/' in steps[claim]['run']
    assert not any('runner.' in str(value) for value in job['env'].values())
    assert 'commit_coupang_state.sh' in steps[claim+1]['run']
    for step in steps[claim+2:]:
        if step.get('if')=='always()' or 'scheduled_post.py' in step.get('run',''):
            continue
        assert "steps.daily.outputs.run == 'true'" in step['if'],step
    assert 'data/scheduled_post_runs.json' in Path('scripts/commit_coupang_state.sh').read_text()
    finish=next(s for s in steps if 'scheduled_post.py finish' in s.get('run',''))
    assert "steps.daily.outputs.reason == 'claimed'" in finish['if']
    failure=next(s for s in steps if 'notify-failure' in s.get('run',''))
    assert 'failure()' in failure['if']


@pytest.mark.parametrize('day,category', [('2026-09-20', '생산성'),
    ('2026-09-27', '리뷰'), ('2026-10-04', '테크'), ('2026-10-11', '생산성'),
    ('2026-12-27', '테크'), ('2027-01-03', '생산성')])
def test_sunday_rotation_primary_recovery_finish_and_duplicates(tmp_path, day, category):
    path = tmp_path / 'runs.json'
    env = environment(day, '0 2 * * 0')
    assert schedule.claim(env, path, at(day))['category'] == category
    schedule.finish({**env, 'SCHEDULE_JOB_STATUS': 'success'}, path)
    assert schedule.read_state(path)['runs'][day]['status'] == 'success'
    for cron in ('0 2 * * 0', '17,47 2-13 * * *'):
        assert schedule.claim(environment(day, cron, '101'), path, at(day))['reason'] == 'already_attempted'
    manual = {**environment(day, run='102'), 'GITHUB_EVENT_NAME': 'workflow_dispatch',
              'SCHEDULE_RECOVERY': 'true', 'BLOG_CATEGORY': category}
    assert schedule.claim(manual, path, at(day))['reason'] == 'already_attempted'
    # Catch-up can be first; rotation does not depend on prior completed weeks.
    assert schedule.claim(environment(day, '17,47 2-13 * * *'),
                          tmp_path/'catchup.json', at(day))['category'] == category
    assert schedule.claim(manual, tmp_path/'manual.json', at(day))['category'] == category


def test_rotation_is_continuous_across_years():
    start = date(2026, 9, 20)
    for week in range(160):
        assert category_for_date(start + timedelta(weeks=week)) == ('생산성', '리뷰', '테크')[week % 3]


def test_sunday_run_cannot_post_on_monday(tmp_path):
    assert schedule.claim(environment('2026-09-20', '0 2 * * 0'), tmp_path/'runs.json',
                          at('2026-09-21'))['reason'] == 'outside_scheduled_day'


def test_workflows_research_and_post_all_scheduled_categories():
    wf = yaml.safe_load(Path('.github/workflows/auto-post.yml').read_text())
    for cron in schedule.CRONS:
        assert cron in [s['cron'] for s in wf.get('on', wf.get(True))['schedule']]
        assert f"github.event.schedule == '{cron}'" in wf['jobs']['post-queue']['if']
    research = yaml.safe_load(Path('.github/workflows/blog-keyword-select.yml').read_text())
    choices = research.get('on', research.get(True))['workflow_dispatch']['inputs']['category']['options']
    assert schedule.CATEGORIES <= set(choices)
    step = next(s for s in research['jobs']['select']['steps'] if 'SELECT_CATEGORY' in s.get('env', {}))
    assert step['env']['SELECT_CATEGORY'] == "${{ inputs.category || 'scheduled' }}"
