"""Read-only WordPress inventory diagnostics; never emit credentials or post content."""
import json
import os
import re
from io import StringIO

import requests
from dotenv import dotenv_values


def summarize(response):
    result = {'http_status': response.status_code}
    try:
        body = response.json()
    except ValueError:
        return {**result, 'shape': 'non_json'}
    if not isinstance(body, list):
        code = body.get('code') if isinstance(body, dict) else None
        # Only recognized WordPress codes; arbitrary server strings may contain secrets.
        if isinstance(code, str) and code in {'rest_cannot_view', 'rest_forbidden', 'rest_invalid_param',
                    'incorrect_password', 'invalid_username', '401', '403'}:
            result['error_code'] = code
        return {**result, 'shape': 'not_list'}
    pages = response.headers.get('X-WP-TotalPages', '')
    result.update(shape='list', count=len(body), pages_valid=bool(re.fullmatch(r'[0-9]+', pages)),
                  invalid_title_rows=[], invalid_meta_rows=[])
    if result['pages_valid']:
        result['total_pages'] = int(pages)
    for index, row in enumerate(body):
        if (not isinstance(row, dict) or not isinstance(row.get('title'), dict)
                or not isinstance(row['title'].get('rendered'), str)):
            result['invalid_title_rows'].append(index)
        if isinstance(row, dict) and row.get('meta') and not isinstance(row['meta'], dict):
            result['invalid_meta_rows'].append(index)
    return result


def check(env, get=requests.get):
    keys = ('WP_GENERAL_URL', 'WP_GENERAL_USERNAME', 'WP_GENERAL_APP_PASSWORD')
    if any(not env.get(key) for key in keys) or env[keys[0]].rstrip('/') != 'https://trendpulse.blog':
        return {'status': 'invalid_configuration'}
    # Match dotenv parsing in the posting job without writing or logging secrets.
    parsed = dotenv_values(stream=StringIO('\n'.join(f'{key}={env[key]}' for key in keys)),
                           interpolate=False)
    interpolated = dotenv_values(stream=StringIO('\n'.join(f'{key}={env[key]}' for key in keys)))
    report = {'dotenv_roundtrip_equal': all(parsed.get(key) == env[key] for key in keys),
              'dotenv_interpolated_equal': all(interpolated.get(key) == env[key] for key in keys),
              'heredoc_expansion_possible': any(any(char in env[key] for char in ('$','`','\\')) for key in keys),
              'probes': []}
    standard = {'status': 'publish,draft,pending,future', 'per_page': 100,
                'page': 1, '_fields': 'title,meta'}
    variants = [('inventory_view', standard), ('inventory_edit', {**standard, 'context': 'edit'}),
                ('latest_published', {'status': 'publish', 'per_page': 1, 'context': 'edit'})]
    for name, params in variants:
        for page in range(1, 21):
            try:
                response = get('https://trendpulse.blog/wp-json/wp/v2/posts',
                    auth=(env[keys[1]], env[keys[2]]),
                    headers={'User-Agent': 'Mozilla/5.0 (TrendPulse topic selection)'},
                    params={**params, 'page': page}, timeout=30, allow_redirects=False)
                summary = summarize(response)
            except requests.RequestException:
                summary = {'error': 'request_failed'}
            report['probes'].append({'name': name, 'page': page, **summary})
            if (name == 'latest_published' or summary.get('http_status') != 200
                    or page >= summary.get('total_pages', 1)):
                break
    return report


if __name__ == '__main__':
    print(json.dumps(check(os.environ), ensure_ascii=False))
