#!/usr/bin/env python3
"""발행된 머니 글의 가독성·고지 결함을 소급 수정한다 (2026-07-22 감사 후속).

수정 항목:
  1. 밝은 배경(3줄 요약 박스·CTA Step 카드) 위 <strong>이 다크 accent(#c4b5fd 등)로
     덮여 대비비 1.2~1.6:1이 된 것 → 배경에 맞는 가독 색으로 복원
  2. 비의료 주제(에너지바우처 등)에 잘못 붙은 의료 면책 문구 제거
  3. __trashed 슬러그 완전 삭제

DRY_RUN=true면 대상만 보고한다.
"""

import os
import re

import requests

BASE_URL = (os.environ.get("WP_GENERAL_URL") or "").rstrip("/")
API = f"{BASE_URL}/wp-json/wp/v2"
DRY_RUN = (os.environ.get("DRY_RUN", "true").lower() != "false")

session = requests.Session()
session.auth = (os.environ.get("WP_GENERAL_USERNAME", ""),
                os.environ.get("WP_GENERAL_APP_PASSWORD", ""))
session.headers.update({"User-Agent": "Mozilla/5.0 (trendpulse-contrast-fix)"})

# 다크테마 accent 팔레트 (밝은 배경 위에서 판독 불가가 되는 색들)
DARK_ACCENTS = ("#c4b5fd", "#67e8f9", "#a78bfa", "#7dd3fc", "#93c5fd", "#5eead4")
# 밝은 배경 컨테이너 → 그 안의 strong에 써야 할 색
LIGHT_BOXES = {
    "#e8f4fd": "#1e3a5f",   # 3줄 요약 박스 (연하늘)
    "#fff8e1": "#7c4a03",   # 핵심 인사이트 박스 (연노랑)
}
# 컬러 CTA 카드 배경 (진한 단색) → 흰색 글씨
SOLID_CARDS = ("#5046e5", "#e91e63", "#00bcd4", "#388e3c", "#0066cc")

MEDICAL_LINE = ("본 글은 지원 제도 안내이며 의학적 진단·치료에 대한 조언이 아닙니다. "
                "구체적인 사항은 관할 기관 또는 의료기관에서 확인하세요.")
MEDICAL_TOPIC_RE = re.compile(
    r"검진|예방접종|백신|의료비|치매|질환|진료|병원|처방|임플란트|보청기|건강보험")


def fix_light_box_strongs(html: str) -> tuple[str, int]:
    """밝은 배경 div/컬러 카드 블록 안의 strong 색상을 배경에 맞게 교정."""
    fixed = 0

    def fix_block(block: str, target_color: str) -> str:
        nonlocal fixed

        def repl(m):
            nonlocal fixed
            attrs, inner = m.group(1), m.group(2)
            cm = re.search(r"color\s*:\s*(#[0-9a-fA-F]{3,6})", attrs)
            if cm and cm.group(1).lower() in [c.lower() for c in DARK_ACCENTS]:
                fixed += 1
                new_attrs = re.sub(r"color\s*:\s*#[0-9a-fA-F]{3,6}",
                                   f"color:{target_color}", attrs)
                return f"<strong{new_attrs}>{inner}</strong>"
            return m.group(0)

        return re.sub(r"<strong([^>]*)>([^<]*)</strong>", repl, block)

    # 밝은 배경 박스: 여는 div부터 대응 </div>까지를 근사 매칭 (박스는 중첩이 얕음)
    for bg, color in LIGHT_BOXES.items():
        pattern = re.compile(
            rf'(<div[^>]*background(?:-color)?\s*:\s*{re.escape(bg)}[^>]*>)(.*?)(</div>)',
            re.DOTALL | re.IGNORECASE)
        html = pattern.sub(lambda m: m.group(1) + fix_block(m.group(2), color) + m.group(3), html)

    # 진한 단색 카드: 그 안의 strong은 흰색
    for bg in SOLID_CARDS:
        pattern = re.compile(
            rf'(<(?:div|a)[^>]*background(?:-color)?\s*:\s*{re.escape(bg)}[^>]*>)(.*?)(</(?:div|a)>)',
            re.DOTALL | re.IGNORECASE)
        html = pattern.sub(lambda m: m.group(1) + fix_block(m.group(2), "#ffffff") + m.group(3), html)

    return html, fixed


def fix_medical_disclaimer(html: str, title: str) -> tuple[str, bool]:
    """비의료 주제에 붙은 의료 면책 문구 제거."""
    if MEDICAL_LINE not in html:
        return html, False
    if MEDICAL_TOPIC_RE.search(title):
        return html, False  # 실제 의료 주제 — 유지
    cleaned = html.replace(MEDICAL_LINE, "").replace("<br/><br/>", "<br/>")
    # 고지 문단이 비었으면 문단째 제거
    cleaned = re.sub(r'<p id="policy-disclaimer"[^>]*>\s*(?:<br/>)?\s*</p>', "", cleaned)
    return cleaned, True


def main():
    if not BASE_URL:
        raise SystemExit("WP_GENERAL_URL 필요")
    print(f"대상: {BASE_URL} | DRY_RUN={DRY_RUN}\n{'=' * 55}")

    r = session.get(f"{API}/posts", params={
        "status": "publish", "per_page": 30, "orderby": "date", "order": "desc",
        "context": "edit", "_fields": "id,slug,title,content"}, timeout=60)
    r.raise_for_status()

    total_contrast, total_medical = 0, 0
    for p in r.json():
        html = p["content"].get("raw") or ""
        title = p["title"].get("raw") or ""
        new_html, n_fixed = fix_light_box_strongs(html)
        new_html, med_removed = fix_medical_disclaimer(new_html, title)
        if n_fixed == 0 and not med_removed:
            continue
        total_contrast += n_fixed
        total_medical += int(med_removed)
        marks = []
        if n_fixed:
            marks.append(f"대비 {n_fixed}곳")
        if med_removed:
            marks.append("의료고지 제거")
        print(f"  #{p['id']} {title[:40]:42} → {', '.join(marks)}")
        if not DRY_RUN:
            ur = session.post(f"{API}/posts/{p['id']}", json={"content": new_html}, timeout=60)
            if ur.status_code != 200:
                print(f"    ⚠️ 업데이트 실패 {ur.status_code}: {ur.text[:120]}")

    print(f"\n합계: 대비 교정 {total_contrast}곳, 의료고지 제거 {total_medical}건")

    # __trashed 슬러그 완전 삭제
    tr = session.get(f"{API}/posts", params={
        "search": "trashed", "status": "any", "context": "edit", "per_page": 30,
        "_fields": "id,slug"}, timeout=60)
    victims = [i for i in (tr.json() if tr.status_code == 200 else [])
               if re.match(r"^_*trashed(-\d+)?$", i.get("slug", ""))]
    print(f"__trashed 삭제 대상: {[v['slug'] for v in victims] or '없음'}")
    if not DRY_RUN:
        for v in victims:
            dr = session.delete(f"{API}/posts/{v['id']}", params={"force": "true"}, timeout=40)
            print(f"  {v['slug']}: {dr.status_code}")

    if DRY_RUN:
        print("\nDRY_RUN — 변경 없음. 적용하려면 DRY_RUN=false")


if __name__ == "__main__":
    main()
