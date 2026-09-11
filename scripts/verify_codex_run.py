"""Verify results from the existing general/queue pipeline, without selecting topics."""
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from run_codex_worker import verify_published


def verify_waiting(results, session, base, queue_path=Path('data/topic_queue_general.json')):
    """Only a matching held queue row AND live draft prove affiliate waiting."""
    if len(results) != 1:
        raise RuntimeError('Expected exactly one waiting draft')
    result = results[0]
    if (result.get('success') is not True or result.get('awaiting_affiliate') is not True
            or result.get('status') != 'draft' or type(result.get('post_id')) is not int
            or result['post_id'] <= 0 or base != 'https://trendpulse.blog'):
        raise RuntimeError('Invalid affiliate waiting result')
    rows = json.loads(queue_path.read_text())
    matching = [row for row in rows if row.get('post_id') == result['post_id']]
    if (len(matching) != 1 or matching[0].get('status') != 'held_draft'
            or matching[0].get('affiliate_state') not in ('waiting', 'notification_unknown')
            or matching[0].get('category') not in ('취업', '건강', '생활정보')):
        raise RuntimeError('Affiliate waiting queue mismatch')
    response = session.get(f"{base}/wp-json/wp/v2/posts/{result['post_id']}",
                           params={'context': 'edit'}, timeout=60, allow_redirects=False)
    if response.status_code != 200:
        raise RuntimeError('Draft verification unavailable')
    post = response.json()
    if post.get('id') != result['post_id'] or post.get('status') != 'draft':
        raise RuntimeError('Affiliate waiting draft mismatch')
    return result['post_id']


def main():
    load_dotenv()
    if os.getenv('BLOG_RESUME_DRAFT_ID'):
        # Recovery already reads back and verifies the exact draft ID.
        return
    path = Path(os.environ['BLOG_RESULT_PATH'])
    if not path.exists():
        print('No posting result produced (for example, empty queue); no publication claimed')
        return
    results = json.loads(path.read_text())
    if not results:
        print('No topics processed; no publication claimed')
        return
    if os.getenv('BLOG_PUBLISH') != 'true':
        print('Publication was not requested; draft result retained')
        return
    session = requests.Session()
    session.auth = (os.environ['WP_GENERAL_USERNAME'], os.environ['WP_GENERAL_APP_PASSWORD'])
    session.headers['User-Agent'] = 'Mozilla/5.0 (TrendPulse publication verification)'
    if any(result.get('awaiting_affiliate') for result in results):
        post_id = verify_waiting(results, session, os.environ['WP_GENERAL_URL'].rstrip('/'))
        print('VERIFIED DRAFT WAITING_FOR_COUPANG', post_id, flush=True)
        if os.getenv('GITHUB_STEP_SUMMARY'):
            with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as summary:
                summary.write(f'쿠팡 링크 답장 대기: 초안 #{post_id} (미발행)\n')
        return
    url = verify_published(results, session, os.environ['WP_GENERAL_URL'].rstrip('/'))
    print('VERIFIED CODEX PUBLISHED', url, flush=True)
    with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as summary:
        summary.write(f'Codex subscription: [verified published post]({url})\n')


if __name__ == '__main__':
    main()
