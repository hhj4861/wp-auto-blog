"""Reader ads keep their exact provider bytes and stay outside selectable panels."""
import re
import pytest
from bs4 import BeautifulSoup
from src.article_format import format_general_article
from src.category_format import CATEGORY_SECTIONS
from src.reader_monetization import reflow_reader_ads
from tests.test_category_format import RAW, SOURCE


def legacy():
    # Deliberately use single quotes/entities/whitespace that a serializer would change.
    first = "<div data-monetization='ad'><p>広告 &amp; ad</p><ins data-ad-slot='a'></ins><script>window.fake = 1 < 2;</script></div>"
    second = '<div data-monetization="ad"><ins data-ad-slot="b"></ins></div>'
    prefix = "<style>foreign {color: red}</style><div class='wpab-menu-reader' data-reader-version='category-menu-v1'>"
    body = "<section id='quick-answer'><p>답변 &amp; 조건</p></section><nav data-reader-menu>메뉴</nav><div data-reader-panels><section data-reader-panel><h2>정보</h2><p>원문  그대로</p></section><section data-reader-panel><h2>예외</h2></section></div>"
    sources = "<section id='verified-sources'><p>근거</p></section>"
    footer = "<div data-monetization='cta'><a href='https://gov.kr/'>공식 안내</a></div>"
    return prefix + body + sources + first + second + footer + '</div>', first, second


def test_reflow_preserves_every_other_byte_and_is_idempotent():
    raw, first, second = legacy()
    fixed = reflow_reader_ads(raw)
    assert fixed.replace(first, '').replace(second, '') == raw.replace(first, '').replace(second, '')
    soup = BeautifulSoup(fixed, 'html.parser')
    quick = soup.select_one('#quick-answer')
    panels = soup.select_one('[data-reader-panels]')
    assert quick.find_next_sibling()['data-monetization'] == 'ad'
    assert panels.find_next_sibling()['data-monetization'] == 'ad'
    assert not soup.select('[data-reader-panel] [data-monetization]')
    assert reflow_reader_ads(fixed) == fixed


@pytest.mark.parametrize('category', [*CATEGORY_SECTIONS, '취업'])
def test_new_categories_publish_ads_after_answer_and_details(category):
    html = format_general_article(RAW, category=category, sources=[SOURCE])
    soup = BeautifulSoup(html, 'html.parser')
    assert soup.select_one('#quick-answer').find_next_sibling()['data-monetization'] == 'ad'
    assert soup.select_one('[data-reader-panels]').find_next_sibling()['data-monetization'] == 'ad'
    assert len(soup.select('[data-monetization="ad"]')) == 2
    assert not soup.select('[data-reader-panel] ins.adsbygoogle')


def test_single_ad_no_ads_and_no_sources():
    raw, first, second = legacy()
    one = reflow_reader_ads(raw.replace(second, '').replace("<section id='verified-sources'><p>근거</p></section>", ''))
    assert one.count(first) == 1
    assert reflow_reader_ads(raw.replace(first, '').replace(second, '')) == raw.replace(first, '').replace(second, '')


@pytest.mark.parametrize('change', [
    lambda raw: raw + raw,
    lambda raw: raw.replace("id='quick-answer'", "id='missing'"),
    lambda raw: raw.replace('data-reader-panels', 'data-missing'),
    lambda raw: raw.removesuffix('</div>'),
    lambda raw: raw.replace('category-menu-v1', 'unsupported'),
])
def test_ambiguous_layout_fails_closed(change):
    raw, _, _ = legacy()
    with pytest.raises(ValueError): reflow_reader_ads(change(raw))


def test_nested_or_extra_owned_ads_fail_closed():
    raw, first, _ = legacy()
    for bad in [raw.replace('<nav data-reader-menu>메뉴</nav>', '<nav data-reader-menu>'+first+'</nav>'),
                raw.replace('<p>원문  그대로</p>', '<p>원문  그대로</p>'+first)]:
        with pytest.raises(ValueError): reflow_reader_ads(bad)


def test_cover_css_is_scoped_and_never_hides_ads():
    from src.category_format import reader_styles
    css = reader_styles('테크')
    assert '.single-post:has(.wpab-menu-reader) .blog-card-single-head .blog-card-right-inner{display:none}' in css
    assert 'aspect-ratio:auto' in css
    assert 'font-size:clamp(20px,2.1vw,26px)' in css
    assert not re.search(r'(?:adsbygoogle|google-auto-placed)[^{]*\{[^}]*display:none', css)
