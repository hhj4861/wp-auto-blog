#!/usr/bin/env python3
"""지정한 draft 포스트를 발행한다 (POC 발행용).

POC_CATEGORY가 지정되면 정책형 고지 문구(기준일·투자/의료)를 코드로 삽입 후 발행한다.
"""

import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

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
        print("((...)) 플레이스홀더 제거 후 발행")
    # 정책형 고지 문구는 코드가 강제 삽입 (프롬프트 규칙은 방어선이 아님)
    category = (os.environ.get("POC_CATEGORY") or "").strip()
    if category:
        from src.monetization import add_policy_disclaimers
        title_text = re.sub(r"<[^>]+>", "", p["title"].get("raw") or "")
        cleaned = add_policy_disclaimers(cleaned, category=category, topic=title_text)
        print(f"정책 고지 삽입 (category={category})")
    if cleaned != content:
        payload["content"] = cleaned
    ur = session.post(f"{API}/posts/{POST_ID}", json=payload, timeout=60)
    ur.raise_for_status()
    v = ur.json()
    print(f"발행 완료: {v['link']} (status={v['status']}, date={v['date']})")


if __name__ == "__main__":
    main()
