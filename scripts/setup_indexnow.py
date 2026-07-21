#!/usr/bin/env python3
"""IndexNow 최초 설정: 키 파일을 WP 미디어에 업로드하고 기존 발행 URL을 일괄 제출한다."""

import os
import re
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.indexnow import INDEXNOW_KEY, INDEXNOW_KEY_LOCATION, ping_urls  # noqa: E402

BASE_URL = (os.environ.get("WP_GENERAL_URL") or "").rstrip("/")
API = f"{BASE_URL}/wp-json/wp/v2"

session = requests.Session()
session.auth = (os.environ.get("WP_GENERAL_USERNAME", ""),
                os.environ.get("WP_GENERAL_APP_PASSWORD", ""))
session.headers.update({"User-Agent": "Mozilla/5.0 (trendpulse-indexnow-setup)"})


def ensure_key_file():
    # 이미 접근 가능하면 스킵
    r = requests.get(INDEXNOW_KEY_LOCATION, timeout=20,
                     headers={"User-Agent": "Mozilla/5.0"})
    if r.status_code == 200 and r.text.strip() == INDEXNOW_KEY:
        print(f"키 파일 이미 존재: {INDEXNOW_KEY_LOCATION}")
        return True
    ur = session.post(f"{API}/media", files={
        "file": (f"{INDEXNOW_KEY}.txt", INDEXNOW_KEY.encode(), "text/plain"),
    }, timeout=60)
    if ur.status_code != 201:
        print(f"⚠️ 키 파일 업로드 실패({ur.status_code}): {ur.text[:200]}")
        return False
    url = ur.json().get("source_url", "")
    print(f"키 파일 업로드 완료: {url}")
    if url != INDEXNOW_KEY_LOCATION:
        print(f"⚠️ 업로드 URL이 코드 상수와 다름! src/indexnow.py의 "
              f"INDEXNOW_KEY_LOCATION을 다음으로 수정 필요: {url}")
    vr = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    print(f"키 파일 검증: HTTP {vr.status_code}, 내용 일치={vr.text.strip() == INDEXNOW_KEY}")
    return vr.status_code == 200


def bulk_ping():
    r = requests.get(f"{BASE_URL}/post-sitemap.xml", timeout=30,
                     headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    urls = re.findall(r"<loc>([^<]+)</loc>", r.text)
    print(f"사이트맵 URL {len(urls)}건 수집")
    ok = ping_urls(urls)
    print(f"일괄 제출 결과: {'성공' if ok else '실패'}")


if __name__ == "__main__":
    if ensure_key_file():
        bulk_ping()
