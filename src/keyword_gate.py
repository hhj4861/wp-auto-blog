"""키워드 수요·경쟁 게이트 — 발행 전에 '이길 수 있는 키워드인가'를 판정한다.

두 신호를 결합한다:
  1. 수요: 네이버 검색광고 API(/keywordstool)의 월간 검색수 + 경쟁정도
  2. 경쟁: 구글 SERP 1페이지의 정부·대형매체 점유율(gov_ratio)

판정:
  - 검색량 미달              → skip (쓸 이유 없음)
  - 검색량 충분 + 경쟁 낮음  → go (그대로 생성)
  - 검색량 충분 + 경쟁 높음  → longtail (헤드 대신 롱테일 파생어로 대체)

가드레일은 프롬프트가 아니라 코드로 — 판정 결과는 파이프라인이 강제 적용한다.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
import urllib.parse
import urllib.request

try:
    from loguru import logger
except ImportError:  # 스탠드얼론 스크립트에서도 동작하도록
    import logging

    logger = logging.getLogger(__name__)

API_BASE = "https://api.searchad.naver.com"
KEYWORDSTOOL_URI = "/keywordstool"

# 판정 임계값
MIN_MONTHLY_SEARCH = 500      # 이 미만이면 쓸 가치 없음
HEAD_SEARCH_VOLUME = 50_000   # 이 이상은 헤드텀 — 경쟁 검사 필수
MAX_GOV_RATIO = 0.4           # SERP 1페이지 정부·대형매체 비중 상한

# SERP에서 '우리가 못 이기는' 도메인 (정부·공공·대형 언론/금융)
DOMINANT_DOMAIN_RE = re.compile(
    r"\.go\.kr|\.or\.kr|\.gov|korea\.kr|nts\.go\.kr|hometax|wetax|"
    r"naver\.com|namu\.wiki|wikipedia\.org|"
    r"toss\.im|kbstar|shinhan|wooribank|hanabank|nonghyup|"
    r"chosun\.com|joongang\.co\.kr|donga\.com|hankyung\.com|mk\.co\.kr|"
    r"yna\.co\.kr|sbs\.co\.kr|kbs\.co\.kr|mbc\.co\.kr|brunch\.co\.kr",
    re.IGNORECASE)


def _credentials() -> tuple[str, str, str] | None:
    cid = os.getenv("NAVER_AD_CUSTOMER_ID", "").strip()
    api_key = os.getenv("NAVER_AD_API_KEY", "").strip()
    secret = os.getenv("NAVER_AD_SECRET_KEY", "").strip()
    if not (cid and api_key and secret):
        return None
    return cid, api_key, secret


def _signed_headers(method: str, uri: str, cid: str, api_key: str, secret: str) -> dict:
    ts = str(round(time.time() * 1000))
    sig = base64.b64encode(
        hmac.new(secret.encode(), f"{ts}.{method}.{uri}".encode(), hashlib.sha256).digest()
    ).decode()
    return {"X-Timestamp": ts, "X-API-KEY": api_key, "X-Customer": cid, "X-Signature": sig}


def _to_int(value) -> int:
    """'< 10' 같은 문자열 응답을 정수로 정규화."""
    if isinstance(value, int):
        return value
    s = str(value).strip()
    return 0 if s.startswith("<") else int(re.sub(r"[^0-9]", "", s) or 0)


def fetch_keyword_stats(hint: str, attempt: int = 0) -> list[dict]:
    """연관 키워드와 월간 검색수를 조회한다. 실패 시 빈 리스트(게이트 통과)."""
    creds = _credentials()
    if not creds:
        logger.debug("네이버 검색광고 API 자격증명 없음 — 키워드 게이트 건너뜀")
        return []
    cid, api_key, secret = creds
    # API는 공백을 허용하지 않는다
    hint = re.sub(r"\s+", "", hint)[:40]
    url = f"{API_BASE}{KEYWORDSTOOL_URI}?" + urllib.parse.urlencode(
        {"hintKeywords": hint, "showDetail": "1"})
    req = urllib.request.Request(
        url, headers=_signed_headers("GET", KEYWORDSTOOL_URI, cid, api_key, secret))
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except Exception as e:  # noqa: BLE001 — 조회 실패가 발행을 막아선 안 된다
        if attempt < 2:
            time.sleep(2 * (attempt + 1))
            return fetch_keyword_stats(hint, attempt + 1)
        logger.warning(f"키워드 조회 실패({hint}): {type(e).__name__} {e}")
        return []

    out = []
    for k in payload.get("keywordList", []):
        pc = _to_int(k.get("monthlyPcQcCnt", 0))
        mo = _to_int(k.get("monthlyMobileQcCnt", 0))
        out.append({
            "keyword": k.get("relKeyword", ""),
            "monthly": pc + mo,
            "comp": k.get("compIdx", ""),
            "ad_depth": k.get("plAvgDepth", 0),
        })
    out.sort(key=lambda x: x["monthly"], reverse=True)
    return out


def _no_ad_data(stats: list[dict]) -> bool:
    """검색광고 API에 데이터가 없는 '광고 제한 키워드'인지 판정.

    기초연금·보조금24·재난적의료비처럼 광고 집행이 제한된 정부 복지 키워드는
    실제 검색 수요가 커도 API가 '< 10 / 연관 0건'으로 응답한다. 이걸 저수요로
    오판하면 우리 핵심 카테고리가 통째로 걸러진다.
    """
    return len(stats) <= 1 and all(s["monthly"] == 0 and not s.get("ad_depth")
                                   for s in stats)


def fetch_serp_domains(query: str) -> list[str]:
    """검색 1페이지 결과 도메인 목록. 실패 시 빈 리스트.

    구글·빙은 서버 스크래핑을 차단하므로 DuckDuckGo HTML 엔드포인트를 쓴다.
    엔진이 달라 순위는 정확히 일치하지 않지만, '이 쿼리를 정부·대형매체가
    장악했는가'라는 판정에는 충분한 프록시다.
    """
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(
        {"q": query, "kl": "kr-kr"})
    # 연속 호출은 레이트리밋으로 빈 결과를 받는다 — 간격을 두고 재시도
    for attempt in range(3):
        if attempt:
            time.sleep(3 * attempt)
        req = urllib.request.Request(url, headers={
            "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/120.0.0.0 Safari/537.36"),
            "Accept-Language": "ko-KR,ko;q=0.9",
        })
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:  # noqa: BLE001
            logger.debug(f"SERP 조회 실패({query}): {type(e).__name__}")
            continue

        domains = []
        for m in re.finditer(r'uddg=([^&"\']+)', html):
            target = urllib.parse.unquote(m.group(1))
            host = urllib.parse.urlparse(target).hostname
            if not host:
                continue
            host = host.lower()
            if host not in domains and "duckduckgo" not in host:
                domains.append(host)
        if domains:
            return domains[:10]
    logger.debug(f"SERP 결과 없음({query}) — 레이트리밋 가능성")
    return []


def gov_ratio(domains: list[str]) -> float | None:
    """SERP 1페이지에서 '못 이기는 도메인' 비중. 조회 실패 시 None(=미확인)."""
    if not domains:
        return None
    hits = sum(1 for d in domains if DOMINANT_DOMAIN_RE.search(d))
    return hits / len(domains)


def evaluate(topic: str, keywords: list[str] | None = None,
             check_serp: bool = True) -> dict:
    """토픽의 수요·경쟁을 평가해 판정을 돌려준다.

    Returns:
        {verdict: go|longtail|skip|unknown, monthly, comp, gov_ratio,
         head_keyword, longtails: [...], reason}
    """
    norm = lambda s: re.sub(r"\s+", "", s).lower()  # noqa: E731
    kws = [k for k in (keywords or []) if k.strip()]

    # 시드 후보: 앞 두 키워드를 합친 구체어를 먼저 시도한다.
    # 큐의 첫 키워드가 '추석'처럼 포괄적이면 파생어가 주제를 이탈하기 때문.
    candidates = []
    if len(kws) >= 2:
        candidates.append(kws[0] + kws[1])
    candidates.append(kws[0] if kws else topic)

    stats, seed, head = [], candidates[-1], None
    for cand in candidates:
        rows = fetch_keyword_stats(cand)
        if not rows:
            continue
        exact = next((r for r in rows if norm(r["keyword"]) == norm(cand)), None)
        if exact and exact["monthly"] >= MIN_MONTHLY_SEARCH:
            stats, seed, head = rows, cand, exact
            break
        # 폴백은 '더 풍부한 응답'을 우선한다. 합성 시드('중장년재취업신중년')는
        # 빈 응답 1건을 주는데 이걸 붙들면 뒤 후보의 좋은 데이터를 버리게 된다.
        if len(rows) > len(stats):
            stats, seed = rows, cand
    if not stats:
        return {"verdict": "unknown", "monthly": 0, "comp": "", "gov_ratio": None,
                "head_keyword": seed, "longtails": [],
                "reason": "검색량 조회 불가 — 게이트 통과(기본 허용)"}

    if head is None:
        # 정확 일치가 없으면 시드를 포함하는 것 중 최대 검색량
        # (stats[0]을 그대로 쓰면 무관한 초대형 키워드가 잡힌다)
        seed_n = norm(seed)
        head = next((s for s in stats if norm(s["keyword"]) == seed_n),
                    next((s for s in stats if seed_n in norm(s["keyword"])), stats[0]))
    monthly = head["monthly"]
    head_n = norm(head["keyword"])

    if monthly < MIN_MONTHLY_SEARCH:
        # 광고 제한 키워드는 데이터 부재이지 저수요가 아니다 → 통과시킨다
        if _no_ad_data(stats):
            return {"verdict": "unknown", "monthly": 0, "comp": head["comp"],
                    "gov_ratio": None, "head_keyword": head["keyword"], "longtails": [],
                    "reason": ("광고 제한 키워드로 추정(검색광고 API 데이터 없음) — "
                               "수요 판정 불가, 게이트 통과")}
        # 시드는 약해도 같은 주제의 연관 키워드가 살아 있으면 그쪽을 헤드로 승격.
        # 판정 기준은 합성 시드가 아니라 핵심 명사(큐의 첫 키워드) 포함 여부 —
        # '통신비미환급금'(220) 대신 '통신비환급금조회'(3,450)를 잡기 위함.
        anchor = norm(kws[0]) if kws else head_n
        alt = next((s for s in stats
                    if s["monthly"] >= MIN_MONTHLY_SEARCH and anchor in norm(s["keyword"])),
                   None)
        if alt:
            return {"verdict": "go", "monthly": alt["monthly"], "comp": alt["comp"],
                    "gov_ratio": None, "head_keyword": alt["keyword"],
                    "longtails": [],
                    "reason": (f"시드 '{head['keyword']}'는 월 {monthly:,}회로 약하나 "
                               f"연관어 '{alt['keyword']}' 월 {alt['monthly']:,}회 — "
                               f"이 키워드로 공략")}
        return {"verdict": "skip", "monthly": monthly, "comp": head["comp"],
                "gov_ratio": None, "head_keyword": head["keyword"], "longtails": [],
                "reason": f"월 검색량 {monthly:,}회 < 기준 {MIN_MONTHLY_SEARCH:,}회"}

    # 롱테일 후보: 헤드 키워드를 그대로 포함하면서(= 같은 주제) 검색량이 작은 파생어.
    # 시드가 아니라 헤드 기준으로 걸러야 '추석' → '추석선물세트' 같은 이탈을 막는다.
    longtails = [
        s for s in stats
        if norm(s["keyword"]) != head_n
        and MIN_MONTHLY_SEARCH <= s["monthly"] < min(monthly, HEAD_SEARCH_VOLUME)
        and head_n in norm(s["keyword"])
    ][:5]

    ratio = None
    if check_serp and monthly >= HEAD_SEARCH_VOLUME:
        ratio = gov_ratio(fetch_serp_domains(head["keyword"]))
        # 미확인(레이트리밋)일 때도 헤드텀은 보수적으로 롱테일 우회 —
        # 월 5만회 이상 키워드의 1페이지가 비어 있을 가능성은 사실상 없다
        if ratio is None or ratio > MAX_GOV_RATIO:
            shown = "확인 불가" if ratio is None else f"{ratio:.0%}"
            return {"verdict": "longtail", "monthly": monthly, "comp": head["comp"],
                    "gov_ratio": ratio, "head_keyword": head["keyword"],
                    "longtails": longtails,
                    "reason": (f"월 {monthly:,}회 헤드텀, SERP 정부·대형매체 점유 "
                               f"{shown} — 롱테일로 우회 권장")}

    shown = "미검사" if ratio is None else f"{ratio:.0%}"
    return {"verdict": "go", "monthly": monthly, "comp": head["comp"],
            "gov_ratio": ratio, "head_keyword": head["keyword"],
            "longtails": longtails,
            "reason": f"월 {monthly:,}회, 경쟁 {head['comp']}, SERP 점유 {shown}"}
