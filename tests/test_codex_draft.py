import copy
import json
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
