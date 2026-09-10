from unittest.mock import Mock
import logging

import requests
import pytest

from src import market_search as search


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
