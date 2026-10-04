import importlib
from unittest.mock import Mock

import pytest
import requests

from src import indexnow

URL = 'https://trendpulse.blog/excel-macro-workflow-2026/'


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch):
    for key in ('INDEXNOW_API', 'INDEXNOW_KEY', 'INDEXNOW_KEY_LOCATION'):
        monkeypatch.delenv(key, raising=False)


def response(code=200, body=None):
    return Mock(status_code=code, json=Mock(return_value=body or {}))


@pytest.mark.parametrize('code,status', [(200, 'accepted'), (202, 'verification_pending')])
def test_verified_participating_endpoint_receipt_is_not_indexing(monkeypatch, code, status):
    post = Mock(return_value=response(code))
    monkeypatch.setattr(indexnow.requests, 'post', post)
    result = indexnow.submit_urls([URL, URL, 'https://trendpulse.blog/한글/'])
    assert result == {'endpoint': 'searchadvisor.naver.com', 'submitted_count': 2,
                      'accepted': True, 'http_status': code, 'status': status}
    args, kwargs = post.call_args
    assert args == ('https://searchadvisor.naver.com/indexnow',)
    assert kwargs['allow_redirects'] is False and kwargs['timeout'] == 30
    assert kwargs['json']['urlList'] == [URL, 'https://trendpulse.blog/%ED%95%9C%EA%B8%80/']


@pytest.mark.parametrize('url', [None, '', 'https://trendpulse.blog.evil.test/a',
    'https://evil.test/trendpulse.blog', 'https://trendpulse.blog@evil.test/a',
    'https://evil@trendpulse.blog/a', 'https://trendpulse.blog:444/a',
    'ftp://trendpulse.blog/a', 'https://trendpulse.blog/a#fragment',
    'https://trendpulse.blog/a\nb', 'https://trendpulse.blog/a\\b'])
def test_foreign_or_malformed_urls_are_never_submitted(monkeypatch, url):
    post = Mock()
    monkeypatch.setattr(indexnow.requests, 'post', post)
    assert indexnow.submit_urls([url])['status'] == 'no_valid_urls'
    post.assert_not_called()


@pytest.mark.parametrize('name,value', [
    ('INDEXNOW_API', 'https://unapproved.test/indexnow'),
    ('INDEXNOW_KEY', 'short'), ('INDEXNOW_KEY', 'not valid key'),
    ('INDEXNOW_KEY_LOCATION', 'https://other.test/key.txt'),
    ('INDEXNOW_KEY_LOCATION', 'https://trendpulse.blog/key.txt?secret=1'),
])
def test_invalid_configuration_fails_before_network(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    post = Mock()
    monkeypatch.setattr(indexnow.requests, 'post', post)
    assert indexnow.submit_urls([URL])['status'] == 'invalid_configuration'
    post.assert_not_called()


def test_key_directory_scope_rejects_parent_escape(monkeypatch):
    monkeypatch.setenv('INDEXNOW_KEY_LOCATION', 'https://trendpulse.blog/catalog/key.txt')
    post = Mock(return_value=response())
    monkeypatch.setattr(indexnow.requests, 'post', post)
    result = indexnow.submit_urls([URL, 'https://trendpulse.blog/catalog/../elsewhere',
        'https://trendpulse.blog/catalog/%2e%2e/elsewhere', 'https://trendpulse.blog/catalog/a'])
    assert result['submitted_count'] == 1
    assert post.call_args.kwargs['json']['urlList'] == ['https://trendpulse.blog/catalog/a']


def test_ownership_rejection_keeps_engine_and_public_key_results_separate(monkeypatch):
    monkeypatch.setenv('INDEXNOW_API', 'https://api.indexnow.org/indexnow')
    post = Mock(return_value=response(403, {'errorCode': 'UserForbiddedToAccessSite',
                                         'message': 'PRIVATE provider diagnostic'}))
    monkeypatch.setattr(indexnow.requests, 'post', post)
    monkeypatch.setattr(indexnow, 'check_key', lambda host: 'key_matches')
    result = indexnow.submit_urls([URL])
    assert result['accepted'] is False
    assert result['status'] == 'ownership_rejected'
    assert result['key_check'] == 'key_matches'
    assert result['error_code'] == 'UserForbiddedToAccessSite'
    assert 'PRIVATE' not in str(result)
    post.assert_called_once()  # No retry or other-engine fallback on an access rejection.


@pytest.mark.parametrize('code,status', [(400, 'invalid_request'), (422, 'invalid_request'),
    (429, 'rate_limited'), (500, 'http_error'), (302, 'http_error')])
def test_failures_and_redirects_are_not_success_or_retried(monkeypatch, code, status):
    post = Mock(return_value=response(code, {'errorCode': 'PRIVATE unknown'}))
    monkeypatch.setattr(indexnow.requests, 'post', post)
    result = indexnow.submit_urls([URL])
    assert result['accepted'] is False and result['status'] == status
    assert 'PRIVATE' not in str(result)
    post.assert_called_once()


def test_network_failure_is_nonblocking_and_redacted(monkeypatch):
    monkeypatch.setattr(indexnow.requests, 'post', Mock(side_effect=requests.Timeout('PRIVATE request')))
    assert indexnow.submit_urls([URL])['status'] == 'network_error'
    assert indexnow.ping_urls([URL]) is False


@pytest.mark.parametrize('code,body,expected', [
    (200, indexnow.INDEXNOW_KEY.encode(), 'key_matches'),
    (200, b'\xef\xbb\xbf' + indexnow.INDEXNOW_KEY.encode() + b'\n', 'key_matches'),
    (200, b'<html>not the key</html>', 'key_content_mismatch'),
    (200, b'x' * 1025, 'key_content_mismatch'),
    (200, b'\xff\xff', 'key_content_mismatch'), (404, b'', 'key_http_error'),
    (301, b'', 'key_http_error')])
def test_public_key_probe_is_bounded_and_does_not_follow_redirects(monkeypatch, code, body, expected):
    result = response(code)
    result.iter_content.return_value = [body]
    context = Mock(__enter__=Mock(return_value=result), __exit__=Mock(return_value=False))
    get = Mock(return_value=context)
    monkeypatch.setattr(indexnow.requests, 'get', get)
    assert indexnow.check_key() == expected
    assert get.call_args.kwargs['allow_redirects'] is False
    assert get.call_args.kwargs['stream'] is True


def test_batch_over_limit_does_not_silently_drop_urls(monkeypatch):
    post = Mock()
    monkeypatch.setattr(indexnow.requests, 'post', post)
    assert indexnow.submit_urls([URL + str(i) for i in range(10001)])['status'] == 'too_many_urls'
    post.assert_not_called()


def setup_module_script():
    return importlib.import_module('scripts.setup_indexnow')


def test_setup_defaults_to_readonly_probe(monkeypatch):
    module = setup_module_script()
    monkeypatch.setattr(module, 'load_dotenv', lambda: None)
    monkeypatch.setattr(module, 'check_key', lambda host: 'key_matches')
    submit = Mock()
    monkeypatch.setattr(module, 'submit_urls', submit)
    assert module.main([]) == 0
    submit.assert_not_called()


def test_setup_explicit_submission_uses_configured_path(monkeypatch):
    module = setup_module_script()
    monkeypatch.setattr(module, 'load_dotenv', lambda: None)
    monkeypatch.setattr(module, 'check_key', lambda host: 'key_matches')
    submit = Mock(return_value={'accepted': True})
    monkeypatch.setattr(module, 'submit_urls', submit)
    assert module.main(['--submit', URL]) == 0
    submit.assert_called_once_with([URL], 'trendpulse.blog')


@pytest.mark.parametrize('status,body,exit_code', [
    (200, b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>' + URL.encode() + b'</loc></url></urlset>', 0),
    (503, b'provider error', 1), (200, b'invalid XML', 1)])
def test_setup_explicit_sitemap_handles_valid_and_failed_inputs(monkeypatch, status, body, exit_code):
    module = setup_module_script()
    monkeypatch.setattr(module, 'load_dotenv', lambda: None)
    monkeypatch.setattr(module, 'check_key', lambda host: 'key_matches')
    monkeypatch.setattr(module.requests, 'get', Mock(return_value=Mock(status_code=status, content=body)))
    submit = Mock(return_value={'accepted': True})
    monkeypatch.setattr(module, 'submit_urls', submit)
    assert module.main(['--sitemap', 'https://trendpulse.blog/post-sitemap.xml']) == exit_code
    if exit_code == 0:
        submit.assert_called_once_with([URL], 'trendpulse.blog')
    else:
        submit.assert_not_called()


def test_setup_does_not_submit_with_failed_public_key_check(monkeypatch):
    module = setup_module_script()
    monkeypatch.setattr(module, 'load_dotenv', lambda: None)
    monkeypatch.setattr(module, 'check_key', lambda host: 'key_http_error')
    submit = Mock()
    monkeypatch.setattr(module, 'submit_urls', submit)
    assert module.main(['--submit', URL]) == 1
    submit.assert_not_called()
