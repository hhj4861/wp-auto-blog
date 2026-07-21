#!/usr/bin/env python3
"""지정한 draft 포스트를 발행한다 (POC 발행용)."""

import os

import requests

BASE_URL = (os.environ.get("WP_GENERAL_URL") or "").rstrip("/")
API = f"{BASE_URL}/wp-json/wp/v2"
POST_ID = int(os.environ.get("POC_POST_ID", "0"))
NEW_SLUG = (os.environ.get("POC_NEW_SLUG") or "").strip()

session = requests.Session()
session.auth = (os.environ.get("WP_GENERAL_USERNAME", ""),
                os.environ.get("WP_GENERAL_APP_PASSWORD", ""))
session.headers.update({"User-Agent": "Mozilla/5.0 (trendpulse-publish)"})


def main():
    if not POST_ID:
        raise SystemExit("POC_POST_ID 필요")
    r = session.get(f"{API}/posts/{POST_ID}", params={"context": "edit"}, timeout=60)
    r.raise_for_status()
    p = r.json()
    print(f"대상: #{POST_ID} {p['title']['raw']!r} (현재: {p['status']})")
    if p["status"] == "publish":
        if NEW_SLUG and p.get("slug") != NEW_SLUG:
            ur = session.post(f"{API}/posts/{POST_ID}", json={"slug": NEW_SLUG}, timeout=60)
            ur.raise_for_status()
            print(f"슬러그 교정: {p.get('slug')} → {NEW_SLUG}")
            print(f"새 링크: {ur.json()['link']} (구 슬러그는 WP가 자동 리다이렉트)")
        else:
            print(f"이미 발행됨: {p['link']}")
        return
    payload = {"status": "publish"}
    if NEW_SLUG:
        payload["slug"] = NEW_SLUG
    # 발행 전 기계적 결함 정리: ((...)) 인용 플레이스홀더 제거
    import re
    content = p["content"].get("raw") or ""
    cleaned = re.sub(r"\(\([^()\n]{2,60}\)\)", "", content)
    if cleaned != content:
        cleaned = re.sub(r"(?<=[가-힣\w.,]) {2,}(?=[가-힣\w])", " ", cleaned)
        payload["content"] = cleaned
        print("((...)) 플레이스홀더 제거 후 발행")
    ur = session.post(f"{API}/posts/{POST_ID}", json=payload, timeout=60)
    ur.raise_for_status()
    v = ur.json()
    print(f"발행 완료: {v['link']} (status={v['status']}, date={v['date']})")


if __name__ == "__main__":
    main()
