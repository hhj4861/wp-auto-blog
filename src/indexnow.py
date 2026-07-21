"""IndexNow 핑 — 발행 즉시 참여 검색엔진(Bing·Naver·Yandex 등)에 URL 제출.

trendpulse.blog 전용: 키 파일은 WP 미디어 라이브러리에 업로드되어 있다
(scripts/setup_indexnow.py로 최초 1회 설정).
"""

from __future__ import annotations

import os

import requests
from loguru import logger

INDEXNOW_KEY = os.getenv("INDEXNOW_KEY", "413338ab31bcc9bb0ed71149930283af")
INDEXNOW_KEY_LOCATION = os.getenv(
    "INDEXNOW_KEY_LOCATION",
    "https://trendpulse.blog/wp-content/uploads/2026/07/413338ab31bcc9bb0ed71149930283af.txt",
)
INDEXNOW_API = "https://api.indexnow.org/indexnow"


def ping_urls(urls: list[str], host: str = "trendpulse.blog") -> bool:
    """URL 목록을 IndexNow로 제출한다 (최대 10,000건/호출).

    Returns:
        True if accepted (200/202), False otherwise. 실패해도 발행 흐름을 막지 않는다.
    """
    urls = [u for u in urls if u and host in u]
    if not urls:
        return False
    payload = {
        "host": host,
        "key": INDEXNOW_KEY,
        "keyLocation": INDEXNOW_KEY_LOCATION,
        "urlList": urls[:10000],
    }
    try:
        r = requests.post(INDEXNOW_API, json=payload, timeout=30)
    except requests.RequestException as e:
        logger.warning(f"IndexNow ping 실패: {e}")
        return False
    ok = r.status_code in (200, 202)
    log = logger.info if ok else logger.warning
    log(f"IndexNow ping: {len(payload['urlList'])}건 제출 → HTTP {r.status_code}")
    return ok
