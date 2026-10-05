"""Recover source acquisition, while retaining search and publication gates."""
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from src import analysis_runtime as runtime
from src import editorial, market_topics as market
from src.codex_search import NativeSearchError
from tests.test_market_topics import (
    analysis, evidence, organic_sample,
    isolated_market_history,  # noqa: F401
)


@pytest.fixture(autouse=True)
def isolated(isolated_market_history):
    pass


def recruit_case(monkeypatch, *, repeat=False, same=False, keyword='한국부동산원채용'):
    old = evidence('https://example.go.kr/old')
    new = evidence('https://example.go.kr/current')
    new['excerpt'] += ' 신규 채용의 새로운 공식 상세 근거입니다.'
    import hashlib
    new['sha256'] = hashlib.sha256(new['excerpt'].encode()).hexdigest()
    if same:
        new = deepcopy(old)
    no = {'supported': False, 'rejection_reason': 'expired_information'}
    model = Mock(side_effect=[no, no if repeat else analysis(keyword)])
    research = Mock(return_value=([new], {'provider': 'codex_web', 'searched': True}))
    monkeypatch.setattr(market, 'ask', model)
    monkeypatch.setattr(market, 'research_official_sources', research)
    return keyword, old, new, model, research


def recover(case, category='취업', budget=None):
    keyword, old, _, _, _ = case
    return market._review_with_source_recovery(keyword, category, datetime.now(timezone.utc).isoformat(),
        organic_sample(keyword), [old], provider='codex_native_search', evidence_mode='serp',
        research=None, allow_recovery=True, budget=budget if budget is not None else {'attempts': 0})


def test_expired_recruitment_researches_new_evidence_once_and_discards_old_body(monkeypatch):
    case = recruit_case(monkeypatch)
    budget = {'attempts': 0}
    item, reason, _, audit = recover(case, budget=budget)
    assert reason is None and budget['attempts'] == 1
    assert item['verified_sources'] == [case[2]]
    assert case[3].call_count == 2
    requirements = case[4].call_args.kwargs['coverage_gaps']
    assert requirements['recovery_type'] == 'current_recruitment'
    assert requirements['existing_urls'] == [case[1]['url']]
    assert audit['source_recovery']['outcome'] == 'review_passed'
    assert len(audit['source_recovery']['retry_review']['official_sources']) == 1


@pytest.mark.parametrize('same,repeat', [(True, False), (False, True)])
def test_no_new_evidence_or_still_expired_stays_rejected(monkeypatch, same, repeat):
    case = recruit_case(monkeypatch, same=same, repeat=repeat)
    item, reason, _, audit = recover(case)
    assert item is None and reason
    assert case[4].call_count == 1
    assert case[3].call_count == (1 if same else 2)
    assert audit['source_recovery']['outcome'] == ('no_changed_source' if same else 'review_rejected')


@pytest.mark.parametrize('category,keyword,budget', [
    ('건강', '암검진', 0), ('취업', '식물보호기사', 0),
    ('취업', '한국부동산원채용', market.MAX_SOURCE_RECOVERIES),
])
def test_expired_recovery_is_scoped_and_bounded(monkeypatch, category, keyword, budget):
    case = recruit_case(monkeypatch, keyword=keyword)
    assert recover(case, category, {'attempts': budget})[0] is None
    case[4].assert_not_called()


def test_recovered_recruitment_runs_real_full_selection_gates(monkeypatch):
    keyword, old, new, model, research = recruit_case(monkeypatch)
    model.side_effect = [{'candidates': [{'keyword': keyword}]},
                        {'supported': False, 'rejection_reason': 'expired_information'}, analysis(keyword)]
    monkeypatch.setattr(market, 'demand_candidates', lambda _: {keyword: {'keyword': keyword, 'monthly': 1200}})
    monkeypatch.setattr(market, 'search_results', Mock(return_value=('codex_native_search', organic_sample(keyword))))
    monkeypatch.setattr(market, 'candidate_sources', Mock(return_value=[old]))
    monkeypatch.setattr(market, 'fetch_trend_change', lambda _: None)
    report = market.select_category('취업', 1, titles=[])
    assert len(report['selected']) == 1 and report['rejected'] == report['held'] == []
    item = report['selected'][0]
    assert item['monthly_search'] == 1200 and item['keyword'] == keyword
    assert item['verified_sources'] == [new]
    assert market.fresh_market_item(item, '취업')
    assert market.opportunity.issues(item) == market.suitability.issues(item) == []


def test_recruitment_prefers_employer_and_current_public_job_sources(monkeypatch):
    search = Mock(return_value=('codex_native_search', []))
    monkeypatch.setattr(market, 'search_results', search)
    assert market.official_search_urls('한국전력기술채용', '취업') == []
    queries = [c.args[0] for c in search.call_args_list]
    assert queries[0].endswith('site:kepco-enc.com')
    assert all('채용공고' in q and str(datetime.now().year) in q for q in queries)
    assert [q.split('site:')[1] for q in queries] == [
        'kepco-enc.com', 'job.alio.go.kr', 'gojobs.go.kr', 'work24.go.kr']
    assert market._official_search_extra_domains('삼성채용') == ['samsungcareers.com']
    assert market._official_search_extra_domains('한국부동산원채용') == ['reb.or.kr']
    assert editorial.is_official_url('https://www.kepco-enc.com/board.es?act=view')
    assert not editorial.is_official_url('https://kepco-enc.com.attacker.example/board.es')


def test_invalid_native_arguments_retry_exact_query_once(caplog):
    rows = organic_sample('한국부동산원채용')
    call = Mock(side_effect=[NativeSearchError('invalid_search_arguments'), rows])
    assert runtime.validated_call(call, '한국부동산원채용', label='native_search') == rows
    assert [c.args[0] for c in call.call_args_list] == ['한국부동산원채용'] * 2
    assert 'invalid_search_arguments' in caplog.text


@pytest.mark.parametrize('code', ['invalid_search_arguments', 'unexpected_web_activity', 'unexpected_search_query'])
def test_invalid_or_unbound_native_search_never_returns_unverified_rows(code):
    call = Mock(side_effect=NativeSearchError(code))
    with pytest.raises(runtime.AnalysisError):
        runtime.validated_call(call, '한국부동산원채용', label='native_search')
    assert call.call_count == (2 if code == 'invalid_search_arguments' else 1)


def test_non_search_validation_does_not_gain_retry():
    call = Mock(side_effect=NativeSearchError('invalid_search_arguments'))
    with pytest.raises(runtime.AnalysisError):
        runtime.validated_call(call, '한국부동산원채용', label='topic_plan')
    call.assert_called_once()
