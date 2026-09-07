#!/usr/bin/env python3
"""정크 카테고리 정리 — 백틱 이름 중복 카테고리 병합 + 빈 카테고리 삭제.

카테고리 아카이브를 색인 대상으로 돌리기 전 위생 작업이다. 두 가지를 처리한다:
  1. 병합: 이름이 백틱으로 감싸진 카테고리(LLM 메타 잔존물, 예 `테크`)의 글을
     같은 이름의 정상 카테고리(테크)로 재배정한 뒤 빈 카테고리를 삭제한다.
  2. 삭제: 글 0개인 카테고리를 삭제한다. 기본 카테고리(default_category)는
     WordPress가 삭제를 막으므로 건너뛴다.

기본은 계획만 출력(dry-run). 실제 변경은 --apply.
"""

import argparse
import os
import sys
import urllib.parse

import requests

UA = {"User-Agent": "Mozilla/5.0 (wpab-category-cleanup)"}
STATUSES = "publish,draft,pending,private,future"


def _auth():
    user = os.environ.get("WP_GENERAL_USERNAME") or os.environ.get("WP_USERNAME") or ""
    pw = os.environ.get("WP_GENERAL_APP_PASSWORD") or os.environ.get("WP_APP_PASSWORD") or ""
    if not user or not pw:
        sys.exit("자격증명 없음 — WP_USERNAME/WP_APP_PASSWORD (또는 WP_GENERAL_*) 필요")
    return (user, pw)


def _label(cat: dict) -> str:
    return f"{cat['name']!r}(id={cat['id']}, /{urllib.parse.unquote(cat['slug'])}/, {cat['count']}글)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=os.environ.get("WP_GENERAL_URL") or os.environ.get("WP_URL"))
    ap.add_argument("--apply", action="store_true", help="실제로 변경한다(기본은 계획만 출력)")
    args = ap.parse_args()

    base = (args.site or "").rstrip("/")
    if not base:
        sys.exit("--site 또는 WP_URL 필요")
    auth, api = _auth(), f"{base}/wp-json/wp/v2"
    s = requests.Session()
    s.auth, s.headers = auth, UA

    default_id = s.get(f"{api}/settings", timeout=30).json()["default_category"]
    cats = s.get(f"{api}/categories?per_page=100&_fields=id,slug,name,count", timeout=30).json()
    by_name = {c["name"]: c for c in cats}

    merges, deletes, skipped = [], [], []
    for c in cats:
        stripped = c["name"].strip("`").strip()
        if stripped != c["name"] and stripped in by_name:
            merges.append((c, by_name[stripped]))
        elif c["count"] == 0:
            (skipped if c["id"] == default_id else deletes).append(c)

    print(f"대상: {base} (카테고리 {len(cats)}개, 기본 카테고리 id={default_id})\n")
    print("[병합] 백틱 중복 → 정상 카테고리")
    for src, dst in merges:
        print(f"  {_label(src)}  →  {_label(dst)}")
    print("\n[삭제] 글 0개")
    for c in deletes:
        print(f"  {_label(c)}")
    for c in skipped:
        print(f"  (건너뜀 — 기본 카테고리라 삭제 불가) {_label(c)}")

    if not args.apply:
        print("\n계획만 출력했습니다. 실행하려면 --apply")
        return 0

    print("\n=== 실행 ===")
    for src, dst in merges:
        posts = s.get(f"{api}/posts?categories={src['id']}&per_page=100&status={STATUSES}"
                      f"&_fields=id,slug,categories", timeout=60).json()
        for p in posts:
            new = [cid for cid in p["categories"] if cid != src["id"]]
            if dst["id"] not in new:
                new.append(dst["id"])
            r = s.post(f"{api}/posts/{p['id']}", json={"categories": new}, timeout=60)
            r.raise_for_status()
            print(f"  재배정 #{p['id']} {urllib.parse.unquote(p['slug'])[:40]} → {dst['name']}")
        r = s.delete(f"{api}/categories/{src['id']}?force=true", timeout=30)
        r.raise_for_status()
        print(f"  삭제 {_label(src)}")

    for c in deletes:
        r = s.delete(f"{api}/categories/{c['id']}?force=true", timeout=30)
        r.raise_for_status()
        print(f"  삭제 {_label(c)}")

    left = s.get(f"{api}/categories?per_page=100&_fields=id,slug,name,count", timeout=30).json()
    print(f"\n[결과] 카테고리 {len(cats)}개 → {len(left)}개")
    for c in sorted(left, key=lambda x: -x["count"]):
        print(f"  {c['count']:>4}글  {c['name']}  /{urllib.parse.unquote(c['slug'])}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
