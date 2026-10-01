"""Scarce review pools refill without changing demand or publication gates."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from src import market_topics as market, review_discovery as review, selection_feedback as feedback
# Re-export the shared autouse fixture to isolate all external boundaries.
from tests.test_market_topics import isolated_market_history as isolated_market_history
from tests.test_selection_feedback import install_selection, failed_report


def install_refills(monkeypatch, initial, batches, *, passing=(), shortlist=None):
    keys = list(dict.fromkeys(initial + [key for batch in batches for key in batch]))
    stats, search, offered = install_selection(monkeypatch, keys, passing=passing, shortlist=shortlist)
    seeds = tuple(f'보충시드{i}' for i in range(len(batches)))
    monkeypatch.setattr(review, 'expansion_seeds', lambda _: seeds)
    response = [{key: stats[key] for key in batch} for batch in [initial, *batches]]
    demand = Mock(side_effect=response)
    monkeypatch.setattr(market, 'demand_candidates', demand)
    return stats, search, offered, demand


def test_recorded_96_candidate_failure_can_refill_without_clearing_31_failures(monkeypatch):
    # Reuse the recorded keyword names, not old measurements as live evidence.
    recorded = json.loads((Path(__file__).parent / 'fixtures/review_pool_exhausted_20260929.json').read_text())
    rejected = [row['keyword'] for row in recorded['discovery_rejections']]
    historical = [row['keyword'] for row in recorded['failure_history']]
    assert len(rejected) == 80 and len(historical) == 31
    initial = [*rejected, *historical[:15], '청소기필터']
    assert len(set(initial)) == 96
    good = '모니터주사율'
    def shortlist(rows):
        return {'candidates': [{'keyword': good}] if any(r['keyword'] == good for r in rows) else [],
                'skipped': [{'keyword': r['keyword'], 'reason_code': 'purchase_intent_unclear'}
                            for r in rows if r['keyword'] != good]}
    stats, search, offered, demand = install_refills(monkeypatch, initial, [[good]],
                                                    passing=[good], shortlist=shortlist)
    now = datetime.now(timezone.utc)
    history = feedback.load_history(failed_report(historical, at=now), '리뷰', now)
    report = market.select_category('리뷰', 1, [], failure_history=history)
    assert report['selected'][0]['keyword'] == good
    assert report['selected'][0]['monthly_search'] == stats[good]['monthly']
    assert market.fresh_market_item(report['selected'][0], '리뷰')
    assert market.enqueue_report([], report)[0]['keyword'] == good
    assert all(row in report['failure_history'] for row in history)
    assert len(report['failure_history']) == len(history) + 3
    assert len(report['deferred_keywords']) == 31
    assert len(report['deferred_measured_keywords']) == 15
    assert report['proposal_rounds'][0]['skipped'][0]['reason_code'] == 'purchase_intent_unclear'
    assert report['discovery_replenishment'][0]['available_after'] == 1
    assert good not in offered[0] and good in offered[-1]
    searched = [market.norm(call.args[0]) for call in search.call_args_list]
    assert len(searched) == 4 and searched[-1] == good and '청소기필터' in searched
    assert not set(searched) & set(historical)
    assert demand.call_count == 2


def test_all_rejected_shortlist_gets_distinct_new_pool_not_same_top_120(monkeypatch):
    initial = [f'노트북{i}메모리' for i in range(120)]
    good = '모니터주사율'
    def shortlist(rows):
        return {'candidates': [{'keyword': good}] if rows[0]['keyword'] == good else []}
    _, search, offered, demand = install_refills(monkeypatch, initial, [[good]],
                                                 passing=[good], shortlist=shortlist)
    report = market.select_category('리뷰', 1, [])
    assert len(offered) == 3 and len(set(offered[0] + offered[1])) == 120
    assert offered[2] == [good]
    assert report['selected'][0]['keyword'] == good
    assert report['research_pool_size'] == 121
    assert search.call_count == 2  # One uncertain memory question, then the new endorsed family.
    assert search.call_args.args == (good,)


def test_refilled_candidate_still_needs_full_source_and_search_review(monkeypatch):
    bad, good = '노트북램', '모니터주사율'
    _, search, offered, _ = install_refills(monkeypatch, [bad], [[good]], passing=[good])
    report = market.select_category('리뷰', 1, [])
    assert report['rejected'][0]['keyword'] == bad
    assert report['selected'][0]['keyword'] == good
    assert offered == [[bad], [good]]
    assert search.call_count == 2


def test_expansion_exhaustion_stops_without_forcing_or_inventing_demand(monkeypatch):
    key = '청소기필터'
    _, search, offered, demand = install_refills(monkeypatch, [key], [[key]] * 3,
                                                 shortlist=lambda _: {'candidates': []})
    report = market.select_category('리뷰', 1, [])
    assert report['selected'] == [] and report['research_stop_reason'] == 'pool_exhausted'
    assert report['measured_candidates'] == 1 and demand.call_count == 4
    assert len(report['discovery_replenishment']) == 3
    assert offered == [[key]]
    assert report['proposal_rounds'][0]['skipped'][0]['reason_code'] == 'not_reported'
    search.assert_called_once_with(review.research_query(key))
    with pytest.raises(RuntimeError):
        market.enqueue_report([], report)


def test_initial_empty_demand_can_recover_but_missing_credentials_cannot(monkeypatch):
    good = '노트북배터리'
    stats, _, _, demand = install_refills(monkeypatch, [], [[good]], passing=[good])
    demand.side_effect = [market.NoMeasuredDemand(), stats]
    assert market.select_category('리뷰', 1, [])['selected'][0]['keyword'] == good
    demand.reset_mock()
    demand.side_effect = RuntimeError('Measured market demand requires Naver credentials')
    with pytest.raises(RuntimeError, match='credentials'):
        market.select_category('리뷰', 1, [])
    assert demand.call_count == 1


def test_lookup_failure_is_audited_and_next_seed_can_recover(monkeypatch):
    good = '모니터해상도'
    stats, _, _, demand = install_refills(monkeypatch, [], [[], [], [good]], passing=[good])
    demand.side_effect = [{}, OSError('private provider data'), market.NoMeasuredDemand(), stats]
    report = market.select_category('리뷰', 1, [])
    assert [row['status'] for row in report['discovery_replenishment']] == [
        'lookup_unavailable', 'no_measured_demand', 'measured']
    assert 'private provider data' not in json.dumps(report)
    assert report['selected'][0]['keyword'] == good


def test_refill_enforces_exact_500_demand_floor_and_does_not_borrow_seed_volume(monkeypatch):
    real_demand = market.demand_candidates
    low, good = '노트북배터리', '모니터주사율'
    install_refills(monkeypatch, [], [[low, good]], passing=[good])
    for name in ('NAVER_AD_CUSTOMER_ID', 'NAVER_AD_API_KEY', 'NAVER_AD_SECRET_KEY'):
        monkeypatch.setenv(name, 'test-only')
    def lookup(seed):
        return [] if seed in review.SEEDS else [
            {'keyword': low, 'monthly': 499}, {'keyword': good, 'monthly': 500},
            {'keyword': '측정불완전', 'monthly': 0}]
    monkeypatch.setattr(market, 'fetch_keyword_stats', lookup)
    monkeypatch.setattr(market, 'demand_candidates', real_demand)
    report = market.select_category('리뷰', 1, [])
    assert report['measured_candidates'] == 1
    assert report['selected'][0]['monthly_search'] == 500
    assert report['selected'][0]['keyword'] == good


def test_refills_cannot_reopen_cooldown_exclusions_or_increase_history_retry_budget(monkeypatch):
    now = datetime.now(timezone.utc)
    expired = [f'노트북{i}메모리' for i in range(4)]
    active, excluded, duplicate, good = '로봇청소기문턱', '제습기평수', '공기청정기필터', '모니터주사율'
    history = feedback.load_history(failed_report(expired, at=now - timedelta(days=4)), '리뷰', now)
    history += feedback.load_history(failed_report([active], at=now), '리뷰', now)
    _, search, offered, _ = install_refills(monkeypatch, expired[:2],
        [[*expired, active, excluded, duplicate, good]], passing=[good])
    report = market.select_category('리뷰', 1, [duplicate], excluded_keywords=[excluded], failure_history=history)
    assert set(report['retry_keywords']) == set(expired[:2])
    assert set(sum(offered, [])) == {*expired[:2], good}
    assert report['selected'][0]['keyword'] == good
    assert search.call_count == 3


def test_time_budget_stops_refill_before_another_seed_or_model_request(monkeypatch):
    _, search, offered, demand = install_refills(monkeypatch, [], [['모니터주사율'], ['노트북램']])
    elapsed = [0]
    monkeypatch.setattr(market, 'monotonic', lambda: elapsed[0])
    def lookup(seeds):
        if seeds == market.CATEGORIES['리뷰']:
            return {}
        elapsed[0] = market.MAX_RESEARCH_SECONDS + 1
        return {}
    demand.side_effect = lookup
    report = market.select_category('리뷰', 1, [])
    assert report['research_stop_reason'] == 'time_budget'
    assert demand.call_count == 2 and not offered
    search.assert_not_called()


def test_healthy_pool_and_non_review_categories_do_not_expand(monkeypatch):
    _, _, _, demand = install_refills(monkeypatch, ['노트북램'], [['모니터주사율']], passing=['노트북램'])
    assert market.select_category('리뷰', 1, [])['selected']
    assert demand.call_count == 1
    _, _, _ = install_selection(monkeypatch, ['엑셀함수'], category='생산성', passing=['엑셀함수'])
    refill = Mock(side_effect=AssertionError('Review expansion in another category'))
    monkeypatch.setattr(review, 'expansion_seeds', refill)
    assert market.select_category('생산성', 1, [])['selected']
    refill.assert_not_called()


def test_daily_expansion_rotation_has_fixed_budget_no_repeated_primary_seed():
    now = datetime.now(timezone.utc)
    today, tomorrow = review.expansion_seeds(now), review.expansion_seeds(now + timedelta(days=1))
    assert set(today) == set(tomorrow) == set(review.EXPANSION_SEEDS)
    assert len(today) == len(set(today)) == 12 and today[0] != tomorrow[0]
    assert not set(today) & set(review.SEEDS)
    assert all(review.discovery_issue(seed) is None for seed in today)


@pytest.mark.parametrize('response', [None, {'skipped': None}, {'skipped': ['bad', {'keyword': [], 'reason_code': []}]}])
def test_missing_or_malformed_skip_reasons_are_not_fabricated(response):
    assert review.shortlist_skips([{'keyword': '청소기필터'}], [], response) == [
        {'keyword': '청소기필터', 'reason_code': 'not_reported', 'kind': 'model_shortlist_opinion'}]


def test_explicit_skips_retire_only_offered_candidates_and_never_selected_proposals(monkeypatch):
    bad, skipped, good = '노트북램', '청소기필터', '모니터주사율'
    def shortlist(rows):
        key = good if any(row['keyword'] == good for row in rows) else bad
        return {'candidates': [{'keyword': key}], 'skipped': [
            {'keyword': skipped, 'reason_code': 'purchase_intent_unclear'},
            {'keyword': key, 'reason_code': 'scope_too_broad'},
            {'keyword': good, 'reason_code': 'scope_too_broad'}]}
    _, _, offered, _ = install_refills(monkeypatch, [bad, skipped], [[good]],
                                        passing=[good], shortlist=shortlist)
    report = market.select_category('리뷰', 1, [])
    assert report['selected'][0]['keyword'] == good
    assert offered == [[skipped, bad], [skipped], [good]]
    assert report['proposal_rounds'][0]['skipped'] == [
        {'keyword': skipped, 'reason_code': 'purchase_intent_unclear', 'kind': 'model_shortlist_opinion'}]
