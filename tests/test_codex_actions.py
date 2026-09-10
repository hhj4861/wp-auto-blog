import json
from unittest.mock import Mock

import pytest
import yaml

from scripts.run_codex_worker import command, verify_published
from scripts.codex_worker_auth import validate_auth
from src.codex_client import require_private_actions

REGULAR_CATEGORY_SCHEDULES = ('0 2 * * 1,3,5', '0 2 * * 2,4', '0 2 * * 6')
ONE_TIME_CATEGORY_CRON = '37 6 10 9 *'
ONE_TIME_CATEGORY_DATE = '2026-09-10'


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
    assert [entry['cron'] for entry in schedules] == [*REGULAR_CATEGORY_SCHEDULES, ONE_TIME_CATEGORY_CRON]
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


def _queue_job():
    from pathlib import Path
    return yaml.safe_load(Path('.github/workflows/auto-post.yml').read_text())['jobs']['post-queue']


def test_one_time_categories_are_serial_and_refresh_main_before_authentication():
    from pathlib import Path
    job = _queue_job()
    assert ONE_TIME_CATEGORY_CRON in job['if']
    assert all(schedule in job['if'] for schedule in REGULAR_CATEGORY_SCHEDULES)
    assert 'strategy' not in job
    assert job['env']['BLOG_SCHEDULE_BATCH'] == "${{ github.event.schedule == '" + ONE_TIME_CATEGORY_CRON + "' && '1' || '' }}"
    assert f"github.event.schedule == '{ONE_TIME_CATEGORY_CRON}' && 'codex'" in job['env']['BLOG_WRITER_PROVIDER']
    assert job['timeout-minutes'] == "${{ github.event.schedule == '" + ONE_TIME_CATEGORY_CRON + "' && 180 || 60 }}"
    steps = job['steps']
    checkout = next(step for step in steps if step.get('name') == 'Checkout repository')
    assert checkout['with']['ref'] == "${{ github.event_name == 'schedule' && 'main' || github.ref }}"
    names = [step.get('name') for step in steps]
    assert names.index('Guard one-time category schedule') < names.index('Restore Codex authentication')
    guard = next(step for step in steps if step.get('name') == 'Guard one-time category schedule')
    assert guard['if'] == f"github.event.schedule == '{ONE_TIME_CATEGORY_CRON}'"
    artifact = next(step for step in steps if step.get('name') == 'Upload logs')
    assert artifact['with']['name'] == 'pipeline-logs-queue-${{ github.run_id }}'
    assert sum(step.get('run') == 'python scripts/codex_worker_auth.py restore' for step in steps) == 1
    assert sum(step.get('run') == 'python scripts/codex_worker_auth.py persist' for step in steps) == 1
    verification = next(step for step in steps if step.get('name') == 'Verify Codex publication result')
    assert "env.BLOG_SCHEDULE_BATCH != '1'" in verification['if']
    pipeline = next(step for step in steps if step.get('name', '').startswith('Run pipeline'))
    assert pipeline['timeout-minutes'] == "${{ github.event.schedule == '" + ONE_TIME_CATEGORY_CRON + "' && 165 || 50 }}"
    retry = yaml.safe_load(Path('.github/workflows/auto-post.yml').read_text())['jobs']['retry-on-waf-block']
    assert f"github.event.schedule != '{ONE_TIME_CATEGORY_CRON}'" in retry['if']


def _run_queue_shell(tmp_path, *, batch=False, schedule='', input_category='', fail_stage='', fail_category=''):
    """Execute the actual Actions shell with fixed event values and no real Python/API."""
    import os
    import subprocess
    script = next(step['run'] for step in _queue_job()['steps']
                  if step.get('name', '').startswith('Run pipeline'))
    script = script.replace('${{ github.event.inputs.category }}', input_category)
    script = script.replace('${{ github.event.schedule }}', schedule)
    assert '${{' not in script
    calls = tmp_path / 'calls'
    fake_python = tmp_path / 'python'
    fake_python.write_text('#!/bin/sh\n'
        'printf "%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n" "$BLOG_CATEGORY" "$BLOG_RESULT_PATH" '
        '"$BLOG_CODEX_HOME" "${BLOG_REQUIRE_MARKET_TOPIC-}" "${BLOG_REQUIRE_PUBLICATION_RESULT-}" "$*" >> "$TEST_CALLS"\n'
        'case "$1" in scripts/select_blog_keywords.py) STAGE=selector;; -m) STAGE=main;; scripts/verify_codex_run.py) STAGE=verify;; *) exit 9;; esac\n'
        'if [ "$STAGE" = "$FAIL_STAGE" ] && [ "$BLOG_CATEGORY" = "$FAIL_CATEGORY" ]; then exit 7; fi\n'
        'exit 0\n')
    fake_python.chmod(0o700)
    result = subprocess.run(['bash', '-e', '-c', script], capture_output=True, text=True, timeout=5,
        env={'PATH': str(tmp_path) + os.pathsep + '/usr/bin:/bin', 'BLOG_RESUME_DRAFT_ID': '',
             'BLOG_SCHEDULE_BATCH': '1' if batch else '', 'TEST_CALLS': str(calls),
             'BLOG_CATEGORY': '', 'BLOG_RESULT_PATH': str(tmp_path / 'blog-result.json'),
             'BLOG_CODEX_HOME': str(tmp_path / 'codex-home'), 'RUNNER_TEMP': str(tmp_path),
             'FAIL_STAGE': fail_stage, 'FAIL_CATEGORY': fail_category})
    keys = ('category', 'path', 'home', 'market', 'strict_result', 'argv')
    return result, [dict(zip(keys, line.split('\t'))) for line in calls.read_text().splitlines()] if calls.exists() else []


def test_single_batch_selects_publishes_and_verifies_three_categories_with_one_auth_home(tmp_path):
    result, calls = _run_queue_shell(tmp_path, batch=True, schedule=ONE_TIME_CATEGORY_CRON,
                                    input_category='batch must take precedence')
    assert result.returncode == 0, result.stderr
    assert len(calls) == 9
    for index, category in enumerate(('생활정보', '취업', '건강'), 1):
        subset = calls[(index - 1) * 3:index * 3]
        assert [call['argv'] for call in subset] == [
            f'scripts/select_blog_keywords.py --category {category} --enqueue --reuse',
            f'-m src.main --mode general --from-queue --auto-publish --category {category}',
            'scripts/verify_codex_run.py']
        assert all(call['category'] == category and call['path'] == str(tmp_path / f'blog-result-category-{index}.json')
                   and call['strict_result'] == '1' for call in subset)
        assert subset[1]['market'] == subset[2]['market'] == '1'
    assert {call['home'] for call in calls} == {str(tmp_path / 'codex-home')}
    assert result.stdout.count('Category publication verified:') == 3


@pytest.mark.parametrize('stage,failed_calls', [('selector', 1), ('main', 2), ('verify', 3)])
def test_batch_failure_stops_that_category_but_continues_and_returns_failure(tmp_path, stage, failed_calls):
    result, calls = _run_queue_shell(tmp_path, batch=True, schedule=ONE_TIME_CATEGORY_CRON,
                                    fail_stage=stage, fail_category='취업')
    assert result.returncode == 1
    assert len([call for call in calls if call['category'] == '취업']) == failed_calls
    assert len([call for call in calls if call['category'] == '생활정보']) == 3
    assert len([call for call in calls if call['category'] == '건강']) == 3
    assert calls[-1]['argv'] == 'scripts/verify_codex_run.py' and calls[-1]['category'] == '건강'
    assert 'Category publication failed or held: 취업' in result.stdout
    assert result.stdout.count('Category publication verified:') == 2
    assert {call['home'] for call in calls} == {str(tmp_path / 'codex-home')}


@pytest.mark.parametrize('schedule,input_category,expected', [
    (REGULAR_CATEGORY_SCHEDULES[0], '', '생활정보'),
    (REGULAR_CATEGORY_SCHEDULES[1], '', '취업'),
    (REGULAR_CATEGORY_SCHEDULES[2], '', '건강'),
    ('', '건강', '건강'), ('', '', '생활정보'),
])
def test_regular_and_manual_queue_categories_remain_unchanged(tmp_path, schedule, input_category, expected):
    result, calls = _run_queue_shell(tmp_path, schedule=schedule,
                                    input_category=input_category)
    assert result.returncode == 0, result.stderr
    assert [call['argv'] for call in calls] == [f'scripts/select_blog_keywords.py --category {expected} --enqueue --reuse',
                     f'-m src.main --mode general --from-queue --auto-publish --category {expected}']
    assert calls[0]['market'] == '' and calls[1]['market'] == '1'
    assert all(call['strict_result'] == '' for call in calls)


def test_normal_selector_failure_does_not_publish(tmp_path):
    result, calls = _run_queue_shell(tmp_path, input_category='건강', fail_stage='selector')
    assert result.returncode == 7
    assert [call['argv'] for call in calls] == ['scripts/select_blog_keywords.py --category 건강 --enqueue --reuse']


@pytest.mark.parametrize('exists', [False, True])
@pytest.mark.parametrize('required', [False, True])
def test_strict_batch_verification_rejects_missing_or_empty_result_without_network(tmp_path, monkeypatch, exists, required):
    import importlib
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path('scripts').resolve()))
    verifier = importlib.import_module('scripts.verify_codex_run')
    monkeypatch.setattr(verifier, 'load_dotenv', lambda: None)
    monkeypatch.delenv('BLOG_RESUME_DRAFT_ID', raising=False)
    monkeypatch.setenv('BLOG_REQUIRE_PUBLICATION_RESULT', '1' if required else '')
    path = tmp_path / 'result.json'
    if exists:
        path.write_text('[]')
    monkeypatch.setenv('BLOG_RESULT_PATH', str(path))
    session = Mock(side_effect=AssertionError('No WordPress request without a result'))
    monkeypatch.setattr(verifier.requests, 'Session', session)
    if required:
        with pytest.raises(RuntimeError, match='Required publication result is'):
            verifier.main()
    else:
        verifier.main()
    session.assert_not_called()


@pytest.mark.parametrize('date,attempt,allowed', [
    (ONE_TIME_CATEGORY_DATE, '1', True), (ONE_TIME_CATEGORY_DATE, '2', False),
    (ONE_TIME_CATEGORY_DATE, '', False), ('2027-09-10', '1', False),
    ('2026-09-11', '1', False), ('2026-09-09', '1', False),
])
def test_one_time_date_and_first_attempt_guard_executes_before_any_work(tmp_path, date, attempt, allowed):
    import os
    import subprocess
    guard = next(step for step in _queue_job()['steps']
                 if step.get('name') == 'Guard one-time category schedule')
    fake_date = tmp_path / 'date'
    fake_date.write_text('#!/bin/sh\n'
                         'test "$1" = "-u" || exit 9\n'
                         'printf "%s\\n" "$TEST_DATE"\n')
    fake_date.chmod(0o700)
    result = subprocess.run(['bash', '-e', '-c', guard['run'] + '\nprintf "guard passed\\n"'],
        capture_output=True, text=True, timeout=5,
        env={'PATH': str(tmp_path) + os.pathsep + '/usr/bin:/bin',
             'TEST_DATE': date, 'GITHUB_RUN_ATTEMPT': attempt})
    assert (result.returncode == 0) is allowed
    assert ('guard passed' in result.stdout) is allowed


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
