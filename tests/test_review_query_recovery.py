"""Recorded production failures; proposed rewrites and provider evidence are synthetic."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import pytest
from src import market_topics as market, selection_feedback as feedback
from tests.test_market_topics import isolated_market_history as isolated_market_history
from tests.test_selection_feedback import install_selection

RECORDED = json.loads(Path('tests/fixtures/review_query_failure_20261001.json').read_text())
FAILED = [row for row in RECORDED['candidate_decisions']
          if row['reason'] == 'invalid search query transformation']


@pytest.mark.parametrize('row', FAILED, ids=lambda row: row['keyword'])
def test_recorded_candidate_reaches_search_and_keeps_evidence_bound_to_original(monkeypatch, row):
    key = row['keyword']
    # Original invalid model text was not recorded. Reproduce the strict token
    # conflict with synthetic spacing; do not present it as the production text.
    proposed = re.sub(r'([A-Z]+)([0-9])', r'\1 \2', key)
    measured, search, _ = install_selection(monkeypatch, [key], passing=[key],
        shortlist=lambda _: {'candidates': [{'keyword': key, 'search_query': proposed}]})
    report = market.select_category('리뷰', 1, [])
    search.assert_called_once_with(key)
    item = report['selected'][0]
    assert item['monthly_search'] == measured[key]['monthly']
    assert item['organic_query'] == key
    assert item['opportunity_evidence']['search_review']['executed_query'] == key
    assert report['proposal_rounds'][0]['proposals'][0]['query_error'] == 'search_query_token_change'
    assert market.fresh_market_item(item, '리뷰')
    assert market.enqueue_report([], report)[0]['organic_query'] == key
    tampered = deepcopy(item)
    tampered['organic_query'] = proposed
    assert not market.fresh_market_item(tampered, '리뷰')


def test_real_invalid_transformations_never_poison_keyword_failure_history():
    assert len(FAILED) == 13 and len(RECORDED['candidate_decisions']) == 17
    report = {**RECORDED, 'rejected': FAILED}
    assert feedback.load_history(report, '리뷰', datetime.now(timezone.utc)) == []


def test_query_recovery_cannot_override_negative_article_evidence(monkeypatch):
    key = 'SSD1TB'
    _, search, _ = install_selection(monkeypatch, [key], passing=[],
        shortlist=lambda _: {'candidates': [{'keyword': key, 'search_query': 'SSD 1TB'}]})
    report = market.select_category('리뷰', 1, [])
    search.assert_called_once_with(key)
    assert report['selected'] == []
    assert report['rejected'][0]['reason'] == 'search intent or official evidence does not support an article'
    assert report['failure_history'][0]['reason_code'] == 'source_coverage'
    with pytest.raises(RuntimeError): market.enqueue_report([], report)


def test_recovery_does_not_execute_an_unmeasured_keyword(monkeypatch):
    _, search, _ = install_selection(monkeypatch, ['SSD1TB'],
        shortlist=lambda _: {'candidates': [{'keyword': 'SSD999TB', 'search_query': 'SSD 999TB'}]})
    report = market.select_category('리뷰', 1, [])
    assert not report['selected']
    search.assert_not_called()
