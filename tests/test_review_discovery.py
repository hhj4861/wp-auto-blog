from hashlib import sha256
import json
from unittest.mock import Mock

import pytest

from src import market_topics as market
from src import review_discovery as review
from tests.test_selection_feedback import install_selection
from tests.test_market_topics import isolated_market_history


@pytest.mark.parametrize('keyword', [
    '청소기', '미세먼지', '캠핑용품', '로봇청소기', '무선청소기', '삼성노트북',
    '공기청정기렌탈', '원룸청소기', '스팀물걸레청소기', '차량용무선청소기',
    '가습기공기청정기', '공기청정기', '선풍기', '로보락로봇청소기', '물걸레청소기',
    '게이밍노트북', '사무용노트북', '리퍼노트북', '유선청소기', '베이크아웃방법',
    'LG그램', '무선청소기필터교체방법', '노트북램고장',
])
def test_previous_failed_or_maintenance_terms_are_not_buying_questions(keyword):
    assert review.discovery_issue(keyword)


@pytest.mark.parametrize('keyword', [*review.SEEDS, '노트북램16기가32기가차이',
    'LG그램메모리', '갤럭시북배터리사용시간', '공기청정기필터비교', '모니터주사율차이'])
def test_measured_product_questions_can_enter_existing_semantic_gates(keyword):
    assert review.discovery_issue(keyword) is None


def source(url, body, title='제품 사양'):
    return {'url': url, 'title': title, 'excerpt': body,
            'sha256': sha256(body.encode()).hexdigest()}


@pytest.mark.parametrize('bad', [
    None, {}, {'title': None, 'excerpt': None}, {'url': ['bad']},
    source('https://www.lg.com/us/support/help-library/poor-suction', 'vacuum suction repair'),
    source('https://www.samsung.com/sec/speaker', '갤럭시 홈 미니 사용시간과 필터'),
    source('https://www.consumer.go.kr/selectCrtfcInfo', '무선청소기 흡입력 인증 목록'),
    source('https://www.samsung.com/sec/vacuum', '매장 안내', '무선청소기 흡입력'),
])
def test_irrelevant_pages_never_consume_vacuum_purchase_source_slots(bad):
    assert not review.relevant_source('무선청소기흡입력', bad)


def test_source_requires_every_requested_facet_and_ignores_gram_ram_collision():
    assert not review.relevant_source('노트북램', source('https://lg.com/kr/gram', 'LG 그램 노트북 프로그램 안내'))
    assert not review.relevant_source('노트북램배터리', source('https://lg.com/kr/gram', 'LG 그램 노트북 메모리 16GB'))
    assert review.relevant_source('노트북램배터리', source('https://lg.com/kr/gram', 'LG 그램 노트북 메모리 16GB 배터리 사용시간'))


def test_official_research_uses_domestic_product_scopes_and_keeps_later_urls(monkeypatch):
    queries = []
    def search(query):
        queries.append(query)
        if 'site:samsung.com/sec' in query:
            return 'test', [{'url': f'https://www.samsung.com/sec/vacuums/model{i}'} for i in range(4)] + [
                {'url': 'https://www.samsung.com/us/vacuums/other'},
                {'url': 'https://www.samsung.com.evil.example/sec/vacuums'}]
        if 'site:lg.com/kr' in query:
            return 'test', [{'url': f'https://www.lg.com/kr/vacuum-cleaners/{i}'} for i in range(4)]
        return 'test', [{'url': 'https://www.kca.go.kr/test/cleaner'}]
    monkeypatch.setattr(market, 'search_results', search)
    urls = market.official_search_urls('무선청소기흡입력')
    assert len(urls) == 9
    assert '/sec/' in urls[0] and '/kr/' in urls[1] and 'kca.go.kr' in urls[2]
    assert all('/us/' not in url and 'evil' not in url for url in urls)
    assert queries == ['무선청소기흡입력 제품 사양 site:samsung.com/sec',
                       '무선청소기흡입력 제품 사양 site:lg.com/kr',
                       '무선청소기흡입력 제품 사양 site:kca.go.kr']


def test_unrelated_sources_do_not_hide_later_fetched_product_evidence(monkeypatch):
    urls = [f'https://www.samsung.com/sec/product/{i}' for i in range(8)]
    bodies = [source(url, f'갤럭시 홈 미니 도움말 {i}') for i, url in enumerate(urls[:5])]
    bodies += [source(url, f'무선청소기 흡입력 시험 조건 제품 {i}') for i, url in enumerate(urls[5:])]
    fetch = Mock(side_effect=lambda url: bodies[urls.index(url)])
    monkeypatch.setattr(market, 'fetch_source', fetch)
    monkeypatch.setattr(market, 'official_search_urls', lambda _: urls[2:])
    assert market.candidate_sources('무선청소기흡입력', [{'url': url} for url in urls[:2]], category='리뷰') == bodies[5:]
    assert fetch.call_count == 8


def test_native_research_rechecks_source_body_and_ignores_model_excerpt(monkeypatch):
    from types import SimpleNamespace
    bad = source('https://www.samsung.com/sec/speaker', '갤럭시 홈 미니 연결 방법')
    good = source('https://www.lg.com/kr/vacuum/spec', '무선청소기 흡입력 시험 조건')
    research = Mock(return_value={'searched': True, 'opened_urls': [bad['url']],
        'text': json.dumps({'candidate_urls': [good['url']], 'excerpt': '무선청소기 흡입력'})})
    monkeypatch.setattr('src.codex_client.CodexSubscriptionClient',
                        lambda **kw: SimpleNamespace(research=research))
    monkeypatch.setattr(market, 'fetch_source', lambda url: bad if url == bad['url'] else good)
    sources, trace = market.research_official_sources('무선청소기흡입력', '리뷰', '2026-09-29')
    assert sources == [{**good, 'locator_origin': 'model_reported_locator'}]
    assert len(trace['locators']) == 2
    assert '흡입력' in research.call_args.args[0] and '시험 조건' in research.call_args.args[0]


def test_broad_measured_terms_cannot_reach_search_or_shortlist(monkeypatch):
    broad, good = ['청소기', '미세먼지', '캠핑용품'], '노트북램16기가32기가차이'
    stats, search, offered = install_selection(monkeypatch, broad + [good], passing=[good])
    report = market.select_category('리뷰', 1, [])
    assert offered == [[good]]
    search.assert_called_once_with(good)
    assert {row['keyword'] for row in report['discovery_rejections']} == set(broad)
    assert report['selected'][0]['monthly_search'] == stats[good]['monthly']
    assert market.fresh_market_item(report['selected'][0], '리뷰')


def test_all_broad_terms_leave_auditable_report_without_forced_selection(monkeypatch):
    _, search, offered = install_selection(monkeypatch, ['청소기', '미세먼지', '캠핑용품'])
    report = market.select_category('리뷰', 1, [])
    search.assert_not_called()
    assert not offered and not report['selected']
    assert len(report['discovery_rejections']) == 3
    with pytest.raises(RuntimeError):
        market.enqueue_report([], report)


@pytest.mark.parametrize('keyword', ['흡입력좋은청소기', '소음적은청소기추천', '노트북램가성비순위'])
def test_facet_does_not_make_unbounded_recommendation_publishable(keyword):
    assert review.discovery_issue(keyword) == 'review_recommendation_unbounded'


def test_catalog_url_cannot_supply_comparison_evidence():
    assert not review.relevant_source('노트북메모리', source(
        'https://www.samsung.com/sec/memory-storage/all-memory-storage/', '노트북 메모리 16GB'))


def test_robot_research_includes_two_manufacturers_and_consumer_agency(monkeypatch):
    hosts = ['kr.roborock.com', 'store.kr.dreametech.com', 'samsung.com/sec', 'kca.go.kr']
    queries = []
    def search(query):
        queries.append(query)
        host = query.split('site:', 1)[1]
        return 'test', [{'url': f'https://{host}/products/{i}'} for i in range(4)]
    monkeypatch.setattr(market, 'search_results', search)
    urls = market.official_search_urls('로봇청소기문턱')
    assert queries == [f'로봇청소기문턱 제품 사양 site:{host}' for host in hosts]
    assert urls[:4] == [f'https://{host}/products/0' for host in hosts]
    assert len(urls) == 12
    for host in hosts[:2]:
        assert market.is_official_url('https://' + host + '/products/test')
        assert not market.is_official_url('https://' + host + '.evil.example/products/test')
        assert review.relevant_source('로봇청소기문턱', source(
            'https://' + host + '/products/test', '로봇청소기 문턱 시험 조건'))
