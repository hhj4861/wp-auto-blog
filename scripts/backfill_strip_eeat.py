#!/usr/bin/env python3
"""기존 발행글에서 허위 E-E-A-T(가짜 저자·팀·테스트 주장) 일괄 제거.

AdSense '저가치/기만적 콘텐츠' 대응 — src.monetization.strip_fabricated_eeat 재사용.
단건 조회(context=edit)로 CDN 캐시 함정 회피, 변경분만 업데이트(멱등).

사용법:  venv/bin/python scripts/backfill_strip_eeat.py
"""
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.monetization import strip_fabricated_eeat  # noqa: E402


def main() -> int:
    load_dotenv(str(Path(__file__).parent.parent / ".env"))
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
        batch = r.json()
        if not batch:
            break
        ids += [p["id"] for p in batch]
        page += 1
    print(f"발행글 {len(ids)}개 스캔")

    changed = errors = 0
    for pid in ids:
        try:
            p = requests.get(f"{api}/posts/{pid}", auth=auth,
                             params={"context": "edit", "_fields": "id,content.raw"},
                             timeout=30).json()
            raw = p["content"]["raw"]
            new = strip_fabricated_eeat(raw)
            if new != raw:
                requests.post(f"{api}/posts/{pid}", auth=auth,
                              json={"content": new}, timeout=60).raise_for_status()
                changed += 1
        except Exception as e:
            errors += 1
            print(f"  실패 #{pid}: {e}")

    print(f"\n완료: 허위 E-E-A-T 제거 {changed}개 글 / 실패 {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
