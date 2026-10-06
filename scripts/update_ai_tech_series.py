"""Update only the three published AI-tech bodies, preserving their identities.

No image upload or new post is made. The initial reviewed public text is pinned;
changes by another editor cause a stop. Existing WordPress secrets stay on CI.
"""
import hashlib
import json
import os
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from publish_ai_tech_series import Publisher, ROOT, SITE, SPECS, emit, require, snapshot

BASE_TEXT_DIGESTS = {
    1838: 'f43c7bff792737cc79ecaf700b07039ce91a76af872882915b1e3bb8f576d445',
    1840: '5fb8b0cf0189783cc98d5365043e75e08933c0106c4c3330b7dfac62a470cc5d',
    1843: '8c147f945c0c08675e9f8099ade0e39c84fb0bcd28ea6076716542def6ad5c6c',
}
MEDIA_IDS = {1838:1846, 1840:1847, 1843:1848}
PRESERVE = ('id','slug','status','title','excerpt','date','date_gmt','link','featured_media','categories','tags')


def text_digest(body):
    article = BeautifulSoup(body, 'html.parser').select_one('.wpab-article')
    require(article is not None, 'Article container missing')
    return hashlib.sha256(article.get_text(' ', strip=True).encode()).hexdigest()


def validate_body(body, pid):
    soup = BeautifulSoup(body, 'html.parser')
    article = soup.select_one('.wpab-article')
    require(article is not None and article.select_one('#quick-answer') is not None, 'Article or answer missing')
    require(len(article.get_text(' ', strip=True)) >= 6000, 'Detailed article missing')
    diagrams = article.select('figure.tp-diagram')
    require(len(diagrams) >= (3 if pid == 1843 else 2), 'Required explanatory diagrams missing')
    require(all(d.find('figcaption') and d.select_one('.tp-node') and d.select_one('.tp-note') for d in diagrams),
            'Diagram caption, explanation or nodes missing')
    require(soup.find('style') and '@media(max-width:600px)' in body, 'Responsive diagram styles missing')
    require(not soup.select('script,iframe,ins,form'), 'Unexpected active or advertising content')
    require(SPECS[pid][5] in body and '가정' in body or SPECS[pid][5] in body and '가상' in body,
            'Sources or illustrative-example labels missing')
    return body


def validate_identity(post, pid):
    spec = SPECS[pid]
    require(post.get('id') == pid and post.get('slug') == spec[1], 'Post identity mismatch')
    require(post.get('title',{}).get('raw') == spec[2], 'Title changed since review')
    require(post.get('status') == 'publish', 'Expected published post')
    require(post.get('link') == SITE+'/'+spec[1]+'/', 'Public URL changed')
    require(post.get('featured_media') == MEDIA_IDS[pid], 'Featured image changed')


class Updater(Publisher):
    def run(self, ids, bodies, backup_dir, apply=False):
        require(ids and len(set(ids)) == len(ids) and all(i in SPECS for i in ids), 'Unapproved post ID')
        # Validate every input and original before the first write.
        originals = {pid:self.post(pid) for pid in ids}
        for pid in ids:
            validate_body(bodies[pid], pid)
            validate_identity(originals[pid], pid)
            raw = originals[pid]['content']['raw']
            require(raw == bodies[pid] or text_digest(raw) == BASE_TEXT_DIGESTS[pid],
                    'Published text changed since editorial review')
            emit(stage='update_preflight', post_id=pid, diagrams=bodies[pid].count('class="tp-diagram"'), apply=apply)
        if not apply:
            return
        backup_dir.mkdir(parents=True, exist_ok=True)
        for pid, original in originals.items():
            # Public editorial fields only; no credentials or authentication data.
            before = {k:original[k] for k in PRESERVE + ('content','modified_gmt') if k in original}
            target = backup_dir/f'{pid}-before.json'
            with target.open('x') as f:
                json.dump(before, f, ensure_ascii=False, indent=2)
        for pid, original in originals.items():
            if original['content']['raw'] == bodies[pid]:
                emit(stage='already_updated', post_id=pid, link=original['link'])
                continue
            current = self.post(pid)
            require(snapshot(current) == snapshot(original) and
                    all(current.get(k) == original.get(k) for k in PRESERVE),
                    'Concurrent post change; refusing overwrite')
            # Never retry writes automatically: read back the post after a transport failure.
            self.call('POST', f'/posts/{pid}', json={'content':bodies[pid]})
            final = self.post(pid)
            require(final.get('content',{}).get('raw') == bodies[pid], 'Saved content differs from reviewed HTML')
            require(all(final.get(k) == original.get(k) for k in PRESERVE), 'Protected post metadata changed')
            validate_body(final['content']['raw'], pid)
            emit(stage='updated_verified', post_id=pid, link=final['link'],
                 visible_chars=len(BeautifulSoup(bodies[pid], 'html.parser').select_one('.wpab-article').get_text(' ',strip=True)),
                 content_sha256=hashlib.sha256(bodies[pid].encode()).hexdigest())


def main():
    require(os.environ.get('WP_GENERAL_URL','').rstrip('/') == SITE, 'Unexpected WordPress site')
    user, password = os.environ.get('WP_GENERAL_USERNAME'), os.environ.get('WP_GENERAL_APP_PASSWORD')
    require(user and password, 'WordPress credentials missing')
    ids = [int(x.strip()) for x in os.environ.get('POC_POST_ID','').split(',') if x.strip()]
    require(all(pid in SPECS for pid in ids), 'Unapproved post ID')
    bodies = {pid:(ROOT/'data/editorial/2026-10-06'/f'{SPECS[pid][0]}.html').read_text() for pid in ids}
    session = requests.Session(); session.auth = (user,password)
    session.headers['User-Agent'] = 'TrendPulse-reviewed-editorial-update/1.0'
    # CI ephemeral output is retained as a short-lived artifact; no local default.
    backup = Path(os.environ['EDITORIAL_BACKUP_DIR'])
    Updater(session).run(ids, bodies, backup, apply=os.environ.get('APPLY') == 'true')

if __name__ == '__main__':
    try:
        main()
    except requests.RequestException as exc:
        raise SystemExit('API transport failed: '+type(exc).__name__)
    except (RuntimeError, ValueError, KeyError) as exc:
        raise SystemExit(str(exc))
