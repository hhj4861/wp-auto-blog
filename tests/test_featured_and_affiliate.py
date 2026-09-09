from unittest.mock import Mock, patch

import pytest

from src.monetization import insert_coupang_prep_box, _valid_coupang_url
from src.wordpress_client import WordPressClient, WPConfig, PostStatus
from src.image_fetcher import FetchedImage, ImageSource


@pytest.mark.parametrize('images', [[], [FetchedImage('https://images.example/a.jpg', '면접', '', ImageSource.PEXELS, 1200, 800)]])
def test_missing_or_failed_thumbnail_saves_draft(images):
    client = WordPressClient(WPConfig('https://trendpulse.blog', 'user', 'pass'))
    content = Mock(title='면접 자기소개', html='<h2>소개</h2><p>본문</p>',
                   keywords=['면접'], meta_description='', focus_keyphrase='', slug_hint='intro')
    response = Mock(status_code=200, headers={'Content-Type': 'application/json'})
    response.json.return_value = {'id': 1, 'link': 'https://trendpulse.blog/intro',
                                  'title': {'rendered': '면접 자기소개'}, 'status': 'draft'}
    with patch.object(client, '_upload_media', return_value=(None, None)), \
         patch.object(client, '_prepare_content', return_value=content.html), \
         patch.object(client, '_request_with_retry', return_value=response) as request, \
         patch('requests.put'):
        post = client.create_post(content, images, status=PostStatus.PUBLISH,
                                  require_featured_image=True, skip_hero_image=True)
    assert post.status == PostStatus.DRAFT
    payload = next(c.kwargs['json'] for c in request.call_args_list if c.args[0] == 'POST' and '/posts' in c.args[1])
    assert payload['status'] == 'draft'


def test_topic_matching_and_idempotent_disclosure():
    body = '<h2>준비</h2><p>내용</p><h2>마무리</h2>'
    assert insert_coupang_prep_box(body, topic='면접 1분 자기소개') == body
    out = insert_coupang_prep_box(body, topic='면접 복장 체크리스트')
    assert '면접용 구두' in out
    assert '토익스피킹' not in out
    assert 'sponsored' in out and 'coupang-disclosure' in out
    assert insert_coupang_prep_box(out, topic='면접 복장 체크리스트') == out


def test_only_configured_short_tracking_links_accepted():
    assert _valid_coupang_url('https://link.coupang.com/a/abc')
    assert not _valid_coupang_url('https://evilcoupang.com/a/abc')
    assert not _valid_coupang_url('https://www.coupang.com/')
