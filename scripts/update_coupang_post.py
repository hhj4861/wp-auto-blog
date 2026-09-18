"""Add reviewed products to one already-public post; never regenerate or republish it."""
from copy import deepcopy
from html import escape
import json
from pathlib import Path

from bs4 import BeautifulSoup
import requests

from scripts import publish_codex_draft as draft
from src.codex_client import CodexSubscriptionClient
from src.coupang_policy import is_product_promotion, no_coupang_content
from src.coupang_products import insert_products, products_preserved, review_products
from src.coupang_telegram import _validate_record, published_post_fingerprint

DATA = Path('data')


def _brief(request):
    matches = [row for row in draft._rows(DATA / 'topic_queue_general.json')
               if row.get('post_id') == request['post_id']]
    if len(matches) != 1:
        raise draft.AffiliateDraftError('request_binding_mismatch')
    brief = matches[0]
    if (brief.get('status') != 'completed' or brief.get('post_status') != 'publish'
            or brief.get('source') != draft.market.SOURCE or not is_product_promotion(brief)
            or brief.get('affiliate_flow') != 'post_update'
            or brief.get('affiliate_state') != 'publishing'
            or brief.get('affiliate_request_id') != request['request_id']
            or brief.get('url') != request['post_url']
            or any(brief.get(key) != request.get(key)
                   for key in ('category', 'keyword', 'topic', 'selected_at'))):
        raise draft.AffiliateDraftError('request_binding_mismatch')
    return brief


def update_post(post_id, env, *, affiliate_request):
    """Only a durable, run-bound reply can update the published snapshot it names."""
    try:
        return _update_post(post_id, env, deepcopy(affiliate_request))
    except draft.AffiliateDraftError:
        raise
    except Exception:
        raise draft.AffiliateDraftError('verification_unavailable') from None


def _update_post(post_id, env, request):
    _validate_record(request)
    if (env.get('WP_GENERAL_URL', '').rstrip('/') != 'https://trendpulse.blog'
            or type(post_id) is not int or post_id != request['post_id']
            or request.get('affiliate_flow') != 'post_update'
            or request['status'] != 'publishing' or not request['products']
            or request.get('publish_attempt_run') != env.get('GITHUB_RUN_ID')
            or 'reply_update_id' not in request or request.get('last_error')):
        raise draft.AffiliateDraftError('invalid_request')
    brief = _brief(request)
    endpoint = f'https://trendpulse.blog/wp-json/wp/v2/posts/{post_id}'
    with requests.Session() as session:
        session.trust_env = False
        session.auth = (env['WP_GENERAL_USERNAME'], env['WP_GENERAL_APP_PASSWORD'])
        session.headers['User-Agent'] = 'Mozilla/5.0 (TrendPulse product update)'

        def read():
            post = draft._json(session.get(endpoint, params={'context': 'edit'},
                                           timeout=60, allow_redirects=False))
            if not draft._confirmed_publication(post_id, post) or post['link'] != request['post_url']:
                raise draft.AffiliateDraftError('unexpected_post_status')
            return post

        original = read()
        if published_post_fingerprint(original) != request['draft_fingerprint']:
            raise draft.AffiliateDraftError('request_binding_mismatch')
        body = original['content']['raw']
        if not no_coupang_content(body):
            raise draft.AffiliateDraftError('unexpected_affiliate_content')
        soup = BeautifulSoup(body, 'html.parser')
        if not soup.select_one('.wpab-article') or not soup.select_one('#quick-answer'):
            raise draft.AffiliateDraftError('verification_unavailable')
        products, request_id = request['products'], request['request_id']
        updated = insert_products(body, products, request_id=request_id)
        # Compare normalized HTML after removing exactly our two inserted nodes.
        # No metadata generation, body repair or title/date/status mutations.
        stripped = BeautifulSoup(draft._remove_owned_coupang_content(updated), 'html.parser')
        if str(stripped) != str(soup) or not products_preserved(updated, products, request_id=request_id):
            raise draft.AffiliateDraftError('products_changed')
        client = CodexSubscriptionClient(home=env['BLOG_CODEX_HOME'], model=env.get('BLOG_CODEX_MODEL', ''))
        title = draft._text(original, 'title')
        if review_products(products, title=title, category=brief['category'],
                           body=updated, call_llm=client.generate):
            raise draft.AffiliateDraftError('product_review_failed')
        # Refresh official sources to review the commercial addition in context;
        # keyword selection age is irrelevant to an already-public article.
        sources = draft._required_sources(brief)
        review_body = '<h1>' + escape(title) + '</h1>' + updated
        if not sources or draft.review_evidence(review_body, sources, client.generate):
            raise draft.AffiliateDraftError('product_review_failed')
        if _brief(request) != brief or published_post_fingerprint(read()) != request['draft_fingerprint']:
            raise draft.AffiliateDraftError('request_binding_mismatch')
        backup = DATA / 'editorial-backups' / f'coupang-update-{post_id}-{request_id}.json'
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(json.dumps(original, ensure_ascii=False), encoding='utf-8')

        # One write only. Even a lost response is reconciled by readback, never retried.
        try:
            draft._json(session.post(endpoint, json={'content': updated}, timeout=60, allow_redirects=False))
        except Exception:
            pass
        try:
            saved = read()
            unchanged = ('title', 'excerpt', 'meta', 'categories', 'featured_media', 'slug',
                         'date', 'date_gmt', 'status', 'link')
            if (draft._text(saved, 'content') != updated
                    or any(saved.get(key) != original.get(key) for key in unchanged)
                    or not products_preserved(saved['content']['raw'], products, request_id=request_id)):
                raise ValueError
        except Exception:
            raise draft.AffiliateDraftError('publication_unconfirmed') from None
        return saved['link']
