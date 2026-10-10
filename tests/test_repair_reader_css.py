from copy import deepcopy
from unittest.mock import Mock
import pytest
from scripts.repair_reader_css import compact_style, repair

RAW = '<p>보존</p><style id="wpab-reading-styles">\n.wpab-menu-reader { color:red }\n\n.wpab-menu-reader nav { display:grid }\n</style><script>keep()</script><p>끝</p>'


def test_compaction_changes_only_owned_style_whitespace():
    fixed = compact_style(RAW)
    assert fixed == '<p>보존</p><style id="wpab-reading-styles">.wpab-menu-reader { color:red } .wpab-menu-reader nav { display:grid }</style><script>keep()</script><p>끝</p>'
    assert compact_style(fixed) == fixed
    for bad in ['<style>body{}</style>', RAW + RAW, RAW.replace('color:red', '<p>bad')]:
        with pytest.raises(ValueError): compact_style(bad)


def client():
    post = dict(id=1907,slug='excel-chart-guide',status='publish',content={'raw':RAW},modified_gmt='now',title={'raw':'글'},featured_media=0,date_gmt='date',categories=[1],tags=[2],excerpt={'raw':'요약'},link='https://trendpulse.blog/excel-chart-guide/')
    saved = deepcopy(post); saved['content']['raw'] = compact_style(RAW)
    session = Mock()
    def response(p): return Mock(json=lambda:deepcopy(p))
    session.get.side_effect = [response(post), response(post), response(saved)]
    return session, post, saved, response


def test_write_only_content_and_preserve_readback():
    session, _, _, _ = client()
    assert repair(session,1907,'excel-chart-guide',apply=True)['verified']
    assert session.post.call_args.kwargs['json'] == {'content':compact_style(RAW)}


def test_dry_run_and_identity_fail_closed():
    session, _, _, _ = client()
    assert repair(session,1907,'excel-chart-guide')['dry_run']
    session.post.assert_not_called()
    session, _, _, _ = client()
    with pytest.raises(RuntimeError): repair(session,1908,'excel-chart-guide',apply=True)
    session.post.assert_not_called()


def test_changed_post_is_not_overwritten():
    session, post, _, response = client()
    changed = deepcopy(post); changed['content']['raw']+='edit'
    session.get.side_effect=[response(post),response(changed)]
    with pytest.raises(RuntimeError,match='changed since'): repair(session,1907,'excel-chart-guide',apply=True)
    session.post.assert_not_called()


def test_readback_detects_lost_metadata():
    session, post, saved, response = client(); saved['title']={'raw':'wrong'}
    session.get.side_effect=[response(post),response(post),response(saved)]
    with pytest.raises(RuntimeError,match='preservation'): repair(session,1907,'excel-chart-guide',apply=True)
