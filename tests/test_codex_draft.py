import copy
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

import pytest

from scripts import publish_codex_draft as module


def test_metadata_is_generated_from_existing_body():
    post = {'title': {'raw': '면접 Guide'}, 'content': {'raw': '<p>실제 경험을 설명하세요.</p>'}}
    meta = {'title': '면접 자기소개 작성법', 'focus_keyphrase': '면접 자기소개', 'meta_description': '설명'}
    call = Mock(return_value=json.dumps(meta))
    assert module.prepare_metadata(post, call) == meta
    assert '실제 경험을 설명하세요.' in call.call_args.args[0]


@pytest.mark.parametrize('outcome', ['success', 'review_failure', 'concurrent_edit', 'published'])
def test_recovery_preserves_body_and_checks_before_writing(tmp_path, monkeypatch, outcome):
    monkeypatch.chdir(tmp_path)
    body = '<div class="wpab-article"><section id="quick-answer">요약</section><section id="verified-sources"><a href="https://example.go.kr/source">자료</a></section></div>'
    original = {'id': 1713, 'status': 'publish' if outcome == 'published' else 'draft', 'slug': 'draft-slug',
        'title': {'raw': '면접 Guide'}, 'content': {'raw': body}, 'excerpt': {}, 'meta': {}, 'modified_gmt': 'old'}
    current = copy.deepcopy(original)
    if outcome == 'concurrent_edit': current['modified_gmt'] = 'new'
    saved = dict(original, status='publish', link='https://trendpulse.blog/draft-slug/')
    session = Mock()
    session.headers = {}
    session.get.side_effect = [Mock(json=lambda x=x: x) for x in (original, current, saved)]
    monkeypatch.setattr(module.requests, 'Session', lambda: session)
    monkeypatch.setattr(module, 'fetch_source', lambda url: {'url': url})
    monkeypatch.setattr(module, 'CodexSubscriptionClient', lambda **kwargs: Mock())
    monkeypatch.setattr(module, 'prepare_metadata', lambda *args: {'title': '면접 자기소개', 'focus_keyphrase': '면접', 'meta_description': '설명'})
    monkeypatch.setattr(module, 'check_quality', lambda *args: [])
    monkeypatch.setattr(module, 'editorial_checks', lambda *args: [])
    monkeypatch.setattr(module, 'validate_identity', lambda *args: [])
    monkeypatch.setattr(module, 'review_evidence', lambda *args: ['unsupported'] if outcome == 'review_failure' else [])
    from src.pipeline import BlogPipeline
    monkeypatch.setattr(BlogPipeline, '_load_post_registry', lambda self: [])
    monkeypatch.setattr(BlogPipeline, '_save_to_registry', Mock())
    env = {'WP_GENERAL_URL': 'https://trendpulse.blog', 'WP_GENERAL_USERNAME': 'test',
           'WP_GENERAL_APP_PASSWORD': 'test', 'BLOG_CODEX_HOME': str(tmp_path)}
    if outcome == 'success':
        assert module.publish_draft(1713, env) == saved['link']
        payload = session.post.call_args.kwargs['json']
        assert payload['status'] == 'publish'
        assert 'content' not in payload
    else:
        with pytest.raises(RuntimeError): module.publish_draft(1713, env)
        session.post.assert_not_called()


@pytest.fixture
def market_case(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = tmp_path / 'data'
    data.mkdir()
    monkeypatch.setattr(module.market, 'LEDGER', data / 'posted_market_keywords.json')
    keyword = '당화혈색소정상수치'
    topic = keyword + ': 정상과 진단 기준'
    urls = ['https://www.diabetes.or.kr/source', 'https://www.diabetes.or.kr/faq']
    body = ('<div class="wpab-article"><section id="quick-answer"><p>' + keyword
            + ' 안내</p></section><h2 id="levels">확인 기준</h2><p>근거 없는 주장</p>'
            + '<section id="verified-sources">'
            + ''.join(f'<a href="{url}">자료</a>' for url in urls) + '</section></div>')
    brief = {'source': module.market.SOURCE, 'selection_version': 4, 'category': '건강',
             'keyword': keyword, 'keywords': [keyword], 'topic': topic, 'intent': '기준 확인',
             'gap': '진단과 관리 목표의 차이', 'status': 'held_draft',
             'selected_at': datetime.now(timezone.utc).isoformat(), 'monthly_search': 24610,
             'score': 50, 'source_url': urls[0], 'evidence_mode': 'serp',
             'verified_sources': [{'url': url, 'excerpt': '저장된 이전 근거'} for url in urls],
             'organic_results': [{'url': urls[0]}], 'organic_domains': ['diabetes.or.kr'],
             'intent_results': [urls[0]]}
    original = {'id': 1724, 'status': 'draft', 'slug': 'a1c-levels', 'title': {'raw': topic},
                'content': {'raw': body}, 'excerpt': {'raw': '설명'}, 'meta': {},
                'modified_gmt': 'original', 'categories': [46], 'featured_media': 1723}
    queue = [dict(brief, status='superseded'), brief]
    registry = [{'topic': topic, 'title': topic, 'keywords': [keyword], 'category': '건강'}]
    (data / 'topic_queue_general.json').write_text(json.dumps(queue), encoding='utf-8')
    (data / 'post_registry_general.json').write_text(json.dumps(registry), encoding='utf-8')
    sources = [{'url': url, 'excerpt': '최신 공식 자료로 확인된 기준', 'checked_on': '2026-09-10'} for url in urls]
    fetch = Mock(side_effect=lambda url: copy.deepcopy(next(source for source in sources if source['url'] == url)))
    monkeypatch.setattr(module, 'fetch_source', fetch)
    state = {'current': copy.deepcopy(original), 'posted': False, 'post_status': 200,
             'live': [copy.deepcopy(original)], 'readback_change': {}, 'read_calls': 0}
    session = Mock()
    session.headers = {}

    def response(payload, status=200, headers=None):
        result = Mock(status_code=status, headers=headers or {})
        result.json.return_value = copy.deepcopy(payload)
        return result

    def get(url, **kwargs):
        if url.endswith('/posts/1724'):
            state['read_calls'] += 1
            result = copy.deepcopy(original if state['read_calls'] == 1 else state['current'])
            if state['posted']:
                result.update(state['readback_change'])
            return response(result)
        if url.endswith('/categories/46'):
            return response({'id': 46, 'name': '건강'})
        if url.endswith('/media/1723'):
            return response({'id': 1723, 'media_type': 'image', 'source_url': 'https://trendpulse.blog/image.png'})
        if url.endswith('/posts'):
            return response(state['live'], headers={'X-WP-TotalPages': '1'})
        raise AssertionError(url)

    def post(url, json, **kwargs):
        assert url.endswith('/posts/1724')
        state['posted'] = True
        state['current'].update(status=json['status'], title={'raw': json['title']},
                                content={'raw': json['content']}, meta=json['meta'],
                                excerpt={'raw': json['excerpt']},
                                link='https://trendpulse.blog/a1c-levels/')
        return response(state['current'], state['post_status'])

    session.get.side_effect = get
    session.post.side_effect = post
    monkeypatch.setattr(module.requests, 'Session', lambda: session)
    metadata = {'title': topic, 'focus_keyphrase': keyword, 'meta_description': keyword + ' 설명'}

    def generate(prompt):
        if 'JSON만 반환: {"title"' in prompt:
            return json.dumps(metadata)
        if 'correcting an existing Korean article' in prompt:
            payload = json.loads(prompt.split('\n', 1)[1])
            assert all(source['excerpt'] == '최신 공식 자료로 확인된 기준' for source in payload['sources'])
            return payload['article'].replace('근거 없는 주장', '공식 자료로 확인된 기준')
        if 'conservative Korean editorial fact checker' in prompt:
            return json.dumps({'issues': ['공식 근거 없는 주장 삭제'] if '근거 없는 주장' in prompt else []})
        raise AssertionError('Unexpected mocked prompt')

    client = Mock(generate=Mock(side_effect=generate))
    monkeypatch.setattr(module, 'CodexSubscriptionClient', lambda **kwargs: client)
    quality, editorial, identity = Mock(return_value=[]), Mock(return_value=[]), Mock(return_value=[])
    monkeypatch.setattr(module, 'check_quality', quality)
    monkeypatch.setattr(module, 'editorial_checks', editorial)
    monkeypatch.setattr(module, 'validate_identity', identity)
    from src.pipeline import BlogPipeline
    monkeypatch.setattr(BlogPipeline, '_load_post_registry', lambda self: [])
    registry_write = Mock()
    monkeypatch.setattr(BlogPipeline, '_save_to_registry', registry_write)
    env = {'WP_GENERAL_URL': 'https://trendpulse.blog', 'WP_GENERAL_USERNAME': 'test',
           'WP_GENERAL_APP_PASSWORD': 'test', 'BLOG_CODEX_HOME': str(tmp_path),
           'BLOG_MODE': 'queue', 'BLOG_CATEGORY': '건강'}
    return locals()


def test_market_recovery_uses_actual_repair_and_duplicate_helpers_once(market_case):
    c = market_case
    assert module.publish_draft(1724, c['env']) == 'https://trendpulse.blog/a1c-levels/'
    payload = c['session'].post.call_args.kwargs
    assert payload['allow_redirects'] is False
    assert payload['json']['content'] != c['body']
    assert '근거 없는 주장' not in payload['json']['content']
    assert 'slug' not in payload['json'] and 'featured_media' not in payload['json']
    c['session'].post.assert_called_once()
    assert [call.args[0] for call in c['fetch'].call_args_list] == c['urls']
    assert c['quality'].call_count == c['editorial'].call_count == c['identity'].call_count == 1
    assert len([call for call in c['client'].generate.call_args_list
                if 'correcting an existing Korean article' in call.args[0]]) == 1
    queue = json.loads((c['data'] / 'topic_queue_general.json').read_text())
    assert queue[0]['status'] == 'superseded'
    assert queue[1]['status'] == 'completed' and queue[1]['post_id'] == 1724
    assert queue[1]['selected_at'] == c['brief']['selected_at']
    ledger = json.loads((c['data'] / 'posted_market_keywords.json').read_text())
    assert ledger[0]['post_id'] == 1724 and ledger[0]['keyword'] == c['keyword']
    c['registry_write'].assert_called_once()


@pytest.mark.parametrize('kind', ['live', 'queue', 'registry', 'ledger'])
def test_market_recovery_never_excludes_another_duplicate(market_case, kind):
    c = market_case
    duplicate = {'keyword': c['keyword'], 'topic': c['topic'], 'title': c['topic'],
                 'keywords': [c['keyword']], 'category': '건강', 'status': 'completed'}
    if kind == 'live':
        c['state']['live'].append({'id': 2000, 'title': {'raw': '2025 당화 혈색소 정상 수치 안내'}, 'meta': {}})
    else:
        name = {'queue': 'topic_queue_general.json', 'registry': 'post_registry_general.json',
                'ledger': 'posted_market_keywords.json'}[kind]
        path = c['data'] / name
        rows = json.loads(path.read_text()) if path.exists() else []
        rows.append(duplicate)
        path.write_text(json.dumps(rows))
    with pytest.raises(RuntimeError, match='Duplicate|Ambiguous'):
        module.publish_draft(1724, c['env'])
    c['session'].post.assert_not_called()
    c['client'].generate.assert_not_called()


@pytest.mark.parametrize('field', ['modified_gmt', 'content', 'title', 'meta', 'categories', 'featured_media', 'slug', 'status'])
def test_market_recovery_blocks_concurrent_edits(market_case, field):
    c = market_case
    c['state']['current'][field] = 'changed'
    with pytest.raises(RuntimeError, match='changed during review'):
        module.publish_draft(1724, c['env'])
    c['session'].post.assert_not_called()


@pytest.mark.parametrize('kind', ['failed_source', 'blank_source', 'stored_blank', 'stale', 'wrong_id', 'ambiguous', 'missing', 'wrong_mode', 'wrong_category'])
def test_market_recovery_holds_invalid_brief_or_sources_before_llm(market_case, kind):
    c = market_case
    if kind == 'failed_source':
        c['fetch'].side_effect = [c['sources'][0], None]
    elif kind == 'blank_source':
        c['sources'][1]['excerpt'] = ' '
    elif kind == 'wrong_mode':
        c['env']['BLOG_MODE'] = 'general'
    elif kind == 'wrong_category':
        c['env']['BLOG_CATEGORY'] = '취업'
    else:
        path = c['data'] / 'topic_queue_general.json'
        queue = json.loads(path.read_text())
        if kind == 'stored_blank': queue[1]['verified_sources'][1]['excerpt'] = ''
        if kind == 'stale': queue[1]['selected_at'] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        if kind == 'wrong_id': queue[1]['post_id'] = 1725
        if kind == 'ambiguous': queue.append(copy.deepcopy(queue[1]))
        if kind == 'missing': queue = []
        path.write_text(json.dumps(queue))
    with pytest.raises(RuntimeError): module.publish_draft(1724, c['env'])
    c['session'].post.assert_not_called()
    c['client'].generate.assert_not_called()


@pytest.mark.parametrize('gate', ['quality', 'editorial', 'identity', 'evidence'])
def test_market_recovery_requires_all_gates_after_the_single_repair(market_case, monkeypatch, gate):
    c = market_case
    if gate == 'evidence':
        monkeypatch.setattr(module, 'review_evidence', Mock(return_value=['still unsupported']))
    else:
        c[gate].return_value = ['repaired content failed']
    with pytest.raises(RuntimeError, match='publication checks failed'):
        module.publish_draft(1724, c['env'])
    c['session'].post.assert_not_called()
    assert len([call for call in c['client'].generate.call_args_list
                if 'correcting an existing Korean article' in call.args[0]]) == 1


def test_market_recovery_does_not_repair_without_evidence_issues(market_case, monkeypatch):
    c = market_case
    monkeypatch.setattr(module, 'review_evidence', Mock(return_value=[]))
    repair = Mock(side_effect=AssertionError('must not repair'))
    monkeypatch.setattr(module, 'repair_evidence', repair)
    module.publish_draft(1724, c['env'])
    repair.assert_not_called()
    assert c['session'].post.call_args.kwargs['json']['content'] == c['body']


def test_market_recovery_rejects_update_redirect_without_retry(market_case):
    c = market_case
    c['state']['post_status'] = 302
    with pytest.raises(RuntimeError, match='redirect'):
        module.publish_draft(1724, c['env'])
    c['session'].post.assert_called_once()
    assert not (c['data'] / 'posted_market_keywords.json').exists()


@pytest.mark.parametrize('change', [{'id': 1725}, {'slug': 'other'}, {'featured_media': 0},
                                   {'content': {'raw': 'wrong'}}, {'status': 'draft'}, {'meta': {}},
                                   {'meta': {'_yoast_wpseo_focuskw': '당화혈색소정상수치',
                                             '_yoast_wpseo_metadesc': '근거 없는 옛 설명'}},
                                   {'excerpt': {'raw': '근거 없는 옛 설명'}}])
def test_market_recovery_verifies_published_readback(market_case, change):
    c = market_case
    c['state']['readback_change'] = change
    with pytest.raises(RuntimeError): module.publish_draft(1724, c['env'])
    c['session'].post.assert_called_once()
    # A confirmed publish response is durable even when the following readback fails.
    assert (c['data'] / 'posted_market_keywords.json').exists()
    assert json.loads((c['data'] / 'topic_queue_general.json').read_text())[1]['status'] == 'held_draft'


def test_market_recovery_duplicate_lookup_failure_is_closed(market_case):
    c = market_case
    original_get = c['session'].get.side_effect
    def get(url, **kwargs):
        if url.endswith('/posts'):
            raise module.requests.ConnectionError('unavailable')
        return original_get(url, **kwargs)
    c['session'].get.side_effect = get
    with pytest.raises(module.requests.ConnectionError): module.publish_draft(1724, c['env'])
    c['session'].post.assert_not_called()


def test_market_recovery_regenerates_only_derived_faq_from_repaired_visible_answers(market_case):
    c = market_case
    from bs4 import BeautifulSoup
    from src.monetization import insert_faq_schema
    faq = ('<h2 id="faq">자주 묻는 질문</h2><h3>당화혈색소 검사는 무엇인가요?</h3>'
           '<p>근거 없는 주장 대신 확인해야 하는 내용입니다.</p><h3>검사 기준은 어디서 확인하나요?</h3>'
           '<p>공식 자료로 확인된 기준을 읽어 보세요.</p>')
    other = '<style>.wpab-article{color:black}</style><script type="application/ld+json">{"@type":"Article","name":"글"}</script>'
    body = insert_faq_schema(c['body'].replace('<section id="verified-sources">', faq + '<section id="verified-sources">')) + other
    c['original']['content']['raw'] = body
    c['state']['current']['content']['raw'] = body
    module.publish_draft(1724, c['env'])
    saved = c['session'].post.call_args.kwargs['json']['content']
    soup = BeautifulSoup(saved, 'html.parser')
    schemas = [json.loads(node.string) for node in soup.find_all('script', type='application/ld+json')]
    faq_schema = next(schema for schema in schemas if schema.get('@type') == 'FAQPage')
    assert len(faq_schema['mainEntity']) == 2
    assert '근거 없는 주장' not in json.dumps(faq_schema, ensure_ascii=False)
    assert {'@type': 'Article', 'name': '글'} in schemas
    assert str(soup.style) == '<style>.wpab-article{color:black}</style>'
    metadata_prompt = next(call.args[0] for call in c['client'].generate.call_args_list
                           if 'JSON만 반환: {"title"' in call.args[0])
    assert '근거 없는 주장' not in metadata_prompt


@pytest.mark.parametrize('schema', [
    {'@graph': [{'@type': 'FAQPage'}, {'@type': 'Article'}]},
    {'@type': ['FAQPage', 'Article']},
    [{'@type': 'FAQPage'}, {'@type': 'Article'}],
])
def test_market_recovery_refuses_ambiguous_faq_graphs(market_case, schema):
    c = market_case
    c['original']['content']['raw'] += '<script type="application/ld+json">' + json.dumps(schema) + '</script>'
    with pytest.raises(RuntimeError, match='Mixed FAQ'):
        module.publish_draft(1724, c['env'])
    c['session'].post.assert_not_called()


def test_market_recovery_checks_metadata_facts_and_never_retries_repair(market_case):
    c = market_case
    c['metadata']['meta_description'] = '근거 없는 주장'
    with pytest.raises(RuntimeError, match='publication checks failed'):
        module.publish_draft(1724, c['env'])
    c['session'].post.assert_not_called()
    assert len([call for call in c['client'].generate.call_args_list
                if 'correcting an existing Korean article' in call.args[0]]) == 1


def test_market_recovery_checks_original_expiry_immediately_before_mutation(market_case, monkeypatch):
    c = market_case
    fresh = Mock(side_effect=[True, True, False])
    monkeypatch.setattr(module.market, 'fresh_market_item', fresh)
    with pytest.raises(RuntimeError, match='expired or invalid'):
        module.publish_draft(1724, c['env'])
    assert all(call.args[0]['status'] == 'pending' and call.args[0]['selected_at'] == c['brief']['selected_at']
               for call in fresh.call_args_list)
    c['session'].post.assert_not_called()


def test_market_recovery_preserves_ledger_when_readback_times_out(market_case):
    c = market_case
    original_get = c['session'].get.side_effect
    def get(url, **kwargs):
        if c['state']['posted']:
            raise module.requests.Timeout('readback timeout')
        return original_get(url, **kwargs)
    c['session'].get.side_effect = get
    with pytest.raises(module.requests.Timeout): module.publish_draft(1724, c['env'])
    c['session'].post.assert_called_once()
    assert json.loads((c['data'] / 'posted_market_keywords.json').read_text())[0]['post_id'] == 1724
    assert json.loads((c['data'] / 'topic_queue_general.json').read_text())[1]['status'] == 'held_draft'


def test_market_recovery_requires_existing_featured_media(market_case):
    c = market_case
    c['original']['featured_media'] = 0
    with pytest.raises(RuntimeError, match='featured media unavailable'):
        module.publish_draft(1724, c['env'])
    c['session'].post.assert_not_called()


def test_market_metadata_cannot_choose_another_keyword():
    post = {'title': {'raw': '건강 정보'}, 'content': {'raw': '<p>본문</p>'}}
    call = Mock(return_value=json.dumps({'title': '다른키워드 정보', 'focus_keyphrase': '다른키워드', 'meta_description': '설명'}))
    with pytest.raises(ValueError, match='changed the market keyword'):
        module.prepare_metadata(post, call, keyword='당화혈색소정상수치')


def test_registry_exception_never_folds_another_year_into_this_draft(market_case):
    c = market_case
    c['original']['title']['raw'] = '2026 ' + c['topic']
    path = c['data'] / 'post_registry_general.json'
    rows = json.loads(path.read_text())
    rows[0]['title'] = '2025 ' + c['topic']
    path.write_text(json.dumps(rows))
    with pytest.raises(RuntimeError, match='Duplicate market keyword'):
        module.publish_draft(1724, c['env'])
    c['session'].post.assert_not_called()
