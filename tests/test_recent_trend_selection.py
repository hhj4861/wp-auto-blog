"""Exercise actual market selection and its downstream freshness gates with synthetic signals."""
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock
import json
from pathlib import Path

import pytest
import yaml

from src import market_topics as market, recent_search_trend as trend
from tests.test_market_topics import (isolated_market_history, candidate, analysis, evidence, organic_sample)
from tests.test_recent_search_trend import series, credentials


def signal(key, rising=True):
    now = datetime.now(timezone.utc)
    return trend.analyze(key, series(None if rising else [20] * 15, now=now), now)


def test_low_monthly_candidates_retained_only_when_daily_client_configured(monkeypatch):
    for name in ('NAVER_AD_CUSTOMER_ID', 'NAVER_AD_API_KEY', 'NAVER_AD_SECRET_KEY'):
        monkeypatch.setenv(name, 'test')
    monkeypatch.setattr(market, 'fetch_keyword_stats', lambda _: [
        {'keyword': '엑셀신규설정', 'monthly': 80}, {'keyword': '엑셀사용법', 'monthly': 1200},
        {'keyword': '엑셀마스킹', 'monthly': 0, 'monthly_status': 'unavailable'}])
    monkeypatch.delenv('NAVER_API_HUB_CLIENT_ID', raising=False)
    monkeypatch.delenv('NAVER_API_HUB_CLIENT_SECRET', raising=False)
    assert list(market.demand_candidates(['엑셀'])) == ['엑셀사용법']
    credentials(monkeypatch)
    assert list(market.demand_candidates(['엑셀'])) == ['엑셀신규설정', '엑셀사용법']


def test_recent_rise_precedes_high_volume_and_unverified_small_terms_are_excluded():
    key = '엑셀신규설정'
    rows = {key: {'keyword': key, 'monthly': 80, 'recent_search_trend': signal(key)},
            '엑셀사용법': {'keyword': '엑셀사용법', 'monthly': 50000},
            '엑셀미검증': {'keyword': '엑셀미검증', 'monthly': 80}}
    result = market.candidate_pool(rows, [], '생산성')
    assert [row['keyword'] for row in result] == [key, '엑셀사용법']
    assert market.candidate_pool(rows, [key], '생산성')[0]['keyword'] == '엑셀사용법'


def test_probe_reserves_capacity_for_small_terms_and_binds_exact_queries(monkeypatch):
    rows = {f'엑셀설정{i}': {'keyword': f'엑셀설정{i}', 'monthly': 1000 + i} for i in range(130)}
    rows['엑셀신규설정'] = {'keyword': '엑셀신규설정', 'monthly': 80}
    c = Mock(enabled=True, now=datetime.now(timezone.utc), cache={})
    c.collect.side_effect = lambda keys: {key: signal(key) for key in keys}
    market.enrich_recent_trends(rows, [], '생산성', c)
    queried = c.collect.call_args.args[0]
    assert len(queried) == 120
    assert '엑셀신규설정' in queried
    assert rows['엑셀신규설정']['recent_search_trend']['keyword'] == '엑셀신규설정'
    assert sum(row['recent_search_trend']['status'] == 'budget_exhausted' for row in rows.values()) == 11


def test_complete_selection_low_monthly_rise_passes_gates_and_queue_priority(monkeypatch):
    key = '시험준비물'
    now = datetime.now(timezone.utc)
    s = signal(key)
    monkeypatch.setattr(market, 'demand_candidates', lambda _: {key: {'keyword': key, 'monthly': 80}})
    collector = Mock(enabled=True, now=now, cache={})
    collector.collect.return_value = {key: s}
    collector.summary.return_value = {'status': 'checked'}
    monkeypatch.setattr(market.recent, 'Collector', lambda _: collector)
    monkeypatch.setattr(market, 'search_results', lambda _: ('google_custom_search', organic_sample(key)))
    monkeypatch.setattr(market, 'candidate_sources', lambda *a, **k: [evidence()])
    monkeypatch.setattr(market, 'ask', lambda prompt: {'candidates': [{'keyword': key}]} if '후보:' in prompt else analysis())
    google = Mock(side_effect=AssertionError('daily signal must not be counted twice'))
    monkeypatch.setattr(market, 'fetch_trend_change', google)
    report = market.select_category('취업', top_n=1, titles=[])
    item = report['selected'][0]
    assert item['monthly_search'] == 80
    assert item['score_components']['demand'] <= 15
    assert item['score_components']['recent_trend'] == s['points']
    assert market.fresh_market_item(item, '취업')
    assert market.current_priority(item)
    queue = market.enqueue_report([], report)
    assert max([candidate(score=100), *queue], key=market.priority_key)['keyword'] == key
    changed = {**item, 'recent_search_trend': {**s, 'points': 99}}
    assert not market.fresh_market_item(changed, '취업')
    assert not market.fresh_market_item(item, '취업', now + timedelta(days=1))
    assert not market.fresh_market_item({**item, 'hold_reasons': ['unverified_source_coverage']}, '취업')
    google.assert_not_called()


def test_recent_rise_does_not_override_negative_source_verdict(monkeypatch):
    key = '시험준비물'
    collector = Mock(enabled=True, now=datetime.now(timezone.utc), cache={})
    collector.collect.return_value = {key: signal(key)}
    collector.summary.return_value = {'status': 'checked'}
    monkeypatch.setattr(market.recent, 'Collector', lambda _: collector)
    monkeypatch.setattr(market, 'demand_candidates', lambda _: {key: {'keyword': key, 'monthly': 80}})
    monkeypatch.setattr(market, 'search_results', lambda _: ('google_custom_search', organic_sample(key)))
    monkeypatch.setattr(market, 'candidate_sources', lambda *a, **k: [evidence()])
    monkeypatch.setattr(market, 'ask', lambda prompt: {'candidates': [{'keyword': key}]} if '후보:' in prompt else analysis(supported=False))
    assert market.select_category('취업', titles=[])['selected'] == []


def test_enabling_daily_api_invalidates_legacy_reuse(monkeypatch):
    item = candidate()
    credentials(monkeypatch)
    assert not market.fresh_market_item(item, '취업')


def test_prompt_exposes_daily_relative_summary_not_full_series():
    s = signal('엑셀틀고정')
    row = market.candidate_prompt_row({'keyword': '엑셀틀고정', 'monthly': 100, 'recent_search_trend': s})
    assert row['recent_search_trend']['unit'] == 'relative_index'
    assert 'data' not in row['recent_search_trend']


def test_both_selection_workflows_inject_hub_credentials():
    for name in ('auto-post.yml', 'blog-keyword-select.yml'):
        obj = yaml.safe_load(Path('.github/workflows', name).read_text())
        steps = [step for job in obj['jobs'].values() for step in job.get('steps', [])
                 if 'scripts/select_blog_keywords.py' in step.get('run', '')]
        assert steps
        for step in steps:
            assert step['env']['NAVER_API_HUB_CLIENT_ID'] == '${{ secrets.NAVER_API_HUB_CLIENT_ID }}'
            assert step['env']['NAVER_API_HUB_CLIENT_SECRET'] == '${{ secrets.NAVER_API_HUB_CLIENT_SECRET }}'


def test_final_ranking_prioritizes_rise_regardless_of_model_order_and_monthly_volume(monkeypatch):
    rising_key, evergreen_key = '시험준비물', '면접준비물'
    signals = {rising_key: trend.analyze(rising_key,
                   series([20] * 12 + [25, 26, 29], now=datetime.now(timezone.utc)), datetime.now(timezone.utc)),
               evergreen_key: signal(evergreen_key, rising=False)}
    assert signals[rising_key]['qualified_rising']
    c = Mock(enabled=True, now=datetime.now(timezone.utc), cache={})
    c.collect.return_value = signals
    c.summary.return_value = {'status': 'checked'}
    monkeypatch.setattr(market.recent, 'Collector', lambda _: c)
    monkeypatch.setattr(market, 'demand_candidates', lambda _: {
        rising_key: {'keyword': rising_key, 'monthly': 10},
        evergreen_key: {'keyword': evergreen_key, 'monthly': 20000}})
    monkeypatch.setattr(market, 'search_results', lambda key: ('google_custom_search', organic_sample(key)))
    monkeypatch.setattr(market, 'candidate_sources', lambda *a, **k: [evidence()])
    monkeypatch.setattr(market, 'ask', lambda _: {'candidates': [
        {'keyword': evergreen_key}, {'keyword': rising_key}]})
    monkeypatch.setattr(market, '_review_with_source_recovery', lambda key, *a, **k: (
        {'keyword': key, 'category': '취업', 'topic': key + ' 확인 방법', 'intent': '무엇을 준비하나',
         'gap': '준비물 체크리스트', 'source_url': evidence()['url'], 'verified_sources': [evidence()],
         'intent_results': [organic_sample(key)[0]['url']], 'valid_until': None,
         'intent_evidence': market_test_intent(key)}, None, None, {}))
    report = market.select_category('취업', titles=[])
    assert report['selection_scope'] == 'recent_rise_then_score'
    assert [item['keyword'] for item in report['selected']] == [rising_key, evergreen_key]
    assert all(market.fresh_market_item(item, '취업') for item in report['selected'])


def market_test_intent(key):
    from tests.test_market_topics import intent_review
    return intent_review(key)


def test_unavailable_daily_data_does_not_restore_larger_monthly_weight():
    components = {'demand': 35, 'organic_opportunity': 24, 'trend': 0}
    market.apply_recent_components(components, trend.unavailable('q', datetime.now(timezone.utc), 'network_error'))
    assert components['demand'] == 15
    assert components['recent_trend'] == 0


def test_rising_aliases_do_not_duplicate_the_research_pool():
    keys = ('엑셀틀고정', '엑셀 틀고정')
    rows = {key: {'keyword': key, 'monthly': 100, 'recent_search_trend': signal(key)} for key in keys}
    assert len(market.candidate_pool(rows, [], '생산성')) == 1
