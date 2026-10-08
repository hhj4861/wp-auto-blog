from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock
import json
import pytest
from bs4 import BeautifulSoup
from src import latest_issues as latest, market_topics as market
from src.editorial import _publication_dates

NOW = datetime.fromisoformat('2026-10-08T04:00:00+00:00')
EVENT = '새 에이전트가 도구 실행 권한을 사용자에게 먼저 확인하는 기능을 공개했습니다. 기존 기능과 달라진 승인 절차와 적용 대상을 발표합니다.'


def item():
    return {'keyword': '새에이전트', 'category': '테크', 'topic': '새에이전트 공개: 달라진 실행 승인',
            'intent': '새 기능에서 무엇이 바뀌었나?', 'score': 20,
            'verified_sources': [{'url': 'https://openai.com/index/example/', 'title': '새에이전트 공개',
             'excerpt': '2026년 10월 8일 발표. ' + EVENT + ' 상세 설명입니다.' * 20,
             'publication_dates': ['2026-10-08T01:00:00Z']}]}


def verdict(**changes):
    return {'is_new_event': True, 'topic_is_about_event': True, 'scope': 'full_topic',
            'event_kind': 'release', 'source_index': 0, 'event_date': '2026-10-08',
            'date_quote': '2026년 10월 8일', 'event_quote': EVENT, **changes}


def approved():
    row = item(); row['latest_issue_evidence'] = latest.review(row, NOW, lambda _: verdict()); return row


def test_current_issue_and_reuse_pass():
    row = approved()
    assert latest.issues(row, NOW) == []
    assert latest.current_sources_match(row, deepcopy(row['verified_sources']), NOW)


@pytest.mark.parametrize('changes,reason', [
    ({'is_new_event': False}, 'not_a_current_issue'),
    ({'topic_is_about_event': False}, 'not_a_current_issue'),
    ({'scope': 'narrower_query'}, 'not_a_current_issue'),
    ({'event_kind': 'evergreen'}, 'not_a_current_issue'),
    ({'source_index': True}, 'invalid_issue_source'),
    ({'source_index': 9}, 'invalid_issue_source'),
    ({'event_quote': '원문에 존재하지 않는 새로운 발표 내용을 임의로 만들어서는 안 됩니다.'}, 'ungrounded_issue_event'),
    ({'date_quote': '2026-10-07'}, 'ungrounded_issue_date'),
    ({'event_date': '2026-10-07'}, 'ungrounded_issue_date'),
    ({'event_date': '2026-02-30'}, 'invalid_issue_date'),
])
def test_invalid_or_evergreen_verdict_never_passes(changes, reason):
    row = item(); row['latest_issue_evidence'] = latest.review(row, NOW, lambda _: verdict(**changes))
    assert latest.issues(row, NOW) == [reason]


def test_old_event_with_fresh_fetch_and_title_year_fails():
    row = item(); row['topic'] = '2026 최신 설치 방법'
    row['verified_sources'][0].update(excerpt='2021-10-05 ' + EVENT, checked_on='2026-10-08', publication_dates=[])
    row['latest_issue_evidence'] = latest.review(row, NOW, lambda _: verdict(event_date='2021-10-05', date_quote='2021-10-05'))
    assert latest.issues(row, NOW) == ['issue_outside_window']


def test_date_added_to_generic_install_guide_fails_semantic_gate():
    row = item(); row['topic'] = '윈도우11 설치 방법 2026'
    row['latest_issue_evidence'] = latest.review(row, NOW, lambda _: verdict(topic_is_about_event=False))
    assert latest.issues(row, NOW) == ['not_a_current_issue']


def test_yesterday_midnight_boundary_and_cache_expiry():
    row = item(); row['verified_sources'][0]['publication_dates'] = ['2026-10-07T00:00:00+09:00']
    row['latest_issue_evidence'] = latest.review(row, NOW, lambda _: verdict(event_date='2026-10-07', date_quote='2026-10-07T00:00:00+09:00'))
    assert latest.issues(row, NOW) == []
    assert latest.issues(row, datetime.fromisoformat('2026-10-09T00:00:00+09:00')) == ['issue_outside_window']


def test_future_timestamp_today_fails():
    row = item(); row['verified_sources'][0]['publication_dates'] = ['2026-10-08T20:00:00+09:00']
    row['latest_issue_evidence'] = latest.review(row, NOW, lambda _: verdict(date_quote='2026-10-08T20:00:00+09:00'))
    assert latest.issues(row, NOW) == ['issue_outside_window']


@pytest.mark.parametrize('field', ['keyword', 'topic', 'intent', 'category'])
def test_evidence_cannot_be_relabelled(field):
    row = approved(); row[field] += '변경'
    assert latest.issues(row, NOW) == ['stale_latest_issue_evidence']


def test_writer_refetch_must_keep_event_and_date():
    row = approved(); sources = deepcopy(row['verified_sources'])
    sources[0]['excerpt'] = '일반 설치 안내입니다.' * 50
    assert not latest.current_sources_match(row, sources, NOW)


def test_publication_metadata_does_not_accept_modified_or_copyright():
    html = '''<meta property="article:modified_time" content="2026-10-08">
    <meta property="article:published_time" content="2021-10-05">
    <script type="application/ld+json">{"@type":"NewsArticle","dateModified":"2026-10-08","datePublished":"2021-10-05"}</script>
    <footer>Copyright 2026-10-08</footer>'''
    assert _publication_dates(BeautifulSoup(html, 'html.parser')) == ['2021-10-05']


def test_discovery_uses_date_limited_queries_and_actual_fetched_source():
    source = item()['verified_sources'][0]
    search = Mock(return_value=('test_search', [{'url': source['url'], 'title': source['title']}]))
    fetch = Mock(return_value=source)
    ask = Mock(return_value={'candidates': [{'keyword': '새에이전트', 'source_index': 0}]})
    seeds, audit = latest.discover('테크', NOW, search, fetch, ask, deadline=float('inf'))
    assert seeds == ['새에이전트'] and audit['status'] == 'discovered'
    assert all('after:2026-10-07 before:2026-10-09' in c.args[0] for c in search.call_args_list)
    assert fetch.call_count == 1


def test_old_page_with_fresh_search_snippet_is_not_recent():
    source = item()['verified_sources'][0]
    source.update(excerpt='2021-10-05 ' + EVENT, publication_dates=['2021-10-05'])
    search = lambda _: ('test', [{'url': source['url'], 'title': '오늘 최신 2026-10-08'}])
    ask = Mock()
    seeds, audit = latest.discover('테크', NOW, search, lambda *a: source, ask, deadline=float('inf'))
    assert not seeds and audit['sources'][0]['status'] == 'no_recent_date'
    ask.assert_not_called()


def test_final_article_must_be_about_event_and_include_date():
    row = approved(); html = '<p>2026년 10월 8일 ' + EVENT + '</p>'
    call = lambda _: {'about_event': True, 'date_correct': True, 'article_quote': EVENT}
    assert latest.review_article(row['topic'], html, row, row['verified_sources'], call, NOW) == []
    assert latest.review_article(row['topic'], '<p>'+EVENT+'</p>', row, row['verified_sources'], call, NOW)
    assert latest.review_article(row['topic'], html, row, row['verified_sources'], lambda _: {'about_event': False}, NOW)


def test_newer_event_beats_high_monthly_demand_score():
    older = approved(); newer = approved()
    older['latest_issue_evidence']['review']['event_date'] = '2026-10-07'; older['score'] = 99
    assert max([older, newer], key=latest.priority) is newer


def test_real_published_windows_candidate_cannot_be_reused_or_enqueued():
    row = json.loads((Path(__file__).parent / 'fixtures/windows_install_published_20261008.json').read_text())
    # Upgrading a cached version number cannot manufacture missing issue evidence.
    row['selection_version'] = market.PROCESS_VERSION
    now = datetime.fromisoformat(row['selected_at']) + timedelta(minutes=1)
    assert market.fresh_research_item(row, '테크', now)
    assert not market.opportunity.issues(row, now) and not market.suitability.issues(row, now)
    assert market.current_priority(row)
    assert latest.issues(row, now) == ['missing_latest_issue_evidence']
    assert not market.fresh_market_item(row, '테크', now)
    with pytest.raises(RuntimeError): market.enqueue_report([], {'category': '테크', 'selected': [row]})


@pytest.fixture
def selection_case(monkeypatch, tmp_path):
    """Run real selection/cache/event gates; mock only network and model responses."""
    from hashlib import sha256
    from tests.test_market_topics import organic_sample, synthetic_search_review, analysis
    source = item()['verified_sources'][0]
    today = datetime.now(timezone.utc).astimezone(latest.KST).date().isoformat()
    source.update(excerpt=today + ' ' + EVENT + ' 새에이전트 공식 발표 내용입니다.' * 15,
                  checked_on=today, original_url=source['url'], publication_dates=[today])
    source['sha256'] = sha256(source['excerpt'].encode()).hexdigest()
    monkeypatch.setattr(market, 'ROOT', tmp_path)
    monkeypatch.setattr(market, 'LEDGER', tmp_path / 'history.json')
    monkeypatch.setattr(market.latest_issues, 'discover', lambda *a, **kw:
                        (['새에이전트'], {'status': 'discovered', 'candidates': [{'keyword': '새에이전트', 'source': source}]}))
    monkeypatch.setattr(market, 'demand_candidates', lambda _: {'새에이전트': {'keyword': '새에이전트', 'monthly': 90000}})
    monkeypatch.setattr(market, 'discover_youtube', lambda *a: ([], {'status': 'test'}))
    monkeypatch.setattr(market, 'merge_cak_candidates', lambda stats, *a: (stats, {'direct_count': 0}))
    monkeypatch.setattr(market, 'search_results', lambda q: ('google_custom_search', organic_sample('새에이전트')))
    monkeypatch.setattr(market, 'candidate_sources', lambda *a: [source])
    monkeypatch.setattr(market, 'fetch_trend_change', lambda _: 100)
    monkeypatch.setattr(market, 'review_search', synthetic_search_review)
    state = {'is_new_event': True}
    def ask(prompt):
        if '조사 후보를 고르세요.' in prompt:
            return {'candidates': [{'keyword': '새에이전트'}]}
        if '최신 이슈 발행 필수 심사입니다' in prompt:
            return verdict(event_date=today, date_quote=today, is_new_event=state['is_new_event'])
        return analysis('새에이전트', '테크', topic='새에이전트 신규 기능 공개',
                        intent='새 승인 기능은 무엇이 달라졌나?', source_indices=[0])
    monkeypatch.setattr(market, 'ask', ask)
    def independent_plan(candidate, now, _):
        quote = candidate['verified_sources'][0]['excerpt']
        return market.suitability.review_plan(candidate, now, lambda _: {
            'scope': 'full_keyword', 'target_keyword': candidate['keyword'],
            'sources': [{'source_index': 0, 'quote': quote, 'entity': '새에이전트', 'context': 'system_rules'}],
            'required_facets': [{'facet': candidate['intent'], 'answer': EVENT, 'supported': True, 'source_index': 0, 'quote': quote}],
            'current_relevance': {'kind': 'evergreen', 'source_index': 0, 'quote': quote, 'event_start': None, 'event_end': None, 'date_quote': None}})
    monkeypatch.setattr(market, 'review_plan', independent_plan)
    return state


def test_full_selection_enqueues_verified_new_issue(selection_case):
    report = market.select_category('테크', top_n=1, titles=[])
    assert len(report['selected']) == 1, report['candidate_decisions']
    row = report['selected'][0]
    assert not latest.issues(row)
    assert market.fresh_market_item(row, '테크')
    assert market.enqueue_report([], report) == [row]
    assert report['selection_scope'] == 'newest_verified_issue_then_score'


def test_full_selection_high_demand_and_trend_cannot_override_old_issue(selection_case):
    selection_case['is_new_event'] = False
    report = market.select_category('테크', top_n=1, titles=[])
    assert not report['selected']
    assert any('not_a_current_issue' in row['hold_reasons'] for row in report['held'])
    with pytest.raises(RuntimeError): market.enqueue_report([], report)


def test_announcement_host_does_not_allow_user_community_subdomains():
    from src.editorial import is_official_url
    assert is_official_url('https://openai.com/index/news/')
    assert not is_official_url('https://community.openai.com/t/announcement')


def test_closed_windows_candidate_cannot_be_recovered_as_market_draft():
    from scripts.publish_codex_draft import _fresh
    row = json.loads((Path(__file__).parent / 'fixtures/windows_install_published_20261008.json').read_text())
    row['selection_version'] = market.PROCESS_VERSION
    with pytest.raises(RuntimeError): _fresh(row)
