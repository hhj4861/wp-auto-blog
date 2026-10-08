"""Replay production source misrouting without weakening publication reviews."""
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from src import market_topics as market, editorial, selection_trace
from tests.test_market_topics import evidence, isolated_market_history
from tests.test_selection_feedback import install_selection

RECORDED = json.loads((Path(__file__).parent / 'fixtures/tech_selection_20261008.json').read_text())


def test_technical_source_queries_use_manufacturers_not_government(monkeypatch):
    search = Mock(return_value=('codex_native_search', []))
    monkeypatch.setattr(market, 'search_results', search)
    market.official_search_urls('공유기 설치', '테크')
    assert [c.args[0] for c in search.call_args_list] == [
        '공유기 설치 site:tp-link.com', '공유기 설치 site:iptime.com']
    search.reset_mock()
    market.official_search_urls('윈도우 포맷', '테크')
    search.assert_called_once_with('윈도우 포맷 site:support.microsoft.com')
    search.reset_mock()
    market.official_search_urls('알수없는기기설정', '테크')
    search.assert_not_called()  # Native research must identify the actual publisher.


def test_recorded_government_pages_cannot_consume_tech_source_slots(monkeypatch):
    urls = [source['url'] for row in RECORDED['sources']
            if row['keyword'] in ('인터넷속도측정', '인터넷설치', '공유기설치')
            for source in row['diagnostics']['official_sources']]
    good = evidence('https://www.tp-link.com/kr/support/faq/3316/')
    good.update(title='공유기 초기 설치 방법', excerpt='공유기 WAN 및 LAN 연결 설정 안내 ' * 30)
    fetch = Mock(return_value=good)
    monkeypatch.setattr(market, 'fetch_source', fetch)
    monkeypatch.setattr(market, 'official_search_urls', Mock(return_value=[*urls, good['url']]))
    sources = market.candidate_sources('공유기설치', [{'url': url} for url in urls], '테크')
    assert sources == [good]
    fetch.assert_called_once_with(good['url'])
    market.official_search_urls.assert_called_once_with('공유기설치', '테크')


def test_native_research_obeys_same_route_and_records_exclusions(monkeypatch):
    from src import codex_client
    bad = 'https://www.moel.go.kr/info/lawinfo/instruction/view.do?bbs_seq=20260400639'
    good = 'https://www.tp-link.com/kr/support/faq/3316/'
    client = Mock()
    client.research.return_value = {'searched': True, 'opened_urls': [bad, good], 'text': ''}
    monkeypatch.setattr(codex_client, 'CodexSubscriptionClient', Mock(return_value=client))
    source = evidence(good)
    source.update(title='공유기 설치', excerpt='공유기 설치와 WAN 연결 ' * 30)
    fetch = Mock(return_value=source)
    monkeypatch.setattr(market, 'fetch_source', fetch)
    events = []
    token = selection_trace._events.set(events)
    try:
        sources, trace = market.research_official_sources('공유기설치', '테크', '2026-10-08')
    finally:
        selection_trace._events.reset(token)
    fetch.assert_called_once_with(good)
    assert sources[0]['url'] == good and trace['searched']
    assert events[1]['outcome'] == 'wrong_topic_publisher'
    assert events[2]['outcome'] == 'fetched'
    assert '일반 정부·지자체·채용·기업정보' in client.research.call_args.args[0]


def test_clear_unrelated_apple_body_is_not_evidence(monkeypatch):
    unrelated = evidence('https://apps.apple.com/kr/app/taxi/id6670617418')
    unrelated.update(title='K맘택시', excerpt='임산부 택시 예약 안내 ' * 30)
    monkeypatch.setattr(market, 'fetch_source', Mock(return_value=unrelated))
    assert market._read_candidate_source('아이폰15프로출시일', '테크', unrelated['url']) is None


def test_fixed_fetch_failure_codes_survive_cache_hits(monkeypatch):
    def unavailable(*_):
        editorial._source_fetch_failure('timeout')
        return None
    fetch = Mock(side_effect=unavailable)
    monkeypatch.setattr(editorial, '_fetch_source', fetch)
    with editorial.source_fetch_scope():
        for _ in range(2):
            with editorial.source_failure_scope() as failures:
                assert editorial.fetch_source('https://support.microsoft.com/a') is None
            assert failures == ['timeout']
    fetch.assert_called_once()
    with editorial.source_failure_scope() as unrelated:
        pass
    assert unrelated == []


def test_uncertain_head_terms_do_not_spend_technical_recovery_budget():
    skipped = RECORDED['shortlist_skips'] + [
        {'keyword': '공유기설치', 'reason_code': 'insufficient_specificity'},
        {'keyword': '윈도우포맷', 'reason_code': 'insufficient_specificity'}]
    result = market.information_research_candidates(skipped, 100, '테크')
    keys = {row['keyword'] for row in result}
    assert '갤럭시S25' not in keys and '인터넷속도측정' not in keys
    assert {'공유기설치', '윈도우포맷'} <= keys


def test_selection_passes_category_and_explains_budget_stop(monkeypatch):
    install_selection(monkeypatch, ['공유기설치'], category='테크', passing=['공유기설치'])
    source = Mock(return_value=[evidence()])
    monkeypatch.setattr(market, 'candidate_sources', source)
    report = market.select_category('테크', 1, [])
    assert source.call_args.args[2] == '테크'
    assert report['selected'] and report['selection_outcome'] == 'selected'
    assert report['selection_funnel']['evaluated'] == 1
    assert 'source_discovery_audit' in report
    report.update(selected=[], research_stop_reason='round_limit')
    copied = selection_trace.capture(lambda: report)()
    assert copied['selection_outcome'] == 'research_budget_exhausted'
    assert copied['selection_funnel']['stop_reason'] == 'round_limit'


def test_router_allowlist_does_not_accept_lookalike_hosts():
    assert editorial.is_official_url('https://www.tp-link.com/kr/support/faq/3316/')
    assert editorial.is_official_url('https://iptime.com/iptime/')
    assert not editorial.is_official_url('https://tp-link.com.evil.example/a')


def test_operational_failure_keeps_completed_source_attempts(monkeypatch):
    from src import analysis_runtime as runtime
    @selection_trace.capture
    @runtime.selection_scope
    def failing(category):
        selection_trace.record('공유기설치', category, 'source_search_requested',
                               query='공유기설치 site:tp-link.com')
        raise runtime.AnalysisError('unauthorized')
    report = failing('테크')
    assert report['selection_outcome'] == 'analysis_unavailable'
    assert report['operational_error'] == 'unauthorized'
    assert report['source_discovery_audit'][0]['query'] == '공유기설치 site:tp-link.com'
    assert not report['selected']


def test_redirect_to_wrong_publisher_does_not_supply_evidence(monkeypatch):
    source = evidence('https://www.moel.go.kr/law')
    source.update(title='공유기 설치', excerpt='공유기 설치 ' * 60)
    monkeypatch.setattr(market, 'fetch_source', Mock(return_value=source))
    assert market._read_candidate_source('공유기설치', '테크',
                                        'https://www.tp-link.com/start') is None
