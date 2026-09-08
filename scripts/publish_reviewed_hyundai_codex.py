"""Publish one locally generated and reviewed Codex article; no LLM auth in CI."""
import argparse
from datetime import date
import hashlib
import json
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DIRECTORY = ROOT / "data/editorial/2026-09-08"
SLUG = "hyundai-september-2026-recruitment-eligibility"
TITLE = "2026 현대자동차 9월 신입채용 지원자격·어학성적 체크리스트"
DESCRIPTION = "현대자동차 2026년 9월 신입채용 마감은 9월 14일 17시입니다. 졸업예정자 지원 조건, OPIc·토익스피킹 확인 방법과 직무별 공고 점검표를 공식 자료로 정리했습니다."


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    body = (DIRECTORY / "hyundai-codex-publish.html").read_text(encoding="utf-8")
    review = json.loads((DIRECTORY / "hyundai-codex-review.json").read_text(encoding="utf-8"))
    if review["issues"] or review.get("publish_sha256") != hashlib.sha256(body.encode()).hexdigest():
        raise RuntimeError("Review failed or content changed after review")
    if not 0 <= (date.today() - date.fromisoformat(review["reviewed_on"])).days <= 3:
        raise RuntimeError("Recheck recruitment dates before publishing")
    base = os.environ["WP_GENERAL_URL"].rstrip("/")
    if base != "https://trendpulse.blog":
        raise RuntimeError("Only TrendPulse is authorized")
    session = requests.Session()
    session.auth = (os.environ["WP_GENERAL_USERNAME"], os.environ["WP_GENERAL_APP_PASSWORD"])
    session.headers["User-Agent"] = "Mozilla/5.0 (TrendPulse reviewed editorial publishing)"
    api = base + "/wp-json/wp/v2"

    def get(resource, **params):
        response = session.get(api + resource, params=params, timeout=60)
        response.raise_for_status()
        return response.json()

    def update(resource, payload):
        # Never automatically retry post creation after an ambiguous network error.
        response = session.post(api + resource, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()

    existing = get("/posts", slug=SLUG, context="edit", status="publish,draft,pending,future,private")
    related = get("/posts", search="현대", context="edit", per_page=100, status="publish,draft,pending,future,private")
    for post in related:
        title = post["title"]["raw"]
        print("EXISTING", post["id"], title, flush=True)
        if post["slug"] != SLUG and ("현대자동차" in title or "현대차" in title) and any(term in title for term in ("지원자격", "어학성적", "9월 신입")):
            raise RuntimeError("Overlapping Hyundai article found; review before creating another")
    categories = [c for c in get("/categories", search="취업", per_page=100) if c["name"] == "취업"]
    if len(categories) != 1:
        raise RuntimeError("Expected one existing 취업 category")
    print("REVIEWED", TITLE, "characters", len(body), "category", categories[0]["id"], flush=True)
    if not args.publish:
        print("PREVIEW ONLY; no WordPress changes", flush=True)
        return
    if existing:
        if len(existing) != 1:
            raise RuntimeError("Ambiguous existing slug")
        post = existing[0]
        if post["title"]["raw"] != TITLE or post["content"]["raw"].strip() != body.strip():
            raise RuntimeError("Existing slug has different content; refusing overwrite")
        if post["status"] == "publish":
            print("ALREADY PUBLISHED", post["link"], flush=True)
            return
        if post["status"] != "draft":
            raise RuntimeError("Existing post is not an expected draft")
    else:
        post = update("/posts", {
            "slug": SLUG, "title": TITLE, "content": body, "status": "draft",
            "categories": [categories[0]["id"]], "excerpt": DESCRIPTION,
            "comment_status": "closed", "ping_status": "closed",
            "meta": {"_yoast_wpseo_metadesc": DESCRIPTION,
                     "_yoast_wpseo_focuskw": "현대자동차 9월 신입채용 지원자격",
                     "_yoast_wpseo_title": TITLE + " | TrendPulse"},
        })
        print("DRAFT CREATED", post["id"], flush=True)
    saved = get(f"/posts/{post['id']}", context="edit")
    if saved["slug"] != SLUG or saved["content"]["raw"].strip() != body.strip():
        raise RuntimeError("Saved draft verification failed; not publishing")
    update(f"/posts/{post['id']}", {"status": "publish"})
    saved = get(f"/posts/{post['id']}", context="edit")
    if saved["status"] != "publish" or saved["content"]["raw"].strip() != body.strip():
        raise RuntimeError("Published post verification failed")
    print("VERIFIED PUBLISHED", saved["id"], saved["link"], flush=True)


if __name__ == "__main__":
    main()
