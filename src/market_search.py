"""Read organic result URLs and snippets without inventing search evidence."""

import os
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup
import requests


def result_row(url, title='', snippet=''):
    try:
        parts = urlsplit(url)
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
            return None
        if parts.hostname == 'duckduckgo.com' or parts.hostname.endswith('.duckduckgo.com'):
            return None
        return {'url': url, 'domain': parts.hostname.lower(),
                'title': str(title)[:300], 'snippet': str(snippet)[:1000]}
    except (ValueError, TypeError):
        return None


def search_results(query):
    """Prefer Google CSE; label DuckDuckGo explicitly when it is the fallback.

    Keep separate result positions from the same domain: deduplicating hosts
    would undercount a site occupying several places on the first page.
    """
    key, engine = os.getenv('GOOGLE_SEARCH_API_KEY'), os.getenv('GOOGLE_SEARCH_ENGINE_ID')
    if key and engine:
        try:
            response = requests.get('https://www.googleapis.com/customsearch/v1',
                params={'key': key, 'cx': engine, 'q': query, 'gl': 'kr', 'hl': 'ko', 'num': 10},
                timeout=20)
            response.raise_for_status()
            rows = [result_row(item.get('link'), item.get('title', ''), item.get('snippet', ''))
                    for item in response.json().get('items', [])]
            rows = [row for row in rows if row]
            if rows:
                return 'google_custom_search', rows[:10]
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            pass  # Never log a request URL containing the API key.
    try:
        response = requests.get('https://html.duckduckgo.com/html/',
            params={'q': query, 'kl': 'kr-kr'},
            headers={'User-Agent': 'Mozilla/5.0', 'Accept-Language': 'ko-KR,ko;q=0.9'}, timeout=25)
        response.raise_for_status()
        rows, seen = [], set()
        for anchor in BeautifulSoup(response.text, 'html.parser').select('a.result__a'):
            link = urljoin(response.url, anchor.get('href', ''))
            link = parse_qs(urlsplit(link).query).get('uddg', [link])[0]
            container = anchor.find_parent(class_='result')
            snippet = container.select_one('.result__snippet') if container else None
            row = result_row(link, anchor.get_text(' ', strip=True),
                             snippet.get_text(' ', strip=True) if snippet else '')
            if row and row['url'] not in seen:
                rows.append(row)
                seen.add(row['url'])
        return 'duckduckgo_proxy', rows[:10]
    except (requests.RequestException, ValueError, TypeError):
        return 'duckduckgo_proxy', []
