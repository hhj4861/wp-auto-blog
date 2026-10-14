from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from src import market_topics as market


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.delenv('BLOG_RESEARCH_SEEDS', raising=False)
    monkeypatch.setattr(market.shared_discovery, 'enabled', lambda: False)


@pytest.mark.parametrize('raw', ['x' * 801, '\n'.join(f'항목{i}' for i in range(9)),
                                 'x' * 81, '!!!', '검색\t어'])
def test_invalid_seeds_stop_before_research(monkeypatch, raw):
    monkeypatch.setenv('BLOG_RESEARCH_SEEDS', raw)
    latest = Mock()
    monkeypatch.setattr(market, 'select_latest_issues', latest)
    with pytest.raises(ValueError):
        market.select_category('생활정보', titles=[])
    latest.assert_not_called()


def test_seed_hints_keep_latest_first(monkeypatch):
    monkeypatch.setattr(market, 'LATEST_LISTING_SELECTION', True)
    monkeypatch.setenv('BLOG_RESEARCH_SEEDS', '대형폐기물\n대형폐기물\n분리배출')
    assert market.research_seed_keywords() == ['대형폐기물', '분리배출']
    latest = {'selected': [{'keyword': 'official latest'}], 'held': [], 'rejected': []}
    monkeypatch.setattr(market, 'select_latest_issues', lambda *a, **kw: latest)
    fallback = Mock()
    monkeypatch.setattr(market, '_select_measured_category', fallback)
    assert market.select_category('생활정보', titles=[]) is latest
    fallback.assert_not_called()


def test_extra_seed_still_requires_measured_demand(monkeypatch):
    monkeypatch.setenv('BLOG_RESEARCH_SEEDS', '대형폐기물')
    monkeypatch.setattr(market.latest_issues, 'discover', lambda *a, **kw: ([], {}))
    measured = Mock(side_effect=market.NoMeasuredDemand())
    monkeypatch.setattr(market, 'demand_candidates', measured)
    with pytest.raises(market.NoMeasuredDemand):
        market._select_measured_category('생활정보', titles=[])
    assert measured.call_args.args[0] == ['대형폐기물', *market.CATEGORIES['생활정보']]


def test_shared_discovery_authority_cannot_be_overridden(monkeypatch):
    monkeypatch.setenv('BLOG_RESEARCH_SEEDS', '대형폐기물')
    monkeypatch.setattr(market.shared_discovery, 'enabled', lambda: True)
    with pytest.raises(ValueError, match='shared discovery'):
        market.research_seed_keywords()


@pytest.mark.parametrize('category,event', [('all', 'workflow_dispatch'),
                                           ('scheduled', 'workflow_dispatch'),
                                           ('생활정보', 'schedule')])
def test_seeds_require_explicit_manual_category(monkeypatch, category, event):
    from scripts import select_blog_keywords as cli
    monkeypatch.setenv('BLOG_RESEARCH_SEEDS', '대형폐기물')
    monkeypatch.setenv('GITHUB_EVENT_NAME', event)
    monkeypatch.setattr('sys.argv', ['select', '--category', category])
    inventory = Mock()
    monkeypatch.setattr(cli, 'existing_titles', inventory)
    with pytest.raises(ValueError, match='manual category'):
        cli.main()
    inventory.assert_not_called()


def test_workflow_passes_hints_as_data_only():
    config = yaml.safe_load(Path('.github/workflows/auto-post.yml').read_text())
    queue = config['jobs']['post-queue']
    assert queue['env']['BLOG_RESEARCH_SEEDS'] == "${{ inputs.research_seeds || '' }}"
    for step in queue['steps']:
        assert 'inputs.research_seeds' not in step.get('run', '')
    assert 'BLOG_RESEARCH_SEEDS' not in config['jobs']['post-general']['env']


def test_manual_hints_trigger_fresh_research_even_with_reusable_stock(tmp_path, monkeypatch):
    import json
    from scripts import select_blog_keywords as cli
    monkeypatch.setenv('BLOG_RESEARCH_SEEDS', '대형폐기물')
    monkeypatch.setenv('GITHUB_EVENT_NAME', 'workflow_dispatch')
    monkeypatch.setattr('sys.argv', ['select', '--category', '생활정보', '--reuse'])
    monkeypatch.setattr(cli, 'ROOT', tmp_path)
    report_path = tmp_path / 'report.json'
    report_path.write_text(json.dumps({'생활정보': {'category': '생활정보', 'selected': [
        {'keyword': 'old', 'topic': 'old topic'}]}}))
    monkeypatch.setattr(cli, 'REPORT', report_path)
    monkeypatch.setattr(cli, 'existing_titles', lambda: [])
    monkeypatch.setattr(cli, 'fresh_market_item', lambda *a: True)
    monkeypatch.setattr(cli, 'duplicate', lambda *a: False)
    monkeypatch.setattr(market, 'LATEST_LISTING_SELECTION', False)
    reuse = Mock()
    monkeypatch.setattr(cli, '_sources_accessible', reuse)
    research = Mock(return_value={'category': '생활정보', 'selected': [], 'rejected': [], 'held': []})
    monkeypatch.setattr(cli, 'select_category', research)
    assert cli.main() == 1
    research.assert_called_once()
    reuse.assert_not_called()
