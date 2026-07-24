#!/usr/bin/env python3
"""레거시 저품질 글을 draft로 내려 도메인 품질 신호를 머니 글에 집중시킨다.

배경 (2026-07-24 GSC): 구글이 1월에 레거시 HN 번역글을 크롤 후 '색인 가치 없음'
판정(크롤링됨-미색인 30건) → 도메인 신뢰도 하락 → 6개월간 재크롤 중단.
레거시를 걷어내면 재크롤 시 소수 정예 고품질 사이트로 재평가된다.

판별: 신규 파이프라인 머니 글은 ASCII 슬러그(financial-investment-tax-...),
레거시 글은 한글 슬러그(%-인코딩). 슬러그에 비ASCII가 있으면 레거시로 본다.
페이지(privacy/about/contact)와 ASCII 슬러그 글은 유지.

DRY_RUN=true면 대상만 보고. KEEP_SLUGS(콤마구분)로 예외 지정 가능.
"""

import os
import re

import requests

BASE_URL = (os.environ.get("WP_GENERAL_URL") or "").rstrip("/")
API = f"{BASE_URL}/wp-json/wp/v2"
DRY_RUN = (os.environ.get("DRY_RUN", "true").lower() != "false")
KEEP_SLUGS = {s.strip() for s in os.environ.get("KEEP_SLUGS", "").split(",") if s.strip()}

session = requests.Session()
session.auth = (os.environ.get("WP_GENERAL_USERNAME", ""),
                os.environ.get("WP_GENERAL_APP_PASSWORD", ""))
session.headers.update({"User-Agent": "Mozilla/5.0 (trendpulse-concentrate)"})

ASCII_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# 구 파이프라인의 템플릿 접미사 — 영문 슬러그여도 이게 붙으면 레거시(개편 전 글).
# -guide-YYYY는 신규 머니 글(energy-cashback-apply-guide-2026 등)과 충돌하므로 제외.
# 누출된 레거시 IT 글은 전부 -review-YYYY 패턴.
LEGACY_SUFFIX_RE = re.compile(r"-review-\d{4}$")


def is_legacy(slug: str) -> bool:
    """레거시 판정: 한글 %-인코딩 슬러그이거나, 구 템플릿 접미사(-review-YYYY 등)를
    가진 영문 슬러그. 신규 머니 글은 -status/-wetax/…-guide 등 서술형 슬러그라 걸리지 않는다.

    단, 신규 머니 글이 우연히 -guide-YYYY 형태면 KEEP_SLUGS로 예외 지정한다.
    """
    if slug in KEEP_SLUGS:
        return False
    if not ASCII_SLUG_RE.match(slug):
        return True  # 한글 슬러그 = 레거시
    return bool(LEGACY_SUFFIX_RE.search(slug))


def main():
    if not BASE_URL:
        raise SystemExit("WP_GENERAL_URL 필요")
    print(f"대상: {BASE_URL} | DRY_RUN={DRY_RUN}\n{'=' * 62}")

    keep, draft = [], []
    page = 1
    while True:
        r = session.get(f"{API}/posts", params={
            "status": "publish", "per_page": 100, "page": page, "context": "edit",
            "_fields": "id,slug,title,categories"}, timeout=60)
        if r.status_code == 400:
            break
        r.raise_for_status()
        posts = r.json()
        if not posts:
            break
        for p in posts:
            slug = p.get("slug", "")
            title = p["title"].get("raw", "")[:46]
            (draft if is_legacy(slug) else keep).append((p["id"], slug, title))
        total_pages = int(r.headers.get("X-WP-TotalPages", "1"))
        if page >= total_pages:
            break
        page += 1

    print(f"유지(머니 글) {len(keep)}건 · 레거시 draft {len(draft)}건\n")
    print("--- 유지되는 글 (전체) ---")
    for pid, slug, title in keep:
        print(f"  KEEP #{pid} /{slug}/  {title}")
    print(f"\n--- draft 강등되는 레거시 (처음 30건 / 총 {len(draft)}) ---")
    for pid, slug, title in draft[:30]:
        print(f"  DRAFT #{pid} {title}")

    if not DRY_RUN and draft:
        print(f"\n{len(draft)}건 draft 강등 중...")
        done = 0
        for pid, _, _ in draft:
            ur = session.post(f"{API}/posts/{pid}", json={"status": "draft"}, timeout=40)
            if ur.status_code == 200:
                done += 1
            else:
                print(f"  ⚠️ #{pid} 실패 {ur.status_code}")
        print(f"완료: {done}/{len(draft)}건")
    elif DRY_RUN:
        print("\nDRY_RUN — 변경 없음. 적용하려면 DRY_RUN=false")


if __name__ == "__main__":
    main()
