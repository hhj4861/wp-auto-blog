#!/usr/bin/env python3
"""GSC 사이트맵 제출·처리 상태 진단 — '미발견(디스커버리)' 원인 규명용.

색인 감사에서 대부분 URL이 'Google에 아직 알려지지 않은 URL'(미발견)로 나올 때,
그 최상류 원인이 '사이트맵 미제출/처리 실패/에러'인지 확정한다.

출력:
  1. GSC에 제출된 사이트맵 목록 (없으면 그것이 원인)
  2. 각 사이트맵의 마지막 제출/다운로드 시각, 대기·에러·경고, 유형별 제출/색인 수
  3. 사이트맵 파일 자체의 실제 URL 개수(사이트맵 접근성 교차확인)

dry 조회만. 아무것도 변경하지 않음.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.gsc_client import list_sitemaps, fetch_sitemap_urls, SITE_URL  # noqa: E402


def main() -> int:
    print(f"속성: {SITE_URL} | 사이트맵 제출·처리 상태")
    print("=" * 64)

    sitemaps = list_sitemaps(SITE_URL)
    if not sitemaps:
        print("\n🚨 GSC에 제출된 사이트맵이 **없음**.")
        print("   → 이것이 '미발견' 대량 발생의 유력한 최상류 원인입니다.")
        print("   → 조치: Search Console > 색인 > Sitemaps 에 sitemap_index.xml"
              " (또는 wp-sitemap.xml) 제출.")
    else:
        print(f"\n제출된 사이트맵 {len(sitemaps)}개:\n")
        for sm in sitemaps:
            path = sm.get("path", "?")
            print(f"▼ {path}")
            print(f"   마지막 제출:   {sm.get('lastSubmitted', '(없음)')}")
            print(f"   마지막 다운로드: {sm.get('lastDownloaded', '(없음/미처리)')}")
            print(f"   대기중(isPending): {sm.get('isPending', '?')}"
                  f"  | 인덱스형: {sm.get('isSitemapsIndex', '?')}")
            warns = sm.get("warnings", "0")
            errs = sm.get("errors", "0")
            print(f"   경고 {warns} · 에러 {errs}")
            for c in sm.get("contents", []):
                print(f"   - {c.get('type', '?')}: 제출 {c.get('submitted', '?')} "
                      f"· 색인 {c.get('indexed', '?')}")
            print()

    # 교차확인: 사이트맵 파일 자체는 접근·파싱되는가
    urls = fetch_sitemap_urls(SITE_URL, limit=10000)
    print(f"[교차확인] 사이트맵 파일 실접근 URL 수: {len(urls)}개"
          f" ({'접근 가능' if urls else '접근 실패 — 사이트맵 자체 문제 가능'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
