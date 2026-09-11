"""Approval stages with real local stores/parsers; all remote effects are mocked.

Reloading the store models the checkout after CI's required commit boundary.
These tests do not run Git or prove GitHub's remote persistence themselves.
"""
import copy
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import coupang_telegram_worker as worker
from src.coupang_telegram import RequestStore, TelegramClient, TelegramError, draft_fingerprint
from tests.test_codex_draft import affiliate_case, market_case  # pytest fixtures, no remote I/O


def fake_telegram():
    client = TelegramClient({'TELEGRAM_BOT_TOKEN': '1234:' + 'a' * 30, 'TELEGRAM_CHAT_ID': '555'})
    state = {'updates': [], 'next_message': 41, 'sent': []}

    def call(method, payload):
        if method == 'getWebhookInfo':
            return {'url': ''}
        if method == 'getUpdates':
            return copy.deepcopy(state['updates'])
        if method == 'sendMessage':
            state['next_message'] += 1
            state['sent'].append(copy.deepcopy(payload))
            return {'message_id': state['next_message'], 'chat': {'id': 555}}
        raise AssertionError('Unexpected mocked Telegram operation')

    client._call = Mock(side_effect=call)
    return client, state


def reply(update_id=90, message_id=42):
    return {'update_id': update_id, 'message': {
        'message_id': 100, 'chat': {'id': 555, 'type': 'private'},
        'from': {'id': 555, 'is_bot': False},
        'reply_to_message': {'message_id': message_id},
        'text': '기록용 노트 | https://link.coupang.com/a/abcd1234',
    }}


@pytest.fixture
def worker_case(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = tmp_path / 'data'
    data.mkdir()
    monkeypatch.setattr(worker, 'DATA', data)
    stamp = datetime.now(timezone.utc)
    monkeypatch.setattr(worker, 'now', lambda: stamp)
    post = {'id': 1724, 'status': 'draft', 'modified_gmt': '2026-09-11T00:00:00',
            'content': {'raw': '<div class="wpab-article">본문</div>'},
            'title': {'raw': '검사 준비물 안내'}, 'excerpt': {'raw': '요약'}, 'meta': {},
            'categories': [46], 'featured_media': 1723, 'slug': 'sample-draft'}
    row = {'status': 'held_draft', 'affiliate_state': 'waiting', 'post_id': 1724,
           'category': '건강', 'keyword': '검사준비물', 'topic': '검사 준비물 안내',
           'selected_at': stamp.isoformat()}
    path = data / 'topic_queue_general.json'
    path.write_text(json.dumps([row]))
    store = RequestStore(data / 'coupang_requests.json')
    client, telegram = fake_telegram()
    read = Mock(return_value=copy.deepcopy(post))
    monkeypatch.setattr(worker, 'read_draft', read)
    env = {'GITHUB_RUN_ID': '1000', 'WP_GENERAL_URL': 'https://trendpulse.blog',
           'WP_GENERAL_USERNAME': 'test', 'WP_GENERAL_APP_PASSWORD': 'test',
           'BLOG_CODEX_HOME': '/tmp/test-codex-home'}
    return SimpleNamespace(data=data, path=path, stamp=stamp, post=post, row=row, store=store,
                           client=client, telegram=telegram, read=read, env=env)


def make_ready(c):
    identifiers = worker.register(c.store, c.client, c.env)
    worker.notify(c.store, c.client, identifiers)
    c.telegram['updates'] = [reply()]
    assert worker.process_updates(c.store, c.client) == identifiers
    return identifiers[0]


def test_approval_stages_reload_durable_intents_and_publish_the_same_real_draft(affiliate_case, monkeypatch):
    """Actual worker + store + Telegram parser + draft publisher; only transport/LLM are doubles."""
    from scripts.publish_codex_draft import publish_draft

    c = affiliate_case
    monkeypatch.setattr(worker, 'DATA', c['data'])
    monkeypatch.setattr(worker, 'read_draft', lambda post_id, env: copy.deepcopy(c['original']))
    store = RequestStore(c['data'] / 'coupang_requests.json')
    client, telegram = fake_telegram()
    env = {**c['env'], 'GITHUB_RUN_ID': '12345'}
    identifiers = worker.register(store, client, env)
    assert len(identifiers) == 1 and not telegram['sent']
    request_id = identifiers[0]
    # CI must commit both files at this boundary before the notify stage.
    store = RequestStore(store.path)
    pending = store.find(request_id)
    assert pending['status'] == 'notification_unknown'
    assert pending['draft_fingerprint'] == draft_fingerprint(c['original'])
    assert json.loads((c['data'] / 'topic_queue_general.json').read_text())[1]['affiliate_request_id'] == request_id
    worker.notify(store, client, identifiers)
    store = RequestStore(store.path)
    assert store.find(request_id)['status'] == 'waiting'
    telegram['updates'] = [reply()]
    assert worker.process_updates(store, client) == [request_id]
    store = RequestStore(store.path)
    assert store.find(request_id)['status'] == 'ready'
    assert worker.prepare(store, client, env['GITHUB_RUN_ID']) == request_id
    # CI must commit the publishing intent before this stage may touch WordPress.
    store = RequestStore(store.path)
    armed = copy.deepcopy(store.find(request_id))
    assert armed['status'] == 'publishing' and armed['publish_attempt_run'] == '12345'
    assert worker.publish(store, client, request_id, env, publisher=publish_draft) == 'https://trendpulse.blog/a1c-levels/'
    c['session'].post.assert_called_once()
    assert c['session'].post.call_args.args[0].endswith('/posts/1724')
    completed = RequestStore(store.path).find(request_id)
    assert completed['status'] == 'published' and completed['selected_at'] == armed['selected_at']
    queue = json.loads((c['data'] / 'topic_queue_general.json').read_text())
    assert queue[1]['status'] == 'completed' and queue[1]['affiliate_state'] == 'published'
    assert queue[1]['post_id'] == 1724
    ledger = json.loads((c['data'] / 'posted_market_keywords.json').read_text())
    assert len(ledger) == 1 and ledger[0]['post_id'] == 1724
    assert len(telegram['sent']) == 2  # Request plus completion, never another post.
    assert worker.process_updates(store, client) == []
    assert worker.prepare(store, client, '12346') == ''
    with pytest.raises(TelegramError, match='invalid_request'):
        worker.publish(store, client, request_id, {**env, 'GITHUB_RUN_ID': '12346'}, publisher=publish_draft)
    c['session'].post.assert_called_once()


def test_register_persists_notification_intent_before_any_message(worker_case):
    c = worker_case
    identifiers = worker.register(c.store, c.client, c.env)
    record = RequestStore(c.store.path).find(identifiers[0])
    assert record['status'] == 'notification_unknown' and record['message_key'] is None
    assert record['last_error'] == 'notification_delivery_unknown'
    assert c.telegram['sent'] == []
    c.read.assert_called_once_with(1724, c.env)
    assert json.loads(c.path.read_text())[0]['affiliate_request_id'] == identifiers[0]


def test_notification_unknown_is_not_armed_again_after_a_restart(worker_case):
    c = worker_case
    identifiers = worker.register(c.store, c.client, c.env)
    c.client.send_request = Mock(side_effect=TelegramError('telegram_timeout'))
    with pytest.raises(TelegramError, match='notification_delivery_unknown'):
        worker.notify(c.store, c.client, identifiers)
    restarted = RequestStore(c.store.path)
    assert restarted.find(identifiers[0])['status'] == 'notification_unknown'
    assert worker.register(restarted, c.client, c.env) == []
    worker.notify(restarted, c.client, [])
    c.client.send_request.assert_called_once()
    assert not (c.data / 'posted_market_keywords.json').exists()


def test_notification_success_save_failure_leaves_durable_unknown_without_resend(worker_case, monkeypatch):
    c = worker_case
    identifiers = worker.register(c.store, c.client, c.env)
    monkeypatch.setattr(c.store, 'save', Mock(side_effect=TelegramError('request_store_write_failed')))
    with pytest.raises(TelegramError, match='request_store_write_failed'):
        worker.notify(c.store, c.client, identifiers)
    restarted = RequestStore(c.store.path)
    assert restarted.find(identifiers[0])['status'] == 'notification_unknown'
    assert worker.register(restarted, c.client, c.env) == []
    assert len(c.telegram['sent']) == 1


def test_register_expired_draft_never_fetches_or_notifies(worker_case):
    c = worker_case
    c.row['selected_at'] = (c.stamp - timedelta(hours=37)).isoformat()
    c.path.write_text(json.dumps([c.row]))
    assert worker.register(c.store, c.client, c.env) == []
    c.read.assert_not_called()
    assert not c.telegram['sent'] and c.store.data['requests'] == []
    assert json.loads(c.path.read_text())[0]['affiliate_error'] == 'request_expired'


@pytest.mark.parametrize('failure', ['wordpress_unavailable', 'draft_changed'])
def test_register_isolates_one_bad_draft_and_preserves_other_notifications_and_replies(worker_case, failure):
    c = worker_case
    existing = worker.register(c.store, c.client, c.env)
    worker.notify(c.store, c.client, existing)
    rows = json.loads(c.path.read_text())
    rows += [{**c.row, 'post_id': 1725}, {**c.row, 'post_id': 1726}]
    c.path.write_text(json.dumps(rows))
    def read(post_id, env):
        if post_id == 1725:
            raise TelegramError(failure)
        return {**copy.deepcopy(c.post), 'id': post_id}
    c.read.side_effect = read
    new_ids = worker.register(c.store, c.client, c.env)
    assert len(new_ids) == 1
    assert c.store.find(new_ids[0])['post_id'] == 1726
    assert c.store.find(existing[0])['status'] == 'waiting'
    assert not any(record['post_id'] == 1725 for record in c.store.data['requests'])
    failed = json.loads(c.path.read_text())[1]
    assert failed['affiliate_state'] == 'held' and failed['affiliate_error'] == failure
    # The failed new draft does not prevent an already-notified draft's reply.
    c.telegram['updates'] = [reply()]
    assert worker.process_updates(c.store, c.client) == existing
    assert RequestStore(c.store.path).find(existing[0])['status'] == 'ready'


@pytest.mark.parametrize('stage', ['prepare', 'publish'])
def test_reply_expiry_keeps_original_selection_time_and_cannot_publish(worker_case, monkeypatch, stage):
    c = worker_case
    identifier = make_ready(c)
    before = c.store.find(identifier)['selected_at']
    if stage == 'publish':
        assert worker.prepare(c.store, c.client, '1000') == identifier
    monkeypatch.setattr(worker, 'now', lambda: c.stamp + timedelta(hours=37))
    publisher = Mock(side_effect=AssertionError('expired request must not publish'))
    if stage == 'prepare':
        assert worker.prepare(c.store, c.client, '1000') == ''
    else:
        with pytest.raises(TelegramError, match='request_expired'):
            worker.publish(c.store, c.client, identifier, c.env, publisher=publisher)
    record = RequestStore(c.store.path).find(identifier)
    assert record['status'] == 'held' and record['last_error'] == 'request_expired'
    assert record['selected_at'] == before
    assert json.loads(c.path.read_text())[0]['affiliate_state'] == 'held'
    publisher.assert_not_called()


def test_previous_publishing_intent_is_held_without_another_publication(worker_case):
    c = worker_case
    identifier = make_ready(c)
    worker.prepare(c.store, c.client, '999')
    restarted = RequestStore(c.store.path)
    publisher = Mock(side_effect=AssertionError('previous publication must not be repeated'))
    assert worker.prepare(restarted, c.client, '1000') == ''
    with pytest.raises(TelegramError, match='invalid_request'):
        worker.publish(restarted, c.client, identifier, c.env, publisher=publisher)
    record = RequestStore(c.store.path).find(identifier)
    assert record['status'] == 'held' and record['last_error'] == 'publication_outcome_unknown'
    assert json.loads(c.path.read_text())[0]['status'] == 'held_draft'
    publisher.assert_not_called()


def test_prepare_arms_only_one_of_multiple_ready_categories(worker_case):
    c = worker_case
    first = make_ready(c)
    other = c.store.create(1725, '취업', '시험준비물', '시험 준비물 안내', 'a' * 64, c.row['selected_at'])
    other.update(status='ready', message_key='b' * 64,
                 products=[{'name': '기록용 노트', 'url': 'https://link.coupang.com/a/another'}])
    c.store.save()
    rows = json.loads(c.path.read_text())
    rows.append({**c.row, 'post_id': 1725, 'category': '취업'})
    c.path.write_text(json.dumps(rows))
    assert worker.prepare(c.store, c.client, '1000') == first
    records = RequestStore(c.store.path).data['requests']
    assert [row['status'] for row in records] == ['publishing', 'ready']
    assert [row['affiliate_state'] for row in json.loads(c.path.read_text())] == ['publishing', 'ready']


@pytest.mark.parametrize('state', ['ready', 'wrong_run'])
def test_publish_requires_an_armed_intent_bound_to_current_run(worker_case, state):
    c = worker_case
    identifier = make_ready(c)
    if state == 'wrong_run':
        worker.prepare(c.store, c.client, '999')
    publisher = Mock()
    with pytest.raises(TelegramError, match='invalid_request'):
        worker.publish(c.store, c.client, identifier, c.env, publisher=publisher)
    publisher.assert_not_called()


def test_publisher_error_is_sanitized_and_stays_held_without_retry(worker_case, capsys):
    c = worker_case
    identifier = make_ready(c)
    worker.prepare(c.store, c.client, '1000')
    publisher = Mock(side_effect=RuntimeError('PRIVATE-REPLY-AUTH-ERROR'))
    with pytest.raises(TelegramError, match='publication_failed') as error:
        worker.publish(c.store, c.client, identifier, c.env, publisher=publisher)
    assert error.value.__suppress_context__
    publisher.assert_called_once()
    assert publisher.call_args.args[0] == 1724
    configured = publisher.call_args.args[1]
    assert configured['BLOG_MODE'] == 'queue' and configured['BLOG_CATEGORY'] == '건강'
    assert configured['BLOG_PUBLISH'] == 'true' and configured['BLOG_WRITER_PROVIDER'] == 'codex'
    assert c.store.find(identifier)['status'] == 'held'
    assert json.loads(c.path.read_text())[0]['affiliate_error'] == 'publication_failed'
    output = capsys.readouterr()
    assert 'PRIVATE' not in output.out + output.err + c.store.path.read_text() + str(c.telegram['sent'])
    assert worker.prepare(RequestStore(c.store.path), c.client, '1001') == ''


def test_success_feedback_failure_does_not_change_publication_state_or_retry(worker_case, capsys):
    c = worker_case
    identifier = make_ready(c)
    worker.prepare(c.store, c.client, '1000')
    c.client.send_feedback = Mock(side_effect=TelegramError('telegram_timeout'))
    publisher = Mock(return_value='https://trendpulse.blog/sample-draft/')
    assert worker.publish(c.store, c.client, identifier, c.env, publisher=publisher).endswith('/sample-draft/')
    assert RequestStore(c.store.path).find(identifier)['status'] == 'published'
    publisher.assert_called_once()
    assert 'durable post state retained' in capsys.readouterr().out


def test_state_save_failure_after_publish_recovers_as_unknown_not_a_second_post(worker_case, monkeypatch):
    c = worker_case
    identifier = make_ready(c)
    worker.prepare(c.store, c.client, '1000')
    publisher = Mock(return_value='https://trendpulse.blog/sample-draft/')
    monkeypatch.setattr(c.store, 'save', Mock(side_effect=TelegramError('request_store_write_failed')))
    with pytest.raises(TelegramError, match='request_store_write_failed'):
        worker.publish(c.store, c.client, identifier, c.env, publisher=publisher)
    restarted = RequestStore(c.store.path)
    assert restarted.find(identifier)['status'] == 'publishing'
    assert worker.prepare(restarted, c.client, '1001') == ''
    with pytest.raises(TelegramError):
        worker.publish(restarted, c.client, identifier, {**c.env, 'GITHUB_RUN_ID': '1001'}, publisher=publisher)
    publisher.assert_called_once()


@pytest.mark.parametrize('value', [None, '', 'not-a-date', '2026-01-01', '2026-01-01T00:00:00'])
def test_invalid_expiry_is_closed(worker_case, value):
    assert worker.expired({'selected_at': value})


def test_main_never_logs_untrusted_exceptions(worker_case, monkeypatch, capsys):
    c = worker_case
    monkeypatch.setattr(worker, 'load_dotenv', lambda: None)
    monkeypatch.setattr(worker, 'TelegramClient', lambda env: c.client)
    monkeypatch.setattr(worker, 'register', Mock(side_effect=RuntimeError('PRIVATE-EXCEPTION-TEXT')))
    monkeypatch.setattr('sys.argv', ['worker', 'register'])
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    assert worker.main() == 1
    output = capsys.readouterr()
    assert 'operation_failed' in output.out and 'PRIVATE' not in output.out + output.err


def test_main_refuses_nonmain_actions_before_client_or_store(worker_case, monkeypatch):
    monkeypatch.setattr(worker, 'load_dotenv', lambda: None)
    client = Mock(side_effect=AssertionError('no client on feature branch'))
    monkeypatch.setattr(worker, 'TelegramClient', client)
    monkeypatch.setattr('sys.argv', ['worker', 'receive'])
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.setenv('GITHUB_REF', 'refs/heads/feature')
    assert worker.main() == 1
    client.assert_not_called()
