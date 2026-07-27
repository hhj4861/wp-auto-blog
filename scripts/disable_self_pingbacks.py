#!/usr/bin/env python3
"""셀프 핑백 전면 차단 (일회성 정리, 멱등).

우리 글끼리의 내부링크가 글 저장/발행 때마다 핑백 승인 대기를 만들어 모더레이션
메일 노이즈가 됨. 조치:
  1. 사이트 기본 ping_status → closed (신규 글)
  2. 기존 전체 글 ping_status → closed (수신 거부 — 이후 재저장돼도 안 쌓임)
  3. 승인 대기 중인 pingback 댓글 휴지통 이동 (일반 댓글은 건드리지 않음)

신규 발행분은 wordpress_client.create_post가 ping_status=closed를 명시(코드 가드레일).

사용법:  venv/bin/python scripts/disable_self_pingbacks.py
"""
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv


def main() -> int:
    load_dotenv(str(Path(__file__).parent.parent / ".env"))
    api = os.environ["WP_URL"].rstrip("/") + "/wp-json/wp/v2"
    auth = (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])

    # 1) 사이트 기본값
    r = requests.post(f"{api}/settings", auth=auth,
                      json={"default_ping_status": "closed"}, timeout=30)
    r.raise_for_status()
    print(f"사이트 기본 ping_status → {r.json()['default_ping_status']}")

    # 2) 기존 글 전체 닫기 (이미 closed면 스킵)
    posts, page = [], 1
    while True:
        r = requests.get(f"{api}/posts", auth=auth,
                         params={"per_page": 100, "page": page,
                                 "status": "publish,draft",
                                 "_fields": "id,ping_status"}, timeout=60)
        if r.status_code == 400:
            break
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        posts += batch
        page += 1
    targets = [p["id"] for p in posts if p.get("ping_status") != "closed"]
    print(f"글 {len(posts)}개 중 ping_status open {len(targets)}개 닫는 중")

    errors = 0
    for pid in targets:
        try:
            requests.post(f"{api}/posts/{pid}", auth=auth,
                          json={"ping_status": "closed"},
                          timeout=60).raise_for_status()
        except Exception as e:
            errors += 1
            print(f"  실패 #{pid}: {e}")

    # 3) 대기 중 pingback 휴지통 (type=pingback만 — 일반 댓글 보존)
    r = requests.get(f"{api}/comments", auth=auth,
                     params={"status": "hold", "type": "pingback",
                             "per_page": 100, "_fields": "id"}, timeout=30)
    r.raise_for_status()
    pending = [c["id"] for c in r.json()]
    trashed = 0
    for cid in pending:
        try:
            requests.delete(f"{api}/comments/{cid}", auth=auth,
                            timeout=30).raise_for_status()
            trashed += 1
        except Exception as e:
            errors += 1
            print(f"  핑백 삭제 실패 #{cid}: {e}")

    print(f"\n완료: 글 {len(targets)}개 닫음, 대기 핑백 {trashed}개 휴지통 / 실패 {errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
