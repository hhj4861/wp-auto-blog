"""Unpublish exactly one reviewed post; keep its body, media and history."""
import os
import requests

BASE = 'https://trendpulse.blog'


def close_post(session, post_id, slug, *, apply=False):
    if type(post_id) is not int or post_id <= 0 or not slug or '/' in slug:
        raise ValueError('Exact post ID and slug required')
    url = f'{BASE}/wp-json/wp/v2/posts/{post_id}'
    response = session.get(url, params={'context': 'edit'}, timeout=45, allow_redirects=False)
    response.raise_for_status()
    original = response.json()
    if (original.get('id') != post_id or original.get('slug') != slug
            or original.get('status') not in ('publish', 'draft')):
        raise RuntimeError('Post identity/status mismatch; no change made')
    if not apply:
        return {'post_id': post_id, 'status': original['status'], 'dry_run': True}
    if original['status'] != 'draft':
        response = session.post(url, json={'status': 'draft'}, timeout=45, allow_redirects=False)
        response.raise_for_status()
    response = session.get(url, params={'context': 'edit'}, timeout=45, allow_redirects=False)
    response.raise_for_status()
    saved = response.json()
    if saved.get('status') != 'draft' or any(saved.get(k) != original.get(k)
            for k in ('id', 'slug', 'title', 'content', 'featured_media', 'date_gmt')):
        raise RuntimeError('Draft readback or content preservation verification failed')
    return {'post_id': post_id, 'status': 'draft', 'verified': True}


def main():
    if os.environ['WP_GENERAL_URL'].rstrip('/') != BASE:
        raise RuntimeError('Unexpected WordPress site')
    session = requests.Session()
    session.auth = (os.environ['WP_GENERAL_USERNAME'], os.environ['WP_GENERAL_APP_PASSWORD'])
    session.headers['User-Agent'] = 'Mozilla/5.0 (TrendPulse approved unpublish)'
    result = close_post(session, int(os.environ['CLOSE_POST_ID']), os.environ['CLOSE_POST_SLUG'],
                        apply=os.environ.get('DRY_RUN') == 'false')
    print(result, flush=True)


if __name__ == '__main__':
    main()
