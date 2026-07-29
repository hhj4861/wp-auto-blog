#!/usr/bin/env python3
"""차전자피 가이드 (trendpulse, 한글, CI 실행) — 블로그용 검색량 상위 키워드.

keyword-intel 블로그용(검색광고 절대검색량) 상위 '차전자피'. 각질필링/알부틴/그릭요거트와
동일 trendpulse 캐논 포맷(그린틸 H2·P/UL/LI·Unsplash 히어로·관련글·광고2슬롯·FAQ·참고자료).
수익화: 올리브영(식이섬유 이너뷰티, rwardCode)만 + 제휴 고지. 쿠팡은 추후 딥링크로.
정직성: 성분·근거·주의(물 충분히·약물간섭) 중심, 브랜드·가격·후기 조작 없음. 멱등.
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

SLUG = "psyllium-husk-fiber-guide-2026"
TITLE = "차전자피, 변비·다이어트에 진짜 효과 있을까 — 식이섬유 완전정리 (2026)"
META_DESC = (
    "차전자피(질경이씨 껍질)가 변비·콜레스테롤·다이어트에 어떻게 작용하는지, 올바른 "
    "복용법과 물·약물 주의사항까지 2026년 기준으로 정리했습니다."
)
FOCUS_KW = "차전자피"
OLIVE = ("https://global.oliveyoung.com/display/search?query="
         + quote("식이섬유") + "&rwardCode=HHJZ4861&utm_source=influencers")
COUPANG = "https://link.coupang.com/a/fMy8G5OEa4"  # lptag=AF4383841

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
    ("Q1. 차전자피가 정확히 뭐예요?",
     "질경이(Plantago) 씨앗의 <strong style=\"color:#6ee7b7\">껍질(psyllium husk)</strong>로, "
     "물에 닿으면 크게 부푸는 <strong style=\"color:#60a5fa\">수용성 식이섬유</strong>입니다. 장에서 "
     "젤처럼 변해 배변·포만감·콜레스테롤 관리에 쓰입니다."),
    ("Q2. 변비에 어떻게 도움이 되나요?",
     "물을 흡수해 <strong style=\"color:#6ee7b7\">변의 부피를 늘리고 부드럽게</strong> 만들어 배변을 "
     "돕습니다. 단 <strong style=\"color:#60a5fa\">물을 충분히</strong> 마시지 않으면 오히려 막힐 수 "
     "있으니 물 섭취가 핵심입니다."),
    ("Q3. 다이어트·콜레스테롤에도 좋나요?",
     "젤화되면서 <strong style=\"color:#6ee7b7\">포만감</strong>을 줘 식사량 조절에 도움을 주고, "
     "수용성 섬유가 <strong style=\"color:#60a5fa\">콜레스테롤·혈당</strong> 관리에 긍정적이라는 근거가 "
     "있습니다. 다만 '살 빠지는 약'이 아니라 식단 보조입니다."),
    ("Q4. 먹을 때 주의할 점은?",
     "① <strong style=\"color:#60a5fa\">반드시 충분한 물</strong>과 함께(가루를 물 없이 삼키면 목·식도 "
     "막힘 위험) ② <strong style=\"color:#60a5fa\">약 복용과 1~2시간 간격</strong>(섬유가 약 흡수를 "
     "방해할 수 있음) ③ 처음엔 소량부터(가스·팽만 적응)."),
]
SOURCES = [
    "(식품의약품안전처) 차전자피·식이섬유 기능성 정보",
    "(질병관리청 국가건강정보포털) 변비·식이섬유 관리 정보",
    "(대한소화기학회) 변비·섬유 섭취 일반 정보",
]

ARTICLE = f"""
{P}변비·다이어트·콜레스테롤 얘기에 자주 등장하는 게 <strong>차전자피</strong>입니다. '식이섬유 덩어리'로 알려졌는데, 실제로 어떻게 작용하고 어떻게 먹어야 하는지, 무엇을 조심해야 하는지를 <strong>근거 중심</strong>으로 정리했습니다.</p>

{H2}차전자피가 뭐고, 왜 먹을까</h2>
{P}차전자피는 <strong>질경이 씨앗의 껍질</strong>로, 물을 만나면 몇 배로 부푸는 <strong>수용성 식이섬유</strong>입니다. 장 속에서 젤처럼 변해 ① 변의 부피를 늘려 <strong>배변</strong>을 돕고 ② <strong>포만감</strong>을 주며 ③ <strong>콜레스테롤·혈당</strong> 관리에 긍정적 역할을 합니다. 핵심은 <em>'물을 머금는 섬유'</em>라는 점입니다.</p>

{H2}어디에 도움이 되나</h2>
{UL}
{LI}<strong>변비</strong> — 변을 부드럽고 크게 만들어 배변을 촉진(단, 물 충분히)</li>
{LI}<strong>다이어트</strong> — 젤화로 포만감 → 식사량 조절 보조(약 아님, 식단 보조)</li>
{LI}<strong>콜레스테롤·혈당</strong> — 수용성 섬유가 흡수를 늦춰 관리에 긍정적</li>
{LI}<strong>장 건강</strong> — 규칙적 배변·장 환경에 도움</li>
</ul>

{H2}올바른 복용법</h2>
{P}순서와 양이 중요합니다. ① 1회 <strong>티스푼 1~2</strong> 정도를 <strong>충분한 물(한 컵 이상)</strong>에 타서 바로 ② 하루 1~2회, 식전이 흔함 ③ 처음엔 <strong>소량부터</strong> 시작해 가스·팽만에 적응 ④ 하루 총 <strong>수분 섭취를 늘리기</strong>. 물이 부족하면 효과는커녕 막힐 수 있습니다.</p>
{P}차전자피·식이섬유 제품(가루·캡슐)은 쿠팡·올리브영에서 비교할 수 있습니다(가격·재고 실시간 확인).</p>
{product_button("차전자피·식이섬유", COUPANG)}
{olive_link("식이섬유 제품")}

{H2}⚠️ 주의사항 — 물과 약물 간격이 핵심</h2>
{P}세 가지는 꼭 지키세요. 첫째, <strong>물 없이 가루를 삼키지 마세요</strong> — 식도·목에서 부풀어 막힘 위험이 있습니다. 둘째, <strong>약 복용과 1~2시간 간격</strong>을 두세요(섬유가 약 흡수를 방해할 수 있음). 셋째, 장 폐색·연하곤란 등 <strong>지병이 있으면 복용 전 상담</strong>하세요.</p>

{H2}결론</h2>
{P}정리하면 ① 차전자피 = 물 머금는 <strong>수용성 식이섬유</strong> ② 변비·포만감·콜레스테롤 보조 ③ <strong>충분한 물 + 약과 간격</strong>이 안전의 핵심. '마법의 다이어트약'이 아니라 <strong>식단·수분과 함께</strong> 쓰는 보조라는 점만 기억하면 됩니다.</p>

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
            params={"query": "fiber supplement seeds healthy", "per_page": 1,
                    "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {key}"}, timeout=20,
        )
        r.raise_for_status()
        photo = r.json()["results"][0]
        alt = photo.get("alt_description") or "fiber supplement"
        credit = photo["user"]["name"]
        img = requests.get(photo["urls"]["regular"], timeout=30)
        img.raise_for_status()
        up = requests.post(
            f"{api}/media", auth=auth,
            headers={"Content-Disposition": 'attachment; filename="psyllium-hero.jpg"',
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
