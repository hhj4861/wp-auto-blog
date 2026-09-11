from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from scripts.report_keyword_performance import build_report


def ledger():
    return [{'keyword': '산업기사시험일정', 'category': '취업', 'post_id': 1743,
             'url': 'https://trendpulse.blog/industrial-engineer-exam-2026/',
             'published_at': '2026-09-10T13:05:13+00:00'}]


def clock(day):
    return datetime.fromisoformat(day + 'T20:00:00+00:00')


def test_new_post_is_pending_without_zero_metrics_or_api_calls():
    query, inspect = Mock(), Mock()
    row = build_report(ledger(), query, inspect, clock('2026-09-11'))['posts'][0]
    assert row['windows']['7']['status'] == row['windows']['28']['status'] == 'collecting'
    assert row['windows']['7']['metrics'] is None
    query.assert_not_called()
    inspect.assert_not_called()


def test_mature_windows_use_exact_url_final_data_and_pacific_dates():
    totals = {'clicks': 5, 'impressions': 100, 'ctr': .05, 'position': 8}
    query = Mock(side_effect=[[totals], [{'query': '산업기사 시험일정', **totals}]])
    inspect = Mock(return_value={'verdict': 'PASS'})
    row = build_report(ledger(), query, inspect, clock('2026-09-19'))['posts'][0]
    assert row['windows']['7']['status'] == 'reported'
    assert row['windows']['7']['metrics'] == totals
    assert row['windows']['28']['status'] == 'collecting'
    call = query.call_args_list[0]
    assert call.args == ('2026-09-10', '2026-09-16', [])
    assert call.kwargs['data_state'] == 'final'
    assert call.kwargs['filters'] == [{'dimension': 'page', 'operator': 'equals',
                                      'expression': ledger()[0]['url']}]


def test_missing_rows_and_failed_calls_are_not_zero_performance():
    row = build_report(ledger(), Mock(return_value=[]), Mock(return_value={'error': 'private'}),
                       clock('2026-10-11'))['posts'][0]
    assert row['windows']['7']['status'] == row['windows']['28']['status'] == 'no_reported_rows'
    assert row['windows']['7']['metrics'] is None
    assert row['index'] == {'status': 'unavailable'}
    report = build_report(ledger(), Mock(side_effect=SystemExit('private credentials')),
                         Mock(side_effect=RuntimeError('private')), clock('2026-10-11'))
    assert report['posts'][0]['windows']['7']['status'] == 'unavailable'
    assert 'private' not in str(report)


@pytest.mark.parametrize('url', ['https://example.com/post/', 'http://trendpulse.blog/post/',
                               'https://user:password@trendpulse.blog/post/',
                               'https://trendpulse.blog/post/?key=secret'])
def test_invalid_destination_is_rejected_before_reading_api(url):
    rows = ledger(); rows[0]['url'] = url
    query = Mock()
    with pytest.raises(ValueError, match='Invalid published keyword ledger'):
        build_report(rows, query, Mock(), clock('2026-10-11'))
    query.assert_not_called()


def test_before_delay_buffer_and_old_or_duplicate_posts_are_bounded():
    rows = ledger()
    assert build_report(rows, Mock(), Mock(return_value={}), clock('2026-09-18'))['posts'][0]['windows']['7']['status'] == 'collecting'
    report = build_report(rows * 3, Mock(return_value=[]), Mock(return_value={}), clock('2026-09-19'))
    assert len(report['posts']) == 1
    assert not build_report(rows, Mock(), Mock(), clock('2027-01-01'))['posts']


def test_gsc_midnight_uses_pacific_day_not_utc_day():
    rows = ledger(); rows[0]['published_at'] = '2026-09-11T01:00:00+00:00'
    report = build_report(rows, Mock(), Mock(), clock('2026-09-11'))
    assert report['posts'][0]['windows']['7']['start'] == '2026-09-10'


def test_gsc_client_preserves_default_and_sends_explicit_final(monkeypatch):
    from src import gsc_client
    monkeypatch.setattr(gsc_client, '_headers', lambda: {})
    request = Mock(return_value=Mock(status_code=200, json=lambda: {'rows': []}))
    monkeypatch.setattr(gsc_client.requests, 'post', request)
    gsc_client.query('2026-09-01', '2026-09-07', [])
    assert request.call_args.kwargs['json']['dataState'] == 'all'
    gsc_client.query('2026-09-01', '2026-09-07', [], data_state='final')
    assert request.call_args.kwargs['json']['dataState'] == 'final'
    with pytest.raises(ValueError):
        gsc_client.query('2026-09-01', '2026-09-07', [], data_state='invented')
    assert request.call_count == 2


@pytest.mark.parametrize('row', [{}, {'clicks': 0, 'impressions': None, 'ctr': 0, 'position': 0},
                              {'clicks': -1, 'impressions': 0, 'ctr': 0, 'position': 0},
                              {'clicks': 0, 'impressions': 0, 'ctr': 2, 'position': 0}])
def test_final_api_response_missing_metrics_is_unavailable_not_zero(monkeypatch, row):
    from src import gsc_client
    monkeypatch.setattr(gsc_client, '_headers', lambda: {})
    monkeypatch.setattr(gsc_client.requests, 'post', Mock(return_value=Mock(
        status_code=200, json=lambda: {'rows': [row]})))
    report = build_report(ledger(), gsc_client.query, Mock(return_value={}), clock('2026-10-11'))
    assert report['posts'][0]['windows']['7']['status'] == 'unavailable'
    assert report['posts'][0]['windows']['7']['metrics'] is None


def test_time_budget_preserves_unavailable_evidence_without_starting_requests():
    query, inspect, snapshots = Mock(), Mock(), []
    report = build_report(ledger(), query, inspect, clock('2026-10-11'),
        time_budget_seconds=0, on_progress=lambda value: snapshots.append(str(value)))
    assert report['posts'][0]['windows']['7']['reason'] == 'time_budget'
    assert report['posts'][0]['index']['reason'] == 'time_budget'
    assert len(snapshots) >= 4
    query.assert_not_called()
    inspect.assert_not_called()


def test_progress_is_written_before_a_query_can_be_interrupted():
    snapshots = []
    with pytest.raises(KeyboardInterrupt):
        build_report(ledger(), Mock(side_effect=KeyboardInterrupt), Mock(), clock('2026-10-11'),
                     on_progress=lambda value: snapshots.append(str(value)))
    assert 'query_pending' in snapshots[-1]
    assert 'industrial-engineer-exam-2026' in snapshots[-1]
