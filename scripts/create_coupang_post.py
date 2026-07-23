#!/usr/bin/env python3
"""쿠팡 제휴 전용 신규 글 발행 + 기존 글 원복 (trendpulse, CI 실행).

방침: 기존 글은 수정하지 않는다 — 제휴별 전용 신규 글로 운영.
- #827(미네랄 글)에 삽입했던 쿠팡 박스/고지문을 제거(원복)
- 쿠팡 상품 2개를 다루는 전용 신규 글을 발행 (광고·고지문·품질 게이트 적용)
멱등: 같은 슬러그 글이 이미 있으면 생성을 건너뛴다.
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

SLUG = "sleep-supplement-combo-guide-2026"
TITLE = "수면 영양제 뭐부터 시작할까? 멜라토닌·테아닌·유산균 실전 조합 가이드"
META_DESC = (
    "수면 영양제를 처음 시작한다면 멜라토닌·테아닌·유산균 조합부터. "
    "성분별 작용 원리, 복용 타이밍, 주의사항까지 2026년 실전 가이드로 정리했습니다."
)
FOCUS_KW = "수면 영양제"
LINK_MELATONIN = "https://link.coupang.com/a/fCnS1Z77W8"
LINK_LACTOFIT = "https://link.coupang.com/a/fCnXmvwMsS"


def product_button(label: str, url: str) -> str:
    return (
        f'<p style="margin:18px 0;"><a href="{url}" target="_blank" '
        f'rel="nofollow sponsored" style="display:inline-block;background:#e84c3d;'
        f'color:#fff;padding:12px 26px;border-radius:8px;text-decoration:none;'
        f'font-weight:bold;">🛒 {label} 쿠팡 최저가 보기 →</a></p>'
    )


ARTICLE = f"""
<p>밤에 누워도 30분 넘게 뒤척이고, 아침엔 잔 것 같지 않은 날이 이어진다면 수면의 '양'보다 '질'이 무너진 상태일 가능성이 큽니다. 수면제를 먹기엔 부담스럽고, 그렇다고 방치하자니 낮의 집중력이 갈수록 떨어지는 분들이 가장 먼저 시도해볼 만한 것이 <strong>수면 영양제</strong>입니다. 이 글에서는 처음 시작하는 분 기준으로 멜라토닌·테아닌·유산균 세 가지 성분의 조합을 실전 순서대로 정리했습니다.</p>

<h2>왜 '조합'이 중요한가: 성분마다 맡는 역할이 다르다</h2>
<p>수면 영양제는 한 가지 성분이 모든 걸 해결해주지 않습니다. 성분마다 개입하는 단계가 다르기 때문입니다.</p>
<ul>
<li><strong>멜라토닌</strong> — 뇌에 '지금은 밤'이라는 신호를 보내 수면 리듬 자체를 앞당깁니다. 잠드는 데 오래 걸리는 <em>입면 지연형</em>에 맞습니다.</li>
<li><strong>테아닌</strong> — 녹차에서 유래한 아미노산으로, 각성 상태를 낮춰 긴장을 풀어줍니다. 머릿속이 시끄러워 잠이 안 오는 <em>과각성형</em>에 맞습니다.</li>
<li><strong>유산균(프로바이오틱스)</strong> — 직접적인 수면 성분은 아니지만, 장-뇌 축(gut-brain axis) 연구가 쌓이며 장 환경이 스트레스 호르몬과 수면의 질에 영향을 준다는 근거가 늘고 있습니다. 기초 체력처럼 깔아두는 성분입니다.</li>
</ul>

<h2>1단계: 멜라토닌 + 테아닌 — 입면을 잡는 시작 조합</h2>
<p>국내에서 일반 식품으로 유통되는 멜라토닌 제품은 식물성 원료 기반이 많고, 테아닌과 함께 배합된 제품이 시작하기에 무난합니다. 해외 직구 고용량(5~10mg)부터 시작하는 것보다, <strong>1일 2mg 수준의 저용량</strong>으로 몸의 반응을 확인하는 편이 안전합니다.</p>
<p>제가 기준으로 삼는 선택 조건은 세 가지입니다: ① 식약처 인증 여부 ② 멜라토닌 함량이 명확히 표기돼 있을 것 ③ 테아닌 등 보조 성분의 배합량 공개. 이 조건을 채운 제품 중 접근성이 좋은 것이 아래 제품입니다.</p>
{product_button("식물성 멜라토닌 2mg + 테아닌 나잇", LINK_MELATONIN)}
<p><strong>복용 타이밍</strong>: 취침 30분~1시간 전. 멜라토닌은 '먹고 버티는' 성분이 아니라 먹고 바로 조명을 낮추고 화면을 끄는 것까지가 한 세트입니다. 복용 후에도 스마트폰을 보면 블루라이트가 멜라토닌 신호를 상쇄합니다.</p>

<h2>2단계: 유산균 — 장이 편해야 수면 루틴이 유지된다</h2>
<p>수면 개선을 시작한 분들이 의외로 놓치는 게 장 컨디션입니다. 새벽에 속이 더부룩해 깨거나, 스트레스를 받으면 장부터 반응하는 타입이라면 유산균을 기본으로 깔아두는 것이 수면 루틴 유지에 도움이 됩니다. 국내에서 가장 검증 데이터가 많은 건 역시 대중적인 생유산균 제품군입니다.</p>
{product_button("락토핏 생유산균 골드", LINK_LACTOFIT)}
<p><strong>복용 타이밍</strong>: 유산균은 아침 공복 또는 식후 등 제품 권장을 따르되, 매일 같은 시간에 먹는 일관성이 균주 정착에 더 중요합니다.</p>

<h2>성분별 비교 한눈에 보기</h2>
<table style="width:100%;border-collapse:collapse;">
<tr style="background:#2d2d3a;color:#fff;"><th style="padding:10px;">성분</th><th style="padding:10px;">맞는 유형</th><th style="padding:10px;">복용 시점</th><th style="padding:10px;">체감 시기</th></tr>
<tr><td style="padding:10px;">멜라토닌</td><td style="padding:10px;">잠들기까지 오래 걸림</td><td style="padding:10px;">취침 30분~1시간 전</td><td style="padding:10px;">수일 내</td></tr>
<tr><td style="padding:10px;">테아닌</td><td style="padding:10px;">긴장·생각 과다형</td><td style="padding:10px;">저녁~취침 전</td><td style="padding:10px;">당일~수일</td></tr>
<tr><td style="padding:10px;">유산균</td><td style="padding:10px;">장 예민·스트레스형</td><td style="padding:10px;">매일 일정 시간</td><td style="padding:10px;">2~4주</td></tr>
</table>

<h2>주의사항: 영양제가 해결 못 하는 것</h2>
<p>세 가지는 반드시 짚고 갑니다. 첫째, <strong>멜라토닌은 임신·수유 중이거나 자가면역 질환, 항응고제 복용 중이라면 복용 전 의사 상담이 필요합니다.</strong> 둘째, 2주 이상 꾸준히 복용해도 수면이 나아지지 않거나 코골이·무호흡이 의심되면 영양제가 아니라 수면클리닉 진료가 맞습니다. 셋째, 카페인을 오후 2시 이후에도 마시면서 영양제로 잠을 잡으려는 건 순서가 뒤바뀐 접근입니다.</p>

<h2>결론: 오늘 밤부터 적용하는 순서</h2>
<p>정리하면 이렇습니다. ① 오후 2시 이후 카페인 끊기 ② 취침 1시간 전 멜라토닌+테아닌 복용 후 조명 낮추기 ③ 유산균은 매일 아침 고정 ④ 2주간 기상 시각을 일정하게 유지하며 변화 기록. 영양제는 이 루틴의 보조 바퀴이지 엔진이 아닙니다. 다만 보조 바퀴가 있으면 루틴이 자리 잡을 때까지 넘어지지 않고 버틸 수 있습니다.</p>
"""


def revert_old_post(api: str, auth: tuple) -> None:
    """#827 미네랄 글에서 쿠팡 박스·고지문 제거 (기존 글 무수정 방침)."""
    r = requests.get(
        f"{api}/posts", auth=auth,
        params={"search": "미네랄이 수면과 집중력", "per_page": 3,
                "status": "publish", "_fields": "id"},
        timeout=30,
    )
    r.raise_for_status()
    posts = r.json()
    if not posts:
        print("원복 대상 글 없음")
        return
    pid = posts[0]["id"]
    p = requests.get(
        f"{api}/posts/{pid}", auth=auth,
        params={"context": "edit", "_fields": "id,content.raw"}, timeout=30,
    ).json()
    raw = p["content"]["raw"]
    cleaned = re.sub(
        r'\s*<div style="max-width:800px;margin:35px auto;padding:20px;'
        r'background:#2d2d3a;[^>]*>.*?함께 챙기면 좋은 보충제.*?</div>\s*',
        "\n", raw, flags=re.S,
    )
    cleaned = re.sub(
        r'<p id="coupang-disclosure"[^>]*>.*?</p>\s*', "", cleaned, flags=re.S,
    )
    if cleaned != raw:
        requests.post(
            f"{api}/posts/{pid}", auth=auth, json={"content": cleaned}, timeout=60,
        ).raise_for_status()
        print(f"원복 완료: #{pid} (쿠팡 박스·고지문 제거)")
    else:
        print(f"원복 불필요: #{pid} (이미 깨끗함)")


def main() -> int:
    base = os.environ["WP_GENERAL_URL"].rstrip("/")
    auth = (os.environ["WP_GENERAL_USERNAME"], os.environ["WP_GENERAL_APP_PASSWORD"])
    api = f"{base}/wp-json/wp/v2"

    revert_old_post(api, auth)

    # 멱등: 동일 슬러그 존재 시 스킵
    dup = requests.get(
        f"{api}/posts", auth=auth,
        params={"slug": SLUG, "status": "publish,draft", "_fields": "id,link"},
        timeout=30,
    ).json()
    if dup:
        print(f"SKIP (이미 존재): {dup[0]['link']}")
        return 0

    html = insert_monetization(ARTICLE.strip())  # 광고 유닛 (공식 CTA 없음)
    html = add_coupang_disclosure(html)
    assert COUPANG_DISCLOSURE in html, "고지문 누락"

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

    r = requests.post(
        f"{api}/posts", auth=auth,
        json={
            "title": TITLE,
            "slug": SLUG,
            "content": html,
            "excerpt": META_DESC,
            "status": "publish",
            "categories": cat_ids,
            "meta": {
                "_yoast_wpseo_metadesc": META_DESC,
                "_yoast_wpseo_focuskw": FOCUS_KW,
                "_yoast_wpseo_title": f"{TITLE} | TrendPulse",
            },
        },
        timeout=60,
    )
    r.raise_for_status()
    print(f"발행 완료: {r.json()['link']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
