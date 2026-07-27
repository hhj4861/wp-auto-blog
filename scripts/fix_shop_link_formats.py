#!/usr/bin/env python3
"""발행글의 구형식 쇼핑몰 검색 URL 일괄 교정 (범용, 멱등).

몰이 검색 경로를 바꿔 링크가 404가 될 때마다 REWRITES에 (구형식, 신형식)을
추가하고 실행한다. check_shop_links.py(주간 CI)가 깨짐을 감지하는 짝 스크립트.

주의: 긴 패턴을 먼저 — 'search?q='는 'search?query='의 접두라서 순서가 바뀌면
      '?query=' 링크가 오염된다.

이력:
  - yesstyle /en/search?q= → /en/list.html?q=  (2026-07-27 실측 404)
  - oliveyoung /search?query=, /search?q= → /display/search?query=  (2026-07-23 실측 404)

사용법:  venv/bin/python scripts/fix_shop_link_formats.py
"""
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

REWRITES = [
    ("www.yesstyle.com/en/search?q=", "www.yesstyle.com/en/list.html?q="),
    ("global.oliveyoung.com/search?query=", "global.oliveyoung.com/display/search?query="),
    ("global.oliveyoung.com/search?q=", "global.oliveyoung.com/display/search?query="),
]


def rewrite(html: str) -> str:
    for old, new in REWRITES:
        html = html.replace(old, new)
    return html


def main() -> int:
    load_dotenv(str(Path(__file__).parent.parent / ".env"))
    api = os.environ["WP_URL"].rstrip("/") + "/wp-json/wp/v2"
    auth = (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])

    ids, page = [], 1
    while True:
        r = requests.get(f"{api}/posts", auth=auth,
                         params={"per_page": 100, "page": page,
                                 "status": "publish,draft", "_fields": "id"},
                         timeout=60)
        if r.status_code == 400:
            break
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        ids += [p["id"] for p in batch]
        page += 1
    print(f"글 {len(ids)}개 스캔 (publish+draft)")

    changed = errors = 0
    for pid in ids:
        try:
            p = requests.get(f"{api}/posts/{pid}", auth=auth,
                             params={"context": "edit", "_fields": "id,content.raw"},
                             timeout=30).json()
            raw = p["content"]["raw"]
            new = rewrite(raw)
            if new == raw:
                continue
            requests.post(f"{api}/posts/{pid}", auth=auth,
                          json={"content": new}, timeout=60).raise_for_status()
            changed += 1
            print(f"  교정 #{pid}")
        except Exception as e:
            errors += 1
            print(f"  실패 #{pid}: {e}")

    print(f"\n완료: 구형식 링크 교정 {changed}개 글 / 실패 {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
