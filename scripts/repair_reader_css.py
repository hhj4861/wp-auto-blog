"""Repair owned reader assets; preserve all other content bytes."""
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


def upgrade_assets(html):
    """Replace only our CSS/JS bodies. Editorial HTML stays byte-for-byte intact."""
    from bs4 import BeautifulSoup
    from src.category_format import reader_styles
    from pathlib import Path
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


def repair(session, post_id, slug, *, apply=False, upgrade=False, legacy_recruitment=False, backup_dir=None):
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
    if legacy_recruitment:
        if upgrade:
            raise ValueError('Choose either legacy conversion or asset upgrade')
        from scripts.reformat_recruitment_posts import convert_legacy_recruitment
        fixed = convert_legacy_recruitment(raw, post_id, slug)
        if backup_dir is None:
            raise ValueError('Backup directory required for legacy conversion')
        from pathlib import Path
        folder = Path(backup_dir)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f'{post_id}-original.html').write_text(raw, encoding='utf-8')
        (folder / f'{post_id}-proposed.html').write_text(fixed, encoding='utf-8')
    else:
        fixed = upgrade_assets(raw) if upgrade else compact_style(raw)
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
                 apply=os.environ.get('DRY_RUN') == 'false',
                 upgrade=os.environ.get('UPGRADE_READER_ASSETS') == 'true',
                 legacy_recruitment=os.environ.get('REFORMAT_LEGACY_RECRUITMENT') == 'true',
                 backup_dir=os.environ.get('READER_BACKUP_DIR')), flush=True)


if __name__ == '__main__':
    main()
