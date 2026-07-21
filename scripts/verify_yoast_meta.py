#!/usr/bin/env python3
"""Yoast 메타 REST 저장 여부 검증 스크립트.

wp-auto-blog 파이프라인이 보내는 _yoast_wpseo_* 메타가 실제로 WordPress에
저장되는지 확인한다. mu-plugin(wordpress/mu-plugins/wpab-yoast-rest-meta.php)
설치 전에는 FAIL(사일런트 드롭), 설치 후에는 PASS가 나와야 한다.

동작: 비공개 draft 테스트 글 생성 → context=edit로 재조회 → 메타 비교 → 글 삭제(force).

사용법:
    python scripts/verify_yoast_meta.py            # .env의 WP_URL 사이트 대상
"""

import os
import sys

import requests
from dotenv import load_dotenv

YOAST_TEST_META = {
    "_yoast_wpseo_metadesc": "wpab meta persistence probe",
    "_yoast_wpseo_focuskw": "wpab probe",
    "_yoast_wpseo_title": "wpab probe title",
    "_yoast_wpseo_meta-robots-noindex": "1",  # 테스트 글이므로 noindex
    "_yoast_wpseo_meta-robots-nofollow": "1",
}


def check_meta_persistence(sent: dict, readback: dict) -> list:
    """보낸 메타(sent)와 재조회 메타(readback)를 비교해 누락/불일치 키 목록을 반환한다."""
    missing = []
    for key, value in sent.items():
        if readback.get(key) != value:
            missing.append(key)
    return missing


def main() -> int:
    load_dotenv()
    wp_url = os.environ.get("WP_URL", "").rstrip("/")
    auth = (os.environ.get("WP_USERNAME", ""), os.environ.get("WP_APP_PASSWORD", ""))
    if not wp_url or not all(auth):
        print("ERROR: WP_URL / WP_USERNAME / WP_APP_PASSWORD 환경변수가 필요합니다")
        return 2

    api = f"{wp_url}/wp-json/wp/v2/posts"
    post_id = None
    try:
        resp = requests.post(
            api,
            auth=auth,
            json={
                "title": "[WPAB] yoast meta persistence probe",
                "content": "internal probe post - safe to delete",
                "status": "draft",
                "meta": YOAST_TEST_META,
            },
            timeout=30,
        )
        resp.raise_for_status()
        post_id = resp.json()["id"]
        print(f"draft 테스트 글 생성: id={post_id}")

        readback = requests.get(
            f"{api}/{post_id}", auth=auth, params={"context": "edit"}, timeout=30
        )
        readback.raise_for_status()
        stored_meta = readback.json().get("meta") or {}

        missing = check_meta_persistence(YOAST_TEST_META, stored_meta)
        if missing:
            print("FAIL: 다음 Yoast 메타가 저장되지 않았습니다 (REST에서 드롭됨):")
            for key in missing:
                print(f"  - {key} (저장값: {stored_meta.get(key)!r})")
            print("→ wordpress/mu-plugins/wpab-yoast-rest-meta.php를 서버에 설치하세요")
            return 1
        print("PASS: Yoast 메타 5종 모두 저장 확인 — mu-plugin 정상 동작")
        return 0
    finally:
        if post_id:
            requests.delete(f"{api}/{post_id}", auth=auth, params={"force": 1}, timeout=30)
            print(f"테스트 글 삭제 완료: id={post_id}")


if __name__ == "__main__":
    sys.exit(main())
