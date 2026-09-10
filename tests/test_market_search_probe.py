import json
import logging
import os
from unittest.mock import Mock

import pytest
import requests

from scripts import check_market_search as probe


@pytest.fixture(autouse=True)
def search_configuration(monkeypatch):
    monkeypatch.delenv('MARKET_SEARCH_PROVIDER', raising=False)
    monkeypatch.setenv('GOOGLE_SEARCH_API_KEY', 'private-probe-key')
    monkeypatch.setenv('GOOGLE_SEARCH_ENGINE_ID', 'private-probe-engine')
    monkeypatch.delenv('GOOGLE_SEARCH_ALTERNATE_API_KEY', raising=False)


def google_response(query, count=6, domains=3):
    return Mock(status_code=200, json=Mock(return_value={'items': [
        {'link': f'https://site{index % domains}.example/result/{index}',
         'title': query, 'snippet': 'private-result-text'}
        for index in range(count)
    ]}))


def read_reports(capsys):
    output = capsys.readouterr()
    assert output.err == ''
    assert 'private-' not in output.out
    assert 'https://' not in output.out
    assert not any(query in output.out for query, _ in probe.CASES)
    return [json.loads(line) for line in output.out.splitlines()]


def test_real_search_helpers_probe_three_cases_without_exposing_results(monkeypatch, capsys):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs['params']['q']))
        return google_response(kwargs['params']['q'])

    monkeypatch.setattr(probe.market_search.requests, 'get', get)
    assert probe.main() == 0
    reports = read_reports(capsys)
    assert [query for _, query in calls] == [case[0] for case in probe.CASES]
    assert all(url == 'https://www.googleapis.com/customsearch/v1' for url, _ in calls)
    assert reports == [dict(case=index, credential_source='current', provider='google_custom_search', row_count=6,
                           sample_row_count=6, distinct_domains=3, approximate_related_rows=6,
                           reason='ok', failures=[], google_project_numbers=[]) for index in (1, 2, 3)]


def test_failure_then_ddg_success_reports_actual_fallback_and_fixed_reason(monkeypatch, capsys):
    def get(url, **kwargs):
        if 'googleapis.com' in url:
            response = Mock(status_code=400)
            response.raise_for_status.side_effect = requests.HTTPError('private-probe-key')
            response.json.return_value = {'error': {'message': 'API_KEY_INVALID private-probe-key'}}
            return response
        query = kwargs['params']['q']
        html = ''.join(f'<div class="result"><a class="result__a" '
                       f'href="https://site{i % 3}.example/{i}">{query}</a>'
                       '<span class="result__snippet">private-result-text</span></div>' for i in range(5))
        return Mock(status_code=200, url=url, text=html)

    monkeypatch.setattr(probe.market_search.requests, 'get', get)
    assert probe.main() == 0
    for report in read_reports(capsys):
        assert report['provider'] == 'duckduckgo_proxy'
        assert report['sample_row_count'] == 5
        assert report['failures'] == [{'provider': 'google_custom_search',
                                      'reason': 'api_key_invalid', 'http_status': 400}]


def test_empty_challenge_fails_all_three_cases_without_logging_secrets(monkeypatch, capsys, caplog):
    monkeypatch.delenv('GOOGLE_SEARCH_API_KEY')
    response = Mock(status_code=202, url='https://html.duckduckgo.com/html/',
                    text='<form id="challenge-form">private-challenge</form>')
    get = Mock(return_value=response)
    monkeypatch.setattr(probe.market_search.requests, 'get', get)
    assert probe.main() == 1
    assert get.call_count == 3
    for report in read_reports(capsys):
        assert report['reason'] == 'empty_results'
        assert report['row_count'] == report['sample_row_count'] == report['distinct_domains'] == 0
        assert report['failures'] == [
            {'provider': 'google_custom_search', 'reason': 'configuration_missing', 'http_status': None},
            {'provider': 'duckduckgo_proxy', 'reason': 'challenge', 'http_status': 202},
        ]
    assert caplog.text == ''


def test_network_failure_does_not_leak_exception_urls_or_skip_later_cases(monkeypatch, capsys, caplog):
    get = Mock(side_effect=requests.Timeout('https://private-host/?key=private-probe-key'))
    monkeypatch.setattr(probe.market_search.requests, 'get', get)
    assert probe.main() == 1
    assert get.call_count == 6
    for report in read_reports(capsys):
        assert report['reason'] == 'empty_results'
        assert [failure['reason'] for failure in report['failures']] == ['network_error', 'network_error']
    assert caplog.text == ''


@pytest.mark.parametrize('count,domains', [(4, 4), (6, 2)])
def test_insufficient_sample_fails_with_shared_thresholds(monkeypatch, capsys, count, domains):
    monkeypatch.setattr(probe.market_search.requests, 'get',
                        lambda url, **kwargs: google_response(kwargs['params']['q'], count, domains))
    assert probe.main() == 1
    assert {report['reason'] for report in read_reports(capsys)} == {'insufficient_search_sample'}


def test_shared_sample_validation_excludes_duplicate_self_and_invalid_rows(monkeypatch, capsys):
    response = google_response(probe.CASES[0][0], count=5)
    items = response.json.return_value['items']
    items[1]['link'] = items[0]['link'] + '#duplicate'
    items[2]['link'] = 'https://trendpulse.blog/already-published'
    items[3]['title'] = ''
    items[4]['link'] = 'https://private-user:private-password@site.example/a'
    monkeypatch.setattr(probe.market_search.requests, 'get', lambda *args, **kwargs: response)
    assert probe.main() == 1
    for report in read_reports(capsys):
        assert report['row_count'] == 4
        assert report['sample_row_count'] == report['distinct_domains'] == 1
        assert report['reason'] == 'insufficient_search_sample'


def test_unrelated_successful_http_response_does_not_pass(monkeypatch, capsys):
    monkeypatch.setattr(probe.market_search.requests, 'get', lambda *a, **k: google_response('무관한 결과'))
    assert probe.main() == 1
    for report in read_reports(capsys):
        assert report['approximate_related_rows'] == 0
        assert report['reason'] == 'no_keyword_overlap'


def test_approximate_match_accepts_spacing_and_intent_synonyms(monkeypatch, capsys):
    titles = iter(('ＩＴＱ 확인서 발급', '종소세 기한 후 신고 환급', '대장 내시경 식단'))
    monkeypatch.setattr(probe.market_search.requests, 'get', lambda *a, **k: google_response(next(titles)))
    assert probe.main() == 0
    assert [report['approximate_related_rows'] for report in read_reports(capsys)] == [6, 6, 6]


def test_unexpected_error_and_debug_logs_are_private_and_logging_is_restored(monkeypatch, capsys, caplog):
    logger = probe.market_search.logger
    original = (logger.handlers[:], logger.propagate, logger.level, logger.disabled)
    noisy = logging.getLogger('urllib3.connectionpool')
    monkeypatch.setattr(noisy, 'level', logging.DEBUG)

    def fail(*args, **kwargs):
        logger.warning('private-provider-response')
        noisy.debug('https://private-host/?key=private-probe-key')
        raise RuntimeError('private-unexpected-error')

    monkeypatch.setattr(probe.market_search, 'search_results', fail)
    with caplog.at_level(logging.DEBUG):
        assert probe.main() == 1
    assert {report['reason'] for report in read_reports(capsys)} == {'search_error'}
    assert caplog.text == ''
    assert (logger.handlers, logger.propagate, logger.level, logger.disabled) == original
    assert noisy.level == logging.DEBUG


@pytest.mark.parametrize('provider,rows,reason', [
    ('private-unknown-provider', [], 'unexpected_provider'),
    ('google_custom_search', {'private': 'bad-payload'}, 'invalid_result_shape'),
])
def test_invalid_contract_emits_fixed_reason(monkeypatch, capsys, provider, rows, reason):
    monkeypatch.setattr(probe.market_search, 'search_results', lambda query: (provider, rows))
    assert probe.main() == 1
    assert {report['reason'] for report in read_reports(capsys)} == {reason}


def test_diagnostic_handler_rejects_unrecognized_fields():
    handler = probe._Failures()
    record = logging.LogRecord('probe', logging.WARNING, '', 0, probe.FAILURE_TEMPLATE,
                               ('private-provider', 'private-reason', 'private-status'), None)
    handler.emit(record)
    assert handler.items == [{'provider': 'unknown', 'reason': 'unclassified_failure', 'http_status': None}]


@pytest.mark.parametrize('original_present', [True, False])
def test_alternate_key_runs_once_and_cannot_turn_current_failure_into_success(
        monkeypatch, capsys, original_present):
    if not original_present:
        monkeypatch.delenv('GOOGLE_SEARCH_API_KEY')
    monkeypatch.setenv('GOOGLE_SEARCH_ALTERNATE_API_KEY', 'private-alternate-key')
    google_calls = []

    def get(url, **kwargs):
        if 'googleapis.com' in url:
            google_calls.append(kwargs['params']['q'])
            if kwargs['params']['key'] == 'private-alternate-key':
                return google_response(kwargs['params']['q'])
            response = Mock(status_code=400)
            response.raise_for_status.side_effect = requests.HTTPError('private-current-key-rejected')
            response.json.return_value = {'error': {'message': 'API_KEY_INVALID'}}
            return response
        return Mock(status_code=202, url=url, text='<form id="challenge-form">private-body</form>')

    monkeypatch.setattr(probe.market_search.requests, 'get', get)
    assert probe.main() == 1
    reports = read_reports(capsys)
    assert len(reports) == 4
    assert [report['credential_source'] for report in reports] == ['current'] * 3 + ['alternate']
    assert [report['reason'] for report in reports] == ['empty_results'] * 3 + ['ok']
    assert reports[-1]['provider'] == 'google_custom_search'
    assert google_calls == ([case[0] for case in probe.CASES] if original_present else []) + [probe.CASES[0][0]]
    assert os.environ.get('GOOGLE_SEARCH_API_KEY') == ('private-probe-key' if original_present else None)


def test_successful_current_configuration_never_tries_alternate(monkeypatch, capsys):
    monkeypatch.setenv('GOOGLE_SEARCH_ALTERNATE_API_KEY', 'private-alternate-key')
    calls = []

    def get(url, **kwargs):
        calls.append(kwargs['params']['key'])
        return google_response(kwargs['params']['q'])

    monkeypatch.setattr(probe.market_search.requests, 'get', get)
    assert probe.main() == 0
    assert len(read_reports(capsys)) == 3
    assert calls == ['private-probe-key'] * 3


def test_explicit_native_failure_never_retries_with_an_alternate_google_key(monkeypatch, capsys):
    monkeypatch.setenv('MARKET_SEARCH_PROVIDER', 'codex_native_search')
    monkeypatch.setenv('GOOGLE_SEARCH_ALTERNATE_API_KEY', 'private-alternate-key')
    search = Mock(return_value=('codex_native_search', []))
    monkeypatch.setattr(probe.market_search, 'search_results', search)
    assert probe.main() == 1
    assert search.call_count == 3
    reports = read_reports(capsys)
    assert len(reports) == 3
    assert all(report['provider'] == 'codex_native_search' for report in reports)
    assert all(report['reason'] == 'empty_results' for report in reports)


def test_native_samples_preserve_provider_and_the_same_sample_thresholds(monkeypatch, capsys):
    monkeypatch.setenv('MARKET_SEARCH_PROVIDER', 'codex_native_search')

    def search(query):
        rows = [{'url': f'https://site{i % 3}.example/{i}',
                 'domain': f'site{i % 3}.example', 'title': query,
                 'snippet': 'private-result-text'} for i in range(5)]
        return 'codex_native_search', rows

    monkeypatch.setattr(probe.market_search, 'search_results', search)
    assert probe.main() == 0
    for report in read_reports(capsys):
        assert report['provider'] == 'codex_native_search'
        assert report['sample_row_count'] == 5
        assert report['distinct_domains'] == 3
        assert report['approximate_related_rows'] == 5


def test_alternate_exception_restores_original_key_and_stays_private(monkeypatch, capsys):
    monkeypatch.setenv('GOOGLE_SEARCH_ALTERNATE_API_KEY', 'private-alternate-key')
    search = Mock(side_effect=RuntimeError('private-exception'))
    monkeypatch.setattr(probe.market_search, 'search_results', search)
    assert probe.main() == 1
    assert search.call_count == 4
    assert {report['reason'] for report in read_reports(capsys)} == {'search_error'}
    assert os.environ['GOOGLE_SEARCH_API_KEY'] == 'private-probe-key'


def test_errorinfo_project_number_is_bound_to_alternate_probe_only(monkeypatch, capsys, caplog):
    monkeypatch.setenv('GOOGLE_SEARCH_ALTERNATE_API_KEY', 'private-alternate-key')

    def get(url, **kwargs):
        if 'googleapis.com' not in url:
            return Mock(status_code=202, url=url, text='<form id="challenge-form">private-body</form>')
        alternate = kwargs['params']['key'] == 'private-alternate-key'
        response = Mock(status_code=403 if alternate else 400)
        response.raise_for_status.side_effect = requests.HTTPError('https://private-url/?key=private-key')
        detail = {'@type': 'type.googleapis.com/google.rpc.ErrorInfo', 'reason': 'SERVICE_DISABLED',
                  'metadata': {'service': 'customsearch.googleapis.com', 'consumer': 'projects/123456789012',
                               'activationUrl': 'https://private-console-url/', 'key': 'private-alternate-key'}}
        response.json.return_value = {'error': {'message': 'private-message' if alternate else 'API_KEY_INVALID',
                                              'details': [detail] if alternate else []}}
        return response

    monkeypatch.setattr(probe.market_search.requests, 'get', get)
    assert probe.main() == 1
    reports = read_reports(capsys)
    assert [report['google_project_numbers'] for report in reports] == [[], [], [], ['123456789012']]
    assert reports[-1]['credential_source'] == 'alternate'
    assert reports[-1]['failures'][0] == {'provider': 'google_custom_search', 'reason': 'api_not_enabled',
                                        'http_status': 403}
    assert reports[-1]['reason'] == 'empty_results'
    assert caplog.text == ''


@pytest.mark.parametrize('number', ['123\nprivate-key', '123\n', '123?key=private-key', '１２３', 123, None])
def test_probe_project_event_validates_numbers_again(number):
    handler = probe._Failures()
    record = logging.LogRecord('probe', logging.DEBUG, '', 0, probe.market_search.GOOGLE_PROJECT_TEMPLATE,
                               (number,), None)
    handler.emit(record)
    assert handler.google_project_numbers == []
    assert handler.items == []


def test_search_probe_workflow_is_exclusive_and_has_no_publication_or_codex_credentials():
    from pathlib import Path
    import yaml

    workflow = yaml.safe_load(Path('.github/workflows/blog-keyword-select.yml').read_text())
    jobs = workflow['jobs']
    probe_job = jobs['search-check']
    assert probe_job['if'] == 'inputs.search_check_only == true'
    assert probe_job['permissions'] == {'contents': 'read'}
    for name in ('select', 'candidate-check'):
        assert 'inputs.search_check_only != true' in jobs[name]['if']
    check = next(step for step in probe_job['steps'] if step.get('name') == 'Check actual search result availability')
    assert check['run'] == 'python scripts/check_market_search.py'
    assert set(check['env']) == {'GOOGLE_SEARCH_API_KEY', 'GOOGLE_SEARCH_ENGINE_ID'}
    assert check['env']['GOOGLE_SEARCH_API_KEY'] == '${{ secrets.GOOGLE_CUSTOM_SEARCH_API_KEY }}'
    job_text = json.dumps(probe_job)
    assert all(word not in job_text for word in ('CODEX_AUTH', 'WP_GENERAL', 'select_blog_keywords',
                                               'git push', 'src.main', 'fetch_cak_candidates'))
