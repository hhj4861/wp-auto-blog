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


def ensure_bing_plugin():
    """Microsoft 공식 IndexNow 플러그인 설치/활성화 — 루트 키 서빙과
    발행 시 자동 제출을 플러그인이 처리한다."""
    r = session.get(f"{API}/plugins", params={"search": "indexnow"}, timeout=40)
    if r.status_code == 200:
        for p in r.json():
            if "indexnow" in p.get("plugin", "").lower():
                print(f"IndexNow 플러그인 이미 설치됨: {p['plugin']} (status={p['status']})")
                if p["status"] != "active":
                    ar = session.post(f"{API}/plugins/{p['plugin']}",
                                      json={"status": "active"}, timeout=60)
                    print(f"활성화: {ar.status_code}")
                return True
    ir = session.post(f"{API}/plugins",
                      json={"slug": "indexnow", "status": "active"}, timeout=120)
    if ir.status_code == 201:
        print(f"IndexNow 플러그인 설치+활성화 완료: {ir.json().get('plugin')}")
        return True
    print(f"⚠️ 플러그인 설치 실패({ir.status_code}): {ir.text[:200]}")
    return False


def check_root_key():
    """루트 키 파일 존재 확인 (수동 업로드 필요 항목)."""
    r = requests.get(INDEXNOW_KEY_LOCATION, timeout=20,
                     headers={"User-Agent": "Mozilla/5.0"})
    ok = r.status_code == 200 and r.text.strip() == INDEXNOW_KEY
    if ok:
        print(f"루트 키 파일 확인: {INDEXNOW_KEY_LOCATION}")
    else:
        print(f"루트 키 파일 없음(HTTP {r.status_code}) — Hostinger 파일 관리자에서 "
              f"public_html/{INDEXNOW_KEY}.txt (내용: 키 문자열)를 업로드하면 "
              f"일괄 제출이 가능해집니다")
    return ok


def bulk_ping():
    r = requests.get(f"{BASE_URL}/post-sitemap.xml", timeout=30,
                     headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    urls = re.findall(r"<loc>([^<]+)</loc>", r.text)
    print(f"사이트맵 URL {len(urls)}건 수집")
    ok = ping_urls(urls)
    print(f"일괄 제출 결과: {'성공' if ok else '실패'}")


if __name__ == "__main__":
    ensure_bing_plugin()
    if check_root_key():
        bulk_ping()
