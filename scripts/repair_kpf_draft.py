"""One-off reviewed correction of draft 1894; never publishes or creates posts."""
import hashlib
import json
import os
from pathlib import Path

import requests

POST_ID = 1894
TITLE = "2026 한국언론진흥재단 채용: 정규직 신입 지원·일정 총정리"
BEFORE_SHA = "aa09831470fc472f0ecacfaf65d325af118d5f89d420c7cfad4715a111f50cad"
NOTICE = ("https://kpf.or.kr/front/board/boardContentsView.do?board_id=268"
          "&amp;contents_id=74a9591e297944da81d66eb34493e7c5"
          "&amp;link_g_topmenu_id=ccd1e88d6d7345cca51f20ce9f56d652"
          "&amp;link_g_submenu_id=0017607aa5cc49deb9e877eff2ba59e8"
          "&amp;link_g_homepage=F")
APPLY_URL = "https://kpf.plusrecruit.co.kr/#/"
PROTECTED = ("id", "status", "slug", "date", "date_gmt", "title", "excerpt",
             "featured_media", "categories", "tags", "meta")


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def patch_html(body):
    changes = [
        ("https://www.kpf.or.kr/kpf/26/subview.do", NOTICE, 4),
        ('<span style="color: #94a3b8; font-size: 0.85em;">(온라인 접수 사이트)</span>',
         f'<a href="{APPLY_URL}" target="_blank" rel="noopener">온라인 접수 사이트</a>', 3),
        ('<span style="color: #94a3b8; font-size: 0.85em;">(공식 온라인 접수 사이트)</span>',
         f'<a href="{APPLY_URL}" target="_blank" rel="noopener">공식 온라인 접수 사이트</a>', 1),
        ("(온라인 접수 사이트)", "온라인 접수 사이트", 1),  # FAQ structured data
        ("임용 후 즉시 근무할 수 없는 경우에는 임용이 취소될 수 있어요.",
         "임용 후 즉시 근무할 수 없으면 임용이 취소됩니다.", 1),
    ]
    for old, new, expected in changes:
        if body.count(old) != expected:
            raise ValueError("Reviewed text occurrence mismatch; no write")
        body = body.replace(old, new)
    return body


def validate(post):
    if (post.get("id") != POST_ID or post.get("status") != "draft"
            or post.get("title", {}).get("raw") != TITLE
            or digest(post["content"]["raw"]) != BEFORE_SHA):
        raise ValueError("Draft identity or content changed; no write")


def repair(session, api, output):
    def read():
        res = session.get(f"{api}/posts/{POST_ID}", params={"context": "edit"},
                          timeout=45, allow_redirects=False)
        if res.status_code != 200:
            raise RuntimeError("Draft read failed")
        return res.json()
    before = read()
    validate(before)
    body = patch_html(before["content"]["raw"])
    output.mkdir(parents=True, exist_ok=True)
    (output / "before.json").write_text(json.dumps(before, ensure_ascii=False))
    (output / "proposed.html").write_text(body)
    current = read()
    if (any(current.get(k) != before.get(k) for k in (*PROTECTED, "modified_gmt"))
            or current.get("content") != before.get("content")):
        raise RuntimeError("Concurrent edit detected; no write")
    res = session.post(f"{api}/posts/{POST_ID}", json={"content": body},
                       timeout=45, allow_redirects=False)
    if res.status_code != 200:
        raise RuntimeError("Draft write not confirmed; inspect before retry")
    after = read()
    (output / "after.json").write_text(json.dumps(after, ensure_ascii=False))
    if (after["content"]["raw"] != body
            or any(after.get(k) != before.get(k) for k in PROTECTED)):
        raise RuntimeError("Draft verification failed; inspect backup")
    result = {"id": POST_ID, "status": after["status"], "verified": True,
              "before_sha256": BEFORE_SHA, "after_sha256": digest(body),
              "changed_fields": ["content"], "published": False}
    (output / "result.json").write_text(json.dumps(result))
    print(json.dumps(result))
    return result


def main():
    base = os.environ["WP_GENERAL_URL"].rstrip("/")
    if base != "https://trendpulse.blog" or os.environ.get("POC_POST_ID") != str(POST_ID):
        raise ValueError("This operation only permits TrendPulse draft 1894")
    session = requests.Session()
    session.auth = (os.environ["WP_GENERAL_USERNAME"], os.environ["WP_GENERAL_APP_PASSWORD"])
    session.headers["User-Agent"] = "Mozilla/5.0 (TrendPulse reviewed draft correction)"
    repair(session, base + "/wp-json/wp/v2", Path(os.environ["RUNNER_TEMP"]) / "kpf-draft-review")


if __name__ == "__main__":
    main()
