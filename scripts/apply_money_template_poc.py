#!/usr/bin/env python3
"""POC: 재산세 draft(post 1411)에 수익화 템플릿 레이어를 적용한다.

적용 항목:
  - 인아티클 광고 유닛 2개: 도입부 직후(AD1) + 본문 중반(AD2)
    * 정책 안전: CTA 버튼과 섹션 단위(수백 px)로 이격, 상단에 '광고' 라벨 명시
  - 공식 사이트 CTA 버튼 2개 (위택스 조회/납부) — 광고와 시각적으로 명확히 구분
  - 관련 글 내부 링크 박스 (결론 앞)
  - 참고 자료의 회색 텍스트 출처 → 공식 사이트 실링크
  - <!-- IMAGE --> 주석 제거, 슬러그 영문 교체, 카테고리 '생활정보' 생성/배정

draft 상태는 유지한다 (발행하지 않음).
"""

import os
import re
import sys

import requests

BASE_URL = (os.environ.get("WP_GENERAL_URL") or "").rstrip("/")
USERNAME = os.environ.get("WP_GENERAL_USERNAME") or ""
APP_PASSWORD = os.environ.get("WP_GENERAL_APP_PASSWORD") or ""
API = f"{BASE_URL}/wp-json/wp/v2"

POST_ID = int(os.environ.get("POC_POST_ID", "1411"))
AD_CLIENT = "ca-pub-7509086152335830"
AD_SLOTS = ["3599000043", "7637749188"]
NEW_SLUG = "property-tax-july-2026-wetax"
NEW_CATEGORY = {"name": "생활정보", "slug": "life-info"}

session = requests.Session()
session.auth = (USERNAME, APP_PASSWORD)
session.headers.update({"User-Agent": "Mozilla/5.0 (trendpulse-poc-apply)"})


def ad_unit(slot):
    return f'''
<div style="max-width:800px;margin:35px auto;">
<p style="text-align:center;color:#94a3b8;font-size:0.75em;letter-spacing:2px;margin:0 0 4px 0;">광고</p>
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={AD_CLIENT}" crossorigin="anonymous"></script>
<ins class="adsbygoogle" style="display:block; text-align:center;" data-ad-layout="in-article" data-ad-format="fluid" data-ad-client="{AD_CLIENT}" data-ad-slot="{slot}"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
</div>
'''


def cta_button(label, url, sub):
    return f'''
<div style="max-width:800px;margin:45px auto;text-align:center;">
<a href="{url}" target="_blank" rel="noopener" style="display:inline-block;background:#0066cc;color:#ffffff;font-size:1.15em;font-weight:bold;padding:18px 42px;border-radius:12px;text-decoration:none;box-shadow:0 4px 15px rgba(0,102,204,0.4);">{label}</a>
<p style="color:#94a3b8;font-size:0.8em;margin-top:8px;">{sub}</p>
</div>
'''


def related_box(posts):
    items = "".join(
        f'<li style="margin-bottom:10px;"><a href="{p["link"]}" '
        f'style="color:#67e8f9;text-decoration:none;">{p["title"]}</a></li>'
        for p in posts)
    return f'''
<div style="max-width:800px;margin:35px auto;padding:20px;background:#2d2d3a;border-radius:12px;border-left:4px solid #5046e5;">
<p style="margin:0 0 12px 0;font-size:1.05em;font-weight:bold;color:#ffffff;">📌 함께 보면 좋은 글</p>
<ul style="margin:0;padding-left:18px;color:#e0e0e0;line-height:1.6;">{items}</ul>
</div>
'''


SOURCE_LINKS = [
    (r'<span style="color: #94a3b8; font-size: 0.85em;">\(위택스\(WeTax\)\)</span>',
     '<a href="https://www.wetax.go.kr" target="_blank" rel="noopener" style="color:#67e8f9;">위택스(WeTax)</a>'),
    (r'<span style="color: #94a3b8; font-size: 0.85em;">\(서울시 이택스\)</span>',
     '<a href="https://etax.seoul.go.kr" target="_blank" rel="noopener" style="color:#67e8f9;">서울시 이택스</a>'),
    (r'<span style="color: #94a3b8; font-size: 0.85em;">\(행정안전부\)</span>',
     '<a href="https://www.mois.go.kr" target="_blank" rel="noopener" style="color:#67e8f9;">행정안전부</a>'),
    (r'<span style="color: #94a3b8; font-size: 0.85em;">\(카드고릴라\)</span>',
     '<a href="https://www.card-gorilla.com" target="_blank" rel="noopener" style="color:#67e8f9;">카드고릴라</a>'),
]


def ensure_category():
    r = session.get(f"{API}/categories", params={"slug": NEW_CATEGORY["slug"]}, timeout=30)
    if r.status_code == 200 and r.json():
        return r.json()[0]["id"]
    r = session.post(f"{API}/categories", json=NEW_CATEGORY, timeout=30)
    if r.status_code == 201:
        return r.json()["id"]
    print(f"⚠️ 카테고리 생성 실패({r.status_code}): {r.text[:150]}")
    return None


def recent_posts(exclude_id, n=3):
    r = session.get(f"{API}/posts", params={
        "status": "publish", "per_page": n + 1, "orderby": "date", "order": "desc",
        "_fields": "id,link,title"}, timeout=30)
    r.raise_for_status()
    out = []
    for p in r.json():
        if p["id"] == exclude_id:
            continue
        out.append({"link": p["link"],
                    "title": re.sub(r"<[^>]+>", "", p["title"]["rendered"])})
    return out[:n]


def main():
    r = session.get(f"{API}/posts/{POST_ID}", params={"context": "edit"}, timeout=60)
    r.raise_for_status()
    post = r.json()
    content = post["content"]["raw"]
    print(f"대상: #{POST_ID} {post['title']['raw']!r} (status={post['status']})")

    # 1) IMAGE 주석 제거
    content = re.sub(r"<!--\s*IMAGE:[^>]*-->\n?", "", content)

    # 2) 출처 텍스트 → 실링크 (참고 자료 박스 내)
    for pat, repl in SOURCE_LINKS:
        content = re.sub(pat, repl, content, count=1)

    # 3) H2 앵커 기준 삽입
    h2s = [m.start() for m in re.finditer(r"<h2[\s>]", content)]
    if len(h2s) < 5:
        sys.exit(f"H2가 {len(h2s)}개뿐 — 앵커 부족, 중단")
    inserts = [
        (h2s[0], ad_unit(AD_SLOTS[0])),                                   # 도입부 직후
        (h2s[2], cta_button("🏛️ 위택스에서 재산세 조회·납부 바로가기",
                            "https://www.wetax.go.kr/",
                            "행정안전부 공식 지방세 납부 사이트로 이동합니다")),  # 조회 섹션 끝
        (h2s[3], ad_unit(AD_SLOTS[1])),                                   # 한 섹션 건너 중반부
        (h2s[-1], related_box(recent_posts(POST_ID))),                    # 결론 앞
    ]
    for pos, html in sorted(inserts, key=lambda x: -x[0]):
        content = content[:pos] + html + content[pos:]

    # 4) 말미 CTA (마지막 문단 뒤, 광고와 충분히 이격)
    end_cta = cta_button("✅ 지금 위택스에서 내 재산세 확인하기",
                         "https://www.wetax.go.kr/",
                         "납부 기한: 2026년 7월 31일까지")
    content = re.sub(r"</div>\s*$", end_cta + "</div>", content)

    # 5) 카테고리/슬러그
    cat_id = ensure_category()
    payload = {"content": content, "slug": NEW_SLUG}
    if cat_id:
        payload["categories"] = [cat_id]
    ur = session.post(f"{API}/posts/{POST_ID}", json=payload, timeout=60)
    ur.raise_for_status()
    print("업데이트 완료")

    # 6) 검증: 재조회 후 삽입 요소 카운트
    vr = session.get(f"{API}/posts/{POST_ID}", params={"context": "edit"}, timeout=60)
    vr.raise_for_status()
    v = vr.json()
    c = v["content"]["raw"]
    ins_count = c.count('<ins class="adsbygoogle"')
    push_count = c.count("adsbygoogle || []).push")
    wetax_count = c.count("wetax.go.kr")
    img_comments = c.upper().count("<!-- IMAGE")
    src_links = (c.count("card-gorilla.com") + c.count("etax.seoul.go.kr")
                 + c.count("mois.go.kr"))
    related = "있음" if "함께 보면 좋은 글" in c else "없음"
    print("-" * 50)
    print(f"슬러그: {v['slug']}")
    print(f"카테고리 ID: {v.get('categories')}")
    print(f"광고 <ins> 유닛: {ins_count}개 | push(): {push_count}개")
    print(f"CTA 버튼(wetax 링크): {wetax_count}개")
    print(f"관련 글 박스: {related}")
    print(f"IMAGE 주석 잔존: {img_comments}개")
    print(f"출처 실링크(카드고릴라/이택스/행안부): {src_links}개")
    print(f"상태: {v['status']} (draft 유지) → 미리보기: {BASE_URL}/?p={POST_ID}&preview=true")


if __name__ == "__main__":
    main()
