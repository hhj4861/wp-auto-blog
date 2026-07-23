#!/usr/bin/env python3
"""발행된 머니 글에 FAQPage JSON-LD를 소급 삽입한다.

이미 파이프라인에 build_faq_schema가 들어갔으므로 신규 글은 자동 처리된다.
이 스크립트는 그 전에 발행된 글에만 소급 적용한다. DRY_RUN=true면 대상만 보고.
"""

import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.monetization import build_faq_schema  # noqa: E402

BASE_URL = (os.environ.get("WP_GENERAL_URL") or "").rstrip("/")
API = f"{BASE_URL}/wp-json/wp/v2"
DRY_RUN = (os.environ.get("DRY_RUN", "true").lower() != "false")

session = requests.Session()
session.auth = (os.environ.get("WP_GENERAL_USERNAME", ""),
                os.environ.get("WP_GENERAL_APP_PASSWORD", ""))
session.headers.update({"User-Agent": "Mozilla/5.0 (trendpulse-faq-schema)"})


def main():
    r = session.get(f"{API}/posts", params={
        "status": "publish", "per_page": 40, "orderby": "date", "order": "desc",
        "context": "edit", "_fields": "id,slug,title,content"}, timeout=60)
    r.raise_for_status()

    applied = 0
    for p in r.json():
        html = p["content"].get("raw") or ""
        schema = build_faq_schema(html)
        if not schema:
            continue  # FAQ 없음 또는 이미 스키마 있음
        applied += 1
        print(f"  #{p['id']} {p['title'].get('raw','')[:44]:46} → 스키마 추가")
        if not DRY_RUN:
            ur = session.post(f"{API}/posts/{p['id']}",
                              json={"content": html + "\n" + schema}, timeout=60)
            if ur.status_code != 200:
                print(f"    ⚠️ 실패 {ur.status_code}: {ur.text[:120]}")

    print(f"\nFAQ 스키마 적용: {applied}건")
    if DRY_RUN:
        print("DRY_RUN — 변경 없음")


if __name__ == "__main__":
    main()
