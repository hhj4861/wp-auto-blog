"""정체성 게이트 테스트.

하위호환 회귀 방지 포함:
- 바쿠치올 영문 K-Beauty(소량 한글 고유어 섞임) 통과
- 알부틴 한글 건강(trendpulse) 통과
"""

import pytest

from src.identity_gate import validate_identity


# 충분한 분량의 영문 본문(한글 없음)
_EN_HTML = "<p>" + ("This is a comprehensive English article about software tools. " * 40) + "</p>"

# 충분한 분량의 한글 본문
_KO_HTML = "<p>" + ("이 글은 건강과 다이어트에 관한 한국어 정보입니다. " * 40) + "</p>"

# 바쿠치올류: 영문 본문에 소량 한글 고유어만 섞임
_EN_WITH_KO_TERMS = (
    "<p>" + ("Bakuchiol is a plant-derived retinol alternative for K-Beauty routines. " * 40)
    + "바쿠치올 차전자피 알부틴</p>"
)


def test_bytepulse_english_valid_category_passes():
    # (a) bytepulse 영문 + 유효 카테고리 → 통과
    issues = validate_identity(mode="tech", category="AI Tools", title="Best AI Tools", html=_EN_HTML)
    assert issues == []


def test_bytepulse_korean_body_flags_language():
    # (b) bytepulse에 한글 본문 → 언어 issue
    issues = validate_identity(mode="tech", category="tech", title="Title", html=_KO_HTML)
    assert any("정체성(언어)" in i and "bytepulse" in i for i in issues)


def test_bytepulse_off_identity_category_flags_category():
    # (c) bytepulse에 off-identity 카테고리('건강') → 카테고리 issue
    issues = validate_identity(mode="kculture", category="건강", title="K-Pop News", html=_EN_HTML)
    assert any("정체성(카테고리)" in i for i in issues)
    # 언어는 문제 없어야 함
    assert not any("정체성(언어)" in i for i in issues)


def test_trendpulse_korean_valid_category_passes():
    # (d) trendpulse 한글 + 유효 카테고리 → 통과
    issues = validate_identity(mode="general", category="건강", title="건강 정보", html=_KO_HTML)
    assert issues == []


def test_trendpulse_english_body_flags_language():
    # (e) trendpulse 영문 본문 → 언어 issue
    issues = validate_identity(mode="general", category="건강", title="건강", html=_EN_HTML)
    assert any("정체성(언어)" in i and "trendpulse" in i for i in issues)


def test_bytepulse_minor_korean_terms_passes():
    # (f) 소량 한글 고유어 섞인 영문(바쿠치올류) → 통과
    issues = validate_identity(mode="tech", category="k-beauty", title="Bakuchiol Guide", html=_EN_WITH_KO_TERMS)
    assert issues == []


# --- 하위호환 회귀 ---------------------------------------------------------
def test_backward_compat_bakuchiol_kbeauty():
    # 기존 유효 발행글: 바쿠치올 영문 K-Beauty
    issues = validate_identity(mode="kculture", category="K-Beauty", title="Bakuchiol", html=_EN_WITH_KO_TERMS)
    assert issues == []


def test_backward_compat_arbutin_health_korean():
    # 기존 유효 발행글: 알부틴 한글 건강(trendpulse)
    issues = validate_identity(mode="general", category="건강", title="알부틴 효능", html=_KO_HTML)
    assert issues == []


def test_missing_category_flags():
    for cat in (None, "", "   "):
        issues = validate_identity(mode="tech", category=cat, title="T", html=_EN_HTML)
        assert any("카테고리 미배정" in i for i in issues)


def test_env_extra_category(monkeypatch):
    monkeypatch.setenv("IDENTITY_EXTRA_CATEGORIES", "라이프,여행")
    issues = validate_identity(mode="general", category="여행", title="여행 정보", html=_KO_HTML)
    assert issues == []


def test_category_normalization_slug_and_name():
    # slug/name·대소문자·하이픈 정규화 매칭
    for cat in ("ai-tools", "AI Tools", "AITOOLS", "Dev-Productivity"):
        issues = validate_identity(mode="tech", category=cat, title="T", html=_EN_HTML)
        assert not any("정체성(카테고리)" in i for i in issues), cat


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
