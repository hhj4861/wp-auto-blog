#!/usr/bin/env python3
"""쿠팡 제휴 전용 신규 글 — 운동 보충제 입문 (크레아틴·BCAA) (trendpulse, CI 실행).

create_coupang_post.py와 동일 포맷 + src.post_format 공유 빌더(FAQ·참고자료)로
전 글 포맷 일치. 상품은 kit(keyword-intel) 쇼핑수요 상위(크레아틴·BCAA 각 100).
정직성: 브랜드·가격·복용경험 조작 없이 성분·근거·주의 위주. 링크는 사용자 쿠팡 파트너스 실링크.
멱등: 동일 슬러그 존재 시 업데이트.
"""

import os
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.monetization import (  # noqa: E402
    COUPANG_DISCLOSURE,
    add_coupang_disclosure,
    check_quality,
    insert_monetization,
)
from src.post_format import H2_GRADIENT as H2, P, UL, LI, faq_section, sources_section  # noqa: E402

SLUG = "workout-supplement-starter-creatine-bcaa-2026"
TITLE = "운동 보충제 입문: 크레아틴 vs BCAA, 뭐부터 시작할까 (2026 실전 가이드)"
META_DESC = (
    "헬스 시작하면 크레아틴·BCAA 중 뭘 먼저? 각 성분의 근거·복용법·차이를 정리하고 "
    "초보자 우선순위까지 2026년 실전 가이드로 짚었습니다."
)
FOCUS_KW = "운동 보충제"
LINK_CREATINE = "https://link.coupang.com/a/fIFJf5CmJg"  # 크레아틴
LINK_BCAA = "https://link.coupang.com/a/fIFK4scwq4"      # BCAA


def product_button(label: str, url: str) -> str:
    return (
        f'<p style="max-width:800px;margin:24px auto;"><a href="{url}" target="_blank" '
        f'rel="nofollow sponsored" style="display:inline-block;background:#e84c3d;'
        f'color:#fff;padding:12px 26px;border-radius:8px;text-decoration:none;'
        f'font-weight:bold;">🛒 {label} 쿠팡 최저가 보기 →</a></p>'
    )


FAQ = [
    ("Q1. 크레아틴이랑 BCAA 중 하나만 산다면?",
     "초보자라면 <strong style=\"color:#6ee7b7\">크레아틴</strong>이 우선입니다. 근력·근비대에 대한 근거가 가장 두텁고 가성비도 좋아요. BCAA는 단백질 섭취가 충분하면 효과가 제한적이라는 연구가 많습니다."),
    ("Q2. 크레아틴 로딩 꼭 해야 하나요?",
     "필수는 아닙니다. 하루 <strong style=\"color:#60a5fa\">3~5g을 꾸준히</strong> 먹으면 2~3주 후 근육 내 농도가 로딩과 같은 수준에 도달합니다. 로딩(1주간 20g)은 빨리 채우고 싶을 때 선택입니다."),
    ("Q3. BCAA는 언제 먹나요?",
     "보통 운동 전·중에 마십니다. 다만 <strong style=\"color:#60a5fa\">하루 단백질을 체중당 1.6g 이상</strong> 챙긴다면 BCAA의 추가 이득은 크지 않다는 게 중론이라, 단백질 섭취가 우선입니다."),
    ("Q4. 크레아틴 먹으면 살(물)이 찌나요?",
     "근육 세포에 수분을 끌어와 초기에 체중이 1~2kg 늘 수 있지만 <strong style=\"color:#6ee7b7\">체지방이 아니라 근육 내 수분</strong>입니다. 신장 질환이 없다면 일반적으로 안전하나, 지병이 있으면 복용 전 상담하세요."),
]
SOURCES = [
    "(식품의약품안전처) 건강기능식품·크레아틴 관련 정보",
    "(국제스포츠영양학회 ISSN) 크레아틴·단백질 섭취 포지션 스탠드",
    "(질병관리청 국가건강정보포털) 단백질 보충제 일반 정보",
]

ARTICLE = f"""
{P}헬스를 시작하면 가장 먼저 눈에 들어오는 보충제가 <strong>크레아틴</strong>과 <strong>BCAA</strong>입니다. 둘 다 '근육에 좋다'고 하는데, 실제로는 작용도 근거도 다릅니다. 이 글에서는 초보자 기준으로 두 성분의 차이·근거·복용법과 <strong>우선순위</strong>를 정리했습니다.</p>

{H2}크레아틴 vs BCAA: 근거의 무게가 다르다</h2>
{P}보충제는 '유명하다'가 아니라 '근거가 있다'로 골라야 합니다. 두 성분은 근거 수준부터 차이가 큽니다.</p>
{UL}
{LI}<strong>크레아틴</strong> — 근력·고강도 운동 수행·근비대에 대해 <em>가장 많이 연구된</em> 보충제입니다. 효과·안전성 근거가 두텁고 가격도 쌉니다.</li>
{LI}<strong>BCAA(류신·이소류신·발린)</strong> — 근합성 신호에 관여하지만, <em>총 단백질 섭취가 충분하면</em> 추가 이득이 제한적이라는 연구가 많습니다. 단백질이 부족한 상황의 보조재 성격에 가깝습니다.</li>
</ul>

{H2}1순위: 크레아틴 — 초보자의 기본기</h2>
{P}선택 기준은 단순합니다: ① <strong>크레아틴 모노하이드레이트</strong> 단일 성분(가장 검증됨) ② 불필요한 첨가물이 적을 것 ③ 하루 3~5g을 오래 먹을 양·가격. 마이크로나이즈드(미분화) 제품이 물에 잘 풀립니다.</p>
{product_button("추천 크레아틴", LINK_CREATINE)}
{P}<strong>복용법</strong>: 하루 3~5g을 매일 같은 시간에. 로딩은 선택(1주 20g→이후 유지). 운동일/휴식일 관계없이 <strong>꾸준함</strong>이 핵심이라 물·음료에 타서 습관화하세요.</p>

{H2}2순위: BCAA — 단백질을 채운 다음</h2>
{P}BCAA는 단백질 섭취가 부족한 다이어트·공복 운동·장시간 운동에서 보조 역할을 합니다. 총 단백질(체중당 1.6g 이상)을 먼저 채우고, 그다음 운동 중 음용으로 얹는 순서가 합리적입니다. 향·용해성이 매일 마시기 편한지도 봅니다.</p>
{product_button("추천 BCAA", LINK_BCAA)}
{P}<strong>복용법</strong>: 보통 운동 전·중 물에 타서. 비율은 류신 중심(2:1:1 이상)이 일반적입니다. 단, 식사·단백질 파우더로 단백질이 충분하다면 BCAA 우선순위는 낮습니다.</p>

{H2}한눈에 비교</h2>
<table style="max-width:800px;width:100%;margin:20px auto;border-collapse:collapse;color:#cbd5e1;">
<tr style="background:#2d2d3a;color:#fff;"><th style="padding:10px;">성분</th><th style="padding:10px;">주 효과</th><th style="padding:10px;">근거 수준</th><th style="padding:10px;">복용 시점</th></tr>
<tr><td style="padding:10px;">크레아틴</td><td style="padding:10px;">근력·근비대·수행능력</td><td style="padding:10px;">매우 두터움</td><td style="padding:10px;">매일 3~5g</td></tr>
<tr><td style="padding:10px;">BCAA</td><td style="padding:10px;">근합성 보조(단백질 부족 시)</td><td style="padding:10px;">조건부</td><td style="padding:10px;">운동 전·중</td></tr>
</table>

{H2}주의사항: 보충제는 식단·운동의 보조다</h2>
{P}세 가지를 짚습니다. 첫째, <strong>보충제는 단백질 식단과 훈련을 대체하지 않습니다.</strong> 총 단백질·총 훈련량이 먼저입니다. 둘째, 크레아틴은 일반적으로 안전하지만 <strong>신장 질환 등 지병이 있으면 복용 전 의료진 상담</strong>이 필요합니다. 셋째, '한 달에 몇 kg' 같은 과장 광고 제품은 피하고, 성분·함량이 명확한 제품을 고르세요.</p>

{H2}결론: 초보자의 순서</h2>
{P}정리하면 ① 단백질 식단(체중당 1.6g+) 먼저 ② 크레아틴 3~5g 매일 ③ 필요 시 BCAA를 운동 중에 추가 — 이 순서면 근거 없는 지출을 줄이고 효과는 챙길 수 있습니다. 보충제는 엔진이 아니라 보조 바퀴라는 점만 기억하세요.</p>

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
            params={"query": "gym workout fitness supplement", "per_page": 1,
                    "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {key}"}, timeout=20,
        )
        r.raise_for_status()
        photo = r.json()["results"][0]
        img_url = photo["urls"]["regular"]
        alt = photo.get("alt_description") or "gym workout and fitness"
        credit = photo["user"]["name"]
        img = requests.get(img_url, timeout=30)
        img.raise_for_status()
        headers = {"Content-Disposition": 'attachment; filename="workout-supplement-hero.jpg"',
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


def main() -> int:
    base = os.environ["WP_GENERAL_URL"].rstrip("/")
    auth = (os.environ["WP_GENERAL_USERNAME"], os.environ["WP_GENERAL_APP_PASSWORD"])
    api = f"{base}/wp-json/wp/v2"

    media_id, hero = fetch_hero(api, auth)
    related = fetch_related(api, auth)

    html = insert_monetization(ARTICLE.strip(), related_posts=related)
    html = add_coupang_disclosure(html)
    assert COUPANG_DISCLOSURE in html, "고지문 누락"
    html = (f'<div class="post-content category-건강" data-category="건강">\n'
            f'{hero}{html}\n</div>')

    issues = check_quality(
        title=TITLE, html=html, focus_keyphrase=FOCUS_KW,
        meta_description=META_DESC, require_korean=True,
    )
    if issues:
        print(f"품질 게이트 실패: {issues}")
        return 1
    print("품질 게이트 통과")

    cat = requests.get(
        f"{api}/categories", auth=auth,
        params={"search": "건강", "_fields": "id,name"}, timeout=30,
    ).json()
    cat_ids = [c["id"] for c in cat if c["name"] == "건강"][:1]

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
