#!/usr/bin/env python3
"""알룰로스 가이드 (trendpulse, 한글) — [[스캘폴드: 본문 TODO 채우기]].
검색모듈 블로그용 선정 키워드(월검색량 52,850). 캐논 포맷·올리브영·쿠팡고지·네이버 export 배선 완료.
"""
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.monetization import (  # noqa: E402
    COUPANG_DISCLOSURE, add_coupang_disclosure, check_quality, insert_monetization,
)
from src.post_format import H2_GRADIENT as H2, P, UL, LI, faq_section, sources_section  # noqa: E402
from src.naver_format import save_naver_export  # noqa: E402

SLUG = "allulose-guide-2026"
TITLE = "[[TODO 제목]] — 알룰로스 (2026)"
META_DESC = "[[TODO 메타설명 150자 내외]]"
FOCUS_KW = "알룰로스"
OLIVE = ("https://global.oliveyoung.com/display/search?query="
         + quote("알룰로스") + "&rwardCode=HHJZ4861&utm_source=influencers")
COUPANG = None  # [[TODO 쿠팡 딥링크 있으면 "https://link.coupang.com/a/XXXX"]]

DISCLOSURE = (
    '<div style="background:#2d2d3a;border-left:4px solid #10b981;padding:14px 18px;'
    'margin:0 auto 22px auto;max-width:800px;border-radius:6px;font-size:0.9em;color:#cbd5e1;">'
    '<strong style="color:#6ee7b7;">제휴 안내:</strong> 이 글의 일부 링크는 제휴 링크로, '
    '구매 시 소정의 수수료를 받을 수 있습니다(구매자 추가 부담 없음).</div>'
)


def olive_link(label):
    return (f'<p style="max-width:800px;margin:24px auto;"><a href="{OLIVE}" target="_blank" '
            f'rel="nofollow sponsored" style="display:inline-block;background:#a259c4;color:#fff;'
            f'padding:12px 26px;border-radius:8px;text-decoration:none;font-weight:bold;">'
            f'🫒 {label} 올리브영에서 보기 →</a></p>')


def product_button(label, url):
    return (f'<p style="max-width:800px;margin:24px auto;"><a href="{url}" target="_blank" '
            f'rel="nofollow sponsored" style="display:inline-block;background:#e84c3d;color:#fff;'
            f'padding:12px 26px;border-radius:8px;text-decoration:none;font-weight:bold;">'
            f'🛒 {label} 쿠팡 최저가 보기 →</a></p>')


# [[TODO: 실제 성분 근거로 4개 Q&A 작성 — 지어내지 말 것]]
FAQ = [
    ("Q1. [[TODO]]", "[[TODO 답변]]"),
    ("Q2. [[TODO]]", "[[TODO 답변]]"),
    ("Q3. [[TODO]]", "[[TODO 답변]]"),
    ("Q4. [[TODO]]", "[[TODO 답변]]"),
]
# [[TODO: 공신력 출처만 — (기관) 설명]]
SOURCES = [
    "(식품의약품안전처) [[TODO]]",
    "(질병관리청 국가건강정보포털) [[TODO]]",
    "(대한[[TODO]]학회) [[TODO]]",
]

# [[TODO: 아래 섹션 본문을 성분·근거·주의 중심으로 작성(조작 없음). 기존 발행글(바쿠치올/알부틴) 참고.]]
ARTICLE = f"""
{P}[[TODO 인트로: 알룰로스 가 뭐고 왜 관심인지]]</p>

{H2}[[TODO 소제목 1]]</h2>
{P}[[TODO 본문]]</p>

{H2}[[TODO 소제목 2 — 비교/차이]]</h2>
{P}[[TODO 본문]]</p>

{H2}이런 사람에게 맞다</h2>
{UL}
{LI}[[TODO]]</li>
</ul>

{H2}어떻게 고르나</h2>
{P}[[TODO 고르는 기준]]</p>
{product_button("알룰로스", COUPANG) if COUPANG else ""}
{olive_link("알룰로스")}

{H2}주의사항</h2>
{P}[[TODO 주의]]</p>

{H2}결론</h2>
{P}[[TODO 결론]]</p>

{faq_section(FAQ)}

{sources_section(SOURCES)}
"""


def fetch_hero(api, auth):
    key = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
    if not key:
        return None, ""
    try:
        r = requests.get("https://api.unsplash.com/search/photos",
                         params={"query": "[[TODO unsplash query]] healthy", "per_page": 1,
                                  "orientation": "landscape"},
                         headers={"Authorization": f"Client-ID {key}"}, timeout=20)
        r.raise_for_status()
        photo = r.json()["results"][0]
        img = requests.get(photo["urls"]["regular"], timeout=30); img.raise_for_status()
        up = requests.post(f"{api}/media", auth=auth,
                           headers={"Content-Disposition": 'attachment; filename="allulose-guide-2026.jpg"',
                                     "Content-Type": "image/jpeg"}, data=img.content, timeout=60)
        up.raise_for_status(); media = up.json()
        requests.post(f"{api}/media/{media['id']}", auth=auth,
                      json={"alt_text": photo.get("alt_description") or "알룰로스"}, timeout=20)
        fig = ('<figure class="wp-block-image aligncenter size-large hero-image" '
               'style="max-width:800px;margin:0 auto 30px auto;">'
               f'<img src="{media.get("source_url","")}" alt="알룰로스" '
               'style="width:100%;max-width:800px;height:auto;border-radius:12px;"/>'
               f'<figcaption style="text-align:center;font-size:0.85em;color:#888;margin-top:10px;">'
               f'Photo by {photo["user"]["name"]}</figcaption></figure>\n')
        return media["id"], fig
    except Exception as e:
        print(f"히어로 실패(생략): {e}"); return None, ""


def main():
    base = os.environ["WP_GENERAL_URL"].rstrip("/")
    auth = (os.environ["WP_GENERAL_USERNAME"], os.environ["WP_GENERAL_APP_PASSWORD"])
    api = f"{base}/wp-json/wp/v2"
    if "[[TODO" in ARTICLE or "[[TODO" in TITLE:
        print("스캘폴드 미완성([[TODO]] 잔존) — 본문 채운 뒤 발행하세요."); return 1
    media_id, hero = fetch_hero(api, auth)
    html = insert_monetization(ARTICLE.strip(), related_posts=[])
    if COUPANG:
        html = add_coupang_disclosure(html); assert COUPANG_DISCLOSURE in html
    html = f'<div class="post-content category-건강" data-category="건강">\n{hero}{DISCLOSURE}\n{html}\n</div>'
    issues = check_quality(title=TITLE, html=html, focus_keyphrase=FOCUS_KW,
                           meta_description=META_DESC, require_korean=True)
    if issues:
        print(f"품질 게이트 실패: {issues}"); return 1
    cat = requests.get(f"{api}/categories", auth=auth,
                       params={"search": "건강", "_fields": "id,name"}, timeout=30).json()
    cat_ids = [c["id"] for c in cat if c["name"] == "건강"][:1]
    body = {"title": TITLE, "slug": SLUG, "content": html, "excerpt": META_DESC,
            "status": "publish", "categories": cat_ids,
            "meta": {"_yoast_wpseo_metadesc": META_DESC, "_yoast_wpseo_focuskw": FOCUS_KW,
                     "_yoast_wpseo_title": f"{TITLE} | TrendPulse"}}
    if media_id:
        body["featured_media"] = media_id
    dup = requests.get(f"{api}/posts", auth=auth,
                       params={"slug": SLUG, "status": "publish,draft", "_fields": "id"}, timeout=30).json()
    if dup:
        r = requests.post(f"{api}/posts/{dup[0]['id']}", auth=auth, json=body, timeout=60)
    else:
        r = requests.post(f"{api}/posts", auth=auth, json=body, timeout=60)
    r.raise_for_status(); print(f"발행 완료: {r.json()['link']}")
    save_naver_export(SLUG, TITLE, ARTICLE, coupang_url=COUPANG)
    return 0


if __name__ == "__main__":
    sys.exit(main())
