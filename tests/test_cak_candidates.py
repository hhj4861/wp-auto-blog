from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import math

import pytest

from src import cak_candidates as cak


NOW = datetime(2026, 9, 10, 3, tzinfo=timezone.utc)


def make_item(keyword='혈당관리방법', *, now=NOW, monthly=1200, latest_day=None,
              latest_ratio=60, previous_ratio=20, baseline_mean=20):
    latest = latest_day or (now.astimezone(cak.KST).date() - timedelta(days=1))
    day_pct = (latest_ratio / previous_ratio - 1) * 100 if previous_ratio else None
    baseline_pct = (latest_ratio / baseline_mean - 1) * 100 if baseline_mean else None
    hot = (None if day_pct is None or baseline_pct is None else math.floor(
        min(300, max(0, baseline_pct)) / 300 * 55
        + min(300, max(0, day_pct)) / 300 * 30 + latest_ratio / 100 * 15 + 0.5))
    captured = now - timedelta(hours=2)
    return {
        'keyword': keyword, 'capturedAt': captured.isoformat(),
        'expiresAt': (captured + timedelta(hours=24)).isoformat(),
        'trend': {
            'source': 'naver_datalab_search', 'timeUnit': 'date', 'timeUnitOrigin': 'provider_response',
            'startDate': (latest - timedelta(days=13)).isoformat(),
            'endDate': captured.astimezone(cak.KST).date().isoformat(),
            'latestPeriod': latest.isoformat(), 'previousPeriod': (latest - timedelta(days=1)).isoformat(),
            'baselineStart': (latest - timedelta(days=7)).isoformat(),
            'baselineEnd': (latest - timedelta(days=1)).isoformat(),
            'latestRatio': latest_ratio, 'previousRatio': previous_ratio, 'baselineMean': baseline_mean,
            'expectedBaselineDays': 7, 'observedBaselineDays': 5,
            'dayPct': day_pct, 'baselinePct': baseline_pct,
            'dayPctStatus': 'measured' if previous_ratio else 'zero_baseline',
            'baselinePctStatus': 'measured' if baseline_mean else 'zero_baseline',
            'hotScore': hot, 'calculationVersion': 'daily_observed_v2',
        },
        'searchad': {
            'attemptedAt': (now - timedelta(hours=1)).isoformat(),
            'measuredAt': (now - timedelta(minutes=59)).isoformat(), 'lookupStatus': 'exact',
            'matchMode': 'whitespace_exact', 'matchedKeyword': keyword,
            'monthlyPc': 100, 'monthlyMobile': monthly - 100, 'monthlyTotal': monthly,
            'monthlyPcStatus': 'measured', 'monthlyMobileStatus': 'measured', 'monthlyTotalStatus': 'measured',
            'advertisingCompetition': 'high', 'failureCode': None,
        },
    }


def make_export(items=None, *, now=NOW, ttl=24):
    items = deepcopy(items) if items is not None else [make_item(now=now)]
    generated = now - timedelta(minutes=30)
    for item in items:
        cap = datetime.fromisoformat(item['capturedAt']) + timedelta(hours=ttl)
        item['expiresAt'] = min(datetime.fromisoformat(item['expiresAt']), cap).isoformat()
    expires = min((datetime.fromisoformat(item['expiresAt']) for item in items),
                  default=generated + timedelta(hours=ttl))
    return {'schemaVersion': 1, 'kind': 'cak_keyword_candidates', 'profile': 'blog-kr',
            'generatedAt': generated.isoformat(), 'expiresAt': expires.isoformat(),
            'compliance': {'resaleRestricted': True, 'cacheTtlHours': ttl},
            'scope': {'seedSet': 'g2-seeds', 'requestedKeywordCount': len(items),
                      'storedKeywordCount': len(items), 'eligibleDailyCount': len(items),
                      'exportedCount': len(items), 'truncatedCount': 0},
            'exclusionCounts': {key: 0 for key in cak.EXCLUSION_COUNTS}, 'items': items}


@pytest.fixture(autouse=True)
def no_inherited_transport(monkeypatch):
    monkeypatch.delenv('CAK_KEYWORD_CANDIDATES_FETCH_STATUS_FILE', raising=False)


def write_export(tmp_path, payload):
    path = tmp_path / 'candidates.json'
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    return path


def test_valid_daily_export_preserves_original_measurements_and_clocks(tmp_path):
    payload = make_export()
    items, diagnostics = cak.load_candidate_export(write_export(tmp_path, payload), NOW)
    assert items == payload['items']
    assert diagnostics['status'] == 'ok'
    assert diagnostics['validated_count'] == diagnostics['qualified_rising_count'] == 1
    assert diagnostics['export_metadata']['generatedAt'] == payload['generatedAt']
    assert items[0]['trend']['observedBaselineDays'] == 5
    assert items[0]['trend']['baselineMean'] == 20
    assert items[0]['trend']['hotScore'] == 66


@pytest.mark.parametrize('size,accepted', [(80, True), (81, False)])
def test_export_item_limit(tmp_path, size, accepted):
    payload = make_export([make_item(f'혈당관리방법{i}') for i in range(size)])
    items, diagnostics = cak.load_candidate_export(write_export(tmp_path, payload), NOW)
    assert len(items) == (size if accepted else 0)
    assert diagnostics['status'] == ('ok' if accepted else 'invalid')
    if not accepted:
        assert diagnostics['reason'] == 'too_many_items'


@pytest.mark.parametrize('mutate,reason', [
    (lambda item: item['trend'].update(timeUnit='week'), 'unsupported_trend'),
    (lambda item: item['trend'].pop('timeUnitOrigin'), 'invalid_trend'),
    (lambda item: item['trend'].update(observedBaselineDays=4), 'insufficient_baseline'),
    (lambda item: item['trend'].update(previousPeriod='2026-09-07'), 'invalid_trend_dates'),
    (lambda item: item['trend'].update(dayPct=300), 'inconsistent_growth'),
    (lambda item: item['trend'].update(baselinePct=None), 'inconsistent_growth'),
    (lambda item: item['trend'].update(hotScore=99), 'inconsistent_hot_score'),
    (lambda item: item['trend'].update(latestRatio=True), 'invalid_ratio'),
    (lambda item: item['searchad'].update(monthlyTotal=1300), 'inconsistent_monthly_total'),
    (lambda item: item['searchad'].update(monthlyPc=True), 'invalid_monthly'),
    (lambda item: item['searchad'].update(measuredAt=None), 'invalid_timestamp'),
    (lambda item: item['searchad'].update(matchedKeyword='혈당관리방법효과'), 'monthly_keyword_mismatch'),
])
def test_inconsistent_or_unverified_metrics_are_excluded(tmp_path, monkeypatch, mutate, reason):
    payload = make_export()
    mutate(payload['items'][0])
    monkeypatch.setenv('TREND_TIME_UNIT', 'date')
    items, diagnostics = cak.load_candidate_export(write_export(tmp_path, payload), NOW)
    assert items == []
    assert diagnostics['rejection_counts'] == {reason: 1}


def test_masked_monthly_value_stays_visible_without_becoming_zero_demand(tmp_path):
    payload = make_export()
    payload['items'][0]['searchad'].update(monthlyPc=None, monthlyPcStatus='masked',
                                         monthlyTotal=None, monthlyTotalStatus='unavailable')
    items, diagnostics = cak.load_candidate_export(write_export(tmp_path, payload), NOW)
    assert len(items) == 1 and items[0]['searchad']['monthlyTotal'] is None
    assert diagnostics['monthly_unavailable_count'] == 1
    assert diagnostics['qualified_rising_count'] == 0
    payload['items'][0]['searchad']['monthlyPc'] = 0
    assert cak.load_candidate_export(write_export(tmp_path, payload), NOW)[0] == []


@pytest.mark.parametrize('status,failure', [('failed', 'network'), ('no_exact_match', None),
                                          ('not_configured', 'credentials_missing')])
def test_unavailable_monthly_lookup_is_visible_and_not_eligible(tmp_path, status, failure):
    payload = make_export()
    payload['items'][0]['searchad'].update(lookupStatus=status, failureCode=failure, measuredAt=None,
                                         matchedKeyword=None, monthlyPc=None, monthlyMobile=None,
                                         monthlyTotal=None, monthlyPcStatus='missing', monthlyMobileStatus='missing',
                                         monthlyTotalStatus='unavailable')
    items, diagnostics = cak.load_candidate_export(write_export(tmp_path, payload), NOW)
    assert len(items) == 1 and diagnostics['qualified_rising_count'] == 0
    assert diagnostics['monthly_unavailable_count'] == 1


def test_zero_baseline_does_not_turn_into_a_fabricated_rise(tmp_path):
    payload = make_export([make_item(previous_ratio=0)])
    items, diagnostics = cak.load_candidate_export(write_export(tmp_path, payload), NOW)
    assert items[0]['trend']['dayPct'] is items[0]['trend']['hotScore'] is None
    assert diagnostics['qualified_rising_count'] == 0
    payload['items'][0]['trend'].update(dayPct=300, dayPctStatus='measured', hotScore=66)
    assert cak.load_candidate_export(write_export(tmp_path, payload), NOW)[0] == []


@pytest.mark.parametrize('monthly,latest,previous,baseline,qualified', [
    (999, 60, 20, 20, False), (1000, 60, 20, 20, True),
    (1200, 20, 20, 10, False), (1200, 20, 10, 20, False),
    (1200, 60, 59, 59, False),
])
def test_rising_thresholds_use_exact_demand_and_both_measured_growths(
        tmp_path, monthly, latest, previous, baseline, qualified):
    payload = make_export([make_item(monthly=monthly, latest_ratio=latest,
                                     previous_ratio=previous, baseline_mean=baseline)])
    items, _ = cak.load_candidate_export(write_export(tmp_path, payload), NOW)
    assert cak.qualified_rising(items[0]) is qualified


def test_only_whitespace_may_change_when_joining_monthly_measurements(tmp_path):
    payload = make_export([make_item('2026 건강 검진 일정')])
    payload['items'][0]['searchad']['matchedKeyword'] = '2026건강검진일정'
    assert len(cak.load_candidate_export(write_export(tmp_path, payload), NOW)[0]) == 1
    payload['items'][0]['searchad']['matchedKeyword'] = '2027건강검진일정'
    assert cak.load_candidate_export(write_export(tmp_path, payload), NOW)[0] == []
    payload = make_export([make_item('2026건강검진일정'), make_item('2027건강검진일정')])
    assert len(cak.load_candidate_export(write_export(tmp_path, payload), NOW)[0]) == 2


def test_bad_item_does_not_remove_other_verified_items(tmp_path):
    payload = make_export([make_item(), make_item('예방접종일정')])
    payload['items'][1]['trend']['hotScore'] = -1
    items, diagnostics = cak.load_candidate_export(write_export(tmp_path, payload), NOW)
    assert [item['keyword'] for item in items] == ['혈당관리방법']
    assert diagnostics['status'] == 'partial' and diagnostics['rejected_count'] == 1


@pytest.mark.parametrize('ttl', [0, 25, True])
def test_compliance_ttl_must_be_bounded_positive_integer(tmp_path, ttl):
    payload = make_export()
    payload['compliance']['cacheTtlHours'] = ttl
    items, diagnostics = cak.load_candidate_export(write_export(tmp_path, payload), NOW)
    assert items == [] and diagnostics['reason'] == 'invalid_compliance'


def test_envelope_age_expiry_signal_age_and_data_lag_are_not_renewed(tmp_path):
    payload = make_export()
    path = write_export(tmp_path, payload)
    assert cak.load_candidate_export(path, NOW + timedelta(hours=23))[0] == []
    renewed = deepcopy(payload)
    renewed['generatedAt'] = (NOW + timedelta(hours=23)).isoformat()
    renewed['expiresAt'] = (NOW + timedelta(hours=24)).isoformat()
    items, diagnostics = cak.load_candidate_export(write_export(tmp_path, renewed), NOW + timedelta(hours=23))
    assert items == [] and diagnostics['rejection_counts'] == {'stale_signal': 1}
    old_daily = make_export([make_item(latest_day=NOW.astimezone(cak.KST).date() - timedelta(days=4))])
    items, diagnostics = cak.load_candidate_export(write_export(tmp_path, old_daily), NOW)
    assert items == [] and diagnostics['rejection_counts'] == {'stale_trend': 1}


def test_cached_provenance_rechecks_shorter_ttl_and_calendar_data_lag(tmp_path):
    payload = make_export(ttl=6)
    items, diagnostics = cak.load_candidate_export(write_export(tmp_path, payload), NOW)
    proof = {'relationship': 'exact', 'item': items[0], 'export': diagnostics['export_metadata']}
    assert cak.valid_cak_provenance(proof, items[0]['keyword'], 1200, NOW + timedelta(hours=3))
    assert not cak.valid_cak_provenance(proof, items[0]['keyword'], 1200, NOW + timedelta(hours=4))
    assert not cak.valid_cak_provenance(proof, items[0]['keyword'], 1300, NOW)
    assert not cak.valid_cak_provenance(proof, '혈당관리방법효과', 1200, NOW)
    payload = make_export([make_item(latest_day=NOW.astimezone(cak.KST).date() - timedelta(days=3))])
    items, diagnostics = cak.load_candidate_export(write_export(tmp_path, payload), NOW)
    proof.update(item=items[0], export=diagnostics['export_metadata'])
    assert cak.valid_cak_provenance(proof, items[0]['keyword'], 1200, NOW)
    assert not cak.valid_cak_provenance(proof, items[0]['keyword'], 1200, NOW + timedelta(hours=12))


def test_missing_empty_and_malformed_feeds_have_explicit_safe_diagnostics(tmp_path):
    assert cak.load_candidate_export(None, NOW)[1]['status'] == 'not_configured'
    assert cak.load_candidate_export(tmp_path / 'missing.json', NOW)[1]['status'] == 'missing'
    items, diagnostics = cak.load_candidate_export(write_export(tmp_path, make_export([])), NOW)
    assert items == [] and diagnostics['status'] == 'empty'
    path = tmp_path / 'invalid.json'
    path.write_text('private token: invalid JSON', encoding='utf-8')
    items, diagnostics = cak.load_candidate_export(path, NOW)
    assert items == [] and diagnostics['status'] == 'invalid'
    assert 'private' not in json.dumps(diagnostics)


def test_transport_logs_only_allowlisted_identity_and_never_overrides_import_status(tmp_path, monkeypatch):
    transport = tmp_path / 'transport.json'
    transport.write_text(json.dumps({'status': 'ok', 'reason': 'downloaded', 'sourceRunId': 123,
                                     'artifactId': 456, 'headSha': 'a' * 40,
                                     'sourceRunCreatedAt': NOW.isoformat(),
                                     'token': 'private-token', 'url': 'https://private.example/secret'}))
    monkeypatch.setenv('CAK_KEYWORD_CANDIDATES_FETCH_STATUS_FILE', str(transport))
    items, diagnostics = cak.load_candidate_export(tmp_path / 'absent', NOW)
    assert items == [] and diagnostics['status'] == 'missing'
    assert diagnostics['transport']['sourceRunId'] == 123
    assert 'private' not in json.dumps(diagnostics)
    transport.write_text(json.dumps({'status': 'ok', 'reason': 'private raw exception'}))
    assert cak.load_candidate_export(None, NOW)[1]['transport'] == {'status': 'malformed', 'reason': 'invalid_payload'}


def test_deeply_nested_optional_inputs_fall_back_without_raw_error(tmp_path, monkeypatch):
    path = tmp_path / 'nested.json'
    path.write_text('[' * 2000 + '0' + ']' * 2000)
    items, diagnostics = cak.load_candidate_export(path, NOW)
    assert items == [] and diagnostics['status'] == 'invalid'
    assert diagnostics['reason'] in ('unreadable_export', 'invalid_envelope')
    # CPython versions differ in the nesting they accept. Exercise the exception
    # contract directly as well, without increasing the interpreter's stack risk.
    def recursion_failure(*args, **kwargs):
        raise RecursionError('private parser context')
    monkeypatch.setattr(cak.json, 'loads', recursion_failure)
    assert cak.load_candidate_export(path, NOW)[1]['reason'] == 'unreadable_export'
    monkeypatch.setenv('CAK_KEYWORD_CANDIDATES_FETCH_STATUS_FILE', str(path))
    assert cak.load_candidate_export(None, NOW)[1]['transport'] == {'status': 'malformed', 'reason': 'invalid_payload'}


@pytest.mark.parametrize(('field', 'value'), [
    ('requestedKeywordCount', 0), ('storedKeywordCount', 0), ('eligibleDailyCount', 2),
    ('exportedCount', 0), ('truncatedCount', 1),
])
def test_scope_counts_describe_the_same_bounded_collection(tmp_path, field, value):
    payload = make_export()
    payload['scope'][field] = value
    items, diagnostics = cak.load_candidate_export(write_export(tmp_path, payload), NOW)
    assert items == [] and diagnostics['reason'] == 'invalid_scope'
