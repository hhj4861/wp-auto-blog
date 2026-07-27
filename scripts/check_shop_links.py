#!/usr/bin/env python3
"""쇼핑몰 검색 URL 형식 헬스체크 — 몰이 검색 경로를 바꾸면 404로 감지.

SHOP_SEARCH_URLS(src.monetization, 단일 소스)의 각 템플릿에 샘플 쿼리를 넣어
실제 요청한다. 판정 규칙:
  - 404/410 → 형식 깨짐(확정) → exit 1  ⇒ CI 잡 실패 → GitHub이 소유자에게 메일
  - 403/5xx/타임아웃 → 봇차단·일시 장애일 수 있어 경고만 (올리브영은 curl에 403 주지만
    브라우저는 정상 — 2026-07-27 실측)
  - 2xx/3xx → 정상

깨짐 감지 시 복구 절차: SHOP_SEARCH_URLS에서 새 형식으로 교체(한 곳) →
scripts/fix_shop_link_formats.py의 REWRITES에 (구형식, 신형식) 추가 → 실행(소급).

사용법:  venv/bin/python scripts/check_shop_links.py
"""
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.monetization import SHOP_SEARCH_URLS  # noqa: E402

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
SAMPLE_QUERY = "korean%20skincare"


def main() -> int:
    # 별칭 키(musinsa/musinsa global 등)가 같은 템플릿을 가리키므로 URL 기준 중복 제거
    templates = {}
    for retailer, tpl in SHOP_SEARCH_URLS.items():
        templates.setdefault(tpl, retailer)

    broken, warned = [], []
    for tpl, retailer in templates.items():
        url = tpl.format(q=SAMPLE_QUERY)
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=20,
                             allow_redirects=True)
            status = r.status_code
        except requests.RequestException as e:
            warned.append((retailer, f"요청 실패: {e}"))
            print(f"⚠️  {retailer}: 요청 실패 ({e}) — 일시 장애일 수 있어 경고만")
            continue

        if status in (404, 410):
            broken.append((retailer, status, url))
            print(f"❌ {retailer}: HTTP {status} — 검색 URL 형식 깨짐: {url}")
        elif status >= 400:
            warned.append((retailer, f"HTTP {status}"))
            print(f"⚠️  {retailer}: HTTP {status} — 봇차단/일시 장애 추정, 경고만")
        else:
            print(f"✅ {retailer}: HTTP {status}")

    if broken:
        print(f"\n형식 깨짐 {len(broken)}건 — SHOP_SEARCH_URLS 수정 후 "
              "scripts/fix_shop_link_formats.py로 소급 교정 필요")
        return 1
    print(f"\n정상 (경고 {len(warned)}건)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
