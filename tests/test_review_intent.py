"""Review purpose guidance, exact query binding and replayable negative evidence."""
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from src import market_topics as market, review_discovery as review
from src.search_query import validated_search_query
from tests.test_market_topics import isolated_market_history as isolated_market_history
from tests.test_market_topics import candidate, evidence, organic_sample
from tests.test_selection_feedback import install_selection


@pytest.mark.parametrize('keyword,query', [
    ('가벼운무선청소기', '가벼운 무선청소기'), ('노트북램', '노트북 램'),
    ('LG공기청정기필터', 'LG 공기청정기 필터'), ('노트북SSD', '노트북 SSD'),
    ('삼성노트북배터리', '삼성 노트북 배터리'), ('로봇청소기문턱', '로봇청소기 문턱'),
    ('LG그램16gb', 'LG 그램 16gb'), ('노트북램 site:lg.com', '노트북램 site:lg.com'),
    ('가벼운 무선청소기', '가벼운 무선청소기'),
])
def test_query_changes_spaces_only_and_preserves_syntax(keyword, query):
    assert review.research_query(keyword) == query
    assert validated_search_query(keyword, query) == query
    assert query.replace(' ', '') == keyword.replace(' ', '')


def test_same_review_purpose_reaches_shortlist_plan_and_independent_review(monkeypatch):
    key = '가벼운무선청소기'
    install_selection(monkeypatch, [key], passing=[key])
    original = market.ask
    prompts = []
    def ask(prompt):
        prompts.append(prompt)
        return original(prompt)
    monkeypatch.setattr(market, 'ask', ask)
    report = market.select_category('리뷰', 1, [])
    assert report['selected']
    shortlist = next(p for p in prompts if '조사 후보를 고르세요.' in p)
    plan = next(p for p in prompts if f'검색어는 {key}입니다.' in p)
    captured = Mock(return_value={})
    market.suitability.review_plan(report['selected'][0], datetime.now(timezone.utc), captured)
    independent = captured.call_args.args[0]
    assert all(review.BUYING_INTENT_GUIDANCE in p for p in (shortlist, plan, independent))
    captured.reset_mock()
    market.suitability.review_plan(candidate(), datetime.now(timezone.utc), captured)
    assert review.BUYING_INTENT_GUIDANCE not in captured.call_args.args[0]


def test_negative_review_keeps_actual_search_and_source_inputs_without_extra_fields(monkeypatch):
    key = '노트북램'
    _, search, _ = install_selection(monkeypatch, [key], shortlist=lambda _: {'candidates': []})
    source = {**evidence(), 'private_transport_detail': 'never retain this field'}
    monkeypatch.setattr(market, 'candidate_sources', lambda *_, **kw: [deepcopy(source)])
    report = market.select_category('리뷰', 1, [])
    row = report['rejected'][0]
    assert search.call_args.args == ('노트북 램',)
    assert row['keyword'] == key and row['organic_query'] == '노트북 램'
    assert row['organic_results'] == organic_sample('노트북 램')
    assert row['search_review']['executed_query'] == row['organic_query']
    assert row['verified_sources'] == [{k: source[k] for k in ('url', 'title', 'excerpt', 'sha256', 'checked_on')}]
    assert row['decision_diagnostics']['model_rejection_opinion']['code'] == 'unsupported_claim'
    assert market.opportunity.quality_issues(key, row['organic_provider'], row['organic_results'],
        report['selected_at'], row['search_review'], executed_query=row['organic_query']) == []
    assert report['selected'] == []
    with pytest.raises(RuntimeError):
        market.enqueue_report([], report)


def test_followup_shortlist_does_not_repeat_full_evidence_bodies(monkeypatch):
    keys = [f'노트북{i}메모리' for i in range(8)]
    install_selection(monkeypatch, keys)
    original = market.ask
    prompts = []
    def ask(prompt):
        if '조사 후보를 고르세요.' in prompt:
            prompts.append(prompt)
        return original(prompt)
    monkeypatch.setattr(market, 'ask', ask)
    report = market.select_category('리뷰', 1, [])
    assert len(prompts) >= 2 and report['rejected'][0]['verified_sources']
    assert 'verified_sources' not in prompts[1] and 'official_sources' not in prompts[1]
    assert report['rejected'][0]['reason'] in prompts[1]


def test_rejected_source_recovery_preserves_both_distinct_decision_inputs(monkeypatch):
    key = '가벼운무선청소기'
    first = evidence('https://www.lge.co.kr/vacuum-cleaners/fixture-first')
    second = evidence('https://www.samsung.com/sec/vacuum-cleaners/fixture-second')
    second.update(excerpt=second['excerpt'] + ' 추가 검증 자료', sha256='different-fixture-hash')
    monkeypatch.setattr(market, 'ask', lambda _: {'supported': False, 'rejection_reason': 'source_missing_detail'})
    monkeypatch.setattr(market, 'research_official_sources', lambda *_: ([second], {'provider': 'codex_web', 'searched': True}))
    now = datetime.now(timezone.utc).isoformat()
    _, reason, _, audit = market._review_with_source_recovery(key, '리뷰', now,
        organic_sample(key), [first], provider='codex_native_search', evidence_mode='serp',
        research=None, allow_recovery=True, budget={'attempts': 0})
    assert reason and audit['source_recovery']['outcome'] == 'review_rejected'
    initial = audit['source_recovery']['initial_review']['review_inputs']
    retry = audit['source_recovery']['retry_review']['review_inputs']
    assert initial['official_sources'][0]['url'] == first['url']
    assert retry['official_sources'][0]['url'] == second['url']
    assert initial['search_results'] == retry['search_results'] == organic_sample(key)
