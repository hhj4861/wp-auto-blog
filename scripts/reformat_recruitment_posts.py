"""Preserve the editorial content of two explicitly requested legacy posts."""
from collections import Counter
import json
from bs4 import BeautifulSoup, Tag
from src.recruitment_format import apply_recruitment_layout, recruitment_format_issues
from src.category_format import apply_category_layout

TARGETS = {
    (1894, 'kpf-recruitment-2026'): (
        ['한국언론진흥재단 채용 일정과 모집 조건', '한국언론진흥재단 채용 지원 자격은 어떻게 확인하나요?',
         '공식 온라인 접수는 이 순서로 준비하세요', '필기·면접 준비에 앞서 구분해야 할 정보',
         '제출 전에는 지원 자격과 근무 가능 여부를 점검하세요', 'FAQ'],
        ['facts', 'details', 'prepare', 'prepare', 'check', 'faq']),
    (1897, 'citygas-recruitment-2026'): (
        ['도시가스 대졸 신입 채용 일정과 지원 조건', '도시가스 대졸 신입 채용 직무와 근무지역 비교',
         '필수 지원자격과 우대사항은 나누어 확인해요', '공식 채용 페이지에서 온라인으로 지원하는 순서',
         '직무 경험을 정리하고 제출 전 최종 점검하기', 'FAQ'],
        ['facts', 'details', 'details', 'prepare', 'check', 'faq']),
}
PROTECTED = {'quick-answer', 'verified-sources', 'policy-notice', 'policy-disclaimer', 'coupang-disclosure'}


def preservation_snapshot(html):
    soup = BeautifulSoup(html, 'html.parser')
    for n in list(soup.select('#article-toc, [data-reader-menu], .wpab-check-note, #wpab-reading-styles, #wpab-category-reader')):
        n.decompose()
    scripts = Counter(n.get_text() for n in soup.find_all('script'))
    for n in soup.select('script, style'):
        n.decompose()
    return {
        'text': Counter(soup.stripped_strings),
        'links': Counter((n.get('href'), n.get_text(' ', strip=True)) for n in soup.find_all('a')),
        'ads': Counter(json.dumps(n.attrs, sort_keys=True) for n in soup.select('ins, iframe')),
        'images': Counter((n.get('src'), n.get('alt')) for n in soup.find_all('img')),
        'scripts': scripts,
    }


def convert_legacy_recruitment(html, post_id, slug):
    if (post_id, slug) not in TARGETS:
        raise ValueError('Only the two explicitly requested recruitment posts are supported')
    soup = BeautifulSoup(html, 'html.parser')
    articles = soup.select('.wpab-article')
    if len(articles) != 1:
        raise ValueError('Exactly one shared article wrapper required')
    article = articles[0]
    if article.get('data-reader-version') == 'category-menu-v1':
        if article.get('data-reader-category') != '취업':
            raise ValueError('Reader category mismatch')
        return html
    if not article.find(id='verified-sources'):
        raise ValueError('Verified source section required')
    before = preservation_snapshot(html)
    toc = article.find(id='article-toc')
    if toc:
        toc.decompose()
    # The citygas legacy article wraps each H2 in an anonymous section.
    for node in list(article.find_all(['section', 'div'], recursive=False)):
        if node.get('id') not in PROTECTED and node.find('h2'):
            node.unwrap()
    # Legacy official-site CTAs predate the monetization marker. Keep them visible.
    for node in article.find_all('div', recursive=False):
        note = node.find('p', recursive=False)
        if node.find('a', recursive=False) and note and note.get_text(strip=True) in (
                '공식 사이트로 이동합니다', '공식 사이트에서 최신 정보를 확인하세요'):
            node['data-monetization'] = 'official-cta'
    headings, groups = TARGETS[(post_id, slug)]
    if [h.get_text(' ', strip=True) for h in article.find_all('h2', recursive=False)] != headings:
        raise ValueError('Legacy heading structure changed; manual review required')
    active = None
    index = 0
    sections = {}
    for node in list(article.contents):
        if not isinstance(node, Tag):
            continue
        if (node.get('id') in PROTECTED or node.name in ('script', 'style', 'ins')
                or node.select_one('ins.adsbygoogle') or node.get('data-monetization')):
            continue
        if node.name == 'h2':
            group = groups[index]
            index += 1
            if group not in sections:
                active = soup.new_tag('section', id='recruitment-' + group)
                node.insert_before(active)
                sections[group] = active
            else:
                active = sections[group]
                node.name = 'h3'
        if active is not None:
            active.append(node.extract())
    issues = recruitment_format_issues(str(soup))
    if issues:
        raise ValueError('Existing content does not meet the format: ' + '; '.join(issues))
    fixed = apply_category_layout(apply_recruitment_layout(str(soup)), '취업')
    if preservation_snapshot(fixed) != before:
        raise ValueError('Editorial text, links, images, ads or schema changed')
    output = BeautifulSoup(fixed, 'html.parser')
    if len(output.select('[data-reader-panel]')) != 5:
        raise ValueError('Expected five recruitment menu panels')
    return fixed
