import json
from pathlib import Path

from bs4 import BeautifulSoup

from src.article_format import format_general_article, normalize_article_styles
from src.monetization import build_faq_schema, insert_faq_schema


def test_semantic_faq_is_bounded_and_ignores_toc():
    html = '''<nav>FAQ<h3>목차의 질문인가요?</h3><p>목차를 답변으로 읽으면 안 됩니다.</p></nav>
    <h2>FAQ</h2><h3>지원 조건은 무엇인가요?</h3><p>선택한 공고에서 지원 조건을 확인하세요.</p>
    <h3>언제까지 제출하나요?</h3><p>공식 접수 안내에서 마감을 확인하세요.</p>
    <h2>다른 내용</h2><h3>이것도 질문인가요?</h3><p>다른 섹션은 포함하지 않습니다.</p>'''
    schema = BeautifulSoup(build_faq_schema(html), 'html.parser')
    data = json.loads(schema.script.string)
    assert [x['name'] for x in data['mainEntity']] == ['지원 조건은 무엇인가요?', '언제까지 제출하나요?']
    once = insert_faq_schema(html)
    assert insert_faq_schema(once) == once


def test_legacy_strong_faq_still_supported():
    html = '<h2>FAQ</h2><p><strong>지원 조건은 무엇인가요?</strong></p><p>공고에서 자격 요건을 확인하세요.</p><p><strong>언제까지 제출하나요?</strong></p><p>공식 마감일 이전에 제출하세요.</p>'
    assert len(json.loads(BeautifulSoup(build_faq_schema(html), 'html.parser').script.string)['mainEntity']) == 2


def test_styles_preserve_text_links_and_explicit_light_callout():
    raw = '<div style="background:white;color:black"><p>흰 상자의 본문</p></div><h2>FAQ</h2><h3>지원 조건은 무엇인가요?</h3><p><a href="https://example.org/">공식 공고</a>를 확인하세요.</p>'
    formatted = normalize_article_styles(raw)
    before, after = BeautifulSoup(raw, 'html.parser'), BeautifulSoup(formatted, 'html.parser')
    assert before.get_text(' ', strip=True) == after.get_text(' ', strip=True)
    assert after.a['href'] == before.a['href']
    assert not after.div.p.has_attr('style')
    assert len(after.select('[data-faq-card]')) == 1
    assert normalize_article_styles(formatted) == formatted


def test_real_codex_article_has_complete_shared_format():
    root = Path(__file__).resolve().parent.parent / 'data/editorial/2026-09-08'
    raw = (root / 'hyundai-codex.html').read_text()
    sources = json.loads((root / 'hyundai-codex-sources.json').read_text())
    formatted = format_general_article(raw, sources=sources, category='취업',
        related_posts=[{'url': 'https://trendpulse.blog/daegieop-gongchae-2026-hbangi/', 'title': '공채 일정 비교'}])
    soup = BeautifulSoup(formatted, 'html.parser')
    assert soup.select_one('#policy-notice')
    assert soup.select_one('#quick-answer')
    assert soup.select_one('#article-toc')
    assert soup.select_one('#verified-sources')
    assert len(soup.select('[data-faq-card]')) == 3
    assert len(soup.select('ins.adsbygoogle')) == 2
    assert all(t.get('style') for t in soup.find_all('table'))
    assert len(json.loads(soup.select_one('script[type="application/ld+json"]').string)['mainEntity']) == 3
    # Every original paragraph survives, including its Korean text and source links.
    original = BeautifulSoup(raw, 'html.parser')
    for paragraph in original.find_all('p'):
        assert paragraph.get_text(' ', strip=True) in soup.get_text(' ', strip=True)


def test_visual_steps_are_numbered_once_and_preserve_links():
    raw = '<ol data-visual="steps" aria-label="준비 순서"><li><strong>자격 확인</strong><a href="https://example.org/">공고 확인</a></li><li><strong>제출 확인</strong>접수 상태 확인</li></ol>'
    once = normalize_article_styles(raw)
    soup = BeautifulSoup(once, 'html.parser')
    assert [x.get_text() for x in soup.select('[data-step-number]')] == ['01', '02']
    assert soup.ol['aria-label'] == '준비 순서'
    assert soup.a['href'] == 'https://example.org/'
    assert 'min(100%,170px)' in soup.ol['style']
    assert normalize_article_styles(once) == once


def test_plain_lists_are_not_turned_into_diagrams():
    soup = BeautifulSoup(normalize_article_styles('<ol><li>첫 항목</li><li>둘째 항목</li></ol>'), 'html.parser')
    assert not soup.select('[data-step-number]')
    assert 'display:grid' not in soup.ol['style']
