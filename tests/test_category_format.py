"""Category menus retain evidence and work without JavaScript after WP filtering."""
import json
import pytest
from bs4 import BeautifulSoup
from src.article_format import format_general_article
from src.category_format import CATEGORY_SECTIONS, SECTION_IDS, apply_category_layout, category_format_issues, category_writing_rules

RAW = '''<section id="quick-answer"><p>핵심 답변과 원문을 확인하세요.</p></section>
<section id="reader-overview"><h2>판단 기준</h2><p>조건을 살펴봅니다.</p><p>예외를 함께 확인합니다.</p><table><tr><th>항목</th><td>조건</td></tr></table></section>
<section id="reader-process"><h2>실행 순서</h2><ol data-visual="steps"><li><strong>첫 단계</strong><p>확인합니다.</p></li><li><strong>다음 단계</strong><p>기록합니다.</p></li></ol></section>
<section id="reader-details"><h2>상세 예시</h2><p>편집부 예시입니다.</p><p>실제 조건과 구분합니다.</p><a href="#reader-check">점검 이동</a></section>
<section id="reader-faq"><h2>자주 묻는 질문</h2><h3>어디서 확인하나요?</h3><p>공식 안내에서 확인합니다.</p><h3>예외는 있나요?</h3><p>조건에 따라 다릅니다.</p><h3>자동 확인인가요?</h3><p>개인 점검용입니다.</p></section>
<section id="reader-check"><h2>최종 점검</h2><ul data-visual="checklist"><li>원문 확인</li><li>예외 확인</li><li>결과 확인</li></ul></section>'''
SOURCE = dict(url='https://www.cdc.gov/sleep/about/index.html', title='공식 근거', checked_on='2026-10-10', sha256='fixture', original_url='https://www.cdc.gov/sleep/about/index.html', excerpt='원문 확인')

@pytest.mark.parametrize('category', CATEGORY_SECTIONS)
def test_format_preserves_content_sources_schema_and_visible_monetization(category):
    rendered = format_general_article(RAW, category=category, sources=[SOURCE],
        official_link='공식 안내|https://www.gov.kr/', related_posts=[dict(url='https://trendpulse.blog/example/', title='관련 안내')])
    soup = BeautifulSoup(rendered, 'html.parser')
    assert not category_format_issues(rendered, category)
    style = soup.select_one('#wpab-reading-styles').string
    assert '\n' not in style and '\r' not in style  # WordPress wpautop must not paragraph CSS
    assert len(soup.select('[data-reader-panel]')) == 5
    assert len(soup.select('[data-reader-menu] a')) == 6
    assert not soup.select('[data-reader-panel][hidden]')
    assert not soup.select('[data-reader-panel] [data-monetization], [data-reader-panel] #verified-sources, [data-reader-panel] #policy-notice')
    assert len(soup.select('ins.adsbygoogle')) == 2
    assert len(soup.select('[data-monetization="cta"]')) == 2
    assert soup.select_one('[data-monetization="related"] a')['href'] == 'https://trendpulse.blog/example/'
    assert len(soup.select('.wpab-check-note')) == 1
    assert '새로고침하면 초기화' in soup.select_one('.wpab-check-note').text
    for link in soup.select('[data-reader-menu] a'):
        assert soup.select_one(link['href'])
    for p in BeautifulSoup(RAW, 'html.parser').find_all('p'):
        assert p.text in soup.get_text()
    assert len(json.loads(soup.select_one('script[type="application/ld+json"]').string)['mainEntity']) == 3
    assert apply_category_layout(rendered, category) == rendered
    soup.select_one('#wpab-category-reader').decompose()
    assert len(soup.select('[data-reader-panel]:not([hidden])')) == 5
    assert soup.select_one('#verified-sources a')['href'] == SOURCE['url']

@pytest.mark.parametrize('category', CATEGORY_SECTIONS)
def test_writing_contract_and_gate(category):
    rules = category_writing_rules(category)
    assert all(key in rules for key in SECTION_IDS)
    assert not category_format_issues(RAW, category)
    missing = RAW.replace('id="reader-details"', 'id="missing"')
    assert any('reader-details' in issue for issue in category_format_issues(missing, category))
    thin = RAW.replace('<p>실제 조건과 구분합니다.</p>', '')
    assert category_format_issues(thin, category) == ['카테고리 포맷 상세 설명 부족: reader-details']

def test_unknown_category_is_unchanged():
    assert apply_category_layout('<p>글</p>', 'K-Pop') == '<p>글</p>'
    assert not category_writing_rules('K-Pop')
    assert not category_format_issues('', 'K-Pop')

def test_evidence_repair_rejects_missing_reader_contract():
    from src.editorial import repair_evidence, EvidenceRepairError
    body = '<div class="wpab-article wpab-menu-reader" data-reader-version="category-menu-v1" data-reader-category="테크">'+RAW+'</div>'
    broken = body.replace('id="reader-details"', 'id="missing"')
    with pytest.raises(EvidenceRepairError, match='template_changed'):
        repair_evidence(body, [SOURCE], lambda prompt: broken, ['근거 확인'])


@pytest.mark.parametrize('category', CATEGORY_SECTIONS)
def test_generator_retries_then_holds_missing_category_sections(monkeypatch, category):
    from unittest.mock import Mock, patch
    from src.content_generator import ContentGenerator, ContentConfig, ContentType
    monkeypatch.delenv('BLOG_OFFICIAL_SOURCE_URLS', raising=False)
    with patch.object(ContentGenerator, '_setup_apis'):
        generator = ContentGenerator(ContentConfig(language='ko'))
    def research(**kwargs):
        generator._research_sources = [dict(SOURCE)]
        return ''
    monkeypatch.setattr(generator, 'research_with_grounding', research)
    monkeypatch.setattr(generator, '_validate', lambda html: (True, []))
    monkeypatch.setattr('src.content_generator.review_evidence', lambda *a: [])
    prefix = '---SEO-META---\nFOCUS_KEYPHRASE: 안내\nMETA_DESCRIPTION: 공식 자료 안내입니다.\nSLUG: reader-test\n---CONTENT---\n<h1>공식 자료 안내</h1>'
    missing = '<section id="quick-answer"><p>요약</p></section><h2>FAQ</h2>'
    writer = Mock(side_effect=[prefix + missing, prefix + RAW])
    monkeypatch.setattr(generator, '_call_llm', writer)
    result = generator.generate('공식 자료 안내', ['안내'], ContentType.GUIDE, category=category)
    assert writer.call_count == 2
    assert 'category-menu-v1' in writer.call_args_list[0].args[0]
    assert not result.editorial_issues
    writer.side_effect = [prefix + missing, prefix + missing]
    failed = generator.generate('공식 자료 안내', ['안내'], ContentType.GUIDE, category=category)
    assert any('카테고리 포맷 필수 섹션' in issue for issue in failed.editorial_issues)
