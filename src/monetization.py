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
from urllib.parse import urlparse

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


# ---------------------------------------------------------------- 품질 게이트

_PLACEHOLDER_RE = re.compile(r"\(\([^()\n]{2,60}\)\)")


def strip_placeholders(html: str) -> str:
    """((Sleep 2024)) 류의 인용 플레이스홀더를 기계적으로 제거한다 (게이트 전 자가치유)."""
    cleaned = _PLACEHOLDER_RE.sub("", html)
    if cleaned != html:
        cleaned = re.sub(r"(?<=[가-힣\w.,]) {2,}(?=[가-힣\w])", " ", cleaned)
        logger.info("본문 ((...)) 플레이스홀더 자동 제거됨")
    return cleaned
_TITLE_ARTIFACT_RE = re.compile(r"[`\"]|\(\s*(?:유형|\d+\s*자)")


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

    if not focus_keyphrase.strip():
        issues.append("포커스 키프레이즈 비어 있음")
    if len(meta_description.strip()) < 50:
        issues.append(f"메타 설명이 너무 짧음({len(meta_description.strip())}자)")

    return issues
