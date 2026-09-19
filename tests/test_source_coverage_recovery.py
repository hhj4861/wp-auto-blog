"""Mock semantic answers and transport; run real evidence bindings and gates."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from unittest.mock import Mock

import pytest

from src import market_topics as market
from tests.test_market_topics import (
    candidate, evidence, synthetic_plan_review, synthetic_search_review,
    analysis, organic_sample,
)


@pytest.fixture
def recovery(monkeypatch):
    item = candidate()
    detail = evidence('https://other.go.kr/details')
    detail['excerpt'] += ' 공식 기관의 누락 서류 보완 절차와 확인 창구를 안내합니다.'
    detail['sha256'] = sha256(detail['excerpt'].encode()).hexdigest()
    research = Mock(return_value=([detail], {'provider': 'codex_web', 'searched': True}))
    monkeypatch.setattr(market, 'research_official_sources', research)
    monkeypatch.setattr('requests.sessions.Session.request', Mock(side_effect=AssertionError('No live HTTP')))
    monkeypatch.delenv('CAK_KEYWORD_CANDIDATES_FILE', raising=False)
    return item, detail, research


def install_reviews(monkeypatch, *, always_hold=False, invalid_retry=False, cost=False):
    calls = []

    def reviewer(item, now, _):
        raw = deepcopy(synthetic_plan_review(item, now, None)['review'])
        if cost:
            for row in raw['sources']:
                row.update(entity='공식병원', context='single_institution')
        if not calls or always_hold:
            raw['scope'] = 'unknown'
            raw['required_facets'][0].update(supported=False, answer='서류 보완 절차가 부족합니다.')
        elif invalid_retry:
            raw['required_facets'][0]['quote'] = '원문에 없는 인용입니다.'
        calls.append(deepcopy(item))
        return market.suitability.review_plan(item, now, lambda _: raw)

    monkeypatch.setattr(market, 'review_plan', reviewer)
    return calls


def run(item, budget=None):
    return market._review_source_coverage(item, item['selected_at'], budget=budget or {'attempts': 0})


def test_new_body_is_rechecked_without_changing_query_or_measured_demand(recovery, monkeypatch):
    item, detail, research = recovery
    original = deepcopy(item)
    calls = install_reviews(monkeypatch)
    budget = {'attempts': 0}
    assert run(item, budget) == []
    assert budget['attempts'] == 1 and len(calls) == 2
    assert item['verified_sources'] == [detail, *original['verified_sources']]
    for key in ('keyword', 'topic', 'intent', 'gap', 'monthly_search', 'organic_results',
                'organic_provider', 'selected_at', 'opportunity_evidence'):
        assert item[key] == original[key]
    assert item['source_url'] == detail['url']
    audit = item['decision_diagnostics']['coverage_recovery']
    assert audit['outcome'] == 'review_passed'
    assert audit['requirements']['missing_facets'] == [
        {'question': item['intent'], 'missing_evidence': '서류 보완 절차가 부족합니다.'}]
    research.assert_called_once_with(item['keyword'], item['category'], item['selected_at'],
                                     coverage_gaps=audit['requirements'])
    assert market.suitability.issues(item, datetime.fromisoformat(item['selected_at'])) == []
    assert market.opportunity.issues(item, datetime.fromisoformat(item['selected_at'])) == []


@pytest.mark.parametrize('failure', ['exception', 'no_body', 'same_url', 'same_body', 'unsafe', 'no_search'])
def test_unusable_research_keeps_original_hold_and_evidence(recovery, monkeypatch, failure):
    item, detail, research = recovery
    original = deepcopy(item)
    calls = install_reviews(monkeypatch)
    if failure == 'exception':
        research.side_effect = RuntimeError('private provider error')
    elif failure == 'no_body':
        research.return_value = ([], {'provider': 'codex_web', 'searched': True})
    elif failure == 'same_url':
        detail['url'] = item['source_url']
    elif failure == 'same_body':
        detail.update(excerpt=item['verified_sources'][0]['excerpt'],
                      sha256=item['verified_sources'][0]['sha256'])
    elif failure == 'unsafe':
        detail['url'] = 'https://untrusted.example/detail'
    else:
        research.return_value = ([detail], {'provider': 'codex_web', 'searched': False})
    assert set(run(item)) == {'narrower_source_coverage', 'unverified_source_coverage'}
    assert item['verified_sources'] == original['verified_sources']
    assert len(calls) == 1
    assert 'private provider error' not in str(item)


@pytest.mark.parametrize('invalid', [False, True])
def test_still_unsupported_or_ungrounded_retry_cannot_publish(recovery, monkeypatch, invalid):
    item, _, research = recovery
    calls = install_reviews(monkeypatch, always_hold=not invalid, invalid_retry=invalid)
    assert run(item)
    assert len(calls) == 2
    assert item['decision_diagnostics']['coverage_recovery']['outcome'] == 'review_rejected'
    assert run(item)  # Already attempted: never performs a second research call.
    research.assert_called_once()


@pytest.mark.parametrize('guard', ['budget', 'earlier_recovery', 'invalid_serp', 'currentness'])
def test_recovery_never_bypasses_other_gates_or_shared_budget(recovery, monkeypatch, guard):
    item, _, research = recovery
    install_reviews(monkeypatch)
    budget = {'attempts': market.MAX_SOURCE_RECOVERIES if guard == 'budget' else 0}
    if guard == 'earlier_recovery':
        item['decision_diagnostics'] = {'source_recovery': {'attempted': True}}
    elif guard == 'invalid_serp':
        item['organic_results'][0]['snippet'] = 'changed after search review'
    elif guard == 'currentness':
        original_review = market.review_plan
        def unknown_currentness(*args):
            bound = original_review(*args)
            bound['review']['current_relevance']['kind'] = 'unknown'
            return bound
        monkeypatch.setattr(market, 'review_plan', unknown_currentness)
    assert run(item, budget)
    research.assert_not_called()


def test_one_institution_stays_held_despite_new_url_and_positive_model_opinion(recovery, monkeypatch):
    _, detail, research = recovery
    item = candidate(keyword='CT비용', category='건강')
    detail['url'] = 'https://example.go.kr/second-price-page'
    for source in [*item['verified_sources'], detail]:
        source['excerpt'] += ' 공식병원의 CT 검사 비용은 100,000원입니다.'
        source['sha256'] = sha256(source['excerpt'].encode()).hexdigest()
    install_reviews(monkeypatch, cost=True)
    assert 'narrower_source_coverage' in run(item)
    research.assert_called_once()
    assert item['decision_diagnostics']['coverage_recovery']['outcome'] == 'review_rejected'


def test_missing_facets_reach_research_prompt_but_locators_still_require_fetch(monkeypatch):
    from src import codex_client
    detail = evidence('https://other.go.kr/details')
    client = Mock()
    client.research.return_value = {'searched': True, 'opened_urls': [detail['url']], 'text': ''}
    monkeypatch.setattr(codex_client, 'CodexSubscriptionClient', Mock(return_value=client))
    fetch = Mock(return_value=None)
    monkeypatch.setattr(market, 'fetch_source', fetch)
    gaps = {'missing_facets': [{'question': '누락된 항목', 'missing_evidence': '독립 기관 가격표'}]}
    sources, _ = market.research_official_sources('CT비용', '건강', '2026-09-19', coverage_gaps=gaps)
    assert sources == []
    assert '독립 기관 가격표' in client.research.call_args.args[0]
    fetch.assert_called_once_with(detail['url'])


def test_selection_and_queue_accept_only_revalidated_coverage(recovery, monkeypatch, tmp_path):
    original, _, research = recovery
    keyword = original['keyword']
    monkeypatch.setattr(market, 'ROOT', tmp_path)
    monkeypatch.setattr(market, 'LEDGER', tmp_path / 'ledger.json')
    monkeypatch.setattr(market, 'demand_candidates', lambda _: {keyword: {'keyword': keyword, 'monthly': 1200}})
    monkeypatch.setattr(market, 'search_results', lambda _: ('google_custom_search', organic_sample(keyword)))
    monkeypatch.setattr(market, 'review_search', synthetic_search_review)
    monkeypatch.setattr(market, 'candidate_sources', lambda *_: original['verified_sources'])
    monkeypatch.setattr(market, 'ask', Mock(side_effect=[{'candidates': [{'keyword': keyword}]}, analysis(keyword)]))
    monkeypatch.setattr(market, 'fetch_trend_change', lambda _: None)
    install_reviews(monkeypatch)
    report = market.select_category('취업', 1, titles=[])
    assert report['rejected'] == report['held'] == []
    assert report['source_recovery_attempts'] == 1
    selected = report['selected'][0]
    assert market.fresh_market_item(selected, '취업')
    assert market.enqueue_report([], report) == [selected]
    assert selected['monthly_search'] == 1200 and selected['keyword'] == keyword
    research.assert_called_once()
