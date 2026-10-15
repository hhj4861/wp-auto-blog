"""Repair owned reader assets or explicitly reflow owned ads; preserve other bytes."""
import os
import json
from pathlib import Path
from time import time_ns
import re
import requests

BASE = 'https://trendpulse.blog'
PRESERVED_FIELDS = ('id', 'slug', 'status', 'title', 'featured_media', 'date_gmt',
                    'categories', 'tags', 'excerpt', 'meta')
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


def upgrade_assets(html):
    """Replace only our CSS/JS bodies. Editorial HTML stays byte-for-byte intact."""
    from bs4 import BeautifulSoup
    from src.category_format import reader_styles
    soup = BeautifulSoup(html, 'html.parser')
    articles = soup.select('.wpab-menu-reader')
    if len(articles) != 1 or articles[0].get('data-reader-version') != 'category-menu-v1':
        raise ValueError('Exactly one supported reader required')
    article = articles[0]
    if len(article.select(':scope > [data-reader-menu]')) != 1 or len(article.select(':scope > [data-reader-panels] > [data-reader-panel]')) < 2:
        raise ValueError('Reader menu/panel contract missing')
    # Validate original owned style before replacing it.
    compact_style(html)
    script = re.compile(r'(<script\b[^>]*\bid=["\']wpab-category-reader["\'][^>]*>)(.*?)(</script\s*>)', re.S | re.I)
    if len(list(script.finditer(html))) != 1:
        raise ValueError('Exactly one owned reader script required')
    css = reader_styles(article.get('data-reader-category'))
    js = Path(__file__).resolve().parents[1].joinpath('src/category_reader.js').read_text(encoding='utf-8')
    fixed = STYLE.sub(lambda m: m[1] + css + m[3], html)
    return script.sub(lambda m: m[1] + js + m[3], fixed)


def repair(session, post_id, slug, *, apply=False, upgrade=False, reflow=False, backup_dir=None):
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
    fixed = upgrade_assets(raw) if upgrade else compact_style(raw)
    if reflow:
        from src.reader_monetization import reflow_reader_ads
        fixed = reflow_reader_ads(fixed)
    if not apply:
        return {'post_id': post_id, 'dry_run': True, 'changed': fixed != raw}
    backup = None
    if fixed != raw:
        current = read()
        if (current.get('modified_gmt') != original.get('modified_gmt')
                or current['content']['raw'] != raw
                or any(current.get(key) != original.get(key) for key in PRESERVED_FIELDS)):
            raise RuntimeError('Post changed since inspection; no update made')
        if reflow:
            if not backup_dir:
                raise ValueError('A backup directory is required before applying ad reflow')
            directory = Path(backup_dir)
            directory.mkdir(parents=True, exist_ok=True)
            backup = directory / f'reader-{post_id}-{time_ns()}.json'
            with backup.open('x', encoding='utf-8') as handle:
                json.dump(original, handle, ensure_ascii=False)
        response = session.post(url, json={'content': fixed}, timeout=45, allow_redirects=False)
        response.raise_for_status()
    saved = read()
    if saved['content']['raw'] != fixed or any(saved.get(k) != original.get(k) for k in
            PRESERVED_FIELDS):
        raise RuntimeError('Readback preservation verification failed')
    return {'post_id': post_id, 'verified': True, 'url': saved['link'], 'changed': fixed != raw, 'backup': str(backup) if backup else None}


def main():
    if os.environ['WP_GENERAL_URL'].rstrip('/') != BASE:
        raise RuntimeError('Unexpected WordPress site')
    session = requests.Session()
    session.auth = (os.environ['WP_GENERAL_USERNAME'], os.environ['WP_GENERAL_APP_PASSWORD'])
    session.headers['User-Agent'] = 'Mozilla/5.0 (TrendPulse reader CSS repair)'
    print(repair(session, int(os.environ['REPAIR_READER_POST_ID']), os.environ['REPAIR_READER_POST_SLUG'],
                 apply=os.environ.get('DRY_RUN') == 'false',
                 upgrade=os.environ.get('UPGRADE_READER_ASSETS') == 'true',
                 reflow=os.environ.get('REFLOW_READER_ADS') == 'true',
                 backup_dir=os.environ.get('READER_BACKUP_DIR')), flush=True)


if __name__ == '__main__':
    main()
