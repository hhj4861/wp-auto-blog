from unittest.mock import Mock
import json

import pytest

from src import analysis_runtime as runtime
from src.codex_client import CodexRequestError, CodexResponseError
from src.codex_search import NativeSearchError


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(runtime, 'sleep', lambda _: None)


@pytest.mark.parametrize('error,code,retry', [
    (CodexRequestError(1, '503 service secret'), 'network_or_service', True),
    (CodexResponseError('timeout', 'private-command'), 'timeout', True),
    (CodexResponseError('empty_response', 'private-path'), 'empty_response', True),
    (NativeSearchError('timeout'), 'timeout', True),
    (TimeoutError('secret'), 'timeout', True),
    (CodexRequestError(1, 'refresh_token_reused secret'), 'refresh_token_reused', False),
    (CodexRequestError(1, '429 too many requests secret'), 'usage_limit', False),
    (CodexRequestError(1, 'model_not_found secret'), 'model_unavailable', False),
    (RuntimeError('secret'), 'unexpected_error', False),
])
def test_classified_failures_recover_only_transient_ones(error, code, retry, caplog):
    call = Mock(side_effect=[error, '{"supported":false}'])
    if retry:
        assert runtime.validated_call(call, 'private prompt', runtime.parse_json) == {'supported': False}
    else:
        with pytest.raises(runtime.AnalysisError) as caught:
            runtime.validated_call(call, 'private prompt', runtime.parse_json)
        assert caught.value.code == code
    assert call.call_count == (2 if retry else 1)
    assert 'secret' not in caplog.text and 'private' not in caplog.text


def test_nested_failures_do_not_multiply_attempts():
    call = Mock(side_effect=CodexResponseError('timeout', 'secret'))
    outer = lambda prompt: runtime.validated_call(call, prompt, runtime.parse_json)
    with pytest.raises(runtime.AnalysisError) as caught:
        runtime.validated_call(outer, 'input')
    assert caught.value.code == 'timeout' and call.call_count == 2


def test_all_stages_share_extra_call_budget_and_diagnostics():
    calls = []
    @runtime.selection_scope
    def run(category):
        for i in range(8):
            call = Mock(side_effect=['{', '{}'])
            calls.append(call)
            try:
                runtime.validated_call(call, 'input', runtime.parse_json, label='topic_suitability')
            except runtime.AnalysisError:
                pass
        return {'selected': []}
    report = run('리뷰')
    assert [call.call_count for call in calls] == [2] * 4 + [1] * 4
    assert report['analysis_recovery_attempts'] == 4
    assert len(report['analysis_diagnostics']) == 12
    assert {x['stage'] for x in report['analysis_diagnostics']} == {'topic_suitability'}
    # Context is reset after returning; an unrelated operation can retry.
    call = Mock(side_effect=['{', '{}'])
    assert runtime.validated_call(call, 'input', runtime.parse_json) == {}


def test_fatal_failure_stops_later_calls_and_never_returns_selected():
    later = Mock(return_value='{}')
    @runtime.selection_scope
    def run(category):
        try:
            runtime.validated_call(Mock(side_effect=CodexRequestError(1, 'unauthorized')), 'input')
        except runtime.AnalysisError:
            pass
        try:
            runtime.validated_call(later, 'input')
        except runtime.AnalysisError:
            pass
        return {'selected': [{'keyword': 'cannot publish'}]}
    report = run('리뷰')
    later.assert_not_called()
    assert report['selected'] == [] and report['operational_error'] == 'unauthorized'
    assert report['analysis_recovery_attempts'] == 0


def test_shortlist_exception_produces_fresh_empty_report_with_history():
    @runtime.selection_scope
    def run(category, **kwargs):
        runtime.validated_call(Mock(side_effect=RuntimeError('secret')), 'input')
    history = [{'keyword': 'retained'}]
    report = run('리뷰', failure_history=history)
    assert report['selected'] == [] and report['failure_history'] == history
    assert report['research_stop_reason'] == 'analysis_unavailable'
    assert report['operational_error'] == 'unexpected_error'
    assert report['analysis_diagnostics'][0]['status'] == 'error'


def test_schema_recovery_cannot_change_a_valid_negative_decision():
    call = Mock(side_effect=['{', '{"supported":false}', '{"supported":true}'])
    assert runtime.validated_call(call, 'input', runtime.parse_json) == {'supported': False}
    assert call.call_count == 2


def test_deadline_prevents_added_calls(monkeypatch):
    clock = [0]
    monkeypatch.setattr(runtime, 'monotonic', lambda: clock[0])
    call = Mock()
    def fail(_):
        clock[0] = 1501
        raise TimeoutError('secret')
    call.side_effect = fail
    @runtime.selection_scope
    def run(category):
        runtime.validated_call(call, 'input')
    report = run('리뷰')
    assert report['analysis_recovery_attempts'] == 0 and call.call_count == 1


@pytest.mark.parametrize('raw', [None, 'x' * 100001, 'not json'])
def test_bad_json_is_bounded(raw):
    call = Mock(return_value=raw)
    with pytest.raises(runtime.AnalysisError, match='invalid_json'):
        runtime.validated_call(call, 'input', runtime.parse_json)
    assert call.call_count == 2


def test_recovered_transport_followed_by_bad_schema_cannot_multiply_calls():
    call = Mock(side_effect=[CodexResponseError('timeout', 'private'), '{}', '{"ok":true}'])
    def schema(raw):
        value = runtime.parse_json(raw)
        if value.get('ok') is not True:
            raise ValueError('missing field')
        return value
    with pytest.raises(runtime.AnalysisError, match='invalid_schema'):
        runtime.validated_call(lambda prompt: runtime.validated_call(call, prompt), 'input', schema)
    assert call.call_count == 2
