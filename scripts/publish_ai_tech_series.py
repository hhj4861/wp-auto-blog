"""Publish only the three user-approved, already reviewed AI tech drafts.

Run in the existing WordPress-secret environment. No credentials are exported.
This task-specific entry point never generates or replaces article content.
"""
import hashlib
import json
import os
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image, ImageChops, ImageStat, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://trendpulse.blog'
SPECS = {
    1838: ('muse', 'meta-muse-ai-agent-guide', 'Meta Muse란? 개인 AI 에이전트의 기능·한국 이용 조건·업무 활용법', 'd54651e91645125a3a06474f7c30a39860a1019df7e1f3166237a5fffa5f48a3', 'Meta Muse 개인 AI 에이전트를 표현한 따뜻한 작업 공간의 개념 일러스트', 'about.fb.com'),
    1840: ('dots', 'openai-dots-ai-agent-guide', 'OpenAI Dots란? AI 에이전트 기능·이용 조건·업무 활용 가이드', '876631fc1c56855bbbea97643cf8f0cb8ae3ae42e87e29c6621d02777d87c90c', 'OpenAI Dots의 클라우드 작업을 표현한 푸른 작업 공간의 개념 일러스트', 'openai.com'),
    1843: ('jev', 'typesafe-jev-decision-model-guide', 'TypeSafe Jev란? 판단 모델의 원리·활용법과 정확도 오해 정리', '949123e052fe2be112e944889a2078a6a97d0146d272451541a211c4ad89f6f4', 'TypeSafe Jev의 구조화된 판단을 표현한 초록색 분류 트레이 개념 일러스트', 'typesafe.ai'),
}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def emit(**record):
    print(json.dumps(record, ensure_ascii=False), flush=True)


def snapshot(post):
    return tuple(json.dumps(post.get(k), sort_keys=True) for k in
                 ('id', 'slug', 'status', 'modified_gmt', 'title', 'content', 'excerpt', 'featured_media', 'categories', 'tags'))


def validate_post(post, pid):
    name, slug, title, digest, alt, source = SPECS[pid]
    require(post.get('id') == pid and post.get('slug') == slug, 'Post identity mismatch')
    require(post.get('title', {}).get('raw') == title, 'Reviewed title changed')
    require(post.get('status') in ('draft', 'publish'), 'Unexpected post status')
    body = post.get('content', {}).get('raw', '')
    require(len(body) > 3500 and 'wpab-article' in body and 'quick-answer' in body and source in body,
            'Reviewed article content missing')
    require(post.get('categories') and post.get('excerpt', {}).get('raw'), 'Article metadata missing')
    image = ROOT / 'data/editorial/2026-10-06' / (name + '.png')
    data = image.read_bytes()
    require(data.startswith(b'\x89PNG\r\n\x1a\n') and hashlib.sha256(data).hexdigest() == digest,
            'Reviewed image changed')
    return data


class Publisher:
    def __init__(self, session, public=None):
        self.session = session
        self.public = public or requests.Session()

    def call(self, method, path, **kwargs):
        r = self.session.request(method, SITE + '/wp-json/wp/v2' + path,
                                 timeout=(10, 60), allow_redirects=False, **kwargs)
        require(200 <= r.status_code < 300, f'WordPress {method} {path}: HTTP {r.status_code}')
        return r.json()

    def post(self, pid):
        return self.call('GET', f'/posts/{pid}', params={'context': 'edit'})

    def verify_media(self, media, spec):
        url = media.get('source_url', '')
        require(urlsplit(url).scheme == 'https' and urlsplit(url).hostname == 'trendpulse.blog',
                'Unexpected media host')
        require(media.get('media_type') == 'image' and media.get('mime_type') == 'image/png', 'Unexpected media type')
        response = self.public.get(url, timeout=(10, 60), allow_redirects=False)
        require(response.status_code == 200, 'Uploaded image unavailable')
        # WordPress may strip PNG metadata or recompress the container. Verify
        # decoded pixels as well as dimensions, rather than encoded bytes alone.
        original = Image.open(ROOT / 'data/editorial/2026-10-06' / (spec[0] + '.png')).convert('RGB')
        try:
            actual = Image.open(BytesIO(response.content)).convert('RGB')
        except (UnidentifiedImageError, OSError):
            raise RuntimeError('Uploaded image bytes are not a valid image')
        require(actual.size in (original.size, (1600, 900)), 'Unexpected server image dimensions')
        # The production image optimizer caps these covers at 1600x900.
        # Compare their appearance after the known resize; a different cover
        # or material visual change must still hold publication.
        reference = original.resize(actual.size, Image.Resampling.LANCZOS)
        rms = max(ImageStat.Stat(ImageChops.difference(reference, actual)).rms)
        def dhash(image):
            small = image.convert('L').resize((9, 8), Image.Resampling.LANCZOS)
            pixels = list(small.getdata())
            return [pixels[y*9+x] > pixels[y*9+x+1] for y in range(8) for x in range(8)]
        distance = sum(a != b for a, b in zip(dhash(reference), dhash(actual)))
        emit(stage='media_integrity', media_id=media.get('id'), original_size=original.size,
             uploaded_size=actual.size, encoded_match=hashlib.sha256(response.content).hexdigest() == spec[3],
             pixel_rms=round(rms, 3), visual_hash_distance=distance)
        require(rms <= 8 and distance <= 3, 'Uploaded image differs from reviewed cover')
        return url

    def run(self, ids, apply=False):
        require(ids and len(set(ids)) == len(ids) and all(pid in SPECS for pid in ids), 'Unapproved post ID')
        # Read and validate every requested draft before the first mutation.
        originals = {pid: self.post(pid) for pid in ids}
        images = {pid: validate_post(originals[pid], pid) for pid in ids}
        for pid in ids:
            original = originals[pid]
            spec = SPECS[pid]
            emit(stage='preflight', post_id=pid, status=original['status'], image=spec[0], apply=apply)
            if not apply:
                continue
            if original['status'] == 'publish':
                require(original.get('featured_media'), 'Published post missing cover; manual review required')
                media = self.call('GET', f"/media/{original['featured_media']}")
                self.verify_media(media, spec)
                emit(stage='already_published', post_id=pid, link=original['link'])
                continue
            media_slug = f'ai-tech-{spec[0]}-cover-20261006'
            matches = self.call('GET', '/media', params={'slug': media_slug, 'context': 'edit'})
            require(len(matches) <= 1, 'Ambiguous existing cover')
            if matches:
                media = matches[0]
            else:
                # No automatic retry for uploads: after an ambiguous failure a rerun
                # finds the deterministic filename/slug instead of duplicating it.
                media = self.call('POST', '/media', data=images[pid], headers={
                    'Content-Type': 'image/png',
                    'Content-Disposition': f'attachment; filename="{media_slug}.png"'})
            url = self.verify_media(media, spec)
            mid = media['id']
            self.call('POST', f'/media/{mid}', json={'alt_text': spec[4], 'title': spec[2], 'post': pid})
            saved_media = self.call('GET', f'/media/{mid}')
            require(saved_media.get('alt_text') == spec[4] and saved_media.get('post') == pid,
                    'Cover metadata not saved')
            current = self.post(pid)
            require(snapshot(current) == snapshot(original), 'Post changed while preparing cover')
            self.call('POST', f'/posts/{pid}', json={'featured_media': mid})
            attached = self.post(pid)
            expected = dict(current, featured_media=mid, modified_gmt=attached.get('modified_gmt'))
            require(snapshot(attached) == snapshot(expected), 'Unexpected change while attaching cover')
            require(attached['status'] == 'draft', 'Post status changed before publication')
            emit(stage='cover_verified', post_id=pid, media_id=mid, media_url=url)
            current = self.post(pid)
            require(snapshot(current) == snapshot(attached), 'Post changed before publication')
            self.call('POST', f'/posts/{pid}', json={'status': 'publish'})
            final = self.post(pid)
            require(final.get('status') == 'publish' and final.get('featured_media') == mid
                    and final.get('slug') == spec[1]
                    and final.get('content', {}).get('raw') == original['content']['raw'],
                    'Publication verification failed')
            require(final.get('link') == SITE + '/' + spec[1] + '/', 'Unexpected public URL')
            emit(stage='published_verified', post_id=pid, media_id=mid, link=final['link'])


def main():
    require(os.environ.get('WP_GENERAL_URL', '').rstrip('/') == SITE, 'Unexpected WordPress site')
    user = os.environ.get('WP_GENERAL_USERNAME')
    password = os.environ.get('WP_GENERAL_APP_PASSWORD')
    require(user and password, 'WordPress credentials missing')
    ids = [int(s.strip()) for s in os.environ.get('POC_POST_ID', '').split(',') if s.strip()]
    session = requests.Session()
    session.auth = (user, password)
    session.headers['User-Agent'] = 'TrendPulse-reviewed-tech-publication/1.0'
    Publisher(session).run(ids, apply=os.environ.get('APPLY') == 'true')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, requests.RequestException) as exc:
        # Do not print request objects, authorization headers, or server bodies.
        if isinstance(exc, requests.RequestException):
            raise SystemExit('API transport failed: ' + type(exc).__name__)
        raise SystemExit(str(exc))
