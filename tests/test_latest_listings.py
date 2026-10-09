"""Dated official listings replace date-operator web search for latest-issue discovery."""
from datetime import date, datetime

from src import latest_listings as listings

NOW = datetime.fromisoformat('2026-10-09T09:00:00+09:00')

KOREA_PAGE = '''<div class="list_type"><ul>
<li><a href="/news/policyNewsView.do?newsId=1&amp;pageIndex=1">
<span class="text"><strong>메틸수은 기준 초과 &#39;수산물가공품&#39; 회수 조치</strong>
<span class="lead">식약처는 해당 제품을 회수한다고 밝혔다.</span>
<span class="source"><span>2026.10.08</span><span>식품의약품안전처</span></span></span></a></li>
<li><a href="/news/policyNewsView.do?newsId=2&amp;pageIndex=1">
<span class="text"><strong>외교부 공관장 인사</strong><span class="lead">붙임 참조</span>
<span class="source"><span>2026.10.08</span><span>외교부</span></span></span></a></li>
<li><a href="/news/policyNewsView.do?newsId=3&amp;pageIndex=1">
<span class="text"><strong>지난주 질병 발표</strong><span class="lead">과거</span>
<span class="source"><span>2026.10.01</span><span>질병관리청</span></span></span></a></li>
</ul></div>'''

RSS = '''<rss><channel>
<item><title><![CDATA[갤럭시 신제품 공개]]></title><link>https://news.samsung.com/kr/new</link>
<pubDate>Thu, 08 Oct 2026 07:46:00 +0000</pubDate><description>삼성전자가 공개했다</description></item>
<item><title>지난 행사</title><link>https://news.samsung.com/kr/old</link>
<pubDate>Tue, 06 Oct 2026 08:00:00 +0000</pubDate></item>
</channel></rss>'''

ATOM = '''<feed><entry><title>새 기능</title><link href="https://www.apple.com/kr/newsroom/2026/10/x/"/>
<updated>2026-10-08T21:00:00-07:00</updated><summary>요약</summary></entry></feed>'''


def test_korea_news_rows_carry_absolute_url_title_department_and_date():
    # Press-release pages keep the body in a scripted document viewer (attachments);
    # policy news articles carry the full HTML body that fetch_source can ground.
    rows = listings.parse_korea_news(KOREA_PAGE)
    assert rows[0] == {'url': 'https://www.korea.kr/news/policyNewsView.do?newsId=1',
                       'title': "메틸수은 기준 초과 '수산물가공품' 회수 조치",
                       'lead': '식약처는 해당 제품을 회수한다고 밝혔다.',
                       'published': date(2026, 10, 8), 'publisher': '식품의약품안전처'}
    assert [row['publisher'] for row in rows] == ['식품의약품안전처', '외교부', '질병관리청']


def test_rss_and_atom_entries_use_kst_publication_dates():
    rss = listings.parse_feed(RSS, 'samsung_newsroom')
    assert rss[0]['url'] == 'https://news.samsung.com/kr/new' and rss[0]['title'] == '갤럭시 신제품 공개'
    assert rss[0]['published'] == date(2026, 10, 8) and rss[0]['publisher'] == 'samsung_newsroom'
    # 21:00 PDT on Oct 8 is 13:00 KST on Oct 9.
    assert listings.parse_feed(ATOM, 'apple_newsroom')[0]['published'] == date(2026, 10, 9)


def test_collect_keeps_only_window_items_from_category_publishers(monkeypatch):
    pages = {listings.KOREA_NEWS_URL.format(page=1): KOREA_PAGE,
             listings.KOREA_NEWS_URL.format(page=2): '<ul></ul>'}
    rows = listings.collect('건강', NOW, get_text=lambda url: pages.get(url, ''))
    assert [row['title'] for row in rows] == ["메틸수은 기준 초과 '수산물가공품' 회수 조치"]


def test_collect_stops_paging_once_listing_is_older_than_the_window():
    calls = []
    def get_text(url):
        calls.append(url)
        return KOREA_PAGE  # page already reaches 10/01, older than the window
    listings.collect('건강', NOW, get_text=get_text)
    # Each list (press releases, policy news) stops after its first page.
    assert calls == [listings.KOREA_PRESS_URL.format(page=1), listings.KOREA_NEWS_URL.format(page=1)]


def test_feed_categories_read_their_newsrooms_and_tolerate_one_failing_source():
    def get_text(url):
        if 'samsung' in url:
            return RSS
        raise OSError('down')
    rows = listings.collect('리뷰', NOW, get_text=get_text)
    assert [row['url'] for row in rows] == ['https://news.samsung.com/kr/new']


def test_every_category_has_dated_official_sources():
    assert set(listings.SOURCES) == {'생활정보', '취업', '건강', '생산성', '리뷰', '테크'}


KCA_PAGE = '''<table class="board m_board"><tbody>
<tr><td class="brd_none b_num">3725</td><td class="title">
<a href="?menukey=4002&amp;mode=view&amp;no=1004568797" class="title" style="">[화장실용 화장지 품질비교 결과] 흡수성은 모든 제품이 우수하고, 물풀림성도 향상돼&nbsp;<img src='/new.gif' alt='새글' /></a>
</td><td class="b_write">섬유신소재팀</td><td class="b_date">2026-10-08</td><td class="b_hit">199</td></tr>
<tr><td class="brd_none b_num">3720</td><td class="title">
<a href="?menukey=4002&amp;mode=view&amp;no=1004500000" class="title">[지난 시험] 예전 결과</a>
</td><td class="b_write">시험팀</td><td class="b_date">2026-10-01</td><td class="b_hit">776</td></tr>
</tbody></table>'''


def test_consumer_agency_product_tests_are_dated_review_sources():
    rows = listings.parse_kca_press(KCA_PAGE)
    assert rows[0] == {'url': 'https://www.kca.go.kr/home/sub.do?menukey=4002&mode=view&no=1004568797',
                       'title': '[화장실용 화장지 품질비교 결과] 흡수성은 모든 제품이 우수하고, 물풀림성도 향상돼',
                       'lead': '', 'published': date(2026, 10, 8), 'publisher': '한국소비자원'}
    def get_text(url):
        if url == listings.KCA_PRESS_URL:
            return KCA_PAGE
        raise OSError('feeds down')
    assert [row['url'] for row in listings.collect('리뷰', NOW, get_text=get_text)] == [rows[0]['url']]


def test_productivity_uses_workspace_feature_updates_not_customer_stories():
    assert 'google_workspace_updates' in listings.SOURCES['생산성']['feeds']
    assert 'openai_news' not in listings.SOURCES['생산성']['feeds']
    assert 'skhynix_newsroom' in listings.SOURCES['테크']['feeds']


def test_every_listed_feed_is_an_official_publisher():
    from src.editorial import is_official_url
    samples = {'samsung_newsroom': 'https://news.samsung.com/kr/x', 'apple_newsroom': 'https://www.apple.com/kr/newsroom/x',
               'google_korea_blog': 'https://blog.google/intl/ko-kr/x/', 'openai_news': 'https://openai.com/index/x/',
               'google_workspace_updates': 'https://workspaceupdates.googleblog.com/2026/10/x.html',
               'skhynix_newsroom': 'https://news.skhynix.co.kr/x/'}
    assert set(samples) == set(listings.FEEDS)
    assert all(is_official_url(url) for url in samples.values())
    # Exact hosts only: an arbitrary blog on the same platform is not official.
    assert not is_official_url('https://someone.googleblog.com/x.html')


BLOGGER = """<feed><entry><published>2026-10-08T08:34:24.249-07:00</published>
<title type='text'>Carrier Link for Google Voice</title>
<link rel='replies' type='application/atom+xml' href='https://workspaceupdates.googleblog.com/feeds/1/comments/default'/>
<link rel='alternate' type='text/html' href='http://workspaceupdates.googleblog.com/2026/10/carrier-link.html'/>
</entry></feed>"""


def test_blogger_atom_uses_the_alternate_article_link_with_single_quotes():
    row = listings.parse_feed(BLOGGER, 'google_workspace_updates')[0]
    assert row['url'] == 'https://workspaceupdates.googleblog.com/2026/10/carrier-link.html'
    assert row['published'] == date(2026, 10, 9)  # 08:34 PDT = 00:34 KST next day


def test_consumer_agency_listing_uses_the_pinned_chain_fetcher(monkeypatch):
    calls = []
    class Response:
        text = 'ok'
        def raise_for_status(self): pass
    monkeypatch.setattr(listings.source_tls, 'get', lambda url, **kw: calls.append(url) or Response())
    assert listings._get_text(listings.KCA_PRESS_URL) == 'ok'
    assert calls == [listings.KCA_PRESS_URL]


MOEL_PAGE = '''<table class="tstyle_list"><tbody>
<tr><td class="m_hidden" aria-label="번호">16079</td><td class="txt_left" aria-label="제목"><strong class="b_tit">
<a href="enewsView.do?news_seq=20054" class="ellipsis" onclick="scEventListener.fnView('20054');return false;" title="(참고) 사회적 대화 제3차 실무협의체 개최">(참고) 사회적 대화 제3차 실무협의체 개최</a>
</strong></td><td aria-label="첨부"></td><td aria-label="등록일">2026.10.08</td><td aria-label="조회" class="txt_right">522</td></tr>
<tr><td aria-label="번호">16070</td><td aria-label="제목"><strong class="b_tit"><a href="enewsView.do?news_seq=20040" title="지난 발표">지난 발표</a></strong></td>
<td aria-label="등록일">2026.10.01</td></tr></tbody></table>'''


def test_labor_ministry_press_list_gives_html_body_pages_for_jobs():
    rows = listings.parse_moel_press(MOEL_PAGE)
    assert rows[0] == {'url': 'https://www.moel.go.kr/news/enews/report/enewsView.do?news_seq=20054',
                       'title': '(참고) 사회적 대화 제3차 실무협의체 개최', 'lead': '',
                       'published': date(2026, 10, 8), 'publisher': '고용노동부'}
    assert listings.SOURCES['취업'].get('moel') is True
    pages = {listings.MOEL_PRESS_URL: MOEL_PAGE}
    collected = listings.collect('취업', NOW, get_text=lambda url: pages.get(url, '<ul></ul>'))
    assert [row['url'] for row in collected] == [rows[0]['url']]


def test_korea_reads_both_press_releases_and_policy_news():
    # Press-release bodies are now read from their HWPX attachments (editorial).
    press = KOREA_PAGE.replace('/news/policyNewsView.do?newsId=1&', '/briefing/pressReleaseView.do?newsId=7&')
    rows = listings.parse_korea_news(press)
    assert rows[0]['url'] == 'https://www.korea.kr/briefing/pressReleaseView.do?newsId=7'
    pages = {listings.KOREA_PRESS_URL.format(page=1): press, listings.KOREA_NEWS_URL.format(page=1): KOREA_PAGE}
    urls = [row['url'] for row in listings.collect('건강', NOW, get_text=lambda url: pages.get(url, '<ul></ul>'))]
    assert urls == ['https://www.korea.kr/briefing/pressReleaseView.do?newsId=7',
                    'https://www.korea.kr/news/policyNewsView.do?newsId=1']
