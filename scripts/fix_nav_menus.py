#!/usr/bin/env python3
"""내비게이션 정리:
  1. 헤더 메뉴에서 소개/개인정보처리방침/문의 페이지 항목 제거
  2. 헤더 메뉴에 '생활정보' 카테고리 추가
  3. 푸터(메뉴 위치 또는 위젯 영역)에 페이지 3종 링크 배치 — 가능한 수단 순서대로 시도
"""

import os

import requests

BASE_URL = (os.environ.get("WP_GENERAL_URL") or "").rstrip("/")
API = f"{BASE_URL}/wp-json/wp/v2"
PAGE_SLUGS = ["about", "privacy-policy", "contact"]
CATEGORY_SLUG = "life-info"

session = requests.Session()
session.auth = (os.environ.get("WP_GENERAL_USERNAME", ""),
                os.environ.get("WP_GENERAL_APP_PASSWORD", ""))
session.headers.update({"User-Agent": "Mozilla/5.0 (trendpulse-nav-fix)"})


def get(path, **params):
    r = session.get(f"{API}{path}", params=params, timeout=40)
    return r.json() if r.status_code == 200 else None


def main():
    # 인벤토리 출력
    menus = get("/menus") or []
    locations = get("/menu-locations") or {}
    sidebars = get("/sidebars") or []
    print("메뉴:", [(m["id"], m.get("name"), m.get("locations")) for m in menus])
    print("메뉴 위치:", {k: v.get("menu") for k, v in locations.items()})
    print("위젯 영역:", [s.get("id") for s in sidebars])

    page_ids = {}
    for slug in PAGE_SLUGS:
        pages = get("/pages", slug=slug) or []
        if pages:
            page_ids[slug] = pages[0]["id"]
    print("페이지 ID:", page_ids)

    cats = get("/categories", slug=CATEGORY_SLUG) or []
    cat_id = cats[0]["id"] if cats else None
    print("생활정보 카테고리 ID:", cat_id)

    # 1) 헤더 메뉴에서 페이지 항목 제거 + 생활정보 추가
    #    (헤더 메뉴 = 테마 위치에 연결된 메뉴, 없으면 첫 메뉴)
    assigned = [v.get("menu") for v in locations.values() if v.get("menu")]
    header_menu = next((m for m in menus if m["id"] in assigned), menus[0] if menus else None)
    if header_menu:
        print(f"헤더 메뉴: #{header_menu['id']} {header_menu.get('name')!r}")
        items = get("/menu-items", menus=header_menu["id"], per_page=100) or []
        removed = 0
        has_life_info = False
        for it in items:
            if it.get("object") == "page" and it.get("object_id") in page_ids.values():
                r = session.delete(f"{API}/menu-items/{it['id']}",
                                   params={"force": "true"}, timeout=40)
                print(f"  - 메뉴 항목 제거 #{it['id']} ({it['title']['rendered']}): {r.status_code}")
                removed += 1
            if it.get("object") == "category" and it.get("object_id") == cat_id:
                has_life_info = True
        if cat_id and not has_life_info:
            r = session.post(f"{API}/menu-items", json={
                "title": "생활정보", "menus": header_menu["id"], "type": "taxonomy",
                "object": "category", "object_id": cat_id, "status": "publish",
            }, timeout=40)
            print(f"  + 생활정보 카테고리 메뉴 추가: {r.status_code}")
        print(f"헤더 정리 완료 (페이지 항목 {removed}건 제거)")

    # 2) 푸터 배치
    footer_loc = next((k for k in locations if "footer" in k.lower()), None)
    footer_sidebar = next((s for s in sidebars
                           if "footer" in s.get("id", "").lower()
                           or "footer" in (s.get("name") or "").lower()), None)
    links_html = ('<p style="text-align:center;font-size:0.9em;">'
                  '<a href="/about/">소개</a> &nbsp;·&nbsp; '
                  '<a href="/privacy-policy/">개인정보처리방침</a> &nbsp;·&nbsp; '
                  '<a href="/contact/">문의</a></p>')

    if footer_loc:
        footer_menus = [m for m in menus if (m.get("name") or "").lower() == "footer"]
        if footer_menus:
            fm_id = footer_menus[0]["id"]
        else:
            r = session.post(f"{API}/menus", json={
                "name": "Footer", "locations": [footer_loc]}, timeout=40)
            if r.status_code != 201:
                print(f"⚠️ 푸터 메뉴 생성 실패({r.status_code}): {r.text[:150]}")
                return
            fm_id = r.json()["id"]
        existing = get("/menu-items", menus=fm_id, per_page=100) or []
        existing_pages = {i.get("object_id") for i in existing if i.get("object") == "page"}
        titles = {"about": "소개", "privacy-policy": "개인정보처리방침", "contact": "문의"}
        for slug, pid in page_ids.items():
            if pid in existing_pages:
                continue
            r = session.post(f"{API}/menu-items", json={
                "title": titles[slug], "menus": fm_id, "type": "post_type",
                "object": "page", "object_id": pid, "status": "publish",
            }, timeout=40)
            print(f"  + 푸터 메뉴에 {titles[slug]} 추가: {r.status_code}")
        # 위치 연결 보장
        session.post(f"{API}/menus/{fm_id}", json={"locations": [footer_loc]}, timeout=40)
        print(f"푸터 메뉴 위치({footer_loc}) 연결 완료")
    elif footer_sidebar:
        widgets = get("/widgets", sidebar=footer_sidebar["id"]) or []
        if any("privacy-policy" in (w.get("rendered") or "") for w in widgets):
            print("푸터 위젯에 링크 이미 존재")
        else:
            r = session.post(f"{API}/widgets", json={
                "id_base": "custom_html", "sidebar": footer_sidebar["id"],
                "instance": {"raw": {"title": "", "content": links_html}},
            }, timeout=40)
            print(f"푸터 위젯 추가: {r.status_code}")
    else:
        print("⚠️ 푸터 메뉴 위치/위젯 영역이 테마에 없음 — 소개·개인정보처리방침·문의 링크는")
        print("   각 페이지 상호 링크와 sitemap으로 접근 가능. 테마 푸터 노출은 관리자에서")
        print("   외모 > 테마 파일 편집(footer.php) 또는 테마 변경 시 처리 필요.")


if __name__ == "__main__":
    main()
