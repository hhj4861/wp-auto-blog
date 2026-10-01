"""Empty name-only opinions must reach evidence gates within a fixed budget."""
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from src import market_topics as market, review_discovery as review, selection_feedback as feedback
from tests.test_market_topics import isolated_market_history as isolated_market_history
from tests.test_review_replenishment import install_refills
from tests.test_selection_feedback import failed_report, install_selection


def empty_shortlist(_):
    return {'candidates': []}


@pytest.mark.parametrize('passing', [False, True])
def test_october_first_failure_reaches_real_gates_and_only_eligible_item_is_queued(monkeypatch, passing):
    recorded = json.loads((Path(__file__).parent / 'fixtures/review_empty_shortlist_20261001.json').read_text())
    rounds = recorded['proposal_rounds']
    assert recorded['measured_candidates'] == 341 and recorded['evaluated_candidates'] == 0
    responses = iter({'candidates': [], 'skipped': row['skipped']} for row in rounds)
    good = '가벼운무선청소기'
    stats, search, offered, _ = install_refills(monkeypatch, rounds[0]['offered_keywords'],
        [rounds[1]['offered_keywords']], passing=[good] if passing else [],
        shortlist=lambda _: next(responses))
    report = market.select_category('리뷰', 1, [])
    searched = [market.norm(call.args[0]) for call in search.call_args_list]
    assert set(searched[:2]) == {'노트북램', good}
    assert report['proposal_rounds'][0]['proposals'] == []
    assert sorted(report['proposal_rounds'][0]['skipped'], key=lambda row: row['keyword']) == sorted(
        rounds[0]['skipped'], key=lambda row: row['keyword'])
    assert report['proposal_rounds'][0]['no_eligible_proposal'] is True
    assert report['proposal_rounds'][0]['measured_fallback'] is True
    assert report['shortlist_research_attempts'] == len(searched)
    if passing:
        assert len(offered) == 1
        item = report['selected'][0]
        assert item['keyword'] == good and item['monthly_search'] == stats[good]['monthly']
        assert item['organic_query'] == review.research_query(good)
        assert market.fresh_market_item(item, '리뷰')
        assert market.enqueue_report([], report)[0]['keyword'] == good
    else:
        assert len(offered) == 2 and len(searched) == 3
        assert len(report['rejected']) == 3 and report['selected'] == []
        assert 'LG공기청정기필터교체' not in searched and '노트북SSD추가' not in searched
        with pytest.raises(RuntimeError):
            market.enqueue_report([], report)


@pytest.mark.parametrize('code', ['scope_too_broad', 'maintenance_intent', 'duplicate_intent', 'category_mismatch'])
def test_explicit_hard_rejections_are_not_researched(monkeypatch, code):
    key = '노트북램'
    _, search, _ = install_selection(monkeypatch, [key], passing=[key], shortlist=lambda _: {
        'candidates': [], 'skipped': [{'keyword': key, 'reason_code': code}]})
    report = market.select_category('리뷰', 1, [])
    search.assert_not_called()
    assert report['shortlist_research_attempts'] == 0 and report['selected'] == []


@pytest.mark.parametrize('response', [None, [], {}, {'candidates': None}, {'candidates': 'bad'},
    {'candidates': [None]}, {'candidates': [{'keyword': 'invented'}]},
    {'candidates': [{'keyword': '노트북램', 'search_query': '노트북램 site:lg.com'}]}])
def test_malformed_or_invalid_proposals_do_not_trigger_recovery(monkeypatch, response):
    _, search, _ = install_selection(monkeypatch, ['노트북램'], passing=['노트북램'], shortlist=lambda _: response)
    report = market.select_category('리뷰', 1, [])
    search.assert_not_called()
    assert report['shortlist_research_attempts'] == 0 and report['selected'] == []


def test_recovery_is_diverse_bounded_and_keeps_exact_queries():
    keys = ['LG공기청정기필터', '삼성공기청정기필터', '노트북램', '가벼운무선청소기']
    skipped = [{'keyword': key, 'reason_code': 'insufficient_specificity'} for key in keys]
    picked = review.shortlist_research_candidates(skipped, 2)
    assert [row['keyword'] for row in picked] == [keys[0], keys[2]]
    assert all(row['search_query'].replace(' ', '') == row['keyword'] for row in picked)
    assert review.shortlist_research_candidates(skipped, 0) == []
    assert review.shortlist_research_candidates([
        {'keyword': '청소기', 'reason_code': 'not_reported'},
        {'keyword': '청소기필터청소방법', 'reason_code': 'not_reported'}], 2) == []


def test_recovery_retains_demand_cooldown_exclusion_duplicate_and_retry_limits(monkeypatch):
    keys = ['노트북램', '노트북배터리', '공기청정기필터', '모니터해상도', '무선청소기흡입력']
    real_demand = market.demand_candidates
    stats, search, _ = install_selection(monkeypatch, keys, passing=keys, shortlist=empty_shortlist)
    for name in ('NAVER_AD_CUSTOMER_ID', 'NAVER_AD_API_KEY', 'NAVER_AD_SECRET_KEY'):
        monkeypatch.setenv(name, 'test-only')
    monkeypatch.setattr(market, 'fetch_keyword_stats', lambda _: list(stats.values()))
    monkeypatch.setattr(market, 'demand_candidates', real_demand)
    stats[keys[0]]['monthly'] = 499
    history = feedback.load_history(failed_report([keys[1]], at=datetime.now(timezone.utc)),
                                    '리뷰', datetime.now(timezone.utc))
    report = market.select_category('리뷰', 1, [keys[2]], excluded_keywords=[keys[3]], failure_history=history)
    search.assert_called_once_with(review.research_query(keys[4]))
    assert report['failure_history'] == history and report['retry_keywords'] == []


def test_partial_shortlist_and_other_categories_keep_existing_behavior(monkeypatch):
    keys = ['노트북램', '청소기필터']
    _, search, _ = install_selection(monkeypatch, keys, passing=keys,
        shortlist=lambda _: {'candidates': [{'keyword': keys[0]}]})
    report = market.select_category('리뷰', 1, [])
    search.assert_called_once_with(keys[0])
    assert report['shortlist_research_attempts'] == 0
    _, search, _ = install_selection(monkeypatch, ['엑셀함수'], category='생산성', shortlist=empty_shortlist)
    report = market.select_category('생산성', 1, [])
    search.assert_not_called()
    assert report['shortlist_research_attempts'] == 0


def test_timeout_before_or_during_recovery_records_only_actual_attempts(monkeypatch):
    keys = ['노트북램', '모니터주사율']
    elapsed = [0]
    monkeypatch.setattr(market, 'monotonic', lambda: elapsed[0])
    _, search, _ = install_selection(monkeypatch, keys, shortlist=empty_shortlist)
    original = search.side_effect
    def timed_search(query):
        elapsed[0] = market.MAX_RESEARCH_SECONDS
        return original(query)
    search.side_effect = timed_search
    report = market.select_category('리뷰', 1, [])
    assert report['research_stop_reason'] == 'time_budget'
    assert report['shortlist_research_attempts'] == search.call_count == 1
    assert len(report['proposal_rounds'][0]['research_fallback_attempted']) == 1
    elapsed[0] = 0
    def timed_shortlist(_):
        elapsed[0] = market.MAX_RESEARCH_SECONDS
        return {'candidates': []}
    _, search, _ = install_selection(monkeypatch, keys, shortlist=timed_shortlist)
    report = market.select_category('리뷰', 1, [])
    search.assert_not_called()
    assert report['shortlist_research_attempts'] == 0
    assert report['research_stop_reason'] == 'time_budget'


@pytest.mark.parametrize('gate', ['search', 'sources', 'plan'])
def test_recovery_does_not_bypass_publication_evidence_gates(monkeypatch, gate):
    key = '노트북램'
    _, search, _ = install_selection(monkeypatch, [key], passing=[key], shortlist=empty_shortlist)
    if gate == 'search':
        monkeypatch.setattr(market, 'review_search', lambda *_, **kw: None)
    elif gate == 'sources':
        monkeypatch.setattr(market, 'candidate_sources', lambda *_, **kw: [])
    else:
        monkeypatch.setattr(market, 'review_plan', lambda *_, **kw: {})
    report = market.select_category('리뷰', 1, [])
    search.assert_called_once_with(review.research_query(key))
    assert report['selected'] == [] and report['shortlist_research_attempts'] == 1
    assert report['rejected'] or report['held']
    with pytest.raises(RuntimeError):
        market.enqueue_report([], report)


def test_failed_additional_research_is_cooled_down_on_next_run(monkeypatch):
    key = '노트북램'
    _, first, _ = install_selection(monkeypatch, [key], shortlist=empty_shortlist)
    report = market.select_category('리뷰', 1, [])
    first.assert_called_once_with(review.research_query(key))
    assert report['failure_history'][0]['keyword'] == key
    _, second, _ = install_selection(monkeypatch, [key], passing=[key], shortlist=empty_shortlist)
    retry = market.select_category('리뷰', 1, [], failure_history=report['failure_history'])
    second.assert_not_called()
    assert retry['failure_history'] == report['failure_history']
    assert retry['selected'] == [] and retry['shortlist_research_attempts'] == 0
