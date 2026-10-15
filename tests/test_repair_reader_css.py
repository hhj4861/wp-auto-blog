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


def test_upgrade_preserves_every_byte_outside_owned_assets():
    from scripts.repair_reader_css import upgrade_assets, STYLE
    from src.article_format import format_general_article
    from tests.test_category_format import RAW as BODY
    import re
    raw = format_general_article(BODY, category='생산성')
    raw = raw.replace('.wpab-reader-layout{display:grid;', '.wpab-reader-layout{display:block;')
    fixed = upgrade_assets(raw)
    strip = lambda value: re.sub(r'(<script id="wpab-category-reader">).*?(</script>)', r'\1\2', STYLE.sub(lambda m: m[1] + m[3], value), flags=re.S)
    assert strip(fixed) == strip(raw)
    assert upgrade_assets(fixed) == fixed
    for bad in [raw.replace('category-menu-v1', 'unknown'), raw.replace('wpab-category-reader', 'foreign'), raw + raw]:
        with pytest.raises(ValueError): upgrade_assets(bad)


def test_reflow_preview_and_apply_backup_preserve_body_and_metadata(tmp_path):
    import json
    from src.article_format import format_general_article
    from tests.test_category_format import RAW as BODY, SOURCE
    from scripts.repair_reader_css import upgrade_assets
    from src.reader_monetization import reflow_reader_ads
    # Build old footer placement with valid owned assets, as in persisted WP raw.
    raw = format_general_article(BODY, category='생산성', sources=[SOURCE])
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(raw, 'html.parser'); article = soup.select_one('.wpab-menu-reader')
    for ad in list(article.select('[data-monetization="ad"]')): article.append(ad.extract())
    raw = str(soup)
    fixed = reflow_reader_ads(upgrade_assets(raw))
    session, post, saved, response = client()
    post['content']['raw'] = raw; saved['content']['raw'] = fixed
    session.get.side_effect = [response(post)]
    assert repair(session,1907,'excel-chart-guide',upgrade=True,reflow=True)['changed']
    session.post.assert_not_called(); assert not list(tmp_path.iterdir())
    session.get.side_effect = [response(post),response(post),response(saved)]
    result = repair(session,1907,'excel-chart-guide',apply=True,upgrade=True,reflow=True,backup_dir=tmp_path)
    assert result['verified']
    from pathlib import Path
    assert json.loads(Path(result['backup']).read_text(encoding='utf-8')) == post
    assert session.post.call_args.kwargs['json'] == {'content':fixed}
    session.get.side_effect = [response(post),response(post)]
    session.post.reset_mock()
    with pytest.raises(ValueError,match='backup directory'):
        repair(session,1907,'excel-chart-guide',apply=True,upgrade=True,reflow=True)
    session.post.assert_not_called()


def test_same_second_metadata_edit_is_not_overwritten():
    session, post, _, response = client()
    changed = deepcopy(post); changed['meta'] = {'_yoast_wpseo_metadesc':'다른 편집'}
    session.get.side_effect = [response(post), response(changed)]
    with pytest.raises(RuntimeError,match='changed since'):
        repair(session,1907,'excel-chart-guide',apply=True)
    session.post.assert_not_called()


def test_readback_detects_changed_seo_metadata():
    session, post, saved, response = client(); saved['meta'] = {'_yoast_wpseo_metadesc':'변경됨'}
    session.get.side_effect = [response(post), response(post), response(saved)]
    with pytest.raises(RuntimeError,match='preservation'):
        repair(session,1907,'excel-chart-guide',apply=True)
