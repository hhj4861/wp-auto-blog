#!/usr/bin/env python3
"""Refresh a bounded set of stale, search-performing TrendPulse job articles.

Uses complete GSC dates, preserves URLs, backs up raw posts and routes updates
through the same source/quality gates as new posts. No mail or social posting.
"""

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv()


def select_candidates(rows, minimum_clicks=3):
    return sorted(
        [r for r in rows if r["clicks"] >= minimum_clicks
         and 0 < r["position"] <= 20 and urlsplit(r["page"]).hostname == "trendpulse.blog"
         and urlsplit(r["page"]).path.strip("/")
         and len(urlsplit(r["page"]).path.strip("/").split("/")) == 1],
        key=lambda r: (-r["clicks"], -r["impressions"]),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.limit <= 3:
        raise SystemExit("limit must be 1..3")
    # Set before importing the GSC client, which reads the site at module import.
    os.environ["GSC_SITE_URL"] = "https://trendpulse.blog/"
    from src.gsc_client import query
    from src.pipeline import BlogPipeline, PipelineConfig
    from src.content_generator import ContentType

    end = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=3)
    start = end - dt.timedelta(days=27)
    rows = select_candidates(query(start.isoformat(), end.isoformat(), ["page"]))
    base = os.environ["WP_GENERAL_URL"].rstrip("/")
    if base != "https://trendpulse.blog":
        raise SystemExit("TrendPulse URL mismatch")
    session = requests.Session()
    session.auth = (os.environ["WP_GENERAL_USERNAME"], os.environ["WP_GENERAL_APP_PASSWORD"])
    api = base + "/wp-json/wp/v2"
    cats = session.get(api + "/categories", params={"slug": "jobs"}, timeout=30)
    cats.raise_for_status()
    if len(cats.json()) != 1:
        raise SystemExit("jobs category not found")
    job_id = cats.json()[0]["id"]
    output = Path("data/editorial-backups") / os.environ.get("GITHUB_RUN_ID", "refresh-local")
    output.mkdir(parents=True, exist_ok=True)
    outcomes, selected = [], 0
    pipeline = None
    for row in rows:
        if selected >= args.limit:
            break
        slug = unquote(urlsplit(row["page"]).path.strip("/"))
        res = session.get(api + "/posts", params={"slug": slug, "context": "edit"}, timeout=30)
        res.raise_for_status()
        posts = res.json()
        if len(posts) != 1:
            continue
        post = posts[0]
        if post["status"] != "publish" or job_id not in post["categories"]:
            continue
        modified = dt.datetime.fromisoformat(post["modified_gmt"]).replace(tzinfo=dt.timezone.utc)
        if dt.datetime.now(dt.timezone.utc) - modified < dt.timedelta(days=7):
            continue
        selected += 1
        pid = post["id"]
        (output / f"{pid}-before.json").write_text(json.dumps(post, ensure_ascii=False, indent=2))
        print(f"{'APPLY' if args.apply else 'CANDIDATE'} #{pid} {slug} clicks={row['clicks']}", flush=True)
        if not args.apply:
            outcomes.append({"id": pid, "url": row["page"], "action": "preview"})
            continue
        if pipeline is None:
            pipeline = BlogPipeline(PipelineConfig(
                mode="general", category="취업", auto_publish=True,
                content_type=ContentType.GUIDE, use_llm_topics=False))
        result = pipeline.refresh_post(
            pid, post["title"]["raw"], category="취업",
            expected_modified_gmt=post["modified_gmt"])
        outcomes.append({"id": pid, "url": row["page"], **result.to_dict()})
        if result.success:
            after = session.get(f"{api}/posts/{pid}", params={"context": "edit"}, timeout=30)
            after.raise_for_status()
            saved = after.json()
            (output / f"{pid}-after.json").write_text(json.dumps(saved, ensure_ascii=False, indent=2))
            if saved["slug"] != post["slug"] or saved["status"] != post["status"]:
                raise RuntimeError("Refresh changed URL or publication status")
        (output / "results.json").write_text(json.dumps(outcomes, ensure_ascii=False, indent=2))
    (output / "results.json").write_text(json.dumps(outcomes, ensure_ascii=False, indent=2))
    print(f"Checked {len(rows)} candidates; selected {selected}", flush=True)
    if any(o.get("success") is False for o in outcomes):
        raise SystemExit("One or more updates were held; originals preserved. See results artifact.")


if __name__ == "__main__":
    main()
