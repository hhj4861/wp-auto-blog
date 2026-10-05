"""Final-review contracts: bounded recovery, full coverage, and redacted diagnosis."""
from copy import deepcopy
import io
import json
from unittest.mock import Mock

import pytest
from loguru import logger

from src import market_opportunity as opportunity
from src.monetization import add_policy_disclaimers
from tests.test_market_opportunity import (
    ANSWER, ARTICLE, TOPIC, approved_article_brief,  # noqa: F401
)


@pytest.fixture
def scoped(approved_article_brief):
    brief = deepcopy(approved_article_brief)
    brief['suitability_evidence'] = {'review': {'required_facets': [
        {'facet': name, 'supported': True, 'answer': ANSWER}
        for name in ('관리 방법', '회복 방법', '재발 기준')]}}
    return brief


def response(**changes):
    return {'covers_primary_intent': True, 'answer_quote': ANSWER,
            'facet_reviews': [{'facet_index': i, 'covered': True, 'reason': 'covered',
                              'answer_quote': ANSWER} for i in range(3)], **changes}


def run(brief, model, html=ARTICLE):
    output = io.StringIO()
    sink = logger.add(output, format='{message}')
    try:
        issues = opportunity.review_article(TOPIC, html, '', brief, model)
    finally:
        logger.remove(sink)
    diagnostic = json.loads(output.getvalue().split('article_intent_review ')[1])
    return issues, diagnostic


def test_complete_article_records_full_coverage_without_model_text(scoped):
    model = Mock(return_value=response(secret='private value'))
    issues, diagnostic = run(scoped, model)
    assert issues == [] and diagnostic['status'] == 'accepted'
    assert len(diagnostic['article_sha256']) == len(diagnostic['brief_sha256']) == 64
    assert [r['facet_index'] for r in diagnostic['attempts'][0]['facets']] == [0, 1, 2]
    assert 'private' not in json.dumps(diagnostic) and ANSWER not in json.dumps(diagnostic, ensure_ascii=False)
    model.assert_called_once()


def test_missing_recovery_method_stays_held_with_exact_facet_and_no_retry(scoped):
    raw = response()
    raw['facet_reviews'][1].update(covered=False, reason='missing_answer', answer_quote='')
    model = Mock(return_value=raw)
    issues, diagnostic = run(scoped, model)
    assert issues == ['최종 글의 필수 답변 누락: 항목 2']
    assert diagnostic['attempts'][0]['missing_facet_indices'] == [1]
    assert diagnostic['attempts'][0]['facets'][1]['reason'] == 'missing_answer'
    model.assert_called_once()  # Never fish for a more favorable substantive verdict.


def test_primary_intent_rejection_is_distinct_from_missing_facets(scoped):
    model = Mock(return_value=response(covers_primary_intent=False, answer_quote=''))
    issues, diagnostic = run(scoped, model)
    assert '주된 질문' in issues[0]
    assert diagnostic['status'] == 'primary_intent_not_covered'
    model.assert_called_once()


@pytest.mark.parametrize('facet', [None, 1])
def test_wrong_quote_is_corrected_once_without_rewriting_content(scoped, facet):
    raw = response()
    if facet is None:
        raw['answer_quote'] = '본문에 없는 private-token 인용입니다'
    else:
        raw['facet_reviews'][facet]['answer_quote'] = '본문에 없는 private-token 인용입니다'
    model = Mock(side_effect=[raw, response()])
    issues, diagnostic = run(scoped, model)
    assert issues == [] and model.call_count == 2
    reason = 'article_quote' if facet is None else 'article_facet_quote'
    assert diagnostic['attempts'][0]['reason'] == reason
    assert diagnostic['attempts'][1]['status'] == 'reviewed'
    retry = model.call_args_list[1].args[0]
    assert reason in retry and '부정 판정은 바꾸지' in retry
    assert 'private-token' not in retry + json.dumps(diagnostic)


def test_unfixed_quote_failure_is_not_reported_as_bad_content(scoped):
    model = Mock(return_value=response(answer_quote='없는 근거 문장입니다'))
    issues, diagnostic = run(scoped, model)
    assert issues == ['최종 검색 의도 심사 오류: invalid_schema:article_quote']
    assert diagnostic['status'] == 'review_error' and model.call_count == 2


@pytest.mark.parametrize('change,reason', [
    (lambda r: r.pop('facet_reviews'), 'article_facets'),
    (lambda r: r['facet_reviews'].pop(), 'article_facets'),
    (lambda r: r['facet_reviews'][1].update(facet_index=0), 'article_facet_index'),
    (lambda r: r['facet_reviews'][0].update(facet_index=True), 'article_facet_index'),
    (lambda r: r['facet_reviews'][0].update(facet_index=9), 'article_facet_index'),
    (lambda r: r['facet_reviews'][0].update(covered='true'), 'article_facet_verdict'),
    (lambda r: r['facet_reviews'][0].update(reason='private arbitrary explanation'), 'article_facet_verdict'),
])
def test_bad_facet_responses_cannot_grant_publication(scoped, change, reason):
    raw = response(); change(raw)
    model = Mock(return_value=raw)
    issues, diagnostic = run(scoped, model)
    assert issues == ['최종 검색 의도 심사 오류: invalid_schema:' + reason]
    assert model.call_count == 2 and 'private arbitrary' not in json.dumps(diagnostic)


@pytest.mark.parametrize('node', ['h2', 'nav', 'footer'])
def test_non_answer_text_cannot_supply_facet_quote(scoped, node):
    raw = response(); raw['facet_reviews'][1]['answer_quote'] = '소제목 또는 안내에만 있는 구절입니다.'
    model = Mock(return_value=raw)
    issues, _ = run(scoped, model, ARTICLE + f'<{node}>소제목 또는 안내에만 있는 구절입니다.</{node}>')
    assert 'article_facet_quote' in issues[0]


def test_policy_disclaimer_cannot_supply_answer_evidence(scoped):
    text = '공고를 확인하라는 고지에만 있는 답변입니다.'
    model = Mock(return_value=response(answer_quote=text))
    issues, _ = run(scoped, model, ARTICLE + f'<p id="policy-disclaimer">{text}</p>')
    assert 'article_quote' in issues[0]
    assert text not in model.call_args_list[0].args[0]


@pytest.mark.parametrize('topic', ['구내염빨리낫는법', '폐암 초기증상', '혈당 정상수치'])
def test_clinical_article_has_health_notice_and_no_policy_boilerplate(topic):
    html = add_policy_disclaimers('<p>실제 본문</p>', '건강', topic)
    assert '일반적인 건강 정보' in html and '의료진과 상담' in html
    assert '공식 공고' not in html and '지원 제도 안내' not in html
    assert add_policy_disclaimers(html, '건강', topic) == html


@pytest.mark.parametrize('category,topic', [('건강', '예방접종 지원사업 신청'), ('취업', '채용 공고')])
def test_policy_articles_keep_application_notice(category, topic):
    html = add_policy_disclaimers('<p>실제 본문</p>', category, topic)
    assert '공식 공고' in html



@pytest.mark.parametrize('primary', [False, True])
def test_quote_recovery_cannot_overwrite_observed_negative_verdict(scoped, primary):
    raw = response(covers_primary_intent=primary)
    if primary:
        raw['facet_reviews'][0].update(covered=False, reason='partial_answer', answer_quote='')
    raw['facet_reviews'][2]['answer_quote'] = '본문에 없는 구절입니다'
    model = Mock(side_effect=[raw, response()])
    issues, diagnostic = run(scoped, model)
    assert issues and model.call_count == 2
    assert diagnostic['status'] == ('missing_required_facets' if primary else 'primary_intent_not_covered')
