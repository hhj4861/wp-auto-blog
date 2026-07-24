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


def _access_token() -> str:
    creds = service_account.Credentials.from_service_account_info(
        _load_sa_info(), scopes=SCOPES)
    creds.refresh(GoogleAuthRequest())
    return creds.token


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
