"""IndexNow notifications through one explicitly selected participating endpoint.

Acceptance is a notification receipt, never proof of indexing. Ownership failures
are reported separately from publication, without retrying another provider.
"""
from __future__ import annotations

import os
import re
from urllib.parse import urlsplit, unquote
import posixpath

import requests
from loguru import logger

INDEXNOW_KEY = os.getenv("INDEXNOW_KEY", "413338ab31bcc9bb0ed71149930283af")
INDEXNOW_KEY_LOCATION = os.getenv(
    "INDEXNOW_KEY_LOCATION", "https://trendpulse.blog/413338ab31bcc9bb0ed71149930283af.txt")
# The global endpoint rejects this site's valid public key (403). Naver accepted
# the identical submission; IndexNow participants share received notifications.
INDEXNOW_API = "https://searchadvisor.naver.com/indexnow"
ENDPOINTS = {INDEXNOW_API, "https://api.indexnow.org/indexnow"}
ERROR_CODES = {'UserForbiddedToAccessSite', 'SiteVerificationNotCompleted',
               'InvalidRequest', 'InvalidKey'}


def _same_host_url(url, host):
    if not isinstance(url, str) or re.search(r'[\s\\\x00-\x1f\x7f]', url):
        return False
    try:
        parts = urlsplit(url)
        return (parts.scheme in ('http', 'https') and parts.hostname == host
                and not parts.username and not parts.password and not parts.fragment
                and parts.port in (None, 443 if parts.scheme == 'https' else 80))
    except ValueError:
        return False


def _configuration(host):
    endpoint = os.getenv('INDEXNOW_API', INDEXNOW_API)
    key = os.getenv('INDEXNOW_KEY', INDEXNOW_KEY)
    location = os.getenv('INDEXNOW_KEY_LOCATION', INDEXNOW_KEY_LOCATION)
    if (not isinstance(host, str) or not re.fullmatch(r'[a-z0-9.-]+', host)
            or endpoint not in ENDPOINTS or not re.fullmatch(r'[A-Za-z0-9-]{8,128}', key)
            or not _same_host_url(location, host) or urlsplit(location).query):
        return None
    return endpoint, key, location


def check_key(host='trendpulse.blog'):
    """Bounded public ownership check; a local success is not engine verification."""
    config = _configuration(host)
    if not config:
        return 'invalid_configuration'
    _, key, location = config
    try:
        with requests.get(location, timeout=15, allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                return 'key_http_error'
            body = bytearray()
            for chunk in response.iter_content(chunk_size=256):
                body.extend(chunk)
                if len(body) > 1024:
                    return 'key_content_mismatch'
            try:
                return ('key_matches' if body.decode('utf-8-sig').strip() == key
                        else 'key_content_mismatch')
            except UnicodeError:
                return 'key_content_mismatch'
    except requests.RequestException:
        return 'key_network_error'


def submit_urls(urls: list[str], host='trendpulse.blog') -> dict:
    """Submit once, returning safe diagnostics. No cross-provider fallback."""
    config = _configuration(host)
    if not config:
        return {'status': 'invalid_configuration', 'accepted': False}
    endpoint, key, location = config
    scope = posixpath.dirname(unquote(urlsplit(location).path)).rstrip('/') + '/'
    encoded, seen = [], set()
    for url in urls:
        if not _same_host_url(url, host):
            continue
        path = posixpath.normpath(unquote(urlsplit(url).path))
        if scope != '/' and not path.startswith(scope):
            continue
        value = requests.utils.requote_uri(url)
        if value not in seen:
            seen.add(value)
            encoded.append(value)
    if not encoded:
        return {'status': 'no_valid_urls', 'accepted': False}
    # Never silently drop URLs beyond the protocol's per-request limit.
    if len(encoded) > 10000:
        return {'status': 'too_many_urls', 'accepted': False}
    result = {'endpoint': urlsplit(endpoint).hostname, 'submitted_count': len(encoded),
              'accepted': False}
    try:
        response = requests.post(endpoint, json={'host': host, 'key': key,
            'keyLocation': location, 'urlList': encoded}, timeout=30, allow_redirects=False)
    except requests.RequestException:
        return {**result, 'status': 'network_error'}
    result['http_status'] = response.status_code
    if response.status_code in (200, 202):
        return {**result, 'accepted': True,
                'status': 'accepted' if response.status_code == 200 else 'verification_pending'}
    result['status'] = {403: 'ownership_rejected', 429: 'rate_limited',
                        400: 'invalid_request', 422: 'invalid_request'}.get(
                            response.status_code, 'http_error')
    try:
        data = response.json()
        code = data.get('errorCode', data.get('code')) if isinstance(data, dict) else None
        if isinstance(code, str) and code in ERROR_CODES:
            result['error_code'] = code
    except (ValueError, TypeError):
        pass
    if response.status_code == 403:
        result['key_check'] = check_key(host)
    return result


def ping_urls(urls: list[str], host: str = 'trendpulse.blog') -> bool:
    """Non-blocking notification result, separate from WordPress publication."""
    result = submit_urls(urls, host)
    log = logger.info if result['accepted'] else logger.warning
    log('IndexNow notification: {}', result)
    return result['accepted']
