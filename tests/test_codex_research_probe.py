import json
from unittest.mock import Mock

import pytest
import yaml
from pathlib import Path

from scripts import check_codex_research as probe


@pytest.mark.parametrize('searched,opened,fetched,expected', [
    (False, [], False, 'no_observed_search'),
    (True, [], False, 'no_official_source_locators'),
    (True, ['https://blog.example/'], False, 'no_official_source_locators'),
    (True, ['https://example.go.kr/info'], False, 'official_html_unavailable'),
    (True, ['https://example.go.kr/info'], True, 'ok'),
])
def test_probe_distinguishes_tool_evidence_and_http_access(monkeypatch, capsys, searched, opened, fetched, expected):
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    client = Mock()
    client.research.return_value = {'text': 'final message must not be logged',
        'searched': searched, 'opened_urls': opened, 'diagnostics': {'completed_web_items': 2}}
    monkeypatch.setattr(probe, 'CodexSubscriptionClient', Mock(return_value=client))
    monkeypatch.setattr(probe, 'fetch_source', lambda _: {'excerpt': 'official'} if fetched else None)
    assert probe.main() == (0 if expected == 'ok' else 1)
    output = capsys.readouterr().out
    report = json.loads(output)
    assert report['reason'] == expected
    assert 'final message' not in output and 'https://' not in output


def test_probe_does_not_expose_unknown_exception(monkeypatch, capsys):
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    monkeypatch.setattr(probe, 'CodexSubscriptionClient', Mock(side_effect=RuntimeError('private diagnostic')))
    assert probe.main() == 1
    assert json.loads(capsys.readouterr().out) == {'reason': 'research_probe_failed'}


@pytest.mark.parametrize('searched,fetched', [(False, True), (True, False), (True, True)])
def test_reported_locator_needs_observed_search_and_independent_fetch(monkeypatch, capsys, searched, fetched):
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    client = Mock()
    client.research.return_value = {'text': '{"candidate_urls":["https://example.go.kr/guide"]}',
                                  'searched': searched, 'opened_urls': []}
    monkeypatch.setattr(probe, 'CodexSubscriptionClient', Mock(return_value=client))
    fetch = Mock(return_value={'excerpt': 'actual HTTP text'} if fetched else None)
    monkeypatch.setattr(probe, 'fetch_source', fetch)
    assert probe.main() == (0 if searched and fetched else 1)
    report = json.loads(capsys.readouterr().out)
    assert report['opened_url_count'] == 0
    if searched:
        assert report['model_reported_locator_count'] == 1
        fetch.assert_called_once_with('https://example.go.kr/guide')
    else:
        fetch.assert_not_called()


def test_research_only_workflow_preserves_auth_cleanup_and_skips_publication():
    workflow = yaml.safe_load(Path('.github/workflows/blog-keyword-select.yml').read_text())
    steps = {step.get('name'): step for step in workflow['jobs']['select']['steps']}
    assert 'inputs.research_check_only == true' in steps['Check native Codex web research']['if']
    for name in ('Discover and verify category topics', 'Save category research report', 'Commit verified report'):
        assert 'inputs.research_check_only != true' in steps[name]['if']
    assert steps['Persist refreshed Codex auth and clean up']['if'] == 'always()'
