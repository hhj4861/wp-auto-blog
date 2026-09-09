from unittest.mock import Mock

import requests

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
