"""정체성 게이트 — 블로그별 언어/카테고리 정합성을 코드로 강제한다.

check_quality(monetization.py)와 동일한 계약을 따른다:
validate_identity(...)는 '문제 문자열 리스트'를 반환하며, 빈 리스트면 통과다.

배경:
- bytepulse(tech/kculture 모드)는 영문 블로그다. 한글 본문이 새면 정체성 붕괴.
- trendpulse(general 모드)는 한글 블로그다. 영문 본문이 새면 정체성 붕괴.
- 카테고리는 각 블로그에 실제 존재하는 것만 허용한다(오배정 방지).

임계값은 소량의 한글 고유어(예: '바쿠치올', '차전자피')가 섞인 영문 글이
통과하도록 여유 있게 잡는다.
"""

from __future__ import annotations

import os
import re

# --- 언어 판정용 문자 클래스 -------------------------------------------------
_HANGUL_RE = re.compile(r"[가-힣]")  # 완성형 한글 음절
_LATIN_RE = re.compile(r"[A-Za-z]")
_TAG_RE = re.compile(r"<[^>]+>")

# 언어 임계값
_BYTEPULSE_HANGUL_MAX = 0.30  # 이 비율 초과면 '영문 블로그에 한글 과다'
_TRENDPULSE_HANGUL_MIN = 0.15  # 이 비율 미만이면 '한글 블로그인데 한글 부족'

# --- 블로그별 유효 카테고리 --------------------------------------------------
# 정규화된 형태(소문자·공백/하이픈 제거, 한글 그대로)로 비교한다.
# bytepulse: 실측 WP REST(slug|name) 기반. slug와 name 양쪽 표기를 모두 넣는다.
# trendpulse: 관찰된 한글 카테고리 + IDENTITY_EXTRA_CATEGORIES(env)로 확장.
ALLOWED_CATEGORIES: dict[str, set[str]] = {
    # bytepulse 영문 블로그를 공유하는 두 모드
    "tech": {
        "ai-tools", "ai tools",
        "content-tools", "content tools",
        "dev-productivity", "dev productivity",
        "k-beauty", "k beauty",
        "k-culture", "k culture",
        "k-fashion", "k fashion",
        "k-food", "k food",
        "k-pop", "k pop",
        "saas-reviews", "saas reviews",
        "tech",
        "uncategorized",
    },
    "kculture": {
        "ai-tools", "ai tools",
        "content-tools", "content tools",
        "dev-productivity", "dev productivity",
        "k-beauty", "k beauty",
        "k-culture", "k culture",
        "k-fashion", "k fashion",
        "k-food", "k food",
        "k-pop", "k pop",
        "saas-reviews", "saas reviews",
        "tech",
        "uncategorized",
    },
    # trendpulse 한글 블로그
    # ⚠️ 소스 오브 트루스 = wordpress_client.CATEGORY_TAGS 의 trendpulse 사일로 키
    #    (테크·비즈니스·생산성·리뷰·건강·생활정보·취업) + create 스크립트가 쓰는 뷰티/미용/다이어트.
    #    카테고리 추가 시 여기도 갱신할 것 — 누락되면 정상 발행이 draft로 오탐 차단됨.
    "general": {
        # CATEGORY_TAGS 사일로 7종
        "테크",
        "비즈니스",
        "생산성",
        "리뷰",
        "건강",
        "생활정보",
        "취업",
        # 미용/다이어트 계열 (수기 create 스크립트 실사용)
        "뷰티",
        "미용",
        "다이어트",
    },
}

# 블로그 이름(에러 메시지용)
_BLOG_NAME = {
    "tech": "bytepulse",
    "kculture": "bytepulse",
    "general": "trendpulse",
}


def _normalize_category(value: str) -> str:
    """카테고리 비교용 정규화: 소문자화 + 공백/하이픈 제거 (한글은 보존)."""
    return re.sub(r"[\s\-_]+", "", value.strip().lower())


def _allowed_for_mode(mode: str) -> set[str]:
    """모드별 허용 카테고리(정규화 집합). general은 env 확장을 반영."""
    base = ALLOWED_CATEGORIES.get(mode, set())
    normalized = {_normalize_category(c) for c in base}
    if mode == "general":
        extra = os.getenv("IDENTITY_EXTRA_CATEGORIES", "")
        for c in extra.split(","):
            c = c.strip()
            if c:
                normalized.add(_normalize_category(c))
    return normalized


def _hangul_ratio(html: str) -> float:
    """태그 제거 텍스트에서 (한글) / (한글+라틴문자) 비율. 문자 없으면 0.0."""
    text = _TAG_RE.sub(" ", html)
    hangul = len(_HANGUL_RE.findall(text))
    latin = len(_LATIN_RE.findall(text))
    denom = hangul + latin
    if denom == 0:
        return 0.0
    return hangul / denom


def validate_identity(mode: str, category, title: str, html: str) -> list[str]:
    """블로그 정체성(언어+카테고리) 위반 목록을 반환. 빈 리스트면 통과.

    check_quality와 동일한 계약이라 pipeline의 gate_issues에 합칠 수 있다.
    """
    issues: list[str] = []
    blog = _BLOG_NAME.get(mode, mode)

    # --- 검사 A: 언어 ---
    ratio = _hangul_ratio(html)
    if mode in ("tech", "kculture"):
        if ratio > _BYTEPULSE_HANGUL_MAX:
            issues.append(
                f"정체성(언어): bytepulse는 영문이어야 함(한글 비율 {ratio * 100:.0f}%)"
            )
    elif mode == "general":
        if ratio < _TRENDPULSE_HANGUL_MIN:
            issues.append("정체성(언어): trendpulse는 한글이어야 함")

    # --- 검사 B: 카테고리 ---
    if category is None or (isinstance(category, str) and not category.strip()):
        issues.append("카테고리 미배정")
    else:
        allowed = _allowed_for_mode(mode)
        if _normalize_category(str(category)) not in allowed:
            issues.append(f"정체성(카테고리): {category}는 {blog} 유효 카테고리 아님")

    return issues
