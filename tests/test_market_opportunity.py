"""Pure search-opportunity gates, with synthetic evidence and no external calls."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import Mock

import pytest

from src import market_opportunity as opportunity


NOW = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
KEYWORD = 'ITQ자격증조회'
TOPIC = 'ITQ자격증조회 방법과 취득 내역 확인'
INTENT = '취득한 ITQ 자격증과 성적 정보를 어디서 확인하나요?'
UNSET = object()


def search_rows():
    domains = ['alpha.example', 'beta.example', 'alpha.example',
               'gamma.example', 'beta.example']
    return [
        {
            'url': f'https://{domain}/guide/{index}',
            'domain': domain,
            'title': f'ITQ 자격증 조회와 취득 내역 확인 안내 {index}',
            'snippet': '취득한 ITQ 자격증과 성적 정보를 조회하는 경로를 안내합니다.',
        }
        for index, domain in enumerate(domains)
    ]


def review():
    return {
        'scope': 'full_keyword',
        'target_keyword': KEYWORD,
        'matches': [
            {'result_index': 0, 'quote': 'ITQ 자격증 조회와 취득 내역 확인'},
            {'result_index': 1, 'quote': '취득한 ITQ 자격증과 성적 정보를 조회하는 경로'},
        ],
    }


def candidate(*, results=None, proposed_review=None, provider='google_custom_search',
              checked_at=UNSET):
    results = search_rows() if results is None else results
    checked_at = NOW.isoformat() if checked_at is UNSET else checked_at
    item = {
        'keyword': KEYWORD, 'topic': TOPIC, 'intent': INTENT,
        'selected_at': checked_at, 'organic_provider': provider,
        'organic_results': results, 'evidence_mode': 'serp',
        'trend_growth': None, 'publish_eligible': True,
    }
    item['opportunity_evidence'] = opportunity.assess(
        KEYWORD, TOPIC, INTENT, provider, results,
        review() if proposed_review is None else proposed_review, checked_at,
    )
    return item


def rejection(item, reason=None):
    problems = opportunity.issues(item, NOW)
    assert isinstance(problems, list)
    assert problems, 'Unverified evidence must not authorize automatic publication'
    if reason is not None:
        assert reason in problems


@pytest.mark.parametrize('provider', ['google_custom_search', 'duckduckgo_proxy'])
def test_verified_sample_and_two_independent_quotes_allow_unknown_trend(provider):
    item = candidate(provider=provider)
    evidence = item['opportunity_evidence']
    assert evidence['result_count'] == 5
    assert evidence['domain_count'] == 3
    assert evidence['dominant_ratio'] == 0
    assert item['trend_growth'] is None
    assert opportunity.issues(item, NOW) == []


def test_measured_zero_trend_does_not_change_opportunity_eligibility():
    item = candidate()
    item['trend_growth'] = 0.0
    assert opportunity.issues(item, NOW) == []


@pytest.mark.parametrize('mode', ['official_pages', '', None])
def test_official_sources_alone_cannot_replace_observed_search_results(mode):
    item = candidate()
    item['evidence_mode'] = mode
    rejection(item, 'organic_results_unavailable')


@pytest.mark.parametrize('results', [[], search_rows()[:4], [search_rows()[0]] * 5])
def test_empty_small_or_repeated_samples_cannot_pass(results):
    rejection(candidate(results=results), 'insufficient_search_sample')


def test_five_urls_from_only_two_domains_do_not_prove_enough_coverage():
    rows = search_rows()
    rows[3].update(url='https://alpha.example/guide/3', domain='alpha.example')
    rejection(candidate(results=rows), 'insufficient_search_sample')


def test_fragment_variants_and_trailing_slash_do_not_multiply_a_result():
    rows = search_rows()[:3]
    rows.extend([
        {**rows[0], 'url': rows[0]['url'] + '#section'},
        {**rows[1], 'url': rows[1]['url'] + '/'},
    ])
    assert len(opportunity.sample_rows(rows)) == 3
    rejection(candidate(results=rows), 'insufficient_search_sample')


@pytest.mark.parametrize('dominant_count,allowed', [(3, True), (4, False)])
def test_dominant_result_boundary_counts_positions_not_unique_hosts(dominant_count, allowed):
    rows = search_rows()
    for index in range(dominant_count):
        domain = f'public{index}.go.kr'
        rows[index].update(url=f'https://{domain}/guide', domain=domain)
    item = candidate(results=rows)
    assert item['opportunity_evidence']['dominant_ratio'] == dominant_count / 5
    if allowed:
        assert opportunity.issues(item, NOW) == []
    else:
        rejection(item, 'dominant_search_results')


@pytest.mark.parametrize('matches', [
    [],
    [{'result_index': 0, 'quote': 'ITQ 자격증 조회와 취득 내역 확인'}],
    [{'result_index': 0, 'quote': 'ITQ 자격증 조회와 취득 내역 확인'},
     {'result_index': 2, 'quote': 'ITQ 자격증 조회와 취득 내역 확인'}],
    [{'result_index': 0, 'quote': '검색 결과에는 없는 장기 미접속 계정 복구'},
     {'result_index': 1, 'quote': '취득한 ITQ 자격증과 성적 정보를 조회하는 경로'}],
    [{'result_index': 0, 'quote': 'ITQ'},
     {'result_index': 1, 'quote': '취득한 ITQ 자격증과 성적 정보를 조회하는 경로'}],
    [{'result_index': -1, 'quote': 'ITQ 자격증 조회와 취득 내역 확인'},
     {'result_index': 1, 'quote': '취득한 ITQ 자격증과 성적 정보를 조회하는 경로'}],
    [{'result_index': 99, 'quote': 'ITQ 자격증 조회와 취득 내역 확인'},
     {'result_index': 1, 'quote': '취득한 ITQ 자격증과 성적 정보를 조회하는 경로'}],
    [{'result_index': True, 'quote': 'ITQ 자격증 조회와 취득 내역 확인'},
     {'result_index': 0, 'quote': '취득한 ITQ 자격증과 성적 정보를 조회하는 경로'}],
])
def test_intent_needs_actual_quotes_from_two_different_domains(matches):
    proposal = review()
    proposal['matches'] = matches
    rejection(candidate(proposed_review=proposal), 'unverified_intent_quotes')


def test_quote_matching_tolerates_presentation_whitespace_and_html_entities():
    rows = search_rows()
    rows[0]['title'] = 'ITQ&nbsp;자격증 조회와 취득 내역 확인 안내'
    proposal = review()
    proposal['matches'][0]['quote'] = 'ITQ자격증조회와\n취득내역확인'
    assert opportunity.issues(candidate(results=rows, proposed_review=proposal), NOW) == []


def test_discarded_result_does_not_shift_original_evidence_indices():
    rows = [{'url': 'https://ignored.example', 'domain': 'ignored.example',
             'title': '', 'snippet': ''}, *search_rows()]
    proposal = review()
    proposal['matches'][0]['result_index'] = 1
    proposal['matches'][1]['result_index'] = 2
    assert opportunity.issues(candidate(results=rows, proposed_review=proposal), NOW) == []


@pytest.mark.parametrize('change', [
    {'scope': 'narrower_intent'},
    {'scope': None},
    {'target_keyword': 'ITQ장기미접속로그인오류'},
    {'target_keyword': '2027ITQ자격증조회'},
])
def test_broad_keyword_demand_cannot_be_assigned_to_another_or_narrower_intent(change):
    proposal = {**review(), **change}
    rejection(candidate(proposed_review=proposal), 'narrower_or_unverified_search_intent')


def test_same_target_keyword_with_display_spacing_remains_valid():
    proposal = {**review(), 'target_keyword': 'itq 자격증 조회'}
    assert opportunity.issues(candidate(proposed_review=proposal), NOW) == []


@pytest.mark.parametrize('field,value', [
    ('keyword', 'ITQ자격증발급'),
    ('topic', 'ITQ자격증조회: 장기 미접속 로그인 실패 해결'),
    ('intent', '장기 미접속 계정을 어떻게 다시 만드나요?'),
])
def test_cached_evidence_cannot_follow_a_changed_keyword_title_or_intent(field, value):
    item = candidate()
    item[field] = value
    rejection(item, 'search_evidence_binding_mismatch')


@pytest.mark.parametrize('offset,allowed', [
    (timedelta(hours=36), True),
    (timedelta(hours=36, microseconds=1), False),
    (timedelta(seconds=-1), False),
])
def test_search_sample_age_has_an_exact_36_hour_boundary(offset, allowed):
    item = candidate(checked_at=(NOW - offset).isoformat())
    if allowed:
        assert opportunity.issues(item, NOW) == []
    else:
        rejection(item, 'stale_search_sample')


@pytest.mark.parametrize('timestamp', ['', 'not-a-date', None, True, [], {}, '2026-09-10T08:00:00'])
def test_malformed_or_naive_timestamp_is_rejected_without_exception(timestamp):
    rejection(candidate(checked_at=timestamp), 'stale_search_sample')


def test_selection_timestamp_cannot_be_renewed_without_search_evidence():
    item = candidate()
    item['selected_at'] = (NOW - timedelta(minutes=1)).isoformat()
    rejection(item, 'stale_search_sample')


@pytest.mark.parametrize('version', [None, 0, -1, 2, '1', True, [], {}])
def test_old_missing_or_malformed_evidence_version_is_not_reusable(version):
    item = candidate()
    item['opportunity_evidence']['version'] = version
    rejection(item, 'missing_opportunity_evidence')


@pytest.mark.parametrize('field,value', [
    ('result_count', 100), ('domain_count', 100), ('dominant_ratio', 0.9),
    ('result_count', []), ('domain_count', {}), ('dominant_ratio', True),
])
def test_stored_counters_do_not_override_recomputed_evidence(field, value):
    item = candidate()
    item['opportunity_evidence'][field] = value
    rejection(item, 'search_sample_changed')


def test_changed_result_content_invalidates_quotes_even_when_counts_stay_the_same():
    item = candidate()
    item['organic_results'][0]['title'] = '관련 없는 소식'
    item['organic_results'][0]['snippet'] = '이 문서는 해당 조회 절차를 설명하지 않습니다.'
    rejection(item, 'unverified_intent_quotes')


def test_true_publication_flag_cannot_bypass_missing_evidence():
    item = candidate()
    del item['opportunity_evidence']
    item['publish_eligible'] = True
    item['hold_reasons'] = []
    rejection(item, 'missing_opportunity_evidence')


def test_true_publication_flag_cannot_bypass_an_official_only_sample():
    item = candidate(results=[])
    item.update(publish_eligible=True, hold_reasons=[], evidence_mode='official_pages')
    rejection(item, 'organic_results_unavailable')


@pytest.mark.parametrize('value', [None, [], {}, True, 0, 'not-a-result-list'])
def test_malformed_result_collection_is_rejected_without_exception(value):
    item = candidate()
    item['organic_results'] = value
    rejection(item, 'insufficient_search_sample')


@pytest.mark.parametrize('value', [None, [], {}, True, 1])
def test_malformed_url_is_discarded_without_interrupting_review(value):
    rows = search_rows()
    rows[0]['url'] = value
    rejection(candidate(results=rows), 'insufficient_search_sample')


@pytest.mark.parametrize('value', [None, [], {}, True, 1, 'unknown_search', 'naver_web_search'])
def test_malformed_or_unknown_provider_is_rejected_without_exception(value):
    rejection(candidate(provider=value), 'organic_results_unavailable')


@pytest.mark.parametrize('value', [None, [], {}, True, 1, 'invalid'])
def test_nonobject_or_empty_candidate_is_rejected_without_exception(value):
    rejection(value)


@pytest.mark.parametrize('value', [None, [], True, 1, 'invalid'])
def test_malformed_review_does_not_supply_verified_intent(value):
    evidence = opportunity.assess(KEYWORD, TOPIC, INTENT, 'google_custom_search',
                                  search_rows(), value, NOW.isoformat())
    item = candidate()
    item['opportunity_evidence'] = evidence
    rejection(item, 'unverified_intent_quotes')


@pytest.mark.parametrize('value', [None, [], {}, True])
def test_malformed_matches_are_not_verified_quotes(value):
    proposal = review()
    proposal['matches'] = value
    rejection(candidate(proposed_review=proposal), 'unverified_intent_quotes')


def test_invalid_match_shapes_are_skipped_and_two_valid_quotes_survive():
    proposal = review()
    proposal['matches'] = [None, [], True, {'result_index': [], 'quote': {}},
                           *deepcopy(proposal['matches'])]
    assert opportunity.issues(candidate(proposed_review=proposal), NOW) == []


ANSWER = '취득한 자격과 성적 정보는 자격취득현황에서 조회할 수 있습니다.'
ARTICLE = (
    '<article class="wpab-article"><div id="quick-answer"><p>' + ANSWER + '</p></div>'
    '<h2>자격증 조회 순서</h2><p>로그인한 뒤 My자격 메뉴에서 자격취득현황을 선택합니다.</p>'
    '<h2>조회되지 않을 때</h2><p>취득 내역을 확인할 수 없다면 고객센터에 문의합니다.</p></article>'
)
HELD_ARTICLE = '최종 글이 검증된 검색어의 주된 질문에 답하는지 확인되지 않음'


@pytest.fixture
def approved_article_brief(monkeypatch):
    # Freeze only time. The real sample, quote, binding and age gates still run.
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW if tz is not None else NOW.replace(tzinfo=None)

    monkeypatch.setattr(opportunity, 'datetime', FrozenDateTime)
    return candidate()


def article_response(*, covers=True, quote=ANSWER):
    return json.dumps({'covers_primary_intent': covers, 'answer_quote': quote}, ensure_ascii=False)


def test_final_article_review_uses_approved_scope_and_accepts_a_real_body_quote(approved_article_brief):
    """LLM agreement is mocked; this tests the gate contract, not semantic accuracy."""
    model = Mock(return_value=article_response())
    assert opportunity.review_article(TOPIC, ARTICLE, '취득 내역 조회 방법',
                                      approved_article_brief, model) == []
    model.assert_called_once()
    prompt = model.call_args.args[0]
    assert KEYWORD in prompt and TOPIC in prompt and INTENT in prompt
    assert ANSWER in prompt
    assert '제목과 본문의 중심' in prompt
    assert 'FAQ 한 줄' in prompt


def test_narrow_login_only_article_stays_held_when_scope_reviewer_rejects_it(approved_article_brief):
    # Whether this answer is too narrow belongs to the model. False must be enforced
    # even though the keyword is in the title and its answer_quote exists in the body.
    narrow = '장기 미접속으로 로그인할 수 없으면 계정을 다시 가입합니다.'
    model = Mock(return_value=article_response(covers=False, quote=narrow))
    issues = opportunity.review_article(
        'ITQ자격증조회: 장기 미접속 로그인 오류 해결', '<p>' + narrow + '</p>',
        '장기 미접속 계정 해결', approved_article_brief, model)
    assert issues == [HELD_ARTICLE]
    model.assert_called_once()


@pytest.mark.parametrize('quote', ['본문에 없는 자격증 조회 안내 문구입니다.', '조회', '', None, [], True])
def test_model_true_cannot_replace_a_substantive_existing_body_quote(approved_article_brief, quote):
    model = Mock(return_value=article_response(quote=quote))
    assert opportunity.review_article(TOPIC, ARTICLE, '', approved_article_brief, model) == [HELD_ARTICLE]
    model.assert_called_once()


@pytest.mark.parametrize('location', ['title', 'description'])
def test_quote_present_only_in_title_or_description_cannot_prove_body_coverage(approved_article_brief, location):
    title = ANSWER if location == 'title' else TOPIC
    description = ANSWER if location == 'description' else ''
    model = Mock(return_value=article_response())
    html = '<article><p>이 본문은 로그인 오류에 관한 짧은 설명만 제공합니다.</p></article>'
    assert opportunity.review_article(title, html, description, approved_article_brief, model) == [HELD_ARTICLE]


@pytest.mark.parametrize('heading', ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
def test_heading_alone_is_not_a_substantive_answer_quote(approved_article_brief, heading):
    model = Mock(return_value=article_response())
    html = ('<article><' + heading + '>' + ANSWER + '</' + heading + '>'
            '<p>실제 설명은 로그인 문제만 짧게 다룹니다.</p></article>')
    assert opportunity.review_article(TOPIC, html, '', approved_article_brief, model) == [HELD_ARTICLE]
    # Headings still provide context for the model; they cannot prove body coverage.
    assert ANSWER in model.call_args.args[0]


@pytest.mark.parametrize('outside_body', [
    '<nav>{}</nav>', '<footer>{}</footer>', '<script type="application/ld+json">{}</script>',
    '<style>{}</style>', '<section id="verified-sources">{}</section>',
    '<aside class="wpab-related">{}</aside>', '<div class="wpab-ad">{}</div>',
])
def test_navigation_sources_related_ads_and_code_cannot_supply_answer_quote(approved_article_brief, outside_body):
    model = Mock(return_value=article_response())
    html = ('<article><p>실제 본문은 로그인 문제만 설명합니다.</p>'
            + outside_body.format(ANSWER) + '</article>')
    assert opportunity.review_article(TOPIC, html, '', approved_article_brief, model) == [HELD_ARTICLE]
    prompt = model.call_args.args[0]
    assert ANSWER not in prompt


def test_visible_body_quote_is_accepted_with_markup_spacing_and_entities(approved_article_brief):
    html = ARTICLE.replace(ANSWER, '취득한&nbsp;자격과 <strong>성적 정보는</strong> 자격취득현황에서 조회할 수 있습니다.')
    model = Mock(return_value='```json\n' + article_response() + '\n```')
    assert opportunity.review_article(TOPIC, html, '', approved_article_brief, model) == []


@pytest.mark.parametrize('raw', [
    None, True, [], {}, '', 'not-json', '[]', 'true', 'null', '{}',
    '{"covers_primary_intent": "true", "answer_quote": "실제 인용이 있어도 문자열 true는 금지"}',
])
def test_malformed_model_response_fails_closed_without_another_call(approved_article_brief, raw):
    model = Mock(return_value=raw)
    assert opportunity.review_article(TOPIC, ARTICLE, '', approved_article_brief, model) == [HELD_ARTICLE]
    model.assert_called_once()


@pytest.mark.parametrize('mode', ['exception', 'invalid_response', 'invented_quote'])
def test_provider_errors_and_model_output_are_never_exposed(approved_article_brief, capsys, caplog, mode):
    secret = 'secret-token=private-value https://private.example/api?key=private-value'
    model = (Mock(side_effect=RuntimeError(secret)) if mode == 'exception' else
             Mock(return_value=secret if mode == 'invalid_response' else article_response(quote=secret)))
    assert opportunity.review_article(TOPIC, ARTICLE, '', approved_article_brief, model) == [HELD_ARTICLE]
    output = capsys.readouterr()
    assert secret not in output.out + output.err + caplog.text
    model.assert_called_once()


@pytest.mark.parametrize('offset', [timedelta(hours=36, seconds=1), timedelta(seconds=-1)])
def test_stale_or_future_approved_evidence_prevents_article_model_call(approved_article_brief, offset):
    stamp = (NOW - offset).isoformat()
    approved_article_brief['selected_at'] = stamp
    approved_article_brief['opportunity_evidence']['checked_at'] = stamp
    model = Mock(side_effect=AssertionError('Stale evidence must not reach the model'))
    issues = opportunity.review_article(TOPIC, ARTICLE, '', approved_article_brief, model)
    assert issues == ['검색 의도 검수 입력이 유효하지 않음']
    model.assert_not_called()


@pytest.mark.parametrize('html', ['', '<nav>본문이 아닌 메뉴 문구입니다.</nav>', '가' * 100_001])
def test_empty_or_oversized_substantive_body_prevents_model_call(approved_article_brief, html):
    model = Mock(side_effect=AssertionError('Invalid body must not reach the model'))
    assert opportunity.review_article(TOPIC, html, '', approved_article_brief, model) == ['검색 의도 검수 본문이 없거나 너무 큼']
    model.assert_not_called()


@pytest.mark.parametrize('field', ['title', 'html', 'description'])
@pytest.mark.parametrize('value', [None, [], {}, True])
def test_malformed_article_fields_prevent_model_call(approved_article_brief, field, value):
    values = {'title': TOPIC, 'html': ARTICLE, 'description': '자격증 조회 안내'}
    values[field] = value
    model = Mock(side_effect=AssertionError('Malformed article must not reach the model'))
    assert opportunity.review_article(**values, brief=approved_article_brief, call_llm=model) == ['검색 의도 검수 입력이 유효하지 않음']
    model.assert_not_called()
