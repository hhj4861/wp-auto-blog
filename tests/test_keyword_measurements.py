"""Only complete SearchAd device measurements may enter the measured demand pool."""

import io
import json
from types import SimpleNamespace

import pytest

from src import keyword_gate as gate


@pytest.mark.parametrize(('raw', 'expected'), [
    (0, (0, 'measured')),
    (1200, (1200, 'measured')),
    (1200.0, (1200, 'measured')),
    ('0', (0, 'measured')),
    (' 1,200 ', (1200, 'measured')),
    ('001200', (1200, 'measured')),
    ('9,007,199,254,740,991', (9_007_199_254_740_991, 'measured')),
    ('<10', (None, 'masked')),
    (' < 10 ', (None, 'masked')),
    (None, (None, 'missing')),
    ('', (None, 'missing')),
    (' \t ', (None, 'missing')),
    (-1000, (None, 'invalid')),
    ('-1,000', (None, 'invalid')),
    ('-12.5', (None, 'invalid')),
    (12.5, (None, 'invalid')),
    ('12.5', (None, 'invalid')),
    ('1200.0', (None, 'invalid')),
    ('+1200', (None, 'invalid')),
    ('1e6', (None, 'invalid')),
    ('1,20', (None, 'invalid')),
    ('1,200,', (None, 'invalid')),
    ('1 200', (None, 'invalid')),
    ('월 1200회', (None, 'invalid')),
    ('<1000', (None, 'invalid')),
    (True, (None, 'invalid')),
    (False, (None, 'invalid')),
    (float('nan'), (None, 'invalid')),
    (float('inf'), (None, 'invalid')),
    ([], (None, 'invalid')),
    ({}, (None, 'invalid')),
    (9_007_199_254_740_992, (None, 'invalid')),
    ('9007199254740992', (None, 'invalid')),
    ('9' * 5000, (None, 'invalid')),
])
def test_device_measurements_preserve_unknown_status(raw, expected):
    assert gate._monthly_measurement(raw) == expected
    assert gate._to_int(raw) == expected[0]


@pytest.fixture
def mock_searchad(monkeypatch):
    for key in ('NAVER_AD_CUSTOMER_ID', 'NAVER_AD_API_KEY', 'NAVER_AD_SECRET_KEY'):
        monkeypatch.setenv(key, 'test-placeholder')
    warnings = []
    monkeypatch.setattr(gate, 'logger', SimpleNamespace(warning=warnings.append, debug=lambda _: None))

    def respond(rows, *, raw_payload=False):
        body = json.dumps(rows if raw_payload else {'keywordList': rows},
                          ensure_ascii=False).encode('utf-8')
        monkeypatch.setattr(gate.urllib.request, 'urlopen',
                            lambda request, timeout: io.BytesIO(body))
        return warnings

    return respond


def test_complete_counts_sum_and_sort_without_warning(mock_searchad):
    warnings = mock_searchad([
        {'relKeyword': '실제영회', 'monthlyPcQcCnt': 0, 'monthlyMobileQcCnt': '0'},
        {'relKeyword': '건강관리방법', 'monthlyPcQcCnt': '1,200', 'monthlyMobileQcCnt': 4500},
    ])

    result = gate.fetch_keyword_stats('건강 관리')

    assert [row['monthly'] for row in result] == [5700, 0]
    assert all(row['monthly_status'] == 'measured' for row in result)
    assert result[0]['monthly_pc'] == 1200
    assert result[0]['monthly_mobile'] == 4500
    assert all(row['monthly_pc_status'] == row['monthly_mobile_status'] == 'measured'
               for row in result)
    assert warnings == []


@pytest.mark.parametrize(('device', 'raw', 'expected_status'), [
    ('monthlyPcQcCnt', '< 10', 'masked'),
    ('monthlyMobileQcCnt', '<10', 'masked'),
    ('monthlyPcQcCnt', None, 'missing'),
    ('monthlyMobileQcCnt', '', 'missing'),
    ('monthlyPcQcCnt', '-1000', 'invalid'),
    ('monthlyMobileQcCnt', '500.0', 'invalid'),
])
def test_incomplete_side_cannot_borrow_high_other_device_volume(
        mock_searchad, device, raw, expected_status):
    from src.market_topics import demand_candidates

    source = {'relKeyword': '혈당관리방법', 'monthlyPcQcCnt': 500_000,
              'monthlyMobileQcCnt': 500_000, 'plAvgDepth': 1}
    source[device] = raw
    warnings = mock_searchad([source])
    result = gate.fetch_keyword_stats('혈당')[0]

    field = 'monthly_pc' if device == 'monthlyPcQcCnt' else 'monthly_mobile'
    other = 'monthly_mobile' if device == 'monthlyPcQcCnt' else 'monthly_pc'
    assert result['monthly'] == 0
    assert result['monthly_status'] == 'unavailable'
    assert result[field] is None
    assert result[field + '_status'] == expected_status
    assert result[other] == 500_000
    assert result[other + '_status'] == 'measured'
    with pytest.raises(RuntimeError, match='No measured demand'):
        demand_candidates(['혈당'])
    assert warnings == ['검색광고 월검색량 불완전: 1건'] * 2


def test_missing_field_is_not_measured_zero_and_logs_only_incomplete_count(mock_searchad):
    warnings = mock_searchad([
        {'relKeyword': '비공개원문', 'monthlyMobileQcCnt': 1000},
        {'relKeyword': '정상측정값', 'monthlyPcQcCnt': 0, 'monthlyMobileQcCnt': 1000},
        {'relKeyword': '민감한응답내용', 'monthlyPcQcCnt': 'unexpected', 'monthlyMobileQcCnt': '< 10'},
    ])

    result = gate.fetch_keyword_stats('조회시드')

    assert [row['monthly'] for row in result] == [1000, 0, 0]
    assert result[1]['monthly_pc'] is None
    assert result[1]['monthly_pc_status'] == 'missing'
    assert result[2]['monthly_pc_status'] == 'invalid'
    assert result[2]['monthly_mobile_status'] == 'masked'
    assert warnings == ['검색광고 월검색량 불완전: 2건']


@pytest.mark.parametrize('payload', [
    None, [], '원문응답비공개', 1200, True, {},
    {'keywordList': None}, {'keywordList': {}}, {'keywordList': '민감한응답'},
    {'keywordList': 123}, {'keywordList': True},
])
def test_bad_payload_or_keyword_list_returns_empty_with_fixed_diagnostic(mock_searchad, payload):
    warnings = mock_searchad(payload, raw_payload=True)

    assert gate.fetch_keyword_stats('조회시드') == []
    assert warnings == ['검색광고 응답 형식 오류: invalid_payload']


@pytest.mark.parametrize('bad_row', [
    None, [], '잘못된행', 1200, True, {},
    {'relKeyword': None}, {'relKeyword': 500}, {'relKeyword': True},
    {'relKeyword': []}, {'relKeyword': {}}, {'relKeyword': ''}, {'relKeyword': ' \t '},
])
def test_bad_rows_are_skipped_without_losing_other_measured_rows(mock_searchad, bad_row):
    warnings = mock_searchad([
        bad_row,
        {'relKeyword': '  건강관리방법 ', 'monthlyPcQcCnt': 100, 'monthlyMobileQcCnt': 900},
        {'relKeyword': '예방접종대상', 'monthlyPcQcCnt': 1500, 'monthlyMobileQcCnt': 3500},
    ])

    result = gate.fetch_keyword_stats('건강')

    assert [row['keyword'] for row in result] == ['예방접종대상', '건강관리방법']
    assert [row['monthly'] for row in result] == [5000, 1000]
    assert warnings == ['검색광고 응답 행 제외: 1건']


@pytest.mark.parametrize('bad_payload', [None, {'keywordList': None}, {'keywordList': [None]}])
def test_bad_optional_seed_response_preserves_existing_evergreen_demand(
        mock_searchad, monkeypatch, bad_payload):
    from src.market_topics import demand_candidates

    warnings = mock_searchad([])
    payloads = iter([
        {'keywordList': [{'relKeyword': '건강검진대상', 'monthlyPcQcCnt': 500, 'monthlyMobileQcCnt': 1500}]},
        bad_payload,
    ])
    monkeypatch.setattr(gate.urllib.request, 'urlopen', lambda request, timeout:
                        io.BytesIO(json.dumps(next(payloads)).encode('utf-8')))

    result = demand_candidates(['건강검진', '추가후보'])

    assert list(result) == ['건강검진대상']
    assert result['건강검진대상']['monthly'] == 2000
    assert len(warnings) == 1


def test_request_failure_never_logs_raw_error_or_keyword(mock_searchad, monkeypatch):
    warnings = mock_searchad([])

    def fail(request, timeout):
        raise ValueError('민감한응답이나인증정보')

    monkeypatch.setattr(gate.urllib.request, 'urlopen', fail)

    assert gate.fetch_keyword_stats('비공개조회어', attempt=2) == []
    assert warnings == ['검색광고 조회 실패: unavailable']
