"""Bounded, redacted diagnostics for model calls; negative opinions are not errors."""
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
import json
import logging
import re
from time import monotonic, sleep

from src.codex_client import CodexRequestError, CodexResponseError

log = logging.getLogger(__name__)
_STATE = ContextVar('analysis_state', default=None)
_OPERATION = ContextVar('analysis_operation', default=None)
_STAGE = ContextVar('analysis_stage', default='selection')
RETRYABLE = frozenset({'network_or_service', 'timeout', 'empty_response', 'invalid_json', 'invalid_schema'})
FATAL = frozenset({'refresh_token_reused', 'refresh_token_expired', 'refresh_token_revoked',
    'invalid_grant', 'token_invalidated', 'access_token_expired', 'account_deactivated',
    'refresh_failed', 'unauthorized', 'authentication_required', 'usage_limit',
    'model_unavailable', 'prompt_too_large', 'cli_incompatible'})
NATIVE_CODES = frozenset({'native_search_failed', 'invalid_protocol', 'output_limit',
    'unexpected_eof', 'server_request_denied', 'rpc_failed', 'turn_failed',
    'structured_results_unavailable', 'empty_structured_results', 'structured_fields_incomplete',
    'native_fields_incomplete', 'no_observed_search', 'invalid_results_shape',
    'invalid_query', 'unsafe_thread_configuration', 'unexpected_home_configuration',
    'unexpected_tool_activity', 'unexpected_web_activity', 'unexpected_search_query',
    'invalid_search_arguments', 'missing_search_arguments', 'unbound_search_arguments',
    'invalid_raw_item', 'unexpected_raw_item_type', 'unexpected_raw_agent_recipient',
    'unexpected_raw_function_identity', 'unexpected_raw_output_identity',
    'invalid_raw_call_id', 'invalid_raw_output_id'})
CODES = RETRYABLE | FATAL | NATIVE_CODES | {'unclassified', 'unexpected_error', 'retry_budget_exhausted'}
MAX_EXTRA_CALLS = 4


# Closed diagnostic vocabulary: never copy model fields or exception text.
VALIDATION_REASONS = frozenset({
    'review_object', 'scope', 'target_keyword', 'sources_list', 'facets_list',
    'relevance_object', 'source_index', 'source_quote', 'source_entity',
    'source_context', 'source_duplicate', 'source_coverage', 'facet_quote',
    'facet_text', 'facet_answer', 'facet_supported', 'relevance_quote',
    'relevance_kind', 'event_start', 'event_end', 'date_quote',
    'quote_index', 'quote_conflict', 'response_size',
})


class SchemaValidationError(ValueError):
    def __init__(self, reason, row_index=None):
        self.detail = {'reason': reason if isinstance(reason, str) and reason in VALIDATION_REASONS
                       else 'invalid_value'}
        if type(row_index) is int and 0 <= row_index < 8:
            self.detail['row_index'] = row_index
        super().__init__('invalid_schema')


class AnalysisError(RuntimeError):
    def __init__(self, code, attempts=(), *, validation=None):
        self.code = code if code in CODES else 'unexpected_error'
        self.attempts = list(attempts)
        self.validation = validation
        super().__init__(self.code)


def error_code(error):
    if isinstance(error, AnalysisError):
        return error.code
    if isinstance(error, (CodexRequestError, CodexResponseError)):
        return error.reason if error.reason in CODES else 'unclassified'
    try:
        from src.codex_search import NativeSearchError
    except ImportError:
        pass  # An unavailable adapter must not break error reporting itself.
    else:
        if isinstance(error, NativeSearchError):
            return error.reason if error.reason in CODES else 'unclassified'
    if isinstance(error, json.JSONDecodeError):
        return 'invalid_json'
    if isinstance(error, TimeoutError):
        return 'timeout'
    return 'unexpected_error'


def parse_json(raw):
    if not isinstance(raw, str) or len(raw) > 100_000:
        raise AnalysisError('invalid_json')
    return json.loads(re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip()))


def stage(name):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            token = _STAGE.set(name)
            try:
                return fn(*args, **kwargs)
            finally:
                _STAGE.reset(token)
        return wrapped
    return decorate


def can_retry():
    state, operation = _STATE.get(), _OPERATION.get()
    if operation is not None and operation['extra_calls'] >= 1:
        return False
    if state is not None:
        if state['fatal'] or state['extra_calls'] >= MAX_EXTRA_CALLS or monotonic() >= state['deadline']:
            return False
        state['extra_calls'] += 1
    if operation is not None:
        operation['extra_calls'] += 1
    return True


def operation_budget(fn):
    """Transport and schema wrappers share one extra call, even when nested."""
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if _OPERATION.get() is not None:
            return fn(*args, **kwargs)
        token = _OPERATION.set({'extra_calls': 0})
        try:
            return fn(*args, **kwargs)
        finally:
            _OPERATION.reset(token)
    return wrapped


@operation_budget

def validated_call(call, prompt, validate=lambda value: value, *, label=None):
    """At most two calls on identical evidence. Never retry a valid negative verdict.

    Nested validators share a four-extra-call selection budget. Only fixed codes,
    durations and stage names enter logs; no prompt, exception text or response.
    """
    attempts = []
    name = label or _STAGE.get()
    state = _STATE.get()
    request_prompt = prompt
    for index in range(2):
        started = monotonic()
        try:
            if state and state['fatal']:
                raise AnalysisError(state['fatal'])
            raw = call(request_prompt)
            try:
                value = validate(raw)
            except AnalysisError:
                raise
            except SchemaValidationError as error:
                raise AnalysisError('invalid_schema', validation=error.detail) from None
            except json.JSONDecodeError:
                raise AnalysisError('invalid_json') from None
            except (ValueError, TypeError, KeyError, OverflowError, AttributeError):
                raise AnalysisError('invalid_schema') from None
        except Exception as error:
            code = error_code(error)
            event = {'stage': name, 'attempt': index + 1, 'status': 'error', 'code': code,
                     'elapsed_ms': round((monotonic() - started) * 1000)}
            detail = getattr(error, 'validation', None)
            if (isinstance(detail, dict) and isinstance(detail.get('reason'), str)
                    and detail['reason'] in VALIDATION_REASONS | {'invalid_value'}):
                safe_detail = {'reason': detail['reason']}
                row = detail.get('row_index')
                if type(row) is int and 0 <= row < 8:
                    safe_detail['row_index'] = row
                event['validation'] = safe_detail
                request_prompt = prompt + '\n검증 오류(고정 코드): ' + json.dumps(safe_detail) + (
                    '\n해당 항목을 입력 원문과 스키마에 맞게 수정해 전체 JSON을 다시 반환하세요. '
                    '근거와 부정 판정은 바꾸지 마세요. 인용은 원문의 구절 번호를 선택하세요.')
            attempts.append(event)
            if state is not None:
                state['events'].append(event)
                if code in FATAL:
                    state['fatal'] = code
            log.warning('analysis_attempt %s', json.dumps(event))
            # An inner bounded call already exhausted its recovery; never multiply it.
            if (index == 0 and code in RETRYABLE and not isinstance(error, AnalysisError)
                    and can_retry()):
                sleep(1 if code in {'timeout', 'network_or_service'} else 0)
                continue
            # Validation errors are ours and can use the same bounded retry.
            if index == 0 and code in {'invalid_json', 'invalid_schema'} and not getattr(error, 'attempts', ()) and can_retry():
                continue
            raise AnalysisError(code, attempts) from None
        event = {'stage': name, 'attempt': index + 1, 'status': 'returned',
                 'elapsed_ms': round((monotonic() - started) * 1000)}
        attempts.append(event)
        if state is not None:
            state['events'].append(event)
        return value


def raise_if_fatal():
    state = _STATE.get()
    if state and state['fatal']:
        raise AnalysisError(state['fatal'])


def selection_scope(fn):
    @wraps(fn)
    def wrapped(category, *args, **kwargs):
        state = {'events': [], 'extra_calls': 0, 'fatal': None, 'deadline': monotonic() + 25 * 60}
        token = _STATE.set(state)
        stage_token = _STAGE.set('shortlist')
        try:
            try:
                report = fn(category, *args, **kwargs)
            except AnalysisError as error:
                report = {'category': category, 'selected_at': datetime.now(timezone.utc).isoformat(),
                          'selected': [], 'held': [], 'rejected': [],
                          'failure_history': kwargs.get('failure_history') or [],
                          'research_stop_reason': 'analysis_unavailable', 'operational_error': error.code}
            report['analysis_diagnostics'] = state['events']
            report['analysis_recovery_attempts'] = state['extra_calls']
            if state['fatal']:
                report.update(selected=[], research_stop_reason='analysis_unavailable',
                              operational_error=state['fatal'])
            return report
        finally:
            _STAGE.reset(stage_token)
            _STATE.reset(token)
    return wrapped
