#!/usr/bin/env python3
"""발행된 글 중 본문이 비었거나 깨진 글을 찾아 draft로 강등한다.

증상: 본문 텍스트가 극단적으로 짧음(생성 실패·잘림), 제목과 본문 불일치.
레거시 저품질 글 정리 겸, 색인 대상에서 깨진 글을 제거한다.

DRY_RUN=true면 대상만 보고. MIN_CHARS 미만을 깨진 글로 판정(기본 400자).
"""

import os
import re

import requests

BASE_URL = (os.environ.get("WP_GENERAL_URL") or "").rstrip("/")
API = f"{BASE_URL}/wp-json/wp/v2"
DRY_RUN = (os.environ.get("DRY_RUN", "true").lower() != "false")
MIN_CHARS = int(os.environ.get("MIN_CHARS", "400"))

session = requests.Session()
session.auth = (os.environ.get("WP_GENERAL_USERNAME", ""),
                os.environ.get("WP_GENERAL_APP_PASSWORD", ""))
session.headers.update({"User-Agent": "Mozilla/5.0 (trendpulse-broken-audit)"})


def body_text_len(html: str) -> int:
    """스크립트/스타일/태그 제거 후 순수 본문 글자 수."""
    t = re.sub(r"<script[\s\S]*?</script>", "", html)
    t = re.sub(r"<style[\s\S]*?</style>", "", t)
    # figcaption(사진 출처)·광고 라벨은 본문으로 치지 않음
    t = re.sub(r"<figcaption[\s\S]*?</figcaption>", "", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", t)
    return len(t.strip())


def main():
    if not BASE_URL:
        raise SystemExit("WP_GENERAL_URL 필요")
    print(f"대상: {BASE_URL} | DRY_RUN={DRY_RUN} | 기준: 본문 {MIN_CHARS}자 미만\n{'=' * 62}")

    broken, checked = [], 0
    page = 1
    while True:
        r = session.get(f"{API}/posts", params={
            "status": "publish", "per_page": 100, "page": page, "context": "edit",
            "_fields": "id,slug,title,content"}, timeout=60)
        if r.status_code == 400:
            break
        r.raise_for_status()
        posts = r.json()
        if not posts:
            break
        for p in posts:
            checked += 1
            raw = p["content"].get("raw") or ""
            n = body_text_len(raw)
            if n < MIN_CHARS:
                broken.append((p["id"], n, p["title"].get("raw", "")[:48], p.get("slug", "")))
        total_pages = int(r.headers.get("X-WP-TotalPages", "1"))
        if page >= total_pages:
            break
        page += 1

    broken.sort(key=lambda x: x[1])
    print(f"발행글 {checked}건 점검 → 깨진 글 {len(broken)}건\n")
    for pid, n, title, slug in broken:
        print(f"  #{pid} ({n:>4}자) {title}")
        print(f"        /{slug}/")

    if not DRY_RUN and broken:
        print(f"\n{len(broken)}건 draft 강등 중...")
        for pid, _, _, _ in broken:
            ur = session.post(f"{API}/posts/{pid}", json={"status": "draft"}, timeout=40)
            if ur.status_code != 200:
                print(f"  ⚠️ #{pid} 실패 {ur.status_code}")
        print("완료")
    elif DRY_RUN:
        print("\nDRY_RUN — 변경 없음. 적용하려면 DRY_RUN=false")


if __name__ == "__main__":
    main()
