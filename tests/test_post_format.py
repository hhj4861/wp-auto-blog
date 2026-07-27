"""trendpulse 캐논 포맷 공유 빌더 — FAQ·참고자료 섹션 구조 고정."""
import re
import pytest
from src.post_format import faq_section, sources_section, H2_GRADIENT


class TestFaqSection:
    QA = [("Q1. 언제 먹나요?", "취침 전입니다."),
          ("Q2. 부작용은?", "과다 복용을 피하세요.")]

    @pytest.mark.unit
    def test_has_gradient_h2_heading(self):
        out = faq_section(self.QA)
        assert "자주 묻는 질문 (FAQ)" in out
        assert H2_GRADIENT in out  # 캐논 그라디언트 H2

    @pytest.mark.unit
    def test_all_qa_rendered(self):
        out = faq_section(self.QA)
        for q, a in self.QA:
            assert q in out and a in out

    @pytest.mark.unit
    def test_alternating_box_backgrounds(self):
        out = faq_section(self.QA)
        assert "#2d2d3a" in out and "#252532" in out  # 교차 배경

    @pytest.mark.unit
    def test_empty_returns_blank(self):
        assert faq_section([]) == ""


class TestSourcesSection:
    @pytest.mark.unit
    def test_renders_box_and_items(self):
        out = sources_section(["(식품의약품안전처) 건강기능식품 기능성 정보",
                               "(국가건강정보포털) 탈모 관리"])
        assert "참고 자료" in out
        assert "식품의약품안전처" in out and "국가건강정보포털" in out
        assert out.count("<li") == 2

    @pytest.mark.unit
    def test_empty_returns_blank(self):
        assert sources_section([]) == ""
