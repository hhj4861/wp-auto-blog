"""Live check must fail closed and have no publishing credentials or write permissions."""
import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from scripts import check_claude_fallback as probe
from src import codex_search
from src.codex_client import CodexResponseError


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    monkeypatch.delenv('MARKET_SEARCH_PROVIDER', raising=False)
    def forbidden_primary(*args, **kwargs):
        raise AssertionError('Diagnostic must never call live Codex')
    monkeypatch.setattr(codex_search, '_codex_native_search', forbidden_primary)

    client = Mock()
    client.generate.side_effect = ['{"verified":true}', '{"sticky":true}']
    client.search.return_value = [{'url': 'https://example.com/article', 'title': 'Actual result title', 'snippet': ''}]
    client.research.return_value = {'provider': 'claude_web', 'searched': True,
                                   'opened_urls': ['https://example.com/detail']}
    monkeypatch.setattr(probe.claude_subscription, 'ClaudeSubscriptionClient', Mock(return_value=client))
    return client


def test_check_uses_live_client_callbacks_and_restores_process_configuration(client, monkeypatch):
    monkeypatch.setenv('BLOG_CODEX_HOME', '/original/home')
    monkeypatch.setenv('BLOG_CODEX_USAGE_FALLBACK', 'off')
    report = probe.check()
    assert report['status'] == 'ok'
    assert report['simulated_codex_usage_limit'] is report['live_claude'] is True
    assert report['primary_calls'] == 1
    assert report['search_provider'] == 'claude_native_search'
    client.search.assert_called_once_with(probe.QUERY)
    assert os.environ['BLOG_CODEX_HOME'] == '/original/home'
    assert os.environ['BLOG_CODEX_USAGE_FALLBACK'] == 'off'
    assert 'MARKET_SEARCH_PROVIDER' not in os.environ


@pytest.mark.parametrize('stage', ['generate', 'search', 'research'])
def test_failed_live_stage_never_reports_success_or_emits_private_output(client, monkeypatch, capsys, stage):
    getattr(client, stage).side_effect = CodexResponseError('authentication_required', 'private raw output')
    assert probe.main() == 1
    raw = capsys.readouterr().out
    report = json.loads(raw)
    assert report['status'] == 'failed'
    assert 'private raw output' not in raw


def test_unobserved_research_is_not_live_success(client, capsys):
    client.research.return_value['searched'] = False
    assert probe.main() == 1
    assert json.loads(capsys.readouterr().out)['reason'] == 'invalid_schema'


def test_workflow_has_only_subscription_secret_and_read_permission():
    workflow = yaml.safe_load(Path('.github/workflows/claude-fallback-check.yml').read_text())
    assert workflow['permissions'] == {'contents': 'read'}
    job = workflow['jobs']['check']
    assert 'github.event.repository.default_branch' in job['if']
    secret_steps = [s for s in job['steps'] if 'CLAUDE_CODE_OAUTH_TOKEN' in s.get('env', {})]
    assert len(secret_steps) == 1
    assert set(secret_steps[0]['env']) == {'CLAUDE_CODE_OAUTH_TOKEN'}
    raw = json.dumps(workflow)
    assert 'WP_GENERAL' not in raw and 'TELEGRAM' not in raw and 'API_KEY' not in raw
    assert job['steps'][0]['with']['persist-credentials'] is False
