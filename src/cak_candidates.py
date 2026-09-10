"""Validate the measured CAK JSON boundary without querying either producer or API."""

from datetime import date, datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo


MAX_ITEMS = 80
MAX_FILE_BYTES = 2_000_000
KST = ZoneInfo('Asia/Seoul')
SCOPE_COUNTS = ('requestedKeywordCount', 'storedKeywordCount', 'eligibleDailyCount',
                'exportedCount', 'truncatedCount')
EXCLUSION_COUNTS = ('expired', 'unknownTimeUnit', 'nonDaily', 'invalidSeries',
                    'missingPreviousDay', 'insufficientBaseline')
FAILURE_CODES = {'credentials_missing', 'http_unauthorized', 'http_forbidden', 'rate_limited',
                 'http_server', 'http_client', 'network', 'schema_invalid', 'unclassified'}
TRANSPORT_STATUSES = {'ok', 'empty', 'unavailable', 'stale', 'malformed'}
TRANSPORT_REASONS = {'downloaded', 'no_token', 'no_recent_run', 'no_artifact', 'artifact_expired',
                     'api_unauthorized', 'api_forbidden',
                     'api_unavailable', 'download_failed', 'untrusted_redirect', 'artifact_too_large',
                     'invalid_archive', 'digest_mismatch', 'invalid_payload', 'write_failed'}
TREND_FIELDS = ('source', 'timeUnit', 'timeUnitOrigin', 'startDate', 'endDate', 'latestPeriod',
                'previousPeriod', 'baselineStart', 'baselineEnd', 'latestRatio', 'previousRatio',
                'baselineMean', 'expectedBaselineDays', 'observedBaselineDays', 'dayPct',
                'baselinePct', 'dayPctStatus', 'baselinePctStatus', 'hotScore', 'calculationVersion')
SEARCHAD_FIELDS = ('attemptedAt', 'measuredAt', 'lookupStatus', 'matchMode', 'matchedKeyword',
                   'monthlyPc', 'monthlyMobile', 'monthlyTotal', 'monthlyPcStatus',
                   'monthlyMobileStatus', 'monthlyTotalStatus', 'advertisingCompetition', 'failureCode')


class InvalidCandidate(ValueError):
    """Only fixed classifications may appear in import diagnostics."""


def measurement_key(keyword):
    """SearchAd's exact match removes whitespace only, including no year folding."""
    return re.sub(r'\s+', '', keyword)


def _require(condition, reason):
    if not condition:
        raise InvalidCandidate(reason)


def _timestamp(value):
    _require(isinstance(value, str), 'invalid_timestamp')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, 'invalid_timestamp')
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise InvalidCandidate('invalid_timestamp') from None


def _date(value):
    _require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value), 'invalid_trend_dates')
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise InvalidCandidate('invalid_trend_dates') from None


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _metadata(payload, now, item_count=None):
    _require(isinstance(payload, dict), 'invalid_envelope')
    _require(type(payload.get('schemaVersion')) is int and payload['schemaVersion'] == 1
             and payload.get('kind') == 'cak_keyword_candidates'
             and payload.get('profile') == 'blog-kr', 'unsupported_schema')
    compliance = payload.get('compliance')
    _require(isinstance(compliance, dict) and compliance.get('resaleRestricted') is True,
             'invalid_compliance')
    ttl = compliance.get('cacheTtlHours')
    _require(_integer(ttl, 1) and ttl <= 24, 'invalid_compliance')
    scope = payload.get('scope')
    _require(isinstance(scope, dict) and scope.get('seedSet') == 'g2-seeds'
             and all(_integer(scope.get(key)) for key in SCOPE_COUNTS), 'invalid_scope')
    _require(scope['requestedKeywordCount'] >= scope['storedKeywordCount'] >= scope['eligibleDailyCount']
             and scope['exportedCount'] <= MAX_ITEMS
             and scope['eligibleDailyCount'] == scope['exportedCount'] + scope['truncatedCount'],
             'invalid_scope')
    if item_count is not None:
        _require(scope['exportedCount'] == item_count, 'invalid_scope')
    exclusions = payload.get('exclusionCounts')
    _require(isinstance(exclusions, dict)
             and all(_integer(exclusions.get(key)) for key in EXCLUSION_COUNTS), 'invalid_exclusion_counts')
    generated, expires = _timestamp(payload.get('generatedAt')), _timestamp(payload.get('expiresAt'))
    _require(timedelta(0) <= now - generated <= timedelta(hours=ttl), 'stale_export')
    _require(generated < expires <= generated + timedelta(hours=ttl), 'invalid_export_expiry')
    _require(now < expires, 'stale_export')
    return {'schemaVersion': 1, 'kind': 'cak_keyword_candidates', 'profile': 'blog-kr',
            'generatedAt': payload['generatedAt'], 'expiresAt': payload['expiresAt'],
            'compliance': {'resaleRestricted': True, 'cacheTtlHours': ttl},
            'scope': {'seedSet': 'g2-seeds', **{key: scope[key] for key in SCOPE_COUNTS}},
            'exclusionCounts': {key: exclusions[key] for key in EXCLUSION_COUNTS}}


def _item(raw, metadata, now):
    _require(isinstance(raw, dict), 'invalid_item')
    keyword = raw.get('keyword')
    _require(isinstance(keyword, str) and 0 < len(keyword) <= 100 and bool(measurement_key(keyword)),
             'invalid_keyword')
    ttl = timedelta(hours=metadata['compliance']['cacheTtlHours'])
    generated = _timestamp(metadata['generatedAt'])
    captured, expires = _timestamp(raw.get('capturedAt')), _timestamp(raw.get('expiresAt'))
    _require(timedelta(0) <= now - captured <= ttl and captured <= generated, 'stale_signal')
    _require(captured < expires <= captured + ttl and now < expires, 'stale_signal')
    _require(_timestamp(metadata['expiresAt']) <= expires, 'inconsistent_expiry')
    trend = raw.get('trend')
    _require(isinstance(trend, dict) and all(key in trend for key in TREND_FIELDS), 'invalid_trend')
    _require(trend['source'] == 'naver_datalab_search' and trend['timeUnit'] == 'date'
             and trend['timeUnitOrigin'] == 'provider_response'
             and trend['calculationVersion'] == 'daily_observed_v2', 'unsupported_trend')
    days = {key: _date(trend[key]) for key in
            ('startDate', 'endDate', 'latestPeriod', 'previousPeriod', 'baselineStart', 'baselineEnd')}
    latest = days['latestPeriod']
    _require(days['startDate'] <= days['baselineStart'] == latest - timedelta(days=7)
             and days['previousPeriod'] == days['baselineEnd'] == latest - timedelta(days=1)
             and latest <= days['endDate'] <= captured.astimezone(KST).date(), 'invalid_trend_dates')
    _require(0 <= (now.astimezone(KST).date() - latest).days <= 3, 'stale_trend')
    _require(type(trend['expectedBaselineDays']) is int and trend['expectedBaselineDays'] == 7
             and _integer(trend['observedBaselineDays']) and 5 <= trend['observedBaselineDays'] <= 7,
             'insufficient_baseline')
    _require(all(_number(trend[key]) and 0 <= trend[key] <= 100
                 for key in ('latestRatio', 'previousRatio', 'baselineMean')), 'invalid_ratio')
    for percent, status, denominator in (('dayPct', 'dayPctStatus', 'previousRatio'),
                                         ('baselinePct', 'baselinePctStatus', 'baselineMean')):
        baseline = trend[denominator]
        if baseline == 0:
            _require(trend[status] == 'zero_baseline' and trend[percent] is None, 'inconsistent_growth')
        else:
            expected = (trend['latestRatio'] / baseline - 1) * 100
            _require(trend[status] == 'measured' and _number(trend[percent])
                     and math.isclose(trend[percent], expected, rel_tol=1e-9, abs_tol=1e-7),
                     'inconsistent_growth')
    if trend['previousRatio'] == 0 or trend['baselineMean'] == 0:
        _require(trend['hotScore'] is None, 'inconsistent_hot_score')
    else:
        hot = (min(300, max(0, trend['baselinePct'])) / 300 * 55
               + min(300, max(0, trend['dayPct'])) / 300 * 30 + trend['latestRatio'] / 100 * 15)
        _require(_number(trend['hotScore']) and 0 <= trend['hotScore'] <= 100
                 and trend['hotScore'] == math.floor(hot + 0.5), 'inconsistent_hot_score')
    ad = raw.get('searchad')
    _require(isinstance(ad, dict) and all(key in ad for key in SEARCHAD_FIELDS), 'invalid_searchad')
    _require(ad['lookupStatus'] in ('exact', 'no_exact_match', 'failed', 'not_configured')
             and ad['matchMode'] == 'whitespace_exact', 'invalid_searchad')
    _require(ad['advertisingCompetition'] in ('low', 'mid', 'high', None)
             and (ad['failureCode'] is None or ad['failureCode'] in FAILURE_CODES), 'invalid_searchad')
    attempted = _timestamp(ad['attemptedAt'])
    _require(timedelta(0) <= now - attempted <= ttl and attempted <= generated, 'stale_monthly')
    if ad['lookupStatus'] == 'exact':
        _require(isinstance(ad['matchedKeyword'], str)
                 and measurement_key(ad['matchedKeyword']) == measurement_key(keyword), 'monthly_keyword_mismatch')
        measured = _timestamp(ad['measuredAt'])
        _require(attempted <= measured <= generated and timedelta(0) <= now - measured <= ttl,
                 'stale_monthly')
        _require(ad['failureCode'] is None, 'invalid_searchad')
    else:
        _require(ad['measuredAt'] is None and ad['matchedKeyword'] is None, 'invalid_searchad')
        _require((ad['lookupStatus'] == 'not_configured' and ad['failureCode'] == 'credentials_missing')
                 or (ad['lookupStatus'] == 'no_exact_match' and ad['failureCode'] is None)
                 or (ad['lookupStatus'] == 'failed' and ad['failureCode'] in FAILURE_CODES), 'invalid_searchad')
    for device in ('monthlyPc', 'monthlyMobile'):
        status = ad[device + 'Status']
        _require(status in ('measured', 'masked', 'missing', 'invalid'), 'invalid_monthly')
        _require((_integer(ad[device]) if status == 'measured' else ad[device] is None), 'invalid_monthly')
        _require(ad['lookupStatus'] == 'exact' or ad[device] is None, 'invalid_monthly')
    complete = ad['lookupStatus'] == 'exact' and all(ad[key + 'Status'] == 'measured'
                                                  for key in ('monthlyPc', 'monthlyMobile'))
    if complete:
        _require(ad['monthlyTotalStatus'] == 'measured' and _integer(ad['monthlyTotal'])
                 and ad['monthlyTotal'] == ad['monthlyPc'] + ad['monthlyMobile'], 'inconsistent_monthly_total')
    else:
        _require(ad['monthlyTotalStatus'] == 'unavailable' and ad['monthlyTotal'] is None,
                 'inconsistent_monthly_total')
    return {'keyword': keyword, 'capturedAt': raw['capturedAt'], 'expiresAt': raw['expiresAt'],
            'trend': {key: trend[key] for key in TREND_FIELDS},
            'searchad': {key: ad[key] for key in SEARCHAD_FIELDS}}


def qualified_rising(item):
    ad, trend = item['searchad'], item['trend']
    return (ad['monthlyTotalStatus'] == 'measured' and ad['monthlyTotal'] >= 1000
            and trend['hotScore'] is not None and trend['hotScore'] >= 20
            and trend['dayPctStatus'] == trend['baselinePctStatus'] == 'measured'
            and trend['dayPct'] > 0 and trend['baselinePct'] > 0)


def _safe_transport(raw):
    _require(isinstance(raw, dict) and raw.get('status') in TRANSPORT_STATUSES
             and raw.get('reason') in TRANSPORT_REASONS, 'invalid_transport')
    result = {'status': raw['status'], 'reason': raw['reason']}
    for key in ('sourceRunId', 'artifactId'):
        if key in raw:
            _require(_integer(raw[key], 1), 'invalid_transport')
            result[key] = raw[key]
    if 'headSha' in raw:
        _require(isinstance(raw['headSha'], str) and re.fullmatch(r'[a-fA-F0-9]{40}', raw['headSha']),
                 'invalid_transport')
        result['headSha'] = raw['headSha'].lower()
    if 'sourceRunCreatedAt' in raw:
        _timestamp(raw['sourceRunCreatedAt'])
        result['sourceRunCreatedAt'] = raw['sourceRunCreatedAt']
    return result


def _transport_diagnostics():
    path = os.getenv('CAK_KEYWORD_CANDIDATES_FETCH_STATUS_FILE')
    if not path:
        return None
    try:
        source = Path(path)
        _require(source.stat().st_size <= 16_384, 'invalid_transport')
        return _safe_transport(json.loads(source.read_text(encoding='utf-8')))
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        return {'status': 'malformed', 'reason': 'invalid_payload'}


def load_candidate_export(path, now=None):
    """Return validated items and fixed diagnostics; an optional feed never replaces evergreen."""
    now = now or datetime.now(timezone.utc)
    diagnostics = {'status': 'not_configured', 'reason': None, 'received_count': 0,
                   'validated_count': 0, 'rejected_count': 0, 'qualified_rising_count': 0,
                   'monthly_unavailable_count': 0, 'rejection_counts': {}}
    transport = _transport_diagnostics()
    if transport is not None:
        diagnostics['transport'] = transport
    if not path:
        return [], diagnostics
    try:
        source = Path(path)
        _require(source.stat().st_size <= MAX_FILE_BYTES, 'file_too_large')
        payload = json.loads(source.read_text(encoding='utf-8'),
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        _require(isinstance(payload, dict) and isinstance(payload.get('items'), list), 'invalid_envelope')
        items = payload['items']
        diagnostics['received_count'] = len(items)
        _require(len(items) <= MAX_ITEMS, 'too_many_items')
        metadata = _metadata(payload, now, len(items))
        diagnostics['export_metadata'] = metadata
        validated, seen = [], set()
        for raw in items:
            try:
                item = _item(raw, metadata, now)
                key = measurement_key(item['keyword'])
                _require(key not in seen, 'duplicate_keyword')
                seen.add(key)
                validated.append(item)
            except (InvalidCandidate, TypeError, KeyError, OverflowError) as exc:
                reason = str(exc) if isinstance(exc, InvalidCandidate) else 'invalid_item'
                counts = diagnostics['rejection_counts']
                counts[reason] = counts.get(reason, 0) + 1
        diagnostics.update(validated_count=len(validated), rejected_count=len(items) - len(validated),
                           qualified_rising_count=sum(qualified_rising(item) for item in validated),
                           monthly_unavailable_count=sum(item['searchad']['monthlyTotalStatus'] != 'measured'
                                                         for item in validated))
        diagnostics['status'] = ('empty' if not items else 'ok' if len(validated) == len(items)
                                 else 'partial' if validated else 'invalid')
        if items and not validated:
            diagnostics['reason'] = 'no_valid_items'
        return validated, diagnostics
    except FileNotFoundError:
        diagnostics.update(status='missing', reason='file_missing')
    except InvalidCandidate as exc:
        reason = str(exc)
        diagnostics.update(status='stale' if reason == 'stale_export' else 'invalid', reason=reason)
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        diagnostics.update(status='invalid', reason='unreadable_export')
    return [], diagnostics


def valid_cak_provenance(provenance, keyword, monthly, now=None):
    """Recheck original clocks and measurement identity before cached publication."""
    now = now or datetime.now(timezone.utc)
    try:
        _require(isinstance(provenance, dict), 'invalid_provenance')
        metadata = _metadata(provenance['export'], now)
        item = _item(provenance['item'], metadata, now)
        if 'transport' in provenance:
            _safe_transport(provenance['transport'])
        relationship = provenance['relationship']
        _require(relationship in ('exact', 'related_seed'), 'invalid_provenance')
        if relationship == 'exact':
            return (measurement_key(keyword) == measurement_key(item['keyword'])
                    and monthly == item['searchad']['monthlyTotal']
                    and item['searchad']['monthlyTotalStatus'] == 'measured')
        measured = _timestamp(provenance['relatedMeasuredAt'])
        return (qualified_rising(item) and measurement_key(keyword) != measurement_key(item['keyword'])
                and measurement_key(keyword) == measurement_key(provenance['relatedKeyword'])
                and monthly == provenance['relatedMonthly'] and _integer(monthly, 500)
                and timedelta(0) <= now - measured <= timedelta(hours=metadata['compliance']['cacheTtlHours']))
    except (InvalidCandidate, KeyError, TypeError, ValueError, OverflowError):
        return False
