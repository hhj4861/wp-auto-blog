from datetime import datetime, timezone
from unittest.mock import Mock
import json

import pytest
import requests

from src import youtube_discovery as youtube

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)
ID = 'abcdefghijk'


def item(video_id=ID, **changes):
    row = {'id': video_id, 'snippet': {'title': '노트북 램 구매 전 선택 기준',
        'channelId': 'UC' + 'a' * 22, 'publishedAt': '2026-09-01T00:00:00Z',
        'liveBroadcastContent': 'none'}, 'statistics': {'viewCount': '100000'}}
    row.update(changes)
    return row


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv('YOUTUBE_API_KEY', 'secret-only-in-request')
    def install(items=None):
        rows = items if items is not None else [item()]
        def get(url, **kw):
            body = ({'items': [{'id': {'videoId': row['id']}} for row in rows]}
                    if url.endswith('search') else {'items': rows})
            return Mock(json=lambda: body)
        http = Mock(side_effect=get)
        monkeypatch.setattr(youtube.requests, 'get', http)
        return http
    return install


def test_recent_popularity_is_grounded_seed_not_search_volume(api):
    http = api()
    model = Mock(return_value={'seeds': [{'seed': '노트북 램', 'video_id': ID}]})
    seeds, audit = youtube.discover('리뷰', NOW, model)
    assert seeds == [{'seed': '노트북 램', 'video_id': ID}]
    assert audit['status'] == 'discovered' and audit['videos'][0]['views'] == 100000
    assert 'monthly_search' not in json.dumps(audit)
    assert 'secret-only' not in json.dumps(audit) + str(model.call_args)
    assert http.call_count == 3
    for call in http.call_args_list[:2]:
        params = call.kwargs['params']
        assert params['order'] == 'viewCount' and params['regionCode'] == 'KR'
        assert params['publishedAfter'] == '2026-07-03T00:00:00+00:00'
        assert params['publishedBefore'] == NOW.isoformat()
        assert params['type'] == 'video' and params['maxResults'] == 10


@pytest.mark.parametrize('kind', ['no_key', 'unsupported_category', 'http', 'malformed', 'empty'])
def test_optional_discovery_never_blocks_existing_sources(monkeypatch, api, kind, caplog):
    http = api([] if kind == 'empty' else None)
    if kind == 'no_key':
        monkeypatch.delenv('YOUTUBE_API_KEY')
    elif kind == 'http':
        http.side_effect = requests.HTTPError('secret-token=request-url')
    elif kind == 'malformed':
        http.return_value = Mock(json=lambda: {'items': None})
        http.side_effect = None
    model = Mock()
    seeds, audit = youtube.discover('unknown' if kind == 'unsupported_category' else '리뷰', NOW, model)
    assert seeds == [] and audit['status'] != 'discovered'
    model.assert_not_called()
    assert 'secret-token' not in json.dumps(audit) + caplog.text


@pytest.mark.parametrize('changes', [
    {'statistics': {}}, {'statistics': {'viewCount': True}}, {'statistics': {'viewCount': '-1'}},
    {'snippet': {**item()['snippet'], 'publishedAt': '2026-01-01T00:00:00Z'}},
    {'snippet': {**item()['snippet'], 'publishedAt': '2026-11-01T00:00:00Z'}},
    {'snippet': {**item()['snippet'], 'publishedAt': '2026-09-01T00:00:00'}},
    {'snippet': {**item()['snippet'], 'liveBroadcastContent': 'live'}},
    {'snippet': {**item()['snippet'], 'channelId': 'invalid'}},
])
def test_unverified_dates_views_and_live_videos_are_excluded(api, changes):
    api([item(**changes)])
    model = Mock()
    seeds, audit = youtube.discover('리뷰', NOW, model)
    assert seeds == [] and audit['status'] == 'no_recent_videos'
    model.assert_not_called()


def test_same_channel_cannot_fill_discovery_list(api):
    api([item(video_id=str(i) * 11) for i in range(6)])
    _, audit = youtube.discover('리뷰', NOW, Mock(return_value={'seeds': []}))
    assert len(audit['videos']) == 2


@pytest.mark.parametrize('rows', [None, [], [{'seed': '무관한 청소기', 'video_id': ID}],
    [{'seed': '노트북 램', 'video_id': 'invented'}], [{'seed': '노트북;rm', 'video_id': ID}],
    [None, {}], [{'seed': ['노트북'], 'video_id': ID}]])
def test_invented_or_invalid_seed_never_reaches_demand_lookup(api, rows):
    api()
    seeds, audit = youtube.discover('리뷰', NOW, Mock(return_value={'seeds': rows}))
    assert seeds == [] and audit['status'] in {'seed_analysis_unavailable', 'no_grounded_seeds'}


def test_seed_model_failure_is_redacted_and_optional(api):
    api()
    seeds, audit = youtube.discover('리뷰', NOW, Mock(side_effect=RuntimeError('private-secret')))
    assert seeds == [] and audit['status'] == 'seed_analysis_unavailable'
    assert 'private-secret' not in json.dumps(audit)
