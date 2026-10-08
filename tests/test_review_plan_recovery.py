"""Replay a real production hold; mock external responses, retain real gates."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from src import market_topics as market
from src import selection_feedback as feedback
from tests.test_market_topics import isolated_market_history as isolated_market_history

FIXTURE = Path(__file__).parent / 'fixtures/review_held_20260930.json'


@pytest.fixture
def case(monkeypatch):
    item = json.loads(FIXTURE.read_text())['candidate']
    body = ('테스트청소기는 실제 상품이 아닌 회귀 테스트용 가상 사양입니다. '
            '청소기 본체 무게와 배터리·브러시를 포함한 전체 무게를 구분합니다. '
            '동일한 구성의 무게와 운전 모드별 사용시간을 비교해야 합니다.') * 3
    detail = {'url': 'https://www.lge.co.kr/vacuum-cleaners/test-only-fixture',
              'original_url': 'https://www.lge.co.kr/vacuum-cleaners/test-only-fixture',
              'title': '테스트청소기 무게 비교 사양', 'excerpt': body,
              'sha256': sha256(body.encode()).hexdigest(), 'checked_on': '2026-09-30'}
    trace = {'provider': 'codex_web', 'searched': True}
    research = Mock(return_value=([detail], trace))
    monkeypatch.setattr(market, 'research_official_sources', research)
    monkeypatch.setattr(market, 'review_plan', market.suitability.review_plan)
    quotes = {source['url']: quote for source, quote in zip(item['verified_sources'],
              item['suitability_evidence']['review']['sources'])}
    quotes[detail['url']] = {'quote': body, 'entity': '테스트청소기', 'context': 'single_institution'}
    responses = {'plan': None, 'review': None}
    prompts = []

    def ask(prompt):
        prompts.append(prompt)
        if '검색어는 가벼운청소기입니다.' in prompt:
            data = json.loads(prompt.rsplit('데이터: ', 1)[1])
            pool = data['official_sources']
            index = next(i for i, row in enumerate(pool) if row['url'] == detail['url'])
            response = {'supported': True, 'category': '리뷰',
                'topic': '가벼운청소기 선택 기준: 구성별 무게와 용도 비교',
                'intent': '가벼운청소기의 제품별 구성 무게와 사용 조건을 어떻게 비교할까?',
                'gap': '공식 사양에 근거한 비교표와 구성 확인표', 'source_index': 0,
                'source_indices': [0, index],
                'serp_indices': [row['result_index'] for row in item['opportunity_evidence']['matches']],
                'valid_until': None,
                'intent_evidence': {key: item['opportunity_evidence'][key]
                                    for key in ('scope', 'target_keyword', 'matches')}}
            if responses['plan']:
                responses['plan'](response)
            return response
        data = json.loads(prompt.rsplit('데이터: ', 1)[1])['candidate']
        sources = data['verified_sources']
        raw = {'scope': 'full_keyword', 'target_keyword': data['keyword'],
            'sources': [{**quotes[row['url']], 'source_index': i} for i, row in enumerate(sources)],
            'required_facets': [{'facet': data['intent'], 'answer': '공식 자료의 동일 구성을 비교합니다.',
                                'supported': True, 'source_index': i, 'quote': quotes[row['url']]['quote']}
                               for i, row in enumerate(sources)],
            'current_relevance': {'kind': 'evergreen', 'source_index': 0,
                                 'quote': quotes[sources[0]['url']]['quote'],
                                 'event_start': None, 'event_end': None, 'date_quote': None}}
        if responses['review']:
            responses['review'](raw)
        return raw

    reviewer = Mock(side_effect=ask)
    monkeypatch.setattr(market, 'ask', reviewer)
    return item, detail, research, reviewer, responses, prompts


def recover(case, *, budget=None, reasons=None, titles=(), deadline=float('inf')):
    item = case[0]
    return market._recover_review_plan(item, item['selected_at'],
        item['hold_reasons'] if reasons is None else reasons,
        budget={'attempts': 1} if budget is None else budget, titles=list(titles), deadline=deadline)


def publishable(item):
    item.update(status='pending', hold_reasons=[], publish_eligible=True, selection_version=market.PROCESS_VERSION)
    item['score_components']['intent_fit'] = 15
    item['score'] = round(sum(item['score_components'].values()), 2)
    return market.fresh_market_item(item, '리뷰', datetime.fromisoformat(item['selected_at']))


def test_recorded_failure_requires_more_than_initial_detail_recovery(case):
    item, detail, research, reviewer, _, prompts = case
    original = deepcopy(item)
    now = datetime.fromisoformat(item['selected_at'])
    assert market.opportunity.issues(item, now) == []
    assert set(market.suitability.issues(item, now)) == set(item['hold_reasons'])
    assert item['decision_diagnostics']['source_recovery']['outcome'] == 'review_passed'
    budget = {'attempts': 1}
    assert recover(case, budget=budget) == []
    assert budget['attempts'] == 2 and research.call_count == 1 and reviewer.call_count == 2
    assert item['topic'] != original['topic'] and item['gap'] != original['gap']
    for key in ('keyword', 'category', 'monthly_search', 'demand_scope', 'selected_at',
                'organic_results', 'organic_query', 'organic_provider', 'failure_history'):
        assert item.get(key) == original.get(key)
    assert detail['url'] in [row['url'] for row in item['verified_sources']]
    assert item['decision_diagnostics']['plan_recovery']['outcome'] == 'review_passed'
    assert market.opportunity.issues(item, now) == market.suitability.issues(item, now) == []
    assert publishable(item)
    assert '기존 기획은' in prompts[0] and 'eligible_result_indices' in prompts[0]
    gaps = research.call_args.kwargs['coverage_gaps']
    assert gaps['recovery_type'] == 'review_plan'
    assert gaps['missing_facets'][0]['question'].startswith('가벼운 청소기 중 어떤 제품')
    with pytest.raises(RuntimeError):
        market.enqueue_report([], {'category': '리뷰', 'selected': [original]})


@pytest.mark.parametrize('failure', ['no_body', 'same_url', 'same_body', 'same_excerpt', 'untrusted',
                                  'irrelevant', 'no_search', 'wrong_provider', 'research_exception'])
def test_no_new_verified_body_cannot_reroll_semantic_approval(case, failure):
    item, detail, research, reviewer, _, _ = case
    original = deepcopy(item)
    if failure == 'no_body': research.return_value = ([], {'provider': 'codex_web', 'searched': True})
    elif failure == 'same_url': detail['url'] = item['verified_sources'][0]['url']
    elif failure == 'same_body': detail['sha256'] = item['verified_sources'][0]['sha256']
    elif failure == 'same_excerpt': detail['excerpt'] = item['verified_sources'][0]['excerpt']
    elif failure == 'untrusted': detail['url'] = 'https://untrusted.example/detail'
    elif failure == 'irrelevant': detail.update(title='휴대폰', excerpt='스마트폰 배터리 사용시간')
    elif failure == 'no_search': research.return_value = ([detail], {'provider': 'codex_web', 'searched': False})
    elif failure == 'wrong_provider': research.return_value = ([detail], {'provider': 'model_opinion', 'searched': True})
    else: research.side_effect = RuntimeError('SECRET-SENTINEL')
    assert recover(case) == original['hold_reasons']
    reviewer.assert_not_called()
    for key in ('topic', 'intent', 'gap', 'verified_sources', 'opportunity_evidence', 'suitability_evidence'):
        assert item[key] == original[key]
    assert 'SECRET-SENTINEL' not in json.dumps(item)
    assert recover(case)  # No second research attempt for this candidate.
    research.assert_called_once()


@pytest.mark.parametrize('failure', ['unsupported', 'new_source_unused', 'invalid_source_index',
    'narrow_intent', 'fabricated_intent_quote', 'narrow_coverage', 'missing_facet',
    'fabricated_source_quote', 'expired', 'duplicate'])
def test_replanning_never_bypasses_existing_publication_gates(case, failure):
    item, _, _, _, responses, _ = case
    original = deepcopy(item)
    if failure == 'unsupported': responses['plan'] = lambda x: x.update(supported=False)
    elif failure == 'new_source_unused': responses['plan'] = lambda x: x.update(source_indices=[0])
    elif failure == 'invalid_source_index': responses['plan'] = lambda x: x.update(source_indices=[99])
    elif failure == 'narrow_intent': responses['plan'] = lambda x: x['intent_evidence'].update(scope='narrower_query')
    elif failure == 'fabricated_intent_quote': responses['plan'] = lambda x: x['intent_evidence'].update(matches=[{'result_index': 0, 'quote': '원문에 존재하지 않는 검색 인용입니다'}])
    elif failure == 'narrow_coverage': responses['review'] = lambda x: x.update(scope='narrower_query')
    elif failure == 'missing_facet': responses['review'] = lambda x: x['required_facets'][0].update(supported=False)
    elif failure == 'fabricated_source_quote': responses['review'] = lambda x: x['required_facets'][0].update(quote='존재하지 않는 공식 자료의 인용입니다')
    elif failure == 'expired': responses['plan'] = lambda x: x.update(valid_until='2020-01-01')
    titles = ['가벼운청소기 선택 기준: 구성별 무게와 용도 비교'] if failure == 'duplicate' else []
    assert recover(case, titles=titles)
    for key in ('topic', 'intent', 'gap', 'verified_sources', 'opportunity_evidence', 'suitability_evidence'):
        assert item[key] == original[key]
    assert not publishable(item)


@pytest.mark.parametrize('guard', ['budget', 'time', 'different_category', 'search_changed', 'stale', 'other_hold'])
def test_unrelated_or_invalid_candidates_do_not_start_recovery(case, guard):
    item, _, research, reviewer, _, _ = case
    kwargs = {}
    if guard == 'budget': kwargs['budget'] = {'attempts': market.MAX_SOURCE_RECOVERIES}
    elif guard == 'time': kwargs['deadline'] = 0
    elif guard == 'different_category': item['category'] = '건강'
    elif guard == 'search_changed': item['organic_results'][0]['snippet'] += ' changed'
    elif guard == 'stale': item['opportunity_evidence']['checked_at'] = '2020-01-01T00:00:00+00:00'
    else: kwargs['reasons'] = ['unverified_current_relevance']
    assert recover(case, **kwargs)
    research.assert_not_called()
    reviewer.assert_not_called()


@pytest.mark.parametrize('phase', ['research', 'plan', 'review'])
def test_deadline_is_checked_between_each_external_boundary(case, monkeypatch, phase):
    item, _, research, reviewer, _, _ = case
    times = {'research': [0, 2], 'plan': [0, 0, 2], 'review': [0, 0, 0, 2]}[phase]
    monkeypatch.setattr(market, 'monotonic', Mock(side_effect=times))
    assert recover(case, deadline=1)
    assert item['decision_diagnostics']['plan_recovery']['outcome'] == 'time_budget'
    assert reviewer.call_count == {'research': 0, 'plan': 1, 'review': 2}[phase]
    research.assert_called_once()


def test_three_old_source_slots_can_be_replanned_without_increasing_final_limit(case):
    item, detail, _, _, responses, _ = case
    third = deepcopy(item['verified_sources'][1])
    third.update(url='https://www.samsung.com/sec/old-third')
    item['verified_sources'].append(third)
    raw = deepcopy(item['suitability_evidence']['review'])
    raw['sources'].append({**raw['sources'][1], 'source_index': 2})
    item['suitability_evidence'] = market.suitability.review_plan(item,
        datetime.fromisoformat(item['selected_at']), lambda _: raw)
    # Prompt pool may hold six bodies; the new plan must still select at most three.
    assert recover(case) == []
    assert len(item['verified_sources']) == 2
    assert item['verified_sources'][1]['url'] == detail['url']
    assert publishable(item)


def test_same_valid_search_can_repair_bad_intent_quotes_only_with_new_evidence(case):
    item = case[0]
    item['opportunity_evidence']['matches'] = []
    # The response uses previously verified real quotes, rather than rewriting query demand.
    original_matches = json.loads(FIXTURE.read_text())['candidate']['opportunity_evidence']['matches']
    def valid_intent(response):
        response['intent_evidence'].update(matches=original_matches)
        response['serp_indices'] = [row['result_index'] for row in original_matches]
    case[4]['plan'] = valid_intent
    assert recover(case, reasons=['unverified_intent_quotes']) == []
    assert publishable(item)


def test_failure_history_and_queue_keep_rejecting_unrepaired_candidate(case):
    item = case[0]
    case[2].return_value = ([], None)
    assert recover(case)
    now = datetime.fromisoformat(item['selected_at'])
    history = feedback.load_history({'category': '리뷰', 'selected_at': item['selected_at'],
                                     'selected': [], 'held': [item]}, '리뷰', now)
    assert history[0]['reason_code'] == 'source_coverage'
    assert history[0]['retry_after'] > item['selected_at']
    with pytest.raises(RuntimeError): market.enqueue_report([], {'category': '리뷰', 'selected': [item]})


def test_real_failure_replay_runs_selection_repair_final_checks_and_queue(case, monkeypatch):
    item, detail, research, reviewer, _, _ = case
    original = deepcopy(item)
    fixed = datetime.fromisoformat(item['selected_at'])
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed.astimezone(tz or timezone.utc)
    monkeypatch.setattr(market, 'datetime', Clock)
    key = item['keyword']
    monkeypatch.setattr(market, 'demand_candidates', lambda _: {key: {'keyword': key, 'monthly': 1610}})
    search = Mock(return_value=(item['organic_provider'], deepcopy(item['organic_results'])))
    monkeypatch.setattr(market, 'search_results', search)
    monkeypatch.setattr(market, 'review_search', lambda *a, **kw: deepcopy(original['opportunity_evidence']['search_review']))
    monkeypatch.setattr(market, 'candidate_sources', lambda *a, **kw: [deepcopy(original['verified_sources'][1])])
    monkeypatch.setattr(market, 'fetch_trend_change', lambda _: original['trend_growth'])
    research.side_effect = [(deepcopy(original['verified_sources']), {'provider': 'codex_web', 'searched': True}),
                            ([detail], {'provider': 'codex_web', 'searched': True})]
    initial_calls = []
    def ask(prompt):
        if '조사 후보를 고르세요.' in prompt:
            return {'candidates': [{'keyword': key, 'search_query': original['organic_query']}]}
        if '검색어는 가벼운청소기입니다.' in prompt and '기존 기획은 아래 검증에서' not in prompt:
            initial_calls.append(prompt)
            if len(initial_calls) == 1:
                return {'supported': False, 'rejection_reason': 'source_missing_detail'}
            return {'supported': True, 'category': '리뷰',
                **{key: original[key] for key in ('topic', 'intent', 'gap', 'valid_until')},
                'source_index': 0, 'source_indices': [0, 1],
                'serp_indices': [row['result_index'] for row in original['opportunity_evidence']['matches']],
                'intent_evidence': {key: deepcopy(original['opportunity_evidence'][key])
                                   for key in ('scope', 'target_keyword', 'matches')}}
        if '검색어는 가벼운청소기입니다.' not in prompt:
            data = json.loads(prompt.rsplit('데이터: ', 1)[1])['candidate']
            if data['topic'] == original['topic']:
                return deepcopy(original['suitability_evidence']['review'])
        return reviewer(prompt)
    monkeypatch.setattr(market, 'ask', ask)
    report = market.select_category('리뷰', 1, titles=[])
    assert not report['held'] and not report['rejected'] and len(report['selected']) == 1
    assert report['source_recovery_attempts'] == research.call_count == 2
    selected = report['selected'][0]
    assert selected['keyword'] == key and selected['monthly_search'] == 1610
    assert selected['topic'] != original['topic']
    assert market.fresh_market_item(selected, '리뷰', fixed)
    actual_fresh = market.fresh_market_item
    monkeypatch.setattr(market, 'fresh_market_item', lambda row, category, now=None: actual_fresh(row, category, fixed))
    assert market.enqueue_report([], report) == [selected]
    # Writer/queue reuse still checks bindings: a changed claim cannot reach publication.
    selected['gap'] += ' 근거에 없는 추가 주장'
    assert not market.fresh_market_item(selected, '리뷰')
    with pytest.raises(RuntimeError): market.enqueue_report([], report)
    search.assert_called_once_with(original['organic_query'])
