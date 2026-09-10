"""Verify results from the existing general/queue pipeline, without selecting topics."""
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

from run_codex_worker import verify_published


def main():
    load_dotenv()
    if os.getenv('BLOG_RESUME_DRAFT_ID'):
        # Recovery already reads back and verifies the exact draft ID.
        return
    required = os.getenv('BLOG_REQUIRE_PUBLICATION_RESULT') == '1'
    path = Path(os.environ['BLOG_RESULT_PATH'])
    if not path.exists():
        if required:
            raise RuntimeError('Required publication result is missing')
        print('No posting result produced (for example, empty queue); no publication claimed')
        return
    results = json.loads(path.read_text())
    if not results:
        if required:
            raise RuntimeError('Required publication result is empty')
        print('No topics processed; no publication claimed')
        return
    if os.getenv('BLOG_PUBLISH') != 'true':
        print('Publication was not requested; draft result retained')
        return
    session = requests.Session()
    session.auth = (os.environ['WP_GENERAL_USERNAME'], os.environ['WP_GENERAL_APP_PASSWORD'])
    session.headers['User-Agent'] = 'Mozilla/5.0 (TrendPulse publication verification)'
    url = verify_published(results, session, os.environ['WP_GENERAL_URL'].rstrip('/'))
    print('VERIFIED CODEX PUBLISHED', url, flush=True)
    with Path(os.environ['GITHUB_STEP_SUMMARY']).open('a') as summary:
        summary.write(f'Codex subscription: [verified published post]({url})\n')


if __name__ == '__main__':
    main()
