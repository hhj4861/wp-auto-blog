import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import update_ai_tech_series as m


class FakeUpdater(m.Updater):
    def __init__(self, bodies):
        self.posts = {}
        for pid, body in bodies.items():
            self.posts[pid] = dict(id=pid, slug=m.SPECS[pid][1], title={'raw':m.SPECS[pid][2]},
                status='publish', link=m.SITE+'/'+m.SPECS[pid][1]+'/', featured_media=m.MEDIA_IDS[pid],
                content={'raw':body.replace('함께 읽으면 좋은 글','기존 글')}, excerpt={'raw':'original excerpt'},
                date='2026-10-06T17:16:00', date_gmt='2026-10-06T08:16:00', modified_gmt='original', categories=[1],tags=[2])
        self.writes=[]; self.reads={pid:0 for pid in bodies}
        self.concurrent=False; self.strip_style=False; self.change_metadata=False
    def call(self, method, path, **kw):
        pid=int(path.rsplit('/',1)[-1])
        if method=='POST':
            self.writes.append(kw['json'])
            body=kw['json']['content']
            if self.strip_style: body=body.replace('tp-diagram','lost-diagram')
            self.posts[pid]['content']['raw']=body
            self.posts[pid]['modified_gmt']='updated'
            if self.change_metadata: self.posts[pid]['featured_media']=0
        else:
            self.reads[pid]+=1
            if self.concurrent and self.reads[pid]==2:
                self.posts[pid]['content']['raw']+='another editor'
        return copy.deepcopy(self.posts[pid])


class Tests(unittest.TestCase):
    def setUp(self):
        self.bodies={pid:(m.ROOT/'data/editorial/2026-10-06'/f'{s[0]}.html').read_text() for pid,s in m.SPECS.items()}
        self.p=FakeUpdater(self.bodies)
        self.patch=patch.dict(m.BASE_TEXT_DIGESTS,{pid:m.text_digest(p['content']['raw']) for pid,p in self.p.posts.items()})
        self.patch.start(); self.addCleanup(self.patch.stop)
        self.backup=Mock()
        self.backup.__truediv__=Mock(return_value=Mock())
        self.backup.__truediv__.return_value.open.return_value.__enter__=Mock(return_value=Mock())
        self.backup.__truediv__.return_value.open.return_value.__exit__=Mock(return_value=False)
    def run_update(self, apply=True):
        self.p.run(list(self.bodies),self.bodies,self.backup,apply)
    def test_preflight_no_writes(self):
        self.run_update(False); self.assertEqual(self.p.writes,[]); self.backup.mkdir.assert_not_called()
    def test_all_three_update_preserving_identity_and_rerun_is_idempotent(self):
        before=copy.deepcopy(self.p.posts); self.run_update()
        for pid in before:
            self.assertEqual(self.p.posts[pid]['content']['raw'],self.bodies[pid])
            for k in m.PRESERVE: self.assertEqual(self.p.posts[pid][k],before[pid][k])
        self.assertTrue(all(list(w)==['content'] for w in self.p.writes))
        self.run_update(); self.assertEqual(len(self.p.writes),3)
    def test_unknown_id_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'Unapproved'): self.p.run([999],{},self.backup,True)
        self.assertEqual(self.p.writes,[])
    def test_missing_diagram_in_last_article_blocks_all_updates(self):
        self.bodies[1843]=self.bodies[1843].replace('tp-diagram','no-diagram')
        with self.assertRaisesRegex(RuntimeError,'diagrams missing'): self.run_update()
        self.assertEqual(self.p.writes,[])
    def test_editor_change_since_composition_blocks_all(self):
        self.p.posts[1843]['content']['raw']=self.p.posts[1843]['content']['raw'].replace('기존 글','editor revision')
        with self.assertRaisesRegex(RuntimeError,'changed since'): self.run_update()
        self.assertEqual(self.p.writes,[])
    def test_concurrent_edit_is_not_overwritten(self):
        self.p.concurrent=True
        with self.assertRaisesRegex(RuntimeError,'Concurrent'): self.run_update()
        self.assertEqual(self.p.writes,[])
    def test_wp_stripping_markup_is_not_reported_success(self):
        self.p.strip_style=True
        with self.assertRaisesRegex(RuntimeError,'Saved content differs'): self.run_update()
    def test_metadata_change_is_not_reported_success(self):
        self.p.change_metadata=True
        with self.assertRaisesRegex(RuntimeError,'metadata changed'): self.run_update()
    def test_backup_failure_stops_before_write(self):
        self.backup.mkdir.side_effect=OSError('unavailable')
        with self.assertRaises(OSError): self.run_update()
        self.assertEqual(self.p.writes,[])

if __name__=='__main__': unittest.main()
