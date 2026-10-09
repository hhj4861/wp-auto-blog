"""Dated official listings for latest-issue discovery.

The web search provider ignores date operators, so "what was announced
yesterday or today" comes from official listings that carry their own
publication date: the government policy-news list (with the issuing
ministry) and official newsroom feeds. Listings only locate candidates;
the latest-issue review still grounds the event and date in the fetched body.
"""
from datetime import datetime
from email.utils import parsedate_to_datetime
import html
import re

import requests

from src import source_tls
from src.latest_issues import KST, window

# Policy news articles carry a full HTML body; press-release bodies are read from
# their HWPX attachments by editorial.fetch_source.
KOREA_NEWS_URL = 'https://www.korea.kr/news/policyNewsList.do?pageIndex={page}'
KOREA_PRESS_URL = 'https://www.korea.kr/briefing/pressReleaseList.do?pageIndex={page}'
MAX_KOREA_PAGES = 6
# Ministry of Employment and Labor press list: view pages carry the HTML body.
MOEL_PRESS_URL = 'https://www.moel.go.kr/news/enews/report/enewsList.do'
# Korea Consumer Agency press releases include dated product quality comparisons.
KCA_PRESS_URL = 'https://www.kca.go.kr/home/sub.do?menukey=4002'
FEEDS = {
    'samsung_newsroom': 'https://news.samsung.com/kr/feed',
    'apple_newsroom': 'https://www.apple.com/kr/newsroom/rss-feed.rss',
    'google_korea_blog': 'https://blog.google/intl/ko-kr/rss/',
    'openai_news': 'https://openai.com/news/rss.xml',
    'google_workspace_updates': 'https://workspaceupdates.googleblog.com/feeds/posts/default',
    'skhynix_newsroom': 'https://news.skhynix.co.kr/feed/',
}
# Ministries whose announcements answer each category's reader questions.
SOURCES = {
    '건강': {'press': ('보건복지부', '질병관리청', '식품의약품안전처')},
    '취업': {'press': ('고용노동부', '인사혁신처'), 'moel': True},
    '생활정보': {'press': ('국토교통부', '국세청', '행정안전부', '금융위원회', '공정거래위원회',
                       '재정경제부', '기획재정부', '보건복지부', '기후에너지환경부', '환경부',
                       '국가보훈부', '성평등가족부', '경찰청', '관세청')},
    '테크': {'press': ('과학기술정보통신부',),
             'feeds': ('openai_news', 'google_korea_blog', 'samsung_newsroom', 'skhynix_newsroom')},
    # Feature releases of work tools, not vendor customer stories.
    '생산성': {'feeds': ('google_workspace_updates', 'google_korea_blog')},
    '리뷰': {'kca': True, 'feeds': ('samsung_newsroom', 'apple_newsroom')},
}


def _text(fragment):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', fragment or ''))).strip()


def parse_korea_news(page):
    rows = []
    for path, href, body in re.findall(r'<a href="(/news/policyNewsView\.do|/briefing/pressReleaseView\.do)(\?[^"]+)"[^>]*>(.*?)</a>', page, re.S):
        news_id = re.search(r'newsId=(\d+)', href)
        title = re.search(r'<strong>(.*?)</strong>', body, re.S)
        lead = re.search(r'<span class="lead">(.*?)</span>', body, re.S)
        source = re.search(r'<span class="source">\s*<span>(.*?)</span>\s*<span>(.*?)</span>', body, re.S)
        if not news_id or not title or not source:
            continue
        source = source.groups()
        try:
            published = datetime.strptime(_text(source[0]), '%Y.%m.%d').date()
        except ValueError:
            continue
        rows.append({'url': f'https://www.korea.kr{path}?newsId={news_id.group(1)}',
                     'title': _text(title.group(1)), 'lead': _text(lead.group(1) if lead else ''),
                     'published': published, 'publisher': _text(source[1])})
    return rows


def parse_moel_press(page):
    rows = []
    for row in re.findall(r'<tr>(.*?)</tr>', page, re.S):
        link = re.search(r'<a href="enewsView\.do\?news_seq=(\d+)"[^>]*>(.*?)</a>', row, re.S)
        day = re.search(r'aria-label="등록일">\s*(\d{4}\.\d{2}\.\d{2})\s*<', row)
        if not link or not day:
            continue
        rows.append({'url': f'https://www.moel.go.kr/news/enews/report/enewsView.do?news_seq={link.group(1)}',
                     'title': _text(link.group(2)), 'lead': '',
                     'published': datetime.strptime(day.group(1), '%Y.%m.%d').date(), 'publisher': '고용노동부'})
    return rows


def parse_kca_press(page):
    rows = []
    for row in re.findall(r'<tr>(.*?)</tr>', page, re.S):
        link = re.search(r'<a href="\?menukey=4002&amp;mode=view&amp;no=(\d+)"[^>]*>(.*?)</a>', row, re.S)
        day = re.search(r'<td class="b_date">\s*(\d{4}-\d{2}-\d{2})\s*</td>', row)
        if not link or not day:
            continue
        rows.append({'url': f'{KCA_PRESS_URL}&mode=view&no={link.group(1)}', 'title': _text(link.group(2)),
                     'lead': '', 'published': datetime.strptime(day.group(1), '%Y-%m-%d').date(),
                     'publisher': '한국소비자원'})
    return rows


def _feed_date(value):
    value = (value or '').strip()
    try:
        stamp = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            return None
    return stamp.astimezone(KST).date() if stamp.tzinfo else None


def parse_feed(document, publisher):
    rows = []
    for item in re.findall(r'<(item|entry)\b[^>]*>(.*?)</\1>', document, re.S):
        body = item[1]
        title = re.search(r'<title[^>]*>(.*?)</title>', body, re.S)
        # RSS <link>url</link>, or the Atom alternate (article) link, either quote style.
        atom_links = re.findall(r'<link\b([^>]*)/?>', body)
        alternate = next((re.search(r'href=[\'"]([^\'"]+)', attrs) for attrs in atom_links
                          if re.search(r'href=', attrs) and (not re.search(r'rel=', attrs)
                                                              or re.search(r'rel=[\'"]alternate', attrs))), None)
        link = re.search(r'<link>(.*?)</link>', body, re.S) or alternate
        stamp = re.search(r'<(pubDate|published|updated)>(.*?)</\1>', body, re.S)
        summary = re.search(r'<(description|summary)[^>]*>(.*?)</\1>', body, re.S)
        clean = lambda value: _text(re.sub(r'<!\[CDATA\[|\]\]>', '', value))
        published = _feed_date(stamp.group(2)) if stamp else None
        if not title or not link or not published:
            continue
        url = clean(link.group(1))
        if url.startswith('http://'):
            url = 'https://' + url[len('http://'):]  # feeds list http; fetch over verified HTTPS
        rows.append({'url': url, 'title': clean(title.group(1)),
                     'lead': clean(summary.group(2)) if summary else '',
                     'published': published, 'publisher': publisher})
    return rows


def _get_text(url):
    # source_tls keeps full verification and pins the intermediate missing from kca.go.kr.
    response = source_tls.get(url, timeout=20, headers={'User-Agent': 'Mozilla/5.0 (TrendPulse latest issues)'})
    response.raise_for_status()
    return response.text


def collect(category, now, *, get_text=_get_text):
    """Window items from the category's official publishers; a failing source is skipped."""
    start, end = window(now)
    in_window = lambda row: start.date() <= row['published'] <= end.date()
    config, rows = SOURCES[category], []
    publishers = set(config.get('press', ()))
    for list_url in (KOREA_PRESS_URL, KOREA_NEWS_URL) if publishers else ():
        for page in range(1, MAX_KOREA_PAGES + 1):
            try:
                listed = parse_korea_news(get_text(list_url.format(page=page)))
            except (OSError, requests.RequestException):
                break
            rows.extend(row for row in listed if row['publisher'] in publishers and in_window(row))
            # The list is newest first: stop once it reaches days before the window.
            if not listed or min(row['published'] for row in listed) < start.date():
                break
    if config.get('moel'):
        try:
            rows.extend(row for row in parse_moel_press(get_text(MOEL_PRESS_URL)) if in_window(row))
        except (OSError, requests.RequestException):
            pass
    if config.get('kca'):
        try:
            rows.extend(row for row in parse_kca_press(get_text(KCA_PRESS_URL)) if in_window(row))
        except (OSError, requests.RequestException):
            pass
    for name in config.get('feeds', ()):
        try:
            rows.extend(row for row in parse_feed(get_text(FEEDS[name]), name) if in_window(row))
        except (OSError, requests.RequestException):
            continue
    unique = {}
    for row in rows:
        unique.setdefault(row['url'], row)
    return list(unique.values())
