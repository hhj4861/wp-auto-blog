"""Regression checks for approved recruitment writing and final rendering."""
import json
from unittest.mock import Mock, patch

import pytest
from bs4 import BeautifulSoup

from src.article_format import format_general_article
from src.recruitment_format import apply_recruitment_layout, recruitment_format_issues

SOURCE = dict(url='https://www.skcareers.com/Recruit/Detail/example',
              original_url='https://www.skcareers.com/Recruit/Detail/example',
              title='공식 채용 안내', checked_on='2026-10-10', sha256='fixture', excerpt='검증용 원문')
RAW = '''<section id="quick-answer"><p>공고의 직무와 지원 조건을 비교하세요.</p>
<aside data-recruitment="deadline"><strong>공식 마감 안내</strong><p>예정 여부를 확인하세요.</p></aside></section>
<section id="recruitment-facts"><h2>모집 조건</h2><dl><div><dt>직무</dt><dd>마케팅</dd></div></dl>
<div data-recruitment="companies"><section><h3>기업 안내</h3><p>근무지역 확인</p></section></div></section>
<section><h2>공식 전형</h2><ol data-recruitment="timeline"><li><strong>지원</strong><p>공고 확인</p></li><li><strong>면접</strong><p>별도 안내</p></li></ol></section>
<section id="recruitment-details"><h2>업무 자세히 읽기</h2><p>실제 업무와 자신의 경험을 대조하세요.</p><p>필수 조건과 우대 조건을 구분하세요.</p></section>
<section id="recruitment-prepare"><h2>준비 가이드</h2><p>편집부 준비 제안입니다.</p><ol data-visual="steps"><li><strong>직무 선택</strong><p>경험 연결</p></li><li><strong>제출 확인</strong><p>상태 확인</p></li></ol><p>상황·행동·결과로 경험을 설명하는 연습 예시입니다.</p></section>
<section id="recruitment-check"><h2>최종 점검</h2><ul data-visual="checklist"><li><strong>연락처</strong>오기재 확인</li><li><strong>제출</strong>완료 확인</li></ul></section>
<h2>FAQ</h2><h3>지원 조건은 무엇인가요?</h3><p>공식 공고 기준입니다.</p><h3>전형 일정은 언제인가요?</h3><p>예정 여부를 확인하세요.</p><h3>지원 준비는 어떻게 하나요?</h3><p>편집부 제안을 참고하세요.</p>'''


def test_shared_formatter_preserves_content_provenance_ads_and_faq(monkeypatch):
    monkeypatch.setenv('ADSENSE_SLOTS', '1,2')
    raw = RAW + f'<p><a href="{SOURCE["url"]}">공식 근거</a></p>'
    html = format_general_article(raw, sources=[SOURCE], category='취업')
    soup = BeautifulSoup(html, 'html.parser')
    assert soup.select_one('.wpab-article.wpab-recruitment')['data-article-format'] == 'recruitment-reader-v1'
    assert len(soup.select('details[data-faq-card] summary')) == 3
    assert len(soup.select('ins.adsbygoogle')) == 2
    assert 'min-height:280px' in soup.select_one('ins.adsbygoogle')['style']
    assert soup.select_one('#verified-sources a')['href'] == SOURCE['url']
    schema = json.loads(soup.select_one('script[type="application/ld+json"]').string)
    assert len(schema['mainEntity']) == 3
    from src.monetization import insert_faq_schema
    soup.select_one('script[type="application/ld+json"]').decompose()
    rebuilt = BeautifulSoup(insert_faq_schema(str(soup)), "html.parser")
    assert json.loads(rebuilt.select_one('script[type="application/ld+json"]').string) == schema
    assert not recruitment_format_issues(html)
    for p in BeautifulSoup(raw, 'html.parser').find_all('p'):
        assert p.get_text() in soup.get_text()
    for link in soup.select('#article-toc a'):
        assert soup.find(id=link['href'][1:])
    assert apply_recruitment_layout(html) == html
    assert not soup.select_one('#recruitment-details h2').get('style')


@pytest.mark.parametrize('category', ['생활정보', '건강', '리뷰', '테크', '생산성'])
def test_unapproved_categories_keep_existing_format(category):
    html = format_general_article(RAW, category=category)
    soup = BeautifulSoup(html, 'html.parser')
    assert not soup.select_one('.wpab-recruitment')
    assert len(soup.select('div[data-faq-card]')) == 3
    assert '#292f33' in soup.select_one('#wpab-reading-styles').string


def test_missing_or_thin_sections_are_reported_without_inventing_content():
    assert len(recruitment_format_issues('<p>요약만 있는 글</p>')) == 4
    thin = RAW.replace('<p>실제 업무와 자신의 경험을 대조하세요.</p>', '')
    assert recruitment_format_issues(thin) == ['채용 포맷 상세 설명 부족: recruitment-details']
    assert not recruitment_format_issues(RAW.replace('<aside data-recruitment="deadline"><strong>공식 마감 안내</strong><p>예정 여부를 확인하세요.</p></aside>', ''))


def test_generation_retries_missing_format_and_gates_final_failure(monkeypatch):
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
    prefix = ('---SEO-META---\nFOCUS_KEYPHRASE: 채용\nMETA_DESCRIPTION: 채용 안내입니다.\n'
              'SLUG: hiring-test\n---CONTENT---\n<h1>채용 안내</h1>')
    missing = '<section id="quick-answer"><p>요약</p></section><h2>FAQ</h2>'
    writer = Mock(side_effect=[prefix + missing, prefix + RAW])
    monkeypatch.setattr(generator, '_call_llm', writer)
    result = generator.generate('채용 안내', ['채용'], ContentType.GUIDE, category='취업')
    assert writer.call_count == 2
    assert 'recruitment-reader-v1' in writer.call_args_list[0].args[0]
    assert not result.editorial_issues
    writer.side_effect = [prefix + missing, prefix + missing]
    failed = generator.generate('채용 안내', ['채용'], ContentType.GUIDE, category='취업')
    assert any('채용 포맷 필수 섹션 없음' in x for x in failed.editorial_issues)


@pytest.mark.parametrize('change', ['class', 'detail'])
def test_evidence_repair_cannot_silently_drop_approved_recruitment_format(change):
    from src.editorial import repair_evidence, EvidenceRepairError
    body = '<div class="wpab-article wpab-recruitment" data-article-format="recruitment-reader-v1">' + RAW + '</div>'
    modified = (body.replace('wpab-article wpab-recruitment', 'wpab-article') if change == 'class'
                else body.replace('<p>실제 업무와 자신의 경험을 대조하세요.</p>', ''))
    with pytest.raises(EvidenceRepairError, match='template_changed'):
        repair_evidence(body, [SOURCE], lambda prompt: modified, ['조건을 재확인하세요.'])
