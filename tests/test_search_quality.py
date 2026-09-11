"""All semantic answers are mocks; URL/site/quote/count decisions execute real code."""
from copy import deepcopy
import json
from unittest.mock import Mock

import pytest

from src import search_quality as quality

KEYWORD = '대장내시경비용'
PROVIDER = 'codex_native_search'
STAMP = '2026-09-11T00:00:00+00:00'


def rows(n=5):
    return [{'url': f'https://site{i % 3}.example/article/{i}', 'domain': f'site{i % 3}.example',
             'title': f'대장내시경 비용과 예약 전 확인 사항 {i}',
             'snippet': '일반 검사와 수면 검사 비용의 차이와 확인할 항목을 안내합니다.'}
            for i in range(n)]


def decisions(results, positives=None):
    return [{'result_index': i, 'relevant': positives is None or i in positives, 'quote': row['title']}
            for i, row in quality.raw_rows(results)]


def review(results, positives=None):
    model = Mock(return_value={'decisions': decisions(results, positives)})
    result = quality.review_search(KEYWORD, PROVIDER, results, STAMP, model)
    return result, model


def problems(results, bound):
    return quality.quality_issues(KEYWORD, PROVIDER, results, STAMP, bound)


def metrics(results, bound):
    return quality.search_metrics(KEYWORD, PROVIDER, results, STAMP, bound)


def test_all_rows_reviewed_once_and_metrics_are_recomputed():
    original = rows()
    bound, model = review(original)
    model.assert_called_once()
    prompt = model.call_args.args[0]
    assert all(f'"result_index": {i}' in prompt for i in range(5))
    assert '도구·웹검색·파일을 사용하지 말고' in prompt
    assert problems(original, bound) == []
    assert metrics(original, bound) == {
        'raw_result_count': 5, 'canonical_result_count': 5,
        'relevant_result_count': 5, 'relevant_site_count': 3,
        'relevant_indices': list(range(5)), 'relevance_ratio': 1.0,
        'duplicate_ratio': 0.0, 'known_dominant_ratio': 0.0,
        'site_concentration': 0.4, 'organic_opportunity': 24.0,
    }
    bound['organic_opportunity'] = 100
    assert metrics(original, bound)['organic_opportunity'] == 24.0


@pytest.mark.parametrize('positive_count,allowed', [(2, False), (5, False), (6, True), (10, True)])
def test_all_raw_positions_remain_in_relevance_denominator(positive_count, allowed):
    results = rows(10)
    bound, _ = review(results, set(range(positive_count)))
    issues = problems(results, bound)
    assert (not issues) is allowed
    if not allowed:
        assert 'low_search_relevance' in issues
        with pytest.raises(RuntimeError):
            metrics(results, bound)
    if positive_count == 2:
        assert 'insufficient_relevant_results' in issues


def test_health_audit_seven_results_from_one_site_family_is_held():
    results = rows(10)
    for i in range(7):
        host = 'price.hospitalk.net' if i in (0, 6) else 'www.price.hospitalk.net'
        results[i].update(url=f'https://{host}/cost/{0 if i == 1 else i}', domain=host)
    bound, _ = review(results)
    issues, measured = quality.validation(KEYWORD, PROVIDER, results, STAMP, bound)
    assert measured['known_dominant_ratio'] == 0
    assert measured['canonical_result_count'] == 9
    assert measured['site_concentration'] == 6 / 9
    assert measured['relevance_ratio'] == 0.9
    assert 'concentrated_search_results' in issues
    with pytest.raises(RuntimeError, match='concentrated_search_results'):
        metrics(results, bound)


@pytest.mark.parametrize('family_count,allowed', [(3, True), (4, False)])
def test_site_concentration_half_is_allowed_above_half_is_not(family_count, allowed):
    results = rows(6)
    for i in range(6):
        host = f'part{i}.same-company.com' if i < family_count else f'other{i}.example'
        results[i].update(url=f'https://{host}/article/{i}', domain=host)
    bound, _ = review(results)
    assert (not problems(results, bound)) is allowed
    if not allowed:
        assert 'concentrated_search_results' in problems(results, bound)


def test_www_fragment_and_scheme_clones_never_supply_extra_positive_urls():
    results = rows()
    results.extend([{**results[0], 'url': 'http://www.site0.example/article/0/#part', 'domain': 'www.site0.example'}] * 5)
    bound, _ = review(results)
    issues, measured = quality.validation(KEYWORD, PROVIDER, results, STAMP, bound)
    assert measured['relevant_result_count'] == 5
    assert measured['relevance_ratio'] == 0.5
    assert measured['duplicate_ratio'] == 0.5
    assert 'low_search_relevance' in issues


def test_duplicate_alias_cannot_disagree_about_relevance():
    results = rows()
    results.append({**results[0], 'url': 'https://www.site0.example/article/0', 'domain': 'www.site0.example'})
    model = Mock(return_value={'decisions': decisions(results, set(range(5)))})
    with pytest.raises(RuntimeError, match='conflicting_duplicate_review'):
        quality.review_search(KEYWORD, PROVIDER, results, STAMP, model)
    model.assert_called_once()


@pytest.mark.parametrize('left,right,same', [
    ('www.price.hospitalk.net', 'price.hospitalk.net', True),
    ('news.corporation.co.kr', 'jobs.corporation.co.kr', True),
    ('portal.nts.go.kr', 'www.nts.go.kr', True),
    ('alpha.blogspot.com', 'beta.blogspot.com', False),
    ('alpha.github.io', 'beta.github.io', False),
    ('alice.tistory.com', 'bob.tistory.com', False),
    ('img.alice.tistory.com', 'alice.tistory.com', True),
    ('alpha.example', 'beta.example', False),
    ('www.alpha.example', 'alpha.example', True),
])
def test_registered_domain_and_hosted_tenant_identity(left, right, same):
    assert (quality.site_identity(left) == quality.site_identity(right)) is same


def test_bundled_psl_never_downloads_or_uses_disk_cache(monkeypatch):
    import requests
    import tldextract
    real = tldextract.TLDExtract
    calls = []
    monkeypatch.setattr(requests.Session, 'get', Mock(side_effect=AssertionError('network forbidden')))

    def construct(**kwargs):
        calls.append(kwargs)
        return real(**kwargs)

    monkeypatch.setattr(tldextract, 'TLDExtract', construct)
    quality._extractor.cache_clear()
    try:
        assert quality.site_identity('alpha.blogspot.com') == 'alpha.blogspot.com'
        assert calls == [{'suffix_list_urls': (), 'cache_dir': None,
                          'fallback_to_snapshot': True, 'include_psl_private_domains': True}]
    finally:
        quality._extractor.cache_clear()


@pytest.mark.parametrize('change', [
    lambda ds: ds.pop(),
    lambda ds: ds.append(ds[0]),
    lambda ds: ds.__setitem__(1, ds[0]),
    lambda ds: ds[0].update(result_index=True),
    lambda ds: ds[0].update(result_index=99),
    lambda ds: ds[0].update(result_index=0.0),
    lambda ds: ds[0].update(relevant='true'),
    lambda ds: ds[0].update(relevant=1),
    lambda ds: ds[0].update(quote='짧음'),
    lambda ds: ds[0].update(quote='실제로 존재하지 않는 모델의 의견입니다'),
    lambda ds: ds[0].update(quote=None),
    lambda ds: ds.__setitem__(0, None),
])
def test_missing_or_malformed_row_decisions_never_return_a_verified_review(change):
    results = rows()
    ds = decisions(results)
    change(ds)
    model = Mock(return_value={'decisions': ds})
    with pytest.raises(RuntimeError):
        quality.review_search(KEYWORD, PROVIDER, results, STAMP, model)
    model.assert_called_once()


@pytest.mark.parametrize('response', [None, [], True, {'decisions': None}, 'not-json',
                                      '{"decisions": true}', 'private-model-response'])
def test_invalid_model_shapes_never_escape_as_raw_errors(response):
    with pytest.raises(RuntimeError) as caught:
        quality.review_search(KEYWORD, PROVIDER, rows(), STAMP, Mock(return_value=response))
    assert 'private-' not in str(caught.value)


def test_model_exception_is_fixed_and_not_retried():
    model = Mock(side_effect=RuntimeError('private-token-value'))
    with pytest.raises(RuntimeError, match='model_review_failed') as caught:
        quality.review_search(KEYWORD, PROVIDER, rows(), STAMP, model)
    assert 'private-token-value' not in str(caught.value)
    assert caught.value.__suppress_context__
    model.assert_called_once()


@pytest.mark.parametrize('change', [
    lambda x: x[0].update(title='변경된 제목입니다'),
    lambda x: x[0].update(snippet='변경된 본문 발췌입니다'),
    lambda x: x[0].update(url='https://changed.example/article'),
    lambda x: x.reverse(),
])
def test_raw_result_changes_invalidate_cached_relevance(change):
    results = rows()
    bound, _ = review(results)
    change(results)
    assert problems(results, bound) == ['search_review_binding_mismatch']


@pytest.mark.parametrize('field,value', [('query', 'CT비용'), ('provider', 'google_custom_search'),
                                      ('checked_at', '2026-09-12T00:00:00+00:00'), ('raw_sha256', 'forged')])
def test_review_bindings_cannot_be_transplanted(field, value):
    results = rows()
    bound, _ = review(results)
    bound[field] = value
    assert problems(results, bound) == ['search_review_binding_mismatch']


@pytest.mark.parametrize('bad', [None, [], {}, True, {'version': 0}, {'version': True}])
def test_missing_or_old_review_is_held(bad):
    assert problems(rows(), bad) == ['missing_search_review']


def test_malformed_raw_slots_are_not_silently_removed_from_denominator():
    results = [None, {}, True, {'url': 'javascript:alert(1)'}, {'title': []}, *rows()]
    bound, model = review(results)
    assert [d['result_index'] for d in bound['decisions']] == list(range(5, 10))
    assert 'low_search_relevance' in problems(results, bound)
    assert metrics_for_diagnostics(results, bound)['raw_result_count'] == 10
    model.assert_called_once()


def metrics_for_diagnostics(results, bound):
    return quality.validation(KEYWORD, PROVIDER, results, STAMP, bound)[1]


def test_first_ten_only_no_backfill_or_mutation():
    results = [None] * 6 + rows(10)
    before = deepcopy(results)
    bound, _ = review(results)
    assert results == before
    assert len(bound['decisions']) == 4
    assert 'insufficient_relevant_results' in problems(results, bound)
    results[10]['title'] = 'outside first ten is outside the binding'
    assert 'search_review_binding_mismatch' not in problems(results, bound)


def test_json_text_and_presentation_whitespace_are_supported():
    results = rows()
    ds = decisions(results)
    ds[0]['quote'] = ds[0]['quote'].replace(' ', '\n')
    model = Mock(return_value='```json\n' + json.dumps({'decisions': ds}) + '\n```')
    bound = quality.review_search(KEYWORD, PROVIDER, results, STAMP, model)
    assert problems(results, bound) == []


@pytest.mark.parametrize('field,value', [('keyword', ''), ('keyword', {}), ('provider', []),
                                      ('provider', 'model_answer'), ('checked_at', None),
                                      ('checked_at', 'not-a-date'), ('checked_at', '2026-09-11T00:00:00')])
def test_invalid_input_never_calls_the_model(field, value):
    kwargs = {'keyword': KEYWORD, 'provider': PROVIDER, 'results': rows(), 'checked_at': STAMP}
    kwargs[field] = value
    model = Mock()
    with pytest.raises(RuntimeError, match='invalid_search_input'):
        quality.review_search(**kwargs, call_llm=model)
    model.assert_not_called()


@pytest.mark.parametrize('count,allowed', [(3, True), (4, False)])
def test_known_dominant_ratio_still_applies_to_relevant_results(count, allowed):
    results = rows()
    for i in range(count):
        host = f'authority{i}.go.kr'
        results[i].update(url=f'https://{host}/guide', domain=host)
    bound, _ = review(results)
    assert (not problems(results, bound)) is allowed
    if not allowed:
        assert 'dominant_search_results' in problems(results, bound)


def test_empty_input_is_a_bound_hold_without_a_model_call():
    bound, model = review([])
    assert 'insufficient_relevant_results' in problems([], bound)
    model.assert_not_called()


@pytest.mark.parametrize('results', [None, {}, True, 'not a list'])
def test_non_list_input_cannot_supply_a_review(results):
    model = Mock()
    with pytest.raises(RuntimeError, match='invalid_search_input'):
        quality.review_search(KEYWORD, PROVIDER, results, STAMP, model)
    model.assert_not_called()
