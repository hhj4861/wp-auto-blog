"""New discovery inputs must remain subject to exact demand and full evidence gates."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from unittest.mock import Mock

import pytest
import yaml

from src import market_topics as market, review_discovery as review, review_exploration as explore
from src.analysis_runtime import AnalysisError
from tests.test_market_topics import isolated_market_history as isolated_market_history
from tests.test_review_replenishment import install_refills
from tests.test_selection_feedback import install_selection

REAL_PROPOSE = explore.propose


@pytest.mark.parametrize('key,products,facet', [
    ('SSD1TB', ['저장장치'], '용량'), ('외장SSD2TB', ['저장장치'], '용량'),
    ('1테라외장하드', ['저장장치'], '용량'), ('DDR416GB', ['램'], '용량'),
    ('17인치노트북', ['노트북'], '화면크기'), ('32인치모니터', ['모니터'], '화면크기'),
])
def test_previously_pruned_concrete_products_enter_only_research(key, products, facet):
    assert review.requirements(key)[0] == products
    assert facet in review.requirements(key)[1]
    assert review.discovery_issue(key) is None


@pytest.mark.parametrize('key', ['SSD', '삼성SSD', 'RAM', '램', '무선청소기', '미세먼지', 'SSD추천'])
def test_broad_or_unbounded_queries_stay_out(key):
    assert review.discovery_issue(key)


def source(body, title='제품 사양'):
    return {'url': 'https://www.samsung.com/sec/spec', 'title': title, 'excerpt': body,
            'sha256': sha256(body.encode()).hexdigest()}


@pytest.mark.parametrize('key,body,accepted', [
    ('SSD1TB', 'SSD capacity 1 TB NVMe', True), ('SSD1TB', 'SSD capacity 2 TB NVMe', False),
    ('SSD1TB', 'SSD capacity 11 TB', False), ('SSD1TB', 'SSD endurance 1 TBW capacity 500 GB', False),
    ('외장SSD2TB', 'External SSD capacity 2TB', True),
    ('17인치노트북', '노트북 17인치 화면 상세', True),
    ('17인치노트북', '노트북 16인치 화면 상세', False),
    ('DDR416GB', 'DDR4 memory 16 GB', True), ('DDR416GB', 'DDR4 memory 8 GB', False),
    ('DDR416GB', 'DDR5 memory 16 GB', False),
    ('DDR416G', 'DDR4 memory 16 GB', True), ('DDR416G', 'DDR4 memory 8 GB', False),
])
def test_fetched_body_must_support_requested_constraint(key, body, accepted):
    assert review.relevant_source(key, source(body, title=key)) is accepted


def test_ddr_generation_is_not_part_of_capacity():
    assert review.numeric_constraints('DDR416GB')['capacity'] == {('16', 'gb')}


def stats(*keys):
    return {key: {'keyword': key, 'monthly': 5000} for key in keys}


def test_question_proposals_are_only_unmeasured_hints():
    model = Mock(return_value={'questions': [
        {'anchor': '노트북', 'seed': '노트북17인치무게'},
        {'anchor': 'SSD', 'seed': 'SSD1TB호환'},
        {'anchor': 'SSD', 'seed': 'SSD2TB호환'},
        {'anchor': '모니터', 'seed': '모니터32인치'}]})
    seeds, audit = REAL_PROPOSE(stats('노트북', 'SSD', '모니터'), [], model)
    assert seeds == ['노트북17인치무게', 'SSD1TB호환', '모니터32인치']
    assert all(row['status'] == 'unmeasured' for row in audit['seeds'])
    assert audit['measured'] == [] and model.call_count == 1
    assert 'monthly' not in json.dumps(audit)


@pytest.mark.parametrize('entry', [None, {}, {'anchor': [], 'seed': []},
    {'anchor': 'invented', 'seed': 'SSD1TB'}, {'anchor': 'SSD', 'seed': '모니터32인치'},
    {'anchor': 'SSD', 'seed': 'SSD추천'}, {'anchor': 'SSD', 'seed': 'SSD1TB site:evil.com'},
    {'anchor': 'SSD', 'seed': 'SSD1TB;private'}, {'anchor': 'SSD', 'seed': 'SSD1TB'}])
def test_ungrounded_unsafe_or_excluded_proposals_do_not_get_measured(entry):
    seeds, _ = REAL_PROPOSE(stats('SSD'), ['SSD1TB'], lambda _: {'questions': [entry]})
    assert seeds == []


def test_no_measured_subjects_no_model_and_fatal_error_not_hidden():
    model = Mock()
    assert REAL_PROPOSE(stats('미세먼지'), [], model)[0] == []
    model.assert_not_called()
    model.side_effect = AnalysisError('unauthorized')
    with pytest.raises(AnalysisError):
        REAL_PROPOSE(stats('SSD'), [], model)


@pytest.mark.parametrize('response', [None, [], {}, {'questions': None}])
def test_invalid_response_does_not_force_candidates(response):
    seeds, audit = REAL_PROPOSE(stats('SSD'), [], lambda _: response)
    assert seeds == [] and audit['status'] == 'invalid_response'


def test_explorer_error_is_redacted():
    _, audit = REAL_PROPOSE(stats('SSD'), [], Mock(side_effect=RuntimeError('private-secret')))
    assert audit['status'] == 'analysis_unavailable' and 'private-secret' not in json.dumps(audit)


def test_new_capacity_candidate_reaches_independent_queue_gates(monkeypatch):
    key = 'SSD1TB'
    measured, search, offered = install_selection(monkeypatch, [key], passing=[key])
    report = market.select_category('리뷰', 1, [])
    assert offered[0] == [key] and search.call_count == 1
    assert report['selected'][0]['monthly_search'] == measured[key]['monthly']
    assert market.fresh_market_item(report['selected'][0], '리뷰')
    assert market.enqueue_report([], report)[0]['keyword'] == key


@pytest.mark.parametrize('passing', [True, False])
def test_adaptive_refill_measures_exact_demand_and_retains_verdicts(monkeypatch, passing):
    anchor, question = 'SSD', 'SSD1TB호환'
    all_stats, search, _, demand = install_refills(monkeypatch, [anchor], [],
        passing=[question] if passing else [])
    # Install the external boundary for the new key, then keep the actual refill.
    measured, search, _ = install_selection(monkeypatch, [anchor, question],
        passing=[question] if passing else [])
    demand = Mock(side_effect=[{anchor: measured[anchor]}, {question: measured[question]}])
    monkeypatch.setattr(market, 'demand_candidates', demand)
    monkeypatch.setattr(explore, 'propose', lambda *a: ([question],
        {'status': 'proposed', 'seeds': [{'seed': question, 'status': 'unmeasured'}], 'measured': []}))
    report = market.select_category('리뷰', 1, [])
    assert demand.call_args_list[1].args == ([question],)
    assert demand.call_count == 2 and search.call_count == 1
    assert report['review_question_discovery']['seeds'][0]['status'] == 'lookup_completed'
    if passing:
        assert report['selected'][0]['monthly_search'] == measured[question]['monthly']
        assert market.enqueue_report([], report)[0]['keyword'] == question
    else:
        assert report['selected'] == []
        with pytest.raises(RuntimeError): market.enqueue_report([], report)


def test_demand_probe_workflow_cannot_run_model_or_publication_jobs():
    from pathlib import Path
    data = yaml.load(Path('.github/workflows/blog-keyword-select.yml').read_text(), Loader=yaml.BaseLoader)
    jobs = data['jobs']
    assert jobs['demand-check']['permissions'] == {'contents': 'read'}
    for name, job in jobs.items():
        if name != 'demand-check': assert 'inputs.demand_check_only != true' in job['if']
    env = [step['env'] for step in jobs['demand-check']['steps'] if 'env' in step]
    assert len(env) == 1 and set(env[0]) == {'NAVER_AD_CUSTOMER_ID','NAVER_AD_API_KEY','NAVER_AD_SECRET_KEY'}


def test_memory_source_domains_respect_named_brand():
    assert review.preferred_source_domains('삼성DDR416GB') == ['semiconductor.samsung.com']
    assert review.preferred_source_domains('킹스톤DDR416GB') == ['kingston.com']


@pytest.mark.parametrize('outcome', ['below_floor', 'empty', 'lookup_failure'])
def test_adaptive_refill_cannot_borrow_volume_or_loop_after_failure(monkeypatch, outcome):
    real_demand = market.demand_candidates
    install_refills(monkeypatch, [], [])
    for name in ('NAVER_AD_CUSTOMER_ID', 'NAVER_AD_API_KEY', 'NAVER_AD_SECRET_KEY'):
        monkeypatch.setenv(name, 'test-only')
    proposal = Mock(return_value=(['SSD1TB'], {'status': 'proposed',
        'seeds': [{'seed': 'SSD1TB', 'status': 'unmeasured'}], 'measured': []}))
    monkeypatch.setattr(explore, 'propose', proposal)
    def lookup(seed):
        if seed != 'SSD1TB': return [{'keyword': 'SSD', 'monthly': 90000}]
        if outcome == 'lookup_failure': raise OSError('private provider error')
        return [{'keyword': 'SSD1TB', 'monthly': 499}] if outcome == 'below_floor' else []
    lookup_mock = Mock(side_effect=lookup)
    monkeypatch.setattr(market, 'fetch_keyword_stats', lookup_mock)
    monkeypatch.setattr(market, 'demand_candidates', real_demand)
    report = market.select_category('리뷰', 1, [])
    assert not report['selected'] and report['research_stop_reason'] == 'pool_exhausted'
    proposal.assert_called_once()
    assert [call.args for call in lookup_mock.call_args_list].count(('SSD1TB',)) == 1
    assert 'private provider error' not in json.dumps(report)
    with pytest.raises(RuntimeError): market.enqueue_report([], report)


def test_adaptive_generation_deadline_prevents_demand_and_research(monkeypatch):
    _, search, _, demand = install_refills(monkeypatch, [], [])
    elapsed = [0]
    monkeypatch.setattr(market, 'monotonic', lambda: elapsed[0])
    def propose(*args):
        elapsed[0] = market.MAX_RESEARCH_SECONDS + 1
        return ['SSD1TB'], {'status': 'proposed', 'seeds': [], 'measured': []}
    monkeypatch.setattr(explore, 'propose', propose)
    report = market.select_category('리뷰', 1, [])
    assert report['research_stop_reason'] == 'time_budget'
    demand.assert_called_once()
    search.assert_not_called()
