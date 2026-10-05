"""Production failure replay plus integration through selection and final article gates."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from src import analysis_runtime as runtime, market_topics as market
from src import topic_suitability as suitability, selection_feedback as feedback
from src.codex_client import CodexResponseError, CodexRequestError
from tests.test_market_topics import isolated_market_history, synthetic_plan_review, market_pipeline
from tests.test_selection_feedback import install_selection
from tests.test_market_opportunity import approved_article_brief, ARTICLE, TOPIC, article_response
from tests.test_pipeline_duplicates import codex_pipeline


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(runtime, 'sleep', lambda _: None)
    monkeypatch.delenv('YOUTUBE_API_KEY', raising=False)


def test_recorded_independent_failure_retains_real_inputs_and_reason():
    recorded = json.loads((Path(__file__).parent / 'fixtures/review_independent_failure_20261001.json').read_text())
    candidate = deepcopy(recorded['held'][0])
    assert candidate['keyword'] == '공기청정기필터'
    assert candidate['suitability_evidence']['failure_code'] == 'review_failed'
    original_sources = deepcopy(candidate['verified_sources'])
    now = datetime.fromisoformat(recorded['selected_at'])
    call = Mock(side_effect=CodexResponseError('timeout', 'private subprocess'))
    candidate['suitability_evidence'] = suitability.review_plan(candidate, now, call)
    assert call.call_count == 2
    assert candidate['suitability_evidence']['diagnostics']['code'] == 'timeout'
    assert candidate['verified_sources'] == original_sources
    assert suitability.issues(candidate, now) == ['missing_topic_suitability']
    assert feedback.failure_code(candidate) is None
    assert not market.fresh_market_item(candidate, '리뷰', now)


@pytest.mark.parametrize('outcome', ['recovered', 'negative', 'outage', 'auth'])
def test_selection_only_queues_independently_approved_candidate(monkeypatch, outcome):
    key = '노트북램'
    _, search, _ = install_selection(monkeypatch, [key], passing=[key])
    calls = []
    def review(item, now, unused):
        positive = synthetic_plan_review(item, now, unused)['review']
        if outcome == 'negative':
            positive['required_facets'][0]['supported'] = False
        error = CodexRequestError(1, 'unauthorized') if outcome == 'auth' else CodexResponseError('timeout', 'private')
        call = Mock(side_effect=error if outcome in {'outage', 'auth'} else [error, positive])
        calls.append(call)
        return suitability.review_plan(item, now, call)
    monkeypatch.setattr(market, 'review_plan', review)
    report = market.select_category('리뷰', 1, [])
    assert calls[0].call_count == (1 if outcome == 'auth' else 2)
    if outcome == 'recovered':
        item = market.enqueue_report([], report)[0]
        assert item['keyword'] == key and market.fresh_market_item(item, '리뷰')
        assert report['analysis_recovery_attempts'] == 1
    else:
        assert report['selected'] == []
        with pytest.raises(RuntimeError):
            market.enqueue_report([], report)
        if outcome in {'outage', 'auth'}:
            assert report['failure_history'] == []
        if outcome == 'auth':
            assert report['operational_error'] == 'unauthorized'


def test_unresearched_uncertainty_is_not_retired_after_first_two(monkeypatch):
    keys = ['공기청정기필터', '삼성노트북배터리', '모니터주사율']
    _, search, _ = install_selection(monkeypatch, keys, passing=['모니터주사율'],
        shortlist=lambda _: {'candidates': []})
    # Make the passing candidate third in the offered pool.
    monkeypatch.setattr(market, 'candidate_pool', lambda stats, *a: [stats[k] for k in keys if k in stats])
    report = market.select_category('리뷰', 1, [])
    assert report['shortlist_research_attempts'] == 3 and search.call_count == 3
    assert report['selected'][0]['keyword'] == '모니터주사율'
    assert report['research_rounds'] == 2


def test_youtube_related_keyword_is_independently_measured_and_can_reach_queue(monkeypatch):
    key = '모니터주사율'
    stats, search, _ = install_selection(monkeypatch, [key], passing=[key])
    entry = {'seed': '모니터', 'video_id': 'abcdefghijk'}
    audit = {'status': 'discovered', 'seeds': [entry], 'videos': [{'views': 9999999}]}
    monkeypatch.setattr(market, 'discover_youtube', lambda *a: ([entry], audit))
    demand = Mock(side_effect=[{}, stats])
    monkeypatch.setattr(market, 'demand_candidates', demand)
    report = market.select_category('리뷰', 1, [])
    row = market.enqueue_report([], report)[0]
    assert row['monthly_search'] == 1200 and row['trend_growth'] is None
    assert row['youtube_discovery']['relationship'] == 'related_seed'
    assert row['score_components']['trend'] == 0
    assert demand.call_args_list[1].args == (['모니터'],)


@pytest.mark.parametrize('error', [CodexResponseError('timeout', 'private'),
                                  CodexRequestError(1, '503 service')])
def test_final_article_recovery_uses_real_body_and_does_not_require_new_generation(approved_article_brief, error):
    from src.market_opportunity import review_article
    model = Mock(side_effect=[error, article_response()])
    assert review_article(TOPIC, ARTICLE, '', approved_article_brief, model) == []
    assert model.call_count == 2 and model.call_args_list[0] == model.call_args_list[1]


def test_duplicate_review_recovers_without_accepting_unverified_topic(codex_pipeline):
    pipeline, client, _, _ = codex_pipeline
    client.generate.side_effect = [CodexResponseError('timeout', 'private'), 'NOT_DUPLICATE']
    assert pipeline._is_duplicate('새 주제') is False
    assert client.generate.call_count == 2
    pipeline.wp_client.create_post.assert_not_called()


@pytest.mark.parametrize('final_outcome', ['recovered', 'negative', 'outage'])
def test_selection_queue_writer_final_review_publication_and_ledger(
        market_pipeline, tmp_path, monkeypatch, final_outcome):
    """Real selection/queue/main/pipeline/ledger; external I/O only is substituted.

    Source content and model opinions here are synthetic, not live success evidence.
    """
    import sys
    from src import main as entry
    from src.wordpress_client import CreatedPost, PostStatus
    key = '시험준비물'
    install_selection(monkeypatch, [key], passing=[key], category='취업')
    def independent(item, now, unused):
        raw = synthetic_plan_review(item, now, unused)['review']
        return suitability.review_plan(item, now, Mock(side_effect=[
            CodexResponseError('timeout', 'private'), raw]))
    monkeypatch.setattr(market, 'review_plan', independent)
    report = market.select_category('취업', 1, [])
    queue = market.enqueue_report([], report)
    assert len(queue) == 1
    data = tmp_path / 'data'
    data.mkdir(exist_ok=True)
    path = data / 'topic_queue_general.json'
    path.write_text(json.dumps(queue))
    monkeypatch.setattr(market, 'LEDGER', data / 'ledger.json')
    monkeypatch.setattr(entry, '__file__', str(tmp_path / 'src/main.py'))
    monkeypatch.setattr(entry, 'load_dotenv', lambda: None)
    monkeypatch.setattr(entry, 'setup_logging', lambda **kw: None)
    monkeypatch.setattr(entry, 'BlogPipeline', lambda *a, **kw: market_pipeline)
    market_pipeline._is_duplicate = Mock(return_value=False)
    positive = json.dumps({'covers_primary_intent': final_outcome != 'negative',
                          'answer_quote': '시험준비물은 신분증과 수험표 등 공식 준비물 목록을 확인하세요.',
                          'facet_reviews': [{'facet_index': 0, 'covered': True, 'reason': 'covered',
                                            'answer_quote': '시험준비물은 신분증과 수험표 등 공식 준비물 목록을 확인하세요.'}]})
    error = CodexResponseError('timeout', 'private')
    market_pipeline.content_generator._call_llm.side_effect = (
        [error, positive] if final_outcome != 'outage' else [error, error])
    market_pipeline.wp_client.create_post.side_effect = lambda **kw: CreatedPost(
        123, 'https://trendpulse.blog/synthetic-test/', queue[0]['topic'], kw['status'])
    monkeypatch.setattr(sys, 'argv', ['main', '--mode', 'general', '--from-queue',
                                    '--auto-publish', '--category', '취업'])
    exit_code = entry.main()
    market_pipeline.wp_client.create_post.assert_called_once()
    sent_status = market_pipeline.wp_client.create_post.call_args.kwargs['status']
    assert market_pipeline.content_generator._call_llm.call_count == 2
    if final_outcome == 'recovered':
        assert exit_code == 0 and sent_status == PostStatus.PUBLISH
        assert json.loads(market.LEDGER.read_text())[0]['post_id'] == 123
        assert json.loads(path.read_text())[0]['status'] == 'completed'
    else:
        assert sent_status == PostStatus.DRAFT
        assert not market.LEDGER.exists() or json.loads(market.LEDGER.read_text()) == []


def test_writer_retries_transient_error_without_changing_provider():
    from src.content_generator import ContentGenerator, ContentConfig, LLMProvider
    writer = ContentGenerator.__new__(ContentGenerator)
    writer.config = ContentConfig(provider=LLMProvider.CODEX)
    writer._codex_client = Mock()
    writer._codex_client.generate.side_effect = [CodexResponseError('timeout', 'private'), '<p>원고</p>']
    assert writer._call_llm('input') == '<p>원고</p>'
    assert writer._codex_client.generate.call_count == 2
