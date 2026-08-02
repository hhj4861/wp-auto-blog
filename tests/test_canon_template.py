"""통합 캐논 템플릿 후처리 변환 테스트.

- to_canon_headings: H2를 블로그별 액센트 그라디언트로 정규화(텍스트/앵커 보존)
- insert_monetization: 언어별 광고 라벨/관련글 헤딩(bytepulse 영문)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.post_format import H2_ACCENTS, to_canon_headings  # noqa: E402
from src.monetization import insert_monetization  # noqa: E402


# --- to_canon_headings -------------------------------------------------------

def test_canon_green_accent_applied():
    html = "<h2>소개</h2><p>본문</p>"
    out = to_canon_headings(html, accent="green")
    assert H2_ACCENTS["green"][0] in out  # #10b981
    assert "linear-gradient" in out
    assert "background-clip:text" in out


def test_canon_blue_accent_for_bytepulse():
    html = "<h2>Intro</h2>"
    out = to_canon_headings(html, accent="blue")
    assert H2_ACCENTS["blue"][0] in out  # #0ea5e9
    assert H2_ACCENTS["green"][0] not in out  # 그린 액센트는 안 섞임


def test_canon_preserves_text_and_structure():
    html = "<h2>첫 섹션</h2><p>단락</p><h2>둘째 섹션</h2>"
    out = to_canon_headings(html, accent="green")
    assert "첫 섹션" in out and "둘째 섹션" in out
    assert out.count("<h2") == 2
    assert "<p>단락</p>" in out


def test_canon_preserves_anchor_id():
    # FAQ 스키마·목차 앵커가 의존하는 id는 반드시 보존
    html = '<h2 id="faq">FAQ</h2>'
    out = to_canon_headings(html, accent="blue")
    assert 'id="faq"' in out
    assert "linear-gradient" in out


def test_canon_rewrites_existing_inline_style():
    # 자동생성이 뱉은 자체 스타일 h2를 캐논으로 덮어씀
    html = '<h2 style="color:#ff0000;font-size:2em;">제목</h2>'
    out = to_canon_headings(html, accent="green")
    assert "#ff0000" not in out
    assert H2_ACCENTS["green"][0] in out


def test_canon_no_h2_is_noop():
    html = "<p>H2 없는 본문</p><h3>소제목</h3>"
    assert to_canon_headings(html, accent="green") == html


# --- insert_monetization 언어별 라벨 -----------------------------------------

def _four_h2(lang_word: str) -> str:
    return "".join(f"<h2>{lang_word} {i}</h2><p>x</p>" for i in range(4))


def test_monetization_korean_label_default():
    out = insert_monetization(_four_h2("섹션"))
    assert ">광고</p>" in out  # 기본 한글 라벨
    assert "adsbygoogle" in out


def test_monetization_english_label_for_bytepulse():
    related = [{"url": "https://bytepulse.io/a", "title": "Related A"}]
    out = insert_monetization(
        _four_h2("Section"),
        official_link="",
        related_posts=related,
        ad_label="Ad",
        related_heading="📌 Related Posts",
    )
    assert ">Ad</p>" in out          # 영문 광고 라벨
    assert ">광고</p>" not in out     # 한글 라벨 안 섞임
    assert "Related Posts" in out
    assert "adsbygoogle" in out


def test_monetization_places_two_ads_when_enough_h2():
    out = insert_monetization(_four_h2("섹션"))
    assert out.count("data-ad-slot") == 2  # 도입부 + 섹션3 앞, 유닛 2개
