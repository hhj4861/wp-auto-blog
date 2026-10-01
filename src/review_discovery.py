"""Bound review discovery to measurable buying questions and relevant documents.

These lexical checks only prune research inputs. Search intent and independently
fetched sources must still pass the existing semantic publication gates.
"""
import re
import unicodedata
from urllib.parse import urlsplit

from src.search_query import validated_search_query

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
    '저장장치': ('ssd', 'hdd', '외장하드', 'harddrive', 'solidstatedrive'),
    '램': ('메모리', '램', 'ddr', 'memory', 'ram'),
}
FACETS = {
    '용량': ('용량', 'capacity', 'tb', 'gb', '테라', '기가'),
    '화면크기': ('인치', '형', 'inch', '화면크기', 'screensize'),
    '규격': ('ddr3', 'ddr4', 'ddr5', 'nvme', 'sata'),
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


# Shared by discovery, planning and independent coverage review. These are
# distinctions to verify in real evidence, never an unconditional approval.
BUYING_INTENT_GUIDANCE = """리뷰의 정보 목적에는 구매 전 비교·선택 판단도 포함됩니다.
단순 판매처 이동·주문·최저가 링크만 원하는 거래 목적과, 사양·조건을 비교해 고르려는 목적을 구분하세요.
상품 페이지가 검색 결과에 있다는 이유만으로 정보 목적을 부정하지 마세요. 제목·요약에
해당 선택 항목(무게·메모리·사용면적 등)이 실제 나타나는지 확인하고 근거 없는 의도는 만들지 마세요.
'가벼운무선청소기'의 핵심은 구성별 무게·사용 조건을 비교해 선택하는 것이며,
모든 판매 모델의 순위·최저가·직접 사용 후기를 자동으로 요구하지 않습니다.
'노트북램'은 검색 근거에 따라 구매 용량 선택이면 리뷰, 증설 작업 방법이면 테크입니다.
제품군+판단 항목 후보는 이름만으로 카테고리 불일치를 확정하지 말고 실제 검색으로 구분하세요.
대표 제품을 비교 예시로 쓰려면 서로 다른 제품의 실제 사양과 비교 조건을 공식 본문으로 입증하고,
선택 기준이라는 핵심 질문 전체에 답해야 합니다. 한 제품 소개만으로 전체 선택 질문을 대신하지 마세요.
실측 검색어·검색량·인용 조건은 유지하세요. 근거 없는 추천·우열·체험 주장은 허용하지 않습니다."""


def research_query(keyword):
    """Space known Korean buying terms, retaining exact measured characters."""
    terms = {'무선청소기', '로봇청소기', '가벼운', '경량'}
    for aliases in (*PRODUCTS.values(), *FACETS.values()):
        terms.update(word for word in aliases if re.fullmatch(r'[가-힣]+', word))
    pattern = '|'.join(re.escape(word) for word in sorted(terms, key=lambda word: (-len(word), word)))
    proposed = re.sub(pattern, lambda match: ' ' + match[0] + ' ', keyword)
    try:
        return validated_search_query(keyword, proposed)
    except ValueError:
        return validated_search_query(keyword)


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


def research_family(keyword):
    """Group buying questions across brand/spelling variants for research scheduling."""
    return tuple(map(tuple, requirements(keyword)))


def shortlist_research_candidates(skipped, limit, researched=()):
    """Investigate uncertainty, never turn a name-only opinion into approval.

    Call only for a well-formed, empty shortlist. Inputs have already passed
    measured demand, category, duplicate and cooldown filters. Prefer missing
    opinions and spread a small research budget across product/facet families.
    """
    eligible = [row for row in skipped
                if row['reason_code'] in {'not_reported', 'purchase_intent_unclear',
                                          'insufficient_specificity'}
                and not discovery_issue(row['keyword'])]
    chosen, families = [], {research_family(keyword) for keyword in researched}
    while eligible and len(chosen) < limit:
        eligible = [row for row in eligible if research_family(row['keyword']) not in families]
        if not eligible:
            break
        row = min(eligible, key=lambda row: row['reason_code'] != 'not_reported')
        eligible.remove(row)
        families.add(research_family(row['keyword']))
        chosen.append({'keyword': row['keyword'], 'search_query': research_query(row['keyword']),
                       'reason': 'bounded_research_of_shortlist_uncertainty',
                       'shortlist_reason_code': row['reason_code']})
    return chosen


def compact(value):
    return re.sub(r'[^가-힣a-z0-9]', '', unicodedata.normalize('NFKC', value if isinstance(value, str) else '').lower())


def numeric_constraints(text):
    text = unicodedata.normalize('NFKC', text if isinstance(text, str) else '').lower()
    text = re.sub(r'(ddr[345])(?=\d)', r'\1 ', text)
    # Compact Korean memory queries use DDR416G for DDR4 16 GB.
    text = re.sub(r'(ddr[345]\s+\d+)g(?![a-z])', r'\1gb', text)
    def numbers(pattern):
        return {(str(float(n)).removesuffix('.0'), unit) for n, unit in re.findall(pattern, text)}
    capacity = numbers(r'(?<![\d.])(\d+(?:\.\d+)?)\s*(tb|gb|테라(?:바이트)?|기가(?:바이트)?)(?![a-z])')
    capacity = {(n, 'tb' if unit.startswith('테라') else 'gb' if unit.startswith('기가') else unit)
                for n, unit in capacity}
    screen = numbers(r'(?<![\d.])(\d+(?:\.\d+)?)\s*(인치|inch(?:es)?|형)(?![a-z])')
    return {'capacity': capacity, 'screen': {(n, 'inch') for n, _ in screen},
            'standard': set(re.findall(r'ddr[345]|nvme|sata', text))}


def requirements(keyword):
    key = compact(keyword)
    products = [name for name, aliases in PRODUCTS.items()
                if name not in {'저장장치', '램'} and any(x in (key.replace('갤럭시북', '').replace('galaxybook', '')
                             if name == '스마트폰' else key) for x in aliases)]
    # Components are products in their own right; a laptop query remains a
    # laptop question and must still have laptop compatibility evidence.
    if not products:
        products = [name for name in ('저장장치', '램')
                    if any(x in key for x in PRODUCTS[name])]
    # "그램" is a product family, not evidence of a RAM question.
    facet_key = key.replace('그램', '')
    facets = [name for name, aliases in FACETS.items()
              if any(x in facet_key for x in (*aliases, *QUERY_FACET_ALIASES.get(name, ())))]
    if products == ['저장장치']:
        facets = [facet for facet in facets if facet != '저장장치']
    if products == ['램']:
        facets = [facet for facet in facets if facet != '메모리']
    # Numeric size/capacity must be explicit, not a stray substring in a model.
    constraints = numeric_constraints(keyword)
    facets = [facet for facet in facets if facet not in {'용량', '화면크기'}]
    if constraints['capacity']:
        facets.append('용량')
    if constraints['screen'] and any(x in products for x in ('노트북', '모니터', '스마트폰')):
        facets.append('화면크기')
    if products == ['저장장치'] and not any(x in facet_key for x in ('메모리', '램', 'memory', 'ram')):
        facets = [facet for facet in facets if facet != '메모리']
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


# Known brand constraints are input pruning, not proof that a document answers
# the question. Neutral institutional comparisons remain eligible for review.
BRAND_DOMAINS = (
    (('삼성', 'samsung', '갤럭시'), ('samsung.com',)),
    (('엘지', 'lg', '퓨리케어'), ('lge.co.kr', 'lg.com')),
    (('샌디스크', 'sandisk'), ('sandisk.com',)),
    (('킹스톤', 'kingston'), ('kingston.com',)),
    (('애플', 'apple', '맥북'), ('apple.com',)),
)


def named_brand_domains(keyword):
    key = compact(keyword)
    return {domain for aliases, domains in BRAND_DOMAINS
            if any(alias in key for alias in aliases) for domain in domains}


def storage_question(keyword):
    products, facets = requirements(keyword)
    return '저장장치' in products or '저장장치' in facets


def preferred_source_domains(keyword):
    brands = named_brand_domains(keyword)
    if storage_question(keyword):
        domains = ('sandisk.com', 'semiconductor.samsung.com', 'kingston.com')
        return [domain for domain in domains
                if not brands or any(domain == brand or domain.endswith('.' + brand) for brand in brands)]
    if '램' in requirements(keyword)[0]:
        return [domain for domain in ('semiconductor.samsung.com', 'kingston.com')
                if not brands or any(domain == brand or domain.endswith('.' + brand) for brand in brands)]
    if brands:
        return [domain for _, domains in BRAND_DOMAINS for domain in domains if domain in brands]
    return []


def prioritize_sources(keyword, sources, limit=3):
    # SSD choice requires drive/compatibility documents first. Laptop specs can
    # supplement these, but must not evict them just because fetched earlier.
    if storage_question(keyword):
        primary = [source for source in sources if any(
            term in compact(source.get('title', '')) for term in ('ssd', 'hdd', '저장장치'))
            and not re.search(r'/(?:notebook|galaxybook|macbook)/|/support/model/',
                              urlsplit(source['url']).path, re.I)]
        rest = [source for source in sources if source not in primary]
        return (diverse_sources(primary, limit) + diverse_sources(rest, limit))[:limit]
    return diverse_sources(sources, limit)


def relevant_source(keyword, source):
    if not isinstance(source, dict) or discovery_issue(keyword):
        return False
    products, facets = requirements(keyword)
    body = compact(source.get('excerpt', ''))
    title = compact(source.get('title', ''))
    try:
        parts = urlsplit(source.get('url') or '')
        path = parts.path
        host = (parts.hostname or '').lower()
    except (ValueError, TypeError, AttributeError):
        return False
    brands = named_brand_domains(keyword)
    known = {domain for _, domains in BRAND_DOMAINS for domain in domains}
    def belongs(domains):
        return any(host == domain or host.endswith('.' + domain) for domain in domains)
    if brands and belongs(known) and not belongs(brands):
        return False
    if NON_PURCHASE_URL.search(path):
        return False
    if re.search(r'/all-[^/]+/?$', path):
        return False
    requested = numeric_constraints(keyword)
    observed = numeric_constraints(source.get('excerpt', ''))
    if any(values and not values & observed[kind] for kind, values in requested.items()):
        return False
    # A comparison page can support one requested size; the independent review
    # must verify all alternatives across the final set of fetched documents.
    # All named facets must have body evidence; a navigation title is insufficient.
    return (all(any(alias in title + body for alias in PRODUCTS[name]) for name in products)
            and all(any(alias in (body.replace('그램', '').replace('program', '').replace('gram', '')
                                  if name == '메모리' else body)
                        for alias in FACETS[name]) for name in facets))


def source_hint(keyword):
    products, facets = requirements(keyword)
    detail = ('SSD 자체의 인터페이스(NVMe/SATA), 폼팩터, 용량, 노트북 호환 조건을 설명하는 '
              '저장장치 제조사 자료를 우선하세요. 노트북 본체의 SSD 탑재 용량만으로 '
              'SSD 선택 질문의 근거를 대신하지 마세요. ' if storage_question(keyword) else '')
    if named_brand_domains(keyword):
        detail += '검색어에 명시된 브랜드의 자료를 찾으세요. 다른 브랜드 본체 자료로 대체하지 마세요. '
    return (detail + '구매 전 판단 질문입니다. ' + ', '.join(products) + '의 ' + ', '.join(facets)
            + '를 직접 설명하는 국내 공식 제품 사양·비교표·시험 조건을 찾으세요. '
              '청소·고장 해결 도움말, 인증 등록 목록, 다른 제품 자료는 제외하세요. '
              '비교 질문은 비교 대상 양쪽의 동일 항목과 측정 조건을 확인하세요. '
              '특정 브랜드를 지정하지 않은 여러 제품의 구매 선택 질문이라면 서로 다른 제조사의 '
              '관련 모델 사양을 찾아 같은 구성·측정 조건으로 비교 가능한지 확인하세요. '
              '자료 개수나 제조사 수만으로 질문 전체를 지원한다고 판단하지 마세요.')


def source_publisher(source):
    """Group known manufacturer subdomains; URL diversity alone is not evidence."""
    host = (urlsplit(source['url']).hostname or '').lower().removeprefix('www.')
    if host == 'lge.co.kr' or host.endswith('.lge.co.kr'):
        return 'lg.com'
    for domain in ('samsung.com', 'lg.com', 'apple.com', 'roborock.com', 'dreametech.com'):
        if host == domain or host.endswith('.' + domain):
            return domain
    return host


def diverse_sources(sources, limit=3):
    """Give each fetched publisher one slot before using its other pages."""
    groups = {}
    for source in sources:
        groups.setdefault(source_publisher(source), []).append(source)
    ordered = [rows[index] for index in range(max(map(len, groups.values()), default=0))
               for rows in groups.values() if index < len(rows)]
    return ordered[:limit]
