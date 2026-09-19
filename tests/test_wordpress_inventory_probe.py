import json
from unittest.mock import Mock

import requests

from scripts.check_wordpress_inventory import check, summarize


def test_probe_reports_bad_rows_without_exposing_content_or_headers():
    response = Mock(status_code=200, headers={'X-WP-TotalPages': '2', 'Authorization': 'secret'})
    response.json.return_value = [{'title': {'rendered': 'private title'}, 'meta': []},
                                 {'title': {'raw': 'private title'}, 'meta': ['secret']}, None]
    report = summarize(response)
    assert report['invalid_title_rows'] == [1, 2]
    assert report['invalid_meta_rows'] == [1]
    assert report['pages_valid'] is True
    assert 'private' not in json.dumps(report) and 'secret' not in json.dumps(report)


def test_untrusted_error_strings_and_transport_errors_are_never_logged():
    response = Mock(status_code=403)
    response.json.return_value = {'code': 'secret arbitrary error', 'message': 'secret'}
    get = Mock(side_effect=[response, requests.Timeout('secret'), response])
    report = check({'WP_GENERAL_URL': 'https://trendpulse.blog',
                    'WP_GENERAL_USERNAME': 'private-user', 'WP_GENERAL_APP_PASSWORD': 'secret'}, get)
    assert len(report['probes']) == 3
    assert report['dotenv_roundtrip_equal'] is True
    assert 'secret' not in json.dumps(report) and 'private-user' not in json.dumps(report)
    assert all(call.kwargs['allow_redirects'] is False for call in get.call_args_list)


def test_unrelated_target_cannot_receive_credentials():
    get = Mock()
    assert check({'WP_GENERAL_URL': 'https://wrong.example', 'WP_GENERAL_USERNAME': 'u',
                  'WP_GENERAL_APP_PASSWORD': 'p'}, get) == {'status': 'invalid_configuration'}
    get.assert_not_called()


def test_every_inventory_page_is_checked_without_reading_all_latest_posts():
    response = Mock(status_code=200, headers={'X-WP-TotalPages': '4'})
    response.json.return_value = [{'title': {'rendered': 'private'}, 'meta': {}}]
    get = Mock(return_value=response)
    result = check({'WP_GENERAL_URL': 'https://trendpulse.blog', 'WP_GENERAL_USERNAME': 'u',
                    'WP_GENERAL_APP_PASSWORD': 'p'}, get)
    assert [row['page'] for row in result['probes']] == [1, 2, 3, 4, 1, 2, 3, 4, 1]
    assert all(row['http_status'] == 200 for row in result['probes'])
    assert all(call.kwargs['auth'] == ('u', 'p') for call in get.call_args_list)
    assert all(call.kwargs['timeout'] == 30 for call in get.call_args_list)
    assert 'private' not in json.dumps(result)
