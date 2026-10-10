"""Approved category reading format. Preserve prose; enhance menus without storage."""
from pathlib import Path
from bs4 import BeautifulSoup, Tag
from .recruitment_format import RECRUITMENT_CSS

VERSION = 'category-menu-v1'
CATEGORY_SECTIONS = {
    '생활정보': ('대상·품목 확인', '신청·이용 순서', '준비·예외 조건', '자주 묻는 질문', '최종 점검'),
    '건강': ('핵심 이해', '생활 속 실천', '기록·상황 예시', '상담·자주 묻는 질문', '실천 점검'),
    '리뷰': ('선택 기준', '비교표', '사양·근거 해석', '한계·자주 묻는 질문', '구매 점검'),
    '테크': ('무엇이 달라졌나', '작동 원리', '활용·도입 준비', '한계·자주 묻는 질문', '설정 점검'),
    '생산성': ('방법 선택', '따라 하기', '실무 예시', '문제 해결·자주 묻는 질문', '작업 점검'),
}
COLORS = {'취업':'#354edb', '생활정보':'#08776d', '건강':'#08776d',
          '리뷰':'#895118', '테크':'#354edb', '생산성':'#236945'}
SECTION_IDS = ('reader-overview', 'reader-process', 'reader-details', 'reader-faq', 'reader-check')
RULES = {
    '생활정보': '대상 분기 또는 조건 표, 실제 신청 순서와 준비/예외를 구분. 지원금·법률·기한은 공식 원문만. 편집부 예시는 명시.',
    '건강': '공식 보건기관 근거. 실천 흐름과 기록 예시를 구분. 진단·치료·효능을 단정하거나 개인 판정 점수를 만들지 않기. 필요한 상담 기준 설명.',
    '리뷰': '사용 장면과 비교 기준 표를 제시. 실제 모델은 공식 사양과 확인일 연결. 직접 써보지 않은 후기·측정값·순위·가격을 창작하지 말기. 사양 비교/실측/구매 기준의 범위를 밝히기.',
    '테크': '기존 방식과 변화 비교, 단계/주체별 작동 원리를 의미 있는 HTML로 도식화. 실제 지원 조건과 한계, 설정/복구 확인 포함. 구현 상세는 독자 판단에 필요한 만큼만.',
    '생산성': '권한/방법 선택표와 실제 실행 순서, 편집부 실무 예시, 막힐 때의 해결 방법. 실제 화면을 확인하지 않고 캡처/사용 후기라고 주장하지 않기. 절감시간·효과 수치를 만들지 않기.',
}


def category_writing_rules(category):
    if category not in CATEGORY_SECTIONS:
        return ''
    sections = '\n'.join(f'{i+1}. <section id="{key}"><h2>{label}</h2>상세 본문</section>'
                         for i, (key, label) in enumerate(zip(SECTION_IDS, CATEGORY_SECTIONS[category])))
    return f'''\n=== 승인된 카테고리 포맷 {VERSION}: {category} ===
공통 레이아웃 지시보다 우선한다. quick-answer 요약 뒤 다음 5개 section을 순서대로 작성:
{sections}
H2 문구는 주제에 맞게 다듬되 section id는 유지한다.
reader-overview와 reader-details에는 각각 독립적인 설명 p를 최소 2개 포함한다.
요약·표 반복만으로 채우지 말고 판단 근거, 조건 차이, 예외, 실제 행동을 충분히 설명한다.
reader-overview/process/details 중 적어도 하나에 비교 table, 조건 dl,
또는 ol data-visual="steps" 도식을 포함한다. 사실 수치/순서를 만들어 도식에 채우지 않는다.
reader-faq에는 h3 질문 + p 답변을 최소 3쌍 쓴다. 제목에 FAQ 또는 자주 묻는 질문을 포함한다.
reader-check에는 ul data-visual="checklist"로 3~5개 개인 확인 항목을 쓴다.
체크는 자가 점검이지 진단/자동 확인/신청이 아니다. 체크박스·메뉴·CSS·JS는 코드가 추가한다.
{RULES[category]}
근거 출처는 공식 원문을 연결. 편집부 예시는 예시라고 밝힌다. 핵심 제약은 FAQ 밖에도 설명한다.
'''


def category_format_issues(html, category):
    if category not in CATEGORY_SECTIONS:
        return []
    soup = BeautifulSoup(html, 'html.parser')
    issues = []
    for key in SECTION_IDS:
        sections = soup.find_all('section', id=key)
        if len(sections) != 1 or not sections[0].find('h2'):
            issues.append(f'카테고리 포맷 필수 섹션 없음/중복: {key}')
            continue
        if key in ('reader-overview', 'reader-details'):
            ps = [p for p in sections[0].find_all('p') if p.get_text(strip=True) and not p.find_parent(['li','td'])]
            if len(ps) < 2:
                issues.append(f'카테고리 포맷 상세 설명 부족: {key}')
    if not soup.select_one('#reader-check ul[data-visual="checklist"] li'):
        issues.append('카테고리 포맷 최종 점검 없음')
    if not soup.select_one('#reader-overview table, #reader-overview dl, #reader-process table, #reader-process dl, #reader-details table, [data-visual="steps"]'):
        issues.append('카테고리 포맷 도식 없음')
    return issues


# Inherit the approved readable body styles, then scope menu behavior locally.
CSS = RECRUITMENT_CSS.replace('wpab-recruitment', 'wpab-menu-reader') + '''
.wpab-menu-reader [data-reader-menu]{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin:24px 0;padding:6px;border:1px solid var(--line);border-radius:8px;background:#f2f5f7}
.wpab-menu-reader [data-reader-menu] :is(button,a){font:inherit;font-size:14px;font-weight:650;line-height:1.5;text-align:center;display:block;border:0;border-radius:5px;background:transparent;color:var(--ink);padding:12px 8px;text-decoration:none;cursor:pointer}
.wpab-menu-reader [data-reader-menu] button[aria-selected="true"]{background:var(--blue);color:white}
.wpab-menu-reader [hidden]{display:none!important}
.wpab-menu-reader [data-reader-panel]>:first-child{margin-top:0}
.wpab-menu-reader [data-reader-panel] h2:first-child{margin-top:18px}
.wpab-menu-reader .wpab-all-view>[data-reader-panel]+[data-reader-panel]{border-top:1px solid var(--line);padding-top:22px;margin-top:28px}
.wpab-menu-reader .wpab-personal-check{display:flex;align-items:flex-start;gap:12px;cursor:pointer}
.wpab-menu-reader .wpab-personal-check input{flex:none;width:19px;height:19px;margin:7px 0 0;accent-color:var(--blue)}
.wpab-menu-reader .wpab-personal-check input:checked+span{color:var(--muted);text-decoration:line-through}
.wpab-menu-reader :is(.wpab-check-note,.wpab-check-progress){font-size:13px;color:var(--muted)}
.wpab-menu-reader :is(button,input):focus-visible{outline:3px solid var(--blue);outline-offset:3px}
.wpab-menu-reader [data-reader-panel]{scroll-margin-top:24px}
@container(max-width:500px){.wpab-menu-reader [data-reader-menu] :is(button,a){font-size:13px;padding:12px 4px}}
@media print{.wpab-menu-reader [data-reader-menu]{display:none}.wpab-menu-reader [data-reader-panel][hidden]{display:block!important}.wpab-menu-reader details>*{display:block!important}}
'''


def apply_category_layout(html, category):
    """Format approved categories; never synthesize or discard editorial text.

    Menu links are functional anchors until JS enhances them. Sources, notices,
    ads, related links and schema remain outside hidden panels.
    """
    if category not in COLORS:
        return html
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('.wpab-article')
    if article is None:
        raise ValueError('Category layout requires shared article wrapper')
    if article.get('data-reader-version') == VERSION:
        return html
    article['class'] = list(dict.fromkeys([*article.get('class', []), 'wpab-menu-reader']))
    article['data-reader-version'] = VERSION
    article['data-reader-category'] = category
    for node in article.select('[style]'):
        if node.name not in ('ins', 'iframe') and not node.find_parent('ins'):
            del node['style']
    # Monetization is inserted before nested H2s by the existing renderer.
    # Extract only explicitly owned blocks so whole editorial sections remain tabs.
    for block in list(article.select('[data-monetization]')):
        article.append(block.extract())
    for table in article.find_all('table'):
        table['style'] = 'width:100%;border-collapse:collapse;'
    # Reader layout can retain a legacy single wrapper. Unwrap structural wrappers
    # so headings can be grouped without swallowing sources or monetization.
    for node in list(article.find_all(['div','section'], recursive=False)):
        if node.get('id') not in ('quick-answer','verified-sources') and node.find('h2') and len(node.find_all('h2')) > 1:
            node.unwrap()
    toc = article.select_one('#article-toc')
    if toc:
        toc.decompose()
    nav = soup.new_tag('nav', attrs={'data-reader-menu':'1', 'aria-label':'내용 메뉴'})
    panels = soup.new_tag('div', attrs={'data-reader-panels':'1'})
    current = None
    protected_ids = {'quick-answer','verified-sources','policy-notice','policy-disclaimer','coupang-disclosure','coupang-prep-box'}
    for node in list(article.contents):
        if not isinstance(node, Tag):
            continue
        # Keep provider-owned scripts/ads and non-editorial footer sections visible.
        if (node.get('id') in protected_ids or node.name in ('script','style','ins')
                or node.select_one('ins.adsbygoogle') or node.get('data-monetization')):
            continue
        heading = node if node.name == 'h2' else node.find('h2')
        if heading:
            current = soup.new_tag('section', attrs={'data-reader-panel':'1'})
            current['id'] = 'reader-panel-' + str(len(panels.find_all(recursive=False)))
            panels.append(current)
            link = soup.new_tag('a', href='#'+current['id'])
            labels = dict(zip(SECTION_IDS, CATEGORY_SECTIONS.get(category, ())))
            labels.update({'recruitment-facts':'모집 조건', 'recruitment-details':'직무·조건', 'recruitment-prepare':'준비 가이드', 'recruitment-check':'최종 점검'})
            link.string = labels.get(node.get('id'), heading.get_text(' ', strip=True))
            nav.append(link)
        if current is not None:
            current.append(node.extract())
    if len(panels.find_all(recursive=False)) >= 2:
        all_link = soup.new_tag('a', href='#quick-answer')
        all_link.string = '전체 보기'
        nav.append(all_link)
        quick = article.find(id='quick-answer', recursive=False)
        if quick:
            quick.insert_after(nav)
        else:
            article.insert(0, nav)
        nav.insert_after(panels)
    else:
        # Preserve even malformed/legacy articles; quality gating is separate.
        for panel in list(panels.children):
            for node in list(panel.contents):
                article.append(node.extract())
    for checklist in article.select('[data-visual="checklist"]'):
        note = soup.new_tag('p', attrs={'class':'wpab-check-note'})
        note.string = '개인 점검용입니다. 다른 방문자와 공유되지 않으며 새로고침하면 초기화됩니다. 실제 신청·설정·진단을 수행하지 않습니다.'
        checklist.insert_before(note)
    for card in article.select('[data-faq-card]'):
        if card.name != 'details':
            heading = card.find('h3', recursive=False)
            if heading:
                card.name = 'details'
                heading.wrap(soup.new_tag('summary'))
    style = soup.find('style', id='wpab-reading-styles')
    if style is None:
        style = soup.new_tag('style', id='wpab-reading-styles'); article.insert_before(style)
    style.string = ' '.join(CSS.split()) + '.wpab-article.wpab-menu-reader[data-reader-category="' + category + '"]{--blue:' + COLORS[category] + ';}'
    script = soup.new_tag('script', id='wpab-category-reader')
    script.string = Path(__file__).with_name('category_reader.js').read_text(encoding='utf-8')
    article.insert_after(script)
    return str(soup)
