"""Durable Telegram approval stages. CI commits each intent before remote effects."""
from datetime import datetime, timedelta, timezone
import argparse
import json
import os
from pathlib import Path
import sys

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.coupang_telegram import RequestStore, TelegramClient, TelegramError, draft_fingerprint, process_updates

DATA = Path('data')
CATEGORIES = {'취업', '건강', '생활정보'}


def now():
    return datetime.now(timezone.utc)


def expired(record):
    try:
        stamp = datetime.fromisoformat(record['selected_at'])
        return stamp.tzinfo is None or not timedelta(0) <= now() - stamp <= timedelta(hours=36)
    except (KeyError, ValueError, TypeError):
        return True


def queue_rows():
    try:
        value = json.loads((DATA / 'topic_queue_general.json').read_text())
        if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
            raise ValueError
        return value
    except (OSError, ValueError):
        raise TelegramError('invalid_queue') from None


def save_queue(rows):
    path = DATA / 'topic_queue_general.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def read_draft(post_id, env):
    if env.get('WP_GENERAL_URL', '').rstrip('/') != 'https://trendpulse.blog':
        raise TelegramError('wordpress_unavailable')
    if not env.get('WP_GENERAL_USERNAME') or not env.get('WP_GENERAL_APP_PASSWORD'):
        raise TelegramError('wordpress_unavailable')
    try:
        with requests.Session() as session:
            session.trust_env = False
            session.auth = (env['WP_GENERAL_USERNAME'], env['WP_GENERAL_APP_PASSWORD'])
            session.headers['User-Agent'] = 'Mozilla/5.0 (TrendPulse draft approval)'
            response = session.get(f'https://trendpulse.blog/wp-json/wp/v2/posts/{post_id}',
                                   params={'context': 'edit'}, timeout=60, allow_redirects=False)
            if response.status_code != 200:
                raise ValueError
            post = response.json()
        if type(post.get('id')) is not int or post['id'] != post_id or post.get('status') != 'draft':
            raise TelegramError('draft_changed')
        draft_fingerprint(post)
        return post
    except TelegramError:
        raise
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        raise TelegramError('wordpress_unavailable') from None


def register(store, client, env):
    """Record notification intent BEFORE sending; uncertain deliveries are never retried."""
    client.check_webhook()
    rows = queue_rows()
    identifiers = []
    for row in rows:
        if row.get('status') != 'held_draft' or row.get('affiliate_state') != 'waiting':
            continue
        post_id = row.get('post_id')
        if type(post_id) is not int or post_id <= 0 or row.get('category') not in CATEGORIES:
            raise TelegramError('invalid_queue')
        if expired(row):
            row['affiliate_state'] = 'held'
            row['affiliate_error'] = 'request_expired'
            continue
        existing = next((record for record in store.data['requests'] if record['post_id'] == post_id), None)
        if existing is None:
            try:
                post = read_draft(post_id, env)
            except TelegramError as error:
                # One unavailable or manually changed draft must not block replies
                # belonging to other, already-notified drafts.
                row.update(affiliate_state='held', affiliate_error=error.reason)
                continue
            existing = store.create(post_id, row['category'], row['keyword'], row['topic'],
                                    draft_fingerprint(post), row['selected_at'])
        row['affiliate_request_id'] = existing['request_id']
        if existing['status'] == 'pending_notification':
            existing['status'] = 'notification_unknown'
            existing['last_error'] = 'notification_delivery_unknown'
            identifiers.append(existing['request_id'])
    store.save()
    save_queue(rows)
    return identifiers


def notify(store, client, identifiers):
    """Caller supplies only intents durably committed by this job's register stage."""
    failures = False
    for identifier in identifiers:
        record = store.find(identifier)
        if not record or record['status'] != 'notification_unknown':
            raise TelegramError('invalid_request')
        try:
            key = client.send_request({**record, 'status': 'pending_notification'})
        except TelegramError:
            failures = True
            continue
        record.update(status='waiting', message_key=key)
        record.pop('last_error', None)
        store.save()
    if failures:
        raise TelegramError('notification_delivery_unknown')


def feedback(client, record, text):
    try:
        client.send_feedback(record, text)
    except TelegramError:
        print('Telegram feedback unavailable; durable post state retained', flush=True)


def prepare(store, client, run_id):
    """Arm at most one publication. A previous run's intent requires reconciliation."""
    if not run_id.isdigit():
        raise TelegramError('invalid_request')
    selected = ''
    rows = queue_rows()
    for record in store.data['requests']:
        error = None
        if record['status'] == 'publishing':
            error = 'publication_outcome_unknown'
        elif record['status'] in {'waiting', 'ready', 'pending_notification'} and expired(record):
            error = 'request_expired'
        if error:
            record.update(status='held', last_error=error)
            store.save()
            feedback(client, record, '발행 보류: 요청이 만료되었거나 이전 발행 결과 확인이 필요합니다. 초안을 확인해 주세요.')
        elif record['status'] == 'ready' and not selected:
            record.update(status='publishing', publish_attempt_run=run_id, publishing_at=now().isoformat())
            selected = record['request_id']
        for row in rows:
            if row.get('post_id') == record['post_id']:
                row['affiliate_state'] = record['status']
    store.save()
    save_queue(rows)
    return selected


def publish(store, client, identifier, env, publisher=None):
    record = store.find(identifier)
    if (not record or record['status'] != 'publishing'
            or record.get('publish_attempt_run') != env.get('GITHUB_RUN_ID')):
        raise TelegramError('invalid_request')
    if publisher is None:
        from publish_codex_draft import publish_draft
        publisher = publish_draft
    configured = {**env, 'BLOG_MODE': 'queue', 'BLOG_CATEGORY': record['category'],
                  'BLOG_PUBLISH': 'true', 'BLOG_WRITER_PROVIDER': 'codex'}
    try:
        if expired(record):
            raise TelegramError('request_expired')
        url = publisher(record['post_id'], configured, affiliate_request=dict(record))
    except Exception as error:
        reason = 'request_expired' if isinstance(error, TelegramError) and error.reason == 'request_expired' else 'publication_failed'
        record.update(status='held', last_error=reason)
        store.save()
        rows = queue_rows()
        for row in rows:
            if row.get('post_id') == record['post_id']:
                row.update(affiliate_state='held', affiliate_error=reason)
        save_queue(rows)
        feedback(client, record, '발행 보류: 상품·출처·본문 검증 또는 발행 확인을 통과하지 못했습니다. 자동 재발행하지 않습니다.')
        raise TelegramError(reason) from None
    record.update(status='published', published_url=url, published_at=now().isoformat())
    record.pop('last_error', None)
    store.save()
    feedback(client, record, f'쿠팡 상품 링크를 포함해 발행했습니다.\n{url}')
    print('VERIFIED COUPANG PUBLISHED', url, flush=True)
    return url


def output(name, value):
    if os.getenv('GITHUB_OUTPUT'):
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as handle:
            handle.write(f'{name}={value}\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['check', 'register', 'notify', 'receive', 'prepare', 'publish'])
    parser.add_argument('--request-id', default='')
    args = parser.parse_args()
    load_dotenv()
    try:
        if os.getenv('GITHUB_ACTIONS') == 'true' and os.getenv('GITHUB_REF') != 'refs/heads/main':
            raise TelegramError('invalid_request')
        client = TelegramClient(os.environ)
        store = RequestStore(DATA / 'coupang_requests.json')
        if args.stage == 'check':
            client.check_webhook()
        elif args.stage == 'register':
            output('notification_ids', ','.join(register(store, client, os.environ)))
        elif args.stage == 'notify':
            notify(store, client, [value for value in os.getenv('NOTIFICATION_IDS', '').split(',') if value])
        elif args.stage == 'receive':
            ready = process_updates(store, client)
            print(f'Accepted replies: {len(ready)}')
        elif args.stage == 'prepare':
            output('request_id', prepare(store, client, os.environ.get('GITHUB_RUN_ID', '')))
        elif args.stage == 'publish':
            publish(store, client, args.request_id, os.environ)
        return 0
    except Exception as error:
        reason = error.reason if isinstance(error, TelegramError) else 'operation_failed'
        print('Coupang approval stopped:', reason, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
