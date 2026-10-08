"""Production Wi-Fi intent mismatch: repair requires fresh text and both gates."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from src import market_topics as market
from tests.test_market_topics import isolated_market_history
from tests.test_selection_feedback import install_selection

RECORDED = json.loads((Path(__file__).parent / 'fixtures/tech_held_20261008.json').read_text())


@pytest.fixture
def technical_case(monkeypatch):
    item = deepcopy(RECORDED['candidate'])
    detail = deepcopy(RECORDED['new_source'])
    research = Mock(return_value=([detail], {'provider': 'codex_web', 'searched': True}))
    monkeypatch.setattr(market, 'research_official_sources', research)
    def review(item, now, _):
        quote = item['verified_sources'][0]['excerpt'][:500]
        raw = {'scope': 'full_keyword', 'target_keyword': item['keyword'],
            'sources': [{'source_index': 0, 'quote': quote, 'entity': 'TP-Link 공유기', 'context': 'general'}],
            'required_facets': [{'facet': item['intent'], 'answer': quote[:150], 'supported': True,
                                 'source_index': 0, 'quote': quote}],
            'current_relevance': {'kind': 'evergreen', 'source_index': 0, 'quote': quote,
                                 'event_start': None, 'event_end': None, 'date_quote': None}}
        return market.suitability.review_plan(item, now, lambda _: raw)
    monkeypatch.setattr(market, 'review_plan', review)
    response = {'supported': True, 'category': '테크',
        'topic': '집와이파이설치: 회선 확인부터 공유기 배선·무선 설정까지',
        'intent': '집에 와이파이를 처음 설치할 때 회선과 공유기를 어떻게 연결하고 설정할까?',
        'gap': '회선·WAN/LAN 연결 및 SSID 설정 순서', 'source_index': 2,
        'source_indices': [2], 'serp_indices': [0, 2], 'valid_until': None,
        'intent_evidence': {'scope': 'full_keyword', 'target_keyword': item['keyword'],
            'matches': [{'result_index': i, 'quote': item['organic_results'][i]['title']} for i in (0, 2)]}}
    ask = Mock(return_value=response)
    monkeypatch.setattr(market, 'ask', ask)
    return item, detail, research, ask, response


def repair(item, budget=None):
    return market._recover_review_plan(item, item['selected_at'], item['hold_reasons'],
        budget=budget if budget is not None else {'attempts': 0}, titles=[], deadline=float('inf'))


def test_recorded_technical_scope_is_rebuilt_using_new_installation_body(technical_case):
    item, detail, research, ask, _ = technical_case
    before = deepcopy(item)
    assert market.opportunity.issues(item, datetime.fromisoformat(item['selected_at'])) == [
        'narrower_or_unverified_search_intent']
    budget = {'attempts': 0}
    assert repair(item, budget) == []
    assert budget['attempts'] == 1 and research.call_count == ask.call_count == 1
    assert item['verified_sources'] == [detail]
    assert item['topic'] != before['topic']
    for key in ('keyword', 'category', 'monthly_search', 'organic_query', 'organic_results', 'selected_at'):
        assert item[key] == before[key]
    clock = datetime.fromisoformat(item['selected_at'])
    assert not market.opportunity.issues(item, clock)
    assert not market.suitability.issues(item, clock)
    gaps = research.call_args.kwargs['coverage_gaps']
    assert research.call_args.args[1] == '테크'
    assert gaps['recovery_type'] == 'information_plan'
    assert gaps['search_intent_results'][0]['result_index'] == 0
    assert gaps['search_intent_results'][0]['title'] == item['organic_results'][0]['title']


@pytest.mark.parametrize('failure', ['same_body', 'wrong_publisher', 'narrow_plan', 'bad_quote', 'unsupported', 'source_review', 'budget'])
def test_technical_repair_preserves_hold_without_fresh_full_scope_evidence(technical_case, failure, monkeypatch):
    item, detail, research, _, response = technical_case
    before = deepcopy(item)
    budget = {'attempts': 0}
    if failure == 'same_body':
        research.return_value = ([item['verified_sources'][0]], {'provider': 'codex_web', 'searched': True})
    elif failure == 'wrong_publisher':
        detail['url'] = 'https://www.moel.go.kr/law'
    elif failure == 'narrow_plan':
        response['intent_evidence']['scope'] = 'narrower_query'
    elif failure == 'bad_quote':
        response['intent_evidence']['matches'][0]['quote'] = 'this quote was never present in search results'
    elif failure == 'unsupported':
        response['supported'] = False
    elif failure == 'source_review':
        original = market.review_plan
        def reject(*args):
            result = original(*args)
            result['review']['required_facets'][0]['supported'] = False
            return result
        monkeypatch.setattr(market, 'review_plan', reject)
    else:
        budget['attempts'] = market.MAX_SOURCE_RECOVERIES
    assert repair(item, budget)
    for key in ('topic', 'verified_sources', 'opportunity_evidence'):
        assert item[key] == before[key]
    if failure == 'budget':
        research.assert_not_called()


def test_review_only_exclusions_are_not_sent_to_technical_shortlist(monkeypatch):
    install_selection(monkeypatch, ['와이파이연결방법'], category='테크', passing=['와이파이연결방법'])
    original = market.ask
    prompts = []
    def ask(prompt):
        prompts.append(prompt)
        return original(prompt)
    monkeypatch.setattr(market, 'ask', ask)
    market.select_category('테크', 1, [])
    assert '청소·수리·고장 해결은 구매 비교 목적이 아닙니다' not in prompts[0]
    assert '청소·수리·고장 해결은 구매 비교 목적이 아닙니다' in market.review_shortlist_guidance('리뷰')


def test_isp_sources_are_not_forced_to_router_manufacturers():
    assert market._official_search_extra_domains('인터넷이전설치') == []
    assert market._source_route_issue('인터넷이전설치', '테크', 'https://news.lguplus.com/12936') is None
    assert market._source_route_issue('공유기설치', '테크', 'https://www.moel.go.kr/law')


def test_technical_question_seeds_still_require_their_own_measured_demand(monkeypatch):
    seeds = market.CATEGORIES['테크']
    assert {'윈도우초기화', '아이폰백업', '와이파이비밀번호', '블루투스연결'} <= set(seeds)
    for name in ('NAVER_AD_CUSTOMER_ID', 'NAVER_AD_API_KEY', 'NAVER_AD_SECRET_KEY'):
        monkeypatch.setenv(name, 'synthetic-test-only')
    lookup = Mock(return_value=[{'keyword': '아이폰백업', 'monthly': 0},
                               {'keyword': '아이폰백업방법', 'monthly': 900}])
    monkeypatch.setattr(market, 'fetch_keyword_stats', lookup)
    measured = market.demand_candidates(seeds)
    assert list(measured) == ['아이폰백업방법']
    assert measured['아이폰백업방법']['monthly'] == 900
    assert lookup.call_count == len(seeds)
