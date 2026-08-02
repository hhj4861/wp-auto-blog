"""trendpulse 캐논 글 포맷 공유 빌더.

수기 작성 글(쿠팡 리뷰 등)이 파이프라인 글과 **동일한 포맷**을 갖도록 강제하는
단일 진실 소스. 캐논 기준은 미네랄 글(사용자 검증) 실측 HTML.
포맷이 스크립트마다 드리프트하지 않게 여기서만 정의한다.
"""

from __future__ import annotations

import re

# 그린-틸 그라디언트 H2 (캐논)
H2_GRADIENT = (
    '<h2 style="font-size:1.5em;margin:40px auto 20px auto;max-width:800px;'
    'background:linear-gradient(135deg,#10b981,#22d3ee);'
    '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
    'background-clip:text;">'
)

# 블로그별 H2 액센트 (통합 캐논 — 정체성 유지)
#   green: trendpulse(그린-틸, 캐논 기준) / blue: bytepulse(블루-시안, 기존 본문 팔레트)
H2_ACCENTS = {
    "green": ("#10b981", "#22d3ee"),
    "blue": ("#0ea5e9", "#22d3ee"),
}

_H2_OPEN_RE = re.compile(r"<h2\b([^>]*)>", re.IGNORECASE)
_ID_ATTR_RE = re.compile(r'\bid\s*=\s*"([^"]*)"', re.IGNORECASE)


def _canon_h2_open(accent: str, id_attr: str = "") -> str:
    c1, c2 = H2_ACCENTS.get(accent, H2_ACCENTS["green"])
    id_part = f' id="{id_attr}"' if id_attr else ""
    return (
        f'<h2{id_part} style="font-size:1.5em;margin:40px auto 20px auto;max-width:800px;'
        f"background:linear-gradient(135deg,{c1},{c2});"
        "-webkit-background-clip:text;-webkit-text-fill-color:transparent;"
        'background-clip:text;">'
    )


def to_canon_headings(html: str, accent: str = "green") -> str:
    """자동생성 본문의 <h2> 열림 태그를 캐논 그라디언트로 정규화한다.

    통합 템플릿의 '룩'을 강제하되 **텍스트/구조는 불변**이고 id(앵커·FAQ 스키마용)는
    보존한다. 후처리 초반(수익화·스키마 삽입 전)에 돌려 일관된 스타일을 확보한다.
    """
    def _repl(m: re.Match) -> str:
        attrs = m.group(1) or ""
        idm = _ID_ATTR_RE.search(attrs)
        return _canon_h2_open(accent, idm.group(1) if idm else "")

    return _H2_OPEN_RE.sub(_repl, html)
P = '<p style="max-width:800px;margin:20px auto;text-align:left;line-height:1.8;color:#cbd5e1;">'
UL = '<ul style="max-width:800px;margin:20px auto;line-height:1.8;color:#cbd5e1;padding-left:24px;">'
LI = '<li style="margin-bottom:8px;">'

# FAQ Q&A 박스 교차 스타일 (배경, 질문 강조색) — 캐논 실측
_FAQ_BOX_STYLES = [
    ("background:#2d2d3a;", "color:#a78bfa;"),
    ("background:#252532;", "color:#60a5fa;"),
]


def faq_section(qa_pairs: list[tuple[str, str]]) -> str:
    """자주 묻는 질문(FAQ) 섹션. qa_pairs 비면 빈 문자열."""
    if not qa_pairs:
        return ""
    boxes = []
    for i, (q, a) in enumerate(qa_pairs):
        bg, qc = _FAQ_BOX_STYLES[i % 2]
        boxes.append(
            f'<div style="{bg}padding:20px;border-radius:10px;margin-bottom:15px;">'
            f'<p style="{qc}font-weight:bold;margin:0 0 10px 0;">{q}</p>'
            f'<p style="color:#cbd5e1;margin:0;line-height:1.8;">{a}</p>'
            f"</div>"
        )
    return (
        f"{H2_GRADIENT}자주 묻는 질문 (FAQ)</h2>\n"
        f'<div style="max-width:800px;margin:20px auto;">\n' + "\n".join(boxes) + "\n</div>"
    )


def sources_section(items: list[str]) -> str:
    """참고 자료(출처) 섹션. items 비면 빈 문자열.

    항목은 '(출처기관) — 설명' 형태의 정직한 공신력 출처만. 지어낸 기사·날짜 금지.
    """
    if not items:
        return ""
    lis = "".join(
        f'<li><span style="color:#94a3b8;font-size:0.85em;">{it}</span></li>'
        for it in items
    )
    return (
        '<div style="margin:30px auto;padding:20px;background:#2d2d3a;'
        'border-radius:8px;max-width:800px;">'
        '<h3 style="color:#a78bfa;margin-top:0;">📚 참고 자료</h3>'
        f'<ul style="color:#94a3b8;padding-left:20px;line-height:1.8;">{lis}</ul>'
        "</div>"
    )
