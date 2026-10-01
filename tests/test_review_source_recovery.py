"""Replay production inputs; semantic model responses remain explicit mocks."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src import market_topics as market, review_discovery as review, search_quality as quality
from tests.test_review_discovery import source
from tests.test_selection_feedback import install_selection
from tests.test_market_topics import isolated_market_history as isolated_market_history

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/review_sources_20261001.json').read_text())
STAMP = FIXTURE['selected_at']


def replay_row(keyword='청소기필터'):
    return deepcopy(next(row for row in FIXTURE['rejected'] if row['keyword'] == keyword))


def invoke(row, budget=None, audit=None):
    return market._search_review_with_recovery(row['keyword'], row['organic_provider'],
        row['organic_results'], STAMP, row['organic_query'],
        budget=budget if budget is not None else {'attempts': 0}, audit=audit if audit is not None else {})


def response(row, relevant=True):
    return {'decisions': [{'result_index': index, 'relevant': relevant,
                          'quote': data['title'] + ' ' + data['snippet']}
                         for index, data in quality.raw_rows(row['organic_results'])]}


@pytest.mark.parametrize('code', sorted(market.SEARCH_REVIEW_RETRY_CODES))
def test_fixed_failures_retry_identical_inputs_once_and_keep_diagnostics(monkeypatch, code):
    row, audit, budget = replay_row(), {}, {'attempts': 0}
    returned = {'valid': 'test-double'}
    call = Mock(side_effect=[quality.SearchReviewError(code), returned])
    monkeypatch.setattr(market, 'review_search', call)
    assert invoke(row, budget, audit) == returned
    assert call.call_count == 2 and budget['attempts'] == 1
    for args in call.call_args_list:
        assert args.args[:4] == (row['keyword'], row['organic_provider'], row['organic_results'], STAMP)
        assert args.kwargs == {'executed_query': row['organic_query']}
    assert audit['attempts'] == [{'attempt': 1, 'status': 'error', 'code': code},
                                 {'attempt': 2, 'status': 'returned'}]


def test_real_quote_validation_repairs_format_but_never_changes_search_evidence(monkeypatch):
    row, audit = replay_row(), {}
    original = deepcopy(row)
    bad = response(row)
    bad['decisions'][0]['quote'] = 'fabricated quotation not in the search sample'
    monkeypatch.setattr(market, 'review_search', quality.review_search)
    model = Mock(side_effect=[bad, response(row)])
    monkeypatch.setattr(market, 'ask', model)
    result = invoke(row, audit=audit)
    assert row == original
    assert result['raw_sha256'] == quality.raw_sha256(row['organic_results'])
    assert result['executed_query'] == '청소기 필터'
    assert audit['attempts'][0]['code'] == 'unverified_result_quote'
    assert 'unverified_result_quote' in model.call_args.args[0]
    assert 'fabricated quotation' not in model.call_args.args[0]
    assert not quality.quality_issues(row['keyword'], row['organic_provider'], row['organic_results'],
                                    STAMP, result, executed_query=row['organic_query'])


def test_valid_negative_relevance_verdict_is_not_retried(monkeypatch):
    row, audit = replay_row(), {}
    monkeypatch.setattr(market, 'review_search', quality.review_search)
    model = Mock(return_value=response(row, relevant=False))
    monkeypatch.setattr(market, 'ask', model)
    result = invoke(row, audit=audit)
    model.assert_called_once()
    assert 'insufficient_relevant_results' in quality.quality_issues(row['keyword'],
        row['organic_provider'], row['organic_results'], STAMP, result, executed_query=row['organic_query'])
    assert audit['attempts'] == [{'attempt': 1, 'status': 'returned'}]


@pytest.mark.parametrize('error,expected', [
    (quality.SearchReviewError('invalid_search_input'), 'invalid_search_input'),
    (quality.SearchReviewError('site_identity_unavailable'), 'site_identity_unavailable'),
    (quality.SearchReviewError('PRIVATE-secret'), 'unexpected_review_error'),
    (TypeError('PRIVATE-secret'), 'unexpected_review_error'),
])
def test_non_recoverable_failure_has_safe_code_and_no_retry(monkeypatch, error, expected):
    audit = {}
    call = Mock(side_effect=error)
    monkeypatch.setattr(market, 'review_search', call)
    with pytest.raises(type(error)):
        invoke(replay_row(), audit=audit)
    call.assert_called_once()
    assert audit['attempts'][0]['code'] == expected
    assert 'PRIVATE' not in json.dumps(audit)


def test_retry_budget_is_shared_and_never_makes_persistent_errors_pass(monkeypatch):
    budget = {'attempts': 0}
    call = Mock(side_effect=quality.SearchReviewError('model_review_failed'))
    monkeypatch.setattr(market, 'review_search', call)
    for expected_calls in (2, 4, 5):
        with pytest.raises(quality.SearchReviewError):
            invoke(replay_row(), budget)
        assert call.call_count == expected_calls
    assert budget['attempts'] == 2


def test_selection_report_retains_failed_attempts_and_never_enqueues(monkeypatch):
    install_selection(monkeypatch, ['청소기필터'])
    monkeypatch.setattr(market, 'review_search', Mock(side_effect=quality.SearchReviewError('unverified_result_quote')))
    fetch = Mock(side_effect=AssertionError('Must not research after relevance failure'))
    monkeypatch.setattr(market, 'candidate_sources', fetch)
    report = market.select_category('리뷰', 1, [])
    assert not report['selected'] and not report['held']
    assert report['search_review_recovery_attempts'] == 1
    assert report['rejected'][0]['search_review_diagnostics'] == report['search_review_diagnostics'][0]
    assert len(report['search_review_diagnostics'][0]['attempts']) == 2
    fetch.assert_not_called()
    with pytest.raises(RuntimeError):
        market.enqueue_report([], report)


def test_production_samsung_filter_sources_exclude_lg_appliance():
    row = replay_row('삼성공기청정기필터')
    retained = [s for s in row['official_sources'] if review.relevant_source(row['keyword'], s)]
    assert len(retained) == 2
    assert all('samsung.com' in s['url'] for s in retained)
    assert review.relevant_source(row['keyword'], source('https://kca.go.kr/filter', '삼성 공기청정기 필터 비교 조건'))


def test_component_domains_are_official_but_lookalikes_are_not():
    for domain in ('sandisk.com', 'kingston.com', 'semiconductor.samsung.com'):
        assert market.is_official_url('https://www.' + domain + '/ssd')
        assert not market.is_official_url('https://' + domain + '.evil.example/ssd')
        assert not market.is_official_url('https://' + domain + '@evil.example/ssd')


@pytest.mark.parametrize('keyword,hosts', [
    ('노트북SSD', ['sandisk.com', 'semiconductor.samsung.com', 'kingston.com', 'kca.go.kr']),
    ('삼성노트북SSD', ['semiconductor.samsung.com', 'kca.go.kr']),
    ('삼성공기청정기필터', ['samsung.com/sec', 'kca.go.kr']),
])
def test_search_targets_component_and_named_brand_not_unrelated_appliances(monkeypatch, keyword, hosts):
    queries = []
    monkeypatch.setattr(market, 'search_results', lambda q: (queries.append(q), []))
    assert market.official_search_urls(keyword) == []
    assert queries == [f'{keyword} 제품 사양 site:{host}' for host in hosts]


@pytest.mark.parametrize('native', [False, True])
def test_component_documents_survive_earlier_laptop_specs_in_both_paths(monkeypatch, native):
    laptop = replay_row('노트북SSD')['official_sources']
    drives = [source('https://www.sandisk.com/ko-kr/ssd', '노트북 SSD NVMe SATA 호환 조건', 'SSD 선택 안내'),
              source('https://www.kingston.com/kr/ssd', '노트북 SSD M.2 용량 선택 조건', 'SSD 규격 안내')]
    sources = laptop + drives
    lookup = {s['url']: s for s in sources}
    monkeypatch.setattr(market, 'fetch_source', lambda url: lookup[url])
    if native:
        trace = {'searched': True, 'opened_urls': list(lookup), 'text': '{}'}
        monkeypatch.setattr('src.codex_client.CodexSubscriptionClient',
                            lambda **kw: SimpleNamespace(research=lambda _: trace))
        found, _ = market.research_official_sources('노트북SSD', '리뷰', STAMP)
    else:
        monkeypatch.setattr(market, 'official_search_urls', lambda _: list(lookup)[2:])
        found = market.candidate_sources('노트북SSD', [{'url': s['url']} for s in laptop[:2]], category='리뷰')
    assert [s['url'] for s in found[:2]] == [s['url'] for s in drives]
    assert len(found) == 3


@pytest.mark.parametrize('panel', ['', '<div class="cm-semi-container"></div>',
    '<div class="cm-semi-container"><div class="cm-semi-container">Laptop SSD NVMe SATA</div></div>'])
def test_semiconductor_body_excludes_cookie_overlays_and_cannot_pad_empty_content(panel):
    from bs4 import BeautifulSoup
    from src.editorial import _source_body
    soup = BeautifulSoup('<body><header>MENU</header>' + panel
                         + '<div id="cookie_component">COOKIE POLICY</div>'
                           '<div id="cm-semi-contactus-tobe">CONTACT</div></body>', 'html.parser')
    result = _source_body(soup, 'https://semiconductor.samsung.com/consumer-storage/ssdupgrade/')
    assert result == ('Laptop SSD NVMe SATA' if 'Laptop' in panel else '')


def test_recovered_search_review_continues_through_existing_selection_gates(monkeypatch):
    keyword = '노트북SSD'
    install_selection(monkeypatch, [keyword], passing=[keyword])
    original = market.review_search
    calls = []
    def flaky(*args, **kwargs):
        calls.append(args[:4])
        if len(calls) == 1:
            raise quality.SearchReviewError('incomplete_result_review')
        return original(*args, **kwargs)
    monkeypatch.setattr(market, 'review_search', flaky)
    report = market.select_category('리뷰', 1, [])
    assert calls[0] == calls[1]
    assert report['selected'][0]['keyword'] == keyword
    assert market.fresh_market_item(report['selected'][0], '리뷰')
    assert report['search_review_recovery_attempts'] == 1
    assert report['search_review_diagnostics'][0]['attempts'][0]['code'] == 'incomplete_result_review'


def test_validation_error_after_returned_review_is_still_recorded_without_private_text(monkeypatch):
    install_selection(monkeypatch, ['청소기필터'])
    monkeypatch.setattr(market.opportunity, 'quality_issues', Mock(side_effect=TypeError('PRIVATE-token')))
    report = market.select_category('리뷰', 1, [])
    assert not report['selected'] and report['search_review_recovery_attempts'] == 0
    assert report['search_review_diagnostics'][0]['failure_code'] == 'unexpected_review_error'
    assert 'PRIVATE-token' not in json.dumps(report)
