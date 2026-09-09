from unittest.mock import Mock

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
