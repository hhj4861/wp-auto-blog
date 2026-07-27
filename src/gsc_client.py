"""Google Search Console API 클라이언트 — 페이지·검색어별 노출/클릭/순위 조회.

서비스 계정으로 인증한다. 자격증명은 다음 순서로 로드:
  1. GSC_SA_KEY_B64  — 서비스 계정 JSON을 base64 인코딩한 값 (GitHub Secret용)
  2. GSC_SA_JSON     — 서비스 계정 JSON 원문
  3. GOOGLE_APPLICATION_CREDENTIALS 또는 GSC_SA_JSON_PATH — JSON 파일 경로

필요 권한:
  - GCP 프로젝트에서 'Google Search Console API' 사용 설정
  - 서비스 계정 이메일을 GSC 속성 '사용자 및 권한'에 추가(읽기=제한적으로 충분)
"""

from __future__ import annotations

import base64
import json
import os

import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
# URL 접두어 속성이면 끝에 슬래시 포함
SITE_URL = os.getenv("GSC_SITE_URL", "https://trendpulse.blog/")
API = "https://searchconsole.googleapis.com/webmasters/v3"
# URL Inspection은 v1 엔드포인트(webmasters/v3 아님)
INSPECT_API = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"


def _load_sa_info() -> dict:
    if os.getenv("GSC_SA_KEY_B64", "").strip():
        return json.loads(base64.b64decode(os.environ["GSC_SA_KEY_B64"]).decode())
    if os.getenv("GSC_SA_JSON", "").strip():
        return json.loads(os.environ["GSC_SA_JSON"])
    path = os.getenv("GSC_SA_JSON_PATH") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    raise SystemExit(
        "GSC 자격증명 없음 — GSC_SA_KEY_B64 / GSC_SA_JSON / GSC_SA_JSON_PATH 중 하나 필요")


_CREDS = None


def _access_token() -> str:
    """서비스 계정 토큰. creds 객체를 캐시해 만료 시에만 갱신(호출마다 재발급 방지)."""
    global _CREDS
    if _CREDS is None:
        _CREDS = service_account.Credentials.from_service_account_info(
            _load_sa_info(), scopes=SCOPES)
    if not _CREDS.valid:
        _CREDS.refresh(GoogleAuthRequest())
    return _CREDS.token


def _headers() -> dict:
    return {"Authorization": f"Bearer {_access_token()}",
            "Content-Type": "application/json"}


def query(start_date: str, end_date: str, dimensions: list[str],
          row_limit: int = 25000, filters: list[dict] | None = None) -> list[dict]:
    """Search Analytics 조회. rows(dict 리스트) 반환.

    각 row: {keys: [...], clicks, impressions, ctr, position}
    dimensions 예: ["page"], ["query"], ["page","query"], ["date"]
    """
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "rowLimit": row_limit,
        "dataState": "all",
    }
    if filters:
        body["dimensionFilterGroups"] = [{"filters": filters}]
    url = f"{API}/sites/{requests.utils.quote(SITE_URL, safe='')}/searchAnalytics/query"
    r = requests.post(url, headers=_headers(), json=body, timeout=60)
    if r.status_code != 200:
        raise SystemExit(f"GSC API 오류 {r.status_code}: {r.text[:400]}")
    rows = r.json().get("rows", [])
    out = []
    for row in rows:
        item = {"clicks": row.get("clicks", 0), "impressions": row.get("impressions", 0),
                "ctr": row.get("ctr", 0), "position": row.get("position", 0)}
        for dim, key in zip(dimensions, row.get("keys", [])):
            item[dim] = key
        out.append(item)
    return out


def list_sites() -> list[str]:
    """서비스 계정이 접근 가능한 GSC 속성 목록 (권한 확인용)."""
    r = requests.get(f"{API}/sites", headers=_headers(), timeout=30)
    if r.status_code != 200:
        raise SystemExit(f"GSC sites 오류 {r.status_code}: {r.text[:300]}")
    return [s.get("siteUrl") for s in r.json().get("siteEntry", [])]


def list_sitemaps(site_url: str | None = None) -> list[dict]:
    """제출된 사이트맵 목록·처리 상태 조회 (sitemaps.list).

    각 항목: {path, lastSubmitted, lastDownloaded, isPending, isSitemapsIndex,
             warnings, errors, contents:[{type, submitted, indexed}]}
    비어 있으면 '제출된 사이트맵 없음' = 미발견의 유력 원인.
    """
    site = requests.utils.quote(site_url or SITE_URL, safe="")
    r = requests.get(f"{API}/sites/{site}/sitemaps", headers=_headers(), timeout=30)
    if r.status_code != 200:
        raise SystemExit(f"GSC sitemaps 오류 {r.status_code}: {r.text[:300]}")
    return r.json().get("sitemap", [])


def inspect_url(page_url: str, site_url: str | None = None) -> dict:
    """URL Inspection API — 페이지의 실제 색인 상태 조회.

    반환(주요 키): {
      verdict: PASS|PARTIAL|FAIL|NEUTRAL,
      coverageState: 예 'Submitted and indexed' / 'Crawled - currently not indexed'
                     / 'Discovered - currently not indexed' / 'Excluded by 'noindex' tag',
      robotsTxtState, indexingState, lastCrawlTime, googleCanonical, userCanonical
    }
    실패 시 {error: ...}. 쿼터: 속성당 ~2000/일.
    """
    body = {"inspectionUrl": page_url,
            "siteUrl": site_url or SITE_URL,
            "languageCode": "ko"}
    r = requests.post(INSPECT_API, headers=_headers(), json=body, timeout=60)
    if r.status_code != 200:
        return {"error": f"{r.status_code}: {r.text[:200]}", "verdict": "ERROR"}
    idx = r.json().get("inspectionResult", {}).get("indexStatusResult", {})
    return {
        "verdict": idx.get("verdict", "UNKNOWN"),
        "coverageState": idx.get("coverageState", ""),
        "robotsTxtState": idx.get("robotsTxtState", ""),
        "indexingState": idx.get("indexingState", ""),
        "lastCrawlTime": idx.get("lastCrawlTime", ""),
        "googleCanonical": idx.get("googleCanonical", ""),
        "userCanonical": idx.get("userCanonical", ""),
    }


def fetch_sitemap_urls(site_url: str | None = None, limit: int = 5000) -> list[str]:
    """사이트맵을 재귀 파싱해 모든 페이지 URL 수집.

    WP 코어(/wp-sitemap.xml)와 Yoast(/sitemap_index.xml) 인덱스를 순서대로 시도.
    <sitemap><loc>(하위 인덱스)와 <url><loc>(실제 URL)를 구분해 최종 URL만 반환.
    """
    import re as _re
    import time as _time

    base = (site_url or SITE_URL).rstrip("/")
    seen: set[str] = set()
    out: list[str] = []
    # 기본 python-requests UA는 Hostinger WAF 봇룰에 걸릴 수 있어 브라우저 UA 사용
    ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

    def _get(u: str):
        """WAF/IP 변동 대응 — 3회 재시도."""
        last = None
        for _ in range(3):
            try:
                r = requests.get(u, headers=ua, timeout=30)
                if r.status_code == 200:
                    return r
                last = f"HTTP {r.status_code}"
            except Exception as e:  # noqa: BLE001
                last = str(e)[:120]
            _time.sleep(1.5)
        print(f"[사이트맵 요청 실패] {u} — {last}")
        return None

    def _locs(xml: str) -> list[str]:
        return _re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)

    # 인덱스 후보
    roots = [f"{base}/sitemap_index.xml", f"{base}/wp-sitemap.xml"]
    queue: list[str] = []
    for root in roots:
        r = _get(root)
        if r is not None and "<loc>" in r.text:
            # 인덱스면 하위 사이트맵, 아니면 URL 목록
            if "<sitemapindex" in r.text:
                queue.extend(_locs(r.text))
            else:
                queue.append(root)  # 단일 사이트맵
            break

    for sm in queue:
        if len(out) >= limit:
            break
        r = _get(sm)
        if r is not None:
            for loc in _locs(r.text):
                if loc.endswith(".xml"):  # 중첩 인덱스
                    continue
                if loc not in seen:
                    seen.add(loc)
                    out.append(loc)
                    if len(out) >= limit:
                        break
    return out
