"""Production-source replay and acquisition integration, without changing gates."""
from datetime import date, datetime, timedelta
import hashlib
import json
from pathlib import Path
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from src import codex_client, market_topics as market, recruitment_sources as recruitment
from tests.test_market_topics import analysis, organic_sample
from tests.test_market_topics import isolated_market_history  # noqa: F401

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/recruitment_sources_20261005.json').read_text())


def source(text, number=1):
    return {'url': f'https://job.alio.go.kr/recruitview.do?idx={number}',
            'title': '공공기관 채용정보시스템', 'excerpt': text,
            'checked_on': datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat(),
            'sha256': hashlib.sha256(text.encode()).hexdigest()}


def test_real_failed_sources_cannot_fill_recruitment_slots():
    reasons = [recruitment.source_issue(row['keyword'], row['source'], today=date(2026, 10, 5))
               for row in FIXTURE['sources']]
    assert reasons == ['recruitment_detail_missing', 'expired_recruitment_source',
                       'expired_recruitment_source', *['recruitment_employer_mismatch'] * 3]


@pytest.mark.parametrize('deadline,issue', [
    ('채용기간 26.07.21 ~ 26.08.05', 'expired_recruitment_source'),
    ('접수마감일 2026-10-04', 'expired_recruitment_source'),
    ('접수 마감일 : 2026. 10. 04', 'expired_recruitment_source'),
    ('채용기간 26.10.01 ~ 26.10.05', None),
    ('접수마감일 2026-10-06', None),
    ('채용기간 26.10.01 ~ 26.13.05', 'invalid_recruitment_deadline'),
    ('등록일 2026-01-01 근무기간 26.02.01 ~ 26.08.01', None),
    ('접수마감일 2026-08-01 접수마감일 2026-10-07', None),
    ('접수기간은 첨부 공고문 참조', None),
])
def test_only_explicit_application_deadlines_can_exclude_source(deadline, issue):
    item = source('부산교통공사 응시자격 및 전형절차 ' + deadline)
    assert recruitment.source_issue('부산 교통공사 채용', item, today=date(2026, 10, 5)) == issue


def test_employer_must_appear_in_fetched_body_not_just_search_title():
    item = source('축산물품질평가원 응시자격 및 전형절차')
    item['title'] = '부산교통공사 채용'
    assert recruitment.source_issue('부산교통공사채용', item) == 'recruitment_employer_mismatch'
    assert recruitment.source_issue('채용', item) is None
    assert recruitment.source_issue('공기업채용', item) is None
    assert recruitment.source_issue('시험준비물', item) is None


def acquisition_case():
    invalid = [row['source'] for row in FIXTURE['sources'] if row['keyword'] == '부산교통공사채용']
    future = (datetime.now(ZoneInfo('Asia/Seoul')) + timedelta(days=7)).strftime('%Y-%m-%d')
    today = datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
    valid = source(
        f'부산교통공사 공식 신규직원 채용 응시자격 및 전형절차 접수기간 {today} ~ {future} 접수마감일 {future}. '
        '지원자는 접수 기간 안에 온라인 입사지원서를 제출합니다. 필요한 서류는 입사지원서와 자기소개서이며, '
        '지원 직무의 자격요건과 제출 항목을 확인한 뒤 신청합니다. 서류 심사를 통과하면 필기전형과 면접전형에 참여합니다. '
        '각 단계의 합격 여부와 시험 장소는 공식 홈페이지에서 확인합니다. 제출 내용이 사실과 다르면 합격이 취소될 수 있습니다.', 999999)
    return invalid, valid


def test_invalid_bodies_do_not_exhaust_slots_before_later_organic_detail(monkeypatch, caplog):
    invalid, valid = acquisition_case()
    items = [*invalid, valid]
    lookup = {row['url']: row for row in items}
    monkeypatch.setattr(market, 'fetch_source', lambda url: lookup[url])
    monkeypatch.setattr(market, 'official_search_urls', lambda _, category=None: [])
    assert market.candidate_sources('부산교통공사채용', items) == [valid]
    assert caplog.text.count('recruitment_employer_mismatch') == 3


def test_locator_search_reaches_other_portals_and_is_bounded(monkeypatch):
    calls = []
    def search(query):
        calls.append(query)
        host = query.split('site:')[1]
        return 'codex_native_search', [{'url': f'https://{host}/detail/{i}'} for i in range(4)]
    monkeypatch.setattr(market, 'search_results', search)
    urls = market.official_search_urls('부산교통공사채용')
    assert len(calls) == 3 and len(urls) == 8
    assert [url.split('/')[2] for url in urls[:3]] == ['job.alio.go.kr', 'gojobs.go.kr', 'work24.go.kr']


def test_research_filters_fetched_bodies_even_when_model_proposes_wrong_employer(monkeypatch):
    invalid, valid = acquisition_case()
    lookup = {row['url']: row for row in [*invalid, valid]}
    client = Mock()
    client.research.return_value = {'searched': True, 'opened_urls': list(lookup), 'text': '{}'}
    monkeypatch.setattr(codex_client, 'CodexSubscriptionClient', Mock(return_value=client))
    monkeypatch.setattr(market, 'fetch_source', lambda url: lookup[url])
    sources, trace = market.research_official_sources('부산교통공사채용', '취업', datetime.now(ZoneInfo('Asia/Seoul')).isoformat())
    assert sources == [{**valid, 'locator_origin': 'native_open'}]
    assert trace['searched'] is True


def test_no_valid_replacement_returns_empty_instead_of_promoting_old_sources(monkeypatch):
    rows = [row['source'] for row in FIXTURE['sources'] if row['keyword'] == '국민건강보험공단채용']
    lookup = {row['url']: row for row in rows}
    monkeypatch.setattr(market, 'fetch_source', lambda url: lookup[url])
    monkeypatch.setattr(market, 'official_search_urls', lambda _, category=None: [])
    assert market.candidate_sources('국민건강보험공단채용', rows) == []


def test_hiring_qualifiers_do_not_become_part_of_the_employer_name():
    assert recruitment.employer('2026년 부산교통공사 하반기 신입 채용') == '부산교통공사'
    assert recruitment.employer('신입사원 채용') is None
    assert recruitment.employer('삼성전자 생산직 채용') == '삼성전자'


def test_employment_period_outside_alio_is_not_an_application_deadline():
    item = source('부산교통공사 응시자격 채용기간 26.01.01 ~ 26.08.31')
    item['url'] = 'https://www.gojobs.go.kr/apmView.do?empmnsn=1'
    assert recruitment.source_issue('부산교통공사채용', item, today=date(2026, 10, 5)) is None


def test_alio_historical_body_dates_do_not_override_current_metadata():
    item = source('부산교통공사 응시자격 채용기간 26.10.01 ~ 26.10.10 등록일 2026.10.01 과거 채용기간 26.01.01 ~ 26.01.31')
    assert recruitment.source_issue('부산교통공사채용', item, today=date(2026, 10, 5)) is None


def test_filtered_sources_trigger_fresh_research_before_full_selection(monkeypatch, isolated_market_history):
    keyword = '부산교통공사채용'
    invalid, valid = acquisition_case()
    lookup = {row['url']: row for row in invalid}
    research = Mock(return_value=([valid], {'provider': 'codex_web', 'searched': True}))
    monkeypatch.setattr(market, 'demand_candidates', lambda _: {keyword: {'keyword': keyword, 'monthly': 1200}})
    monkeypatch.setattr(market, 'search_results', Mock(return_value=('codex_native_search', organic_sample(keyword))))
    monkeypatch.setattr(market, 'fetch_source', lambda url: lookup.get(url))
    monkeypatch.setattr(market, 'official_search_urls', lambda _, category=None: list(lookup))
    monkeypatch.setattr(market, 'research_official_sources', research)
    monkeypatch.setattr(market, 'ask', Mock(side_effect=[{'candidates': [{'keyword': keyword}]}, analysis(keyword)]))
    monkeypatch.setattr(market, 'fetch_trend_change', lambda _: None)
    report = market.select_category('취업', 1, titles=[])
    research.assert_called_once()
    assert len(report['selected']) == 1 and not report['rejected'] and not report['held'], ([x.get('reason') for x in report['rejected']], [x.get('hold_reasons') for x in report['held']])
    item = report['selected'][0]
    assert item['verified_sources'] == [valid]
    assert market.fresh_market_item(item, '취업')
    assert market.opportunity.issues(item) == market.suitability.issues(item) == []
