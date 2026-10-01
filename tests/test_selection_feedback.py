"""Repeated selection regressions; external boundaries use synthetic evidence."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import Mock

import pytest

from src import market_topics as market
from src import selection_feedback as feedback
from tests.test_market_topics import (isolated_market_history, analysis, evidence,
                                      organic_sample)


NOW = datetime(2026, 9, 29, 2, tzinfo=timezone.utc)
REPEATED_REVIEW = ['노트북비교', '로봇청소기비교', '무선청소기비교',
                   '무선청소기가격비교', '업무용노트북', '인덕션설치비용', '학생용노트북']


def failed_report(keywords, *, category='리뷰', at=NOW, reason='source_missing_detail'):
    return {'category': category, 'selected_at': at.isoformat(), 'selected': [], 'held': [],
            'rejected': [{'keyword': key,
                          'reason': 'search intent or official evidence does not support an article',
                          'decision_diagnostics': {'model_rejection_opinion':
                              {'kind': 'model_opinion', 'code': reason}}} for key in keywords]}


def install_selection(monkeypatch, keywords, *, passing=(), category='리뷰', shortlist=None):
    stats = {key: {'keyword': key, 'monthly': 1200 + i} for i, key in enumerate(keywords)}
    monkeypatch.setattr(market, 'demand_candidates', lambda _: deepcopy(stats))
    search = Mock(side_effect=lambda key: ('codex_native_search', organic_sample(key)))
    monkeypatch.setattr(market, 'search_results', search)
    monkeypatch.setattr(market, 'candidate_sources', lambda *_, **kw: [evidence()])
    monkeypatch.setattr(market, 'fetch_trend_change', lambda _: None)
    monkeypatch.setattr(market, 'research_official_sources', lambda *_: ([], None))
    offered = []

    def ask(prompt):
        if '조사 후보를 고르세요.' in prompt:
            rows = json.loads(prompt.split('\n후보: ', 1)[1].split('\n기존 제목: ', 1)[0])
            offered.append([row['keyword'] for row in rows])
            return shortlist(rows) if shortlist else {'candidates': [{'keyword': r['keyword']} for r in rows[:6]]}
        key = next(key for key in keywords if f'검색어는 {key}입니다.' in prompt)
        return analysis(key, category) if key in passing else {'supported': False, 'rejection_reason': 'unsupported_claim'}

    monkeypatch.setattr(market, 'ask', ask)
    return stats, search, offered


@pytest.mark.parametrize('row,code,hours', [
    ({'reason': 'search relevance review unavailable'}, 'temporary_failure', 6),
    ({'reason': 'search quality insufficient'}, 'search_quality', 24),
    ({'hold_reasons': ['narrower_source_coverage', 'unverified_source_coverage']}, 'source_coverage', 72),
    ({'hold_reasons': ['narrower_or_unverified_search_intent']}, 'intent_mismatch', 168),
])
def test_reason_specific_expiry_reopens_keyword(row, code, hours):
    report = {'category': '리뷰', 'selected_at': NOW.isoformat(),
              'rejected': [{'keyword': '노트북 비교', **row}]}
    history = feedback.load_history(report, '리뷰', NOW)
    assert history[0]['reason_code'] == code
    assert feedback.deferred_keywords(history, NOW + timedelta(hours=hours, seconds=-1)) == {'노트북비교'}
    assert feedback.deferred_keywords(history, NOW + timedelta(hours=hours)) == set()


def test_history_survives_report_replacement_without_extending_cooldown():
    first = feedback.load_history(failed_report(['노트북비교']), '리뷰', NOW)
    second = {'category': '리뷰', 'selected_at': (NOW + timedelta(hours=1)).isoformat(),
              'selected': [], 'rejected': [], 'failure_history': first}
    assert feedback.load_history(second, '리뷰', NOW + timedelta(hours=2)) == first
    migrated = {**failed_report(['노트북비교']), 'failure_history': first}
    assert feedback.load_history(migrated, '리뷰', NOW) == first
    retry = {**failed_report(['노트북비교'], at=NOW + timedelta(days=4)), 'failure_history': first}
    assert feedback.load_history(retry, '리뷰', NOW + timedelta(days=4))[0]['attempts'] == 2


def test_success_clears_failure_but_categories_and_years_are_independent():
    old = feedback.load_history(failed_report(['2026 노트북 비교']), '리뷰', NOW)
    assert feedback.load_history({'category': '취업', 'failure_history': old}, '리뷰', NOW) == []
    assert '2027노트북비교' not in feedback.deferred_keywords(old, NOW)
    good = {'category': '리뷰', 'selected_at': NOW.isoformat(), 'failure_history': old,
            'selected': [{'keyword': '2026노트북비교'}]}
    assert feedback.load_history(good, '리뷰', NOW) == []


@pytest.mark.parametrize('change', [
    {'failed_at': 'invalid'}, {'failed_at': '2026-09-29T02:00:00'},
    {'failed_at': '2026-09-30T02:00:00+00:00'}, {'retry_after': '2099-01-01T00:00:00+00:00'},
    {'keyword': None}, {'attempts': True}, {'reason_code': ['bad']},
])
def test_corrupt_or_unbounded_memory_cannot_create_permanent_exclusion(change):
    row = feedback.load_history(failed_report(['노트북비교']), '리뷰', NOW)[0]
    report = {'category': '리뷰', 'failure_history': [{**row, **change}]}
    assert feedback.load_history(report, '리뷰', NOW) == []


def test_memory_retention_and_fixed_reason_codes():
    report = failed_report([f'후보{i}' for i in range(700)])
    history = feedback.load_history(report, '리뷰', NOW)
    assert len(history) == feedback.MAX_HISTORY
    assert feedback.load_history(report, '리뷰', NOW + timedelta(days=31)) == []
    assert feedback.failure_code({'reason': 'SECRET raw error'}) is None
    assert feedback.failure_code({'reason': 'invalid or repeated measured keyword'}) is None


@pytest.mark.parametrize('keyword', ['노트북비교', '무선청소기가격비교', 'MRI비용', '50대자격증추천', '갑상선에좋은음식', '대상포진'])
def test_broad_terms_do_not_get_specific_question_bonus(keyword):
    assert market.specificity_score(keyword) == 5


@pytest.mark.parametrize('keyword', ['컴활2급응시자격', '이직확인서작성방법', '엑셀조건부서식', '노트북와이파이연결오류', '국가건강검진대상'])
def test_actionable_measured_questions_keep_discovery_priority(keyword):
    assert market.specificity_score(keyword) == 15


def test_malformed_legacy_diagnostics_do_not_abort_new_research():
    report = failed_report(['노트북비교', '업무용노트북'])
    report['rejected'][0]['reason'] = ['invalid']
    report['rejected'][1]['decision_diagnostics']['model_rejection_opinion']['code'] = ['invalid']
    history = feedback.load_history(report, '리뷰', NOW)
    assert len(history) == 1 and history[0]['reason_code'] == 'temporary_failure'


def test_legacy_seven_review_failures_are_skipped_before_search(monkeypatch):
    now = datetime.now(timezone.utc)
    history = feedback.load_history(failed_report(REPEATED_REVIEW, at=now), '리뷰', now)
    new = '무선청소기흡입력비교'
    stats, search, offered = install_selection(monkeypatch, [*REPEATED_REVIEW, new], passing=[new])
    report = market.select_category('리뷰', 1, [], failure_history=history)
    search.assert_called_once_with(new)
    assert report['selected'][0]['keyword'] == new
    assert report['selected'][0]['monthly_search'] == stats[new]['monthly']
    assert set(report['deferred_keywords']) == set(REPEATED_REVIEW)
    assert report['failure_history'] == history
    assert offered == [[new]]


def test_all_deferred_writes_a_report_without_retrying_or_fabricating_candidates(monkeypatch):
    now = datetime.now(timezone.utc)
    history = feedback.load_history(failed_report(REPEATED_REVIEW, at=now), '리뷰', now)
    _, search, offered = install_selection(monkeypatch, REPEATED_REVIEW)
    report = market.select_category('리뷰', 1, [], failure_history=history)
    assert report['selected'] == [] and report['evaluated_candidates'] == 0
    assert report['failure_history'] == history and offered == []
    search.assert_not_called()
    with pytest.raises(RuntimeError):
        market.enqueue_report([], report)


def test_expired_failures_cannot_take_over_the_next_category_run(monkeypatch):
    now = datetime.now(timezone.utc)
    history = feedback.load_history(failed_report(REPEATED_REVIEW, at=now - timedelta(days=4)), '리뷰', now)
    new = '무선청소기흡입력비교'
    _, search, offered = install_selection(monkeypatch, [*REPEATED_REVIEW, new], passing=[new])
    report = market.select_category('리뷰', 1, [], failure_history=history)
    assert offered[0][0] == new
    assert report['retry_keywords'] == []  # Expired broad terms still fail discovery.
    assert search.call_count == 1
    assert report['selected'][0]['keyword'] == new
    assert len(report['failure_history']) == 7


def test_expired_failure_may_pass_only_after_new_full_evidence_review(monkeypatch):
    now = datetime.now(timezone.utc)
    key = '노트북램비교'
    history = feedback.load_history(failed_report([key], at=now - timedelta(days=4)), '리뷰', now)
    _, search, _ = install_selection(monkeypatch, [key], passing=[key])
    report = market.select_category('리뷰', 1, [], failure_history=history)
    search.assert_called_once_with(key)
    assert market.fresh_market_item(report['selected'][0], '리뷰')
    assert report['failure_history'] == []


def test_expired_bounded_questions_still_have_limited_retry_budget(monkeypatch):
    now = datetime.now(timezone.utc)
    old = [f'노트북{i}메모리비교' for i in range(7)]
    history = feedback.load_history(failed_report(old, at=now - timedelta(days=4)), '리뷰', now)
    new = '무선청소기흡입력비교'
    _, search, offered = install_selection(monkeypatch, old + [new], passing=[new])
    report = market.select_category('리뷰', 1, [], failure_history=history)
    assert offered[0][0] == new
    assert len(report['retry_keywords']) == 2 and search.call_count == 3
    assert report['selected'][0]['keyword'] == new


def test_second_round_explores_unoffered_half_of_120_pool(monkeypatch):
    keys = [f'노트북{i}메모리비교' for i in range(120)]
    stats, search, offered = install_selection(monkeypatch, keys, passing=[keys[60]])
    monkeypatch.setattr(market, 'candidate_pool', lambda *_: list(stats.values()))
    report = market.select_category('리뷰', 1, [])
    assert set(offered[0]).isdisjoint(offered[1])
    assert report['research_rounds'] == 2
    assert report['selected'][0]['keyword'] == keys[60]
    assert search.call_count == 12


def test_third_round_can_find_valid_topic_after_twelve_failures(monkeypatch):
    keys = [f'노트북{i}메모리비교' for i in range(13)]
    stats, search, _ = install_selection(monkeypatch, keys, passing=[keys[-1]])
    monkeypatch.setattr(market, 'candidate_pool', lambda *_: list(stats.values()))
    report = market.select_category('리뷰', 1, [])
    assert report['research_rounds'] == 3 and search.call_count == 13
    assert report['selected'][0]['keyword'] == keys[-1]
    assert report['research_stop_reason'] == 'selection_target'


@pytest.mark.parametrize('shortlist', [lambda _: {'candidates': None},
                                     lambda _: {'candidates': [{'keyword': 'unmeasured invented keyword'}]}])
def test_bad_shortlist_does_not_force_publish_or_research_unendorsed_candidates(monkeypatch, shortlist):
    keys = ['노트북램비교', '무선청소기흡입력비교']
    _, search, _ = install_selection(monkeypatch, keys, passing=keys[:1], shortlist=shortlist)
    report = market.select_category('리뷰', 1, [])
    search.assert_not_called()
    assert report['selected'] == [] and report['evaluated_candidates'] == 0
    assert report['proposal_rounds'][0]['measured_fallback'] is False
    assert report['proposal_rounds'][0]['no_eligible_proposal'] is True
    with pytest.raises(RuntimeError):
        market.enqueue_report([], report)


def test_empty_shortlist_moves_to_unoffered_candidates(monkeypatch):
    keys = [f'노트북{i}메모리비교' for i in range(120)]
    def shortlist(rows):
        return {'candidates': [] if keys[0] in [r['keyword'] for r in rows]
                else [{'keyword': keys[60]}]}
    stats, search, offered = install_selection(monkeypatch, keys, passing=[keys[60]], shortlist=shortlist)
    monkeypatch.setattr(market, 'candidate_pool', lambda *_: list(stats.values()))
    report = market.select_category('리뷰', 1, [])
    assert set(offered[0]).isdisjoint(offered[1])
    assert [market.norm(call.args[0]) for call in search.call_args_list] == [keys[0], keys[60]]
    assert report['selected'][0]['keyword'] == keys[60]


def test_round_and_time_budgets_stop_with_persistable_diagnostics(monkeypatch):
    keys = [f'노트북{i}메모리비교' for i in range(120)]
    _, search, _ = install_selection(monkeypatch, keys)
    report = market.select_category('리뷰', 1, [])
    assert report['evaluated_candidates'] == 24 and search.call_count == 24
    assert report['research_stop_reason'] == 'round_limit'
    assert len(report['failure_history']) == 24
    ticks = iter([0, 0, 0, market.MAX_RESEARCH_SECONDS])
    monkeypatch.setattr(market, 'monotonic', lambda: next(ticks))
    report = market.select_category('리뷰', 1, [])
    assert report['evaluated_candidates'] == 1
    assert report['research_stop_reason'] == 'time_budget'
    assert len(report['failure_history']) == 1


def test_cli_repeated_invocations_preserve_memory_and_select_different_keyword(tmp_path, monkeypatch):
    from scripts import select_blog_keywords as cli
    old, new = '노트북램비교', '노트북배터리사용시간'
    _, first_search, _ = install_selection(monkeypatch, [old])
    report_path = tmp_path / 'report.json'
    (tmp_path / 'data').mkdir(exist_ok=True)
    queue_path = tmp_path / 'data/topic_queue_general.json'
    queue_path.write_text('[]')
    monkeypatch.setattr(cli, 'ROOT', tmp_path)
    monkeypatch.setattr(cli, 'REPORT', report_path)
    monkeypatch.setattr(cli, 'load_dotenv', lambda: None)
    monkeypatch.setattr(cli, 'existing_titles', lambda: [])
    monkeypatch.setattr('sys.argv', ['select', '--category', '리뷰', '--reuse', '--enqueue'])
    assert cli.main() == 1
    first_search.assert_called_once_with(old)
    saved = json.loads(report_path.read_text())['리뷰']['failure_history']
    _, next_search, _ = install_selection(monkeypatch, [old, new], passing=[new])
    assert cli.main() == 0
    next_search.assert_called_once_with(new)
    result = json.loads(report_path.read_text())['리뷰']
    assert result['failure_history'] == saved
    assert result['selected'][0]['keyword'] == new
    queue = json.loads(queue_path.read_text())
    assert len(queue) == 1 and queue[0]['keyword'] == new
    assert market.fresh_market_item(queue[0], '리뷰')
