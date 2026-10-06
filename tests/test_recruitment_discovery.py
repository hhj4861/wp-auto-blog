from datetime import date, datetime, timedelta
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
import requests

from src import recruitment_discovery as discovery, market_topics as market
from tests.test_market_topics import isolated_market_history, organic_sample, analysis, market_pipeline  # noqa: F401
from tests.test_recruitment_sources import source


def listing(name='한국전력공사', *, end='26.10.15', status='진행중', href='/recruitview.do?idx=42'):
    return f'''<table><tr><td><input></td><td>1</td><td><a href="{href}"></a>직원 채용 공고</td>
        <td>{name}</td><td>서울</td><td>정규직</td><td>2026.10.01</td><td>{end}</td><td>{status}</td></tr></table>'''


def notice(today=date(2026, 10, 6), name='한국전력공사'):
    end = today + timedelta(days=7)
    text = (f'{name} 직원 채용 공고. 채용기간 {today:%y.%m.%d} ~ {end:%y.%m.%d} 등록일 {today}. '
            '공식 준비물 안내 응시자격: 지원자는 신분증과 접수 내역을 준비하고 필요한 서류를 확인합니다. '
            '전형절차: 서류심사와 면접을 진행합니다. 제출 서류: 지원서 및 자기소개서. '
            '지원 직무의 자격요건과 제출 항목을 확인한 뒤 신청합니다. '
            '각 단계의 합격 여부와 시험 장소는 공식 홈페이지에서 확인합니다. 제출 내용이 사실과 다르면 합격이 취소될 수 있습니다.')
    src = source(text, 42)
    return {'keyword': name + '채용', 'employer': name, 'url': src['url'],
            'title': name + ' 직원 채용', 'deadline': end.isoformat(), 'employment_type': '정규직', 'source': src}


@pytest.mark.parametrize('changes', [
    {'end': '26.10.05'}, {'end': '26.10.06'}, {'end': '26.13.20'}, {'end': '미정'},
    {'status': '마감'}, {'href': 'https://attacker.example/recruitview.do?idx=42'},
    {'href': '//job.alio.go.kr.attacker.example/recruitview.do?idx=42'},
    {'href': 'http://job.alio.go.kr/recruitview.do?idx=42'}, {'href': '/recruit.do'},
])
def test_listing_rejects_closed_unknown_deadline_and_unsafe_locators(changes):
    assert discovery.listing_rows(listing(**changes), date(2026, 10, 6)) == []


def test_empty_anchor_title_is_read_from_cell_and_company_suffix_removed():
    rows = discovery.listing_rows(listing('한전KPS(주)') * 2, date(2026, 10, 6))
    assert len(rows) == 1
    assert rows[0]['keyword'] == '한전KPS채용'
    assert rows[0]['title'] == '직원 채용 공고'


@pytest.mark.parametrize('change', ['wrong_employer', 'different_deadline', 'missing_period', 'not_started'])
def test_listing_status_never_substitutes_for_independent_detail(change):
    row = notice()
    src = dict(row['source'])
    if change == 'wrong_employer':
        src['excerpt'] = src['excerpt'].replace('한국전력공사', '다른공사')
    elif change == 'different_deadline':
        row['deadline'] = '2026-10-16'
    elif change == 'missing_period':
        src['excerpt'] = src['excerpt'].replace('채용기간', '근무기간')
    else:
        src['excerpt'] = src['excerpt'].replace('26.10.06', '26.10.10')
    assert not discovery.detail_matches(row, src, date(2026, 10, 6))


def test_discovery_follows_current_listing_and_detail_without_search_index(monkeypatch):
    row = notice()
    fetch = Mock(return_value=listing(end='26.10.13'))
    monkeypatch.setattr(discovery, 'fetch_listing', fetch)
    monkeypatch.setattr(discovery, 'fetch_source', lambda url: row['source'])
    results, audit = discovery.discover(date(2026, 10, 6))
    assert len(results) == 1 and results[0]['source'] == row['source']
    assert audit['status'] == 'ready' and audit['detail_attempts'] == 1
    assert fetch.call_count == 2  # repeated page cannot exhaust all detail slots


def test_unavailable_listing_is_diagnostic_not_silent_old_keyword_fallback(monkeypatch):
    monkeypatch.setattr(discovery, 'fetch_listing', Mock(side_effect=requests.Timeout()))
    results, audit = discovery.discover(date(2026, 10, 6))
    assert results == [] and audit['status'] == 'unavailable'
    assert audit['errors'] == ['listing_unavailable']


def test_only_exact_measured_queries_receive_current_evidence(monkeypatch):
    row = notice()
    monkeypatch.setattr(discovery, 'discover', lambda *a, **kw: ([row], {'status': 'ready'}))
    measure = Mock(return_value={row['keyword']: {'keyword': row['keyword'], 'monthly': 1500},
                                '다른공사채용': {'keyword': '다른공사채용', 'monthly': 9000}})
    stats = {'시험준비물': {'keyword': '시험준비물', 'monthly': 1000},
             '한국전력공사채용조건': {'keyword': '한국전력공사채용조건', 'monthly': 99999}}
    # The common isolation fixture replaces the market's module function; use
    # the original imported reference retained below for this test.
    result, audit = REAL_PREPARE(stats, measure, date(2026, 10, 6))
    assert set(result) == {'시험준비물', row['keyword']}
    assert result[row['keyword']]['monthly'] == 1500
    assert result[row['keyword']]['recruitment_notices'] == [row]
    assert audit['measured_supported'] == 1
    measure.assert_called_once_with([row['keyword']])


REAL_PREPARE = discovery.prepare


def test_missing_measurement_does_not_borrow_employer_or_related_volume(monkeypatch):
    monkeypatch.setattr(discovery, 'discover', lambda *a, **kw: ([notice()], {'status': 'ready'}))
    result, audit = REAL_PREPARE({}, Mock(side_effect=RuntimeError('unavailable')), date(2026, 10, 6))
    assert result == {} and audit['measurement_errors']


def test_current_sources_survive_full_selection_and_existing_gates(monkeypatch, market_pipeline):
    today = datetime.now(ZoneInfo('Asia/Seoul')).date()
    row = notice(today)
    key = row['keyword']
    monkeypatch.setattr(discovery, 'prepare', REAL_PREPARE)
    monkeypatch.setattr(discovery, 'discover', lambda *a, **kw: ([row], {'status': 'ready'}))
    monkeypatch.setattr(market, 'demand_candidates', lambda _: {key: {'keyword': key, 'monthly': 1500}})
    monkeypatch.setattr(market, 'search_results', Mock(return_value=('codex_native_search', organic_sample(key))))
    acquire = Mock(side_effect=AssertionError('Do not search stale locators again'))
    monkeypatch.setattr(market, 'candidate_sources', acquire)
    monkeypatch.setattr(market, 'ask', Mock(side_effect=[{'candidates': [{'keyword': key}]}, analysis(key)]))
    monkeypatch.setattr(market, 'fetch_trend_change', lambda _: None)
    report = market.select_category('취업', 1, titles=[])
    assert len(report['selected']) == 1, (report['rejected'], report['held'])
    selected = report['selected'][0]
    assert selected['verified_sources'] == [row['source']]
    assert selected['valid_until'] == row['deadline']
    assert selected['recruitment_deadline'] == row['deadline']
    assert market.fresh_market_item(selected, '취업')
    assert market.opportunity.issues(selected) == market.suitability.issues(selected) == []
    assert report['recruitment_discovery']['measured_supported'] == 1
    acquire.assert_not_called()
    content = market_pipeline.content_generator.generate.return_value
    content.title = selected['topic']
    content.keywords = [key]
    content.focus_keyphrase = key
    content.html = f'<h2>{key}</h2><p>{key}의 지원자는 신분증과 접수 내역을 준비하고 공식 채용 절차를 확인하세요.</p>'
    content.sources = selected['verified_sources']
    result = market_pipeline.run_single(selected['topic'], [key], '취업', market_brief=selected)
    assert result.success, result.error
    market_pipeline.wp_client.create_post.assert_called_once()
    passed = market_pipeline.content_generator.generate.call_args.kwargs['market_brief']
    assert passed['verified_sources'] == [row['source']]
    assert passed['recruitment_deadline'] == row['deadline']


def test_no_current_hiring_evidence_returns_inspectable_empty_report(monkeypatch):
    key = '한국전력공사채용'
    monkeypatch.setattr(discovery, 'prepare', REAL_PREPARE)
    monkeypatch.setattr(discovery, 'discover', lambda *a, **kw: ([], {'status': 'unavailable'}))
    monkeypatch.setattr(market, 'demand_candidates', lambda _: {key: {'keyword': key, 'monthly': 1500}})
    ask = Mock(side_effect=AssertionError('No viable job to review'))
    monkeypatch.setattr(market, 'ask', ask)
    report = market.select_category('취업', 1, titles=[])
    assert report['selected'] == [] and report['research_stop_reason'] == 'pool_exhausted'
    assert report['recruitment_discovery']['unsupported_hiring_keywords'] == [key]
    ask.assert_not_called()


def test_source_backed_jobs_are_not_hidden_by_the_120_keyword_cap():
    stats = {f'시험준비물{i}': {'keyword': f'시험준비물{i}', 'monthly': 40000 - i} for i in range(300)}
    key = '한국전력공사채용'
    stats[key] = {'keyword': key, 'monthly': 500, 'recruitment_notices': [notice()]}
    assert market.candidate_pool(stats, [], '취업')[0]['keyword'] == key


def test_current_notice_does_not_clear_existing_failure_cooldown(monkeypatch):
    from datetime import timezone
    today = datetime.now(ZoneInfo('Asia/Seoul')).date()
    row = notice(today)
    key = row['keyword']
    monkeypatch.setattr(discovery, 'prepare', REAL_PREPARE)
    monkeypatch.setattr(discovery, 'discover', lambda *a, **kw: ([row], {'status': 'ready'}))
    monkeypatch.setattr(market, 'demand_candidates', lambda _: {key: {'keyword': key, 'monthly': 1500}})
    now = datetime.now(timezone.utc)
    history = [{'keyword': key, 'reason_code': 'source_coverage', 'failed_at': now.isoformat(),
                'retry_after': (now + timedelta(days=3)).isoformat(), 'attempts': 1}]
    report = market.select_category('취업', 1, titles=[], failure_history=history)
    assert report['selected'] == [] and report['deferred_keywords']
    assert any(r['keyword'] == key for r in report['failure_history'])


@pytest.mark.parametrize('failure', ['search', 'plan'])
def test_current_notice_does_not_override_negative_independent_reviews(monkeypatch, failure):
    today = datetime.now(ZoneInfo('Asia/Seoul')).date()
    row = notice(today)
    key = row['keyword']
    monkeypatch.setattr(discovery, 'prepare', REAL_PREPARE)
    monkeypatch.setattr(discovery, 'discover', lambda *a, **kw: ([row], {'status': 'ready'}))
    monkeypatch.setattr(market, 'demand_candidates', lambda _: {key: {'keyword': key, 'monthly': 1500}})
    results = organic_sample(key) if failure == 'plan' else organic_sample(key)[:1]
    monkeypatch.setattr(market, 'search_results', Mock(return_value=('codex_native_search', results)))
    monkeypatch.setattr(market, 'ask', Mock(side_effect=[{'candidates': [{'keyword': key}]},
        {'supported': False, 'rejection_reason': 'insufficient_search_intent'}]))
    report = market.select_category('취업', 1, titles=[])
    assert report['selected'] == [] and report['rejected']


def test_empty_seed_measurements_can_be_replaced_by_exact_current_employer_measurements(monkeypatch):
    today = datetime.now(ZoneInfo('Asia/Seoul')).date()
    row = notice(today)
    key = row['keyword']
    monkeypatch.setattr(discovery, 'prepare', REAL_PREPARE)
    monkeypatch.setattr(discovery, 'discover', lambda *a, **kw: ([row], {'status': 'ready'}))
    def measure(seeds):
        if seeds == [key]:
            return {key: {'keyword': key, 'monthly': 1500}}
        raise market.NoMeasuredDemand('no generic seed measurements')
    monkeypatch.setattr(market, 'demand_candidates', measure)
    monkeypatch.setattr(market, 'search_results', Mock(return_value=('codex_native_search', organic_sample(key))))
    monkeypatch.setattr(market, 'ask', Mock(side_effect=[{'candidates': [{'keyword': key}]}, analysis(key)]))
    monkeypatch.setattr(market, 'fetch_trend_change', lambda _: None)
    report = market.select_category('취업', 1, titles=[])
    assert len(report['selected']) == 1


def test_public_listing_and_detail_snapshot_replay():
    import json
    from pathlib import Path
    data = json.loads((Path(__file__).parent / 'fixtures/recruitment_open_20261006.json').read_text())
    rows = discovery.listing_rows(data['listing_rows_html'], date(2026, 10, 6))
    assert len(rows) >= 2
    for notice in data['notices']:
        assert any(row['url'] == notice['url'] for row in rows)
        assert discovery.detail_matches(notice, notice['source'], date(2026, 10, 6))
        assert not discovery.detail_matches(notice, notice['source'], date.fromisoformat(notice['deadline']))


def test_saved_current_job_expires_at_korean_closing_day_even_with_null_model_deadline():
    from tests.test_market_topics import candidate
    from datetime import timezone
    now = datetime(2026, 10, 6, 23, tzinfo=ZoneInfo('Asia/Seoul'))
    item = candidate(selected_at=now.isoformat(), recruitment_deadline='2026-10-07', valid_until=None)
    assert market.fresh_research_item(item, '취업', now)
    assert not market.fresh_research_item(item, '취업', now + timedelta(hours=1))
    assert not market.fresh_research_item(item, '취업', (now + timedelta(hours=1)).astimezone(timezone.utc))


def test_diagnostic_counts_only_jobs_not_other_related_queries(monkeypatch, tmp_path, capsys):
    import json
    from scripts import check_recruitment_discovery as check
    row = notice()
    data = {row['keyword']: {'keyword': row['keyword'], 'monthly': 1500, 'recruitment_notices': [row]},
            '시험준비물': {'keyword': '시험준비물', 'monthly': 9999}}
    monkeypatch.setattr(discovery, 'prepare', lambda *a, **kw: (data, {'status': 'ready'}))
    report = tmp_path / 'report.json'
    report.write_text('{}')
    monkeypatch.setattr(market, 'REPORT', report)
    assert check.main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output['eligible_after_saved_history'] == 1
    assert output['candidates'][0]['keyword'] == row['keyword']
