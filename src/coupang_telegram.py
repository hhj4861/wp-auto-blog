"""Telegram replies bind to one durable draft request, never to the latest post."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from datetime import datetime, timezone
import unicodedata
import uuid

import requests

from src.coupang_search_guidance import product_search_guidance


ERRORS = {
    'telegram_not_configured', 'telegram_invalid_configuration', 'telegram_webhook_active',
    'telegram_timeout', 'telegram_transport_error', 'telegram_http_error',
    'telegram_rate_limited', 'telegram_auth_error', 'telegram_redirect_rejected',
    'telegram_invalid_response', 'invalid_request_store', 'request_store_unavailable',
    'request_store_write_failed', 'request_conflict', 'invalid_request',
    'notification_delivery_unknown', 'invalid_products', 'product_name_required',
    'invalid_product_format', 'invalid_product_name', 'invalid_product_url',
    'duplicate_product_url', 'publication_failed', 'draft_changed', 'source_expired',
    'request_expired', 'review_failed', 'duplicate_keyword',
    'publication_outcome_unknown', 'wordpress_unavailable', 'invalid_queue',
}
PRODUCT_ERRORS = {
    'invalid_products', 'product_name_required', 'invalid_product_format',
    'invalid_product_name', 'invalid_product_url', 'duplicate_product_url',
}
STATUSES = {'pending_notification', 'notification_unknown', 'waiting', 'ready',
            'publishing', 'published', 'held'}
RECORD_FIELDS = {
    'request_id', 'post_id', 'category', 'keyword', 'topic', 'draft_fingerprint',
    'selected_at', 'created_at', 'status', 'message_key', 'products',
}
OPTIONAL_FIELDS = {'last_error', 'reply_update_id', 'published_at', 'published_url',
                   'publish_attempt_run', 'publishing_at'}
FINGERPRINT_FIELDS = ('id', 'status', 'modified_gmt', 'content', 'title', 'excerpt',
                      'meta', 'categories', 'featured_media', 'slug')


class TelegramError(RuntimeError):
    def __init__(self, reason: str):
        self.reason = reason if reason in ERRORS else 'telegram_invalid_response'
        super().__init__(self.reason)


def _integer(value, *, minimum=0):
    return type(value) is int and minimum <= value <= 2**63 - 1


def _text(value, maximum):
    return (isinstance(value, str) and bool(value.strip()) and len(value) <= maximum
            and not any(unicodedata.category(char).startswith('C')
                        or char in '\u2028\u2029' for char in value))


def _hex(value, length):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{' + str(length) + '}', value) is not None


def _timestamp(value):
    try:
        stamp = datetime.fromisoformat(value) if isinstance(value, str) else None
        return bool(stamp and stamp.tzinfo is not None and stamp.utcoffset() is not None)
    except (ValueError, OverflowError):
        return False


def draft_fingerprint(post) -> str:
    """Fingerprint the exact REST edit snapshot; values are never included in errors."""
    try:
        if not isinstance(post, dict) or any(key not in post for key in FINGERPRINT_FIELDS):
            raise ValueError
        raw = json.dumps({key: post[key] for key in FINGERPRINT_FIELDS}, sort_keys=True,
                         separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()
    except (TypeError, ValueError, OverflowError, UnicodeError):
        raise ValueError('invalid_draft_fingerprint') from None


def _validate_record(record):
    if (not isinstance(record, dict) or not RECORD_FIELDS <= set(record)
            or set(record) - RECORD_FIELDS - OPTIONAL_FIELDS
            or not _hex(record['request_id'], 32) or not _integer(record['post_id'], minimum=1)
            or not _text(record['category'], 100) or not _text(record['keyword'], 500)
            or not _text(record['topic'], 1000) or not _hex(record['draft_fingerprint'], 64)
            or not _timestamp(record['selected_at']) or not _timestamp(record['created_at'])
            or not isinstance(record['status'], str) or record['status'] not in STATUSES
            or not isinstance(record['products'], list)):
        raise TelegramError('invalid_request_store')
    status, key = record['status'], record['message_key']
    if key is not None and not _hex(key, 64):
        raise TelegramError('invalid_request_store')
    if ((status in {'waiting', 'ready', 'publishing', 'published'} and key is None)
            or (status in {'pending_notification', 'notification_unknown'} and key is not None)
            or (status in {'pending_notification', 'notification_unknown', 'waiting'} and record['products'])):
        raise TelegramError('invalid_request_store')
    if record['products'] or status in {'ready', 'publishing', 'published'}:
        from src.coupang_products import validate_products
        try:
            if validate_products(record['products']) != record['products']:
                raise ValueError
        except (ValueError, TypeError):
            raise TelegramError('invalid_request_store') from None
    if ('last_error' in record and (not isinstance(record['last_error'], str)
                                  or record['last_error'] not in ERRORS)
            or 'reply_update_id' in record and not _integer(record['reply_update_id'])
            or 'published_at' in record and not _timestamp(record['published_at'])
            or 'publishing_at' in record and not _timestamp(record['publishing_at'])
            or 'publish_attempt_run' in record and (
                not isinstance(record['publish_attempt_run'], str)
                or re.fullmatch(r'[0-9]{1,40}', record['publish_attempt_run']) is None)):
        raise TelegramError('invalid_request_store')
    if 'published_url' in record:
        from urllib.parse import urlsplit
        try:
            value = record['published_url']
            url = urlsplit(value) if isinstance(value, str) else None
            if (not _text(value, 2048) or any(char.isspace() for char in value)
                    or not url or url.scheme != 'https' or not url.hostname
                    or url.username or url.password or url.port not in (None, 443)):
                raise ValueError
        except (ValueError, TypeError):
            raise TelegramError('invalid_request_store') from None


def _validate_store(data):
    if (not isinstance(data, dict) or set(data) != {'schema_version', 'next_update_id', 'requests'}
            or type(data['schema_version']) is not int or data['schema_version'] != 1
            or data['next_update_id'] is not None and not _integer(data['next_update_id'])
            or not isinstance(data['requests'], list)):
        raise TelegramError('invalid_request_store')
    ids, posts, keys = set(), set(), set()
    for record in data['requests']:
        _validate_record(record)
        if record['request_id'] in ids or record['post_id'] in posts:
            raise TelegramError('invalid_request_store')
        ids.add(record['request_id'])
        posts.add(record['post_id'])
        key = record['message_key']
        if key is not None:
            if key in keys:
                raise TelegramError('invalid_request_store')
            keys.add(key)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


class RequestStore:
    """A single writer owns data; callers persist it before the next Telegram poll."""
    def __init__(self, path):
        self.path = Path(path)
        self.data = self.load()

    def load(self):
        try:
            raw = self.path.read_text(encoding='utf-8')
        except FileNotFoundError:
            data = {'schema_version': 1, 'next_update_id': None, 'requests': []}
        except (OSError, UnicodeError):
            raise TelegramError('request_store_unavailable') from None
        else:
            try:
                data = json.loads(raw, object_pairs_hook=_unique_object)
            except (ValueError, TypeError):
                raise TelegramError('invalid_request_store') from None
        _validate_store(data)
        self.data = data
        return data

    def save(self):
        _validate_store(self.data)
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                             prefix='.' + self.path.name + '.', delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(self.data, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        except (OSError, ValueError, TypeError, UnicodeError):
            raise TelegramError('request_store_write_failed') from None
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def find(self, request_id):
        return next((row for row in self.data['requests'] if row['request_id'] == request_id), None)

    def create(self, post_id, category, keyword, topic, draft_fingerprint, selected_at):
        record = {'request_id': uuid.uuid4().hex, 'post_id': post_id, 'category': category,
                  'keyword': keyword, 'topic': topic, 'draft_fingerprint': draft_fingerprint,
                  'selected_at': selected_at, 'created_at': datetime.now(timezone.utc).isoformat(),
                  'status': 'pending_notification', 'message_key': None, 'products': []}
        _validate_record(record)
        for existing in self.data['requests']:
            if existing['post_id'] == post_id:
                if any(existing[key] != record[key] for key in
                       ('category', 'keyword', 'topic', 'draft_fingerprint', 'selected_at')):
                    raise TelegramError('request_conflict')
                return existing
        self.data['requests'].append(record)
        try:
            self.save()
        except Exception:
            self.data['requests'].remove(record)
            raise
        return record


class TelegramClient:
    def __init__(self, env=None):
        env = os.environ if env is None else env
        token, chat = env.get('TELEGRAM_BOT_TOKEN'), env.get('TELEGRAM_CHAT_ID')
        if not token or not chat:
            raise TelegramError('telegram_not_configured')
        if (not isinstance(token, str) or not re.fullmatch(r'[0-9]{1,20}:[A-Za-z0-9_-]{20,200}', token)
                or not isinstance(chat, str) or not re.fullmatch(r'-?[1-9][0-9]{0,18}', chat)):
            raise TelegramError('telegram_invalid_configuration')
        self._token, self._chat_id = token, int(chat)
        if abs(self._chat_id) > 2**63 - 1:
            raise TelegramError('telegram_invalid_configuration')
        user = env.get('TELEGRAM_ALLOWED_USER_ID')
        if self._chat_id < 0:
            if not isinstance(user, str) or not re.fullmatch(r'[1-9][0-9]{0,18}', user):
                raise TelegramError('telegram_invalid_configuration')
            self._user_id = int(user)
            if self._user_id > 2**63 - 1:
                raise TelegramError('telegram_invalid_configuration')
        else:
            self._user_id = self._chat_id

    def _call(self, method, payload):
        try:
            # No browser cookies, netrc credentials, environment proxies or automatic retries.
            with requests.Session() as session:
                session.trust_env = False
                with session.post(f'https://api.telegram.org/bot{self._token}/{method}',
                                  json=payload, timeout=15, allow_redirects=False, stream=True) as response:
                    if 300 <= response.status_code < 400:
                        raise TelegramError('telegram_redirect_rejected')
                    if response.status_code in (401, 403):
                        raise TelegramError('telegram_auth_error')
                    if response.status_code == 429:
                        raise TelegramError('telegram_rate_limited')
                    if response.status_code != 200:
                        raise TelegramError('telegram_http_error')
                    raw = bytearray()
                    for chunk in response.iter_content(16384):
                        raw.extend(chunk)
                        if len(raw) > 1_000_000:
                            raise TelegramError('telegram_invalid_response')
                    data = json.loads(bytes(raw), object_pairs_hook=_unique_object)
            if not isinstance(data, dict) or data.get('ok') is not True or 'result' not in data:
                raise TelegramError('telegram_invalid_response')
            return data['result']
        except requests.Timeout:
            raise TelegramError('telegram_timeout') from None
        except requests.RequestException:
            raise TelegramError('telegram_transport_error') from None
        except (ValueError, TypeError, UnicodeError):
            raise TelegramError('telegram_invalid_response') from None

    def message_key(self, message_id):
        if not _integer(message_id, minimum=1):
            raise TelegramError('telegram_invalid_response')
        return hashlib.sha256(f'{self._chat_id}:{message_id}'.encode()).hexdigest()

    def check_webhook(self):
        result = self._call('getWebhookInfo', {})
        if not isinstance(result, dict) or not isinstance(result.get('url'), str):
            raise TelegramError('telegram_invalid_response')
        if result['url']:
            raise TelegramError('telegram_webhook_active')

    def send_request(self, record):
        _validate_record(record)
        if record['status'] != 'pending_notification':
            raise TelegramError('invalid_request')
        def display(value, maximum):
            return value if len(value) <= maximum else value[:maximum] + '…'
        guidance = product_search_guidance(record['category'], record['keyword'], record['topic'])
        text = ('[쿠팡 링크 요청]\n'
                f"요청: {record['request_id']}\n카테고리: {display(record['category'], 30)}\n"
                f"키워드: {display(record['keyword'], 120)}\n주제: {display(record['topic'], 240)}\n"
                f"초안 ID: {record['post_id']}\n\n{guidance}\n\n"
                '이 메시지에 답장: 상품명 | https://link.coupang.com/a/...\n'
                '상품별 한 줄, 최대 3줄로 보내주세요.\n'
                '상품 링크를 검수한 뒤 같은 초안을 발행합니다. 출처·선정 근거가 만료되면 보류합니다.')
        result = self._call('sendMessage', {'chat_id': self._chat_id, 'text': text,
                                           'link_preview_options': {'is_disabled': True},
                                           'reply_markup': {'force_reply': True, 'selective': True}})
        if (not isinstance(result, dict) or not isinstance(result.get('chat'), dict)
                or type(result['chat'].get('id')) is not int or result['chat']['id'] != self._chat_id):
            raise TelegramError('telegram_invalid_response')
        return self.message_key(result.get('message_id'))

    def send_search_guidance(self, record):
        """Supplement an already-sent request without replacing its reply binding."""
        _validate_record(record)
        if record['status'] != 'waiting':
            raise TelegramError('invalid_request')
        guidance = product_search_guidance(record['category'], record['keyword'], record['topic'])
        return self.send_feedback(record,
            f"[상품 검색 안내] 초안 ID: {record['post_id']}\n\n{guidance}\n\n"
            f"상품을 고르면 원래의 [쿠팡 링크 요청] (초안 {record['post_id']})에 답장해 주세요.\n"
            '이 보충 안내에 답장하면 자동 처리되지 않습니다.\n'
            '답장 형식: 상품명 | https://link.coupang.com/a/...\n상품별 한 줄, 최대 3줄입니다.')

    def get_updates(self, offset):
        if offset is not None and not _integer(offset):
            raise TelegramError('invalid_request')
        payload = {'timeout': 0, 'limit': 100, 'allowed_updates': ['message']}
        if offset is not None:
            payload['offset'] = offset
        updates = self._call('getUpdates', payload)
        if (not isinstance(updates, list) or len(updates) > 100
                or any(not isinstance(row, dict) or not _integer(row.get('update_id')) for row in updates)):
            raise TelegramError('telegram_invalid_response')
        return updates

    def send_feedback(self, record, text):
        _validate_record(record)
        if (not isinstance(text, str) or not text.strip() or len(text) > 3000
                or any((unicodedata.category(char).startswith('C') and char != '\n')
                       or char in '\u2028\u2029' for char in text)):
            raise TelegramError('invalid_request')
        result = self._call('sendMessage', {
            'chat_id': self._chat_id,
            'text': f"[쿠팡링크요청상태] {record['request_id']}\n{text}",
            'link_preview_options': {'is_disabled': True},
        })
        if (not isinstance(result, dict) or not isinstance(result.get('chat'), dict)
                or type(result['chat'].get('id')) is not int or result['chat']['id'] != self._chat_id):
            raise TelegramError('telegram_invalid_response')
        return self.message_key(result.get('message_id'))

    def is_allowed_message(self, message):
        if not isinstance(message, dict):
            return False
        chat, sender = message.get('chat'), message.get('from')
        return (isinstance(chat, dict) and isinstance(sender, dict)
                and type(chat.get('id')) is int and chat['id'] == self._chat_id
                and isinstance(chat.get('type'), str)
                and chat.get('type') in ({'private'} if self._chat_id > 0 else {'group', 'supergroup'})
                and type(sender.get('id')) is int and sender['id'] == self._user_id
                and sender.get('is_bot') is False)


def notify_pending(store, client):
    _validate_store(store.data)
    notified = []
    for record in store.data['requests']:
        if record['status'] != 'pending_notification':
            continue
        pending = dict(record)
        # Persist the uncertainty before the request. A failed success-save must
        # not leave a pending record that would blindly resend on the next run.
        record.update(status='notification_unknown', last_error='notification_delivery_unknown')
        store.save()
        try:
            key = client.send_request(pending)
            if not _hex(key, 64):
                raise TelegramError('telegram_invalid_response')
        except Exception:
            record['status'] = 'notification_unknown'
            record['last_error'] = 'notification_delivery_unknown'
            store.save()
            raise TelegramError('notification_delivery_unknown') from None
        record.update(message_key=key, status='waiting')
        record.pop('last_error', None)
        store.save()  # A failed local save after remote success must propagate.
        notified.append(record['request_id'])
    return notified


def process_updates(store, client):
    """One poll only: persisting this store externally must precede the next call."""
    _validate_store(store.data)
    client.check_webhook()
    offset = store.data['next_update_id']
    updates = client.get_updates(offset)
    if (not isinstance(updates, list) or len(updates) > 100
            or any(not isinstance(row, dict) or not _integer(row.get('update_id')) for row in updates)):
        raise TelegramError('telegram_invalid_response')
    ready, seen = [], set()
    next_offset = offset
    for update in sorted(updates, key=lambda row: row['update_id']):
        update_id = update['update_id']
        if update_id in seen or offset is not None and update_id < offset:
            continue
        seen.add(update_id)
        next_offset = max(next_offset or 0, update_id + 1)
        message = update.get('message')
        if not client.is_allowed_message(message):
            continue
        reply = message.get('reply_to_message')
        if not isinstance(reply, dict) or not _integer(reply.get('message_id'), minimum=1):
            continue
        if 'chat' in reply and (not isinstance(reply['chat'], dict)
                               or type(reply['chat'].get('id')) is not int
                               or reply['chat'].get('id') != message['chat']['id']):
            continue
        key = client.message_key(reply['message_id'])
        record = next((row for row in store.data['requests']
                       if row['status'] == 'waiting' and row['message_key'] == key), None)
        if record is None:
            continue
        from src.coupang_products import parse_products
        try:
            products = parse_products(message.get('text'))
        except (ValueError, TypeError) as error:
            reason = str(error)
            record['last_error'] = reason if reason in PRODUCT_ERRORS else 'invalid_products'
            try:
                client.send_feedback(record,
                    '상품명 | https://link.coupang.com/a/... 형식으로 원래 요청 메시지에 다시 답장해 주세요. '
                    '상품별 한 줄, 최대 3줄입니다.')
            except Exception:
                # Advice is optional; failed delivery must not lose the consumed
                # reply's safe state or cause another poll in this invocation.
                pass
            continue
        record.update(status='ready', products=products, reply_update_id=update_id)
        record.pop('last_error', None)
        ready.append(record['request_id'])
    store.data['next_update_id'] = next_offset
    store.save()
    return ready
