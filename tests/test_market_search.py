from unittest.mock import Mock
import logging
import sys
from types import SimpleNamespace

import requests
import pytest

from src import market_search as search


@pytest.fixture(autouse=True)
def isolated_search_provider(monkeypatch):
    monkeypatch.delenv('MARKET_SEARCH_PROVIDER', raising=False)


@pytest.fixture
def native_adapter(monkeypatch):
    adapter = Mock()
    monkeypatch.setitem(sys.modules, 'src.codex_search', SimpleNamespace(native_search=adapter))
    monkeypatch.setenv('MARKET_SEARCH_PROVIDER', 'codex_native_search')
    # Even configured API keys must not cause a fallback or additional request.
    monkeypatch.setenv('GOOGLE_SEARCH_API_KEY', 'private-google-key')
    monkeypatch.setenv('GOOGLE_SEARCH_ENGINE_ID', 'private-google-engine')
    http = Mock(side_effect=AssertionError('HTTP fallback must not be called'))
    monkeypatch.setattr(search.requests, 'get', http)
    yield adapter
    http.assert_not_called()


def native_row(**changes):
    return {'url': 'https://Example.ORG./guide', 'title': '시험 일정 및 준비물 안내',
            'snippet': '시험 일정과 준비물을 어디서 확인하는지 설명합니다.', **changes}


def test_explicit_native_search_passes_whole_query_and_normalizes_tool_rows(native_adapter):
    native_adapter.return_value = [native_row(domain='forged.example', arbitrary='private-extra')]
    query = 'ITQ 자격증 조회 (전체 취득 내역)'
    assert search.search_results(query) == ('codex_native_search', [{
        'url': 'https://Example.ORG./guide', 'domain': 'example.org',
        'title': '시험 일정 및 준비물 안내',
        'snippet': '시험 일정과 준비물을 어디서 확인하는지 설명합니다.',
    }])
    native_adapter.assert_called_once_with(query)


@pytest.mark.parametrize('payload', [
    None, True, {}, {'results': [native_row()]},
    '모델의 검색 결과 설명',
    '[{"url":"https://example.org","title":"모델 제목","snippet":"모델 설명"}]',
    ['모델 설명', None, True, []], [],
])
def test_native_answer_text_and_non_result_payloads_are_not_evidence(native_adapter, caplog, payload):
    native_adapter.return_value = payload
    assert search.search_results('시험일정') == ('codex_native_search', [])
    native_adapter.assert_called_once_with('시험일정')
    assert 'provider=codex_native_search reason=native_search_unavailable' in caplog.text
    assert '모델' not in caplog.text
    assert 'private-' not in caplog.text


@pytest.mark.parametrize('row', [
    native_row(url='javascript:alert(1)'), native_row(url='https://user:password@example.org/'),
    native_row(url='https://[invalid/'), native_row(url=None), native_row(url={}),
    native_row(title=None), native_row(title={}), native_row(title=' '),
    native_row(snippet=None), native_row(snippet=[]), native_row(snippet=''),
    {'url': 'https://example.org', 'title': '검색 결과', 'content': '본문을 요약으로 대신할 수 없음'},
])
def test_native_malformed_row_does_not_become_stringified_evidence(native_adapter, row):
    native_adapter.return_value = [row, native_row()]
    provider, rows = search.search_results('시험일정')
    assert provider == 'codex_native_search'
    assert rows == [search.result_row(**native_row())]


def test_native_does_not_fill_invalid_first_ten_slots_from_later_results(native_adapter):
    native_adapter.return_value = [None] * 9 + [native_row(), native_row(url='https://later.example/')]
    assert search.search_results('시험일정') == ('codex_native_search', [search.result_row(**native_row())])


def test_native_keeps_repeated_hosts_and_urls_for_downstream_sample_validation(native_adapter):
    native_adapter.return_value = [native_row(), native_row(), native_row(url='https://Example.ORG./second')]
    _, rows = search.search_results('시험일정')
    assert len(rows) == 3
    assert [row['domain'] for row in rows] == ['example.org'] * 3


def test_native_failure_hides_adapter_reason_and_exception_without_retry(native_adapter, caplog):
    error = RuntimeError('private-token https://private.example/?key=private-key')
    error.reason = 'private-untrusted-reason'
    native_adapter.side_effect = error
    assert search.search_results('시험일정') == ('codex_native_search', [])
    native_adapter.assert_called_once_with('시험일정')
    assert 'reason=native_search_unavailable' in caplog.text
    assert 'private-' not in caplog.text
    assert 'https://' not in caplog.text


@pytest.mark.parametrize('provider', ['unknown', 'google_custom_search', 'duckduckgo_proxy',
                                      'codex_native_search ', 'CODEX_NATIVE_SEARCH',
                                      'private-value\nhttps://private.example/?key=private-key'])
def test_unknown_explicit_provider_fails_closed_without_echoing_setting(native_adapter, monkeypatch, caplog, provider):
    monkeypatch.setenv('MARKET_SEARCH_PROVIDER', provider)
    assert search.search_results('시험일정') == (None, [])
    native_adapter.assert_not_called()
    assert 'provider=unavailable reason=unsupported_provider' in caplog.text
    assert 'private-' not in caplog.text
    assert 'https://' not in caplog.text


def test_empty_provider_setting_keeps_existing_google_default(monkeypatch):
    monkeypatch.setenv('MARKET_SEARCH_PROVIDER', '')
    monkeypatch.setenv('GOOGLE_SEARCH_API_KEY', 'test-key')
    monkeypatch.setenv('GOOGLE_SEARCH_ENGINE_ID', 'test-engine')
    response = Mock()
    response.json.return_value = {'items': [
        {'link': 'https://example.org/', 'title': '시험 안내', 'snippet': '실제 검색 결과'},
    ]}
    http = Mock(return_value=response)
    monkeypatch.setattr(search.requests, 'get', http)
    assert search.search_results('시험일정')[0] == 'google_custom_search'
    http.assert_called_once()


def test_google_results_preserve_competitor_positions(monkeypatch):
    monkeypatch.setenv('GOOGLE_SEARCH_API_KEY', 'test-key')
    monkeypatch.setenv('GOOGLE_SEARCH_ENGINE_ID', 'test-engine')
    response = Mock()
    response.json.return_value = {'items': [
        {'link': 'https://example.go.kr/a', 'title': '일정', 'snippet': '시험 일정'},
        {'link': 'https://example.go.kr/b', 'title': '서류'},
        {'link': 'javascript:alert(1)'},
    ]}
    monkeypatch.setattr(search.requests, 'get', lambda *a, **kw: response)
    provider, rows = search.search_results('시험일정')
    assert provider == 'google_custom_search'
    assert [row['domain'] for row in rows] == ['example.go.kr', 'example.go.kr']
    assert rows[0]['snippet'] == '시험 일정'


def test_google_failure_falls_back_to_real_snippets(monkeypatch):
    monkeypatch.setenv('GOOGLE_SEARCH_API_KEY', 'test-key')
    monkeypatch.setenv('GOOGLE_SEARCH_ENGINE_ID', 'test-engine')
    response = Mock(url='https://html.duckduckgo.com/html/', text='''
      <div class="result"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fblog.example%2Fa">준비물</a>
      <a class="result__snippet">수험표와 신분증</a></div>''')
    monkeypatch.setattr(search.requests, 'get', Mock(side_effect=[requests.Timeout(), response]))
    provider, rows = search.search_results('시험준비물')
    assert provider == 'duckduckgo_proxy'
    assert rows == [{'url': 'https://blog.example/a', 'domain': 'blog.example',
                     'title': '준비물', 'snippet': '수험표와 신분증'}]


def test_unavailable_search_is_not_evidence(monkeypatch):
    monkeypatch.delenv('GOOGLE_SEARCH_API_KEY', raising=False)
    monkeypatch.setattr(search.requests, 'get', Mock(side_effect=requests.Timeout()))
    assert search.search_results('시험준비물') == ('duckduckgo_proxy', [])


@pytest.mark.parametrize('error,reason', [
    ('accessNotConfigured', 'api_not_enabled'),
    ('API_KEY_SERVICE_BLOCKED', 'api_key_service_blocked'),
    ('ipRefererBlocked', 'api_key_restricted'),
    ('keyInvalid', 'api_key_invalid'),
    ('dailyLimitExceeded', 'daily_quota_exceeded'),
    ('rateLimitExceeded', 'rate_limit_exceeded'),
    ('This project does not have the access to Custom Search JSON API.', 'api_access_unavailable'),
])
def test_google_rejection_and_ddg_challenge_are_distinguished_without_secrets(monkeypatch, caplog, error, reason):
    monkeypatch.setenv('GOOGLE_SEARCH_API_KEY', 'private-api-key')
    monkeypatch.setenv('GOOGLE_SEARCH_ENGINE_ID', 'private-engine')
    google = Mock(status_code=403)
    google.json.return_value = {'error': {'message': f'{error}; private-api-key; private-account'}}
    google.raise_for_status.side_effect = requests.HTTPError('https://example/?key=private-api-key')
    ddg = Mock(status_code=202, url='https://html.duckduckgo.com/html/',
               text='<form id="challenge-form" action="anomaly.js">private-challenge</form>')
    monkeypatch.setattr(search.requests, 'get', Mock(side_effect=[google, ddg]))
    assert search.search_results('시험준비물') == ('duckduckgo_proxy', [])
    assert f'provider=google_custom_search reason={reason} http_status=403' in caplog.text
    assert 'provider=duckduckgo_proxy reason=challenge http_status=202' in caplog.text
    assert 'private-' not in caplog.text


def test_empty_results_are_not_mislabeled_as_a_challenge(monkeypatch, caplog):
    monkeypatch.delenv('GOOGLE_SEARCH_API_KEY', raising=False)
    response = Mock(status_code=200, url='https://html.duckduckgo.com/html/', text='<p>No results</p>')
    monkeypatch.setattr(search.requests, 'get', lambda *a, **kw: response)
    assert search.search_results('시험준비물') == ('duckduckgo_proxy', [])
    assert 'configuration_missing' in caplog.text
    assert 'reason=no_results http_status=200' in caplog.text
    assert 'reason=challenge' not in caplog.text


def error_info(consumer='projects/123456789012', service='customsearch.googleapis.com'):
    return {'@type': 'type.googleapis.com/google.rpc.ErrorInfo', 'reason': 'SERVICE_DISABLED',
            'metadata': {'consumer': consumer, 'service': service,
                         'activationUrl': 'https://private-project/?key=private-key'}}


def test_google_project_diagnostic_is_separate_and_preserves_failure_event(caplog):
    response = Mock(status_code=403)
    response.json.return_value = {'error': {'message': 'private-error-message',
                                          'details': [error_info(), error_info()]}}
    with caplog.at_level(logging.DEBUG, logger=search.logger.name):
        search.search_failure('google_custom_search', response)
    records = [record for record in caplog.records if record.name == search.logger.name]
    assert [(record.msg, record.args) for record in records] == [
        (search.GOOGLE_PROJECT_TEMPLATE, ('123456789012',)),
        ('Search unavailable: provider=%s reason=%s http_status=%s',
         ('google_custom_search', 'api_not_enabled', 403)),
    ]
    assert 'private-' not in caplog.text
    assert 'https://' not in caplog.text
    assert 'metadata' not in caplog.text


@pytest.mark.parametrize('consumer', [
    'projects/123\nprivate-key', 'projects/123\n', 'projects/123?key=private-key',
    'projects/123/other', ' projects/123', 'projects/１２３', 'projects/123456789012345678901',
    'projects/private-project', 123, None, {'consumer': 'projects/123'},
])
def test_google_project_rejects_non_numeric_or_injected_consumers(caplog, consumer):
    response = Mock(status_code=403)
    response.json.return_value = {'error': {'details': [error_info(consumer)]}}
    with caplog.at_level(logging.DEBUG, logger=search.logger.name):
        search.search_failure('google_custom_search', response)
    assert not any(record.msg == search.GOOGLE_PROJECT_TEMPLATE for record in caplog.records)
    assert 'private-' not in caplog.text
    assert 'https://' not in caplog.text


@pytest.mark.parametrize('payload', [
    {'error': {'message': 'consumer projects/123 service customsearch.googleapis.com'}},
    {'error': {'details': [error_info(service='generativelanguage.googleapis.com')]}},
    {'error': {'details': [error_info(service='customsearch.googleapis.com.private-example')]}},
    {'error': {'details': [{**error_info(), '@type': 'private-error-type'}]}},
    {'error': {'details': [{**error_info(), 'metadata': 'private-metadata'}]}},
    {'error': {'details': {'private-details': error_info()}}},
    {'items': [error_info()]},
    ['private-unexpected-payload'],
])
def test_google_project_requires_typed_error_metadata(payload, caplog):
    response = Mock(status_code=403)
    response.json.return_value = payload
    with caplog.at_level(logging.DEBUG, logger=search.logger.name):
        search.search_failure('google_custom_search', response)
    assert not any(record.msg == search.GOOGLE_PROJECT_TEMPLATE for record in caplog.records)
    assert 'private-' not in caplog.text


def test_regular_warning_logs_do_not_include_project_metadata(caplog):
    response = Mock(status_code=403)
    response.json.return_value = {'error': {'details': [error_info()]}}
    with caplog.at_level(logging.WARNING, logger=search.logger.name):
        search.search_failure('google_custom_search', response)
    assert 'api_not_enabled' in caplog.text
    assert '123456789012' not in caplog.text
    assert 'private-' not in caplog.text
