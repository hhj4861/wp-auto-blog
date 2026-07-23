#!/usr/bin/env python3
"""trendpulse 건강 글에 쿠팡 파트너스 상품 박스 삽입 (부트스트랩용).

GitHub Actions에서 WP_GENERAL_* 시크릿으로 실행한다 (site-fix-nav 패턴).
- 대상 글을 검색으로 찾아 '함께 챙기면 좋은 보충제' 박스를 결론 앞에 삽입
- rel="nofollow sponsored" 부착, 쿠팡 의무 고지문은 가드레일이 자동 삽입
- 멱등: 이미 쿠팡 링크가 있으면 건너뜀
"""

import os
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.monetization import add_coupang_disclosure, insert_related_box  # noqa: E402

# 삽입 대상: (검색어, 박스 항목들)
TARGETS = [
    (
        "미네랄이 수면과 집중력",
        [
            {
                "title": "식물성 멜라토닌 2mg + 테아닌 나잇 (식약처 인증 수면 영양제)",
                "url": "https://link.coupang.com/a/fCnS1Z77W8",
            },
            {
                "title": "락토핏 생유산균 골드 (장 건강 국민 유산균)",
                "url": "https://link.coupang.com/a/fCnXmvwMsS",
            },
        ],
    ),
]

HEADING = "💊 함께 챙기면 좋은 보충제 (쿠팡 최저가)"


def main() -> int:
    base = os.environ["WP_GENERAL_URL"].rstrip("/")
    auth = (os.environ["WP_GENERAL_USERNAME"], os.environ["WP_GENERAL_APP_PASSWORD"])
    api = f"{base}/wp-json/wp/v2"

    failed = 0
    for search, items in TARGETS:
        r = requests.get(
            f"{api}/posts",
            auth=auth,
            params={"search": search, "per_page": 3, "status": "publish",
                    "_fields": "id,title"},
            timeout=30,
        )
        r.raise_for_status()
        posts = r.json()
        if not posts:
            print(f"NOT FOUND: {search}")
            failed += 1
            continue
        pid = posts[0]["id"]

        p = requests.get(
            f"{api}/posts/{pid}", auth=auth,
            params={"context": "edit", "_fields": "id,link,content.raw"}, timeout=30,
        ).json()
        raw = p["content"]["raw"]

        if "link.coupang.com" in raw:
            print(f"SKIP (이미 삽입됨): #{pid} {p['link']}")
            continue

        html = insert_related_box(raw, items, heading=HEADING)
        # 제휴 링크 rel 부착 (쿠팡 링크에만)
        html = re.sub(
            r'<a href="(https://link\.coupang\.com/[^"]+)"',
            r'<a href="\1" target="_blank" rel="nofollow sponsored"',
            html,
        )
        html = add_coupang_disclosure(html)

        requests.post(
            f"{api}/posts/{pid}", auth=auth, json={"content": html}, timeout=60,
        ).raise_for_status()
        print(f"OK: #{pid} {p['link']} — 상품 {len(items)}개 + 고지문 삽입")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
