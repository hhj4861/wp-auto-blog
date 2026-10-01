"""Replay the real filter-cluster shortlist; never fabricate a live success."""
import json
from pathlib import Path

import pytest

from src import market_topics as market, review_discovery as review
from tests.test_market_topics import isolated_market_history as isolated_market_history
from tests.test_review_replenishment import install_refills

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/review_filter_cluster_20261001.json').read_text())


def test_recorded_cluster_spends_one_slot_then_refills_other_questions(monkeypatch):
    initial = FIXTURE['proposal_rounds'][0]['offered_keywords']
    def shortlist(rows):
        recorded = {row['keyword']: row['reason_code'] for row in FIXTURE['proposal_rounds'][0]['skipped']}
        return {'candidates': [], 'skipped': [
            {'keyword': row['keyword'], 'reason_code': recorded.get(row['keyword'], 'not_reported')}
            for row in rows]}
    good = '모니터주사율'
    stats, search, _, demand = install_refills(monkeypatch, initial,
        [['삼성공기청정기필터'], [good]], passing=[good], shortlist=shortlist)
    report = market.select_category('리뷰', 1, [])
    searched = [review.research_family(call.args[0]) for call in search.call_args_list]
    assert searched == [review.research_family('공기청정기필터'), review.research_family(good)]
    assert demand.call_count == 3 and report['shortlist_research_attempts'] == 2
    assert report['selected'][0]['keyword'] == good
    assert report['selected'][0]['monthly_search'] == stats[good]['monthly']
    assert market.fresh_market_item(report['selected'][0], '리뷰')
    assert market.enqueue_report([], report)[0]['keyword'] == good
    assert report['deferred_research_family_keywords']
    assert all(market.norm(row['keyword']) not in report['deferred_research_family_keywords']
               for row in report['failure_history'])


def test_only_aliases_available_stops_without_spending_three_searches(monkeypatch):
    initial = ['엘지공기청정기필터', 'LG퓨리케어필터', 'LG퓨리케어공기청정기필터']
    _, search, _, _ = install_refills(monkeypatch, initial, [['삼성공기청정기필터']],
        shortlist=lambda _: {'candidates': []})
    report = market.select_category('리뷰', 1, [])
    assert report['selected'] == [] and search.call_count == 1
    assert report['research_stop_reason'] == 'pool_exhausted'
    assert len(report['failure_history']) == 1
    with pytest.raises(RuntimeError):
        market.enqueue_report([], report)


def test_distinct_facets_remain_eligible_and_previous_run_is_not_family_cooldown():
    rows = [{'keyword': key, 'reason_code': 'not_reported'} for key in
            ['노트북램', '노트북배터리', '공기청정기필터']]
    chosen = review.shortlist_research_candidates(rows, 3, researched=['삼성노트북램'])
    assert [row['keyword'] for row in chosen] == ['노트북배터리', '공기청정기필터']
    assert len(review.shortlist_research_candidates(rows, 3)) == 3


def test_same_family_model_endorsement_is_not_overridden(monkeypatch):
    keys = ['삼성노트북램', '엘지노트북램']
    _, search, _, _ = install_refills(monkeypatch, keys, [], passing=[keys[0]])
    report = market.select_category('리뷰', 1, [])
    assert report['selected'][0]['keyword'] == keys[0]
    assert search.call_count == 2
    assert report['deferred_research_family_keywords'] == []
