#!/usr/bin/env python3
"""GSC 사이트맵 강제 재제출 — 6개월 정체된 재수집을 깨우기 위한 조치.

이미 제출된 사이트맵을 다시 PUT 하면 Google이 현재 파일을 새로 내려받아
그동안 추가된 URL을 재발견한다. 소유자 권한이 없으면 403(그때는 GSC UI에서 수동).

대상: GSC에 이미 등록된 사이트맵 전부(list_sitemaps). 각각 재제출 결과 출력.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.gsc_client import list_sitemaps, submit_sitemap, SITE_URL  # noqa: E402


def main() -> int:
    print(f"속성: {SITE_URL} | 사이트맵 재제출")
    print("=" * 64)

    sitemaps = list_sitemaps(SITE_URL)
    if not sitemaps:
        print("등록된 사이트맵이 없음 — 재제출 대상 없음. UI에서 신규 제출 필요.")
        return 1

    any_ok = False
    forbidden = False
    for sm in sitemaps:
        path = sm.get("path", "")
        if not path:
            continue
        res = submit_sitemap(path, SITE_URL)
        mark = "✅ 재제출됨" if res["ok"] else f"❌ 실패({res['status']})"
        print(f"{mark}  {path}")
        if res["ok"]:
            any_ok = True
        else:
            if res["status"] == 403:
                forbidden = True
            if res["detail"]:
                print(f"      → {res['detail']}")

    print()
    if any_ok:
        print("재제출 성공 — 수일 내 lastDownloaded 갱신·미발견 감소 예상."
              " gsc-sitemap-status로 재확인.")
    elif forbidden:
        print("403 = 서비스계정에 소유자 권한 없음. GSC UI에서 수동 재제출 필요:")
        print("  Search Console > 색인 > Sitemaps > 기존 항목 삭제 후 sitemap_index.xml 다시 제출.")
    return 0 if any_ok else 2


if __name__ == "__main__":
    sys.exit(main())
