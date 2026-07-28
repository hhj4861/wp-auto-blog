#!/usr/bin/env python3
"""알부틴 크림 가이드 (trendpulse, 한글, CI 실행) — 검색모듈 2위 키워드(opp 55).

keyword-intel 조회 상위 '알부틴 크림' 기반. 각질필링/바쿠치올과 동일 trendpulse 캐논 포맷.
수익화: 올리브영(rwardCode)만 + 제휴 고지. 쿠팡은 추후 딥링크로 추가.
정직성: 성분·근거·주의 중심(알부틴=미백 기능성 고시 성분), 브랜드·가격·후기 조작 없음. 멱등.
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

SLUG = "arbutin-cream-brightening-guide-2026"
TITLE = "알부틴 크림, 기미·잡티에 진짜 효과 있을까 — 성분 완전정리 (2026)"
META_DESC = (
    "알부틴 크림, 하이드로퀴논·비타민C와 뭐가 다른지, 알파·베타 알부틴 차이, "
    "기미·잡티에 어떻게 쓰는지 주의사항까지 2026년 기준으로 정리했습니다."
)
FOCUS_KW = "알부틴 크림"
OLIVE = ("https://global.oliveyoung.com/display/search?query="
         + quote("알부틴") + "&rwardCode=HHJZ4861&utm_source=influencers")
COUPANG = "https://link.coupang.com/a/fKE7QW0Dlc"  # lptag=AF4383841

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
    ("Q1. 알부틴이랑 비타민C, 뭐가 더 나아요?",
     "작용 경로가 달라 <strong style=\"color:#6ee7b7\">함께 쓰면 시너지</strong>가 납니다. 알부틴은 멜라닌을 "
     "만드는 효소(티로시나제)를 <strong style=\"color:#60a5fa\">억제</strong>하고, 비타민C는 항산화·미백을 함께 합니다. "
     "둘 중 하나면 알부틴이 자극이 적은 편이라 입문용으로 무난합니다."),
    ("Q2. 임신·수유 중에도 써도 되나요?",
     "알부틴은 비교적 순한 미백 성분으로 알려져 있지만, <strong style=\"color:#60a5fa\">모든 성분이 개인 상황에 안전한 건 "
     "아니므로</strong> 임신·수유 중에는 산부인과·피부과와 상담 후 사용하세요."),
    ("Q3. 효과는 얼마나 걸려요?",
     "색소는 천천히 옅어집니다. 보통 <strong style=\"color:#60a5fa\">4~8주 이상 꾸준히</strong> 발라야 톤·잡티 변화가 "
     "체감됩니다. 무엇보다 <strong style=\"color:#6ee7b7\">자외선 차단</strong>을 병행하지 않으면 효과가 상쇄됩니다."),
    ("Q4. 하이드로퀴논이랑 뭐가 달라요?",
     "하이드로퀴논은 강력하지만 자극·백반증 등 부작용 우려로 <strong style=\"color:#60a5fa\">전문의 처방 영역</strong>에 "
     "가깝습니다. 알부틴은 그 <strong style=\"color:#6ee7b7\">순한 대안</strong>으로, 국내에서 미백 기능성 원료로 쓰입니다."),
]
SOURCES = [
    "(식품의약품안전처) 미백 기능성화장품 고시 원료·알부틴 정보",
    "(대한피부과학회) 색소침착·기미 관리 일반 정보",
    "(질병관리청 국가건강정보포털) 피부 색소·자외선 차단 정보",
]

ARTICLE = f"""
{P}기미·잡티·칙칙함이 고민이면 한 번쯤 들어봤을 성분이 <strong>알부틴(arbutin)</strong>입니다. '순한 미백'으로 알려져 크림·세럼에 많이 들어가죠. 이 글에서는 알부틴이 어떻게 색소를 옅게 하는지, 하이드로퀴논·비타민C와 뭐가 다른지, 어떻게 골라 써야 하는지를 <strong>성분 근거 중심</strong>으로 정리했습니다.</p>

{H2}알부틴이 뭐고, 왜 미백에 쓸까</h2>
{P}피부가 자외선·자극을 받으면 <strong>멜라닌</strong>을 만들어 방어합니다. 이 멜라닌이 과하게 쌓이면 기미·잡티·색소침착이 되죠. 알부틴은 멜라닌 생성의 핵심 효소인 <strong>티로시나제(tyrosinase)를 억제</strong>해 색소가 더 만들어지는 걸 늦춥니다. 국내에서는 <strong>미백 기능성 원료</strong>로 인정받아 크림·세럼에 널리 쓰입니다. 핵심은 <em>'이미 생긴 색소를 지운다'기보다 '더 생기는 걸 막는다'</em>에 가깝다는 점입니다.</p>

{H2}하이드로퀴논·비타민C와 뭐가 다른가</h2>
{P}미백 성분은 세기·안전성·역할이 제각각입니다.</p>
{UL}
{LI}<strong>하이드로퀴논</strong> — 가장 강력하지만 자극·백반증 우려로 <em>전문의 처방</em> 영역. 일반 화장품엔 제한적.</li>
{LI}<strong>알부틴</strong> — 하이드로퀴논의 <em>순한 배당체</em> 형태. 자극이 적어 데일리 미백 케어에 적합. 국내 미백 기능성 고시 원료.</li>
{LI}<strong>비타민C</strong> — 항산화 + 미백을 함께. 알부틴과 <em>경로가 달라 병행</em> 가능하지만 산화·자극에 유의.</li>
</ul>
<table style="max-width:800px;width:100%;margin:20px auto;border-collapse:collapse;color:#cbd5e1;">
<tr style="background:#2d2d3a;color:#fff;"><th style="padding:10px;">성분</th><th style="padding:10px;">세기</th><th style="padding:10px;">자극</th><th style="padding:10px;">추천</th></tr>
<tr><td style="padding:10px;">하이드로퀴논</td><td style="padding:10px;">강함</td><td style="padding:10px;">높음(처방)</td><td style="padding:10px;">전문의 상담</td></tr>
<tr><td style="padding:10px;">알부틴</td><td style="padding:10px;">중간</td><td style="padding:10px;">낮은 편</td><td style="padding:10px;">데일리·입문</td></tr>
<tr><td style="padding:10px;">비타민C</td><td style="padding:10px;">중간</td><td style="padding:10px;">중간</td><td style="padding:10px;">항산화 병행</td></tr>
</table>

{H2}알파 알부틴 vs 베타 알부틴</h2>
{P}제품 성분표에서 두 가지를 보게 됩니다. 차이를 알면 고르기 쉽습니다.</p>
{UL}
{LI}<strong>알파(α) 알부틴</strong> — 더 <em>안정적이고 효율적</em>이라 미백 효과 측면에서 선호됩니다. 대체로 가격이 높습니다.</li>
{LI}<strong>베타(β) 알부틴</strong> — 상대적으로 저렴하지만 안정성·효율이 알파보다 낮은 편입니다.</li>
</ul>
{P}가성비만 보지 말고 <strong>알파 알부틴 함량·표기</strong>를 확인하는 게 좋습니다.</p>

{H2}이런 사람에게 알부틴이 맞다</h2>
{UL}
{LI}<strong>기미·잡티·색소침착</strong>이 신경 쓰이는 사람</li>
{LI}하이드로퀴논은 부담스럽고 <strong>순한 미백</strong>부터 시작하고 싶은 사람</li>
{LI}<strong>민감성</strong>이라 강한 미백 성분에 자극받는 피부</li>
{LI}여드름 자국 등 <strong>염증 후 색소침착(PIH)</strong> 관리가 필요한 경우</li>
</ul>

{H2}사용법 & 주기</h2>
{P}순서는 간단합니다. ① 세안 → 토너 → <strong>알부틴 크림/세럼</strong> → 보습 ② 아침·저녁 사용 가능 ③ <strong>낮엔 자외선 차단제 필수</strong> ④ 최소 4~8주 꾸준히. 미백 케어의 <strong>절반은 자외선 차단</strong>입니다 — 선크림 없이 알부틴만 바르면 밑 빠진 독에 물 붓기입니다.</p>

{H2}어떻게 고르나 — 올리브영에서 비교</h2>
{P}고르는 기준은 ① <strong>알파 알부틴</strong> 함량·표기 ② 향·알코올 등 자극 성분이 적은지 ③ 매일 부담 없이 쓸 <em>제형·가격</em>. 쿠팡·올리브영에서 알부틴 크림·세럼·앰플을 한눈에 비교할 수 있습니다(가격·재고는 실시간 확인).</p>
{product_button("알부틴 크림", COUPANG)}
{olive_link("알부틴 크림")}

{H2}주의사항 — 미백엔 '자외선 차단'이 절반</h2>
{P}세 가지를 기억하세요. 첫째, <strong>선크림 없이는 효과가 상쇄</strong>됩니다 — 자외선이 다시 색소를 만듭니다. 둘째, <strong>고농도 산·레티놀과 동시 과용</strong>은 자극이 겹치니 번갈아 쓰세요. 셋째, 2~3개월 발라도 <strong>변화가 없거나 색소가 짙어지면</strong> 피부과 진료가 맞습니다(기미는 종류에 따라 시술이 필요).</p>

{H2}결론</h2>
{P}정리하면 ① 알부틴은 '더 생기는 색소를 막는' 순한 미백 ② 알파 알부틴 함량 확인, 저농도부터 ③ 4~8주 꾸준히 + 낮엔 선크림 필수. 크림 하나로 기미가 '지워지는' 건 아니지만, <strong>꾸준한 톤 케어의 든든한 축</strong>은 됩니다.</p>

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
            params={"query": "skincare cream brightening face", "per_page": 1,
                    "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {key}"}, timeout=20,
        )
        r.raise_for_status()
        photo = r.json()["results"][0]
        alt = photo.get("alt_description") or "skincare brightening cream"
        credit = photo["user"]["name"]
        img = requests.get(photo["urls"]["regular"], timeout=30)
        img.raise_for_status()
        up = requests.post(
            f"{api}/media", auth=auth,
            headers={"Content-Disposition": 'attachment; filename="arbutin-cream-hero.jpg"',
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
    html = (f'<div class="post-content category-뷰티" data-category="뷰티">\n'
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
