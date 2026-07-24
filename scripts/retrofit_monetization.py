#!/usr/bin/env python3
"""GSC에서 트래픽 나는 글을 찾아, 광고 유닛이 없는 것에 수익화 레이어를 소급 적용한다.

배경: 82% 트래픽을 내는 에미레이트/JAL 등 레거시 글이 광고 파이프라인 이전에
발행돼 광고 유닛이 0개. 트래픽은 있는데 수익이 0. 이걸 즉시 수익화한다.

적용: 광고 인아티클 2슬롯 + 관련 글 박스(같은 취업/외항사 글) + FAQPage 스키마.
      공식기관 CTA는 외항사엔 해당 도메인이 없어 생략(official_link 없이 호출).
      본문·구조는 건드리지 않고 삽입만 한다.

GSC 노출 MIN_IMPR(기본 3) 이상 + 광고 유닛 없는 글만 대상. DRY_RUN=true면 보고만.
"""

import datetime as dt
import os
import re
import sys
import urllib.parse

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.gsc_client import query  # noqa: E402
from src.monetization import (  # noqa: E402
    insert_monetization, insert_faq_schema, strip_placeholders,
)

BASE_URL = (os.environ.get("WP_GENERAL_URL") or "").rstrip("/")
API = f"{BASE_URL}/wp-json/wp/v2"
DRY_RUN = (os.environ.get("DRY_RUN", "true").lower() != "false")
MIN_IMPR = int(os.environ.get("MIN_IMPR", "3"))
DAYS = int(os.environ.get("GSC_DAYS", "90"))

from requests.adapters import HTTPAdapter  # noqa: E402
from urllib3.util.retry import Retry  # noqa: E402

session = requests.Session()
session.auth = (os.environ.get("WP_GENERAL_USERNAME", ""),
                os.environ.get("WP_GENERAL_APP_PASSWORD", ""))
session.headers.update({"User-Agent": "Mozilla/5.0 (trendpulse-retrofit)"})
# 러너 IP 일시 차단(Network unreachable)·WAF 대응: 연결 실패 재시도
_retry = Retry(total=5, connect=5, backoff_factor=2,
               status_forcelist=(403, 429, 500, 502, 503, 504),
               allowed_methods=frozenset(["GET", "POST"]))
session.mount("https://", HTTPAdapter(max_retries=_retry))


def slug_from_url(url: str) -> str:
    path = urllib.parse.urlparse(url).path.rstrip("/")
    return urllib.parse.unquote(path.split("/")[-1]) if path else ""


def get_post_by_slug(slug: str) -> dict | None:
    for s in (slug, urllib.parse.quote(slug)):
        r = session.get(f"{API}/posts", params={
            "slug": s, "status": "publish", "context": "edit",
            "_fields": "id,slug,title,content,categories"}, timeout=40)
        if r.status_code == 200 and r.json():
            return r.json()[0]
    return None


def related_airline_posts(exclude_id: int, category_ids: list[int], n: int = 3) -> list[dict]:
    """같은 카테고리(취업 등)의 다른 발행글을 관련 글로."""
    if not category_ids:
        return []
    r = session.get(f"{API}/posts", params={
        "categories": ",".join(map(str, category_ids)), "status": "publish",
        "per_page": n + 3, "orderby": "date", "order": "desc",
        "_fields": "id,link,title"}, timeout=40)
    if r.status_code != 200:
        return []
    out = []
    for p in r.json():
        if p["id"] == exclude_id:
            continue
        out.append({"title": re.sub(r"<[^>]+>", "", p["title"]["rendered"]), "url": p["link"]})
        if len(out) >= n:
            break
    return out


def main():
    if not BASE_URL:
        raise SystemExit("WP_GENERAL_URL 필요")
    end = dt.date.today()
    start = end - dt.timedelta(days=DAYS)
    print(f"대상: {BASE_URL} | DRY_RUN={DRY_RUN} | GSC {DAYS}일 노출 {MIN_IMPR}+ 글\n{'=' * 62}")

    pages = [p for p in query(start.isoformat(), end.isoformat(), ["page"])
             if p["impressions"] >= MIN_IMPR]
    pages.sort(key=lambda p: -p["impressions"])
    print(f"GSC 노출 {MIN_IMPR}+ 페이지 {len(pages)}개\n")

    done, skipped = 0, 0
    for pg in pages:
        slug = slug_from_url(pg["page"])
        if not slug or slug == "trendpulse.blog":
            continue
        post = get_post_by_slug(slug)
        if not post:
            print(f"  ? 노출{pg['impressions']:>4} /{slug[:40]}/ — WP 글 못 찾음")
            continue
        html = post["content"].get("raw") or ""
        title = post["title"].get("raw", "")[:40]
        if '<ins class="adsbygoogle"' in html:
            skipped += 1
            continue  # 이미 광고 있음
        # 수익화 레이어 삽입
        new_html = strip_placeholders(html)
        related = related_airline_posts(post["id"], post.get("categories") or [])
        new_html = insert_monetization(new_html, official_link="", related_posts=related)
        new_html = insert_faq_schema(new_html)
        added_ads = new_html.count('<ins class="adsbygoogle"')
        print(f"  ✚ 노출{pg['impressions']:>4} 클릭{pg['clicks']:>3} 순위{pg['position']:>5.1f} "
              f"| 광고 {added_ads} 관련글 {len(related)} FAQ {'O' if 'FAQPage' in new_html else 'X'} "
              f"| {title}")
        if not DRY_RUN:
            ur = session.post(f"{API}/posts/{post['id']}", json={"content": new_html}, timeout=60)
            if ur.status_code == 200:
                done += 1
            else:
                print(f"     ⚠️ 실패 {ur.status_code}: {ur.text[:120]}")

    print(f"\n적용 {done}건 · 이미 광고 있어 건너뜀 {skipped}건")
    if DRY_RUN:
        print("DRY_RUN — 변경 없음. 적용하려면 DRY_RUN=false")


if __name__ == "__main__":
    main()
