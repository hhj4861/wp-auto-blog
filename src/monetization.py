"""수익화 레이어 + 발행 전 품질 게이트 (general/trendpulse 전용).

인아티클 광고 유닛, 공식 사이트 CTA 버튼, 관련 글 내부 링크 박스를
생성된 HTML에 삽입하고, 발행 전 기계 검출 가능한 결함을 점검한다.

AdSense 정책 안전 원칙 (변경 금지):
  - 광고와 CTA 버튼은 섹션 단위로 이격한다 (무효클릭 유도 금지)
  - 광고 상단에 '광고' 라벨을 명시한다
  - CTA는 정부·공공기관 등 신뢰 도메인 공식 사이트로만 연결한다
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from urllib.parse import quote, urlparse

from loguru import logger

DEFAULT_AD_CLIENT = "ca-pub-7509086152335830"
DEFAULT_AD_SLOTS = ("3599000043", "7637749188")

# CTA 버튼을 허용하는 도메인 (LLM이 제안한 공식 링크의 환각/오남용 방지)
TRUSTED_CTA_SUFFIXES = (".go.kr", ".or.kr")
TRUSTED_CTA_HOSTS = {
    "korea.kr", "www.korea.kr", "gov.kr", "www.gov.kr",
    # 공기업/공공서비스 (.co.kr이지만 공식)
    "en-ter.co.kr", "www.kepco.co.kr", "home.kepco.co.kr",  # 한전 에너지캐시백
    "www.letskorail.com", "etk.srail.kr",  # 코레일/SR 승차권
    "www.krx.co.kr", "krx.co.kr",  # 한국거래소 (투자 제도 정보)
}

_H2_RE = re.compile(r"<h2[\s>]")
_HANGUL_RE = re.compile(r"[가-힣]")


def _ad_client() -> str:
    return os.getenv("ADSENSE_CLIENT", DEFAULT_AD_CLIENT)


def _ad_slots() -> list[str]:
    env = os.getenv("ADSENSE_SLOTS", "")
    if env.strip():
        return [s.strip() for s in env.split(",") if s.strip()]
    return list(DEFAULT_AD_SLOTS)


def _ad_unit(client: str, slot: str) -> str:
    return f'''
<div style="max-width:800px;margin:35px auto;">
<p style="text-align:center;color:#94a3b8;font-size:0.75em;letter-spacing:2px;margin:0 0 4px 0;">광고</p>
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={client}" crossorigin="anonymous"></script>
<ins class="adsbygoogle" style="display:block; text-align:center;" data-ad-layout="in-article" data-ad-format="fluid" data-ad-client="{client}" data-ad-slot="{slot}"></ins>
<script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
</div>
'''


def _cta_button(label: str, url: str, sub: str) -> str:
    return f'''
<div style="max-width:800px;margin:45px auto;text-align:center;">
<a href="{url}" target="_blank" rel="noopener" style="display:inline-block;background:#0066cc;color:#ffffff;font-size:1.15em;font-weight:bold;padding:18px 42px;border-radius:12px;text-decoration:none;box-shadow:0 4px 15px rgba(0,102,204,0.4);">{label}</a>
<p style="color:#94a3b8;font-size:0.8em;margin-top:8px;">{sub}</p>
</div>
'''


def _related_box(posts: list[dict], heading: str = "📌 함께 보면 좋은 글") -> str:
    items = "".join(
        f'<li style="margin-bottom:10px;"><a href="{p["url"]}" '
        f'style="color:#67e8f9;text-decoration:none;">{p["title"]}</a></li>'
        for p in posts)
    return f'''
<div style="max-width:800px;margin:35px auto;padding:20px;background:#2d2d3a;border-radius:12px;border-left:4px solid #5046e5;">
<p style="margin:0 0 12px 0;font-size:1.05em;font-weight:bold;color:#ffffff;">{heading}</p>
<ul style="margin:0;padding-left:18px;color:#e0e0e0;line-height:1.6;">{items}</ul>
</div>
'''


def insert_related_box(
    html: str,
    related_posts: list[dict] | None,
    heading: str = "📌 Related Posts",
) -> str:
    """관련 글 박스만 단독 삽입 (tech/kculture 등 광고 레이어 없는 모드용).

    H2가 2개 이상이면 마지막 H2(결론) 앞에, 아니면 본문 말미에 붙인다.
    """
    if not related_posts:
        return html
    box = _related_box(related_posts, heading)
    h2s = [m.start() for m in _H2_RE.finditer(html)]
    if len(h2s) >= 2:
        pos = h2s[-1]
        html = html[:pos] + box + html[pos:]
    else:
        html = html + box
    logger.info(f"관련 글 내부 링크 박스 삽입: {len(related_posts)}개")
    return html


def parse_official_link(value: str) -> tuple[str, str] | None:
    """'이름|URL' 형식의 공식 링크를 검증한다. 신뢰 도메인이 아니면 None."""
    if not value or "|" not in value or value.strip() in ("없음", "-"):
        return None
    name, _, url = value.partition("|")
    name, url = name.strip(), url.strip()
    if not name or not url.startswith("https://"):
        return None
    host = (urlparse(url).hostname or "").lower()
    if host in TRUSTED_CTA_HOSTS or host.endswith(TRUSTED_CTA_SUFFIXES):
        return name, url
    logger.warning(f"OFFICIAL_LINK 비신뢰 도메인 무시: {url}")
    return None


def insert_monetization(
    html: str,
    official_link: str = "",
    related_posts: list[dict] | None = None,
) -> str:
    """광고 유닛/CTA/관련 글 박스를 H2 앵커 기준으로 삽입한다.

    배치 (H2 4개 이상일 때):
      도입부 직후 광고#1 → [섹션2 끝 CTA] → 섹션3 앞 광고#2 → 결론 앞 관련글 → 말미 CTA
    H2가 적으면 광고#1 + 말미 요소만 배치한다.
    """
    client, slots = _ad_client(), _ad_slots()
    cta = parse_official_link(official_link)
    h2s = [m.start() for m in _H2_RE.finditer(html)]

    inserts: list[tuple[int, str]] = []
    if len(h2s) >= 4:
        inserts.append((h2s[0], _ad_unit(client, slots[0])))
        if cta:
            inserts.append((h2s[2], _cta_button(
                f"🏛️ {cta[0]} 바로가기", cta[1], "공식 사이트로 이동합니다")))
        if len(slots) > 1:
            inserts.append((h2s[3], _ad_unit(client, slots[1])))
        if related_posts:
            inserts.append((h2s[-1], _related_box(related_posts)))
    elif h2s:
        inserts.append((h2s[0], _ad_unit(client, slots[0])))
        if related_posts:
            inserts.append((h2s[-1], _related_box(related_posts)))
    else:
        logger.warning("H2 없음 — 광고 삽입 생략")

    for pos, block in sorted(inserts, key=lambda x: -x[0]):
        html = html[:pos] + block + html[pos:]

    if cta:
        html = html + _cta_button(
            f"✅ {cta[0]}에서 직접 확인하기", cta[1], "공식 사이트에서 최신 정보를 확인하세요")

    logger.info(
        f"수익화 레이어 삽입: 광고 {min(len(slots), 2 if len(h2s) >= 4 else 1)}개, "
        f"CTA {'2개' if cta else '0개 (공식 링크 없음)'}, "
        f"관련글 {len(related_posts or [])}개")
    return html


# 쇼핑 링크 가드레일: 프롬프트가 실제 URL 앵커를 요구해도 LLM이 종종
# '(Shop on Musinsa Global →)' 텍스트 플레이스홀더나 '(Shop on<a ...>' 같은
# 깨진 마크업을 남긴다. 규칙은 프롬프트가 아니라 후처리 코드로 강제한다.
SHOP_SEARCH_URLS = {
    "yesstyle": "https://www.yesstyle.com/en/search?q={q}",
    "musinsa global": "https://global.musinsa.com/us/search?keyword={q}",
    "musinsa": "https://global.musinsa.com/us/search?keyword={q}",
    "amazon": "https://www.amazon.com/s?k={q}",
    "olive young global": "https://global.oliveyoung.com/search?query={q}",
    "olive young": "https://global.oliveyoung.com/search?query={q}",
}


# 카테고리별 기본 쇼핑몰 (플레이스홀더에 몰 이름이 없을 때)
DEFAULT_SHOP_RETAILER = {"K-Fashion": "yesstyle", "K-Beauty": "yesstyle"}

# 제휴 링크 플러밍: 소매몰별 제휴 파라미터를 env로 받아 URL에 부착한다.
# 프로그램마다 파라미터 형식이 달라(예: Amazon 'tag=id-20', 각 네트워크 'ref=…'),
# 형식을 하드코딩하지 않고 프로그램이 발급한 쿼리 조각을 env에 그대로 넣게 한다.
#   AFFILIATE_AMAZON=tag=bytepulse-20
#   AFFILIATE_YESSTYLE=ref=xxxxx   (승인 후 발급값)
# env가 비어 있으면 순수 검색 링크로 무해하게 동작한다.
_AFFILIATE_RETAILERS = ("amazon", "yesstyle", "musinsa", "olive young")


def _affiliate_env_key(retailer: str) -> str:
    return "AFFILIATE_" + retailer.strip().upper().replace(" ", "_")


def affiliate_active() -> bool:
    """제휴 파라미터가 하나라도 설정돼 있으면 True (FTC 고지·태그 주입 게이트)."""
    return any(
        os.getenv(_affiliate_env_key(r), "").strip() for r in _AFFILIATE_RETAILERS
    )


def apply_affiliate(url: str, retailer: str) -> str:
    """소매몰별 제휴 파라미터(env)를 URL에 덧붙인다. env 없으면 원본 그대로."""
    frag = os.getenv(_affiliate_env_key(retailer), "").strip().lstrip("?&")
    if not frag:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{frag}"


def _detect_retailer(text: str) -> str | None:
    lowered = text.lower()
    for key in ("olive young", "yesstyle", "musinsa", "amazon"):
        if key in lowered:
            return key
    return None


def fix_shop_links(html: str, search_term: str, default_retailer: str = "amazon") -> str:
    """쇼핑 링크 플레이스홀더를 실제 검색 링크로 치환/수리한다.

    - '(Shop on<a ...>' 처럼 앵커 앞에 붙은 잔여 접두 텍스트 제거
    - 'on<a' 처럼 앵커에 눌어붙은 단어에 공백 삽입
    - href 없는 '(Shop ... →)' 플레이스홀더는: 문구에 알려진 몰이 있으면 그 몰로,
      '(Shop Similar →)' 처럼 몰 언급이 없으면 default_retailer로 링크.
      특정 몰을 지목했는데 미확인 몰이면 제거.
    """
    q = quote(search_term.strip()) if search_term and search_term.strip() else ""

    html = re.sub(r"\(?Shop on\s*(?=<a\s)", "", html)
    html = re.sub(r"\bon(<a\s)", r"on \1", html)

    def _replace(match: re.Match) -> str:
        inner = match.group(1).strip()
        # 이모지/기호 접두(🛒, 🛍️ 등)를 걷어낸 뒤 동사 여부 판단
        stripped = re.sub(r"^[^A-Za-z]+", "", inner)
        retailer = _detect_retailer(inner)
        is_shop_verb = bool(
            re.match(r"(?:Shop|Buy|Order|Get|Find|Browse)(?=[A-Z\s]|$)", stripped, re.IGNORECASE)
        )
        if retailer is None and not is_shop_verb:
            return match.group(0)  # 쇼핑 문구가 아니면 건드리지 않는다
        if retailer is None:
            named_mall = re.match(
                r"(?:Shop|Buy|Order|Get|Find|Browse)\s+on\s+\S", stripped, re.IGNORECASE
            )
            if named_mall:
                logger.warning(f"쇼핑 플레이스홀더 제거 (미확인 몰): {inner}")
                return ""
            retailer = default_retailer
        url_template = SHOP_SEARCH_URLS.get(retailer)
        if not url_template or not q:
            return ""
        url = apply_affiliate(url_template.format(q=q), retailer)
        return (
            f'<a href="{url}" target="_blank" rel="nofollow sponsored" '
            f'style="color:#9b59b6;">{inner} →</a>'
        )

    fixed = re.sub(r"\(([^()<>]{1,80}?)\s*→\s*\)", _replace, html)
    if fixed != html:
        logger.info("쇼핑 링크 플레이스홀더 수리됨")
    return fixed


def strip_dead_ctas(html: str) -> str:
    """앵커 밖에 남은 '(... →)' 죽은 CTA를 제거한다 (fix_shop_links 이후 잔여분).

    링크 없는 CTA 텍스트는 독자에게 깨진 UI로 보인다 — 살리지 못하면 지운다.
    앵커 안에 있는 것과 화살표 없는 일반 괄호는 건드리지 않는다.
    """
    # 앵커 내부는 보호: <a...>...</a> 구간을 치외법권으로 분리 후 나머지만 치환
    parts = re.split(r"(<a\s[^>]*>.*?</a>)", html, flags=re.S)
    removed = 0
    for i in range(0, len(parts), 2):  # 짝수 인덱스 = 앵커 밖 텍스트
        cleaned = re.sub(r"\([^()<>]{1,80}?\s*→\s*\)", "", parts[i])
        if cleaned != parts[i]:
            removed += 1
            parts[i] = cleaned
    if removed:
        logger.warning(f"링크 없는 CTA 제거됨 ({removed}개 구간)")
    return "".join(parts)


def fix_markdown_bold(html: str) -> str:
    """본문에 잔존한 마크다운 **볼드**를 <strong>으로 변환한다."""
    fixed = re.sub(r"\*\*([^*\n]{1,80}?)\*\*", r"<strong>\1</strong>", html)
    if fixed != html:
        logger.info("본문 ** 마크다운 볼드 변환됨")
    return fixed


def unwrap_dead_anchors(html: str) -> str:
    """href=\"#\" 죽은 앵커를 텍스트만 남기고 벗긴다 (#섹션 앵커는 유지)."""
    return re.sub(r'<a\s[^>]*href="#"[^>]*>(.*?)</a>', r"\1", html, flags=re.S)


def fix_category_links(html: str, allowed_urls: list[str], target_url: str) -> str:
    """본문의 /category/ 링크 중 글 자신의 카테고리 계보가 아닌 것을 교정한다.

    LLM이 프롬프트 예시(테크 카테고리 경로)를 그대로 베껴 K-Food 글이
    /category/saas-reviews/ 로 링크되는 오류를 코드로 강제 수리한다.
    """
    allowed_paths = {urlparse(u).path.rstrip("/") for u in allowed_urls}

    def _sub(match: re.Match) -> str:
        href = match.group(2)
        if urlparse(href).path.rstrip("/") in allowed_paths:
            return match.group(0)
        return f"{match.group(1)}{target_url}{match.group(3)}"

    fixed = re.sub(r'(href=")([^"]*/category/[^"]*)(")', _sub, html)
    if fixed != html:
        logger.info("잘못된 카테고리 내부 링크 교정됨")
    return fixed


# ---------------------------------------------------------------- 품질 게이트

_PLACEHOLDER_RE = re.compile(r"\(\([^()\n]{2,60}\)\)")


# 정책·제도형 카테고리 — 고지 문구를 프롬프트에 맡기지 않고 코드로 강제 삽입한다
POLICY_CATEGORIES = ("생활정보", "취업", "건강")
_INVEST_TOPIC_RE = re.compile(
    r"주식|투자|공모주|펀드|배당|양도소득세|양도세|ISA|연금|증권|금투세|대주주|거래세")
# '바우처·보험·암'은 에너지바우처·화재보험 등 비의료 주제에 오탐하므로 제외한다
_MEDICAL_TOPIC_RE = re.compile(
    r"검진|예방접종|백신|의료비|치매|질환|진료|병원|처방|임플란트|보청기|건강보험")


def add_policy_disclaimers(html: str, category: str = "", topic: str = "") -> str:
    """정책형 글에 기준일 안내(상단)와 투자/의료 고지(하단)를 결정적으로 삽입한다.

    LLM 프롬프트 규칙은 방어선이 아니다 — 고지는 항상 코드가 붙인다.
    """
    if category not in POLICY_CATEGORIES:
        return html
    if 'id="policy-notice"' in html:
        return html

    today = datetime.now().strftime("%Y년 %m월")
    notice = (
        f'<p id="policy-notice" style="max-width:800px;margin:10px auto;color:#94a3b8;'
        f'font-size:0.85em;">※ 이 글은 {today} 공식 발표 자료를 기준으로 작성되었습니다. '
        f'제도와 수치는 변경될 수 있으니 신청·결정 전 공식 사이트에서 최종 확인하세요.</p>')
    html = notice + "\n" + html

    tails = []
    if _INVEST_TOPIC_RE.search(topic):
        tails.append("본 글은 제도·세금 정보 안내이며 특정 상품이나 종목에 대한 투자 권유가 "
                     "아닙니다. 투자 판단과 그에 따른 책임은 본인에게 있습니다.")
    if category == "건강" or _MEDICAL_TOPIC_RE.search(topic):
        tails.append("본 글은 지원 제도 안내이며 의학적 진단·치료에 대한 조언이 아닙니다. "
                     "구체적인 사항은 관할 기관 또는 의료기관에서 확인하세요.")
    if tails:
        joined = "<br/>".join(tails)
        html += (f'\n<p id="policy-disclaimer" style="max-width:800px;margin:25px auto;'
                 f'color:#94a3b8;font-size:0.85em;border-top:1px solid #3d3d4a;'
                 f'padding-top:12px;">{joined}</p>')
    logger.info(f"정책 고지 삽입: 기준일 안내 + 하단 고지 {len(tails)}건")
    return html


def strip_placeholders(html: str) -> str:
    """((Sleep 2024)) 류의 인용 플레이스홀더를 기계적으로 제거한다 (게이트 전 자가치유)."""
    cleaned = _PLACEHOLDER_RE.sub("", html)
    if cleaned != html:
        cleaned = re.sub(r"(?<=[가-힣\w.,]) {2,}(?=[가-힣\w])", " ", cleaned)
        logger.info("본문 ((...)) 플레이스홀더 자동 제거됨")
    return cleaned


# FAQ 마크업은 세 변형이 있다:
#  (A) <p><strong>Q1. 질문?</strong>답변</p>
#  (B) <p><strong>Q1. 질문?</strong></p> ... <p>답변</p>
#  (C) <p style="...bold...">Q1. 질문?</p> ... <p>답변</p>  (strong 없이 인라인 볼드)
# 질문 위치를 기준으로 그 뒤 텍스트를 답변으로 잡아 세 변형을 함께 처리한다.
_FAQ_QUESTION_RE = re.compile(
    r"<strong[^>]*>\s*(?:Q\d+[.:]?\s*)?([^<]{5,180}\?)\s*</strong>"
    r"|<p[^>]*font-weight:\s*bold[^>]*>\s*(?:Q\d+[.:]?\s*)?([^<]{5,180}\?)\s*</p>")
_FAQ_SECTION_RE = re.compile(r"(자주\s*묻는|FAQ|자주하는\s*질문)", re.IGNORECASE)


def _clean_text(html_fragment: str) -> str:
    """HTML 조각에서 태그 제거 + HTML 엔티티 정규화."""
    import html as _html
    text = re.sub(r"<[^>]+>", " ", html_fragment)
    text = _html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def build_faq_schema(html: str) -> str:
    """본문의 FAQ 섹션에서 FAQPage JSON-LD를 생성해 반환한다.

    질문이 2개 미만이거나 FAQ 섹션이 없으면 빈 문자열(스팸 신호 방지).
    프롬프트에 맡기지 않고 코드가 결정적으로 생성한다.
    """
    if 'application/ld+json' in html and 'FAQPage' in html:
        return ""  # 이미 있음
    m = _FAQ_SECTION_RE.search(html)
    if not m:
        return ""
    section = html[m.start():]

    qa_pairs = []
    seen = set()
    # 질문 <strong> 위치를 기준으로, 그 뒤 텍스트를 답변으로 잡는다.
    # (A)와 (B) 변형을 함께 처리 — 질문 태그 다음 등장하는 첫 유의미한 텍스트가 답변.
    matches = list(_FAQ_QUESTION_RE.finditer(section))
    for idx, qm in enumerate(matches):
        # group(1)=strong 변형, group(2)=인라인 볼드 p 변형
        question = _clean_text(qm.group(1) or qm.group(2) or "")
        if len(question) < 6 or question in seen:
            continue
        # 답변 범위: 이 질문 끝 ~ 다음 질문 시작. 마지막 질문은 다음 구조 경계
        # (다음 섹션 H2·박스·CTA)에서 끊어 다른 섹션이 답변에 흘러들지 않게 한다.
        start = qm.end()
        if idx + 1 < len(matches):
            end = matches[idx + 1].start()
        else:
            # 마지막 질문: 다음 구조 경계에서 끊는다. 관련글 박스·결론·CTA·참고자료가
            # 답변에 섞이지 않도록 폭넓게 매칭.
            rest = section[start:]
            boundary = re.search(
                r"<h2|📚|📌|📋|🚀|📝|✅\s*Step|함께\s*보면|참고\s*자료|더\s*많은|"
                r"인사이트\s*카테고리|<div[^>]*background:#5046e5", rest)
            end = start + (boundary.start() if boundary else min(len(rest), 600))
        answer = _clean_text(section[start:end])
        # 답변 앞에 붙은 태그 잔여(</p> 등) 제거하고 실제 문장만
        answer = answer.lstrip("> ").strip()
        if len(answer) >= 10:
            qa_pairs.append((question, answer[:500]))
            seen.add(question)
    if len(qa_pairs) < 2:
        return ""

    import json
    schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in qa_pairs
        ],
    }
    logger.info(f"FAQPage 스키마 생성: 질문 {len(qa_pairs)}개")
    return ('<script type="application/ld+json">'
            + json.dumps(schema, ensure_ascii=False) + '</script>')


def insert_faq_schema(html: str) -> str:
    """FAQPage 스키마를 본문 말미에 삽입한다 (없으면 원본 그대로)."""
    schema = build_faq_schema(html)
    return f"{html}\n{schema}" if schema else html
_TITLE_ARTIFACT_RE = re.compile(r"[`\"]|\*\*|\(\s*(?:유형|\d+\s*자)")
# 종목 추천성 문구 — 유사투자자문·YMYL 리스크, 코드로 차단
_STOCK_ADVICE_RE = re.compile(
    r"매수\s*추천|매도\s*추천|추천\s*종목|목표\s*주가|급등\s*예[상정]|"
    r"지금\s*(사야|매수하)|무조건\s*(사세요|매수)")
# 광고 클릭 유도 문구 — 애드센스 무효클릭 정책 위반 (영구 정지 사유)
_INVALID_CLICK_RE = re.compile(r"광고[를을]?\s*(클릭|눌러)|배너[를을]?\s*(클릭|눌러)")


def check_quality(
    title: str,
    html: str,
    focus_keyphrase: str = "",
    meta_description: str = "",
    require_korean: bool = True,
) -> list[str]:
    """발행 전 기계 검출 가능한 결함 목록을 반환한다. 비어 있으면 통과."""
    issues: list[str] = []

    if _TITLE_ARTIFACT_RE.search(title):
        issues.append(f"제목에 메타 잔존물(백틱/따옴표/(N자)/(유형)): {title[:50]!r}")
    if require_korean and not _HANGUL_RE.search(title):
        issues.append(f"한국어 모드인데 제목에 한글 없음: {title[:50]!r}")
    if len(title.strip()) < 8:
        issues.append(f"제목이 너무 짧음({len(title.strip())}자)")

    if _PLACEHOLDER_RE.search(html):
        issues.append("본문에 ((...)) 인용 플레이스홀더 잔존")
    if "---SEO-META---" in html or "FOCUS_KEYPHRASE:" in html:
        issues.append("본문에 SEO-META 블록 잔존")
    if "```" in html or re.search(r"^##\s", html, re.M):
        issues.append("본문에 마크다운 잔존")

    text = re.sub(r"<[^>]+>", " ", html)
    if len(text.strip()) < 1000:
        issues.append(f"본문이 너무 짧음({len(text.strip())}자)")
    if _STOCK_ADVICE_RE.search(text):
        issues.append("종목 추천성 문구 검출 — 투자 권유 금지 (수동 검토 필요)")
    if _INVALID_CLICK_RE.search(text):
        issues.append("광고 클릭 유도 문구 검출 — 애드센스 무효클릭 정책 위반")

    if not focus_keyphrase.strip():
        issues.append("포커스 키프레이즈 비어 있음")
    if len(meta_description.strip()) < 50:
        issues.append(f"메타 설명이 너무 짧음({len(meta_description.strip())}자)")

    return issues
