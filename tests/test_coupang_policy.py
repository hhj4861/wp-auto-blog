import copy
import json
from unittest.mock import Mock

import pytest

from src.coupang_policy import is_product_promotion, no_coupang_content
from src.coupang_telegram import TelegramClient, TelegramError
from scripts import coupang_telegram_worker as worker
from scripts import publish_codex_draft as publisher
from tests.test_coupang_worker import worker_case, make_ready
from tests.test_codex_draft import affiliate_case, market_case


@pytest.mark.parametrize('topic', ['퇴직금 중간정산', '기관지에 좋은 음식', '전기기사 준비방법',
    '전기기사 교재 추천', '배즙 상품 비교', '쿠팡 상품 반품 방법'])
def test_mentions_and_recommendations_never_opt_information_into_promotion(topic):
    assert not is_product_promotion({'topic': topic})
    assert not is_product_promotion({'topic': topic, 'article_type': 'information'})


@pytest.mark.parametrize('value', [None, {}, {'article_type': 'review'}, {'article_type': True}])
def test_unknown_designation_defaults_to_information(value):
    assert not is_product_promotion(value)


def test_only_explicit_editorial_promotion_allows_products():
    assert is_product_promotion({'article_type': 'product_promotion'})
    assert no_coupang_content('<p>퇴직금 중간정산 신청 서류</p>')
    assert not no_coupang_content('<a href="https://link.coupang.com/a/123">상품</a>')


def test_information_draft_never_registers_or_sends_product_request(worker_case):
    c = worker_case
    c.row.pop('article_type')
    c.path.write_text(json.dumps([c.row]))
    assert worker.register(c.store, c.client, c.env) == []
    assert c.store.data['requests'] == []
    assert c.telegram['sent'] == []
    c.read.assert_not_called()
    c.client.check_webhook = Mock(side_effect=AssertionError('no Telegram preflight'))
    assert worker.register(c.store, c.client, c.env) == []


@pytest.mark.parametrize('stage', ['check', 'register', 'notify'])
def test_information_cli_needs_no_telegram_credentials(worker_case, monkeypatch, stage):
    c = worker_case
    c.row.pop('article_type')
    c.path.write_text(json.dumps([c.row]))
    monkeypatch.setattr(worker, 'load_dotenv', lambda: None)
    monkeypatch.setattr(worker, 'TelegramClient', Mock(side_effect=AssertionError('no Telegram client')))
    monkeypatch.setattr('sys.argv', ['worker', stage])
    monkeypatch.delenv('NOTIFICATION_IDS', raising=False)
    assert worker.main() == 0


def test_reclassified_waiting_request_does_not_wait_send_or_arm(worker_case, monkeypatch):
    c = worker_case
    identifiers = worker.register(c.store, c.client, c.env)
    worker.notify(c.store, c.client, identifiers)
    sent = len(c.telegram['sent'])
    rows = json.loads(c.path.read_text()); rows[0]['article_type'] = 'information'
    c.path.write_text(json.dumps(rows))
    assert worker.register(c.store, c.client, c.env) == []
    sleep = Mock(side_effect=AssertionError('information must not wait'))
    monkeypatch.setattr(worker.time, 'sleep', sleep)
    worker.wait_for_reply_window(c.store)
    assert worker.prepare(c.store, c.client, '1000') == ''
    assert c.store.find(identifiers[0])['status'] == 'held'
    assert len(c.telegram['sent']) == sent


def test_queue_reclassification_blocks_reply_even_after_approval(worker_case):
    c = worker_case
    identifier = make_ready(c)
    rows = json.loads(c.path.read_text()); rows[0]['article_type'] = 'information'
    c.path.write_text(json.dumps(rows))
    assert worker.prepare(c.store, c.client, '1000') == ''
    assert c.store.find(identifier)['last_error'] == 'product_promotion_required'


def test_sender_requires_promotion_snapshot(worker_case):
    c = worker_case
    identifier = worker.register(c.store, c.client, c.env)[0]
    record = copy.deepcopy(c.store.find(identifier))
    record['status'] = 'pending_notification'
    record.pop('article_type')
    with pytest.raises(TelegramError, match='product_promotion_required'):
        c.client.send_request(record)
    assert c.telegram['sent'] == []


def test_information_draft_rejects_supplied_products_before_any_write(affiliate_case):
    c = affiliate_case
    path = c['data'] / 'topic_queue_general.json'
    rows = json.loads(path.read_text()); rows[1].pop('article_type')
    path.write_text(json.dumps(rows))
    with pytest.raises(publisher.AffiliateDraftError, match='product_promotion_required'):
        publisher.publish_draft(1724, c['env'], affiliate_request=c['request'])
    c['session'].post.assert_not_called()
    c['client'].generate.assert_not_called()


def test_information_draft_rejects_unowned_product_link(market_case):
    c = market_case
    c['original']['content']['raw'] += '<a href="https://link.coupang.com/a/123">상품</a>'
    with pytest.raises(publisher.AffiliateDraftError, match='unexpected_affiliate_content'):
        publisher.publish_draft(1724, c['env'])
    c['session'].post.assert_not_called()
