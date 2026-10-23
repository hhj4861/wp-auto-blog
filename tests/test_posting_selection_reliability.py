"""Reproduce missing-stock slots and same-topic reselection without live model/WordPress writes."""
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import Mock

import pytest
import requests

from src import market_topics as market
from src import wordpress_inventory_cache as cache
from tests.test_market_topics import (
    candidate, evidence, organic_sample, intent_review,
)

from tests import test_market_topics as market_tests

# Re-export shared pytest fixtures explicitly; model/HTTP boundaries stay isolated.
isolated_market_history = market_tests.isolated_market_history
inventory_read = market_tests.inventory_read
reuse_cli = market_tests.reuse_cli

# Preserve the real boundary before the default transport-isolation fixture replaces it.
real_review_candidate = market.review_candidate


def test_selection_and_writer_use_the_same_semantic_policy(tmp_path, monkeypatch):
    path = tmp_path / 'data/post_registry_general.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps([{'title': '이력서 작성 방법', 'intent': '신입 항목별 작성 요령'}]))
    monkeypatch.setattr(market, 'ROOT', tmp_path)
    client = Mock()
    client.generate.return_value = 'DUPLICATE'
    monkeypatch.setattr('src.codex_client.CodexSubscriptionClient', Mock(return_value=client))
    assert real_review_candidate({'topic': '입사지원서 작성 순서'}, ['기존 글']) is True
    prompt = client.generate.call_args.args[0]
    assert '이력서 작성 방법' in prompt and '신입 항목별 작성 요령' in prompt
    assert '입사지원서 작성 순서' in prompt
    assert 'preparation foods versus examination cost are different' in prompt


def test_selector_discards_semantic_duplicate_and_selects_next_verified_question(monkeypatch):
    keys = ['시험준비물', '면접준비물']
    monkeypatch.setattr(market, 'fetch_trend_change', lambda *a: None)
    monkeypatch.setattr(market, 'demand_candidates', lambda seeds: {
        k: {'keyword': k, 'monthly': 1200, 'comp': '높음'} for k in keys})
    monkeypatch.setattr(market, 'ask', lambda prompt: {'candidates': [{'keyword': k} for k in keys]})
    monkeypatch.setattr(market, 'search_results', lambda q: ('google_custom_search', organic_sample(q)))
    monkeypatch.setattr(market, 'candidate_sources', lambda *a: [evidence()])
    monkeypatch.setattr(market, 'topic_from_evidence', lambda keyword, *a, **kw: (
        candidate(keyword=keyword, keywords=[keyword], topic=keyword + ' 확인 방법',
                  intent_evidence=intent_review(keyword)), None))
    review = Mock(side_effect=[True, False])
    monkeypatch.setattr(market, 'review_candidate', review)
    result = market.select_category('취업', top_n=1, titles=['기존 시험 준비 안내'])
    assert [row['keyword'] for row in result['selected']] == ['면접준비물'], result
    assert any(row['keyword'] == '시험준비물' and row['reason'] == 'semantic_duplicate'
               for row in result['rejected'])
    assert review.call_count == 2


def test_new_research_excludes_writer_rejected_keyword_even_without_report_reuse(reuse_cli):
    c = reuse_cli
    c.queue.write_text(json.dumps([{**candidate(keyword='이력서작성법'), 'status': 'skipped_duplicate'}]))
    fresh = candidate(keyword='면접준비물', keywords=['면접준비물'], topic='면접준비물 확인 방법')
    c.select.side_effect = None
    c.select.return_value = {'category': '취업', 'selected': [fresh]}
    assert c.cli.main() == 0
    assert '이력서작성법' in c.select.call_args.kwargs['excluded_keywords']
    rows = json.loads(c.queue.read_text())
    assert rows[0]['status'] == 'skipped_duplicate'
    assert rows[-1]['keyword'] == '면접준비물'


def test_enqueue_preserves_other_fresh_stock_in_same_category():
    old = candidate(keyword='면접준비물', keywords=['면접준비물'], topic='면접준비물 확인 방법')
    incoming = candidate()
    rows = market.enqueue_report([old], {'category': '취업', 'selected': [incoming]})
    assert [row['status'] for row in rows] == ['pending', 'pending']


@pytest.mark.parametrize('status', ['completed', 'held_draft', 'skipped_duplicate'])
def test_enqueue_cannot_revive_terminal_keyword_even_with_a_stale_selected_report(status):
    old = {**candidate(), 'status': status}
    with pytest.raises(RuntimeError, match='already used or rejected'):
        market.enqueue_report([old], {'category': '취업', 'selected': [candidate()]})
    assert old['status'] == status


def test_recovery_researches_other_categories_when_preferred_has_no_stock(reuse_cli, monkeypatch):
    c = reuse_cli
    monkeypatch.setattr('sys.argv', ['select', '--category', '리뷰', '--enqueue', '--recover-slot'])
    c.select.side_effect = lambda category, *a, **kw: {
        'category': category, 'selected': [candidate()] if category == '취업' else []}
    original_budget = market.MAX_RESEARCH_SECONDS
    assert c.cli.main() == 0
    assert [call.args[0] for call in c.select.call_args_list] == ['리뷰', '취업']
    assert market.MAX_RESEARCH_SECONDS == original_budget
    assert json.loads(c.queue.read_text())[-1]['category'] == '취업'


def test_recovery_does_not_retry_fatal_provider_failures_across_categories(reuse_cli, monkeypatch):
    c = reuse_cli
    monkeypatch.setattr('sys.argv', ['select', '--category', '리뷰', '--enqueue', '--recover-slot'])
    c.select.side_effect = None
    c.select.return_value = {'category': '리뷰', 'selected': [], 'operational_error': 'usage_limit'}
    assert c.cli.main() == 1
    c.select.assert_called_once()


def test_slot_screening_removes_semantic_duplicate_before_choosing_other_stock(tmp_path, monkeypatch, capsys):
    import scripts.pick_slot_category as cli
    bad, good = candidate(), candidate('건강', keyword='검진준비물', keywords=['검진준비물'], topic='검진준비물 확인 방법')
    path = tmp_path / 'queue.json'
    path.write_text(json.dumps([bad, good]))
    monkeypatch.setattr(cli, 'QUEUE', path)
    monkeypatch.setattr(cli, 'load_dotenv', lambda: None)
    monkeypatch.setattr(cli, 'existing_titles', lambda: ['이전 글'])
    monkeypatch.setattr(market, 'review_candidate', lambda item, *a: item['category'] == '취업')
    assert cli.main(['--preferred', '취업']) == 0
    assert capsys.readouterr().out.strip() == '건강'
    assert json.loads(path.read_text())[0]['status'] == 'skipped_duplicate'


def enable_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv('GITHUB_RUN_ID', '123')
    monkeypatch.setenv('RUNNER_TEMP', str(tmp_path))
    path = tmp_path / 'inventory.json'
    monkeypatch.setenv('BLOG_INVENTORY_PATH', str(path))
    return path


def test_complete_inventory_is_reused_but_publication_forces_live_read(inventory_read, tmp_path, monkeypatch):
    path = enable_snapshot(tmp_path, monkeypatch)
    case = inventory_read
    case.get.side_effect = [case.first, case.second, case.first, case.second]
    first = market.existing_titles()
    assert market.existing_titles() == first
    assert case.get.call_count == 2
    with cache.fresh_read():
        assert market.existing_titles() == first
    assert case.get.call_count == 4
    assert path.stat().st_mode & 0o777 == 0o600
    assert 'synthetic-password' not in path.read_text()


def test_partial_inventory_failure_never_saves_a_snapshot(inventory_read, tmp_path, monkeypatch):
    path = enable_snapshot(tmp_path, monkeypatch)
    case = inventory_read
    case.get.side_effect = [case.first, requests.Timeout(), requests.Timeout()]
    with pytest.raises(RuntimeError, match='WordPress inventory unavailable'):
        market.existing_titles()
    assert not path.exists()


@pytest.mark.parametrize('invalid', ['expired', 'future', 'run', 'binding', 'partial', 'invalid_titles'])
def test_snapshot_cannot_survive_its_age_run_identity_or_completeness(tmp_path, monkeypatch, invalid):
    path = enable_snapshot(tmp_path, monkeypatch)
    cache.save(['one'])
    row = json.loads(path.read_text())
    if invalid in ('expired', 'future'):
        delta = timedelta(minutes=-4 if invalid == 'expired' else 1)
        row['fetched_at'] = (datetime.now(timezone.utc) + delta).isoformat()
    elif invalid == 'run':
        row['run_id'] = '456'
    elif invalid == 'binding':
        row['binding'] = 'different-user'
    elif invalid == 'partial':
        row['complete'] = False
    else:
        row['titles'] = [None]
    path.write_text(json.dumps(row))
    assert cache.load() is None


def test_reserve_refill_includes_categories_with_only_one_topic():
    from src.topic_inventory import refill_categories
    stock = [candidate()]
    result = refill_categories(stock, datetime.now(timezone.utc), 6, target=2)
    assert '취업' in result


def test_failed_publication_refresh_never_falls_back_to_saved_inventory(inventory_read, tmp_path, monkeypatch):
    enable_snapshot(tmp_path, monkeypatch)
    case = inventory_read
    case.get.side_effect = [case.first, case.second, requests.ConnectionError(), requests.ConnectionError()]
    market.existing_titles()
    assert cache.load() is not None
    with cache.fresh_read(), pytest.raises(RuntimeError, match='WordPress inventory unavailable'):
        market.existing_titles()
    assert case.get.call_count == 4


def test_recovery_uses_existing_other_category_reserve_without_researching_it(reuse_cli, monkeypatch):
    c = reuse_cli
    c.queue.write_text(json.dumps([candidate()]))
    monkeypatch.setattr('sys.argv', ['select', '--category', '리뷰', '--enqueue', '--recover-slot'])
    c.select.side_effect = None
    c.select.return_value = {'category': '리뷰', 'selected': []}
    assert c.cli.main() == 0
    c.select.assert_called_once()


def test_market_queue_advances_past_more_than_five_duplicates(tmp_path, monkeypatch):
    import src.main as entry
    from src.pipeline import PipelineResult
    data = tmp_path / 'data'
    data.mkdir(exist_ok=True)
    rows = [candidate(keyword=f'시험준비물{i}', keywords=[f'시험준비물{i}'], topic=f'시험준비물{i} 확인')
            for i in range(7)]
    path = data / 'topic_queue_general.json'
    path.write_text(json.dumps(rows))
    pipeline = Mock()
    pipeline.run_single.side_effect = [
        *[PipelineResult(topic=row['topic'], success=False, error='Duplicate topic') for row in rows[:6]],
        PipelineResult(topic=rows[-1]['topic'], success=True)]
    monkeypatch.setattr(entry, '__file__', str(tmp_path / 'src/main.py'))
    monkeypatch.setattr(entry, 'BlogPipeline', lambda **kwargs: pipeline)
    monkeypatch.setattr(entry, 'setup_logging', lambda **kwargs: None)
    monkeypatch.setattr(entry, 'load_dotenv', lambda: None)
    monkeypatch.setattr(market, 'existing_titles', lambda: [])
    monkeypatch.setattr(market, 'fresh_market_item', lambda *args: True)
    monkeypatch.setenv('BLOG_REQUIRE_MARKET_TOPIC', '1')
    monkeypatch.setattr('sys.argv', ['blog', '--mode', 'general', '--from-queue', '--category', '취업', '--dry-run'])
    assert entry.main() == 0
    assert pipeline.run_single.call_count == 7
    assert all(row['status'] == 'skipped_duplicate' for row in json.loads(path.read_text())[:6])


@pytest.mark.parametrize('reason,retries', [('connection_failure', 2), ('timeout', 2),
    ('http_503', 2), ('http_401', 0), ('http_403', 0), ('tls_failure', 0), ('invalid_json', 0)])
def test_preflight_recovers_only_safe_read_transport_failures(monkeypatch, reason, retries):
    import scripts.prepare_posting_inventory as prepare
    inventory = Mock(side_effect=[market.InventoryUnavailable(reason)] * (retries + 1))
    pause = Mock()
    monkeypatch.setattr(prepare, 'load_dotenv', lambda: None)
    monkeypatch.setattr(prepare, 'existing_titles', inventory)
    monkeypatch.setattr(prepare, 'sleep', pause)
    with pytest.raises(market.InventoryUnavailable):
        prepare.main()
    assert inventory.call_count == retries + 1
    assert pause.call_count == retries


def test_preflight_transient_failure_can_recover_before_any_topic_work(monkeypatch):
    import scripts.prepare_posting_inventory as prepare
    inventory = Mock(side_effect=[market.InventoryUnavailable('connection_failure'), ['complete inventory']])
    pause = Mock()
    monkeypatch.setattr(prepare, 'load_dotenv', lambda: None)
    monkeypatch.setattr(prepare, 'existing_titles', inventory)
    monkeypatch.setattr(prepare, 'sleep', pause)
    assert prepare.main() == 0
    assert inventory.call_count == 2
    pause.assert_called_once_with(15)


def test_inventory_failure_notification_identifies_the_read_only_stage(tmp_path):
    from scripts.scheduled_post import failure_message
    path = tmp_path / 'stage'
    path.write_text('inventory')
    message = failure_message({'GITHUB_RUN_ID': '123', 'SCHEDULE_STAGE_PATH': str(path),
        'SCHEDULE_CATEGORY': '건강', 'SCHEDULE_SLOT': 'morning'})
    assert '기존 글 목록 조회·연결 복구' in message


def test_actions_checks_inventory_before_research_or_writer(tmp_path):
    from tests.test_codex_actions import run_queue_step
    result, calls, _ = run_queue_step(tmp_path, '건강', stock='건강',
                                     extra_env={'BLOG_INVENTORY_PATH': str(tmp_path / 'inventory.json')})
    assert result.returncode == 0
    assert calls[0] == 'scripts/prepare_posting_inventory.py'
    assert calls[-1].startswith('-m src.main ')
