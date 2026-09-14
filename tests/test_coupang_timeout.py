"""No-response fallback with real stores/parsers and a shared clock; no external I/O."""
import copy
import json
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from scripts import coupang_telegram_worker as worker
from src import coupang_telegram as telegram_api
from src.coupang_telegram import RequestStore, TelegramError
from tests.test_coupang_worker import worker_case, fake_telegram, reply
from tests.test_codex_draft import affiliate_case, market_case


class Clock:
    def __init__(self, value):
        self.value = value

    def now(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


@pytest.fixture
def timed_case(worker_case, monkeypatch):
    c = worker_case
    c.clock = Clock(c.stamp)
    # Install both clocks before register creates any request.
    monkeypatch.setattr(worker, 'now', c.clock.now)
    monkeypatch.setattr(telegram_api, 'utc_now', c.clock.now)
    return c


def reload_store(c):
    c.store = RequestStore(c.store.path)
    return c.store


def notify_case(c):
    identifiers = worker.register(c.store, c.client, c.env)
    assert len(identifiers) == 1
    c.identifier = identifiers[0]
    reload_store(c)  # The workflow commits this intent before notification.
    worker.notify(c.store, c.client, identifiers)
    reload_store(c)
    return c.store.find(c.identifier)


def poll(c, updates=None, run_id='1000'):
    c.telegram['updates'] = [] if updates is None else updates
    result = worker.process_updates(c.store, c.client, run_id=run_id)
    reload_store(c)  # No next poll/publication before persisted state is reloaded.
    return result


def test_notification_records_its_success_time_without_retroactive_request_timer(timed_case):
    c = timed_case
    identifiers = worker.register(c.store, c.client, c.env)
    before = RequestStore(c.store.path).find(identifiers[0])
    assert before['status'] == 'notification_unknown'
    assert 'notified_at' not in before
    c.clock.advance(7)
    worker.notify(c.store, c.client, identifiers)
    saved = RequestStore(c.store.path).find(identifiers[0])
    assert saved['created_at'] == c.stamp.isoformat()
    assert saved['notified_at'] == c.clock.now().isoformat()
    assert telegram_api.reply_deadline(saved) == c.stamp + timedelta(minutes=30, seconds=7)
    assert saved['selected_at'] == c.row['selected_at']


@pytest.mark.parametrize('elapsed,armed', [(1799, False), (1800, True)])
def test_2959_vs_3000_requires_a_complete_current_run_poll(timed_case, elapsed, armed):
    c = timed_case
    notify_case(c)
    c.clock.advance(elapsed)
    assert poll(c) == []
    checked = c.store.find(c.identifier)
    assert checked['reply_checked_at'] == c.clock.now().isoformat()
    assert checked['reply_checked_run'] == '1000'
    assert worker.prepare(c.store, c.client, '1000') == (c.identifier if armed else '')
    saved = RequestStore(c.store.path).find(c.identifier)
    assert saved['products'] == [] and 'reply_update_id' not in saved
    assert saved['selected_at'] == c.row['selected_at']
    if armed:
        assert saved['publication_mode'] == 'without_products'
        assert saved['status'] == 'publishing'
        assert telegram_api.timeout_publication_allowed(saved, c.clock.now())
    else:
        assert saved['status'] == 'waiting' and 'publication_mode' not in saved


def test_waiting_longer_does_not_turn_a_before_deadline_poll_into_absence_proof(timed_case):
    c = timed_case
    notify_case(c)
    c.clock.advance(1799)
    poll(c)
    checked_at = c.store.find(c.identifier)['reply_checked_at']
    c.clock.advance(10)
    assert worker.prepare(c.store, c.client, '1000') == ''
    assert c.store.find(c.identifier)['reply_checked_at'] == checked_at
    poll(c)
    assert worker.prepare(c.store, c.client, '1000') == c.identifier


def test_poll_start_2959_cannot_become_a_timeout_poll_when_response_arrives_3005(timed_case):
    c = timed_case
    notify_case(c)
    c.clock.advance(1799)
    started = c.clock.now()
    def delayed_poll(offset):
        c.clock.advance(6)
        return []
    c.client.get_updates = Mock(side_effect=delayed_poll)
    assert worker.process_updates(c.store, c.client, run_id='1000') == []
    saved = RequestStore(c.store.path).find(c.identifier)
    assert saved['reply_checked_at'] == started.isoformat()
    assert c.clock.now() == c.stamp + timedelta(minutes=30, seconds=5)
    assert worker.prepare(c.store, c.client, '1000') == ''
    c.client.get_updates.assert_called_once()


@pytest.mark.parametrize('poll_run', [None, '', '999', 'not-a-run'])
def test_old_or_absent_run_binding_does_not_authorize_timeout(timed_case, poll_run):
    c = timed_case
    notify_case(c)
    c.clock.advance(1800)
    poll(c, run_id=poll_run)
    assert worker.prepare(c.store, c.client, '1000') == ''
    poll(c, run_id='1000')
    assert worker.prepare(c.store, c.client, '1000') == c.identifier


@pytest.mark.parametrize('count,allowed', [(99, True), (100, False)])
def test_full_backlog_page_cannot_prove_absence_or_keep_a_previous_marker(timed_case, count, allowed):
    c = timed_case
    notify_case(c)
    c.clock.advance(1800)
    poll(c)  # Exercise invalidation of an existing same-run success marker.
    assert c.store.find(c.identifier)['reply_checked_run'] == '1000'
    updates = [{'update_id': i} for i in range(1, count + 1)]
    assert poll(c, updates) == []
    saved = c.store.find(c.identifier)
    assert c.store.data['next_update_id'] == count + 1
    if not allowed:
        assert 'reply_checked_at' not in saved and 'reply_checked_run' not in saved
    assert worker.prepare(c.store, c.client, '1000') == (c.identifier if allowed else '')


def test_next_complete_poll_after_backlog_can_authorize_without_consuming_reply_twice(timed_case):
    c = timed_case
    notify_case(c)
    c.clock.advance(1800)
    poll(c, [{'update_id': i} for i in range(100)], run_id='1000')
    assert worker.prepare(c.store, c.client, '1000') == ''
    assert poll(c, run_id='1001') == []
    calls = [call for call in c.client._call.call_args_list if call.args[0] == 'getUpdates']
    assert len(calls) == 2 and calls[-1].args[1]['offset'] == 100
    assert worker.prepare(c.store, c.client, '1001') == c.identifier


@pytest.mark.parametrize('earlier_poll', [False, True])
def test_failed_poll_never_supplies_this_runs_absence_proof(timed_case, earlier_poll):
    c = timed_case
    notify_case(c)
    c.clock.advance(1800)
    if earlier_poll:
        poll(c, run_id='999')
    before = c.store.path.read_text()
    c.client.get_updates = Mock(side_effect=TelegramError('telegram_timeout'))
    with pytest.raises(TelegramError, match='telegram_timeout'):
        worker.process_updates(c.store, c.client, run_id='1000')
    c.client.get_updates.assert_called_once()
    assert c.store.path.read_text() == before
    assert worker.prepare(reload_store(c), c.client, '1000') == ''


@pytest.mark.parametrize('elapsed', [1799, 1800, 1900])
def test_valid_reply_received_before_arming_wins_over_elapsed_timeout(timed_case, elapsed):
    c = timed_case
    notify_case(c)
    c.clock.advance(elapsed)
    assert poll(c, [reply()]) == [c.identifier]
    assert worker.prepare(c.store, c.client, '1000') == c.identifier
    saved = RequestStore(c.store.path).find(c.identifier)
    assert saved['publication_mode'] == 'with_products'
    assert saved['products'][0]['name'] == '기록용 노트'
    assert saved['reply_update_id'] == 90
    assert not telegram_api.timeout_publication_allowed(saved, c.clock.now())


def test_ready_reply_has_priority_over_earlier_waiting_timeout_from_another_category(timed_case):
    c = timed_case
    notify_case(c)
    first = c.identifier
    rows = json.loads(c.path.read_text())
    rows.append({**c.row, 'post_id': 1725, 'category': '취업', 'keyword': '시험준비물',
                 'topic': '시험 준비물 안내'})
    c.path.write_text(json.dumps(rows))
    c.read.side_effect = lambda post_id, env: {**copy.deepcopy(c.post), 'id': post_id}
    identifiers = worker.register(c.store, c.client, c.env)
    assert len(identifiers) == 1
    second = identifiers[0]
    worker.notify(c.store, c.client, identifiers)  # Its request message is #43.
    c.clock.advance(1800)
    assert poll(c, [reply(message_id=43)]) == [second]
    assert telegram_api.timeout_ready(c.store.find(first), '1000', c.clock.now())
    assert worker.prepare(c.store, c.client, '1000') == second
    saved = RequestStore(c.store.path)
    assert saved.find(first)['status'] == 'waiting'
    assert saved.find(second)['publication_mode'] == 'with_products'


def test_malformed_reply_blocks_fallback_and_guidance_does_not_restart_timer(timed_case):
    c = timed_case
    notified = copy.deepcopy(notify_case(c))
    c.clock.advance(1800)
    invalid = reply()
    invalid['message']['text'] = 'https://link.coupang.com/a/abcd1234'
    assert poll(c, [invalid]) == []
    saved = c.store.find(c.identifier)
    assert saved['last_error'] == 'product_name_required'
    assert saved['notified_at'] == notified['notified_at']
    assert saved['message_key'] == notified['message_key']
    assert len(c.telegram['sent']) == 2  # Initial request and fixed format advice.
    assert worker.prepare(c.store, c.client, '1000') == ''
    c.clock.advance(1800)
    poll(c, run_id='1001')
    assert worker.prepare(c.store, c.client, '1001') == ''
    assert c.store.find(c.identifier)['notified_at'] == notified['notified_at']
    assert poll(c, [reply(update_id=91)], run_id='1002') == [c.identifier]
    assert worker.prepare(c.store, c.client, '1002') == c.identifier
    assert c.store.find(c.identifier)['publication_mode'] == 'with_products'


def test_supplementary_search_guidance_preserves_original_send_time_and_reply_binding(timed_case):
    c = timed_case
    notified = copy.deepcopy(notify_case(c))
    c.clock.advance(900)
    c.client.send_search_guidance(c.store.find(c.identifier))
    assert c.store.find(c.identifier) == notified
    assert RequestStore(c.store.path).find(c.identifier) == notified
    c.clock.advance(900)
    poll(c)
    assert worker.prepare(c.store, c.client, '1000') == c.identifier
    assert c.store.find(c.identifier)['notified_at'] == notified['notified_at']


@pytest.mark.parametrize('state', ['held', 'notification_unknown', 'pending_notification', 'legacy'])
def test_held_unknown_unnotified_and_legacy_requests_never_acquire_timeout_permission(timed_case, state):
    c = timed_case
    notify_case(c)
    record = c.store.find(c.identifier)
    if state == 'legacy':
        record.pop('notified_at')
    else:
        record['status'] = state
        if state in ('notification_unknown', 'pending_notification'):
            record['message_key'] = None
            record.pop('notified_at')
    c.store.save()
    c.clock.advance(1800)
    poll(c)
    assert worker.prepare(c.store, c.client, '1000') == ''
    assert c.store.find(c.identifier)['products'] == []
    assert 'publication_mode' not in c.store.find(c.identifier)


@pytest.mark.parametrize('elapsed,expected_status', [(24 * 3600, 'waiting'), (37 * 3600, 'held')])
def test_reply_retention_and_original_selection_expiry_cannot_be_extended(timed_case, elapsed, expected_status):
    c = timed_case
    notified = copy.deepcopy(notify_case(c))
    c.clock.advance(elapsed)
    poll(c)
    assert worker.prepare(c.store, c.client, '1000') == ''
    saved = c.store.find(c.identifier)
    assert saved['status'] == expected_status
    assert saved['notified_at'] == notified['notified_at']
    assert saved['selected_at'] == notified['selected_at']
    if expected_status == 'held':
        assert saved['last_error'] == 'request_expired'


def test_late_reply_after_arming_cannot_change_bound_no_product_publication(timed_case):
    c = timed_case
    notify_case(c)
    c.clock.advance(1800)
    poll(c)
    assert worker.prepare(c.store, c.client, '1000') == c.identifier
    armed = copy.deepcopy(c.store.find(c.identifier))
    c.clock.advance(1)
    assert poll(c, [reply()], run_id='1000') == []
    assert c.store.find(c.identifier) == armed
    publisher = Mock(return_value='https://trendpulse.blog/sample-draft/')
    worker.publish(c.store, c.client, c.identifier, c.env, publisher=publisher)
    publisher.assert_called_once()
    assert publisher.call_args.kwargs['affiliate_request']['products'] == []
    assert publisher.call_args.kwargs['affiliate_request']['publication_mode'] == 'without_products'


def test_previous_timeout_publication_intent_stays_held_on_restart_without_reposting(timed_case):
    c = timed_case
    notify_case(c)
    c.clock.advance(1800)
    poll(c)
    assert worker.prepare(c.store, c.client, '1000') == c.identifier
    assert worker.prepare(reload_store(c), c.client, '1001') == ''
    record = c.store.find(c.identifier)
    assert record['status'] == 'held' and record['last_error'] == 'publication_outcome_unknown'
    publisher = Mock()
    with pytest.raises(TelegramError, match='invalid_request'):
        worker.publish(c.store, c.client, c.identifier, {**c.env, 'GITHUB_RUN_ID': '1001'}, publisher=publisher)
    publisher.assert_not_called()


@pytest.mark.parametrize('elapsed,expected_total', [(0, 1800), (1799, 1), (1800, 0)])
def test_wait_for_reply_window_uses_only_bounded_fake_sleeps(timed_case, monkeypatch, elapsed, expected_total):
    c = timed_case
    notify_case(c)
    c.clock.advance(elapsed)
    sleep = Mock(side_effect=c.clock.advance)
    monkeypatch.setattr(worker.time, 'sleep', sleep)
    before_calls = c.client._call.call_count
    worker.wait_for_reply_window(c.store)
    pauses = [call.args[0] for call in sleep.call_args_list]
    assert sum(pauses) == expected_total and all(0 < pause <= 60 for pause in pauses)
    assert c.clock.now() == c.stamp + timedelta(minutes=30)
    assert c.client._call.call_count == before_calls
    assert 'reply_checked_at' not in c.store.find(c.identifier)


def test_wait_clock_rollback_cannot_sleep_beyond_single_thirty_minute_budget(timed_case, monkeypatch):
    c = timed_case
    notify_case(c)
    sleep = Mock(side_effect=lambda seconds: c.clock.advance(-seconds))
    monkeypatch.setattr(worker.time, 'sleep', sleep)
    worker.wait_for_reply_window(c.store)
    assert sleep.call_count == 30
    assert sum(call.args[0] for call in sleep.call_args_list) == 1800


@pytest.mark.parametrize('state', ['ready', 'invalid_reply', 'legacy'])
def test_wait_does_not_delay_ready_replies_or_requests_ineligible_for_timeout(timed_case, monkeypatch, state):
    c = timed_case
    notify_case(c)
    if state == 'ready':
        poll(c, [reply()])
    elif state == 'invalid_reply':
        c.store.find(c.identifier)['last_error'] = 'product_name_required'
    else:
        c.store.find(c.identifier).pop('notified_at')
    c.store.save()
    sleep = Mock(side_effect=AssertionError('no real or simulated waiting expected'))
    monkeypatch.setattr(worker.time, 'sleep', sleep)
    worker.wait_for_reply_window(c.store)
    sleep.assert_not_called()


def test_complete_timeout_flow_uses_same_draft_full_gates_and_durable_history_without_products(affiliate_case, monkeypatch):
    from scripts import publish_codex_draft as publisher_module
    from src import coupang_products

    c = affiliate_case
    clock = Clock(datetime.fromisoformat(c['brief']['selected_at']) + timedelta(seconds=1))
    monkeypatch.setattr(worker, 'now', clock.now)
    monkeypatch.setattr(telegram_api, 'utc_now', clock.now)
    monkeypatch.setattr(worker, 'DATA', c['data'])
    monkeypatch.setattr(worker, 'read_draft', lambda post_id, env: copy.deepcopy(c['original']))
    client, updates = fake_telegram()
    store = RequestStore(c['data'] / 'coupang_requests.json')
    env = {**c['env'], 'GITHUB_RUN_ID': '1000', 'BLOG_COUPANG_TELEGRAM': '1'}
    identifiers = worker.register(store, client, env)
    assert len(identifiers) == 1 and updates['sent'] == []
    identifier = identifiers[0]
    store = RequestStore(store.path)
    worker.notify(store, client, identifiers)
    notified = copy.deepcopy(RequestStore(store.path).find(identifier))
    clock.advance(1800)
    store = RequestStore(store.path)
    assert worker.process_updates(store, client, run_id='1000') == []
    store = RequestStore(store.path)
    assert worker.prepare(store, client, '1000') == identifier
    store = RequestStore(store.path)
    armed = copy.deepcopy(store.find(identifier))
    assert armed['publication_mode'] == 'without_products' and armed['products'] == []
    forbidden = {}
    for name in ('insert_products', 'products_preserved', 'review_products'):
        forbidden[name] = Mock(side_effect=AssertionError('no product operation in timeout flow'))
        monkeypatch.setattr(coupang_products, name, forbidden[name])
    url = worker.publish(store, client, identifier, env, publisher=publisher_module.publish_draft)
    assert url == 'https://trendpulse.blog/a1c-levels/'
    c['session'].post.assert_called_once()
    mutation = c['session'].post.call_args
    assert mutation.args[0].endswith('/posts/1724') and mutation.kwargs['allow_redirects'] is False
    payload = mutation.kwargs['json']
    assert payload['status'] == 'publish' and publisher_module._no_coupang_content(payload['content'])
    assert '공식 자료로 확인된 기준' in payload['content'] and '근거 없는 주장' not in payload['content']
    assert [call.args[0] for call in c['fetch'].call_args_list] == c['urls']
    prompts = [call.args[0] for call in c['client'].generate.call_args_list]
    assert sum('conservative Korean editorial fact checker' in prompt for prompt in prompts) == 2
    assert sum('correcting an existing Korean article' in prompt for prompt in prompts) == 1
    assert sum(prompt.startswith('최종 검색 의도 검수입니다.') for prompt in prompts) == 1
    assert c['quality'].call_count == c['editorial'].call_count == c['identity'].call_count == 1
    for call in forbidden.values():
        call.assert_not_called()
    saved = RequestStore(store.path).find(identifier)
    assert saved['status'] == 'published' and saved['publication_mode'] == 'without_products'
    assert saved['selected_at'] == notified['selected_at']
    assert saved['notified_at'] == notified['notified_at']
    queue = json.loads((c['data'] / 'topic_queue_general.json').read_text())
    assert queue[1]['status'] == 'completed' and queue[1]['affiliate_state'] == 'published'
    assert queue[1]['post_id'] == 1724 and queue[1]['selected_at'] == notified['selected_at']
    ledger = json.loads(publisher_module.market.LEDGER.read_text())
    assert len(ledger) == 1 and ledger[0]['post_id'] == 1724
    assert len(updates['sent']) == 2
    assert '쿠팡 상품 링크 없이 발행했습니다' in updates['sent'][-1]['text']
    updates['updates'] = [reply()]
    assert worker.process_updates(store, client, run_id='1001') == []
    assert worker.prepare(store, client, '1001') == ''
    with pytest.raises(TelegramError, match='invalid_request'):
        worker.publish(store, client, identifier, {**env, 'GITHUB_RUN_ID': '1001'},
                       publisher=publisher_module.publish_draft)
    c['session'].post.assert_called_once()
