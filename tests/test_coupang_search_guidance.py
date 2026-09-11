"""Search guidance helps a person select products without inventing affiliate links."""
import re

import pytest

from src.coupang_search_guidance import product_search_guidance


def test_current_shingles_request_suggests_daily_items_and_explains_their_use():
    text = product_search_guidance(
        '건강', '대상포진초기증상', '대상포진초기증상: 발진 전 통증과 물집의 진행 특징')

    assert '쿠팡에서 검색할 상품' in text
    assert '루즈핏 순면 티셔츠' in text
    assert '건강 기록 노트' in text
    assert '생활' in text or '일상' in text
    assert '기록' in text and '진료' in text
    assert '치료' in text


def test_shingles_vaccination_topic_does_not_inherit_symptom_clothing_suggestions():
    text = product_search_guidance('건강', '대상포진예방접종', '대상포진 예방접종 비용과 대상')

    assert '루즈핏 순면 티셔츠' not in text
    assert '자동으로 정하지 못했습니다' in text


def test_food_article_suggestions_are_foods_instead_of_generic_health_products():
    text = product_search_guidance(
        '건강', '기관지에좋은음식', '기관지에 좋은 음식의 활용과 주의사항')

    assert '배즙' in text and '도라지차' in text
    assert '일반식품' in text
    assert any(word in text for word in ('원재료', '성분'))
    assert '루즈핏 순면 티셔츠' not in text


def test_bronchial_non_food_topic_does_not_inherit_food_searches_from_one_syllable():
    text = product_search_guidance('건강', '기관지배액', '기관지 배액 검사 안내')

    assert '배즙' not in text and '도라지차' not in text


@pytest.mark.parametrize('keyword,topic,exam,stage', [
    ('전기기사필기', '전기기사 필기 시험 준비방법', '전기기사', '필기'),
    ('전기기사실기', '전기기사 실기 준비와 자체평가', '전기기사', '실기'),
    ('컴퓨터활용능력2급필기', '컴퓨터활용능력 2급 필기 준비', '2급', '필기'),
    ('컴활1급실기', '컴활 1급 실기 학습과 점검', '1급', '실기'),
])
def test_exam_search_preserves_exam_grade_and_stage(keyword, topic, exam, stage):
    text = product_search_guidance('취업', keyword, topic)

    assert exam in text and stage in text
    assert '기출문제집' in text
    if '컴활' in keyword or '컴퓨터활용능력' in keyword:
        assert '컴퓨터활용능력' in text or '컴활' in text
        assert ('1급' if exam == '2급' else '2급') not in text
    assert any(word in text for word in ('연도', '최신', '개정', '출판'))


@pytest.mark.parametrize('keyword,topic', [
    ('세금계산서발행', '세금계산서 발행과 증빙 보관'),
    ('영수증정리', '영수증 정리와 보관 방법'),
])
def test_document_topics_suggest_a_product_for_the_document_task(keyword, topic):
    text = product_search_guidance('생활정보', keyword, topic)

    assert '영수증 정리 파일' in text
    assert any(word in text for word in ('칸', '크기', '사이즈'))
    assert '기출문제집' not in text


@pytest.mark.parametrize('category', ['취업', '건강', '생활정보'])
def test_unknown_topic_does_not_force_a_generic_category_product(category):
    text = product_search_guidance(category, '미분류주제', '아직 연결 규칙이 없는 주제')

    assert '자동으로 정하지 못했습니다' in text
    for unrelated in ('루즈핏 순면 티셔츠', '건강 기록 노트', '배즙', '도라지차',
                      '기출문제집', '영수증 정리 파일'):
        assert unrelated not in text


def test_topic_can_supply_the_specific_search_context():
    text = product_search_guidance('건강', '초기증상', '대상포진 초기증상과 진료 준비')

    assert '건강 기록 노트' in text
    assert '자동으로 정하지 못했습니다' not in text


@pytest.mark.parametrize('exam', ['토익스피킹', '토익라이팅', '토익브릿지'])
def test_specific_exam_is_not_collapsed_to_a_different_base_exam(exam):
    text = product_search_guidance('취업', exam + '시험일정', exam + ' 시험 준비')

    assert '검색어: ' + exam + ' 기출문제집' in text
    assert '검색어: 토익 기출문제집' not in text


@pytest.mark.parametrize('category,keyword,topic', [
    ('건강', '대상포진초기증상', '대상포진 초기증상'),
    ('취업', '전기기사필기', '전기기사 필기 준비'),
    ('생활정보', '세금계산서', '세금계산서 발행'),
])
def test_guidance_does_not_invent_a_product_or_affiliate_url(category, keyword, topic):
    text = product_search_guidance(category, keyword, topic)

    assert set(re.findall(r'https?://\S+', text)) <= {'https://www.nhs.uk/conditions/shingles/'}
