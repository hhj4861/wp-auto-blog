#!/usr/bin/env python3
"""그릭요거트 가이드 (trendpulse, 한글, CI 실행) — 블로그용 검색량 상위 키워드.

keyword-intel 블로그용(검색광고 절대검색량) 상위 '그릭요거트'. 각질필링/알부틴과 동일
trendpulse 캐논 포맷(그린틸 H2·P/UL/LI·Unsplash 히어로·관련글·광고2슬롯·FAQ·참고자료).
수익화: 올리브영(장건강 이너뷰티 라인, rwardCode)만 + 제휴 고지. 쿠팡은 추후 딥링크로.
정직성: 성분·영양·주의 중심, 브랜드·가격·후기 조작 없음. 멱등.
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

SLUG = "greek-yogurt-guide-2026"
TITLE = "그릭요거트, 일반 요거트랑 뭐가 다를까 — 단백질·다이어트 완전정리 (2026)"
META_DESC = (
    "그릭요거트가 일반 요거트와 뭐가 다른지, 단백질·장 건강에 왜 좋은지, 고를 때 뭘 "
    "봐야 하는지(당류·단백질)까지 2026년 기준으로 정리했습니다."
)
FOCUS_KW = "그릭요거트"
# 그릭요거트 자체는 식품이라, 올리브영은 인접한 장건강 이너뷰티(유산균/프로바이오틱스)로 연결.
OLIVE = ("https://global.oliveyoung.com/display/search?query="
         + quote("프로바이오틱스") + "&rwardCode=HHJZ4861&utm_source=influencers")
COUPANG = "https://link.coupang.com/a/fMy5FilCqO"  # lptag=AF4383841

DISCLOSURE = (
    '<div style="background:#2d2d3a;border-left:4px solid #10b981;padding:14px 18px;'
    'margin:0 auto 22px auto;max-width:800px;border-radius:6px;font-size:0.9em;color:#cbd5e1;">'
    '<strong style="color:#6ee7b7;">제휴 안내:</strong> 이 글의 일부 링크는 제휴 링크로, '
    '구매 시 소정의 수수료를 받을 수 있습니다(구매자 추가 부담 없음).</div>'
)


def product_button(label: str, url: str) -> str:
    return (
        f'<p style="max-width:800px;margin:24px auto;"><a href="{url}" target="_blank" '
        f'rel="nofollow sponsored" style="display:inline-block;background:#e84c3d;'
        f'color:#fff;padding:12px 26px;border-radius:8px;text-decoration:none;'
        f'font-weight:bold;">🛒 {label} 쿠팡 최저가 보기 →</a></p>'
    )


def olive_link(label: str) -> str:
    return (
        f'<p style="max-width:800px;margin:24px auto;"><a href="{OLIVE}" target="_blank" '
        f'rel="nofollow sponsored" style="display:inline-block;background:#a259c4;'
        f'color:#fff;padding:12px 26px;border-radius:8px;text-decoration:none;'
        f'font-weight:bold;">🫒 {label} 올리브영에서 보기 →</a></p>'
    )


FAQ = [
    ("Q1. 그릭요거트랑 일반 요거트, 뭐가 달라요?",
     "그릭요거트는 일반 요거트에서 <strong style=\"color:#6ee7b7\">유청(수분)을 걸러낸</strong> 것입니다. "
     "그만큼 농축돼서 <strong style=\"color:#60a5fa\">단백질이 약 2배</strong>, 식감은 꾸덕하고, 유당은 "
     "상대적으로 적은 편입니다. 대신 같은 양이면 열량은 더 높을 수 있어요."),
    ("Q2. 다이어트에 정말 도움이 되나요?",
     "단백질이 많아 <strong style=\"color:#6ee7b7\">포만감</strong>이 오래가고 근육 유지에 유리해 "
     "체중 관리 식단에 자주 쓰입니다. 단, <strong style=\"color:#60a5fa\">가당(설탕 첨가) 제품</strong>은 "
     "당류가 높으니 무가당을 고르고 과일·꿀은 직접 소량 추가하는 게 낫습니다."),
    ("Q3. 장 건강에도 좋나요?",
     "발효 유제품이라 <strong style=\"color:#6ee7b7\">유산균(프로바이오틱스)</strong>이 들어 장 환경에 "
     "도움을 줄 수 있습니다. 다만 제품마다 균종·함량이 다르고 살균 과정에서 균이 줄 수도 있어, "
     "장 건강이 주목적이면 별도 <strong style=\"color:#60a5fa\">유산균 보충</strong>과 병행이 확실합니다."),
    ("Q4. 유당불내증인데 먹어도 되나요?",
     "그릭요거트는 유청을 거르며 <strong style=\"color:#60a5fa\">유당이 다소 줄어</strong> 일반 우유보다 "
     "부담이 덜한 경우가 많습니다. 하지만 개인차가 크니 소량부터 시도하고, 불편하면 락토프리 제품을 "
     "고려하세요."),
]
SOURCES = [
    "(식품의약품안전처) 발효유·유산균(프로바이오틱스) 기준·정보",
    "(질병관리청 국가건강정보포털) 단백질·식이 일반 정보",
    "(대한영양사협회) 유제품·식단 일반 정보",
]

ARTICLE = f"""
{P}헬스·다이어트 식단에 빠지지 않는 게 <strong>그릭요거트</strong>입니다. '단백질 많고 장에 좋다'는데, 일반 요거트와 정확히 뭐가 다른지, 고를 때 뭘 봐야 하는지 헷갈리죠. 이 글에서는 그릭요거트의 <strong>영양·차이·고르는 법</strong>을 근거 중심으로 정리했습니다.</p>

{H2}그릭요거트가 뭐고, 일반 요거트와 뭐가 다를까</h2>
{P}그릭요거트는 일반 요거트에서 <strong>유청(액체 수분)을 걸러낸</strong> 농축 요거트입니다. 물이 빠지면서 같은 양 대비 <strong>단백질이 약 2배</strong>로 진해지고, 식감은 꾸덕해집니다. 핵심은 하나 — <em>더 진한 단백질 + 낮아진 유당</em>. 대신 농축된 만큼 지방·열량은 제품에 따라 높을 수 있으니 성분표를 봐야 합니다.</p>

{H2}왜 다이어트·헬스 식단에 쓸까</h2>
{UL}
{LI}<strong>고단백·포만감</strong> — 단백질이 많아 오래 든든하고, 근육 유지에 유리(체중 관리 식단의 단골)</li>
{LI}<strong>낮은 유당</strong> — 유청을 걸러 유당이 다소 줄어 일반 우유보다 부담이 덜한 편</li>
{LI}<strong>발효 유산균</strong> — 프로바이오틱스로 장 환경에 도움 가능(제품별 균종·함량 차이 있음)</li>
{LI}<strong>활용도</strong> — 그대로, 과일·그래놀라, 소스·드레싱 대체 등 활용 폭이 넓음</li>
</ul>

{H2}고를 때 이것만은 확인하자</h2>
{P}세 가지만 보면 됩니다.</p>
{UL}
{LI}<strong>당류</strong> — '가당' 제품은 설탕이 많습니다. <strong>무가당</strong>을 고르고 단맛은 과일·꿀로 직접 소량 추가</li>
{LI}<strong>단백질 함량</strong> — 100g당 단백질 g수를 비교(진짜 그릭인지 가늠). 보통 8~10g 이상</li>
{LI}<strong>원재료</strong> — 우유·유산균 위주로 단순한 것. 증점제·향료가 적을수록 담백</li>
</ul>
<table style="max-width:800px;width:100%;margin:20px auto;border-collapse:collapse;color:#cbd5e1;">
<tr style="background:#2d2d3a;color:#fff;"><th style="padding:10px;">구분</th><th style="padding:10px;">일반 요거트</th><th style="padding:10px;">그릭요거트</th></tr>
<tr><td style="padding:10px;">단백질</td><td style="padding:10px;">보통</td><td style="padding:10px;">약 2배 농축</td></tr>
<tr><td style="padding:10px;">식감</td><td style="padding:10px;">묽음</td><td style="padding:10px;">꾸덕</td></tr>
<tr><td style="padding:10px;">유당</td><td style="padding:10px;">보통</td><td style="padding:10px;">다소 적음</td></tr>
</table>

{H2}장 건강까지 챙기려면</h2>
{P}그릭요거트도 유산균이 있지만 제품·공정에 따라 균이 줄 수 있습니다. <strong>장 건강이 주목적</strong>이라면 그릭요거트에 더해 <strong>유산균(프로바이오틱스) 보충</strong>을 병행하는 게 확실합니다. 쿠팡·올리브영에서 그릭요거트·유산균 제품을 비교할 수 있습니다(가격·재고 실시간 확인).</p>
{product_button("그릭요거트·유산균", COUPANG)}
{olive_link("유산균·프로바이오틱스")}

{H2}주의사항</h2>
{P}두 가지만. 첫째, <strong>'가당' 제품의 당류</strong>를 조심하세요 — 건강식처럼 보여도 설탕이 많으면 다이어트에 역효과입니다. 둘째, <strong>유당불내증</strong>이 심하면 개인차가 크니 소량부터, 불편하면 락토프리를 고려하세요.</p>

{H2}결론</h2>
{P}정리하면 ① 그릭요거트 = 유청 걸러 <strong>단백질 농축·유당 감소</strong> ② 무가당·고단백·단순원재료로 고르기 ③ 장 건강엔 유산균 병행. 식단의 든든한 단백질 축으로 삼되, <strong>당류만 조심</strong>하면 실패가 적습니다.</p>

{faq_section(FAQ)}

{sources_section(SOURCES)}
"""


def fetch_hero(api: str, auth: tuple) -> tuple:
    key = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
    if not key:
        print("UNSPLASH 키 없음 — 히어로 생략")
        return None, ""
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": "greek yogurt bowl healthy", "per_page": 1,
                    "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {key}"}, timeout=20,
        )
        r.raise_for_status()
        photo = r.json()["results"][0]
        alt = photo.get("alt_description") or "greek yogurt bowl"
        credit = photo["user"]["name"]
        img = requests.get(photo["urls"]["regular"], timeout=30)
        img.raise_for_status()
        up = requests.post(
            f"{api}/media", auth=auth,
            headers={"Content-Disposition": 'attachment; filename="greek-yogurt-hero.jpg"',
                     "Content-Type": "image/jpeg"},
            data=img.content, timeout=60)
        up.raise_for_status()
        media = up.json()
        requests.post(f"{api}/media/{media['id']}", auth=auth,
                      json={"alt_text": alt}, timeout=20)
        figure = (
            '<figure class="wp-block-image aligncenter size-large hero-image" '
            'style="max-width:800px;margin:0 auto 30px auto;">'
            f'<img src="{media.get("source_url","")}" alt="{alt}" '
            'style="width:100%;max-width:800px;height:auto;border-radius:12px;"/>'
            '<figcaption style="text-align:center;font-size:0.85em;color:#888;'
            f'margin-top:10px;">Photo by {credit}</figcaption></figure>\n'
        )
        print(f"히어로 업로드: media #{media['id']}")
        return media["id"], figure
    except Exception as e:
        print(f"히어로 실패(생략하고 진행): {e}")
        return None, ""


def fetch_related(api: str, auth: tuple) -> list:
    try:
        r = requests.get(
            f"{api}/posts", auth=auth,
            params={"per_page": 15, "status": "publish", "_fields": "title,link,slug"},
            timeout=30,
        )
        r.raise_for_status()
        out = []
        for p in r.json():
            title = re.sub(r"<[^>]+>", "", p["title"]["rendered"]).strip()
            if p.get("slug") == SLUG or not re.search(r"[가-힣]", title):
                continue
            out.append({"title": title, "url": p["link"]})
            if len(out) >= 3:
                break
        return out
    except Exception as e:
        print(f"관련글 조회 실패(생략): {e}")
        return []


def resolve_category(api: str, auth: tuple) -> list:
    try:
        for name in ("건강", "다이어트", "뷰티"):
            cats = requests.get(
                f"{api}/categories", auth=auth,
                params={"search": name, "_fields": "id,name"}, timeout=30,
            ).json()
            ids = [c["id"] for c in cats if c["name"] == name][:1]
            if ids:
                print(f"카테고리: {name} (#{ids[0]})")
                return ids
    except Exception as e:
        print(f"카테고리 조회 실패(미분류로 진행): {e}")
        return []
    return []


def main() -> int:
    base = os.environ["WP_GENERAL_URL"].rstrip("/")
    auth = (os.environ["WP_GENERAL_USERNAME"], os.environ["WP_GENERAL_APP_PASSWORD"])
    api = f"{base}/wp-json/wp/v2"

    media_id, hero = fetch_hero(api, auth)
    related = fetch_related(api, auth)

    html = insert_monetization(ARTICLE.strip(), related_posts=related)
    html = add_coupang_disclosure(html)
    assert COUPANG_DISCLOSURE in html, "쿠팡 고지문 누락"
    html = (f'<div class="post-content category-건강" data-category="건강">\n'
            f'{hero}{DISCLOSURE}\n{html}\n</div>')

    issues = check_quality(
        title=TITLE, html=html, focus_keyphrase=FOCUS_KW,
        meta_description=META_DESC, require_korean=True,
    )
    if issues:
        print(f"품질 게이트 실패: {issues}")
        return 1
    print("품질 게이트 통과")

    cat_ids = resolve_category(api, auth)
    body = {
        "title": TITLE, "slug": SLUG, "content": html, "excerpt": META_DESC,
        "status": "publish", "categories": cat_ids,
        "meta": {"_yoast_wpseo_metadesc": META_DESC,
                 "_yoast_wpseo_focuskw": FOCUS_KW,
                 "_yoast_wpseo_title": f"{TITLE} | TrendPulse"},
    }
    if media_id:
        body["featured_media"] = media_id

    dup = requests.get(
        f"{api}/posts", auth=auth,
        params={"slug": SLUG, "status": "publish,draft", "_fields": "id"}, timeout=30,
    ).json()
    if dup:
        r = requests.post(f"{api}/posts/{dup[0]['id']}", auth=auth, json=body, timeout=60)
        r.raise_for_status()
        print(f"재포맷 업데이트 완료: {r.json()['link']}")
    else:
        r = requests.post(f"{api}/posts", auth=auth, json=body, timeout=60)
        r.raise_for_status()
        print(f"발행 완료: {r.json()['link']}")
    # 발행 시점 네이버 블로그용 로컬 저장(반자동 — 네이버는 공식 발행 API 없음)
    save_naver_export(SLUG, TITLE, ARTICLE, coupang_url=COUPANG)
    return 0


if __name__ == "__main__":
    sys.exit(main())
