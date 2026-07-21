#!/usr/bin/env python3
"""저사용 태그 정리 스크립트 (bytepulse.io 태그 스프롤 대응).

글 사용 수(count)가 임계값 이하인 태그를 삭제한다. 주의할 점 두 가지:
- WP의 태그 count는 '발행된 글'만 센다. draft/pending/future/private에
  달린 태그가 count=0으로 보이므로, 비공개 글의 태그는 조회해서 보호한다.
- 핵심 태그는 화이트리스트로 보호한다.

기본은 DRY-RUN이며 --apply를 줘야 실제 삭제한다.

사용법:
    python scripts/cleanup_unused_tags.py                    # count=0 대상 미리보기
    python scripts/cleanup_unused_tags.py --apply            # count=0 삭제
    python scripts/cleanup_unused_tags.py --max-count 1 --apply  # 1회 사용 태그까지 삭제
"""

import argparse
import os
import sys

import requests
from dotenv import load_dotenv

# 삭제하지 않는 핵심 태그 (소문자 비교)
TAG_WHITELIST = {
    "ai", "machine learning", "llm", "automation", "saas", "cloud",
    "developer tools", "coding", "workflow", "startup", "api", "backend",
    "frontend", "security", "k-pop", "kpop", "korean pop", "idol",
    "k-beauty", "korean skincare", "korean beauty", "korean cosmetics",
    "k-food", "korean food", "korean cuisine", "korean recipe",
    "k-fashion", "korean fashion", "korean style", "fandom",
}


def fetch_paged(api: str, auth: tuple, path: str, params: dict) -> list:
    items = []
    page = 1
    while True:
        resp = requests.get(
            f"{api}/{path}",
            auth=auth,
            params={**params, "per_page": 100, "page": page},
            timeout=30,
        )
        if resp.status_code == 400:  # 페이지 초과
            break
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        items.extend(batch)
        page += 1
    return items


def protected_tag_ids(api: str, auth: tuple) -> set:
    """비공개(draft/pending/future/private) 글에 달린 태그 ID 집합."""
    posts = fetch_paged(
        api, auth, "posts",
        {"status": "draft,pending,future,private", "_fields": "id,tags",
         "context": "edit"},
    )
    ids = set()
    for p in posts:
        ids.update(p.get("tags") or [])
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="실제로 삭제 실행")
    parser.add_argument(
        "--max-count", type=int, default=0,
        help="이 사용 수 이하의 태그를 삭제 대상으로 본다 (기본 0 = 미사용만)",
    )
    args = parser.parse_args()

    load_dotenv()
    wp_url = os.environ.get("WP_URL", "").rstrip("/")
    auth = (os.environ.get("WP_USERNAME", ""), os.environ.get("WP_APP_PASSWORD", ""))
    if not wp_url or not all(auth):
        print("ERROR: WP_URL / WP_USERNAME / WP_APP_PASSWORD 환경변수가 필요합니다")
        return 2

    api = f"{wp_url}/wp-json/wp/v2"
    tags = fetch_paged(api, auth, "tags", {"_fields": "id,name,count"})
    protected = protected_tag_ids(api, auth)

    targets = [
        t for t in tags
        if t.get("count", 0) <= args.max_count
        and t["id"] not in protected
        and t["name"].strip().lower() not in TAG_WHITELIST
    ]
    skipped_protected = sum(
        1 for t in tags if t.get("count", 0) <= args.max_count and t["id"] in protected
    )
    print(
        f"전체 태그 {len(tags)}개 | count<={args.max_count} 대상 {len(targets)}개 "
        f"(비공개 글 보호 {skipped_protected}개, 화이트리스트 보호 별도)"
    )

    if not targets:
        return 0
    for t in targets[:20]:
        print(f"  - #{t['id']} {t['name']} (count={t.get('count', 0)})")
    if len(targets) > 20:
        print(f"  ... 외 {len(targets) - 20}개")

    if not args.apply:
        print("\nDRY-RUN: 삭제하지 않았습니다. 실제 삭제는 --apply를 붙이세요.")
        return 0

    deleted = failed = 0
    for t in targets:
        try:
            resp = requests.delete(
                f"{api}/tags/{t['id']}", auth=auth, params={"force": 1}, timeout=30
            )
            resp.raise_for_status()
            deleted += 1
        except Exception as e:
            failed += 1
            print(f"  삭제 실패 #{t['id']} {t['name']}: {e}")
    print(f"삭제 완료: {deleted}개, 실패 {failed}개")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
