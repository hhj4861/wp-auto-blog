"""Bound review discovery to measurable buying questions and relevant documents.

These lexical checks only prune research inputs. Search intent and independently
fetched sources must still pass the existing semantic publication gates.
"""
import re
import unicodedata
from urllib.parse import urlsplit

SEEDS = ('무선청소기흡입력', '공기청정기평수', '노트북램', '로봇청소기문턱')
# Query hints only: every returned candidate needs its own measured demand.
# Rotating the starting point prevents a scarce category always sampling one family.
EXPANSION_SEEDS = (
    '모니터주사율', '제습기소비전력', '가벼운무선청소기', '노트북SSD',
    '로봇청소기직배수설치', '공기청정기필터', '스마트폰배터리', '모니터해상도',
    '무선청소기소음', '노트북배터리', '제습기평수', '로봇청소기먼지비움',
)
SHORTLIST_SKIP_CODES = frozenset({
    'purchase_intent_unclear', 'scope_too_broad', 'maintenance_intent',
    'duplicate_intent', 'category_mismatch', 'insufficient_specificity',
})


PRODUCTS = {
    '청소기': ('청소기', 'vacuum', 'cordzero', 'jetbot', 'roborock'),
    '공기청정기': ('공기청정기', 'airpurifier', 'aircleaner', '퓨리케어', 'puricare'),
    '노트북': ('노트북', 'laptop', 'notebook', 'macbook', '맥북', '갤럭시북', '그램'),
    '모니터': ('모니터', 'monitor', 'display'),
    '스마트폰': ('스마트폰', 'smartphone', '아이폰', 'iphone', '갤럭시', 'galaxy'),
    '제습기': ('제습기', 'dehumidifier'),
}
FACETS = {
    '흡입력': ('흡입력', 'suction', 'airwatt'),
    '사용면적': ('사용면적', '적용면적', '평수', '권장면적', 'coverage', 'roomsize', 'cadr'),
    '문턱': ('문턱', '단차', '등반', 'threshold', 'obstacle', 'climbing'),
    '메모리': ('메모리', '램', 'memory', 'ram', '16기가', '32기가', '16gb', '32gb'),
    '저장장치': ('ssd', 'hdd', '저장장치', 'storage'),
    '배터리': ('배터리', '사용시간', 'battery', 'runtime'),
    '소비전력': ('소비전력', '전기요금', '전력소모', 'powerconsumption', 'energy'),
    '소음': ('소음', 'noise', 'decibel'),
    '무게': ('무게', 'weight'),
    '필터': ('필터', 'filter', 'hepa'),
    '화면': ('해상도', '주사율', '화면크기', 'resolution', 'refreshrate', 'screensize'),
    '호환': ('호환', '단자', '포트', 'compatib', 'connector', 'port'),
    '급배수설치': ('직배수', '급배수', '자동급수', 'waterconnection', 'drainage'),
    '먼지비움': ('먼지비움', '먼지비우기', '자동먼지수거', 'autoempty', 'autodust'),
}
# Colloquial query words never substitute for specification evidence in the body.
QUERY_FACET_ALIASES = {'무게': ('가벼운', '가벼움', '경량')}
MAINTENANCE = ('청소방법', '교체방법', '수리', '고장', '오류', '설정방법', '설치방법', '연결방법', '사용법')
UNBOUNDED_RECOMMENDATION = ('좋은', '추천', '순위', '가성비', '베스트')
NON_PURCHASE_URL = re.compile(
    r'help-library/.*(?:troubleshoot|poor-suction|how-to-clean|won-t|wont|replacement-lamp)'
    r'|/license/|selectcrtfcinfo|/freeboard|/product/list\.do', re.I)


def expansion_seeds(clock):
    offset = clock.date().toordinal() % len(EXPANSION_SEEDS)
    return EXPANSION_SEEDS[offset:] + EXPANSION_SEEDS[:offset]


def shortlist_skips(remaining, candidates, response):
    """Record model opinions, with an explicit missing-reason fallback."""
    proposed = {row.get('keyword') for row in candidates if isinstance(row, dict)
                and isinstance(row.get('keyword'), str)}
    skipped = response.get('skipped', []) if isinstance(response, dict) else []
    reasons = {}
    for row in skipped[:60] if isinstance(skipped, list) else []:
        if not isinstance(row, dict):
            continue
        keyword, code = row.get('keyword'), row.get('reason_code')
        if isinstance(keyword, str) and isinstance(code, str) and code in SHORTLIST_SKIP_CODES:
            reasons.setdefault(keyword, code)
    return [{'keyword': row['keyword'], 'reason_code': reasons.get(row['keyword'], 'not_reported'),
             'kind': 'model_shortlist_opinion'} for row in remaining if row['keyword'] not in proposed]


def compact(value):
    return re.sub(r'[^가-힣a-z0-9]', '', unicodedata.normalize('NFKC', value if isinstance(value, str) else '').lower())


def requirements(keyword):
    key = compact(keyword)
    products = [name for name, aliases in PRODUCTS.items()
                if any(x in (key.replace('갤럭시북', '').replace('galaxybook', '')
                             if name == '스마트폰' else key) for x in aliases)]
    # "그램" is a product family, not evidence of a RAM question.
    facet_key = key.replace('그램', '')
    facets = [name for name, aliases in FACETS.items()
              if any(x in facet_key for x in (*aliases, *QUERY_FACET_ALIASES.get(name, ())))]
    return products, facets


def discovery_issue(keyword):
    key = compact(keyword)
    products, facets = requirements(keyword)
    if not products:
        return 'review_product_unidentified'
    if any(word in key for word in MAINTENANCE):
        return 'review_maintenance_intent'
    if any(word in key for word in UNBOUNDED_RECOMMENDATION):
        return 'review_recommendation_unbounded'
    if not facets:
        return 'review_purchase_question_unbounded'
    return None


def relevant_source(keyword, source):
    if not isinstance(source, dict) or discovery_issue(keyword):
        return False
    products, facets = requirements(keyword)
    body = compact(source.get('excerpt', ''))
    title = compact(source.get('title', ''))
    try:
        path = urlsplit(source.get('url') or '').path
    except (ValueError, TypeError, AttributeError):
        return False
    if NON_PURCHASE_URL.search(path):
        return False
    if re.search(r'/all-[^/]+/?$', path):
        return False
    # All named facets must have body evidence; a navigation title is insufficient.
    return (all(any(alias in title + body for alias in PRODUCTS[name]) for name in products)
            and all(any(alias in (body.replace('그램', '').replace('program', '').replace('gram', '')
                                  if name == '메모리' else body)
                        for alias in FACETS[name]) for name in facets))


def source_hint(keyword):
    products, facets = requirements(keyword)
    return ('구매 전 판단 질문입니다. ' + ', '.join(products) + '의 ' + ', '.join(facets)
            + '를 직접 설명하는 국내 공식 제품 사양·비교표·시험 조건을 찾으세요. '
              '청소·고장 해결 도움말, 인증 등록 목록, 다른 제품 자료는 제외하세요. '
              '비교 질문은 비교 대상 양쪽의 동일 항목과 측정 조건을 확인하세요.')
