"""Repair only owned reader CSS whitespace; preserve all other content bytes."""
import os
import re
import requests

BASE = 'https://trendpulse.blog'
STYLE = re.compile(r'(<style\b[^>]*\bid=[\"\']wpab-reading-styles[\"\'][^>]*>)(.*?)(</style\s*>)', re.S | re.I)


def compact_style(html):
    matches = list(STYLE.finditer(html))
    if len(matches) != 1 or 'wpab-menu-reader' not in matches[0].group(2):
        raise ValueError('Exactly one owned category reader stylesheet required')
    match = matches[0]
    if '<' in match.group(2):
        raise ValueError('Unexpected markup in raw stylesheet')
    css = ' '.join(match.group(2).split())
    return html[:match.start(2)] + css + html[match.end(2):]


def repair(session, post_id, slug, *, apply=False):
    if type(post_id) is not int or post_id <= 0 or not slug or '/' in slug:
        raise ValueError('Exact post ID and slug required')
    url = f'{BASE}/wp-json/wp/v2/posts/{post_id}'
    def read():
        response = session.get(url, params={'context': 'edit'}, timeout=45, allow_redirects=False)
        response.raise_for_status()
        return response.json()
    original = read()
    if original.get('id') != post_id or original.get('slug') != slug or original.get('status') != 'publish':
        raise RuntimeError('Published post identity mismatch')
    raw = original['content']['raw']
    fixed = compact_style(raw)
    if not apply:
        return {'post_id': post_id, 'dry_run': True, 'changed': fixed != raw}
    if fixed != raw:
        current = read()
        if current.get('modified_gmt') != original.get('modified_gmt') or current['content']['raw'] != raw:
            raise RuntimeError('Post changed since inspection; no update made')
        response = session.post(url, json={'content': fixed}, timeout=45, allow_redirects=False)
        response.raise_for_status()
    saved = read()
    if saved['content']['raw'] != fixed or any(saved.get(k) != original.get(k) for k in
            ('id', 'slug', 'status', 'title', 'featured_media', 'date_gmt', 'categories', 'tags', 'excerpt')):
        raise RuntimeError('Readback preservation verification failed')
    return {'post_id': post_id, 'verified': True, 'url': saved['link'], 'changed': fixed != raw}


def main():
    if os.environ['WP_GENERAL_URL'].rstrip('/') != BASE:
        raise RuntimeError('Unexpected WordPress site')
    session = requests.Session()
    session.auth = (os.environ['WP_GENERAL_USERNAME'], os.environ['WP_GENERAL_APP_PASSWORD'])
    session.headers['User-Agent'] = 'Mozilla/5.0 (TrendPulse reader CSS repair)'
    print(repair(session, int(os.environ['REPAIR_READER_POST_ID']), os.environ['REPAIR_READER_POST_SLUG'],
                 apply=os.environ.get('DRY_RUN') == 'false'), flush=True)


if __name__ == '__main__':
    main()
