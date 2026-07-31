#!/usr/bin/env python3
"""발행글 광고 유닛에 min-height 공간 예약 추가 — CLS(레이아웃 밀림) 완화.

인-아티클 AdSense가 로드되는 순간 본문이 아래로 밀리며 CLS가 발생
(Lighthouse 2026-07-31: bytepulse 모바일 CLS 0.322). ins에 min-height:280px를
예약해 광고 로드 전후 레이아웃을 고정한다. 멱등 — 이미 min-height 있으면 무변경.

사용법:
  로컬(bytepulse):  venv/bin/python scripts/fix_ad_cls.py       (.env의 WP_URL)
  CI(trendpulse):   trendpulse-coupang.yml 러너로 실행           (WP_GENERAL_* env)
"""
import os
import sys
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
except ImportError:  # CI 러너에는 dotenv 미설치 — Secrets env를 그대로 쓴다
    load_dotenv = None

OLD = ('<ins class="adsbygoogle" style="display:block; text-align:center;" '
       'data-ad-layout="in-article"')
NEW = ('<ins class="adsbygoogle" style="display:block; text-align:center; '
       'min-height:280px;" data-ad-layout="in-article"')


def main() -> int:
    if load_dotenv:
        load_dotenv(str(Path(__file__).parent.parent / ".env"))
    url = os.environ.get("WP_URL") or os.environ["WP_GENERAL_URL"]
    api = url.rstrip("/") + "/wp-json/wp/v2"
    auth = (os.environ.get("WP_USERNAME") or os.environ["WP_GENERAL_USERNAME"],
            os.environ.get("WP_APP_PASSWORD") or os.environ["WP_GENERAL_APP_PASSWORD"])

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
            if OLD not in raw:
                continue
            requests.post(f"{api}/posts/{pid}", auth=auth,
                          json={"content": raw.replace(OLD, NEW)},
                          timeout=60).raise_for_status()
            changed += 1
        except Exception as e:
            errors += 1
            print(f"  실패 #{pid}: {e}")

    print(f"\n완료: 광고 CLS 예약 {changed}개 글 / 실패 {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
