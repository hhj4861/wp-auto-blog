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
            'intent': '새 기능에서 무엇이 바뀌었나?', 'score': 20, 'evidence_mode': 'latest_issue',
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


def test_real_windows_candidate_is_evergreen_fallback_and_its_draft_blocks_republication():
    # Policy 2026-10-09: an evergreen guide may be published only as a fallback when no
    # latest issue exists. The closed #1862 draft stays in the inventory (drafts count),
    # so the same guide is a duplicate and cannot be republished automatically.
    row = json.loads((Path(__file__).parent / 'fixtures/windows_install_published_20261008.json').read_text())
    row['selection_version'] = market.PROCESS_VERSION
    now = datetime.fromisoformat(row['selected_at']) + timedelta(minutes=1)
    assert not latest.required(row)
    assert market.fresh_market_item(row, '테크', now)
    assert market.duplicate(row['keyword'], row['topic'], ['윈도우11설치 방법: 업그레이드와 USB 새 설치 상세가이드'])
    from src import topic_inventory
    latest_row = {**approved(), 'category': '테크', 'status': 'pending'}
    fresh = lambda r, c, n: r is row or r is latest_row
    assert topic_inventory.pick_category([row, latest_row], '테크', now, fresh=fresh) == '테크'
    assert topic_inventory.pick_category([row, {**latest_row, 'category': '건강'}], '테크', now,
                                         fresh=lambda r, c, n: True) == '건강'


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


def test_measured_selection_produces_an_evergreen_fallback_item(selection_case):
    report = market.select_category('테크', top_n=1, titles=[])
    assert len(report['selected']) == 1, report['candidate_decisions']
    row = report['selected'][0]
    assert not latest.required(row) and 'latest_issue_evidence' not in row
    assert market.fresh_market_item(row, '테크')
    assert market.enqueue_report([], report) == [row]


def test_newer_latest_issue_ranks_before_a_high_demand_evergreen_item(selection_case):
    evergreen = market.select_category('테크', top_n=1, titles=[])['selected'][0]
    assert latest.priority(approved()) > latest.priority(evergreen)


def test_announcement_host_does_not_allow_user_community_subdomains():
    from src.editorial import is_official_url
    assert is_official_url('https://openai.com/index/news/')
    assert not is_official_url('https://community.openai.com/t/announcement')


def test_closed_windows_draft_from_an_older_selection_version_cannot_be_recovered():
    from scripts.publish_codex_draft import _fresh
    row = json.loads((Path(__file__).parent / 'fixtures/windows_install_published_20261008.json').read_text())
    with pytest.raises(RuntimeError): _fresh(row)  # selection_version 6 is not current


@pytest.mark.parametrize('value', ['20261008', '2026-W41-4', None, 20261008])
def test_event_date_uses_canonical_day_for_priority(value):
    row = item(); row['latest_issue_evidence'] = latest.review(row, NOW, lambda _: verdict(event_date=value))
    assert latest.issues(row, NOW) == ['invalid_issue_date']


def test_invalid_review_is_not_a_negative_content_verdict():
    row = item(); row['latest_issue_evidence'] = latest.review(row, NOW, lambda _: {})
    assert latest.issues(row, NOW) == ['invalid_issue_review']
    row = approved()
    html = '<p>2026-10-08 ' + EVENT + '</p>'
    assert latest.review_article(row['topic'], html, row, row['verified_sources'], lambda _: {}, NOW) == ['invalid_latest_issue_article_review']


@pytest.fixture
def listing_case(monkeypatch, tmp_path):
    """Listing-driven latest path: real gates, no demand/SERP lookups at all."""
    from hashlib import sha256
    from tests.test_market_topics import analysis
    today = datetime.now(timezone.utc).astimezone(latest.KST).date()
    page = {'url': 'https://www.korea.kr/briefing/pressReleaseView.do?newsId=9', 'title': '새에이전트 공개',
            'excerpt': today.isoformat() + ' ' + EVENT + ' 새에이전트 공식 발표 내용입니다.' * 15,
            'checked_on': today.isoformat(), 'publication_dates': [today.isoformat()]}
    page['sha256'] = sha256(page['excerpt'].encode()).hexdigest()
    listing = [{'url': page['url'], 'title': '새에이전트 공개', 'lead': EVENT,
                'published': today, 'publisher': '과학기술정보통신부'}]
    monkeypatch.setattr(market, 'ROOT', tmp_path)
    monkeypatch.setattr(market, 'LEDGER', tmp_path / 'history.json')
    monkeypatch.setattr(market, 'LATEST_LISTING_SELECTION', True)
    monkeypatch.setattr(market.latest_listings, 'collect', lambda category, now: list(listing))
    monkeypatch.setattr(market, 'fetch_source', lambda url, *a, **k: dict(page) if url == page['url'] else None)
    # The latest path never measures demand; an empty measured pool keeps the
    # evergreen fallback (run only when no latest issue passes) from selecting.
    monkeypatch.setattr(market, 'demand_candidates', lambda seeds: {})
    monkeypatch.setattr(market.latest_issues, 'discover', lambda *a, **kw: ([], {'status': 'test'}))
    monkeypatch.setattr(market, 'discover_youtube', lambda *a: ([], {'status': 'test'}))
    monkeypatch.setattr(market, 'merge_cak_candidates', lambda stats, *a: (stats, {'direct_count': 0}))
    for name in ('search_results', 'candidate_sources', 'fetch_trend_change'):
        monkeypatch.setattr(market, name, Mock(side_effect=AssertionError(name + ' must not run')))
    state = {'is_new_event': True}
    def ask(prompt):
        if '검색어를 최대 6개 추출하세요' in prompt:
            return {'candidates': [{'keyword': '새에이전트', 'source_index': 0}]}
        if '최신 이슈 발행 필수 심사입니다' in prompt:
            return verdict(event_date=today.isoformat(), date_quote=today.isoformat(),
                           is_new_event=state['is_new_event'])
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


def test_listing_issue_is_selected_without_search_volume_and_enqueued(listing_case):
    report = market.select_category('테크', top_n=1, titles=[])
    assert len(report['selected']) == 1, report['candidate_decisions']
    row = report['selected'][0]
    assert row['monthly_search'] is None and row['demand_scope'] == 'latest_issue_exempt'
    assert row['evidence_mode'] == 'latest_issue' and row['organic_results'] == []
    assert row['latest_issue_listing']['publisher'] == '과학기술정보통신부'
    assert market.fresh_market_item(row, '테크')
    assert market.enqueue_report([], report) == [row]
    assert report['selection_scope'] == 'latest_issue_listing'


def test_listing_issue_that_is_not_new_is_held(listing_case):
    listing_case['is_new_event'] = False
    report = market.select_category('테크', top_n=1, titles=[])
    assert not report['selected']
    # No measured evergreen candidate either: the latest diagnostics are kept as the report.
    assert any('not_a_current_issue' in row['hold_reasons'] for row in report['held'])
    assert report['evergreen_fallback_error']


def test_listing_without_window_items_records_the_attempt_before_evergreen_fallback(listing_case, monkeypatch):
    monkeypatch.setattr(market.latest_listings, 'collect', lambda category, now: [])
    report = market.select_category('테크', top_n=1, titles=[])
    assert report['research_stop_reason'] == 'no_latest_listing_items'
    assert report['selected'] == [] and report['evergreen_fallback_error']


@pytest.mark.parametrize('change', [
    {'monthly_search': 300}, {'demand_scope': 'keyword_total'}, {'evidence_mode': 'official_pages'},
    {'organic_results': [{'url': 'https://example.org', 'title': 'x', 'snippet': 'y'}]},
    {'score': 999}, {'latest_issue_listing': None}])
def test_exempt_latest_item_cannot_be_relabelled_or_tampered(listing_case, change):
    row = market.select_category('테크', top_n=1, titles=[])['selected'][0]
    assert not market.fresh_market_item({**row, **change}, '테크')


def test_evergreen_item_cannot_claim_the_latest_demand_exemption(monkeypatch):
    from tests.test_market_topics import candidate
    monkeypatch.setattr(market.latest_issues, 'issues', lambda *a, **k: [])  # isolate the demand gate
    row = candidate()
    assert market.fresh_market_item(row, '취업')
    assert not market.fresh_market_item({**row, 'demand_scope': 'latest_issue_exempt'}, '취업')
    assert not market.fresh_market_item({**row, 'monthly_search': None}, '취업')


def test_final_intent_review_accepts_a_latest_brief_without_search_evidence(listing_case):
    from src import market_opportunity
    row = market.select_category('테크', top_n=1, titles=[])['selected'][0]
    prompts = []
    def llm(prompt):
        prompts.append(prompt)
        return json.dumps({'covers_primary_intent': False, 'answer_quote': '', 'facet_reviews': []})
    html = '<p>' + EVENT + '</p>'
    market_opportunity.review_article(row['topic'], html, row['intent'], row, llm)
    assert prompts, 'a latest brief must reach the final intent review, not fail as invalid input'
    assert json.loads(prompts[0].split('\n', 1)[1])['search_evidence'] == []


def test_writer_demand_gate_is_skipped_only_for_a_latest_issue_brief(listing_case, monkeypatch, mock_env_vars):
    from src import pipeline as module
    from src.pipeline import BlogPipeline, PipelineConfig
    from src.trend_detector import Topic, TrendSource
    row = market.select_category('테크', top_n=1, titles=[])['selected'][0]
    gate = Mock(return_value={'verdict': 'skip', 'reason': '월 검색량 0회'})
    monkeypatch.setattr(module, 'evaluate_keyword', gate)
    pipeline = BlogPipeline(PipelineConfig(mode='general', category='테크', auto_publish=True, use_llm_topics=False))
    pipeline.content_generator = Mock()
    pipeline.content_generator.generate.side_effect = RuntimeError('reached writer')
    topic = Topic(topic=row['topic'], keywords=row['keywords'], source=TrendSource.HACKER_NEWS,
                  score=100, suggested_title=row['topic'], category='테크')
    result = pipeline._process_topic(topic, market_brief=row)
    gate.assert_not_called()
    assert '검색 수요 부족' not in (result.error or '')
    evergreen = pipeline._process_topic(topic)
    assert '검색 수요 부족' in evergreen.error


@pytest.mark.parametrize('kind', ['unknown', 'trending', 'evergreen'])
def test_latest_issue_timeliness_is_delegated_to_the_event_gate(listing_case, monkeypatch, kind):
    # E2E 37880177007: an OpenAI announcement was held as unverified_current_relevance
    # because the reviewer has no "news" kind and answered unknown.
    original = market.suitability.review_plan
    def plan(candidate, now, _):
        quote = candidate['verified_sources'][0]['excerpt']
        return original(candidate, now, lambda _: {
            'scope': 'full_keyword', 'target_keyword': candidate['keyword'],
            'sources': [{'source_index': 0, 'quote': quote, 'entity': '새에이전트', 'context': 'system_rules'}],
            'required_facets': [{'facet': candidate['intent'], 'answer': EVENT, 'supported': True, 'source_index': 0, 'quote': quote}],
            'current_relevance': {'kind': kind, 'source_index': 0, 'quote': quote,
                                  'event_start': None, 'event_end': None, 'date_quote': None}})
    monkeypatch.setattr(market, 'review_plan', plan)
    report = market.select_category('테크', top_n=1, titles=[])
    assert len(report['selected']) == 1, report['held']
    assert market.fresh_market_item(report['selected'][0], '테크')


def test_evergreen_item_still_cannot_use_unknown_relevance():
    from tests.test_topic_suitability import candidate, review, attach
    item = candidate()
    attach(item, review(item, kind='unknown'))
    assert 'unverified_current_relevance' in market.suitability.issues(item, datetime.fromisoformat(item['selected_at']))


# --- Evergreen fallback (user decision 2026-10-09): publish a verified evergreen
# topic only when no latest issue is available; latest stock always comes first.

def test_evergreen_brief_is_not_held_to_the_latest_issue_gate():
    from tests.test_market_topics import candidate
    row = candidate()
    assert not latest.required(row)
    assert market.fresh_market_item(row, '취업')
    assert latest.current_sources_match(row, row['verified_sources'])
    assert latest.review_article('제목', '<p>본문</p>', row, row['verified_sources'], Mock()) == []


def test_latest_brief_still_requires_the_latest_issue_gate(listing_case):
    row = market.select_category('테크', top_n=1, titles=[])['selected'][0]
    assert market.fresh_market_item(row, '테크')
    stale = {**row, 'latest_issue_evidence': {**row['latest_issue_evidence'], 'version': -1}}
    assert not market.fresh_market_item(stale, '테크')


def test_selection_falls_back_to_measured_evergreen_only_when_no_latest_issue(selection_case, monkeypatch):
    monkeypatch.setattr(market, 'LATEST_LISTING_SELECTION', True)
    monkeypatch.setattr(market.latest_listings, 'collect', lambda category, now: [])
    selection_case['is_new_event'] = False  # the measured topic is not a new event
    report = market.select_category('테크', top_n=1, titles=[])
    assert len(report['selected']) == 1, report.get('candidate_decisions')
    row = report['selected'][0]
    assert row['demand_scope'] == 'keyword_total' and 'latest_issue_evidence' not in row
    assert market.fresh_market_item(row, '테크')
    assert report['latest_issue_attempt']['research_stop_reason'] == 'no_latest_listing_items'


def test_selection_does_not_run_the_evergreen_path_when_a_latest_issue_passed(listing_case, monkeypatch):
    monkeypatch.setattr(market, 'demand_candidates', Mock(side_effect=AssertionError('no evergreen research')))
    report = market.select_category('테크', top_n=1, titles=[])
    assert report['selection_scope'] == 'latest_issue_listing' and report['selected']


def test_one_announcement_yields_at_most_one_candidate(listing_case, monkeypatch):
    # E2E 2026-10-09: one MSIT contest release produced two award posts (Earlibot,
    # Psyco-Neu Vision), and one KCA comparison produced a product-name duplicate.
    original = market.ask
    def ask(prompt):
        if '검색어를 최대 6개 추출하세요' in prompt:
            return {'candidates': [{'keyword': '새에이전트', 'source_index': 0},
                                   {'keyword': '승인 절차', 'source_index': 0}]}
        return original(prompt)
    monkeypatch.setattr(market, 'ask', ask)
    report = market.select_category('테크', top_n=2, titles=[])
    assert [row['keyword'] for row in report['selected']] == ['새에이전트']
    assert any(row['reason'] == 'same announcement already evaluated' for row in report['rejected'])
