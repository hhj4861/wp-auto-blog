"""Published post -> durable notification -> reply -> same-post update, with fake transports."""
import copy
import json
from datetime import timedelta
from unittest.mock import Mock

import pytest
import requests

from scripts import coupang_telegram_worker as worker
from scripts import update_coupang_post as updater
from scripts import publish_codex_draft as draft
from src.coupang_products import products_preserved
from src.coupang_telegram import RequestStore, TelegramError, reply_deadline
from tests.test_codex_draft import affiliate_case, market_case
from tests.test_coupang_worker import fake_telegram, reply


@pytest.fixture
def published_case(affiliate_case, monkeypatch):
    c = affiliate_case
    c['original'].update(status='publish', link='https://trendpulse.blog/a1c-levels/',
                         date='2026-09-01T11:00:00', date_gmt='2026-09-01T02:00:00')
    c['original']['content']['raw'] = c['original']['content']['raw'].replace('근거 없는 주장', '공식 자료로 확인된 기준')
    c['state']['current'] = copy.deepcopy(c['original'])
    path = c['data'] / 'topic_queue_general.json'
    rows = json.loads(path.read_text())
    rows[1].update(status='completed', post_status='publish', affiliate_flow='post_update',
                   url=c['original']['link'], selected_at=(worker.now() - timedelta(days=60)).isoformat())
    rows[1].pop('affiliate_request_id')
    path.write_text(json.dumps(rows))
    c['queue_path'] = path
    c['brief'] = rows[1]
    c['session'].__enter__ = Mock(return_value=c['session'])
    c['session'].__exit__ = Mock(return_value=False)

    def post(url, json, **kwargs):
        assert url.endswith('/posts/1724')
        assert set(json) == {'content'}
        c['state']['posted'] = True
        c['state']['current']['content'] = {'raw': json['content']}
        c['state']['current']['modified_gmt'] = 'updated'
        return c['response'](c['state']['current'])

    c['session'].post.side_effect = post
    monkeypatch.setattr(updater, 'CodexSubscriptionClient', lambda **kwargs: c['client'])
    monkeypatch.setattr(worker, 'DATA', c['data'])
    c['store'] = RequestStore(c['data'] / 'coupang_requests.json')
    c['telegram_client'], c['telegram'] = fake_telegram()
    c['env']['GITHUB_RUN_ID'] = '12345'
    return c


def notify(c):
    ids = worker.register(c['store'], c['telegram_client'], c['env'])
    assert len(ids) == 1 and not c['telegram']['sent']
    c['store'] = RequestStore(c['store'].path)
    worker.notify(c['store'], c['telegram_client'], ids)
    c['store'] = RequestStore(c['store'].path)
    return ids[0]


def ready(c):
    identifier = notify(c)
    c['telegram']['updates'] = [reply()]
    assert worker.process_updates(c['store'], c['telegram_client'], run_id='12345') == [identifier]
    c['store'] = RequestStore(c['store'].path)
    assert worker.prepare(c['store'], c['telegram_client'], '12345') == identifier
    c['store'] = RequestStore(c['store'].path)
    return identifier


def test_published_post_accepts_late_reply_updates_only_content_and_never_duplicates(published_case):
    c = published_case
    identifier = ready(c)
    message = c['telegram']['sent'][0]['text']
    assert c['original']['link'] in message
    assert '쿠팡 파트너스' in message and '답장 시간 제한은 없습니다' in message
    assert '30분' not in message
    assert reply_deadline(c['store'].find(identifier)) is None
    # Use the worker's real default dispatch, store, parser, insertion and review functions.
    assert worker.publish(c['store'], c['telegram_client'], identifier, c['env']) == c['original']['link']
    c['session'].post.assert_called_once()
    payload = c['session'].post.call_args.kwargs['json']
    assert set(payload) == {'content'}
    record = RequestStore(c['store'].path).find(identifier)
    assert products_preserved(payload['content'], record['products'], request_id=identifier)
    assert record['status'] == 'published'
    row = json.loads(c['queue_path'].read_text())[1]
    assert row['status'] == 'completed' and row['affiliate_state'] == 'published'
    assert '상품 링크와 광고 고지를 추가했습니다' in c['telegram']['sent'][-1]['text']
    assert c['registry_write'].call_count == 0
    assert not (c['data'] / 'posted_market_keywords.json').exists()  # No second publication record.
    assert list((c['data'] / 'editorial-backups').glob('coupang-update-1724-*.json'))
    assert worker.process_updates(c['store'], c['telegram_client']) == []
    assert worker.prepare(c['store'], c['telegram_client'], '12346') == ''
    c['session'].post.assert_called_once()


def test_no_reply_never_arms_an_update_or_waits(published_case, monkeypatch):
    c = published_case
    identifier = notify(c)
    monkeypatch.setattr(worker.time, 'sleep', Mock(side_effect=AssertionError('must not wait')))
    worker.wait_for_reply_window(c['store'])
    worker.process_updates(c['store'], c['telegram_client'], run_id='12345')
    assert worker.prepare(c['store'], c['telegram_client'], '12345') == ''
    assert c['store'].find(identifier)['status'] == 'waiting'
    c['session'].post.assert_not_called()


@pytest.mark.parametrize('change', ['body', 'title', 'date', 'status', 'queue', 'run', 'unrelated', 'evidence', 'sources'])
def test_changed_or_unverified_posts_are_not_overwritten(published_case, change):
    c = published_case
    identifier = ready(c)
    if change == 'body':
        c['state']['current']['content']['raw'] += '<p>수동 수정</p>'
    elif change == 'title':
        c['state']['current']['title']['raw'] = '변경한 제목'
    elif change == 'date':
        c['state']['current']['date'] = '2026-09-02T11:00:00'
    elif change == 'status':
        c['state']['current']['status'] = 'draft'
    elif change == 'queue':
        rows = json.loads(c['queue_path'].read_text()); rows[1]['article_type'] = 'information'
        c['queue_path'].write_text(json.dumps(rows))
    elif change == 'run':
        c['env']['GITHUB_RUN_ID'] = '54321'
    elif change == 'unrelated':
        c['client'].generate.side_effect = lambda prompt: '{"products":[{"index":0,"relevant":false,"claims_supported":true}]}'
    elif change == 'evidence':
        previous = c['client'].generate.side_effect
        c['client'].generate.side_effect = lambda prompt: ('{"issues":["근거 없는 상품 주장"]}'
            if 'conservative Korean editorial fact checker' in prompt else previous(prompt))
    else:
        c['fetch'].side_effect = lambda url: None
    with pytest.raises(TelegramError):
        worker.publish(c['store'], c['telegram_client'], identifier, c['env'])
    c['session'].post.assert_not_called()


def test_edit_during_review_is_detected_before_write(published_case):
    c = published_case
    identifier = ready(c)
    previous = c['client'].generate.side_effect
    def edit(prompt):
        c['state']['current']['modified_gmt'] = 'human-edit'
        return previous(prompt)
    c['client'].generate.side_effect = edit
    with pytest.raises(TelegramError):
        worker.publish(c['store'], c['telegram_client'], identifier, c['env'])
    c['session'].post.assert_not_called()


@pytest.mark.parametrize('applied', [True, False])
def test_lost_update_response_is_read_back_and_never_retried(published_case, applied):
    c = published_case
    identifier = ready(c)
    previous = c['session'].post.side_effect
    def timeout(*args, **kwargs):
        if applied:
            previous(*args, **kwargs)
        raise requests.Timeout('private transport details')
    c['session'].post.side_effect = timeout
    if applied:
        assert worker.publish(c['store'], c['telegram_client'], identifier, c['env']) == c['original']['link']
    else:
        with pytest.raises(TelegramError, match='publication_failed'):
            worker.publish(c['store'], c['telegram_client'], identifier, c['env'])
        assert c['store'].find(identifier)['status'] == 'held'
    assert worker.prepare(c['store'], c['telegram_client'], '12346') == ''
    c['session'].post.assert_called_once()


def test_notification_failure_keeps_published_article_and_does_not_resend(published_case):
    c = published_case
    identifiers = worker.register(c['store'], c['telegram_client'], c['env'])
    c['telegram_client'].send_request = Mock(side_effect=TelegramError('telegram_timeout'))
    with pytest.raises(TelegramError):
        worker.notify(c['store'], c['telegram_client'], identifiers)
    assert worker.register(RequestStore(c['store'].path), c['telegram_client'], c['env']) == []
    assert c['state']['current']['status'] == 'publish'
    c['session'].post.assert_not_called()


@pytest.mark.parametrize('mode', ['information', 'legacy_public', 'draft'])
def test_unmarked_or_unpublished_articles_do_not_get_followup(published_case, mode):
    c = published_case
    rows = json.loads(c['queue_path'].read_text())
    if mode == 'information':
        rows[1]['article_type'] = 'information'
    elif mode == 'legacy_public':
        rows[1].pop('affiliate_flow')
    else:
        c['original']['status'] = c['state']['current']['status'] = 'draft'
    c['queue_path'].write_text(json.dumps(rows))
    assert worker.register(c['store'], c['telegram_client'], c['env']) == []
    assert not c['telegram']['sent']


def test_invalid_reply_can_be_corrected_after_publication(published_case):
    c = published_case
    identifier = notify(c)
    invalid = reply(); invalid['message']['text'] = 'https://link.coupang.com/a/abcd1234'
    c['telegram']['updates'] = [invalid]
    assert worker.process_updates(c['store'], c['telegram_client']) == []
    assert worker.prepare(c['store'], c['telegram_client'], '12345') == ''
    c['telegram']['updates'] = [reply(update_id=91)]
    assert worker.process_updates(c['store'], c['telegram_client']) == [identifier]
    assert worker.prepare(c['store'], c['telegram_client'], '12345') == identifier


def test_interrupted_update_is_held_without_second_write(published_case):
    c = published_case
    identifier = ready(c)
    assert worker.prepare(RequestStore(c['store'].path), c['telegram_client'], '12346') == ''
    record = RequestStore(c['store'].path).find(identifier)
    assert record['status'] == 'held' and record['last_error'] == 'publication_outcome_unknown'
    c['session'].post.assert_not_called()
