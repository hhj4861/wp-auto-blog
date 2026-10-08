from copy import deepcopy
from unittest.mock import Mock
import pytest
from scripts.close_post import close_post


def setup(post_id=1862, status='publish'):
    original = {'id': post_id, 'slug': 'windows-eleven-install-guide-2026', 'status': status,
                'title': {'raw': 'title'}, 'content': {'raw': 'body'}, 'featured_media': 1861,
                'date_gmt': '2026-10-08T04:34:42'}
    saved = {**deepcopy(original), 'status': 'draft'}
    client = Mock()
    responses = []
    for value in (original, saved):
        response = Mock(); response.json.return_value = value; responses.append(response)
    client.get.side_effect = responses
    return client, saved


def test_close_only_status_and_readback():
    client, _ = setup()
    assert close_post(client, 1862, 'windows-eleven-install-guide-2026', apply=True)['verified']
    assert client.post.call_args.kwargs['json'] == {'status': 'draft'}
    assert client.get.call_count == 2


def test_wrong_target_never_mutates():
    client, _ = setup(post_id=1863)
    with pytest.raises(RuntimeError): close_post(client, 1862, 'windows-eleven-install-guide-2026', apply=True)
    client.post.assert_not_called()


def test_dry_run():
    client, _ = setup()
    assert close_post(client, 1862, 'windows-eleven-install-guide-2026')['dry_run']
    client.post.assert_not_called()


def test_already_draft_idempotent():
    client, _ = setup(status='draft')
    assert close_post(client, 1862, 'windows-eleven-install-guide-2026', apply=True)['verified']
    client.post.assert_not_called()


def test_readback_preserves_content():
    client, saved = setup(); saved['content'] = {'raw': 'changed'}
    with pytest.raises(RuntimeError): close_post(client, 1862, 'windows-eleven-install-guide-2026', apply=True)
