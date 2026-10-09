"""Dated official listings for latest-issue discovery.

The web search provider ignores date operators, so "what was announced
yesterday or today" comes from official listings that carry their own
publication date: the government press-release list (with the issuing
ministry) and official newsroom feeds. Listings only locate candidates;
the latest-issue review still grounds the event and date in the fetched body.
"""
from datetime import datetime
from email.utils import parsedate_to_datetime
import html
import re

import requests

from src.latest_issues import KST, window

KOREA_PRESS_URL = 'https://www.korea.kr/briefing/pressReleaseList.do?pageIndex={page}'
MAX_KOREA_PAGES = 6
FEEDS = {
    'samsung_newsroom': 'https://news.samsung.com/kr/feed',
    'apple_newsroom': 'https://www.apple.com/kr/newsroom/rss-feed.rss',
    'google_korea_blog': 'https://blog.google/intl/ko-kr/rss/',
    'openai_news': 'https://openai.com/news/rss.xml',
}
# Ministries whose announcements answer each category's reader questions.
SOURCES = {
    '건강': {'press': ('보건복지부', '질병관리청', '식품의약품안전처')},
    '취업': {'press': ('고용노동부', '인사혁신처')},
    '생활정보': {'press': ('국토교통부', '국세청', '행정안전부', '금융위원회', '공정거래위원회',
                       '재정경제부', '기획재정부', '보건복지부', '기후에너지환경부', '환경부',
                       '국가보훈부', '성평등가족부', '경찰청', '관세청')},
    '테크': {'press': ('과학기술정보통신부',),
             'feeds': ('openai_news', 'google_korea_blog', 'samsung_newsroom')},
    '생산성': {'feeds': ('google_korea_blog', 'openai_news')},
    '리뷰': {'feeds': ('samsung_newsroom', 'apple_newsroom')},
}


def _text(fragment):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', fragment or ''))).strip()


def parse_korea_press(page):
    rows = []
    for href, body in re.findall(r'<a href="(/briefing/pressReleaseView\.do\?[^"]+)"[^>]*>(.*?)</a>', page, re.S):
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
        rows.append({'url': f'https://www.korea.kr/briefing/pressReleaseView.do?newsId={news_id.group(1)}',
                     'title': _text(title.group(1)), 'lead': _text(lead.group(1) if lead else ''),
                     'published': published, 'publisher': _text(source[1])})
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
        link = (re.search(r'<link>(.*?)</link>', body, re.S)
                or re.search(r'<link[^>]*href="([^"]+)"', body))
        stamp = re.search(r'<(pubDate|published|updated)>(.*?)</\1>', body, re.S)
        summary = re.search(r'<(description|summary)[^>]*>(.*?)</\1>', body, re.S)
        clean = lambda value: _text(re.sub(r'<!\[CDATA\[|\]\]>', '', value))
        published = _feed_date(stamp.group(2)) if stamp else None
        if not title or not link or not published:
            continue
        rows.append({'url': clean(link.group(1)), 'title': clean(title.group(1)),
                     'lead': clean(summary.group(2)) if summary else '',
                     'published': published, 'publisher': publisher})
    return rows


def _get_text(url):
    response = requests.get(url, timeout=20, headers={'User-Agent': 'Mozilla/5.0 (TrendPulse latest issues)'})
    response.raise_for_status()
    return response.text


def collect(category, now, *, get_text=_get_text):
    """Window items from the category's official publishers; a failing source is skipped."""
    start, end = window(now)
    in_window = lambda row: start.date() <= row['published'] <= end.date()
    config, rows = SOURCES[category], []
    publishers = set(config.get('press', ()))
    if publishers:
        for page in range(1, MAX_KOREA_PAGES + 1):
            try:
                listed = parse_korea_press(get_text(KOREA_PRESS_URL.format(page=page)))
            except (OSError, requests.RequestException):
                break
            rows.extend(row for row in listed if row['publisher'] in publishers and in_window(row))
            # The list is newest first: stop once it reaches days before the window.
            if not listed or min(row['published'] for row in listed) < start.date():
                break
    for name in config.get('feeds', ()):
        try:
            rows.extend(row for row in parse_feed(get_text(FEEDS[name]), name) if in_window(row))
        except (OSError, requests.RequestException):
            continue
    unique = {}
    for row in rows:
        unique.setdefault(row['url'], row)
    return list(unique.values())
