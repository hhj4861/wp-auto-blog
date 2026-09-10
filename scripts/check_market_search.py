"""Probe existing search providers without exposing results or publishing anything."""
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import market_search
from src.market_opportunity import MIN_DOMAINS, MIN_RESULTS, PROVIDERS, compact, sample_rows


# These are fixed probes, not new topic candidates or evidence for publication.
CASES = (
    ('ITQ자격증조회', (('itq',), ('조회', '확인', '발급'))),
    ('종합소득세기한후신고환급', (('종합소득세', '종소세'), ('기한후',), ('환급',))),
    ('대장내시경전음식', (('대장내시경',), ('음식', '식사', '식단', '금식', '섭취', '먹'))),
)
FAILURE_REASONS = frozenset({
    'api_not_enabled', 'api_key_service_blocked', 'api_key_restricted', 'api_key_invalid',
    'daily_quota_exceeded', 'rate_limit_exceeded', 'quota_exceeded', 'api_access_unavailable',
    'configuration_missing', 'network_error', 'http_or_response_error', 'no_results', 'challenge',
})
FAILURE_TEMPLATE = 'Search unavailable: provider=%s reason=%s http_status=%s'


class _Failures(logging.Handler):
    """Retain only a known event's enum values, never format arbitrary log text."""

    def __init__(self):
        super().__init__()
        self.items = []

    def emit(self, record):
        if record.msg != FAILURE_TEMPLATE or not isinstance(record.args, tuple) or len(record.args) != 3:
            return
        provider, reason, status = record.args
        if not isinstance(provider, str) or provider not in PROVIDERS:
            provider = 'unknown'
        if not isinstance(reason, str) or reason not in FAILURE_REASONS:
            reason = 'unclassified_failure'
        status = status if type(status) is int and 100 <= status <= 599 else None
        self.items.append({'provider': provider, 'reason': reason, 'http_status': status})


@contextmanager
def _safe_search_logs():
    """Isolate provider warnings and silence HTTP debug URLs for this small probe."""
    logger = market_search.logger
    original = (logger.handlers[:], logger.propagate, logger.level, logger.disabled)
    handler = _Failures()
    noisy = [logging.getLogger(name) for name in ('requests', 'urllib3', 'urllib3.connectionpool')]
    levels = [item.level for item in noisy]
    try:
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.WARNING)
        logger.disabled = False
        for item in noisy:
            item.setLevel(logging.CRITICAL + 1)
        yield handler.items
    finally:
        logger.handlers, logger.propagate, level, logger.disabled = original
        logger.setLevel(level)
        for item, level in zip(noisy, levels):
            item.setLevel(level)
        handler.close()


def probe_case(case_number, query, groups, credential_source='current'):
    report = {'case': case_number, 'credential_source': credential_source,
              'provider': 'unknown', 'row_count': 0,
              'sample_row_count': 0, 'distinct_domains': 0, 'approximate_related_rows': 0,
              'reason': 'search_error', 'failures': []}
    with _safe_search_logs() as failures:
        try:
            provider, results = market_search.search_results(query)
            if not isinstance(provider, str) or provider not in PROVIDERS:
                report['reason'] = 'unexpected_provider'
                return report
            report['provider'] = provider
            if not isinstance(results, list):
                report['reason'] = 'invalid_result_shape'
                return report
            rows = sample_rows(results)
            report.update(row_count=len(results), sample_row_count=len(rows),
                          distinct_domains=len({row['domain'] for _, row in rows}))
            for _, row in rows:
                text = compact(row['title'] + ' ' + row['snippet'])
                if all(any(compact(term) in text for term in group) for group in groups):
                    report['approximate_related_rows'] += 1
            if not rows:
                report['reason'] = 'empty_results'
            elif len(rows) < MIN_RESULTS or report['distinct_domains'] < MIN_DOMAINS:
                report['reason'] = 'insufficient_search_sample'
            elif not report['approximate_related_rows']:
                report['reason'] = 'no_keyword_overlap'
            else:
                report['reason'] = 'ok'
        except Exception:
            # Request exceptions may embed credential-bearing URLs and response bodies.
            report['reason'] = 'search_error'
        finally:
            report['failures'] = failures[:10]
    return report


def main():
    reports = [probe_case(index, query, groups)
               for index, (query, groups) in enumerate(CASES, 1)]
    current_ok = all(report['reason'] == 'ok' for report in reports)
    alternate = os.environ.get('GOOGLE_SEARCH_ALTERNATE_API_KEY')
    if not current_ok and alternate:
        original = os.environ.get('GOOGLE_SEARCH_API_KEY')
        try:
            os.environ['GOOGLE_SEARCH_API_KEY'] = alternate
            reports.append(probe_case(1, *CASES[0], credential_source='alternate'))
        finally:
            if original is None:
                os.environ.pop('GOOGLE_SEARCH_API_KEY', None)
            else:
                os.environ['GOOGLE_SEARCH_API_KEY'] = original
    for report in reports:
        print(json.dumps(report, sort_keys=True))
    # This verifies a usable sample, not ranking, traffic, or a full intent review.
    return 0 if current_ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
