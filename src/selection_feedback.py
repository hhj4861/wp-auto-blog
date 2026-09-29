"""Bounded, category-local retry memory. Never grants publication eligibility."""
from datetime import datetime, timedelta

from src.cak_candidates import measurement_key


RETRY_HOURS = {'temporary_failure': 6, 'search_quality': 24,
               'source_coverage': 72, 'intent_mismatch': 168}
RETENTION_DAYS = 30
MAX_HISTORY = 600


def _date(value):
    try:
        result = datetime.fromisoformat(value)
        return result if result.utcoffset() is not None else None
    except (TypeError, ValueError):
        return None


def failure_code(row):
    """Use fixed diagnostics, never copy provider/model free text into memory."""
    reason = row.get('reason', '')
    reason = reason if isinstance(reason, str) else ''
    holds = row.get('hold_reasons', [])
    holds = set(x for x in holds if isinstance(x, str)) if isinstance(holds, list) else set()
    if holds & {'narrower_or_unverified_search_intent', 'interactive_tool_required'}:
        return 'intent_mismatch'
    if holds & {'narrower_source_coverage', 'unverified_source_coverage'}:
        return 'source_coverage'
    if reason == 'search quality insufficient':
        return 'search_quality'
    if reason == 'search intent or official evidence does not support an article':
        diagnostic = row.get('decision_diagnostics', {})
        opinion = diagnostic.get('model_rejection_opinion', {}) if isinstance(diagnostic, dict) else {}
        code = opinion.get('code') if isinstance(opinion, dict) else None
        code = code if isinstance(code, str) else None
        if code in {'keyword_navigation', 'insufficient_search_intent', 'category_mismatch'}:
            return 'intent_mismatch'
        if code in {'source_navigation', 'source_missing_detail', 'unsupported_claim', 'expired_information'}:
            return 'source_coverage'
        return 'temporary_failure'
    if (holds or reason in {'no accessible official source supports topic',
                           'search relevance review unavailable', 'invalid evidence-backed article plan',
                           'expired or invalid deadline',
                           'organic lookup unavailable; requires a specific measured long-tail'}
            or (isinstance(reason, str) and reason.startswith('codex web research unavailable:'))):
        return 'temporary_failure'
    # Invalid proposals and published duplicates are not new keyword failures.
    return None


def load_history(report, category, now):
    """Import legacy held/rejected rows once, keeping prior untouched timestamps."""
    if not isinstance(report, dict) or report.get('category') != category:
        return []
    rows = {}
    history = report.get('failure_history', [])
    for row in history if isinstance(history, list) else []:
        if not isinstance(row, dict):
            continue
        keyword, code = row.get('keyword'), row.get('reason_code')
        failed, retry = _date(row.get('failed_at')), _date(row.get('retry_after'))
        attempts = row.get('attempts')
        if (not isinstance(keyword, str) or not measurement_key(keyword)
                or not isinstance(code, str) or code not in RETRY_HOURS
                or failed is None or retry is None
                or not now - timedelta(days=RETENTION_DAYS) <= failed <= now
                or retry != failed + timedelta(hours=RETRY_HOURS[code])
                or type(attempts) is not int or not 1 <= attempts <= 1000):
            continue
        key = measurement_key(keyword)
        if key not in rows or failed > _date(rows[key]['failed_at']):
            rows[key] = {k: row[k] for k in
                         ('keyword', 'reason_code', 'failed_at', 'retry_after', 'attempts')}
    attempted_at = _date(report.get('selected_at'))
    if attempted_at is not None and now - timedelta(days=RETENTION_DAYS) <= attempted_at <= now:
        for status in ('held', 'rejected'):
            candidates = report.get(status, [])
            for row in candidates if isinstance(candidates, list) else []:
                if not isinstance(row, dict):
                    continue
                keyword, code = row.get('keyword'), failure_code(row)
                if not isinstance(keyword, str) or not measurement_key(keyword) or code is None:
                    continue
                key = measurement_key(keyword)
                old = rows.get(key)
                if old and _date(old['failed_at']) >= attempted_at:
                    continue
                rows[key] = {'keyword': keyword, 'reason_code': code,
                             'failed_at': attempted_at.isoformat(),
                             'retry_after': (attempted_at + timedelta(hours=RETRY_HOURS[code])).isoformat(),
                             'attempts': min(1000, old['attempts'] + 1) if old else 1}
        for status in ('selected', 'ranked_candidates'):
            candidates = report.get(status, [])
            for row in candidates if isinstance(candidates, list) else []:
                if isinstance(row, dict) and isinstance(row.get('keyword'), str):
                    key = measurement_key(row['keyword'])
                    if key in rows and _date(rows[key]['failed_at']) <= attempted_at:
                        del rows[key]
    return sorted(rows.values(), key=lambda row: _date(row['failed_at']), reverse=True)[:MAX_HISTORY]


def deferred_keywords(history, now):
    return {measurement_key(row['keyword']) for row in history
            if _date(row['retry_after']) > now}
