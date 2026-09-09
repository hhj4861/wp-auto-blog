from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

import pytest
import yaml

from src import market_topics as market


def candidate(category='취업', **extra):
    return {'source': market.SOURCE, 'category': category, 'status': 'pending',
            'selected_at': datetime.now(timezone.utc).isoformat(), 'monthly_search': 1200,
            'source_url': 'https://example.go.kr/info', 'organic_domains': ['blog.example'],
            'topic': '시험 준비물 확인 방법', 'keyword': '시험준비물', 'score': 50, **extra}


def test_category_freshness_and_unknown_evidence():
    row = candidate()
    assert market.fresh_market_item(row, '취업')
    assert not market.fresh_market_item(row, '건강')
    assert not market.fresh_market_item(candidate(source='legacy'), '취업')
    assert not market.fresh_market_item(candidate(monthly_search=0), '취업')
    assert not market.fresh_market_item(candidate(organic_domains=[]), '취업')
    assert not market.fresh_market_item(candidate(selected_at=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()), '취업')


def test_enqueue_keeps_other_categories_and_does_not_fallback():
    health = candidate('건강')
    legacy = {'category': '취업', 'status': 'pending', 'topic': 'old'}
    old = candidate()
    queue = [health, legacy, old]
    with pytest.raises(RuntimeError):
        market.enqueue_report(queue, {'category': '취업', 'selected': []})
    assert old['status'] == 'pending'
    market.enqueue_report(queue, {'category': '취업', 'selected': [candidate()]})
    assert old['status'] == 'superseded'
    assert health['status'] == legacy['status'] == 'pending'


def test_inventory_failure_does_not_mean_unique(monkeypatch):
    for key, value in {'WP_GENERAL_URL':'https://trendpulse.blog', 'WP_GENERAL_USERNAME':'u', 'WP_GENERAL_APP_PASSWORD':'p'}.items():
        monkeypatch.setenv(key, value)
    response = Mock()
    response.raise_for_status.side_effect = RuntimeError('unavailable')
    monkeypatch.setattr(market.requests, 'get', lambda *a, **k: response)
    with pytest.raises(RuntimeError):
        market.existing_titles()


def test_selection_requires_measured_keyword_source_and_serp(monkeypatch):
    proposal = {'keyword': '시험준비물', 'topic': '시험준비물 확인 방법', 'category': '취업',
                'intent': '무엇을 준비하나', 'gap': '준비물 표', 'source_url': 'https://example.go.kr/info'}
    monkeypatch.setattr(market, 'fetch_trend_change', lambda *a: None)
    responses = iter([{'candidates':[proposal]}, {'supported':True}])
    monkeypatch.setattr(market, 'ask', lambda *a, **k: next(responses))
    monkeypatch.setattr(market, 'demand_candidates', lambda seeds: {'시험준비물':{'keyword':'시험준비물','monthly':1200,'comp':'높음'}})
    monkeypatch.setattr(market, 'fetch_source', lambda *a: {'url':proposal['source_url'], 'excerpt':'공식 준비물'})
    monkeypatch.setattr(market, 'organic_results', lambda *a: ('google_custom_search', ['independent.example', 'example.go.kr']))
    result = market.select_category('취업', titles=[])
    assert result['selected'][0]['monthly_search'] == 1200
    assert result['selected'][0]['advertising_competition'] == '높음' # not SEO rejection
    assert result['selected'][0]['trend_growth'] is None


def test_no_credentials_or_competition_cannot_pass(monkeypatch):
    monkeypatch.delenv('NAVER_AD_API_KEY', raising=False)
    with pytest.raises(RuntimeError):
        market.demand_candidates(['취업'])
    with pytest.raises(ValueError):
        market.score_candidate(100000, [], '취업')
    assert market.duplicate('건강 검진', '새로운 제목', ['2026 건강검진 대상'])


def test_analysis_uses_subscription_and_retries_invalid_json(monkeypatch):
    from src import codex_client
    client = Mock()
    client.generate.side_effect = ['{"incomplete":', '{"candidates": []}']
    factory = Mock(return_value=client)
    monkeypatch.setattr(codex_client, 'CodexSubscriptionClient', factory)
    monkeypatch.setenv('BLOG_CODEX_HOME', '/tmp/dedicated-test-home')
    monkeypatch.delenv('GOOGLE_AI_API_KEY', raising=False)
    assert market.ask('후보 분석') == {'candidates': []}
    assert factory.call_args.kwargs['home'] == '/tmp/dedicated-test-home'
    assert client.generate.call_count == 2


def test_workflow_selects_before_existing_category_pipeline():
    from pathlib import Path
    workflow = yaml.safe_load(Path('.github/workflows/auto-post.yml').read_text())
    step = next(s for s in workflow['jobs']['post-queue']['steps'] if s.get('name', '').startswith('Run pipeline'))
    command = step['run']
    assert command.index('select_blog_keywords.py') < command.index('python -m src.main')
    assert '--category "$CAT" --enqueue --reuse' in command
    assert 'BLOG_REQUIRE_MARKET_TOPIC=1' in command
    selector = Path('.github/workflows/blog-keyword-select.yml').read_text()
    assert "inputs.top_n || '2'" in selector
    assert 'scaffold_post.py' not in selector


def test_trend_requires_complete_nonzero_baseline():
    assert market.trend_change([10]*7+[20]*7) == 1.0
    assert market.trend_change([0]*7+[20]*7) is None
    assert market.trend_change([10]*5) is None
    assert not market.fresh_market_item(candidate(valid_until='2000-01-01'), '취업')


def test_year_spacing_and_deleted_posts_remain_duplicates(tmp_path, monkeypatch):
    ledger = tmp_path / 'ledger.json'
    monkeypatch.setattr(market, 'LEDGER', ledger)
    item = candidate(keyword='2026 GSAT 일정', topic='2026 GSAT 일정 확인')
    market.record_published_keyword(item, 12, 'https://trendpulse.blog/old')
    market.record_published_keyword(item, 12, 'https://trendpulse.blog/old')
    import json
    assert len(json.loads(ledger.read_text())) == 1
    assert market.duplicate('2027 gsat일정', '새 제목', market.historical_terms())


def test_cli_empty_top_n_and_category_enqueue(tmp_path, monkeypatch):
    import json
    import scripts.select_blog_keywords as cli
    data = tmp_path / 'data'
    data.mkdir()
    queue_path = data / 'topic_queue_general.json'
    legacy = {'topic': 'old health topic', 'category': '건강', 'status': 'pending'}
    queue_path.write_text(json.dumps([legacy]))
    monkeypatch.setattr(cli, 'ROOT', tmp_path)
    monkeypatch.setattr(cli, 'REPORT', data / 'report.json')
    monkeypatch.setattr(cli, 'existing_titles', lambda: [])
    monkeypatch.setenv('SELECT_TOP_N', '')
    monkeypatch.setattr('sys.argv', ['select', '--category', '취업', '--enqueue'])
    calls = []
    def select(category, top_n, titles):
        calls.append((category, top_n))
        return {'category':category, 'selected':[candidate()]}
    monkeypatch.setattr(cli, 'select_category', select)
    assert cli.main() == 0
    assert calls == [('취업', 2)]
    queued = json.loads(queue_path.read_text())
    assert queued[0] == legacy
    assert market.fresh_market_item(queued[1], '취업')
    monkeypatch.setattr(cli, 'select_category', lambda *a: {'category':'취업','selected':[]})
    assert cli.main() == 1
    assert json.loads(queue_path.read_text()) == queued
