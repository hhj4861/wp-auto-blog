#!/usr/bin/env python3
"""바쿠치올 세럼 리뷰글 (trendpulse, 한글, CI 실행).

검색 1위 키워드 '바쿠치올 세럼' 대응. 기존 trendpulse 캐논 포맷(create_coupang_post
계열) 완전 일치: post-content 래퍼·그린틸 H2·P/UL/LI·Unsplash 히어로·관련글·광고 2슬롯
·FAQ·참고자료·쿠팡 고지문. 링크: 쿠팡 2개(사용자 딥링크) + 올리브영(rwardCode).
정직성: 성분·근거·주의 중심, 브랜드·가격·사용후기 조작 없음. 멱등(동일 슬러그 업데이트).
"""

import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.monetization import (  # noqa: E402
    COUPANG_DISCLOSURE,
    add_coupang_disclosure,
    check_quality,
    insert_monetization,
)
from src.post_format import H2_GRADIENT as H2, P, UL, LI, faq_section, sources_section  # noqa: E402

SLUG = "bakuchiol-serum-guide-2026"
TITLE = "바쿠치올 세럼, 왜 지금 1위일까 — 레티놀 대안 완전정리 (2026)"
META_DESC = (
    "레티놀은 부담스럽고 바쿠치올은 궁금한 분들을 위해, 성분 근거·레티놀과의 차이·"
    "고르는 법·주의사항까지 2026년 기준으로 정리했습니다."
)
FOCUS_KW = "바쿠치올 세럼"

COUPANG_1 = "https://link.coupang.com/a/fJPtkanv6i"
COUPANG_2 = "https://link.coupang.com/a/fJPvwREDOD"
# 올리브영: rwardCode가 아무 URL에 붙어도 30일 쿠키 심어짐(실측). 바쿠치올 검색 진입.
OLIVE = (
    "https://global.oliveyoung.com/display/search?query="
    + quote("바쿠치올") + "&rwardCode=HHJZ4861&utm_source=influencers"
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
    ("Q1. 바쿠치올이랑 레티놀, 뭐가 달라요?",
     "레티놀은 검증이 두터운 대신 <strong style=\"color:#6ee7b7\">자극·홍조·각질</strong>이 잦습니다. "
     "바쿠치올은 식물 유래 성분으로, 한 연구(2019)에서 레티놀과 <strong style=\"color:#60a5fa\">유사한 주름·색소 개선</strong>을 "
     "보이면서 자극은 더 적었다는 보고가 있습니다. 즉 '순한 레티놀 대안' 포지션입니다."),
    ("Q2. 임신·수유 중에도 써도 되나요?",
     "레티놀(레티노이드)은 임신 중 권장되지 않아 그 대안으로 바쿠치올이 자주 언급되지만, "
     "<strong style=\"color:#60a5fa\">모든 성분이 개인 상황에 안전한 건 아니므로</strong> 임신·수유 중에는 반드시 "
     "산부인과·피부과와 상담 후 사용하세요."),
    ("Q3. 언제, 어떻게 발라요?",
     "세안 → 토너 → <strong style=\"color:#6ee7b7\">바쿠치올 세럼</strong> → 크림 순서로, 아침·저녁 모두 사용 가능합니다. "
     "레티놀과 달리 광분해 걱정이 적지만, 낮에는 <strong style=\"color:#60a5fa\">자외선 차단제</strong>를 꼭 함께 쓰세요."),
    ("Q4. 효과는 얼마나 걸려요?",
     "피부 턴오버 주기상 보통 <strong style=\"color:#60a5fa\">4~8주 이상 꾸준히</strong> 써야 결이·톤 변화가 체감됩니다. "
     "처음엔 저농도로 시작해 피부 반응을 보며 늘리는 게 안전합니다."),
]
SOURCES = [
    "(식품의약품안전처) 화장품 성분·기능성화장품 정보",
    "(대한피부과학회) 피부 노화·레티노이드 일반 정보",
    "(British Journal of Dermatology, 2019) 바쿠치올과 레티놀 광노화 비교 연구",
]

ARTICLE = f"""
{P}요즘 스킨케어에서 <strong>바쿠치올(bakuchiol) 세럼</strong> 검색이 부쩍 늘었습니다. 레티놀을 쓰고는 싶은데 자극이 무서운 사람들이 대안으로 찾기 때문입니다. 이 글에서는 바쿠치올이 뭔지, 레티놀과 어떻게 다른지, 어떻게 고르고 써야 하는지를 <strong>성분 근거 중심</strong>으로 정리했습니다.</p>

{H2}바쿠치올이 뭔데 갑자기 1위일까</h2>
{P}바쿠치올은 <strong>바브치(babchi) 씨앗</strong> 등에서 얻는 식물 유래 성분으로, '천연 레티놀 대안'으로 불립니다. 레티놀과 화학 구조는 다르지만, 피부에서 <strong>비슷한 신호(콜라겐·턴오버 자극)</strong>를 낸다고 알려져 인기를 끌고 있습니다. 핵심 매력은 하나입니다 — <em>레티놀만큼 기대하되, 자극은 덜하다</em>는 점.</p>

{H2}레티놀 vs 바쿠치올 — 근거로 비교</h2>
{P}둘 다 '노화 케어' 성분이지만 성격이 다릅니다.</p>
{UL}
{LI}<strong>레티놀</strong> — 주름·색소에 대한 임상 근거가 가장 두텁습니다. 다만 홍조·각질·건조 등 <em>초기 자극</em>이 흔해 적응 기간이 필요합니다.</li>
{LI}<strong>바쿠치올</strong> — 2019년 한 비교 연구에서 레티놀과 <em>유사한 주름·색소 개선</em>을 보이면서 자극(따가움·홍조)은 더 적었다는 보고가 있습니다. 검증 두께는 레티놀보다 얇지만 <em>순함</em>이 강점입니다.</li>
</ul>
<table style="max-width:800px;width:100%;margin:20px auto;border-collapse:collapse;color:#cbd5e1;">
<tr style="background:#2d2d3a;color:#fff;"><th style="padding:10px;">구분</th><th style="padding:10px;">레티놀</th><th style="padding:10px;">바쿠치올</th></tr>
<tr><td style="padding:10px;">근거 두께</td><td style="padding:10px;">매우 두터움</td><td style="padding:10px;">축적 중</td></tr>
<tr><td style="padding:10px;">자극</td><td style="padding:10px;">잦음(적응 필요)</td><td style="padding:10px;">적은 편</td></tr>
<tr><td style="padding:10px;">사용 시간</td><td style="padding:10px;">주로 밤</td><td style="padding:10px;">아침·저녁</td></tr>
<tr><td style="padding:10px;">추천 대상</td><td style="padding:10px;">내성 있는 피부</td><td style="padding:10px;">민감성·입문자</td></tr>
</table>

{H2}이런 사람에게 바쿠치올이 맞다</h2>
{UL}
{LI}<strong>레티놀만 쓰면 따갑고 각질이 일어나는</strong> 민감성 피부</li>
{LI}노화 케어를 <strong>이제 막 시작하는 입문자</strong> (부담 없이 진입)</li>
{LI}아침에도 노화 케어 성분을 쓰고 싶은 사람 (바쿠치올은 낮에도 비교적 무난)</li>
{LI}임신·수유로 레티놀을 피해야 하는 경우 — 단, <strong>반드시 전문의 상담 후</strong></li>
</ul>

{H2}어떻게 고르나 — 쿠팡 인기 바쿠치올 세럼</h2>
{P}고르는 기준은 단순합니다: ① <strong>바쿠치올 함량·순도</strong>가 표기됐는지 ② 향·색소 등 <em>불필요한 자극 성분</em>이 적은지 ③ 매일 부담 없이 쓸 <em>용량·가격</em>. 아래는 쿠팡에서 많이 찾는 바쿠치올 세럼입니다(가격·재고는 실시간 확인).</p>
{product_button("바쿠치올 세럼 추천 ①", COUPANG_1)}
{product_button("바쿠치올 세럼 추천 ②", COUPANG_2)}

{H2}올리브영에서도 고를 수 있어요</h2>
{P}오프라인 매장에서 발림성·향을 직접 보고 싶다면 올리브영도 좋은 선택입니다. 바쿠치올 라인을 한눈에 비교해볼 수 있습니다.</p>
{olive_link("바쿠치올 세럼")}

{H2}주의사항 — 순해도 '테스트'는 하자</h2>
{P}세 가지만 기억하세요. 첫째, 순한 편이어도 <strong>사람마다 반응이 달라</strong> 팔 안쪽 등에 <strong>패치 테스트</strong> 후 얼굴에 쓰는 게 안전합니다. 둘째, <strong>레티놀·고농도 산(AHA/BHA)과 동시 과용</strong>은 피하고 번갈아 쓰세요. 셋째, 낮에는 <strong>자외선 차단제</strong>가 필수입니다 — 노화 케어의 절반은 자외선 차단입니다.</p>

{H2}결론</h2>
{P}정리하면 ① 레티놀이 부담스러웠다면 바쿠치올이 순한 진입점 ② 함량·자극 성분 확인하고 저농도부터 ③ 4~8주 꾸준히 + 낮엔 선크림. 세럼은 '마법'이 아니라 <strong>꾸준한 루틴의 한 축</strong>이라는 점만 기억하면 실패가 적습니다.</p>

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
            params={"query": "skincare serum bottle facial", "per_page": 1,
                    "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {key}"}, timeout=20,
        )
        r.raise_for_status()
        photo = r.json()["results"][0]
        img_url = photo["urls"]["regular"]
        alt = photo.get("alt_description") or "skincare serum bottle"
        credit = photo["user"]["name"]
        img = requests.get(img_url, timeout=30)
        img.raise_for_status()
        headers = {"Content-Disposition": 'attachment; filename="bakuchiol-serum-hero.jpg"',
                   "Content-Type": "image/jpeg"}
        up = requests.post(f"{api}/media", auth=auth, headers=headers,
                           data=img.content, timeout=60)
        up.raise_for_status()
        media = up.json()
        src = media.get("source_url", "")
        requests.post(f"{api}/media/{media['id']}", auth=auth,
                      json={"alt_text": alt}, timeout=20)
        figure = (
            '<figure class="wp-block-image aligncenter size-large hero-image" '
            'style="max-width:800px;margin:0 auto 30px auto;">'
            f'<img src="{src}" alt="{alt}" '
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
    """뷰티/미용 우선, 없으면 건강, 그것도 없으면 미분류. 조회 실패는 치명적 아님."""
    try:
        for name in ("뷰티", "미용", "건강"):
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
    print("카테고리 매칭 없음 — 미분류")
    return []


def main() -> int:
    base = os.environ["WP_GENERAL_URL"].rstrip("/")
    auth = (os.environ["WP_GENERAL_USERNAME"], os.environ["WP_GENERAL_APP_PASSWORD"])
    api = f"{base}/wp-json/wp/v2"

    media_id, hero = fetch_hero(api, auth)
    related = fetch_related(api, auth)

    html = insert_monetization(ARTICLE.strip(), related_posts=related)
    html = add_coupang_disclosure(html)
    assert COUPANG_DISCLOSURE in html, "고지문 누락"
    html = (f'<div class="post-content category-뷰티" data-category="뷰티">\n'
            f'{hero}{html}\n</div>')

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
