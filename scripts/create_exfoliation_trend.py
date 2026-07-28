#!/usr/bin/env python3
"""각질 필링 가이드 (trendpulse, 한글, CI 실행) — 검색모듈 1위 키워드(opp 73).

commerce-automation-kit keyword-intel 조회 상위 '각질 필링' 기반. 바쿠치올과 동일
trendpulse 캐논 포맷(post-content 래퍼·그린틸 H2·P/UL/LI·Unsplash 히어로·관련글·광고2슬롯
·FAQ·참고자료). 수익화: 올리브영(rwardCode)만 + 제휴 고지. 쿠팡은 추후 딥링크로 추가.
정직성: 성분·근거·주의 중심, 브랜드·가격·후기 조작 없음. 멱등(동일 슬러그 업데이트).
"""

import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.monetization import check_quality, insert_monetization  # noqa: E402
from src.post_format import H2_GRADIENT as H2, P, UL, LI, faq_section, sources_section  # noqa: E402

SLUG = "exfoliation-peeling-care-guide-2026"
TITLE = "각질 필링, 제대로 하는 법 — 필링젤·AHA·BHA 총정리 (2026)"
META_DESC = (
    "각질 필링, 스크럽부터 AHA·BHA·PHA까지 뭐가 다른지, 내 피부엔 뭐가 맞는지, "
    "주기·주의사항까지 2026년 기준으로 정리했습니다."
)
FOCUS_KW = "각질 필링"
OLIVE = ("https://global.oliveyoung.com/display/search?query="
         + quote("필링젤") + "&rwardCode=HHJZ4861&utm_source=influencers")

DISCLOSURE = (
    '<div style="background:#2d2d3a;border-left:4px solid #10b981;padding:14px 18px;'
    'margin:0 auto 22px auto;max-width:800px;border-radius:6px;font-size:0.9em;color:#cbd5e1;">'
    '<strong style="color:#6ee7b7;">제휴 안내:</strong> 이 글의 일부 링크는 제휴 링크로, '
    '구매 시 소정의 수수료를 받을 수 있습니다(구매자 추가 부담 없음).</div>'
)


def olive_link(label: str) -> str:
    return (
        f'<p style="max-width:800px;margin:24px auto;"><a href="{OLIVE}" target="_blank" '
        f'rel="nofollow sponsored" style="display:inline-block;background:#a259c4;'
        f'color:#fff;padding:12px 26px;border-radius:8px;text-decoration:none;'
        f'font-weight:bold;">🫒 {label} 올리브영에서 보기 →</a></p>'
    )


FAQ = [
    ("Q1. 각질 필링, 얼마나 자주 해야 하나요?",
     "피부 타입에 따라 다르지만 보통 <strong style=\"color:#6ee7b7\">주 1~2회</strong>가 기준입니다. "
     "매일 하면 피부 장벽이 무너져 오히려 <strong style=\"color:#60a5fa\">홍조·따가움·건조</strong>가 생깁니다. "
     "각질이 얇아진 느낌이면 횟수를 줄이세요."),
    ("Q2. 스크럽(물리적)이랑 산(화학적) 중 뭐가 나아요?",
     "정답은 없습니다. 스크럽은 즉각적이지만 <strong style=\"color:#60a5fa\">미세 상처·자극</strong> 위험이 있고, "
     "AHA/BHA/PHA 같은 화학적 필링은 균일하고 순한 편입니다. "
     "민감성이라면 <strong style=\"color:#6ee7b7\">PHA</strong>처럼 저자극 성분부터 시작하는 게 안전합니다."),
    ("Q3. 필링하고 나서 뭘 발라야 하나요?",
     "각질을 걷어낸 직후 피부는 수분을 잃기 쉽습니다. <strong style=\"color:#6ee7b7\">보습(히알루론산·판테놀 등)</strong>을 "
     "충분히 하고, 낮에는 <strong style=\"color:#60a5fa\">자외선 차단제</strong>가 필수입니다 — 각질 제거 후 자외선에 더 예민해집니다."),
    ("Q4. 레티놀이랑 같이 써도 되나요?",
     "동시에 과하게 쓰면 자극이 겹칩니다. <strong style=\"color:#60a5fa\">날을 번갈아</strong> 쓰거나, "
     "한쪽을 저농도로 시작하세요. 따갑거나 각질이 계속 일어나면 빈도부터 줄이는 게 원칙입니다."),
]
SOURCES = [
    "(식품의약품안전처) 화장품 성분·기능성화장품 정보",
    "(대한피부과학회) 피부 장벽·각질 관리 일반 정보",
    "(질병관리청 국가건강정보포털) 피부 관리·자외선 차단 정보",
]

ARTICLE = f"""
{P}매끈한 피부의 시작은 <strong>각질 필링</strong>이지만, 과하면 오히려 독이 됩니다. 스크럽·필링젤·산(AHA·BHA·PHA)까지 종류가 많아 뭘 골라야 할지 헷갈리죠. 이 글에서는 각 방식의 차이·피부 타입별 선택·올바른 주기와 주의사항을 <strong>성분 근거 중심</strong>으로 정리했습니다.</p>

{H2}각질 필링이 뭐고, 왜 필요할까</h2>
{P}피부는 약 28일 주기로 <strong>턴오버</strong>(오래된 각질이 떨어지고 새 세포가 올라오는 과정)를 합니다. 나이·건조·자외선 등으로 이 주기가 느려지면 <em>묵은 각질</em>이 쌓여 칙칙함·거칠음·모공 막힘·트러블로 이어집니다. 각질 필링은 이 묵은 각질을 걷어내 <strong>흡수·톤·결</strong>을 개선하는 관리입니다. 핵심은 하나 — <em>'제거'가 아니라 '적정선'</em>입니다.</p>

{H2}물리적 vs 화학적 — 뭐가 다른가</h2>
{P}크게 두 갈래입니다. 성격이 다르니 피부 상태에 맞춰 고르세요.</p>
{UL}
{LI}<strong>물리적 필링</strong> — 스크럽·고마쥬·필링젤처럼 <em>문질러</em> 각질을 떼는 방식. 즉각적이지만 알갱이·마찰로 <em>미세 상처·자극</em>이 생길 수 있어 힘 조절이 중요합니다.</li>
{LI}<strong>화학적 필링</strong> — 산 성분으로 각질 결합을 <em>녹여</em> 자연스럽게 탈락시키는 방식. 균일하고 비교적 순합니다. 대표적으로 <strong>AHA</strong>(표면·건성), <strong>BHA</strong>(모공·지성), <strong>PHA</strong>(저자극·민감성)로 나뉩니다.</li>
</ul>
<table style="max-width:800px;width:100%;margin:20px auto;border-collapse:collapse;color:#cbd5e1;">
<tr style="background:#2d2d3a;color:#fff;"><th style="padding:10px;">성분</th><th style="padding:10px;">주 타깃</th><th style="padding:10px;">특징</th><th style="padding:10px;">추천 피부</th></tr>
<tr><td style="padding:10px;">AHA (글리콜산·젖산)</td><td style="padding:10px;">표면 각질·톤</td><td style="padding:10px;">수용성, 결·톤 개선</td><td style="padding:10px;">건성·칙칙함</td></tr>
<tr><td style="padding:10px;">BHA (살리실산)</td><td style="padding:10px;">모공 속 피지</td><td style="padding:10px;">지용성, 모공·블랙헤드</td><td style="padding:10px;">지성·트러블</td></tr>
<tr><td style="padding:10px;">PHA (글루코노락톤)</td><td style="padding:10px;">표면 각질</td><td style="padding:10px;">분자 커서 저자극</td><td style="padding:10px;">민감성·입문자</td></tr>
</table>

{H2}내 피부엔 뭐가 맞을까</h2>
{UL}
{LI}<strong>건성·칙칙함</strong> → AHA 계열 또는 순한 필링젤 (톤·결 위주)</li>
{LI}<strong>지성·모공·블랙헤드</strong> → BHA(살리실산) 토너·패드</li>
{LI}<strong>민감성·입문자</strong> → <strong>PHA</strong>부터 저농도로, 스크럽은 지양</li>
{LI}<strong>복합성</strong> → T존은 BHA, 볼은 AHA/PHA로 부위별 접근</li>
</ul>

{H2}올바른 사용법 & 주기</h2>
{P}순서는 간단합니다. ① <strong>주 1~2회</strong>, 저녁에 세안 후 ② 필링 제품 사용(제품별 지시 시간 준수) ③ <strong>보습</strong> 충분히 ④ 낮엔 <strong>자외선 차단제</strong> 필수. 처음엔 <em>주 1회·저농도</em>로 시작해 피부 반응을 보며 늘리세요. '더 자주 = 더 매끈'이 아니라, <strong>과하면 장벽이 무너집니다.</strong></p>

{H2}어떻게 고르나 — 올리브영에서 비교</h2>
{P}고르는 기준은 ① 내 피부 타입에 맞는 <strong>성분(AHA/BHA/PHA)</strong> ② 향·알코올 등 불필요한 자극 성분이 적은지 ③ 매일이 아니라 <em>주 1~2회</em> 쓸 용량·가격. 올리브영에서 필링젤·필링패드·산 토너를 한눈에 비교할 수 있습니다.</p>
{olive_link("각질 필링 제품")}

{H2}주의사항 — '과각질 제거'가 진짜 위험</h2>
{P}세 가지를 기억하세요. 첫째, <strong>매일 필링 금지</strong> — 따갑고 붉어지면 이미 과한 겁니다. 둘째, <strong>레티놀·고농도 산과 동시 과용 금지</strong>, 번갈아 쓰세요. 셋째, 필링 후엔 <strong>보습 + 자외선 차단</strong>이 세트입니다. 각질을 걷어낸 피부는 자외선·자극에 더 예민합니다.</p>

{H2}결론</h2>
{P}정리하면 ① 내 피부 타입에 맞는 방식(민감성은 PHA부터) ② 주 1~2회, 저농도로 시작 ③ 필링 후 보습+선크림. 각질 필링은 '박박 밀어내는' 게 아니라 <strong>피부 리듬을 되찾아주는 관리</strong>라는 점만 기억하면 실패가 적습니다.</p>

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
            params={"query": "skincare exfoliation face care", "per_page": 1,
                    "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {key}"}, timeout=20,
        )
        r.raise_for_status()
        photo = r.json()["results"][0]
        alt = photo.get("alt_description") or "skincare exfoliation"
        credit = photo["user"]["name"]
        img = requests.get(photo["urls"]["regular"], timeout=30)
        img.raise_for_status()
        up = requests.post(
            f"{api}/media", auth=auth,
            headers={"Content-Disposition": 'attachment; filename="exfoliation-hero.jpg"',
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
