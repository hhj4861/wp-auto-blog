import copy
import unittest
from unittest.mock import Mock, patch
from pathlib import Path
from scripts.repair_kpf_draft import repair, validate, patch_html, POST_ID, TITLE


def body():
    return ("https://www.kpf.or.kr/kpf/26/subview.do " * 4
        + '<span style="color: #94a3b8; font-size: 0.85em;">(온라인 접수 사이트)</span>' * 3
        + '<span style="color: #94a3b8; font-size: 0.85em;">(공식 온라인 접수 사이트)</span>'
        + '(온라인 접수 사이트)'
        + '임용 후 즉시 근무할 수 없는 경우에는 임용이 취소될 수 있어요.')


def post():
    return {"id": POST_ID, "status": "draft", "title": {"raw": TITLE},
            "content": {"raw": body()}, "modified_gmt": "before", "slug": "keep"}


class RepairTest(unittest.TestCase):
    def test_replaces_links_and_fact_without_faq_placeholder(self):
        fixed = patch_html(body())
        self.assertEqual(fixed.count('href="https://kpf.plusrecruit.co.kr/#/"'), 4)
        self.assertNotIn("(온라인 접수 사이트)", fixed)
        self.assertIn("임용이 취소됩니다.", fixed)
        self.assertNotIn("kpf/26/subview", fixed)

    def test_occurrence_guard(self):
        with self.assertRaises(ValueError):
            patch_html(body() + "(온라인 접수 사이트)")

    def test_identity_and_checksum_guard(self):
        for changed in ({"status": "publish"}, {"id": 1897}, {}):
            value = post(); value.update(changed)
            with self.assertRaises(ValueError): validate(value)

    def test_concurrent_edit_prevents_write(self):
        initial = post(); current = copy.deepcopy(initial); current["modified_gmt"] = "new"
        session = Mock()
        session.get.side_effect = [Mock(status_code=200, json=lambda: initial), Mock(status_code=200, json=lambda: current)]
        with patch('scripts.repair_kpf_draft.validate'), patch.object(Path, 'mkdir'), patch.object(Path, 'write_text'):
            with self.assertRaises(RuntimeError): repair(session, "https://example.test", Path("unused"))
        session.post.assert_not_called()

    def test_writes_only_body_and_reads_back_draft(self):
        initial = post(); after = copy.deepcopy(initial); after["content"]["raw"] = patch_html(body())
        session = Mock()
        session.get.side_effect = [Mock(status_code=200, json=lambda: initial), Mock(status_code=200, json=lambda: initial), Mock(status_code=200, json=lambda: after)]
        session.post.return_value = Mock(status_code=200)
        with patch('scripts.repair_kpf_draft.validate'), patch.object(Path, 'mkdir'), patch.object(Path, 'write_text'):
            result = repair(session, "https://example.test", Path("unused"))
        self.assertEqual(session.post.call_args.kwargs["json"], {"content": after["content"]["raw"]})
        self.assertFalse(result["published"])
        self.assertEqual(result["status"], "draft")


if __name__ == "__main__": unittest.main()
