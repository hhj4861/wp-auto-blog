"""Durable Telegram handoff contracts; every transport call is mocked."""
import copy
import hashlib
import json
from unittest.mock import Mock

import pytest
import requests

from src import coupang_telegram as telegram


ENV = {'TELEGRAM_BOT_TOKEN': '12345:' + 'x' * 30, 'TELEGRAM_CHAT_ID': '8123456789'}
PRODUCT = {'name': '국산 배즙', 'url': 'https://link.coupang.com/a/test_123'}
SELECTED = '2026-09-11T02:00:00+00:00'


@pytest.fixture(autouse=True)
def no_real_transport(monkeypatch):
    monkeypatch.setattr(telegram.requests, 'Session', Mock(side_effect=AssertionError('real HTTP forbidden')))


def store_record(tmp_path, *, status='pending_notification', post_id=1751):
    store = telegram.RequestStore(tmp_path / 'requests.json')
    record = store.create(post_id, '건강', '기관지에좋은음식', '기관지에 좋은 음식의 활용과 주의사항', 'a' * 64, SELECTED)
    if status != 'pending_notification':
        record['status'] = status
        record['message_key'] = telegram.TelegramClient(ENV).message_key(501)
        if status in {'ready', 'publishing', 'published'}:
            record['products'] = [dict(PRODUCT)]
        store.save()
    return store, record


def incoming(update_id=100, *, reply_id=501, chat_id=8123456789, sender_id=8123456789,
             chat_type='private', text=None):
    return {'update_id': update_id, 'message': {
        'message_id': 999, 'chat': {'id': chat_id, 'type': chat_type},
        'from': {'id': sender_id, 'is_bot': False},
        'reply_to_message': {'message_id': reply_id},
        'text': text if text is not None else PRODUCT['name'] + ' | ' + PRODUCT['url'],
    }}


def polling_client(updates, env=None):
    client = telegram.TelegramClient(env or ENV)
    client.check_webhook = Mock()
    client.get_updates = Mock(return_value=updates)
    client.send_feedback = Mock()
    return client


def transport(monkeypatch, *, result=None, status=200, raw=None, error=None, chunks=None):
    response = Mock(status_code=status)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.iter_content.return_value = chunks if chunks is not None else [
        raw if raw is not None else json.dumps({'ok': True, 'result': result}).encode()]
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    session.post = Mock(side_effect=error, return_value=response)
    monkeypatch.setattr(telegram.requests, 'Session', Mock(return_value=session))
    return session, response


def test_draft_fingerprint_uses_all_exact_edit_fields_and_ignores_unrelated_fields():
    post = {'id': 1751, 'status': 'draft', 'modified_gmt': '2026-09-11T01:00:00',
            'content': {'raw': '<p>배와 도라지</p>'}, 'title': {'raw': '제목'},
            'excerpt': {'raw': '요약'}, 'meta': {'keyword': '기관지에좋은음식'},
            'categories': [3], 'featured_media': 1750, 'slug': 'pear'}
    expected = hashlib.sha256(json.dumps(post, sort_keys=True, separators=(',', ':'),
                                          ensure_ascii=False).encode()).hexdigest()
    assert telegram.draft_fingerprint({**post, 'link': 'ignored'}) == expected
    for field in telegram.FINGERPRINT_FIELDS:
        changed = {**post, field: None}
        assert telegram.draft_fingerprint(changed) != expected
        with pytest.raises(ValueError, match='^invalid_draft_fingerprint$'):
            telegram.draft_fingerprint({key: value for key, value in post.items() if key != field})
    with pytest.raises(ValueError, match='^invalid_draft_fingerprint$'):
        telegram.draft_fingerprint({**post, 'meta': object()})


def test_create_is_atomic_idempotent_and_has_no_raw_telegram_identity(tmp_path):
    store, record = store_record(tmp_path)
    assert len(record['request_id']) == 32
    assert store.find(record['request_id']) is record
    assert store.find('missing') is None
    assert store.create(1751, record['category'], record['keyword'], record['topic'],
                        record['draft_fingerprint'], SELECTED) is record
    saved = telegram.RequestStore(store.path)
    assert saved.data == store.data
    assert set(saved.data) == {'schema_version', 'next_update_id', 'requests'}
    assert '8123456789' not in store.path.read_text()
    assert ENV['TELEGRAM_BOT_TOKEN'] not in store.path.read_text()


@pytest.mark.parametrize('field,value', [
    ('category', '생활정보'), ('keyword', '배즙효능'), ('topic', '다른 주제'),
    ('draft_fingerprint', 'b' * 64), ('selected_at', '2026-09-11T03:00:00+00:00'),
])
def test_same_post_conflicting_immutable_values_fail_closed(tmp_path, field, value):
    store, record = store_record(tmp_path)
    arguments = {key: record[key] for key in ('post_id', 'category', 'keyword', 'topic', 'draft_fingerprint', 'selected_at')}
    arguments[field] = value
    before = store.path.read_bytes()
    with pytest.raises(telegram.TelegramError, match='^request_conflict$'):
        store.create(**arguments)
    assert store.path.read_bytes() == before


@pytest.mark.parametrize('change', [
    {'selected_at': None}, {'selected_at': '2026-09-11'}, {'post_id': True},
    {'keyword': 'key\nsecret'}, {'request_id': 'a' * 16}, {'status': []},
    {'last_error': 'raw remote credentials'}, {'last_error': {}},
    {'message_key': 'raw-chat:123'}, {'publish_attempt_run': '123/error'},
    {'publish_attempt_run': '1' * 41}, {'publish_attempt_run': 123},
    {'publishing_at': '2026-09-11'}, {'chat_id': 8123456789},
    {'published_url': 'https://user:password@example.com/x'},
    {'published_url': 'https://example.com/\nsecret'},
])
def test_store_rejects_malformed_or_sensitive_fields(tmp_path, change):
    store, record = store_record(tmp_path)
    record.update(change)
    with pytest.raises(telegram.TelegramError, match='^invalid_request_store$'):
        store.save()


def test_store_validates_duplicate_records_json_keys_and_version(tmp_path):
    store, record = store_record(tmp_path)
    store.data['requests'].append(copy.deepcopy(record))
    with pytest.raises(telegram.TelegramError, match='^invalid_request_store$'):
        store.save()
    store.path.write_text('{"schema_version":1,"schema_version":1,"next_update_id":null,"requests":[]}')
    with pytest.raises(telegram.TelegramError, match='^invalid_request_store$'):
        telegram.RequestStore(store.path)


@pytest.mark.parametrize('reason', ['publication_failed', 'draft_changed', 'source_expired', 'request_expired',
                                   'review_failed', 'duplicate_keyword', 'publication_outcome_unknown',
                                   'wordpress_unavailable', 'invalid_queue'])
def test_worker_status_and_fixed_error_fields_round_trip(tmp_path, reason):
    store, record = store_record(tmp_path, status='ready')
    record.update(status='held', last_error=reason, publishing_at=SELECTED, publish_attempt_run='34567890123')
    store.save()
    assert telegram.RequestStore(store.path).data == store.data


def test_failed_atomic_replace_preserves_previous_file_and_cleans_temporary(monkeypatch, tmp_path):
    store, _ = store_record(tmp_path)
    original = store.path.read_bytes()
    store.data['next_update_id'] = 123
    monkeypatch.setattr(telegram.os, 'replace', Mock(side_effect=OSError('PRIVATE-PATH')))
    with pytest.raises(telegram.TelegramError, match='^request_store_write_failed$'):
        store.save()
    assert store.path.read_bytes() == original
    assert list(tmp_path.iterdir()) == [store.path]


@pytest.mark.parametrize('env,reason', [({}, 'telegram_not_configured'),
    ({**ENV, 'TELEGRAM_CHAT_ID': '0'}, 'telegram_invalid_configuration'),
    ({**ENV, 'TELEGRAM_CHAT_ID': '-123'}, 'telegram_invalid_configuration'),
    ({**ENV, 'TELEGRAM_CHAT_ID': '-123', 'TELEGRAM_ALLOWED_USER_ID': '0'}, 'telegram_invalid_configuration'),
    ({**ENV, 'TELEGRAM_BOT_TOKEN': 'token\nsecret'}, 'telegram_invalid_configuration'),
])
def test_configuration_requires_exact_chat_and_group_sender(env, reason):
    with pytest.raises(telegram.TelegramError, match='^' + reason + '$'):
        telegram.TelegramClient(env)


def test_telegram_transport_is_single_request_without_env_auth_redirect_or_long_poll(monkeypatch):
    session, response = transport(monkeypatch, result=[])
    client = telegram.TelegramClient(ENV)
    assert client.get_updates(None) == []
    session.post.assert_called_once()
    args, kwargs = session.post.call_args
    assert args[0].endswith('/getUpdates')
    assert session.trust_env is False
    assert kwargs == {'json': {'timeout': 0, 'limit': 100, 'allowed_updates': ['message']},
                      'timeout': 15, 'allow_redirects': False, 'stream': True}
    assert response.__exit__.called and session.__exit__.called
    assert ENV['TELEGRAM_BOT_TOKEN'] not in repr(client)
    session.post.reset_mock()
    client.get_updates(101)
    assert session.post.call_args.kwargs['json']['offset'] == 101


@pytest.mark.parametrize('status,reason', [(301, 'telegram_redirect_rejected'), (401, 'telegram_auth_error'),
    (403, 'telegram_auth_error'), (429, 'telegram_rate_limited'), (500, 'telegram_http_error')])
def test_http_failures_are_fixed_and_never_retried(monkeypatch, capsys, caplog, status, reason):
    session, _ = transport(monkeypatch, status=status, raw=b'PRIVATE-TOKEN-PAYLOAD')
    with pytest.raises(telegram.TelegramError, match='^' + reason + '$') as caught:
        telegram.TelegramClient(ENV).get_updates(None)
    session.post.assert_called_once()
    output = capsys.readouterr()
    assert 'PRIVATE' not in str(caught.value) + caplog.text + output.out + output.err


@pytest.mark.parametrize('error,reason', [(requests.Timeout('PRIVATE-TOKEN-URL'), 'telegram_timeout'),
    (requests.ConnectionError('PRIVATE-TOKEN-URL'), 'telegram_transport_error'),
    (requests.exceptions.SSLError('PRIVATE-TOKEN-URL'), 'telegram_transport_error')])
def test_transport_errors_remove_original_exception(monkeypatch, error, reason):
    session, _ = transport(monkeypatch, error=error)
    with pytest.raises(telegram.TelegramError, match='^' + reason + '$') as caught:
        telegram.TelegramClient(ENV).get_updates(None)
    assert caught.value.__suppress_context__
    session.post.assert_called_once()


@pytest.mark.parametrize('raw', [b'PRIVATE-NOT-JSON', b'{"ok":false,"description":"PRIVATE"}',
    b'{"ok":true,"ok":true,"result":[]}', b'{"ok":true,"result":[{"update_id":true}]}',
    b'{"ok":true,"result":{}}', b'x' * 1_000_001])
def test_malformed_or_oversize_response_fails_without_raw_data(monkeypatch, raw):
    session, _ = transport(monkeypatch, raw=raw)
    with pytest.raises(telegram.TelegramError, match='^telegram_invalid_response$'):
        telegram.TelegramClient(ENV).get_updates(None)
    session.post.assert_called_once()


def test_webhook_is_checked_without_delete_or_update_consumption(monkeypatch):
    session, _ = transport(monkeypatch, result={'url': 'https://private-webhook.example/secret'})
    with pytest.raises(telegram.TelegramError, match='^telegram_webhook_active$'):
        telegram.TelegramClient(ENV).check_webhook()
    assert session.post.call_count == 1
    assert session.post.call_args.args[0].endswith('/getWebhookInfo')


def test_send_request_and_feedback_target_only_configured_chat(monkeypatch, tmp_path):
    store, record = store_record(tmp_path)
    session, _ = transport(monkeypatch, result={'chat': {'id': 8123456789}, 'message_id': 501})
    client = telegram.TelegramClient(ENV)
    key = client.send_request(record)
    assert key == hashlib.sha256(b'8123456789:501').hexdigest()
    sent = session.post.call_args.kwargs['json']
    assert sent['chat_id'] == 8123456789
    assert '[쿠팡 링크 요청]' in sent['text'] and record['request_id'] in sent['text']
    assert all(str(record[field]) in sent['text'] for field in ('post_id', 'keyword', 'category', 'topic'))
    assert '최대 3줄' in sent['text'] and '답장: 상품명 | https://link.coupang.com/a/...' in sent['text']
    assert '만료되면 보류' in sent['text']
    assert '쿠팡에서 검색할 상품' in sent['text'] and '배즙' in sent['text']
    assert '선택 기준' in sent['text']
    assert sent['reply_markup'] == {'force_reply': True, 'selective': True}
    assert 'parse_mode' not in sent and sent['link_preview_options']['is_disabled']
    assert client.send_feedback(record, '발행 검수를 완료했습니다.') == key
    assert session.post.call_args.kwargs['json']['chat_id'] == 8123456789
    assert 'parse_mode' not in session.post.call_args.kwargs['json']
    with pytest.raises(telegram.TelegramError, match='^invalid_request$'):
        client.send_feedback(record, 'unsafe\x00text')


def test_search_supplement_keeps_original_request_reply_binding(monkeypatch, tmp_path):
    store, record = store_record(tmp_path, status='waiting')
    before = store.path.read_bytes()
    session, _ = transport(monkeypatch, result={'chat': {'id': 8123456789}, 'message_id': 700})
    client = telegram.TelegramClient(ENV)
    original_key = record['message_key']
    client.send_search_guidance(record)
    sent = session.post.call_args.kwargs['json']
    assert sent['chat_id'] == 8123456789
    assert '배즙' in sent['text'] and '원래의 [쿠팡 링크 요청]' in sent['text']
    assert str(record['post_id']) in sent['text'] and record['request_id'] in sent['text']
    assert '이 보충 안내에 답장하면 자동 처리되지 않습니다' in sent['text']
    assert 'reply_markup' not in sent
    assert record['message_key'] == original_key and store.path.read_bytes() == before
    receiver = polling_client([incoming(reply_id=700)])
    assert telegram.process_updates(store, receiver) == []
    assert record['status'] == 'waiting'
    receiver.get_updates.return_value = [incoming(update_id=101, reply_id=501)]
    assert telegram.process_updates(store, receiver) == [record['request_id']]


def test_search_supplement_requires_a_waiting_request(tmp_path):
    _, record = store_record(tmp_path)
    with pytest.raises(telegram.TelegramError, match='^invalid_request$'):
        telegram.TelegramClient(ENV).send_search_guidance(record)


def test_long_request_fields_fit_telegram_limit_and_retain_identity(monkeypatch, tmp_path):
    store = telegram.RequestStore(tmp_path / 'requests.json')
    record = store.create(1754, '건강', '대상포진초기증상' + '😀' * 490,
                          '대상포진 초기증상' + '😀' * 990, 'a' * 64, SELECTED)
    session, _ = transport(monkeypatch, result={'chat': {'id': 8123456789}, 'message_id': 501})
    telegram.TelegramClient(ENV).send_request(record)
    sent = session.post.call_args.kwargs['json']
    assert len(sent['text'].encode('utf-16-le')) // 2 <= 4096
    assert record['request_id'] in sent['text'] and '1754' in sent['text']
    assert '루즈핏 순면 티셔츠' in sent['text'] and '이 메시지에 답장' in sent['text']
    assert record['topic'].endswith('😀' * 990)


def test_notification_is_claimed_before_send_and_saved_waiting_after_success(tmp_path):
    store, record = store_record(tmp_path)
    client = polling_client([])
    def send(pending):
        assert pending['status'] == 'pending_notification'
        assert telegram.RequestStore(store.path).find(record['request_id'])['status'] == 'notification_unknown'
        return client.message_key(501)
    client.send_request = Mock(side_effect=send)
    assert telegram.notify_pending(store, client) == [record['request_id']]
    saved = telegram.RequestStore(store.path).find(record['request_id'])
    assert saved['status'] == 'waiting' and saved['message_key'] == client.message_key(501)
    assert 'last_error' not in saved
    assert telegram.notify_pending(store, client) == []
    client.send_request.assert_called_once()


def test_notification_unknown_is_persisted_and_never_automatically_resent(tmp_path, caplog):
    store, record = store_record(tmp_path)
    client = polling_client([])
    client.send_request = Mock(side_effect=RuntimeError('PRIVATE-URL-TOKEN'))
    with pytest.raises(telegram.TelegramError, match='^notification_delivery_unknown$'):
        telegram.notify_pending(store, client)
    reloaded = telegram.RequestStore(store.path)
    assert reloaded.find(record['request_id'])['last_error'] == 'notification_delivery_unknown'
    assert telegram.notify_pending(reloaded, client) == []
    client.send_request.assert_called_once()
    assert 'PRIVATE' not in store.path.read_text() + caplog.text


@pytest.mark.parametrize('failing_save', [1, 2])
def test_notification_save_failure_stops_and_leaves_no_resendable_success(monkeypatch, tmp_path, failing_save):
    store, record = store_record(tmp_path)
    client = polling_client([])
    client.send_request = Mock(return_value=client.message_key(501))
    real_save, saves = store.save, []
    def save():
        saves.append(1)
        if len(saves) == failing_save:
            raise telegram.TelegramError('request_store_write_failed')
        real_save()
    monkeypatch.setattr(store, 'save', save)
    with pytest.raises(telegram.TelegramError, match='^request_store_write_failed$'):
        telegram.notify_pending(store, client)
    assert client.send_request.call_count == failing_save - 1
    if failing_save == 2:
        assert telegram.RequestStore(store.path).find(record['request_id'])['status'] == 'notification_unknown'


def test_direct_authorized_reply_persists_only_products_update_id_and_hash(tmp_path):
    store, record = store_record(tmp_path, status='waiting')
    update = incoming()
    update['message']['private_extra'] = 'PRIVATE-RAW-ENVELOPE'
    client = polling_client([update])
    assert telegram.process_updates(store, client) == [record['request_id']]
    client.get_updates.assert_called_once_with(None)
    reloaded = telegram.RequestStore(store.path)
    saved = reloaded.find(record['request_id'])
    assert saved['status'] == 'ready' and saved['products'] == [PRODUCT]
    assert saved['reply_update_id'] == 100 and reloaded.data['next_update_id'] == 101
    raw = store.path.read_text()
    assert all(forbidden not in raw for forbidden in ('PRIVATE-RAW', '8123456789', 'reply_to_message', 'is_bot'))
    assert telegram.process_updates(reloaded, client) == []
    assert client.get_updates.call_args.args == (101,)


@pytest.mark.parametrize('mutation', ['other_chat', 'other_sender', 'bot', 'no_reply', 'wrong_reply',
                                     'reply_chat', 'edited', 'channel', 'bool_sender', 'bool_message_id', 'malformed_chat_type'])
def test_unbound_or_unauthorized_updates_are_ignored_but_offset_persisted(tmp_path, mutation):
    store, record = store_record(tmp_path, status='waiting')
    update = incoming()
    message = update['message']
    if mutation == 'other_chat': message['chat']['id'] += 1
    elif mutation == 'other_sender': message['from']['id'] += 1
    elif mutation == 'bot': message['from']['is_bot'] = True
    elif mutation == 'no_reply': message.pop('reply_to_message')
    elif mutation == 'wrong_reply': message['reply_to_message']['message_id'] += 1
    elif mutation == 'reply_chat': message['reply_to_message']['chat'] = {'id': 999}
    elif mutation == 'edited': update['edited_message'] = update.pop('message')
    elif mutation == 'channel': message['chat']['type'] = 'channel'
    elif mutation == 'bool_sender': message['from']['id'] = True
    elif mutation == 'bool_message_id': message['reply_to_message']['message_id'] = True
    elif mutation == 'malformed_chat_type': message['chat']['type'] = {}
    assert telegram.process_updates(store, polling_client([update])) == []
    assert record['status'] == 'waiting' and store.data['next_update_id'] == 101


def test_group_requires_allowed_user_and_private_cannot_override_sender(tmp_path):
    store, record = store_record(tmp_path)
    env = {**ENV, 'TELEGRAM_CHAT_ID': '-100123', 'TELEGRAM_ALLOWED_USER_ID': '456'}
    client = polling_client([], env)
    record.update(status='waiting', message_key=client.message_key(501))
    store.save()
    wrong = incoming(100, chat_id=-100123, sender_id=789, chat_type='supergroup')
    right = incoming(101, chat_id=-100123, sender_id=456, chat_type='supergroup')
    client.get_updates.return_value = [wrong, right]
    assert telegram.process_updates(store, client) == [record['request_id']]
    assert record['reply_update_id'] == 101
    private = telegram.TelegramClient({**ENV, 'TELEGRAM_ALLOWED_USER_ID': '456'})
    assert not private.is_allowed_message(incoming(sender_id=456)['message'])


def test_bad_products_wait_for_correct_reply_without_persisting_raw_text(tmp_path):
    store, record = store_record(tmp_path, status='waiting')
    client = polling_client([incoming(text='PRIVATE-USER-TEXT-WITHOUT-LINK')])
    assert telegram.process_updates(store, client) == []
    assert record['status'] == 'waiting' and record['last_error'] == 'invalid_product_format'
    assert 'PRIVATE' not in store.path.read_text()
    client.send_feedback.assert_called_once()
    assert client.send_feedback.call_args.args[0] is record
    assert '상품명 | https://link.coupang.com/a/...' in client.send_feedback.call_args.args[1]
    assert 'PRIVATE' not in client.send_feedback.call_args.args[1]
    client.get_updates.return_value = [incoming(101)]
    assert telegram.process_updates(store, client) == [record['request_id']]
    assert 'last_error' not in record


def test_invalid_reply_feedback_failure_preserves_waiting_error_and_offset(tmp_path, caplog):
    store, record = store_record(tmp_path, status='waiting')
    client = polling_client([incoming(text='PRIVATE-INVALID-REPLY')])
    client.send_feedback.side_effect = RuntimeError('PRIVATE-REMOTE-ERROR')
    assert telegram.process_updates(store, client) == []
    assert record['status'] == 'waiting' and record['last_error'] == 'invalid_product_format'
    assert telegram.RequestStore(store.path).data['next_update_id'] == 101
    client.get_updates.assert_called_once_with(None)
    assert 'PRIVATE' not in store.path.read_text() + caplog.text


def test_replay_and_out_of_order_updates_cannot_reassign_ready_request(tmp_path):
    store, first = store_record(tmp_path, status='waiting')
    second = store.create(1752, '취업', '전기기사시험일정', '다음 접수 일정', 'b' * 64, SELECTED)
    client = polling_client([])
    second.update(status='waiting', message_key=client.message_key(502))
    store.data['next_update_id'] = 100
    store.save()
    client.get_updates.return_value = [incoming(102, reply_id=502), incoming(99), incoming(100), incoming(100), incoming(103)]
    assert telegram.process_updates(store, client) == [first['request_id'], second['request_id']]
    assert first['reply_update_id'] == 100 and second['reply_update_id'] == 102
    assert store.data['next_update_id'] == 104


def test_poll_save_failure_does_not_acknowledge_or_poll_again(monkeypatch, tmp_path):
    store, _ = store_record(tmp_path, status='waiting')
    before = store.path.read_bytes()
    client = polling_client([incoming()])
    monkeypatch.setattr(store, 'save', Mock(side_effect=telegram.TelegramError('request_store_write_failed')))
    with pytest.raises(telegram.TelegramError, match='^request_store_write_failed$'):
        telegram.process_updates(store, client)
    client.get_updates.assert_called_once_with(None)
    assert store.path.read_bytes() == before


def test_webhook_error_prevents_poll_and_preserves_store(tmp_path):
    store, _ = store_record(tmp_path, status='waiting')
    before = store.path.read_bytes()
    client = polling_client([incoming()])
    client.check_webhook.side_effect = telegram.TelegramError('telegram_webhook_active')
    with pytest.raises(telegram.TelegramError, match='^telegram_webhook_active$'):
        telegram.process_updates(store, client)
    client.get_updates.assert_not_called()
    assert store.path.read_bytes() == before


def test_unknown_parser_error_is_redacted(monkeypatch, tmp_path):
    from src import coupang_products
    store, record = store_record(tmp_path, status='waiting')
    monkeypatch.setattr(coupang_products, 'parse_products', Mock(side_effect=ValueError('PRIVATE-PARSER-ERROR')))
    assert telegram.process_updates(store, polling_client([incoming()])) == []
    assert record['last_error'] == 'invalid_products'
    assert 'PRIVATE' not in store.path.read_text()
