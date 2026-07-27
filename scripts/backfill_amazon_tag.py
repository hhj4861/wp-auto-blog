#!/usr/bin/env python3
"""기존 발행글의 무태그 Amazon 링크에 Associate 태그(bytepulse08-20) 부착.

AFFILIATE_AMAZON env(tag=bytepulse08-20)를 apply_affiliate로 주입. 이미 태그가
있으면 건드리지 않는다(멱등). 단건 조회(context=edit)로 CDN 캐시 함정 회피.

사용법:  venv/bin/python scripts/backfill_amazon_tag.py
"""
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.monetization import apply_affiliate  # noqa: E402

# amazon.com 링크 중 tag= 파라미터가 없는 것만 대상
_AMZN_HREF = re.compile(r'href="(https://www\.amazon\.com/[^"]*)"')


def _tag_href(href: str) -> str:
    if "tag=" in href:
        return href  # 이미 태그 있음
    return apply_affiliate(href, "amazon")


def main() -> int:
    load_dotenv(str(Path(__file__).parent.parent / ".env"))
    if "tag=" not in os.environ.get("AFFILIATE_AMAZON", ""):
        print("ERROR: AFFILIATE_AMAZON(tag=...) env 미설정")
        return 2
    api = os.environ["WP_URL"].rstrip("/") + "/wp-json/wp/v2"
    auth = (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])

    ids, page = [], 1
    while True:
        r = requests.get(f"{api}/posts", auth=auth,
                         params={"per_page": 100, "page": page, "status": "publish",
                                 "_fields": "id"}, timeout=60)
        if r.status_code == 400:
            break
        r.raise_for_status()
        b = r.json()
        if not b:
            break
        ids += [p["id"] for p in b]
        page += 1
    print(f"발행글 {len(ids)}개 스캔")

    changed = links = errors = 0
    for pid in ids:
        try:
            p = requests.get(f"{api}/posts/{pid}", auth=auth,
                             params={"context": "edit", "_fields": "id,content.raw"},
                             timeout=30).json()
            raw = p["content"]["raw"]
            if "amazon.com" not in raw:
                continue
            n = [0]

            def _sub(m):
                new = _tag_href(m.group(1))
                if new != m.group(1):
                    n[0] += 1
                return f'href="{new}"'

            new_raw = _AMZN_HREF.sub(_sub, raw)
            if new_raw != raw:
                requests.post(f"{api}/posts/{pid}", auth=auth,
                              json={"content": new_raw}, timeout=60).raise_for_status()
                changed += 1
                links += n[0]
        except Exception as e:
            errors += 1
            print(f"  실패 #{pid}: {e}")

    print(f"\n완료: 글 {changed}개 / Amazon 링크 {links}건 태그 부착 / 실패 {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
