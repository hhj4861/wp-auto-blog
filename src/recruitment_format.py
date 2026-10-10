"""Approved recruitment-reader-v1: writing contract and isolated WordPress body.

Source of approval: docs/design/trendpulse-reading-concept.html, enriched v2.
Facts remain the writer/evidence review's responsibility; layout never invents them.
"""
from bs4 import BeautifulSoup

FORMAT_VERSION = 'recruitment-reader-v1'

RECRUITMENT_WRITING_RULES = '''
=== 승인된 채용 전용 포맷: recruitment-reader-v1 (공통 디자인/구성보다 우선) ===
취업 카테고리의 신규 글·리프레시에 적용한다. 요약으로 내용을 줄이지 말고,
지원 판단과 실제 준비에 필요한 상세 해설을 충분히 쓴다. 주제가 자격증/면접 등
상시 준비법이면 공고·모집인원·마감일을 만들지 말고 관련 조건과 준비 내용으로 구성한다.
HTML 본문 구성 (제목은 기존 H1/SEO 규칙 유지):
1. <section id="quick-answer">에 핵심 답변 2~3문장.
   공고에 접수 마감이 있으면 <aside data-recruitment="deadline"><strong>마감일과 시간</strong>
   <p>연도·시간대·예정 여부</p><a href="제공된 공식 URL">공식 공고 보기</a></aside>.
   마감 정보가 없으면 aside 생략. 실시간 접수 여부나 D-day를 계산해 쓰지 않는다.
2. <section id="recruitment-facts"><h2>지원 판단에 필요한 조건</h2>…</section>.
   단일 공고는 <dl><div><dt>항목</dt><dd>내용</dd></div></dl>로
   모집 분야·인원·자격·근무지·필수/우대 조건을 비교 가능하게 표현한다.
   여러 기업은 <div data-recruitment="companies"><section><h3>회사명</h3>
   <p>직무·지역·지원 조건 차이</p><a href="제공된 공식 URL">공고 보기</a></section>…</div>.
   같은 조건을 모든 회사에 무단 확장하지 않는다. 미공개 조건은 추정하지 않는다.
3. 실제 전형 일정이 있으면 별도 H2와 <ol data-recruitment="timeline" aria-label="공식 전형 일정">
   <li><strong>전형명</strong><p>확인된 날짜·예정 여부·설명</p></li>…</ol>.
   원문에 있는 모든 필요한 전형을 보존한다. 채용 순서와 준비 권장 순서를 섞지 않는다.
4. <section id="recruitment-details"><h2>직무·조건 자세히 읽기</h2>…</section>.
   직무의 실제 업무, 지원자에게 중요한 조건 차이, 예외를 2개 이상의 단락으로 설명한다.
   표 내용을 반복하지 말고 공고 근거를 연결해 무엇을 비교해야 하는지 설명한다.
   연봉·합격률·채용인원·시험과목이 미공개라면 만들지 않는다.
5. <section id="recruitment-prepare"><h2>지원 준비 가이드</h2>…</section>.
   <p>편집부 준비 제안이며 공식 전형/평가 기준이 아닙니다.</p>로 구분하고,
   <ol data-visual="steps"><li><strong>준비 단계</strong><p>구체적인 행동과 남길 결과물</p></li>…</ol>.
   이어 2개 이상의 상세 단락으로 직무·조건에 맞춘 준비 설명이나 경험 정리 예시를 쓴다.
   예시는 편집부의 작성 연습임을 밝히고 실제 문항·합격 답안·직접 경험으로 꾸미지 않는다.
   수치·효과·우대 같은 사실 주장은 공식 원문으로만 뒷받침한다.
6. <section id="recruitment-check"><h2>제출 전 확인</h2>
   <ul data-visual="checklist"><li><strong>점검 항목</strong>실제로 확인할 것</li>…</ul></section>.
7. <h2>FAQ</h2> 뒤 <h3>질문</h3><p>답변</p> 3쌍. 실제 조건의 헷갈리는 지점을 다룬다.
위 section id는 필수이며 각 section 안에 해당 내용과 H2를 넣는다.
예외적으로 공식 일정 도식은 준비 단계/최종 점검과 별도로 허용한다.
광고·목차·관련 글·출처 목록·CSS·스크립트·사이트 헤더는 코드가 관리한다.
임의 색상/고정 너비/인라인 스타일을 만들지 않는다. 중요 정보는 접힌 FAQ 안에만 넣지 않는다.
'''

RECRUITMENT_CSS = '''
.wpab-article.wpab-recruitment{--ink:#243047;--blue:#354edb;--line:#dfe5ee;--muted:#59677a;--teal:#0a7477;box-sizing:border-box;max-width:960px;margin:24px auto;padding:36px 40px;background:#fff;color:var(--ink);border-radius:12px;font-family:"Apple SD Gothic Neo","Malgun Gothic",sans-serif;font-size:17px;line-height:1.85;word-break:keep-all;overflow-wrap:anywhere;color-scheme:light;container-type:inline-size}
.wpab-recruitment *{box-sizing:border-box;min-width:0}
.wpab-recruitment :is(p,li,dd,td){color:var(--ink);font-size:1em;font-weight:400;line-height:1.85}
.wpab-recruitment p{max-width:74ch;margin:14px 0}
.wpab-recruitment :is(h2,h3,strong,dt){color:var(--ink);-webkit-text-fill-color:currentColor;background:none;font-weight:700}
.wpab-recruitment h2{font-size:26px;line-height:1.45;margin:38px 0 18px;letter-spacing:-.6px;scroll-margin-top:24px}
.wpab-recruitment h3{font-size:20px;line-height:1.55;margin:24px 0 10px}
.wpab-recruitment a{color:var(--blue);text-decoration:underline;text-underline-offset:3px}
.wpab-recruitment :is(a,summary,[tabindex]):focus-visible{outline:3px solid var(--blue);outline-offset:4px}
.wpab-recruitment #quick-answer{padding:20px 24px;background:#f4f7fc;border-radius:10px;margin-bottom:24px}
.wpab-recruitment #quick-answer p:first-child{margin-top:0}
.wpab-recruitment #quick-answer p:last-child{margin-bottom:0}
.wpab-recruitment [data-recruitment="deadline"]{background:#ecebff;border-radius:8px;padding:18px 22px;margin:20px 0}
.wpab-recruitment [data-recruitment="deadline"]>strong{font-size:26px;color:var(--blue)}
.wpab-recruitment #article-toc{padding:12px 0;margin:22px 0;border-block:1px solid var(--line)}
.wpab-recruitment summary{cursor:pointer;color:var(--ink);font-weight:650;line-height:1.6;padding:12px 0}
.wpab-recruitment dl>div{display:grid;grid-template-columns:minmax(90px,150px) 1fr;gap:20px;padding:15px 0;border-bottom:1px solid var(--line)}
.wpab-recruitment dd{margin:0}
.wpab-recruitment [data-recruitment="companies"]{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));border-top:2px solid var(--blue);gap:0}
.wpab-recruitment [data-recruitment="companies"]>section{padding:18px;border-bottom:1px solid var(--line);border-right:1px solid var(--line)}
.wpab-recruitment [data-recruitment="companies"] h3{margin:0 0 12px}
.wpab-recruitment [data-recruitment="timeline"]{display:flex;flex-wrap:wrap;list-style:none;padding:0;margin:30px 0;gap:0}
.wpab-recruitment [data-recruitment="timeline"]>li{flex:1 1 140px;border-top:3px solid var(--line);padding:20px 16px 6px 0;margin:0}
.wpab-recruitment [data-recruitment="timeline"] strong{color:var(--blue)}
.wpab-recruitment [data-recruitment="timeline"] p{font-size:15px;margin:8px 0}
.wpab-recruitment [data-visual]{padding:0;list-style:none;margin:24px 0}
.wpab-recruitment [data-visual]>li{padding:14px 0;border-bottom:1px solid var(--line);list-style:none;margin:0}
.wpab-recruitment [data-visual="steps"]>li{display:grid;grid-template-columns:30px 1fr;gap:14px}
.wpab-recruitment [data-step-number]{display:flex;justify-content:center;align-items:center;width:30px;height:30px;border-radius:50%;background:#ecebff;color:var(--blue);font-size:15px;font-weight:700}
.wpab-recruitment [data-visual-copy]>strong{display:block}
.wpab-recruitment [data-visual-copy] p{margin:7px 0}
.wpab-recruitment [data-visual="checklist"] [data-visual-copy]{display:grid;grid-template-columns:minmax(80px,130px) 1fr;gap:12px}
.wpab-recruitment :is(#recruitment-details,#recruitment-prepare,#recruitment-check){border-top:1px solid var(--line);margin-top:34px;padding-top:6px}
.wpab-recruitment [data-faq-card]{border-bottom:1px solid var(--line);padding:0}
.wpab-recruitment [data-faq-card] h3{display:inline;font-size:17px;margin:0}
.wpab-recruitment [data-faq-card] p{margin:0 0 18px}
.wpab-recruitment :is(#policy-notice,#verified-sources){font-size:14px;color:var(--muted);border-top:1px solid var(--line);margin-top:30px;padding-top:12px}
.wpab-recruitment table{width:100%;border-collapse:collapse;font-size:15px}
.wpab-recruitment :is(th,td){text-align:left;padding:12px;border:1px solid var(--line)}
.wpab-recruitment th{background:#f4f7fc;color:var(--ink)}
.wpab-recruitment ins.adsbygoogle{max-width:100%;overflow:hidden}
.wpab-recruitment [data-table-scroll]{max-width:100%;overflow-x:auto;margin:20px 0}
.single-post .entry:has(.wpab-recruitment){max-width:960px;margin:auto}
@media(max-width:600px){.wpab-article.wpab-recruitment{padding:24px 20px;font-size:16px;border-radius:0}.wpab-recruitment h2{font-size:23px}}
@container(max-width:600px){.wpab-recruitment dl>div{grid-template-columns:1fr;gap:6px}.wpab-recruitment [data-recruitment="companies"]{grid-template-columns:1fr}.wpab-recruitment [data-recruitment="timeline"]{display:block}.wpab-recruitment [data-recruitment="timeline"]>li{border-top:0;border-left:2px solid var(--line);padding:0 0 20px 20px}.wpab-recruitment [data-visual="checklist"] [data-visual-copy]{grid-template-columns:1fr;gap:5px}}
'''


def recruitment_format_issues(html: str) -> list[str]:
    """Block thin/incomplete newly generated recruitment drafts, never invent prose."""
    soup = BeautifulSoup(html, 'html.parser')
    issues = []
    for section_id in ('recruitment-facts', 'recruitment-details', 'recruitment-prepare', 'recruitment-check'):
        section = soup.find('section', id=section_id)
        if not section or not section.find('h2') or not section.get_text(strip=True):
            issues.append(f'채용 포맷 필수 섹션 없음: {section_id}')
            continue
        if section_id in ('recruitment-details', 'recruitment-prepare'):
            # Standalone explanation, not a title or duplicated summary list alone.
            paragraphs = [p for p in section.find_all('p') if not p.find_parent('li') and p.get_text(strip=True)]
            if len(paragraphs) < 2:
                issues.append(f'채용 포맷 상세 설명 부족: {section_id}')
    facts = soup.find(id='recruitment-facts')
    if facts and not facts.select_one('dl, table, [data-recruitment="companies"]'):
        issues.append('채용 포맷 조건 비교 구조 없음')
    prepare = soup.find(id='recruitment-prepare')
    if prepare and not prepare.select_one('ol[data-visual="steps"] li'):
        issues.append('채용 포맷 준비 단계 없음')
    check = soup.find(id='recruitment-check')
    if check and not check.select_one('ul[data-visual="checklist"] li'):
        issues.append('채용 포맷 최종 점검 없음')
    return issues


def apply_recruitment_layout(html: str) -> str:
    """Replace legacy dark styling, preserving all content, links, ads and schema."""
    soup = BeautifulSoup(html, 'html.parser')
    article = soup.select_one('.wpab-article')
    if article is None:
        raise ValueError('Recruitment layout requires the shared article wrapper')
    article['class'] = list(dict.fromkeys([*article.get('class', []), 'wpab-recruitment']))
    article['data-article-format'] = FORMAT_VERSION
    for node in article.select('[style]'):
        # Ad slot sizing belongs to the ad provider. The editorial body does not.
        if node.name not in ('ins', 'iframe') and not node.find_parent('ins'):
            del node['style']
    for table in article.find_all('table'):
        table['style'] = 'width:100%;border-collapse:collapse;'
    for card in article.select('[data-faq-card]'):
        if card.name == 'details':
            continue
        heading = card.find('h3', recursive=False)
        if heading:
            card.name = 'details'
            summary = soup.new_tag('summary')
            heading.wrap(summary)
    style = soup.find('style', id='wpab-reading-styles')
    if style is None:
        style = soup.new_tag('style', id='wpab-reading-styles')
        article.insert_before(style)
    style.string = RECRUITMENT_CSS
    return str(soup)
