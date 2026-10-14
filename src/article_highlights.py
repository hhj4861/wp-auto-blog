"""Evidence-written highlights shared by all six reading formats.

Layout never extracts/truncates prose to guess facts; legacy bodies stay intact.
"""
from bs4 import BeautifulSoup

PRIORITIES = {
    '취업': '지원 대상 / 접수 기한 / 지원 경로. 자격증·상시 준비 글은 응시 조건·준비 범위·확인 경로로 바꾸고 모집 마감을 만들지 않는다.',
    '생활정보': '대상 / 준비 사항 / 신청·이용 경로',
    '건강': '확인된 사실 / 불확실성 / 대응 조건. 집단 위험도를 개인 진단으로 바꾸지 않는다.',
    '리뷰': '맞는 용도 / 비교 차이 / 확인되지 않은 한계. 실측·사용 경험을 만들지 않는다.',
    '테크': '변경점 / 지원 환경 / 제한 조건',
    '생산성': '가능한 작업 / 사전 준비·권한 / 시작 방법',
}


def highlights_writing_rules(category):
    if category not in PRIORITIES:
        return ''
    return f'''
=== 첫 화면 핵심 포맷: article-highlights-v1 ===
앞선 quick-answer의 일반 문단 지시보다 우선한다. 기존 상세 섹션·해설은 유지한다.
<section id="quick-answer" data-highlights="1">
<p data-highlight="conclusion">독자 질문에 답하는 짧은 결론 한 문장</p>
<dl data-highlight="facts">
<div><dt>짧은 항목명</dt><dd>핵심 조건과 예외를 함께 쓴 짧은 답변</dd></div>
</dl>
<aside data-highlight="action"><p>해당 대상·기간·예외를 포함한 구체적인 다음 행동</p></aside>
</section>
위 문구는 구조 예시이며 그대로 출력하지 않는다. facts의 div는 보통 3개,
근거가 부족하면 확인 가능한 1~2개만 쓴다. 항목을 채우려고 사실을 만들지 않는다.
이 카테고리의 정보 우선순위: {PRIORITIES[category]}
결론은 조건부·예정·불확실 정보를 확정 사실로 바꾸지 않는다. 중요한 예외·대상·기간을
짧게 보이려고 삭제하지 않는다. 상세 설명은 본문에 충분히 남긴다.
행동 권고가 원문에 없으면 해당 공식 안내에서 확인할 실제 항목을 구체적으로 제시하고
편집부 확인 제안이라고 밝힌다. 진단·치료·신청 가능 여부를 임의 판정하지 않는다.
링크는 제공된 공식 원문만 사용한다. 자료 확인일·출처 목록은 코드가 추가한다.
CSS·색상·글자 크기·메뉴·스크립트는 만들지 않는다.
'''


def highlights_issues(html, category):
    """New writer gate only. Legacy reformatting does not require new facts."""
    if category not in PRIORITIES:
        return []
    soup = BeautifulSoup(html, 'html.parser')
    blocks = soup.select('section#quick-answer[data-highlights="1"]')
    if len(blocks) != 1 or len(soup.select('#quick-answer')) != 1:
        return ['첫 화면 핵심 포맷 없음/중복: article-highlights-v1']
    quick = blocks[0]
    issues = []
    conclusions = quick.select('p[data-highlight="conclusion"]')
    if len(conclusions) != 1 or not conclusions[0].get_text(strip=True):
        issues.append('첫 화면 결론 없음/중복')
    facts = quick.select('dl[data-highlight="facts"]')
    items = facts[0].find_all('div', recursive=False) if len(facts) == 1 else []
    if not 1 <= len(items) <= 3 or any(
        len(item.find_all(tag, recursive=False)) != 1
        or not item.find(tag, recursive=False).get_text(strip=True)
        for item in items for tag in ('dt', 'dd')
    ):
        issues.append('첫 화면 핵심 조건은 항목명·답변 1~3쌍 필요')
    actions = quick.select('aside[data-highlight="action"]')
    if len(actions) != 1 or not actions[0].get_text(strip=True):
        issues.append('첫 화면 다음 행동 없음/중복')
    return issues


HIGHLIGHTS_CSS = '''
.wpab-menu-reader #quick-answer[data-highlights="1"]{border:1px solid var(--line);border-left:5px solid var(--blue);border-radius:8px;background:var(--tint);padding:24px 28px;margin-bottom:32px}
.wpab-menu-reader #quick-answer [data-highlight="conclusion"]{font-size:clamp(23px,2.8vw,32px);font-weight:750;line-height:1.45;letter-spacing:-.6px;margin:0 0 22px;max-width:36ch}
.wpab-menu-reader #quick-answer [data-highlight="facts"]{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));margin:0;padding:16px 0;border-block:1px solid var(--line)}
.wpab-menu-reader #quick-answer [data-highlight="facts"]>div{display:block;padding:0 18px;border:0;border-right:1px solid var(--line)}
.wpab-menu-reader #quick-answer [data-highlight="facts"]>div:first-child{padding-left:0}
.wpab-menu-reader #quick-answer [data-highlight="facts"]>div:last-child{border-right:0}
.wpab-menu-reader #quick-answer [data-highlight="facts"] dt{font-size:14px;font-weight:500;color:var(--muted)}
.wpab-menu-reader #quick-answer [data-highlight="facts"] dd{margin:6px 0 0;font-size:19px;font-weight:700;line-height:1.55}
.wpab-menu-reader #quick-answer [data-highlight="action"]{margin-top:20px;padding:15px 18px;border-radius:6px;background:#fff}
.wpab-menu-reader #quick-answer [data-highlight="action"] p{margin:0;font-size:16px;line-height:1.75}
.wpab-menu-reader #quick-answer [data-highlight="sources"]{font-size:13px;line-height:1.7;margin:15px 0 0;color:var(--muted)}
@container(max-width:600px){.wpab-menu-reader #quick-answer[data-highlights="1"]{padding:18px}.wpab-menu-reader #quick-answer [data-highlight="facts"]{grid-template-columns:1fr;padding:0}.wpab-menu-reader #quick-answer [data-highlight="facts"]>div{display:grid;grid-template-columns:minmax(70px,1fr) minmax(0,2fr);gap:12px;padding:12px 0;border-right:0;border-bottom:1px solid var(--line)}.wpab-menu-reader #quick-answer [data-highlight="facts"]>div:last-child{border-bottom:0}.wpab-menu-reader #quick-answer [data-highlight="facts"] dd{margin:0;font-size:18px}.wpab-menu-reader #quick-answer [data-highlight="conclusion"]{font-size:24px}}
@media print{.wpab-menu-reader #quick-answer[data-highlights="1"]{break-inside:avoid}}
'''


def add_highlights_sources(soup, article):
    """Reuse verified provenance without assigning every claim to the first source."""
    quick = article.select_one('#quick-answer[data-highlights="1"]')
    sources = article.select_one('#verified-sources')
    if quick is None or sources is None or quick.select_one('[data-highlight="sources"]'):
        return
    line = soup.new_tag('p', attrs={'data-highlight': 'sources'})
    link = soup.new_tag('a', href='#verified-sources')
    link.string = '공식 근거와 자료 확인일 보기'
    line.append(link)
    quick.append(line)
