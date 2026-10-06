import copy
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location('tech_publish', Path(__file__).resolve().parents[1] / 'scripts/publish_ai_tech_series.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class FakePublisher(m.Publisher):
    def __init__(self):
        self.posts = {pid: dict(id=pid, slug=s[1], title={'raw': s[2]}, status='draft',
                               content={'raw': '<article class="wpab-article" id="quick-answer">' + s[5] + 'x'*4000},
                               excerpt={'raw': 'reviewed summary'}, categories=[3], tags=[4],
                               modified_gmt='initial', featured_media=0,
                               link=m.SITE + '/' + s[1] + '/') for pid, s in m.SPECS.items()}
        self.writes = []
        self.media = {}
        self.fail_upload = False
        self.concurrent_change = False
        self.public = SimpleNamespace(get=self.public_get)

    def public_get(self, url, **kwargs):
        name = url.rsplit('/', 1)[-1].split('.')[0]
        return SimpleNamespace(status_code=200, content=(m.ROOT / 'data/editorial/2026-10-06' / (name+'.png')).read_bytes())

    def call(self, method, path, **kwargs):
        if method == 'POST':
            self.writes.append((path, kwargs))
        if path.startswith('/posts/'):
            pid = int(path.rsplit('/', 1)[-1])
            if method == 'POST':
                self.posts[pid].update(kwargs['json'])
            return copy.deepcopy(self.posts[pid])
        if path == '/media':
            if method == 'GET':
                return [copy.deepcopy(v) for v in self.media.values() if v['slug'] == kwargs['params']['slug']]
            if self.fail_upload:
                raise RuntimeError('Upload failed')
            disposition = kwargs['headers']['Content-Disposition']
            slug = disposition.split('filename="')[1].split('.png')[0]
            name = slug.split('-')[2]
            mid = len(self.media) + 100
            self.media[mid] = dict(id=mid, slug=slug, source_url=m.SITE+'/wp-content/uploads/'+name+'.png', media_type='image', mime_type='image/png')
            if self.concurrent_change:
                self.posts[1838]['content']['raw'] += 'new user edit'
            return copy.deepcopy(self.media[mid])
        mid = int(path.rsplit('/', 1)[-1])
        if method == 'POST':
            self.media[mid].update(kwargs['json'])
        return copy.deepcopy(self.media[mid])


class Tests(unittest.TestCase):
    def test_preflight_is_read_only(self):
        p = FakePublisher(); p.run([1838, 1840, 1843]); self.assertEqual(p.writes, [])

    def test_only_approved_posts(self):
        p = FakePublisher()
        with self.assertRaisesRegex(RuntimeError, 'Unapproved'):
            p.run([999], True)
        self.assertEqual(p.writes, [])

    def test_all_posts_checked_before_mutation(self):
        p = FakePublisher(); p.posts[1843]['title']['raw'] = 'changed'
        with self.assertRaisesRegex(RuntimeError, 'title changed'):
            p.run([1838, 1843], True)
        self.assertEqual(p.writes, [])

    def test_upload_failure_never_publishes(self):
        p = FakePublisher(); p.fail_upload = True
        with self.assertRaisesRegex(RuntimeError, 'Upload failed'):
            p.run([1838], True)
        self.assertEqual(p.posts[1838]['status'], 'draft')
        self.assertFalse(any(path.startswith('/posts/') for path, _ in p.writes))

    def test_concurrent_edit_never_overwritten(self):
        p = FakePublisher(); p.concurrent_change = True
        with self.assertRaisesRegex(RuntimeError, 'Post changed'):
            p.run([1838], True)
        self.assertEqual(p.posts[1838]['status'], 'draft')
        self.assertIn('new user edit', p.posts[1838]['content']['raw'])

    def test_all_three_publish_with_distinct_verified_covers_and_rerun_is_safe(self):
        p = FakePublisher(); before = copy.deepcopy(p.posts)
        p.run([1838, 1840, 1843], True)
        for pid in before:
            self.assertEqual(p.posts[pid]['status'], 'publish')
            for key in ('content', 'title', 'slug', 'categories', 'tags'):
                self.assertEqual(before[pid][key], p.posts[pid][key])
        self.assertEqual(len(set(post['featured_media'] for post in p.posts.values())), 3)
        writes = len(p.writes); p.run([1838, 1840, 1843], True)
        self.assertEqual(len(p.writes), writes)

    def test_lossless_png_reencoding_is_accepted(self):
        from io import BytesIO
        from PIL import Image
        p = FakePublisher()
        buf = BytesIO()
        Image.open(m.ROOT / 'data/editorial/2026-10-06/muse.png').save(buf, format='PNG', compress_level=0)
        p.public.get = lambda *a, **k: SimpleNamespace(status_code=200, content=buf.getvalue())
        p.run([1838], True)
        self.assertEqual(p.posts[1838]['status'], 'publish')

    def test_known_server_resize_is_accepted(self):
        from io import BytesIO
        from PIL import Image
        p = FakePublisher(); buf = BytesIO()
        Image.open(m.ROOT / 'data/editorial/2026-10-06/muse.png').resize((1600, 900), Image.Resampling.BICUBIC).save(buf, format='PNG')
        p.public.get = lambda *a, **k: SimpleNamespace(status_code=200, content=buf.getvalue())
        p.run([1838], True)
        self.assertEqual(p.posts[1838]['status'], 'publish')

    def test_different_valid_cover_is_rejected(self):
        p = FakePublisher()
        wrong = (m.ROOT / 'data/editorial/2026-10-06/jev.png').read_bytes()
        p.public.get = lambda *a, **k: SimpleNamespace(status_code=200, content=wrong)
        with self.assertRaisesRegex(RuntimeError, 'differs from reviewed'):
            p.run([1838], True)
        self.assertEqual(p.posts[1838]['status'], 'draft')

    def test_wrong_media_bytes_hold_publication(self):
        p = FakePublisher(); p.public.get = lambda *a, **k: SimpleNamespace(status_code=200, content=b'wrong')
        with self.assertRaisesRegex(RuntimeError, 'image bytes'):
            p.run([1838], True)
        self.assertEqual(p.posts[1838]['status'], 'draft')


if __name__ == '__main__':
    unittest.main()
