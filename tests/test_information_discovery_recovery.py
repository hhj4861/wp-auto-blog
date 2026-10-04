"""Recorded October 4 failures, replayed at external boundaries without relaxing gates."""
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from src import market_topics as market, search_quality as quality
from tests.test_market_topics import evidence
from tests.test_market_topics import isolated_market_history as isolated_market_history
from tests.test_selection_feedback import install_selection, failed_report

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/information_selection_20261004.json').read_text())


def test_recorded_productivity_uncertainty_gets_bounded_real_research(monkeypatch):
    recorded = FIXTURE['categories']['생산성']
    assert recorded['measured_candidates'] == 351 and recorded['evaluated_candidates'] == 1
    skipped = recorded['proposal_rounds'][1]['skipped']
    keys = [row['keyword'] for row in skipped if row['reason_code'] in {'insufficient_specificity', 'not_reported'}]
    key = next(row['keyword'] for row in market.information_research_candidates(skipped, 2, '생산성'))
    stats, search, _ = install_selection(monkeypatch, keys, category='생산성', passing=[key],
        shortlist=lambda _: {'candidates': [], 'skipped': skipped})
    # Use the same measured candidate order as the recorded shortlist.
    for row in stats.values():
        row['monthly'] = 1200
    report = market.select_category('생산성', 1, [])
    assert report['shortlist_research_attempts'] <= market.MAX_SHORTLIST_RESEARCH
    assert key in [call.args[0] for call in search.call_args_list]
    assert report['selected'][0]['keyword'] == key
    assert market.fresh_market_item(report['selected'][0], '생산성')
    assert market.enqueue_report([], report)[0]['monthly_search'] == 1200


def test_information_pool_refills_past_the_original_120_candidates(monkeypatch):
    keys = [f'엑셀주제{i:03}' for i in range(135)]
    target = keys[-1]
    def shortlist(rows):
        return {'candidates': [{'keyword': target}] if target in [r['keyword'] for r in rows] else [],
                'skipped': [{'keyword': r['keyword'], 'reason_code': 'scope_too_broad'}
                            for r in rows if r['keyword'] != target]}
    stats, search, offered = install_selection(monkeypatch, keys, category='생산성', passing=[target], shortlist=shortlist)
    for i, key in enumerate(keys):
        stats[key]['monthly'] = 2000 - i
    report = market.select_category('생산성', 1, [])
    assert len(offered) == 3 and target not in offered[0] + offered[1]
    search.assert_called_once_with(target)
    assert report['research_pool_size'] == 135
    assert report['selected'][0]['keyword'] == target


@pytest.mark.parametrize('response', [{}, {'candidates': None}, {'candidates': [{'keyword': 'invented'}]}])
def test_malformed_information_shortlist_cannot_force_research(monkeypatch, response):
    _, search, _ = install_selection(monkeypatch, ['엑셀함수'], category='생산성', shortlist=lambda _: response)
    report = market.select_category('생산성', 1, [])
    search.assert_not_called()
    assert not report['selected']


@pytest.mark.parametrize('code', ['duplicate_intent', 'category_mismatch', 'scope_too_broad'])
def test_explicit_negative_opinions_are_not_overridden(monkeypatch, code):
    _, search, _ = install_selection(monkeypatch, ['엑셀함수'], category='생산성', shortlist=lambda _: {
        'candidates': [], 'skipped': [{'keyword': '엑셀함수', 'reason_code': code}]})
    report = market.select_category('생산성', 1, [])
    search.assert_not_called()
    assert not report['selected']


def test_uncertain_research_is_bounded_and_negative_evidence_stays_rejected(monkeypatch):
    keys = [f'엑셀함수{i}' for i in range(8)]
    _, search, _ = install_selection(monkeypatch, keys, category='생산성', shortlist=lambda _: {'candidates': []})
    report = market.select_category('생산성', 1, [])
    assert search.call_count == report['shortlist_research_attempts'] == 3
    assert not report['selected'] and len(report['rejected']) == 3
    with pytest.raises(RuntimeError):
        market.enqueue_report([], report)


def test_information_recovery_preserves_cooldowns_and_duplicate_exclusions(monkeypatch):
    keys = ['엑셀함수', '엑셀단축키', '엑셀정렬', '엑셀필터']
    history = market.load_history(failed_report(keys[:1], category='생산성', at=datetime.now(timezone.utc)),
                                  '생산성', datetime.now(timezone.utc))
    _, search, _ = install_selection(monkeypatch, keys, category='생산성', passing=keys,
                                     shortlist=lambda _: {'candidates': []})
    report = market.select_category('생산성', 1, [keys[1]], excluded_keywords=[keys[2]], failure_history=history)
    search.assert_called_once_with(keys[3])
    assert report['failure_history'] == history


def test_health_routes_clinical_sources_before_statutes(monkeypatch):
    sources = [evidence('https://law.go.kr/detail'), evidence('https://cdc.gov/herpes/about/index.html')]
    fetch = Mock(side_effect=lambda url: next(s for s in sources if s['url'] == url))
    monkeypatch.setattr(market, 'fetch_source', fetch)
    lookup = Mock(return_value=[s['url'] for s in sources])
    monkeypatch.setattr(market, 'official_search_urls', lookup)
    assert market.candidate_sources('헤르페스입술', [{'url': sources[0]['url']}], '건강') == sources[1:]
    fetch.assert_called_once_with(sources[1]['url'])
    lookup.assert_called_once_with('헤르페스입술', '건강')
    assert market.candidate_sources('건강보험청구', [{'url': sources[0]['url']}], '건강')[0] == sources[0]


def test_health_official_queries_do_not_search_generic_government_domains(monkeypatch):
    search = Mock(return_value=('codex_native_search', []))
    monkeypatch.setattr(market, 'search_results', search)
    market.official_search_urls('호호바오일사용법', '건강')
    assert [call.args[0] for call in search.call_args_list] == [
        f'호호바오일사용법 site:{domain}' for domain in ('kdca.go.kr', 'cancer.go.kr', 'medlineplus.gov', 'cdc.gov')]


def test_native_health_research_excludes_statutes_and_requests_medical_details(monkeypatch):
    from src import codex_client
    law, detail = 'https://law.go.kr/detail', 'https://medlineplus.gov/detail'
    client = Mock()
    client.research.return_value = {'searched': True, 'opened_urls': [law, detail], 'text': ''}
    monkeypatch.setattr(codex_client, 'CodexSubscriptionClient', Mock(return_value=client))
    fetch = Mock(return_value=evidence(detail))
    monkeypatch.setattr(market, 'fetch_source', fetch)
    sources, trace = market.research_official_sources('호호바오일사용법', '건강', '2026-10-04')
    fetch.assert_called_once_with(detail)
    assert sources[0]['url'] == detail and trace['searched']
    assert '영어 의학 용어' in client.research.call_args.args[0]


def test_recorded_quote_failure_recovers_using_exact_original_passages(monkeypatch):
    results = FIXTURE['quote_failure_results']
    recorded = FIXTURE['categories']['건강']['search_review_diagnostics'][0]
    assert [row['code'] for row in recorded['attempts']] == ['unverified_result_quote'] * 2
    prompts = []
    rows = quality.raw_rows(results)
    def review(prompt):
        prompts.append(prompt)
        return {'decisions': [{'result_index': index, 'relevant': False,
                              'quote_index': 99 if len(prompts) == 1 else 0} for index, _ in rows]}
    monkeypatch.setattr(market, 'review_search', quality.review_search)
    monkeypatch.setattr(market, 'ask', review)
    audit = {}
    report = market._search_review_with_recovery('기미없애는법', 'codex_native_search', results,
        '2026-10-04T02:23:16+00:00', '기미 없애는 법', budget={'attempts': 0}, audit=audit)
    assert len(prompts) == 2 and 'result_index=0' in prompts[1]
    assert audit['attempts'][0]['result_index'] == 0
    for row in report['decisions']:
        assert row['quote'] == quality.quote_choices(dict(rows)[row['result_index']])[0]
    # A valid response is not positive evidence. Negative relevance must still block selection.
    assert 'insufficient_relevant_results' in quality.quality_issues('기미없애는법', 'codex_native_search',
        results, '2026-10-04T02:23:16+00:00', report, executed_query='기미 없애는 법')


@pytest.mark.parametrize('choice', [-1, 999, True, '0'])
def test_invalid_quote_choice_stays_fail_closed(choice):
    rows = quality.raw_rows(FIXTURE['quote_failure_results'])
    with pytest.raises(quality.SearchReviewError, match='unverified_result_quote'):
        quality.resolve_quote_choices(rows, [{'result_index': 0, 'relevant': True, 'quote_index': choice}])


@pytest.mark.parametrize('keyword', ['건강보험청구', 'MRI비용', '건강검진대상조회', '의료법', '예방접종지원금'])
def test_health_administration_keeps_legal_and_billing_sources(keyword):
    assert not market.clinical_health_query(keyword, '건강')


def test_information_research_stops_at_original_deadline(monkeypatch):
    clock = [0]
    monkeypatch.setattr(market, 'monotonic', lambda: clock[0])
    def shortlist(_):
        clock[0] = market.MAX_RESEARCH_SECONDS
        return {'candidates': []}
    _, search, _ = install_selection(monkeypatch, ['엑셀함수'], category='생산성', shortlist=shortlist)
    report = market.select_category('생산성', 1, [])
    search.assert_not_called()
    assert report['research_stop_reason'] == 'time_budget'


def test_quote_choice_review_is_bound_to_original_search_bytes():
    results = FIXTURE['quote_failure_results']
    rows = quality.raw_rows(results)
    review = quality.review_search('기미없애는법', 'codex_native_search', results,
        '2026-10-04T02:23:16+00:00', lambda _: {'decisions': [
            {'result_index': index, 'relevant': True, 'quote_index': 0} for index, _ in rows]})
    changed = [dict(row) for row in results]
    changed[0]['snippet'] += ' 변경된 원문'
    assert quality.quality_issues('기미없애는법', 'codex_native_search', changed,
        '2026-10-04T02:23:16+00:00', review) == ['search_review_binding_mismatch']
