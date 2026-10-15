from unittest.mock import Mock
import pytest
from src import gsc_client


def test_paginated_final_metrics_and_offset(monkeypatch):
    page = {'page':'https://trendpulse.blog/p/','clicks':0,'impressions':1,'ctr':0,'position':3}
    query = Mock(side_effect=[[page,page],[page],[]]);monkeypatch.setattr(gsc_client,'query',query)
    result = gsc_client.query_all('2026-09-01','2026-09-28',['page'],page_size=2,max_rows=6)
    assert result['complete'] and len(result['rows'])==3
    assert query.call_args_list[1].kwargs['start_row']==2
    assert all(c.kwargs['data_state']=='final' for c in query.call_args_list)


def test_row_cap_is_explicit_and_missing_dimension_rejected(monkeypatch):
    monkeypatch.setattr(gsc_client,'query',Mock(return_value=[{'page':'x'}]*2))
    result=gsc_client.query_all('a','b',['page'],page_size=2,max_rows=2)
    assert result['status']=='truncated' and result['complete'] is False
    monkeypatch.setattr(gsc_client,'query',Mock(return_value=[{}]))
    with pytest.raises(ValueError):gsc_client.query_all('a','b',['page'])


def test_posted_offset_and_default_compatibility(monkeypatch):
    monkeypatch.setattr(gsc_client,'_headers',lambda:{})
    post=Mock(return_value=Mock(status_code=200,json=lambda:{'rows':[]}));monkeypatch.setattr(gsc_client.requests,'post',post)
    gsc_client.query('a','b',['page'],start_row=25000)
    assert post.call_args.kwargs['json']['startRow']==25000
    gsc_client.query('a','b',['page'])
    assert 'startRow' not in post.call_args.kwargs['json']
