#!/usr/bin/env python3
"""Apply reviewed content manifests to existing TrendPulse posts, with backups.

Defaults to dry-run. Slug, status and publication date are preserved. This is
deliberately separate from historical maintenance scripts that delete content.
"""

import argparse
from datetime import date
import hashlib
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.editorial import reader_layout
from src.monetization import insert_monetization
from src.post_format import to_canon_headings


def fingerprint(post):
    value = {k: post[k] for k in ("id", "slug", "status", "modified_gmt", "title", "content", "featured_media")}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def validate_entry(entry, root):
    path = (root / entry["content_file"]).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Content path outside manifest directory")
    content = path.read_text()
    soup = BeautifulSoup(content, "html.parser")
    if not soup.find(id="quick-answer") or not soup.find(id="verified-sources"):
        raise ValueError("Reviewed answer and official sources required")
    if "승무원 준비 추천템" in content or soup.find("img"):
        raise ValueError("Unrelated image or affiliate box remains")
    if len(soup.get_text()) < 1000:
        raise ValueError("Reviewed article is unexpectedly short")
    return insert_monetization(reader_layout(to_canon_headings(content)))


def apply_entry(session, api, entry, content, output, apply=False):
    res = session.get(f"{api}/posts", params={"slug": entry["slug"], "context": "edit"}, timeout=45)
    res.raise_for_status()
    posts = res.json()
    if len(posts) != 1 or posts[0]["status"] != "publish":
        raise RuntimeError(f"Expected one published post: {entry['slug']}")
    post = posts[0]
    pid = post["id"]
    backup = output / f"{pid}-before.json"
    backup.write_text(json.dumps(post, ensure_ascii=False, indent=2))
    payload = {
        "title": entry["title"], "content": content, "featured_media": 0,
        "excerpt": entry["meta_description"],
        "meta": {"_yoast_wpseo_metadesc": entry["meta_description"],
                 "_yoast_wpseo_focuskw": entry["focus_keyphrase"],
                 "_yoast_wpseo_title": entry["title"] + " | TrendPulse"},
    }
    (output / f"{pid}-proposed.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"{'APPLY' if apply else 'DRY RUN'} #{pid}: {entry['slug']}", flush=True)
    if not apply:
        return
    current = session.get(f"{api}/posts/{pid}", params={"context": "edit"}, timeout=45)
    current.raise_for_status()
    if fingerprint(current.json()) != fingerprint(post):
        raise RuntimeError("Post changed during preparation; refusing overwrite")
    result = session.post(f"{api}/posts/{pid}", json=payload, timeout=60)
    result.raise_for_status()
    verify = session.get(f"{api}/posts/{pid}", params={"context": "edit"}, timeout=45)
    verify.raise_for_status()
    saved = verify.json()
    for key in ("slug", "status", "date_gmt"):
        if saved[key] != post[key]:
            raise RuntimeError(f"Unexpected change to {key}; backup: {backup}")
    if saved["content"]["raw"].strip() != content.strip() or saved["featured_media"] != 0:
        raise RuntimeError(f"Saved content differs; backup: {backup}")
    (output / f"{pid}-after.json").write_text(json.dumps(saved, ensure_ascii=False, indent=2))
    print(f"VERIFIED {saved['link']}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default="data/editorial/2026-09-08/manifest.json")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    manifest = Path(args.manifest)
    document = json.loads(manifest.read_text())
    if args.apply and (date.today() - date.fromisoformat(document["reviewed_on"])).days > 7:
        raise RuntimeError("Reviewed manifest is older than seven days; recheck facts before applying")
    entries = document["posts"]
    content = [validate_entry(e, manifest.parent) for e in entries]
    base = os.environ["WP_GENERAL_URL"].rstrip("/")
    if urlsplit(base).scheme != "https" or urlsplit(base).hostname != "trendpulse.blog":
        raise RuntimeError("This manifest is only authorized for https://trendpulse.blog")
    output = Path("data/editorial-backups") / os.environ.get("GITHUB_RUN_ID", "local")
    output.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.auth = (os.environ["WP_GENERAL_USERNAME"], os.environ["WP_GENERAL_APP_PASSWORD"])
    session.headers["User-Agent"] = "Mozilla/5.0 (TrendPulse editorial update)"
    for entry, body in zip(entries, content):
        apply_entry(session, base + "/wp-json/wp/v2", entry, body, output, args.apply)


if __name__ == "__main__":
    main()
