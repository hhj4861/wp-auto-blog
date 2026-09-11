"""Topic-specific shopping queries, not verified products or publication approval."""
from __future__ import annotations

import re
import unicodedata


def product_search_guidance(category: str, keyword: str, topic: str) -> str:
    """Keep suggestions narrow; unmatched topics need a human product decision."""
    context = re.sub(r'\s+', '', unicodedata.normalize('NFKC', keyword + ' ' + topic)).lower()
    items: list[tuple[str, str, str]] = []
    note = ''
    if category == '건강':
        if '대상포진' in context and any(term in context for term in ('증상', '통증', '발진', '물집', '진료')):
            items = [
                ('루즈핏 순면 티셔츠', '편하게 입는 일상 의류',
                 '실제 면 함량, 넉넉한 치수, 거친 장식·봉제선 유무 확인'),
                ('건강 기록 노트', '진료 시 전달할 증상·발생 시각 기록',
                 '날짜·시간과 증상을 자유롭게 적을 수 있는 구성 확인'),
            ]
            note = ('생활용품·기록용 후보입니다. 약·연고·면역 영양제나 치료 효과를 표방하는 상품은 제외하세요. '
                    '의류 검색어는 NHS의 헐렁한 옷 착용 안내를 참고했습니다.\n'
                    '참고: https://www.nhs.uk/conditions/shingles/')
        elif '기관지' in context and any(term in context for term in ('음식', '식품', '배즙', '도라지')):
            items = [
                ('배즙', '본문에서 다루는 배를 일반식품으로 소개',
                 '원재료·배 함량·당류·알레르기 표시 확인'),
                ('도라지차', '본문에서 다루는 도라지의 식품 형태 소개',
                 '일반식품 여부, 원재료와 당류 표시 확인'),
            ]
            note = '본문에 실제 등장하는 식재료만 골라주세요. 기관지 치료·예방·효능을 보장하는 상품명은 제외하세요.'
        elif any(term in context for term in ('초기증상', '진료준비', '진료전')):
            items = [('건강 기록 노트', '진료 시 전달할 증상·발생 시각 기록',
                      '날짜·시간·증상을 자유롭게 적는 구성 확인')]
            note = '기록용 후보입니다. 진단·치료용 제품이나 영양제를 임의로 선택하지 마세요.'
        elif any(term in context for term in ('홈트', '스트레칭', '요가')):
            items = [('미끄럼방지 운동 매트', '본문 운동을 할 때 사용하는 바닥 용품',
                      '운동 공간에 맞는 크기, 두께와 미끄럼방지 표기 확인')]
            note = '본문의 운동과 맞는 일반 운동용품만 골라주세요. 통증 치료·재활 효과는 전제하지 않습니다.'
    elif category == '취업':
        # Prefer the measured keyword; a topic can mention other exams in comparisons.
        measured = re.sub(r'\s+', '', unicodedata.normalize('NFKC', keyword)).lower()
        exam = None
        for name in ('전기산업기사', '전기기사', '산업안전산업기사', '산업안전기사',
                     '정보처리산업기사', '정보처리기사', '사회복지사1급', '요양보호사',
                     '장례지도사', '직업상담사2급', '공인중개사', '한국사능력검정',
                     'sqld', 'sqlp', 'adsp', '토익스피킹', '토익라이팅', '토익브릿지',
                     '토익', '한국어능력시험'):
            if name in measured:
                exam = name.upper() if name in {'sqld', 'sqlp', 'adsp'} else name
                break
        computer = re.search(r'(?:컴활|컴퓨터활용능력)([12]급)?', measured)
        if computer:
            exam = '컴퓨터활용능력' + (' ' + computer[1] if computer[1] else '')
        if exam:
            stages = [stage for stage in ('필기', '실기') if stage in measured]
            if not stages:
                stages = [stage for stage in ('필기', '실기') if stage in context]
            suffixes = stages or ['']
            items = [((exam + ' ' + stage + ' 기출문제집').replace('  ', ' '),
                      '글의 시험 준비·자가점검에 참고할 교재',
                      '시험명·급수·과목·최신 출제기준 일치, 해설과 모의문제 수록 여부 확인')
                     for stage in suffixes]
            note = '책의 판·적용 연도를 확인하세요. 특정 교재 구매가 합격이나 합격률을 보장하지 않습니다.'
        elif any(term in measured for term in ('면접', '자기소개서', '이력서')):
            items = [('취업 면접 자기소개서 워크북', '답변과 경험을 정리하는 연습 자료',
                      '지원 직무와 맞는 문항, 작성 공간과 실제 목차 확인')]
    elif category == '생활정보':
        if any(term in context for term in ('세금', '소득세', '세금계산서', '연말정산', '영수증')):
            items = [('영수증 정리 파일', '신고·정산에 필요한 종이 증빙 보관',
                      '서류 크기, 분류 칸과 라벨 부착 가능 여부 확인')]
            note = '종이 서류 보관용 후보입니다. 전자신고만 다루는 글 등 본문과 연결되지 않으면 선택하지 마세요.'
        elif any(term in context for term in ('이사준비', '이사체크', '이삿짐')):
            items = [('이사 포장 박스', '본문의 짐 분류·포장에 사용',
                      '상자 크기·재질·손잡이와 묶음 수량 확인'),
                     ('이사 분류 라벨', '상자별 방·내용물 표시', '부착면과 라벨 크기 확인')]
        elif any(term in context for term in ('여권', '해외여행준비', '여행준비물')):
            items = [('여권 수납 파우치', '여행 서류를 한곳에 보관',
                      '여권·탑승권이 들어가는 크기와 잠금 방식 확인')]

    if not items:
        return ('쿠팡에서 검색할 상품\n'
                '이 주제에 직접 연결되는 상품 검색어를 자동으로 정하지 못했습니다.\n'
                '글에서 실제 사용하는 물건·교재·식재료가 있는지 먼저 확인해 주세요. '
                '적합한 상품이 없으면 링크를 억지로 보내지 말고 대기해 주세요.')
    lines = ['쿠팡에서 검색할 상품 (아래 검색어를 복사하세요)']
    for index, (query, purpose, criteria) in enumerate(items, 1):
        lines.extend([f'{index}. 검색어: {query}', f'   용도: {purpose}', f'   선택 기준: {criteria}'])
    if note:
        lines.append(note)
    lines.append('검색 후보이며 판매 여부·가격은 확인하지 않았습니다. 본문과의 관련성은 링크 수신 후 다시 검수합니다.')
    return '\n'.join(lines)
