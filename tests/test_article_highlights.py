"""Highlights retain qualifications, navigation and evidence across categories."""
import pytest
from bs4 import BeautifulSoup
from src.article_highlights import PRIORITIES, highlights_issues, highlights_writing_rules
from src.article_format import format_general_article
from src.category_format import apply_category_layout

QUICK = '''<section id="quick-answer" data-highlights="1">
<p data-highlight="conclusion">조건에 해당할 때 공식 절차를 이용할 수 있습니다.</p>
<dl data-highlight="facts"><div><dt>대상</dt><dd>공식 안내의 해당 대상만</dd></div>
<div><dt>예외</dt><dd>미확인 조건은 확정하지 않음</dd></div>
<div><dt>확인 경로</dt><dd><a href="https://example.org/official">공식 안내</a></dd></div></dl>
<aside data-highlight="action"><p>해당 대상이라면 신청 전 공식 안내의 준비물을 확인하세요.</p></aside>
</section>'''
RAW = QUICK + '<section><h2>상세 조건</h2><p>빠뜨리면 안 되는 예외 설명입니다.</p></section><section><h2>다음 단계</h2><p>구체적인 절차 설명입니다.</p></section>'
SOURCE = dict(url='https://example.org/official', title='공식 안내', checked_on='2026-10-14', sha256='fixture')

@pytest.mark.parametrize('category', PRIORITIES)
def test_all_categories_keep_highlights_outside_panels(category):
    rendered = format_general_article(RAW, category=category, sources=[SOURCE])
    soup = BeautifulSoup(rendered, 'html.parser')
    assert not highlights_issues(rendered, category)
    quick = soup.select_one('#quick-answer')
    assert not quick.find_parent(attrs={'data-reader-panel': True})
    assert soup.select_one('[data-reader-menu] a').text == '전체 보기'
    assert len(soup.select('[data-reader-panel]:not([hidden])')) == 2
    assert len(soup.select('#quick-answer [data-highlight="sources"]')) == 1
    assert soup.select_one('#quick-answer [data-highlight="sources"] a')['href'] == '#verified-sources'
    assert '2026-10-14' in soup.select_one('#verified-sources').text
    assert '\n' not in soup.select_one('#wpab-reading-styles').string
    for p in BeautifulSoup(RAW, 'html.parser').find_all(['p', 'dt', 'dd']):
        assert p.get_text(' ', strip=True) in soup.get_text(' ', strip=True)
    assert apply_category_layout(rendered, category) == rendered
    soup.select_one('#wpab-category-reader').decompose()
    assert not soup.select('#quick-answer [hidden]')
    assert 'article-highlights-v1' in highlights_writing_rules(category)

@pytest.mark.parametrize('old,new', [
    (' data-highlights="1"', ''),
    ('data-highlight="conclusion"', 'data-highlight="other"'),
    ('<dt>대상</dt>', '<dt></dt>'),
    ('<dd>공식 안내의 해당 대상만</dd>', '<dd></dd>'),
    ('data-highlight="action"', 'data-highlight="other"'),
])
def test_incomplete_highlights_are_held(old, new):
    assert highlights_issues(RAW.replace(old, new), '건강')


def test_few_verified_facts_allowed_without_filler():
    soup = BeautifulSoup(QUICK, 'html.parser')
    for item in soup.select('dl>div')[1:]:
        item.decompose()
    assert not highlights_issues(str(soup), '취업')
    for i in range(3):
        soup.dl.append(BeautifulSoup('<div><dt>항목</dt><dd>값</dd></div>', 'html.parser'))
    assert highlights_issues(str(soup), '취업')


def test_legacy_article_not_given_invented_highlights_or_sources():
    legacy = '<section id="quick-answer"><p>원문 그대로</p></section><h2>상세</h2><p>설명</p>'
    soup = BeautifulSoup(format_general_article(legacy, category='취업'), 'html.parser')
    assert soup.select_one('#quick-answer').text == '원문 그대로'
    assert not soup.select('[data-highlights], [data-highlight="sources"]')
    soup = BeautifulSoup(format_general_article(RAW, category='테크'), 'html.parser')
    assert not soup.select('[data-highlight="sources"]')
    assert not highlights_issues('', 'K-Pop')


def test_duplicate_summary_is_rejected_even_when_one_is_legacy():
    assert highlights_issues(QUICK + '<section id="quick-answer"><p>다른 결론</p></section>', '건강')
