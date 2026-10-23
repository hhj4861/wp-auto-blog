"""Quota recovery contracts; synthetic transports never publish or use real credentials."""
import json
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest
import yaml

from src import subscription_fallback as policy
from src import claude_subscription as claude
from src import codex_client, codex_search, market_search, analysis_runtime


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    monkeypatch.setenv('BLOG_CODEX_USAGE_FALLBACK', 'claude')
    monkeypatch.setenv('CLAUDE_CODE_OAUTH_TOKEN', 'synthetic-oauth')
    monkeypatch.setattr(policy, '_EXHAUSTED', set())


def codex(tmp_path, monkeypatch):
    monkeypatch.setattr(codex_client.shutil, 'which', lambda name: '/bin/codex')
    return codex_client.CodexSubscriptionClient(home=str(tmp_path), model='test', timeout=2)


def final(text='OK', **extra):
    return {'type': 'result', 'subtype': 'success', 'is_error': False, 'result': text, **extra}


def stream(*events):
    return '\n'.join(json.dumps(event) for event in events)


def search_events(query='query', rows=None, *, error=False):
    if rows is None:
        rows = [{'url': 'https://example.com/article', 'title': 'Actual tool title'}]
    return [
        {'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'id': 'search1', 'name': 'WebSearch', 'input': {'query': query}}]}},
        {'type': 'user', 'message': {'content': [
            {'type': 'tool_result', 'tool_use_id': 'search1', 'is_error': error, 'content': 'untrusted'}]},
         'tool_use_result': {'query': query, 'results': [{'tool_use_id': 'native1', 'content': rows}]}},
        final('{"candidate_urls":["https://example.com/model-proposed"]}')]


@pytest.mark.parametrize('method', ['generate', 'research'])
def test_quota_recovers_inside_validation_and_sticks(tmp_path, monkeypatch, method):
    client = codex(tmp_path, monkeypatch)
    primary = Mock(side_effect=codex_client.CodexRequestError(1, 'usage limit'))
    monkeypatch.setattr(client, '_run', primary)
    backup = Mock()
    backup.generate.return_value = '{"ok":true}'
    backup.research.return_value = {'text': 'OK', 'searched': True, 'opened_urls': []}
    monkeypatch.setattr(claude, 'ClaudeSubscriptionClient', Mock(return_value=backup))
    operation = getattr(client, method)

    @analysis_runtime.selection_scope
    def selection(category):
        for _ in range(2):
            result = analysis_runtime.validated_call(operation, 'prompt')
            assert result
        return {'selected': ['kept']}

    report = selection('건강')
    assert report['selected'] == ['kept']
    assert 'operational_error' not in report
    assert primary.call_count == 1
    assert getattr(backup, method).call_count == 2
    assert client.last_provider == 'claude'
    if method == 'research':
        assert result_provider(client) == 'claude_web'


def result_provider(client):
    return client.research('prompt')['provider']


@pytest.mark.parametrize('reason', ['unauthorized', 'refresh_token_reused', 'network_or_service',
    'model_unavailable', 'prompt_too_large', 'empty_response', 'invalid_schema', 'timeout'])
def test_only_quota_can_switch(tmp_path, monkeypatch, reason):
    client = codex(tmp_path, monkeypatch)
    monkeypatch.setattr(client, '_run', Mock(side_effect=codex_client.CodexResponseError(reason, 'safe')))
    backup = Mock()
    monkeypatch.setattr(claude, 'ClaudeSubscriptionClient', backup)
    with pytest.raises(codex_client.CodexResponseError) as error:
        client.generate('prompt')
    assert error.value.reason == reason
    backup.assert_not_called()


@pytest.mark.parametrize('setting', ['', 'off', 'anthropic'])
def test_disabled_policy_keeps_quota_failure(tmp_path, monkeypatch, setting):
    monkeypatch.setenv('BLOG_CODEX_USAGE_FALLBACK', setting)
    client = codex(tmp_path, monkeypatch)
    monkeypatch.setattr(client, '_run', Mock(side_effect=codex_client.CodexRequestError(1, 'usage_limit')))
    with pytest.raises(codex_client.CodexRequestError):
        client.generate('prompt')
    assert not policy.exhausted(client.home, client.model)


def test_success_uses_primary_without_claude_or_oauth(tmp_path, monkeypatch):
    monkeypatch.delenv('CLAUDE_CODE_OAUTH_TOKEN')
    client = codex(tmp_path, monkeypatch)
    monkeypatch.setattr(client, '_run', Mock(return_value={'text': 'primary'}))
    assert client.generate('prompt') == 'primary'
    assert client.last_provider == 'codex'


def test_arbitrary_usage_exception_cannot_switch():
    with pytest.raises(ValueError):
        policy.run(Mock(side_effect=ValueError('usage limit')), Mock(), home='h', model='m')


def test_missing_oauth_stops_without_api_billing(monkeypatch):
    monkeypatch.delenv('CLAUDE_CODE_OAUTH_TOKEN')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'must-not-be-used')
    with pytest.raises(codex_client.CodexResponseError) as error:
        claude.ClaudeSubscriptionClient()
    assert error.value.reason == 'authentication_required'


def test_failed_backup_is_not_replayed_against_primary(tmp_path, monkeypatch):
    client = codex(tmp_path, monkeypatch)
    primary = Mock(side_effect=codex_client.CodexRequestError(1, 'usage limit'))
    monkeypatch.setattr(client, '_run', primary)
    backup = Mock()
    backup.generate.side_effect = codex_client.CodexResponseError('usage_limit', 'Claude quota')
    monkeypatch.setattr(claude, 'ClaudeSubscriptionClient', Mock(return_value=backup))
    for _ in range(2):
        with pytest.raises(codex_client.CodexResponseError):
            client.generate('prompt')
    assert primary.call_count == 1
    assert backup.generate.call_count == 2


def test_runner_marker_is_bound_to_run_attempt_home_and_model(tmp_path, monkeypatch):
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.setenv('RUNNER_TEMP', str(tmp_path))
    monkeypatch.setenv('BLOG_CODEX_USAGE_STATE', str(tmp_path / 'marker'))
    monkeypatch.setenv('GITHUB_RUN_ID', '123')
    monkeypatch.setenv('GITHUB_RUN_ATTEMPT', '1')
    policy.run(Mock(side_effect=codex_client.CodexRequestError(1, 'usage limit')), lambda: 'backup', home='h', model='m')
    policy._EXHAUSTED.clear()  # Simulate the next Python subprocess.
    assert policy.exhausted('h', 'm')
    assert not policy.exhausted('other', 'm')
    assert not policy.exhausted('h', 'other')
    monkeypatch.setenv('GITHUB_RUN_ATTEMPT', '2')
    assert not policy.exhausted('h', 'm')
    monkeypatch.setenv('GITHUB_RUN_ATTEMPT', '1')
    monkeypatch.setenv('GITHUB_RUN_ID', '456')
    assert not policy.exhausted('h', 'm')


def test_marker_outside_runner_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.setenv('RUNNER_TEMP', str(tmp_path / 'runner'))
    monkeypatch.setenv('BLOG_CODEX_USAGE_STATE', str(tmp_path / 'unrelated'))
    assert policy._state_path() is None


def test_exhausted_images_use_existing_editorial_fallback(tmp_path, monkeypatch):
    client = codex(tmp_path, monkeypatch)
    policy._mark(client.home, client.model)
    primary = Mock()
    monkeypatch.setattr(client, '_run', primary)
    with pytest.raises(codex_client.CodexResponseError) as error:
        client.generate_image('image')
    assert error.value.reason == 'usage_limit'
    primary.assert_not_called()


def test_actual_search_events_are_distinct_from_model_claims():
    result = claude._events(stream(*search_events()), web=True, query='query')
    assert result['searched'] is True
    assert result['search_rows'] == [{'url': 'https://example.com/article', 'title': 'Actual tool title', 'snippet': ''}]
    assert result['opened_urls'] == []
    assert result['provider'] == 'claude_web'


@pytest.mark.parametrize('events', [
    [final('{"searched":true,"results":[{"url":"https://example.com"}]}')],
    search_events(error=True),
    [{'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'unbound'}]}}, final()],
    search_events(query='different'),
    search_events()[:-1] + [final(is_error=True)],
    search_events()[:-1] + [final(subtype='error_max_turns')],
    [final(), {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'x', 'name': 'Bash', 'input': {}}]}}],
])
def test_unverified_or_failed_search_cannot_be_evidence(events):
    with pytest.raises(codex_client.CodexResponseError):
        claude._events(stream(*events), web=True, query='query')


def test_webfetch_requires_matching_successful_url():
    events = search_events()[:-1] + [
        {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': 'fetch', 'name': 'WebFetch',
          'input': {'url': 'https://example.com/detail', 'prompt': 'read'}}]}},
        {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'fetch', 'is_error': False}]},
         'tool_use_result': {'code': 200, 'url': 'https://example.com/detail'}}, final()]
    assert claude._events(stream(*events), web=True)['opened_urls'] == ['https://example.com/detail']
    events[-2]['tool_use_result']['url'] = 'https://example.com/model-proposed'
    assert claude._events(stream(*events), web=True)['opened_urls'] == []


def test_native_quota_uses_claude_with_honest_title_only_rows(tmp_path, monkeypatch):
    monkeypatch.setenv('BLOG_CODEX_HOME', str(tmp_path))
    monkeypatch.setenv('MARKET_SEARCH_PROVIDER', 'codex_native_search')
    primary = Mock(side_effect=codex_search.NativeSearchError('usage_limit'))
    monkeypatch.setattr(codex_search, '_codex_native_search', primary)
    backup = Mock()
    backup.search.return_value = claude._events(stream(*search_events()), web=True, query='query')['search_rows']
    monkeypatch.setattr(claude, 'ClaudeSubscriptionClient', Mock(return_value=backup))
    for _ in range(2):
        provider, rows = market_search.search_results('query')
        assert provider == 'claude_native_search'
        assert rows[0]['snippet'] == ''
        assert rows[0]['title'] == 'Actual tool title'
    assert primary.call_count == 1


def test_transport_isolated_environment_tools_and_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(claude.importlib.util, 'find_spec', lambda name: None)
    monkeypatch.setattr(claude.shutil, 'which', lambda name: '/bin/claude')
    for name in ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'WP_GENERAL_APP_PASSWORD', 'CODEX_HOME'):
        monkeypatch.setenv(name, 'sensitive-do-not-forward')
    seen = {}
    def launch(command, **kwargs):
        seen.update(command=command, **kwargs)
        return Mock(returncode=0, communicate=Mock(return_value=(stream(final()), '')))
    monkeypatch.setattr(claude.subprocess, 'Popen', launch)
    client = claude.ClaudeSubscriptionClient(timeout=2)
    assert client.generate('literal $(do-not-execute)') == 'OK'
    assert seen['command'][seen['command'].index('--tools')+1] == ''
    assert '--no-session-persistence' in seen['command']
    assert '--strict-mcp-config' in seen['command']
    assert 'literal $(do-not-execute)' not in seen['command']
    assert seen['env']['CLAUDE_CODE_OAUTH_TOKEN'] == 'synthetic-oauth'
    assert 'sensitive-do-not-forward' not in seen['env'].values()
    assert not Path(seen['cwd']).exists()


def test_transport_timeout_reaps_process(monkeypatch):
    monkeypatch.setattr(claude.importlib.util, 'find_spec', lambda name: None)
    monkeypatch.setattr(claude.shutil, 'which', lambda name: '/bin/claude')
    process = Mock(pid=123, communicate=Mock(side_effect=[subprocess.TimeoutExpired('claude', 2), ('', '')]))
    monkeypatch.setattr(claude.subprocess, 'Popen', Mock(return_value=process))
    kill = Mock()
    monkeypatch.setattr(claude.os, 'killpg', kill)
    with pytest.raises(codex_client.CodexResponseError) as error:
        claude.ClaudeSubscriptionClient(timeout=2).generate('prompt')
    assert error.value.reason == 'timeout'
    kill.assert_called_once()
    assert process.communicate.call_count == 2


def test_workflows_enable_only_subscription_quota_fallback():
    for file, jobs in [('auto-post.yml', ('post-general', 'post-queue')), ('blog-keyword-select.yml', ('select',))]:
        workflow = yaml.safe_load(Path('.github/workflows', file).read_text())
        for job_name in jobs:
            job = workflow['jobs'][job_name]
            assert job['env']['BLOG_CODEX_USAGE_FALLBACK'] == 'claude'
            assert any('BLOG_CODEX_USAGE_STATE=$RUNNER_TEMP/' in step.get('run', '') for step in job['steps'])
            steps = [step for step in job['steps'] if 'select_blog_keywords.py' in step.get('run', '')]
            if steps:
                assert steps[0]['env']['CLAUDE_CODE_OAUTH_TOKEN'] == '${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}'
        if file == 'blog-keyword-select.yml':
            assert any('claude-agent-sdk' in step.get('run', '') for step in job['steps'])


@pytest.mark.parametrize("method", ["generate", "research"])
def test_remote_fixed_provider_contract_does_not_mislabel_claude(tmp_path, monkeypatch, method):
    client = codex(tmp_path, monkeypatch)
    monkeypatch.setattr(client, '_run', Mock(side_effect=codex_client.CodexRequestError(1, 'usage limit')))
    backup = Mock()
    monkeypatch.setattr(claude, 'ClaudeSubscriptionClient', backup)
    with pytest.raises(codex_client.CodexRequestError):
        getattr(client, method)('remote contract', allow_usage_fallback=False)
    backup.assert_not_called()


def test_real_subprocess_quota_recovers_validated_json(tmp_path, monkeypatch):
    import sys
    home = tmp_path / 'codex-auth'
    home.mkdir()
    primary = tmp_path / 'codex-stand-in'
    primary.write_text(f'#!{sys.executable}\nimport sys\nprint("usage_limit", file=sys.stderr)\nsys.exit(1)\n')
    backup = tmp_path / 'claude-stand-in'
    backup.write_text(f'#!{sys.executable}\n' + """import sys, os, json
assert os.environ['CLAUDE_CODE_OAUTH_TOKEN'] == 'synthetic-oauth'
assert 'ANTHROPIC_API_KEY' not in os.environ
assert 'WP_GENERAL_APP_PASSWORD' not in os.environ
assert sys.stdin.read() == '완결된 JSON만 반환'
assert sys.argv[sys.argv.index('--tools') + 1] == ''
print(json.dumps({'type':'result','subtype':'success','is_error':False,'result':'{"ok":true}'}))
""")
    for path in (primary, backup):
        path.chmod(0o700)
    monkeypatch.setattr(claude.importlib.util, 'find_spec', lambda name: None)
    monkeypatch.setattr(codex_client.shutil, 'which', lambda name: str(primary if name == 'codex' else backup))
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'private-api-key')
    monkeypatch.setenv('WP_GENERAL_APP_PASSWORD', 'private-wp-password')
    client = codex_client.CodexSubscriptionClient(home=str(home), timeout=5)
    assert analysis_runtime.validated_call(client.generate, '완결된 JSON만 반환', analysis_runtime.parse_json) == {'ok': True}
    assert client.last_provider == 'claude'


def test_search_slots_are_not_backfilled_after_invalid_first_ten():
    rows = [{'url': 'not-a-url', 'title': 'invalid'}] * 10 + [
        {'url': 'https://example.com/later', 'title': 'Must not fill missing first-ten slots'}]
    result = claude._events(stream(*search_events(rows=rows)), web=True, query='query')
    assert result['search_rows'] == []


def test_observed_standard_websearch_mode_preserves_exact_query_binding():
    events = search_events(query='Claude Code official documentation')
    events[0]['message']['content'][0]['input']['mode'] = 'standard'
    result = claude._events(stream(*events), web=True, query='Claude Code official documentation')
    assert result['searched'] is True
    assert result['search_rows'] == [{'url': 'https://example.com/article',
                                      'title': 'Actual tool title', 'snippet': ''}]


@pytest.mark.parametrize('mode', [None, 'deep', 'research', '', True, 1, {}, []])
def test_unrecognized_websearch_mode_is_not_accepted(mode):
    events = search_events()
    events[0]['message']['content'][0]['input']['mode'] = mode
    with pytest.raises(codex_client.CodexResponseError) as error:
        claude._events(stream(*events), web=True, query='query')
    assert error.value.reason == 'unexpected_search_query'


@pytest.mark.parametrize('extra', [
    {'query': 'different', 'mode': 'standard'},
    {'mode': 'standard', 'allowed_domains': ['example.com']},
    {'mode': 'standard', 'blocked_domains': ['example.com']},
    {'mode': 'standard', 'unknown_option': 'anything'},
])
def test_standard_mode_does_not_relax_query_filters_or_unknown_arguments(extra):
    events = search_events()
    events[0]['message']['content'][0]['input'].update(extra)
    with pytest.raises(codex_client.CodexResponseError) as error:
        claude._events(stream(*events), web=True, query='query')
    assert error.value.reason == 'unexpected_search_query'
