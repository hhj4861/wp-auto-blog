"""Recorded source misrouting and bounded exploration after real negative verdicts."""
from hashlib import sha256
import json
from pathlib import Path
from unittest.mock import Mock
import pytest
from src import review_discovery as review, market_topics as market, review_exploration as explore
from tests.test_market_topics import isolated_market_history as isolated_market_history
from tests.test_selection_feedback import install_selection


def source(body, url='https://www.seagate.com/products/external-hard-drives/portable-drive/'):
    return {'url': url, 'title': 'Drive specification', 'excerpt': body, 'sha256': sha256(body.encode()).hexdigest()}


def test_recorded_hdd_questions_reject_all_misrouted_ssd_sources():
    recorded = json.loads(Path('tests/fixtures/review_routing_failure_20261002.json').read_text())
    assert len(recorded['source_failures']) == 2
    for failure in recorded['source_failures']:
        assert failure['sources']
        assert all(not review.relevant_source(failure['keyword'], row) for row in failure['sources'])


@pytest.mark.parametrize('keyword,body,accepted', [
    ('외장하드1TB', 'External hard drive 1 TB USB bus power', True),
    ('외장하드1TB', 'External SSD 1 TB USB bus power', False),
    ('외장하드1TB', 'Internal HDD 1 TB SATA power', False),
    ('외장하드1TB', 'External hard drive 2 TB USB bus power', False),
    ('외장SSD1TB', 'External SSD 1 TB USB bus power', True),
    ('외장SSD1TB', 'Internal SSD 1 TB NVMe SATA', False),
    ('외장SSD1TB', 'External HDD 1 TB USB power', False),
    ('HDD1TB', 'Internal HDD 1 TB SATA', True),
    ('SSD1TB', 'Internal SSD 1 TB NVMe', True),
])
def test_storage_type_capacity_and_enclosure_must_match(keyword, body, accepted):
    assert review.relevant_source(keyword, source(body)) is accepted


def test_hdd_domains_are_allowed_without_accepting_lookalikes_and_brand_mismatch():
    assert review.preferred_source_domains('외장하드1TB') == ['seagate.com', 'toshiba-storage.com']
    assert review.preferred_source_domains('씨게이트외장하드1TB') == ['seagate.com']
    assert review.preferred_source_domains('도시바외장하드1TB') == ['toshiba-storage.com']
    for domain in ('seagate.com', 'toshiba-storage.com'):
        assert market.is_official_url('https://www.' + domain + '/product')
        assert not market.is_official_url('https://' + domain + '.evil.example/product')
    assert not review.relevant_source('도시바외장하드1TB', source('External hard drive 1 TB USB'))
    assert 'HDD 하드디스크' in review.source_hint('HDD1TB')
    assert review.preferred_source_domains('SSD1TB')[0] == 'sandisk.com'


@pytest.mark.parametrize('passing', [True, False])
def test_new_questions_run_before_remaining_old_candidates_consume_rounds(monkeypatch, passing):
    old = [f'SSD{i}TB' for i in range(1, 10)]
    good = '노트북배터리'
    measured, search, offered = install_selection(monkeypatch, [*old, good], passing=[good] if passing else [])
    demand = Mock(side_effect=[{k:measured[k] for k in old}, {good:measured[good]}])
    monkeypatch.setattr(market, 'demand_candidates', demand)
    monkeypatch.setattr(review, 'expansion_seeds', lambda _: ())
    proposal = Mock(return_value=([good], {'status':'proposed','seeds':[{'seed':good,'status':'unmeasured'}],'measured':[]}))
    monkeypatch.setattr(explore, 'propose', proposal)
    report = market.select_category('리뷰', 1, [])
    assert offered[1][0] == good and set(offered[0][6:]) <= set(offered[1])
    assert report['review_question_discovery']['trigger'] == 'no_pass_after_round'
    assert report['discovery_replenishment'][0]['trigger'] == 'no_pass_after_round'
    proposal.assert_called_once()
    assert len(proposal.call_args.args[3]) >= 6
    assert demand.call_count == 2
    assert report['research_rounds'] <= market.MAX_RESEARCH_ROUNDS
    assert (bool(report['selected'])) is passing
    if passing:
        assert report['selected'][0]['monthly_search'] == measured[good]['monthly']
        assert market.fresh_market_item(report['selected'][0], '리뷰')
    else:
        with pytest.raises(RuntimeError): market.enqueue_report([], report)
