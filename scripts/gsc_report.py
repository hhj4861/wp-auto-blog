#!/usr/bin/env python3
"""GSC 실적 리포트 — 페이지·검색어별 노출/클릭/순위를 뽑아 운영 판단 자료로 정리한다.

출력:
  1. 권한 확인 (접근 가능한 속성 목록)
  2. 요약 (총 클릭/노출/평균순위)
  3. 상위 페이지 (노출순) — 유지할 글
  4. 상위 검색어
  5. 리프레시 후보 (평균순위 8~20위, 노출 있음) — 조금만 밀면 1페이지
  6. 정리 후보 (기간 내 노출 0) — 여기 있는 것만 정리 대상

기간은 GSC_DAYS(기본 90)일. dry한 조회만 하며 아무것도 변경하지 않는다.
"""

import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.gsc_client import query, list_sites, SITE_URL  # noqa: E402

DAYS = int(os.getenv("GSC_DAYS", "90"))


def main():
    end = dt.date.today()
    start = end - dt.timedelta(days=DAYS)
    s, e = start.isoformat(), end.isoformat()
    print(f"속성: {SITE_URL} | 기간: {s} ~ {e} ({DAYS}일)\n{'=' * 64}")

    print("[권한 확인] 접근 가능한 속성:")
    for site in list_sites():
        mark = " ← 대상" if site.rstrip("/") == SITE_URL.rstrip("/") else ""
        print(f"  {site}{mark}")
    print()

    pages = query(s, e, ["page"])
    total_clicks = sum(p["clicks"] for p in pages)
    total_impr = sum(p["impressions"] for p in pages)
    avg_pos = (sum(p["position"] * p["impressions"] for p in pages) / total_impr
               if total_impr else 0)
    print(f"[요약] 클릭 {total_clicks} · 노출 {total_impr} · "
          f"색인·노출된 페이지 {len(pages)}개 · 가중평균순위 {avg_pos:.1f}\n")

    pages.sort(key=lambda p: -p["impressions"])
    print(f"[상위 페이지 — 노출순 / 유지 대상] (총 {len(pages)}개 중 상위 20)")
    for p in pages[:20]:
        slug = p["page"].rstrip("/").split("/")[-1][:44]
        print(f"  노출{p['impressions']:>5} 클릭{p['clicks']:>3} "
              f"순위{p['position']:>5.1f}  /{slug}/")

    queries = query(s, e, ["query"])
    queries.sort(key=lambda q: -q["impressions"])
    print(f"\n[상위 검색어] (총 {len(queries)}개 중 상위 15)")
    for q in queries[:15]:
        print(f"  노출{q['impressions']:>5} 클릭{q['clicks']:>3} "
              f"순위{q['position']:>5.1f}  {q['query'][:40]}")

    refresh = [p for p in pages if 8 <= p["position"] <= 20 and p["impressions"] >= 3]
    refresh.sort(key=lambda p: -p["impressions"])
    print(f"\n[리프레시 후보 — 8~20위, 조금만 밀면 1페이지] ({len(refresh)}개)")
    for p in refresh[:15]:
        slug = p["page"].rstrip("/").split("/")[-1][:44]
        print(f"  노출{p['impressions']:>5} 순위{p['position']:>5.1f}  /{slug}/")

    print(f"\n[정리 후보 판단] 노출 있는 페이지 {len(pages)}개는 '유지'. "
          f"이 목록에 없는 발행글이 '기간 내 노출 0' = 정리 후보입니다.")
    print("  (발행글 전체와 대조하려면 gsc_prune.py 참조 — 별도 실행)")


if __name__ == "__main__":
    main()
