"""Restore missing TrendPulse thumbnails for explicitly selected posts only."""
import argparse
import json
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.editorial_thumbnail import create_editorial_thumbnail
from src.wordpress_client import WPConfig, WordPressClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('post_ids', nargs='+', type=int)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--replace', action='store_true', help='Replace existing thumbnails for the explicit IDs')
    args = parser.parse_args()
    load_dotenv()
    config = WPConfig.from_env('general')
    if config.url != 'https://trendpulse.blog':
        raise ValueError('TrendPulse only')
    client = WordPressClient(config)
    session = requests.Session()
    session.auth = (config.username, config.app_password)
    session.headers['User-Agent'] = 'Mozilla/5.0 (TrendPulse thumbnail repair)'
    for post_id in args.post_ids:
        endpoint = config.url + f'/wp-json/wp/v2/posts/{post_id}'
        def read():
            response = session.get(endpoint, params={'context': 'edit'}, timeout=45)
            response.raise_for_status()
            return response.json()
        original = read()
        if original['featured_media'] and not args.replace:
            print(post_id, 'already has thumbnail; skipped')
            continue
        title = original['title']['raw']
        candidate = create_editorial_thumbnail(title, original['content']['raw'])
        print(post_id, title, candidate.url, flush=True)
        if not args.apply:
            continue
        backup = Path('data/editorial-backups') / f'featured-image-{post_id}.json'
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            backup.write_text(json.dumps(original, ensure_ascii=False), encoding='utf-8')
        media_id, media_url = client._upload_media(candidate.url, title)
        if not media_id:
            raise RuntimeError('Media upload failed; post unchanged')
        current = read()
        if current['modified_gmt'] != original['modified_gmt'] or current['featured_media'] != original['featured_media']:
            raise RuntimeError('Post changed during image upload; refusing overwrite')
        response = session.post(endpoint, json={'featured_media': media_id}, timeout=45)
        response.raise_for_status()
        saved = read()
        assert saved['featured_media'] == media_id
        assert all(saved[k] == original[k] for k in ('content', 'title', 'slug', 'status'))
        print('VERIFIED thumbnail', post_id, media_id, media_url, flush=True)


if __name__ == '__main__':
    main()
