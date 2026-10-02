"""Synthetic daily series and provider envelopes, never live demand evidence."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
import requests

from src import recent_search_trend as trend

NOW = datetime(2026, 10, 2, 8, tzinfo=timezone.utc)


def series(values=None, now=NOW, lag=1):
    values = values or [20] * 12 + [40, 60, 80]
    end = now.astimezone(trend.KST).date() - timedelta(days=lag)
    return [{'period': (end - timedelta(days=len(values) - i - 1)).isoformat(), 'ratio': value}
            for i, value in enumerate(values)]


def credentials(monkeypatch):
    monkeypatch.setenv('NAVER_API_HUB_CLIENT_ID', 'private-test-id')
    monkeypatch.setenv('NAVER_API_HUB_CLIENT_SECRET', 'private-test-secret')


def responder(calls):
    def post(url, **kwargs):
        calls.append((url, kwargs))
        body = kwargs['json']
        return Mock(status_code=200, json=lambda: {**{k: body[k] for k in ('startDate', 'endDate', 'timeUnit')},
            'results': [{'title': row['groupName'], 'keywords': row['keywords'], 'data': series()}
                        for row in reversed(body['keywordGroups'])]})
    return post


def test_recent_growth_uses_three_windows_and_relative_units():
    signal = trend.analyze('엑셀틀고정', series(), NOW)
    assert signal['qualified_rising'] is True
    assert signal['latest_period'] == '2026-10-01'
    assert signal['lag_days'] == 1
    assert signal['rising_days'] == 3
    assert signal['latest_vs_previous_weekday'] == 3
    assert signal['recent_3d_vs_previous_7d'] == 2
    assert signal['unit'] == 'relative_index'
    assert 0 < signal['points'] <= 45
    assert trend.valid(signal, '엑셀틀고정', NOW)


@pytest.mark.parametrize('values', [[20] * 15, [20] * 14 + [100], [80] * 12 + [50, 30, 20]])
def test_flat_single_spike_and_falling_are_not_priority(values):
    signal = trend.analyze('query', series(values), NOW)
    assert signal['status'] == 'measured'
    assert signal['qualified_rising'] is False
    assert signal['points'] == 0


def test_ratios_are_scale_invariant_not_cross_keyword_counts():
    a = trend.analyze('query', series(), NOW)
    b = trend.analyze('query', series([2] * 12 + [4, 6, 8]), NOW)
    assert (a['qualified_rising'], a['points']) == (b['qualified_rising'], b['points'])


@pytest.mark.parametrize('mutation,status', [
    (lambda rows: rows + [rows[0]], 'invalid_response'),
    (lambda rows: rows[:-4], 'stale_data'),
    (lambda rows: rows[7:], 'insufficient_history'),
    (lambda rows: rows[:9] + rows[10:], 'insufficient_history'),
    (lambda rows: rows[:-1] + [{'period': '2026-10-02', 'ratio': 50}], 'invalid_response'),
    (lambda rows: rows[:-1] + [{'period': '2026-10-01', 'ratio': float('nan')}], 'invalid_response'),
    (lambda rows: rows[:-1] + [{'period': '2026-10-01', 'ratio': True}], 'invalid_response'),
    (lambda rows: rows[:-1] + [{'period': '2026-10-01', 'ratio': 101}], 'invalid_response'),
])
def test_bad_or_incomplete_data_never_receives_bonus(mutation, status):
    signal = trend.analyze('query', mutation(series()), NOW)
    assert signal['status'] == status
    assert signal['points'] == 0
    assert signal['qualified_rising'] is False


def test_zero_baseline_never_becomes_infinite_growth():
    assert trend.analyze('q', series([0] * 12 + [10, 20, 30]), NOW)['status'] == 'zero_baseline'


def test_one_day_provider_delay_is_labeled_and_older_data_is_stale():
    assert trend.analyze('q', series(lag=2)[1:], NOW)['lag_days'] == 2
    assert trend.analyze('q', series(lag=3)[2:], NOW)['status'] == 'stale_data'


def test_cache_validation_recomputes_points_and_binds_keyword_and_kst_day():
    s = trend.analyze('q', series(), NOW)
    assert not trend.valid(s, 'another', NOW)
    assert not trend.valid(s, 'q', NOW + timedelta(hours=8))  # next day in KST
    assert not trend.valid(s, 'q', NOW - timedelta(seconds=1))
    for field, value in [('points', 99), ('qualified_rising', False), ('rising_days', 1), ('unit', 'search_count')]:
        changed = {**s, field: value}
        assert not trend.valid(changed, 'q', NOW)


def test_missing_credentials_make_no_request(monkeypatch):
    monkeypatch.delenv('NAVER_API_HUB_CLIENT_ID', raising=False)
    monkeypatch.delenv('NAVER_API_HUB_CLIENT_SECRET', raising=False)
    post = Mock(side_effect=AssertionError('must not send'))
    monkeypatch.setattr(trend.requests, 'post', post)
    collector = trend.Collector(NOW)
    assert collector.collect(['q'])['q']['status'] == 'not_configured'
    assert collector.summary()['status'] == 'not_configured'
    post.assert_not_called()


def test_exact_keyword_batches_and_fixed_trusted_endpoint(monkeypatch):
    credentials(monkeypatch)
    calls = []
    monkeypatch.setattr(trend.requests, 'post', responder(calls))
    c = trend.Collector(NOW)
    results = c.collect([f'keyword{i}' for i in range(7)])
    assert len(calls) == 2
    assert all(row['qualified_rising'] for row in results.values())
    assert calls[0][0] == trend.URL
    assert calls[0][1]['json']['endDate'] == '2026-10-01'
    assert calls[0][1]['json']['startDate'] == '2026-09-17'
    assert calls[0][1]['allow_redirects'] is False
    assert all(len(group['keywords']) == 1 for group in calls[0][1]['json']['keywordGroups'])
    c.collect(['keyword0'])
    assert len(calls) == 2


@pytest.mark.parametrize('code,status,expected_calls', [(401, 'authentication_failed', 1),
    (403, 'authentication_failed', 1), (429, 'rate_limited', 1), (500, 'http_error', 2), (302, 'http_error', 2)])
def test_provider_errors_are_bounded_and_secret_free(monkeypatch, capsys, code, status, expected_calls):
    credentials(monkeypatch)
    post = Mock(return_value=Mock(status_code=code, text='private-test-secret'))
    monkeypatch.setattr(trend.requests, 'post', post)
    c = trend.Collector(NOW)
    results = c.collect([f'q{i}' for i in range(7)])
    assert {row['status'] for row in results.values()} == {status}
    assert post.call_count == expected_calls
    assert 'private-' not in str(results) + str(c.summary())
    assert capsys.readouterr().out == ''


def test_request_and_time_caps(monkeypatch):
    credentials(monkeypatch)
    calls = []
    monkeypatch.setattr(trend.requests, 'post', responder(calls))
    monkeypatch.setattr(trend, 'MAX_CALLS', 1)
    c = trend.Collector(NOW)
    result = c.collect([f'q{i}' for i in range(11)])
    assert len(calls) == 1
    assert result['q10']['status'] == 'budget_exhausted'
    monkeypatch.setattr(trend, 'MAX_SECONDS', 0)
    assert trend.Collector(NOW).collect(['q'])['q']['status'] == 'budget_exhausted'


@pytest.mark.parametrize('kind', ['wrong_keyword', 'wrong_date', 'duplicate_group', 'malformed', 'timeout'])
def test_response_binding_and_network_errors(monkeypatch, kind):
    credentials(monkeypatch)
    normal = responder([])
    def post(url, **kwargs):
        if kind == 'timeout':
            raise requests.Timeout('private-test-secret')
        payload = deepcopy(normal(url, **kwargs).json())
        if kind == 'wrong_keyword': payload['results'][0]['keywords'] = ['another']
        if kind == 'wrong_date': payload['endDate'] = '2026-10-02'
        if kind == 'duplicate_group': payload['results'].append(payload['results'][0])
        if kind == 'malformed': payload = []
        return Mock(status_code=200, json=lambda: payload)
    monkeypatch.setattr(trend.requests, 'post', post)
    value = trend.Collector(NOW).collect(['q'])['q']
    assert value['status'] == ('network_error' if kind == 'timeout' else 'invalid_response')
    assert 'private-' not in str(value)


def test_probe_is_read_only_and_missing_keys_fail_explicitly(monkeypatch, capsys):
    from scripts import check_recent_search_trend as probe
    monkeypatch.delenv('NAVER_API_HUB_CLIENT_ID', raising=False)
    monkeypatch.delenv('NAVER_API_HUB_CLIENT_SECRET', raising=False)
    assert probe.main() == 1
    output = capsys.readouterr().out
    assert 'not_configured' in output
    assert 'private-' not in output
    assert 'https://' not in output


def test_probe_reports_actual_latest_day_without_claiming_absolute_volume(monkeypatch, capsys):
    from scripts import check_recent_search_trend as probe
    credentials(monkeypatch)
    calls = []
    monkeypatch.setattr(trend.requests, 'post', responder(calls))
    monkeypatch.setattr(probe, 'Collector', lambda _: trend.Collector(NOW))
    assert probe.main() == 0
    output = capsys.readouterr().out
    assert '2026-10-01' in output
    assert 'relative_index' in output
    assert 'private-' not in output


def test_replenishment_shares_request_time_budget_but_not_model_wait(monkeypatch):
    credentials(monkeypatch)
    calls = []
    monkeypatch.setattr(trend.requests, 'post', responder(calls))
    # Model research between replenishment calls must not spend network time budget.
    clock = iter([0, 0, 1, 600, 600, 601])
    monkeypatch.setattr(trend, 'monotonic', lambda: next(clock))
    c = trend.Collector(NOW)
    assert c.collect(['first'])['first']['status'] == 'measured'
    assert c.collect(['second'])['second']['status'] == 'measured'
    assert c.elapsed == 2
    assert len(calls) == 2
