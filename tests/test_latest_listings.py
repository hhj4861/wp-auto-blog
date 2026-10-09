"""Dated official listings replace date-operator web search for latest-issue discovery."""
from datetime import date, datetime

from src import latest_listings as listings

NOW = datetime.fromisoformat('2026-10-09T09:00:00+09:00')

KOREA_PAGE = '''<div class="list_type"><ul>
<li><a href="/briefing/pressReleaseView.do?newsId=1&amp;pageIndex=1">
<span class="text"><strong>메틸수은 기준 초과 &#39;수산물가공품&#39; 회수 조치</strong>
<span class="lead">식약처는 해당 제품을 회수한다고 밝혔다.</span>
<span class="source"><span>2026.10.08</span><span>식품의약품안전처</span></span></span></a></li>
<li><a href="/briefing/pressReleaseView.do?newsId=2&amp;pageIndex=1">
<span class="text"><strong>외교부 공관장 인사</strong><span class="lead">붙임 참조</span>
<span class="source"><span>2026.10.08</span><span>외교부</span></span></span></a></li>
<li><a href="/briefing/pressReleaseView.do?newsId=3&amp;pageIndex=1">
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


def test_korea_press_rows_carry_absolute_url_title_department_and_date():
    rows = listings.parse_korea_press(KOREA_PAGE)
    assert rows[0] == {'url': 'https://www.korea.kr/briefing/pressReleaseView.do?newsId=1',
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
    pages = {listings.KOREA_PRESS_URL.format(page=1): KOREA_PAGE,
             listings.KOREA_PRESS_URL.format(page=2): '<ul></ul>'}
    rows = listings.collect('건강', NOW, get_text=lambda url: pages.get(url, ''))
    assert [row['title'] for row in rows] == ["메틸수은 기준 초과 '수산물가공품' 회수 조치"]


def test_collect_stops_paging_once_listing_is_older_than_the_window():
    calls = []
    def get_text(url):
        calls.append(url)
        return KOREA_PAGE  # page already reaches 10/01, older than the window
    listings.collect('건강', NOW, get_text=get_text)
    assert calls == [listings.KOREA_PRESS_URL.format(page=1)]


def test_feed_categories_read_their_newsrooms_and_tolerate_one_failing_source():
    def get_text(url):
        if 'samsung' in url:
            return RSS
        raise OSError('down')
    rows = listings.collect('리뷰', NOW, get_text=get_text)
    assert [row['url'] for row in rows] == ['https://news.samsung.com/kr/new']


def test_every_category_has_dated_official_sources():
    assert set(listings.SOURCES) == {'생활정보', '취업', '건강', '생산성', '리뷰', '테크'}
