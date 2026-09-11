import json
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_codex_run import verify_waiting


@pytest.fixture
def waiting(tmp_path):
    path = tmp_path / 'queue.json'
    path.write_text(json.dumps([{'post_id': 45, 'status': 'held_draft',
                                'affiliate_state': 'waiting', 'category': '건강'}]))
    result = [{'success': True, 'post_id': 45, 'status': 'draft', 'awaiting_affiliate': True}]
    session = Mock()
    session.get.return_value.status_code = 200
    session.get.return_value.json.return_value = {'id': 45, 'status': 'draft'}
    return path, result, session


def test_waiting_is_verified_as_draft_without_publication(waiting):
    path, result, session = waiting
    assert verify_waiting(result, session, 'https://trendpulse.blog', path) == 45
    assert session.get.call_args.kwargs['allow_redirects'] is False
    session.post.assert_not_called()


@pytest.mark.parametrize('change', ['different_id', 'public', 'missing_queue', 'held_quality', 'unverified_result', 'redirect'])
def test_waiting_never_claims_success_for_wrong_state(waiting, change):
    path, result, session = waiting
    if change == 'different_id':
        session.get.return_value.json.return_value['id'] = 46
    elif change == 'public':
        session.get.return_value.json.return_value['status'] = 'publish'
    elif change == 'missing_queue':
        path.write_text('[]')
    elif change == 'held_quality':
        rows = json.loads(path.read_text()); rows[0].pop('affiliate_state')
        path.write_text(json.dumps(rows))
    elif change == 'unverified_result':
        result[0]['awaiting_affiliate'] = False
    else:
        session.get.return_value.status_code = 302
    with pytest.raises(RuntimeError):
        verify_waiting(result, session, 'https://trendpulse.blog', path)
    session.post.assert_not_called()


def test_reply_workflow_persists_intents_before_remote_effects():
    wf = yaml.safe_load(Path('.github/workflows/coupang-replies.yml').read_text())
    trigger = wf.get('on', wf.get(True))
    assert trigger['schedule'] == [{'cron': '7,17,27,37,47,57 * * * *'}]
    job = wf['jobs']['replies']
    assert job['if'] == "github.ref == 'refs/heads/main'"
    steps = job['steps']
    def index(command):
        return next(i for i, step in enumerate(steps) if command in step.get('run', ''))
    commit_indices = [i for i, step in enumerate(steps) if 'commit_coupang_state.sh' in step.get('run', '')]
    assert index('worker.py register') < commit_indices[0] < index('worker.py notify')
    assert index('worker.py receive') < index('worker.py prepare') < commit_indices[1] < index('worker.py publish')
    assert commit_indices[-1] > index('worker.py publish')
    assert steps[commit_indices[-1]]['if'] == 'always()'
    assert sum('worker.py receive' in step.get('run', '') for step in steps) == 1
    auth = next(step for step in steps if step.get('id') == 'auth')
    assert auth['if'] == "steps.approval.outputs.request_id != ''"
    assert any('always()' in step.get('if', '') and 'codex_worker_auth.py persist' in step.get('run', '') for step in steps)


def test_shared_state_and_auth_jobs_queue_instead_of_canceling_pending_posts():
    for path in Path('.github/workflows').glob('*.yml'):
        wf = yaml.safe_load(path.read_text())
        scopes = [wf, *wf.get('jobs', {}).values()]
        for scope in scopes:
            concurrency = scope.get('concurrency', {})
            if isinstance(concurrency, dict) and concurrency.get('group') == 'trendpulse-general-posting':
                assert concurrency.get('queue') == 'max', str(path)
                assert concurrency.get('cancel-in-progress') is False


def test_all_trendpulse_jobs_require_links_and_commit_even_on_notification_failure():
    wf = yaml.safe_load(Path('.github/workflows/auto-post.yml').read_text())
    for name in ['post-general', 'post-queue']:
        job = wf['jobs'][name]
        assert job['env']['BLOG_COUPANG_TELEGRAM'] == '1'
        steps = job['steps']
        check = next(i for i, s in enumerate(steps) if 'worker.py check' in s.get('run', ''))
        generate = next(i for i, s in enumerate(steps) if s.get('name', '').startswith('Run pipeline'))
        register = next(i for i, s in enumerate(steps) if 'worker.py register' in s.get('run', ''))
        notify = next(i for i, s in enumerate(steps) if 'worker.py notify' in s.get('run', ''))
        assert check < generate < register < notify
        assert any('commit_coupang_state.sh' in step.get('run', '') for step in steps[register+1:notify])
        assert any(step.get('if') == 'always()' and ('commit_coupang_state.sh' in step.get('run', '')
                   or 'data/coupang_requests.json' in step.get('run', '')) for step in steps[notify+1:])
