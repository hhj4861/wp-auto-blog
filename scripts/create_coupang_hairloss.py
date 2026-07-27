#!/usr/bin/env python3
"""쿠팡 제휴 전용 신규 글 — 탈모 케어 3단계 (trendpulse, CI 실행).

create_coupang_post.py와 동일한 trendpulse 포맷(post-content 래퍼·그린틸 H2·
히어로·비교표·관련글·광고2·의무고지·🛒버튼). 상품은 kit(keyword-intel) 수요
데이터에서 선정: 탈모 영양제/두피 앰플/두피 스케일러(쇼핑수요 상위).
정직성: 실재하지 않는 브랜드·가격·테스트를 지어내지 않고 성분·사용법 위주로 서술,
구매 링크는 사용자가 쿠팡 파트너스에서 고른 실제 상품으로 연결한다.
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

SLUG = "hair-loss-care-3step-guide-2026"
TITLE = "탈모 케어 3단계: 먹고·바르고·관리하는 실전 조합 (영양제·두피앰플·스케일러)"
META_DESC = (
    "탈모 케어, 뭐부터 시작할까? 속을 채우는 탈모 영양제, 두피에 직접 바르는 앰플, "
    "두피 청결을 위한 스케일러까지 — 성분·사용법·주의사항을 2026년 실전 가이드로 정리했습니다."
)
FOCUS_KW = "탈모 케어"
LINK_NUTRIENT = "https://link.coupang.com/a/fIFCunpLiK"   # 탈모 영양제
LINK_AMPOULE = "https://link.coupang.com/a/fIFMBP0n2O"    # 두피/탈모 앰플
LINK_SCALER = "https://link.coupang.com/a/fIFOsaZ1sO"     # 두피 스케일러

H2 = ('<h2 style="font-size:1.5em;margin:40px auto 20px auto;max-width:800px;'
      'background:linear-gradient(135deg,#10b981,#22d3ee);'
      '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
      'background-clip:text;">')
P = '<p style="max-width:800px;margin:20px auto;text-align:left;line-height:1.8;color:#cbd5e1;">'
UL = '<ul style="max-width:800px;margin:20px auto;line-height:1.8;color:#cbd5e1;padding-left:24px;">'
LI = '<li style="margin-bottom:8px;">'


def product_button(label: str, url: str) -> str:
    return (
        f'<p style="max-width:800px;margin:24px auto;"><a href="{url}" target="_blank" '
        f'rel="nofollow sponsored" style="display:inline-block;background:#e84c3d;'
        f'color:#fff;padding:12px 26px;border-radius:8px;text-decoration:none;'
        f'font-weight:bold;">🛒 {label} 쿠팡 최저가 보기 →</a></p>'
    )


ARTICLE = f"""
{P}머리를 감을 때 배수구에 빠진 머리카락이 눈에 띄기 시작하면 마음이 급해집니다. 그런데 탈모 케어는 한 가지 제품으로 끝나지 않습니다. <strong>속을 채우고(영양제), 두피에 직접 바르고(앰플), 두피를 깨끗이 관리하는(스케일러)</strong> 세 갈래가 서로 다른 지점을 건드리기 때문입니다. 이 글에서는 처음 시작하는 분 기준으로 3단계를 성분·사용법 중심으로 정리했습니다.</p>

{H2}왜 '3단계'인가: 각 단계가 다른 곳을 건드린다</h2>
{P}탈모의 원인은 복합적이라 접근도 여러 갈래로 나뉩니다. 각 단계가 맡는 역할이 다릅니다.</p>
{UL}
{LI}<strong>탈모 영양제(속)</strong> — 모발은 케라틴 단백질이며, 비오틴·판토텐산·아연·L-시스테인 같은 영양소가 모발 생성의 원료·보조인자로 작용합니다. 식사로 부족하기 쉬운 부분을 채우는 기초 단계입니다.</li>
{LI}<strong>두피 앰플(두피)</strong> — 아데노신·나이아신아마이드·비오틴 등 두피 활력 성분을 모근 가까이에 직접 도포합니다. 먹는 것과 별개로 두피 환경에 접근하는 단계입니다.</li>
{LI}<strong>두피 스케일러(청결)</strong> — 과도한 피지·각질·제품 잔여물이 모공을 막으면 위 두 단계 효과도 떨어집니다. 두피를 주기적으로 딥클렌징해 '토양'을 정리하는 단계입니다.</li>
</ul>

{H2}1단계: 탈모 영양제 — 모발의 원료를 속에서 채운다</h2>
{P}선택 기준은 세 가지입니다: ① <strong>비오틴</strong> 함량이 명확히 표기돼 있을 것 ② 아연·판토텐산·L-시스테인 등 모발 관련 보조 성분이 함께 배합됐는지 ③ 식약처 건강기능식품 인증 여부. 매일 꾸준히 먹는 제품이라 하루 1회 복용 편의성도 중요합니다.</p>
{product_button("추천 탈모 영양제", LINK_NUTRIENT)}
{P}<strong>복용 팁</strong>: 비오틴 계열은 지속 복용이 핵심입니다. 모발 주기 특성상 최소 <strong>3~6개월</strong>은 먹어야 변화를 판단할 수 있습니다. 다만 비오틴 고용량은 일부 혈액검사(갑상선·심근효소) 수치를 왜곡할 수 있으니, 검사 예정이라면 며칠 전 중단하고 의료진에게 복용 사실을 알리세요.</p>

{H2}2단계: 두피 앰플 — 모근 가까이 직접 바른다</h2>
{P}앰플은 먹는 영양제가 닿지 못하는 두피 표면·모근 주변에 성분을 직접 올리는 방식입니다. 아데노신·나이아신아마이드 같은 두피 활력 성분, 카페인·멘톨 등 청량감 성분이 흔합니다. 향·자극이 강하지 않고, 도포 후 흡수가 빠른 제형을 고르면 매일 쓰기 편합니다.</p>
{product_button("추천 두피 앰플", LINK_AMPOULE)}
{P}<strong>사용 팁</strong>: 머리를 말린 뒤 <strong>두피가 드러나게 가르마를 나눠</strong> 모발이 아니라 두피에 직접 도포하고, 손끝으로 가볍게 마사지해 흡수시킵니다. 아침·저녁 하루 1~2회가 일반적입니다.</p>

{H2}3단계: 두피 스케일러 — 막힌 모공을 정리한다</h2>
{P}피지 분비가 많거나 스타일링 제품을 자주 쓴다면 두피에 각질·잔여물이 쌓입니다. 스케일러(딥클렌징 제품·두피 브러시류)는 이 노폐물을 풀어내 영양제·앰플이 작용할 '토양'을 정리합니다. 매일 하면 오히려 두피가 예민해질 수 있어 <strong>주 1~2회</strong>가 적당합니다.</p>
{product_button("추천 두피 스케일러", LINK_SCALER)}
{P}<strong>사용 팁</strong>: 샴푸 전 마른 두피 또는 젖은 두피에 적용하는 등 제품 지침을 따르고, 손톱이 아니라 지문면으로 문질러 두피 상처를 피하세요.</p>

{H2}3단계 한눈에 비교</h2>
<table style="max-width:800px;width:100%;margin:20px auto;border-collapse:collapse;color:#cbd5e1;">
<tr style="background:#2d2d3a;color:#fff;"><th style="padding:10px;">단계</th><th style="padding:10px;">접근 지점</th><th style="padding:10px;">핵심 성분</th><th style="padding:10px;">빈도</th></tr>
<tr><td style="padding:10px;">영양제</td><td style="padding:10px;">몸속(모발 원료)</td><td style="padding:10px;">비오틴·아연·L-시스테인</td><td style="padding:10px;">매일 1회</td></tr>
<tr><td style="padding:10px;">두피 앰플</td><td style="padding:10px;">두피 표면·모근</td><td style="padding:10px;">아데노신·나이아신아마이드</td><td style="padding:10px;">하루 1~2회</td></tr>
<tr><td style="padding:10px;">스케일러</td><td style="padding:10px;">모공 청결</td><td style="padding:10px;">딥클렌징·각질 관리</td><td style="padding:10px;">주 1~2회</td></tr>
</table>

{H2}주의사항: 관리로 안 되는 탈모는 병원으로</h2>
{P}세 가지는 반드시 짚고 갑니다. 첫째, <strong>영양제·앰플·스케일러는 건강기능식품·화장품이지 의약품이 아닙니다.</strong> 예방·관리·환경 개선을 돕는 것이지 진행성 탈모를 치료하지 않습니다. 둘째, <strong>단기간에 넓은 부위가 빠지거나 원형으로 빠진다면</strong> 안드로겐성·원형 탈모 등 의학적 원인일 수 있으니 피부과 진료가 먼저입니다(피나스테리드·미녹시딜 등은 의사 상담 영역). 셋째, 어떤 제품이든 <strong>최소 3개월</strong>은 꾸준히 써야 판단이 가능하니 2~3주 만에 효과가 없다고 바꾸지 마세요.</p>

{H2}결론: 오늘부터의 순서</h2>
{P}정리하면 이렇습니다. ① 탈모 영양제로 속을 채우고 ② 두피 앰플을 매일 두피에 바르고 ③ 주 1~2회 스케일러로 모공을 정리 — 이 3단계를 최소 3개월 유지하며 사진으로 기록하세요. 관리는 진행을 늦추고 두피 환경을 지키는 '기초 체력'입니다. 그 위에, 필요하다면 전문의 상담이라는 엔진을 얹는 것이 순서입니다.</p>
"""


def fetch_hero(api: str, auth: tuple) -> tuple:
    """Unsplash 헤어/두피 이미지 → WP 업로드. (media_id, figure_html). 실패 시 (None, "")."""
    key = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
    if not key:
        print("UNSPLASH 키 없음 — 히어로 생략")
        return None, ""
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": "healthy hair scalp care", "per_page": 1,
                    "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {key}"}, timeout=20,
        )
        r.raise_for_status()
        photo = r.json()["results"][0]
        img_url = photo["urls"]["regular"]
        alt = photo.get("alt_description") or "healthy hair and scalp care"
        credit = photo["user"]["name"]

        img = requests.get(img_url, timeout=30)
        img.raise_for_status()
        headers = {"Content-Disposition": 'attachment; filename="hair-loss-care-hero.jpg"',
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
    """최근 발행 한국어 글 3개 → 함께 보면 좋은 글 박스용."""
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
