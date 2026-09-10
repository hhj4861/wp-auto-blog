"""Read organic result URLs and snippets without inventing search evidence."""

import os
import logging
import re
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup
import requests


logger = logging.getLogger(__name__)
GOOGLE_PROJECT_TEMPLATE = 'Google Custom Search diagnostic: project_number=%s'


def _google_error_project_numbers(payload):
    """Read only Custom Search's typed, numeric consumer identifier."""
    error = payload.get('error') if isinstance(payload, dict) else None
    details = error.get('details') if isinstance(error, dict) else None
    if not isinstance(details, list):
        return []
    numbers = []
    for detail in details[:10]:
        if not isinstance(detail, dict) or detail.get('@type') != 'type.googleapis.com/google.rpc.ErrorInfo':
            continue
        metadata = detail.get('metadata')
        if not isinstance(metadata, dict) or metadata.get('service') != 'customsearch.googleapis.com':
            continue
        consumer = metadata.get('consumer')
        match = re.fullmatch(r'projects/([0-9]{1,20})', consumer) if isinstance(consumer, str) else None
        if match and match[1] not in numbers:
            numbers.append(match[1])
    return numbers


def search_failure(provider, response=None, reason='network_error'):
    """Log only fixed reasons/statuses; request URLs can contain API credentials."""
    status = getattr(response, 'status_code', None)
    status = status if type(status) is int else None
    if provider == 'google_custom_search' and response is not None:
        try:
            # Inspect in memory only. Never emit error messages or arbitrary fields.
            payload = response.json()
            detail = str(payload).lower()
            for number in _google_error_project_numbers(payload):
                # The probe captures this separate event; never emit arbitrary metadata.
                logger.debug(GOOGLE_PROJECT_TEMPLATE, number)
            for marker, code in (
                ('accessnotconfigured', 'api_not_enabled'),
                ('service_disabled', 'api_not_enabled'),
                ('api_key_service_blocked', 'api_key_service_blocked'),
                ('iprefererblocked', 'api_key_restricted'),
                ('api_key_http_referrer_blocked', 'api_key_restricted'),
                ('keyinvalid', 'api_key_invalid'),
                ('api_key_invalid', 'api_key_invalid'),
                ('dailylimitexceeded', 'daily_quota_exceeded'),
                ('ratelimitexceeded', 'rate_limit_exceeded'),
                ('quota_exceeded', 'quota_exceeded'),
                ('does not have the access to custom search', 'api_access_unavailable'),
                ('not have access to custom search', 'api_access_unavailable'),
            ):
                if marker in detail:
                    reason = code
                    break
        except (ValueError, TypeError, AttributeError):
            pass
    logger.warning('Search unavailable: provider=%s reason=%s http_status=%s', provider, reason, status)


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
        response = None
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
            search_failure('google_custom_search', response, 'no_results')
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            search_failure('google_custom_search', response,
                           'http_or_response_error' if response is not None else 'network_error')
    else:
        search_failure('google_custom_search', reason='configuration_missing')
    response = None
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
        if not rows:
            challenged = response.status_code == 202 or any(
                marker in response.text for marker in ('anomaly.js', 'id="challenge-form"'))
            search_failure('duckduckgo_proxy', response, 'challenge' if challenged else 'no_results')
        return 'duckduckgo_proxy', rows[:10]
    except (requests.RequestException, ValueError, TypeError):
        search_failure('duckduckgo_proxy', response,
                       'http_or_response_error' if response is not None else 'network_error')
        return 'duckduckgo_proxy', []
