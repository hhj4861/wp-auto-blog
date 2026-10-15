from datetime import datetime, timezone, timedelta
from copy import deepcopy
import csv
import io
from unittest.mock import Mock
import pytest
from src.site_measurement import (SITE, normalize_url, fingerprint, fetch_inventory, windows,
    collect_shard, merge_report, render_report, validate_signals)

NOW=datetime(2026,10,15,2,tzinfo=timezone.utc)


def inventory(count=4):
    posts=[{'post_id':i,'url':f'{SITE}/post-{i}/','slug':f'post-{i}',
        'title':f'Post {i}','category':'취업','published_at':'2026-08-01T00:00:00+00:00',
        'modified_at':'2026-10-01T00:00:00+00:00','format':'legacy'} for i in range(1,count+1)]
    return {'site':SITE,'complete':True,'inventory_id':fingerprint(posts),'posts':posts}


def query(start,end,dims):
    if dims==['page']:
        return {'complete':True,'rows':[{'page':f'{SITE}/post-1/','clicks':1,'impressions':140,'ctr':1/140,'position':6.7}]}
    return {'complete':True,'rows':[{'page':f'{SITE}/post-1/','query':'준비','country':'kor','device':'MOBILE','clicks':1,'impressions':100,'ctr':.01,'position':7}]}


def inspect(url):return {'verdict':'PASS','coverageState':'제출되고 색인이 생성되었습니다.','googleCanonical':url}


def test_inventory_get_only_all_pages_publish_state_and_ledger_reconciliation():
    def get(url,params,**kwargs):
        if 'categories' in url:return Mock(status_code=200,json=lambda:[{'id':1,'name':'생산성'}])
        count=100 if params['page']==1 else 1
        start=1 if params['page']==1 else 101
        rows=[{'id':i,'link':f'{SITE}/p-{i}/','slug':f'p-{i}','status':'publish',
               'title':{'rendered':'<b>Title</b>'},'date_gmt':'2026-08-01T00:00:00',
               'modified_gmt':'2026-09-01T00:00:00','categories':[1], 'content':{'rendered':''}}
               for i in range(start,start+count)]
        return Mock(status_code=200,headers={'X-WP-Total':'101','X-WP-TotalPages':'2'},json=lambda:rows)
    session=Mock(get=Mock(side_effect=get))
    report=fetch_inventory(session,ledger=[{'url':SITE+'/closed/','keyword':'closed'}])
    assert len(report['posts'])==101 and report['posts'][0]['category']=='생산성'
    assert all(p['keyword'] is None for p in report['posts'])
    session.post.assert_not_called()
    assert all(c.kwargs['allow_redirects'] is False for c in session.get.call_args_list)


def test_inventory_failure_or_duplicate_never_becomes_empty_success():
    session=Mock();session.get.return_value=Mock(status_code=403)
    with pytest.raises(RuntimeError):fetch_inventory(session)


@pytest.mark.parametrize('url',['http://trendpulse.blog/p/','https://other.org/p/','https://trendpulse.blog/','https://trendpulse.blog/p/?secret=1'])
def test_url_allowlist(url):
    with pytest.raises(ValueError):normalize_url(url)


def test_final_pacific_dates_and_nonoverlapping_28_day_windows():
    periods=windows(NOW)
    assert periods['28d']=={'start':'2026-09-14','end':'2026-10-11'}
    assert periods['previous28d']=={'start':'2026-08-17','end':'2026-09-13'}


def test_all_shards_union_no_double_counting_and_no_phantom_zeroes():
    inv=inventory();parts=[collect_shard(inv,query,inspect,shard=i,shards=2,now=NOW) for i in range(2)]
    report=merge_report(inv,parts)
    assert report['collection_complete'] and len(report['posts'])==4
    first,missing=report['posts'][:2]
    assert 'ctr_review' in first['review_reasons']
    assert missing['performance']['28d']['status']=='no_reported_rows'
    assert missing['performance']['28d']['metrics'] is None
    assert 'performance_insufficient' in missing['review_reasons']
    assert missing['external']['demand']['status']=='not_connected'


def test_missing_or_wrong_snapshot_shard_keeps_all_posts_unavailable():
    inv=inventory();part=collect_shard(inv,query,inspect,shard=0,shards=2,now=NOW)
    report=merge_report(inv,[part])
    assert len(report['posts'])==4 and not report['collection_complete']
    assert report['posts'][1]['index']['reason']=='missing_shard'
    part['inventory_id']='wrong'
    result=merge_report(inv,[part]);assert result['errors']==['inventory_mismatch']
    assert len(result['posts'])==4


def test_api_errors_truncation_and_partial_progress_do_not_leak_secrets():
    inv=inventory(2);snapshots=[]
    report=collect_shard(inv,Mock(side_effect=RuntimeError('PRIVATE TOKEN')),
        Mock(side_effect=RuntimeError('PRIVATE PASSWORD')),shards=1,now=NOW,
        on_progress=lambda r:snapshots.append(deepcopy(r)))
    assert 'PRIVATE' not in str(report) and len(snapshots)>=4
    assert report['posts'][0]['performance']['28d']['status']=='unavailable'
    assert report['posts'][0]['index']['status']=='unavailable'
    assert not merge_report(inv,[report])['collection_complete']
    bad=Mock(return_value={'complete':False,'rows':[]})
    result=collect_shard(inv,bad,inspect,shards=1,now=NOW)
    assert result['posts'][0]['performance']['28d']['status']=='unavailable'


def test_inspection_cache_is_current_modified_and_error_retryable():
    inv=inventory(1);cache={};reader=Mock(side_effect=inspect)
    collect_shard(inv,query,reader,cache=cache,shards=1,now=NOW)
    reader.reset_mock();collect_shard(inv,query,reader,cache=cache,shards=1,now=NOW+timedelta(days=1));reader.assert_not_called()
    inv['posts'][0]['modified_at']='2026-10-10T00:00:00+00:00';inv['inventory_id']=fingerprint(inv['posts'])
    collect_shard(inv,query,reader,cache=cache,shards=1,now=NOW+timedelta(days=1));assert reader.call_count==1
    reader.reset_mock();collect_shard(inv,query,reader,cache=cache,shards=1,now=NOW+timedelta(days=1),refresh=True);assert reader.call_count==1


def test_new_article_is_collecting_and_budget_still_retains_all_rows():
    inv=inventory(1);inv['posts'][0]['published_at']='2026-10-14T00:00:00+00:00'
    reader=Mock();part=collect_shard(inv,query,reader,shards=1,now=NOW,budget_seconds=0)
    assert part['posts'][0]['performance']['28d']['status']=='collecting'
    assert part['posts'][0]['index']['reason']=='time_budget';reader.assert_not_called()


def test_external_signals_require_engine_currency_and_provenance():
    item={'url':SITE+'/post-1/','demand':{'status':'reported','source':'Planner','engine':'google','region':'KR',
        'monthly_searches':1000,'period_start':'2026-09-01','period_end':'2026-09-30','checked_at':NOW.isoformat()}}
    signals={'schema_version':1,'site':SITE,'posts':[item]}
    assert validate_signals(signals)[item['url']]['demand']['monthly_searches']==1000
    item['demand']['monthly_searches']=float('nan')
    with pytest.raises(ValueError):validate_signals(signals)


def test_html_escaping_csv_formula_safety_and_unknown_rendering():
    inv=inventory(1);inv['posts'][0]['title']='=HYPERLINK("<script>")'
    report=merge_report(inv,[]);csv_text,html=render_report(report)
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert list(csv.reader(io.StringIO(csv_text)))[1][2].startswith("'=")
    assert '일부 미완료' in html and 'not_connected' in html
