#!/usr/bin/env python3
"""GSC 정밀 색인 감사 — 사이트맵 전 URL을 URL Inspection API로 실제 색인 상태 분류.

'노출된 페이지 수'(Search Analytics)는 색인의 하한선일 뿐이다. 이 스크립트는
사이트맵의 모든 URL을 하나씩 검사해 실제 색인/미색인과 그 사유를 집계한다.

출력:
  1. 총 URL 수 (사이트맵)
  2. 색인 상태별 집계 (coverageState)
  3. 미색인 URL 목록 (사유별) — 정리·개선 판단 자료

쿼터: 속성당 ~2000/일. GSC_MAX(기본 500)로 상한. dry 조회만 하며 아무것도 변경 안 함.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.gsc_client import inspect_url, fetch_sitemap_urls, SITE_URL  # noqa: E402

MAX = int(os.getenv("GSC_MAX", "500"))
SLEEP = float(os.getenv("GSC_SLEEP", "0.4"))  # 쿼터·레이트 완충


def bucket(cov: str) -> str:
    """coverageState를 거친 카테고리로 묶는다."""
    c = cov.lower()
    if "and indexed" in c or c == "indexed":
        return "INDEXED"
    if "noindex" in c:
        return "NOINDEX"
    if "duplicate" in c or "canonical" in c or "alternate" in c:
        return "DUPLICATE/CANONICAL"
    if "crawled" in c and "not indexed" in c:
        return "CRAWLED_NOT_INDEXED"
    if "discovered" in c and "not indexed" in c:
        return "DISCOVERED_NOT_INDEXED"
    if "redirect" in c:
        return "REDIRECT"
    if "not found" in c or "404" in c:
        return "NOT_FOUND"
    if "blocked" in c or "robots" in c:
        return "BLOCKED"
    return f"OTHER: {cov or '(빈값)'}"


def main() -> int:
    print(f"속성: {SITE_URL} | URL Inspection 정밀 감사 (상한 {MAX})")
    print("=" * 64)

    urls = fetch_sitemap_urls(SITE_URL, limit=MAX * 2)
    if not urls:
        print("사이트맵에서 URL을 찾지 못함 — sitemap_index.xml / wp-sitemap.xml 확인 필요")
        return 1
    total_sitemap = len(urls)
    urls = urls[:MAX]
    print(f"사이트맵 URL {total_sitemap}개 (이번 검사 {len(urls)}개)\n")

    counts: dict[str, int] = {}
    not_indexed: dict[str, list[str]] = {}
    errors = 0

    for i, u in enumerate(urls, 1):
        res = inspect_url(u, SITE_URL)
        if res.get("verdict") == "ERROR":
            errors += 1
            if errors <= 3:
                print(f"  [검사오류] {u} — {res.get('error')}")
            time.sleep(SLEEP)
            continue
        cat = bucket(res.get("coverageState", ""))
        counts[cat] = counts.get(cat, 0) + 1
        if cat != "INDEXED":
            not_indexed.setdefault(cat, []).append(u)
        if i % 25 == 0:
            print(f"  ...{i}/{len(urls)} 검사")
        time.sleep(SLEEP)

    checked = sum(counts.values())
    indexed = counts.get("INDEXED", 0)
    print(f"\n[집계] 검사 {checked}개 · 색인 {indexed}개 · 미색인 {checked - indexed}개"
          f" · 검사오류 {errors}개")
    rate = (indexed / checked * 100) if checked else 0
    print(f"[색인율] {rate:.1f}%\n")

    print("[상태별 분포]")
    for cat, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {n:>4}  {cat}")

    print("\n[미색인 URL — 사유별] (사유당 최대 40개)")
    for cat, lst in sorted(not_indexed.items(), key=lambda x: -len(x[1])):
        print(f"\n  ▼ {cat} ({len(lst)}개)")
        for u in lst[:40]:
            path = u.replace(SITE_URL.rstrip("/"), "")
            print(f"    {path}")
        if len(lst) > 40:
            print(f"    ... 외 {len(lst) - 40}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
