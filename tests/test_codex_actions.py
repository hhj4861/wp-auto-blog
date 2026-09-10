import json
from unittest.mock import Mock

import pytest
import yaml

from scripts.run_codex_worker import command, verify_published
from scripts.codex_worker_auth import validate_auth
from src.codex_client import require_private_actions


@pytest.mark.parametrize("private,event,ref,allowed", [
    (True, "workflow_dispatch", "refs/heads/main", True),
    (False, "workflow_dispatch", "refs/heads/main", False),
    (True, "pull_request", "refs/heads/main", False),
    (True, "workflow_dispatch", "refs/heads/feature", False),
])
def test_private_ci_boundary(tmp_path, monkeypatch, private, event, ref, allowed):
    path = tmp_path / "event.json"
    path.write_text(json.dumps({"repository": {"private": private, "default_branch": "main", "full_name": "owner/worker"}}))
    for key, value in {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_PATH": str(path),
                       "GITHUB_REPOSITORY": "owner/worker", "GITHUB_REF": ref,
                       "GITHUB_EVENT_NAME": event}.items():
        monkeypatch.setenv(key, value)
    if allowed:
        require_private_actions()
    else:
        with pytest.raises(RuntimeError, match="private worker"):
            require_private_actions()


def response(data):
    return Mock(json=lambda: data, raise_for_status=lambda: None)


def test_input_is_literal_argv_and_subscription_explicit():
    topic = '한글 $(touch /tmp/never) "제목"'
    args = command({"WP_GENERAL_URL": "https://trendpulse.blog", "BLOG_TOPIC": topic, "BLOG_PUBLISH": "true"})
    assert args[args.index("--topic") + 1] == topic
    assert args[args.index("--writer-provider") + 1] == "codex"
    assert "--auto-publish" in args
    assert "--dry-run" not in args
    assert "--dry-run" in command({"WP_GENERAL_URL": "https://trendpulse.blog", "BLOG_MODE": "queue"})


def test_api_auth_not_accepted_as_subscription():
    with pytest.raises(ValueError):
        validate_auth('{"auth_mode":"apikey"}')


@pytest.mark.parametrize('schedule,category', [
    ('0 2 * * 1,3,5', '생활정보'), ('0 2 * * 2,4', '취업'), ('0 2 * * 6', '건강')])
def test_scheduled_codex_preserves_category_and_publishes(schedule, category):
    args = command({'WP_GENERAL_URL': 'https://trendpulse.blog', 'BLOG_MODE': 'queue',
                    'BLOG_PUBLISH': 'true', 'BLOG_SCHEDULE': schedule})
    assert args[args.index('--category') + 1] == category
    assert '--from-queue' in args and '--auto-publish' in args
    assert args[args.index('--writer-provider') + 1] == 'codex'


def test_auth_persists_updated_file_without_printing_then_cleans_up(tmp_path, monkeypatch):
    import scripts.codex_worker_auth as auth
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    monkeypatch.setenv('RUNNER_TEMP', str(tmp_path))
    monkeypatch.setenv('GITHUB_REPOSITORY', 'hhj4861/wp-auto-blog')
    monkeypatch.setenv('WORKER_ADMIN_TOKEN', 'test-only')
    seed = json.dumps({'auth_mode': 'chatgpt', 'tokens': {'refresh_token': 'test-seed'}})
    monkeypatch.setenv('CODEX_AUTH_JSON', seed)
    monkeypatch.setattr('sys.argv', ['auth', 'restore'])
    auth.main()
    path = tmp_path / 'trendpulse-codex/auth.json'
    assert path.stat().st_mode & 0o777 == 0o600
    refreshed = seed.replace('test-seed', 'test-refreshed')
    path.write_text(refreshed)
    run = Mock()
    monkeypatch.setattr(auth.subprocess, 'run', run)
    monkeypatch.setattr('sys.argv', ['auth', 'persist'])
    auth.main()
    assert run.call_args.kwargs['input'] == refreshed
    assert 'test-refreshed' not in str(run.call_args.args)
    assert not path.parent.exists()


@pytest.mark.parametrize('changed', [False, True])
def test_unchanged_auth_skips_secret_write_and_failed_write_still_cleans_up(tmp_path, monkeypatch, changed):
    import subprocess
    import scripts.codex_worker_auth as auth
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    monkeypatch.setenv('RUNNER_TEMP', str(tmp_path))
    monkeypatch.setenv('GITHUB_REPOSITORY', 'hhj4861/wp-auto-blog')
    monkeypatch.setenv('WORKER_ADMIN_TOKEN', 'test-only')
    seed = json.dumps({'auth_mode': 'chatgpt', 'tokens': {'refresh_token': 'test-seed'}})
    monkeypatch.setenv('CODEX_AUTH_JSON', seed)
    monkeypatch.setattr('sys.argv', ['auth', 'restore'])
    auth.main()
    path = tmp_path / 'trendpulse-codex/auth.json'
    if changed:
        path.write_text(seed.replace('test-seed', 'test-refreshed'))
    run = Mock(side_effect=subprocess.CalledProcessError(1, ['gh', 'secret', 'set']))
    monkeypatch.setattr(auth.subprocess, 'run', run)
    monkeypatch.setattr('sys.argv', ['auth', 'persist'])
    if changed:
        with pytest.raises(subprocess.CalledProcessError):
            auth.main()
        run.assert_called_once()
    else:
        auth.main()
        run.assert_not_called()
    assert not path.parent.exists()


@pytest.mark.parametrize('failure', [False, True])
def test_auth_probe_reports_only_allowlisted_metadata(tmp_path, monkeypatch, capsys, failure):
    import base64
    import scripts.check_codex_auth as probe
    from src.codex_client import CodexRequestError
    payload = base64.urlsafe_b64encode(json.dumps({'exp': 1, 'email': 'private@example.com'}).encode()).decode()
    seed = json.dumps({'auth_mode': 'chatgpt', 'last_refresh': '2026-09-09T00:00:00Z',
                      'tokens': {'refresh_token': 'secret-refresh', 'access_token': f'private.{payload}.private',
                                 'id_token': 'secret-id', 'account_id': 'private-account'}})
    auth = tmp_path / 'auth.json'
    auth.write_text(seed)
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    monkeypatch.setenv('BLOG_CODEX_HOME', str(tmp_path))
    client = Mock()
    def generate(prompt):
        assert 'secret' not in prompt
        if failure:
            raise CodexRequestError(1, 'refresh_token_reused; secret-refresh')
        auth.write_text(seed.replace('secret-refresh', 'rotated-secret'))
        return 'private model output must also stay out of the log'
    client.generate.side_effect = generate
    monkeypatch.setattr(probe, 'CodexSubscriptionClient', lambda **kw: client)
    assert probe.main() == int(failure)
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report['reason'] == ('refresh_token_reused' if failure else 'ok')
    assert report['auth_file_changed'] is not failure
    assert report['before']['access_token_expired'] is True
    assert report['before']['last_refresh_utc'] == '2026-09-09T00:00:00+00:00'
    assert report['before']['has_refresh_token'] is True
    for sensitive in ('secret-refresh', 'secret-id', 'private', 'rotated-secret', payload):
        assert sensitive not in output


def test_auth_metadata_never_echoes_unparsed_values():
    from scripts.check_codex_auth import auth_metadata
    report = auth_metadata(json.dumps({'last_refresh': 'secret-value', 'tokens': {'access_token': 'secret-value'}}))
    assert report['access_token_expired'] is None
    assert report['last_refresh_utc'] is None
    assert 'secret-value' not in json.dumps(report)


def test_auth_check_only_skips_keyword_and_report_side_effects():
    from pathlib import Path
    workflow = yaml.safe_load(Path('.github/workflows/blog-keyword-select.yml').read_text())
    assert workflow['concurrency']['group'] == 'trendpulse-general-posting'
    steps = workflow['jobs']['select']['steps']
    for name in ('Discover and verify category topics', 'Save category research report', 'Commit verified report'):
        assert 'inputs.auth_check_only != true' in next(s for s in steps if s.get('name') == name)['if']
    assert next(s for s in steps if s.get('name') == 'Check restored Codex authentication')['if'] == 'inputs.auth_check_only == true'


@pytest.mark.parametrize("results", [[], [{"success": True, "status": "draft"}], [{"success": False}]])
def test_draft_or_no_post_is_not_publication_success(results):
    session = Mock()
    with pytest.raises(RuntimeError, match="one published post"):
        verify_published(results, session, "https://trendpulse.blog")
    session.get.assert_not_called()


def test_posting_requires_wordpress_confirmation():
    session = Mock()
    session.get.return_value = response({"status": "publish", "link": "https://trendpulse.blog/example/"})
    results = [{"success": True, "status": "publish", "post_id": 17, "url": "https://trendpulse.blog/example/"}]
    assert verify_published(results, session, "https://trendpulse.blog") == results[0]['url']
    session.get.return_value = response({"status": "draft", "link": results[0]['url']})
    with pytest.raises(RuntimeError, match="verification failed"):
        verify_published(results, session, "https://trendpulse.blog")


def test_main_emits_actual_result_for_worker(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import src.main as entry
    from src.wordpress_client import PostStatus
    result = SimpleNamespace(success=True, post=SimpleNamespace(
        id=17, title="한글 제목", url="https://trendpulse.blog/example/", status=PostStatus.PUBLISH))
    pipeline = Mock()
    pipeline.run_single.return_value = result
    monkeypatch.setattr(entry, "BlogPipeline", lambda config: pipeline)
    monkeypatch.setattr(entry, "load_dotenv", lambda: None)
    monkeypatch.setattr(entry, "setup_logging", lambda **kwargs: None)
    monkeypatch.setattr("sys.argv", ["blog", "--mode", "general", "--topic", "한글 제목", "--writer-provider", "codex", "--auto-publish"])
    path = tmp_path / "result.json"
    monkeypatch.setenv("BLOG_RESULT_PATH", str(path))
    assert entry.main() == 0
    assert json.loads(path.read_text()) == [{"success": True, "post_id": 17,
        "url": result.post.url, "status": "publish"}]


def test_existing_category_jobs_keep_schedule_and_share_writer():
    from pathlib import Path
    workflow = yaml.safe_load(Path('.github/workflows/auto-post.yml').read_text())
    assert 'post-codex' not in workflow['jobs']
    schedules = workflow.get('on', workflow.get(True))['schedule']
    assert [entry['cron'] for entry in schedules] == ['0 2 * * 1,3,5', '0 2 * * 2,4', '0 2 * * 6']
    for name in ('post-general', 'post-queue'):
        job = workflow['jobs'][name]
        assert 'vars.BLOG_WRITER_PROVIDER' in job['env']['BLOG_WRITER_PROVIDER']
        assert 'writer_provider' not in job['if']
        assert job['concurrency']['cancel-in-progress'] is False
        assert any('always()' in step.get('if', '') and 'persist' in step.get('run', '') for step in job['steps'])
    queue = next(s['run'] for s in workflow['jobs']['post-queue']['steps'] if s.get('name', '').startswith('Run pipeline'))
    assert 'python -m src.main --mode general --from-queue --auto-publish --category "$CAT"' in queue
    for category in ('취업', '건강', '생활정보'):
        assert f'CAT="{category}"' in queue


@pytest.mark.parametrize('worker_exit', [0, 1])
def test_queue_draft_recovery_skips_selection_and_new_post_creation(tmp_path, worker_exit):
    import os
    import subprocess
    from pathlib import Path
    workflow = yaml.safe_load(Path('.github/workflows/auto-post.yml').read_text())
    job = workflow['jobs']['post-queue']
    assert job['env']['BLOG_MODE'] == 'queue'
    script = next(s['run'] for s in job['steps']
                  if s.get('name', '').startswith('Run pipeline'))
    fake_python = tmp_path / 'python'
    calls = tmp_path / 'calls'
    fake_python.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$RECOVERY_CALLS"\n'
                           + f'exit {worker_exit}\n')
    fake_python.chmod(0o700)
    result = subprocess.run(['bash', '-e', '-c', script], capture_output=True, text=True,
        env={**os.environ, 'PATH': str(tmp_path) + os.pathsep + os.environ['PATH'],
             'BLOG_RESUME_DRAFT_ID': '1724', 'RECOVERY_CALLS': str(calls)})
    assert result.returncode == worker_exit, result.stderr
    assert calls.read_text().splitlines() == ['scripts/run_codex_worker.py']
    persistence = next(s for s in job['steps'] if s.get('name') == 'Commit queue and registry updates')
    assert persistence['if'] == 'always()'
    for path in ('data/topic_queue_general.json', 'data/posted_market_keywords.json'):
        assert path in persistence['run']


@pytest.mark.parametrize('repo,event,ref,opt_in,allowed', [
    ('hhj4861/wp-auto-blog', 'workflow_dispatch', 'refs/heads/main', '1', True),
    ('hhj4861/wp-auto-blog', 'schedule', 'refs/heads/main', '1', True),
    ('hhj4861/wp-auto-blog', 'pull_request', 'refs/heads/main', '1', False),
    ('hhj4861/wp-auto-blog', 'workflow_dispatch', 'refs/heads/feature', '1', False),
    ('hhj4861/wp-auto-blog', 'workflow_dispatch', 'refs/heads/main', '', False),
    ('other/repo', 'workflow_dispatch', 'refs/heads/main', '1', False),
])
def test_authorized_public_manual_boundary(tmp_path, monkeypatch, repo, event, ref, opt_in, allowed):
    path = tmp_path / 'event.json'
    path.write_text(json.dumps({'repository': {'private': False, 'default_branch': 'main', 'full_name': repo}}))
    for key, value in {'GITHUB_ACTIONS': 'true', 'GITHUB_EVENT_PATH': str(path),
                       'GITHUB_REPOSITORY': repo, 'GITHUB_EVENT_NAME': event,
                       'GITHUB_REF': ref, 'BLOG_CODEX_PUBLIC_AUTOMATION': opt_in}.items():
        monkeypatch.setenv(key, value)
    if allowed:
        require_private_actions()
    else:
        with pytest.raises(RuntimeError):
            require_private_actions()
