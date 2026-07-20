#!/usr/bin/env python3
"""최신 draft 포스트를 REST로 가져와 검수용 덤프를 만든다 (POC 검증용).

출력:
  poc_dump/post.json  - 전체 필드 (title/slug/meta/content raw)
  poc_dump/post.html  - 본문 HTML만
  stdout              - 요약 + 품질 게이트 예비 점검 결과
"""

import json
import os
import re
import sys

import requests

BASE_URL = (os.environ.get("WP_GENERAL_URL") or "").rstrip("/")
USERNAME = os.environ.get("WP_GENERAL_USERNAME") or ""
APP_PASSWORD = os.environ.get("WP_GENERAL_APP_PASSWORD") or ""
API = f"{BASE_URL}/wp-json/wp/v2"

session = requests.Session()
session.auth = (USERNAME, APP_PASSWORD)
session.headers.update({"User-Agent": "Mozilla/5.0 (trendpulse-poc-inspect)"})


def main():
    status = os.environ.get("POC_STATUS", "draft")
    r = session.get(f"{API}/posts", params={
        "status": status, "orderby": "date", "order": "desc",
        "per_page": 1, "context": "edit",
    }, timeout=60)
    r.raise_for_status()
    posts = r.json()
    if not posts:
        print(f"{status} 상태 포스트 없음")
        sys.exit(1)
    p = posts[0]

    os.makedirs("poc_dump", exist_ok=True)
    with open("poc_dump/post.json", "w", encoding="utf-8") as f:
        json.dump(p, f, ensure_ascii=False, indent=2)
    content = p["content"].get("raw") or p["content"].get("rendered", "")
    with open("poc_dump/post.html", "w", encoding="utf-8") as f:
        f.write(content)

    title = p["title"].get("raw", "")
    meta = p.get("meta", {}) or {}
    text = re.sub(r"<[^>]+>", " ", content)
    h2s = re.findall(r"<h2[^>]*>(.*?)</h2>", content, re.S)

    cats = []
    if p.get("categories"):
        cr = session.get(f"{API}/categories", params={
            "include": ",".join(map(str, p["categories"]))}, timeout=30)
        if cr.status_code == 200:
            cats = [c["name"] for c in cr.json()]

    print("=" * 60)
    print(f"제목: {title}")
    print(f"슬러그: {p.get('slug')}")
    print(f"상태: {p.get('status')} | 날짜: {p.get('date')}")
    print(f"카테고리: {cats} | 태그 수: {len(p.get('tags', []))}")
    print(f"Yoast 키프레이즈: {meta.get('_yoast_wpseo_focuskw')!r}")
    print(f"Yoast 메타설명: {meta.get('_yoast_wpseo_metadesc')!r}")
    print(f"Yoast 타이틀: {meta.get('_yoast_wpseo_title')!r}")
    print(f"본문 길이: {len(content)} bytes / 텍스트 {len(text)}자")
    print(f"H2 ({len(h2s)}개): {[re.sub('<[^>]+>', '', h)[:40] for h in h2s]}")
    ext_links = len(re.findall(r'href="https?://(?!trendpulse)', content))
    int_links = len(re.findall(r'href="https?://trendpulse', content))
    print(f"이미지 태그: {content.count('<img')}개 | 외부 링크: {ext_links}개 | "
          f"내부 링크: {int_links}개")

    print("-" * 60)
    print("품질 게이트 예비 점검:")
    checks = [
        ("제목에 백틱/따옴표 잔존", bool(re.search(r"[`\"]", title))),
        ("제목에 (N자)/(유형) 잔존", bool(re.search(r"\(\s*(?:유형|\d+\s*자)", title))),
        ("제목에 한글 없음", not re.search(r"[가-힣]", title)),
        ("본문 ((...)) 플레이스홀더", bool(re.search(r"\(\([^()\n]{2,60}\)\)", content))),
        ("본문 <!-- IMAGE 주석", "<!-- IMAGE" in content.upper()),
        ("본문 SEO-META 블록 잔존", "SEO-META" in content),
        ("본문 마크다운 잔존(## / ```)", bool(re.search(r"^##\s|```", content, re.M))),
        ("키프레이즈 비어있음", not (meta.get("_yoast_wpseo_focuskw") or "").strip()),
        ("메타설명 비어있음/길이 이상",
         not (140 <= len(meta.get("_yoast_wpseo_metadesc") or "") <= 170)),
        ("본문에 숫자+단위 붙임 오류 의심(예: 79시간)",
         bool(re.search(r"[0-9]{2,}시간", text))),
    ]
    fails = 0
    for name, bad in checks:
        print(f"  {'❌' if bad else '✅'} {name}")
        fails += bad
    print(f"게이트 결과: {'통과' if fails == 0 else f'{fails}건 걸림'}")


if __name__ == "__main__":
    main()
