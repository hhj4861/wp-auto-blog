"""Construct the real posting command without shell interpolation of user input."""
import os
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import requests


def command(env):
    mode = env.get("BLOG_MODE", "general")
    if mode not in {"general", "queue"}:
        raise ValueError("Unsupported worker mode")
    if env.get("WP_GENERAL_URL", "").rstrip("/") != "https://trendpulse.blog":
        raise ValueError("Worker only publishes to TrendPulse")
    args = [sys.executable, "-m", "src.main", "--mode", "general",
            "--writer-provider", "codex", "--content-type", "guide", "--no-llm-topics", "--max-posts", "1"]
    if mode == "queue":
        args.append("--from-queue")
    elif env.get("BLOG_TOPIC"):
        args.extend(["--topic", env["BLOG_TOPIC"]])
    else:
        raise ValueError("General Codex runs require a specific topic")
    category = env.get("BLOG_CATEGORY", "")
    if not category and env.get("BLOG_SCHEDULE"):
        category = {"0 2 * * 2,4": "취업", "0 2 * * 6": "건강"}.get(env["BLOG_SCHEDULE"], "생활정보")
    if category:
        args.extend(["--category", category])
    if env.get("BLOG_PUBLISH") == "true":
        args.append("--auto-publish")
    else:
        args.append("--dry-run")
    return args


def verify_published(results, session, base):
    if len(results) != 1 or not results[0].get("success") or results[0].get("status") != "publish":
        raise RuntimeError("Expected one published post; draft or empty queue is not publishing success")
    post = results[0]
    response = session.get(base + f'/wp-json/wp/v2/posts/{int(post["post_id"])}', timeout=60)
    response.raise_for_status()
    saved = response.json()
    if saved.get("status") != "publish" or saved.get("link") != post["url"]:
        raise RuntimeError("WordPress publication verification failed")
    return post["url"]


def main():
    from dotenv import load_dotenv
    load_dotenv()
    env = dict(os.environ)
    if env.get("BLOG_RESUME_DRAFT_ID"):
        if env.get("BLOG_PUBLISH") != "true":
            raise ValueError("Draft recovery requires explicit publish=true")
        from publish_codex_draft import publish_draft
        url = publish_draft(int(env["BLOG_RESUME_DRAFT_ID"]), env)
        print("VERIFIED CODEX PUBLISHED", url, flush=True)
        if env.get("GITHUB_STEP_SUMMARY"):
            with Path(env["GITHUB_STEP_SUMMARY"]).open("a") as output:
                output.write(f"Codex subscription: [verified published post]({url})\n")
        return 0
    with tempfile.TemporaryDirectory(prefix="blog-result-") as directory:
        path = Path(directory) / "result.json"
        env["BLOG_RESULT_PATH"] = str(path)
        code = subprocess.run(command(env), env=env, check=False).returncode
        if code:
            return code
        if env.get("BLOG_PUBLISH") == "true":
            results = json.loads(path.read_text()) if path.exists() else []
            session = requests.Session()
            session.auth = (env["WP_GENERAL_USERNAME"], env["WP_GENERAL_APP_PASSWORD"])
            session.headers["User-Agent"] = "Mozilla/5.0 (TrendPulse publication verification)"
            url = verify_published(results, session, env["WP_GENERAL_URL"].rstrip("/"))
            print("VERIFIED CODEX PUBLISHED", url, flush=True)
            if env.get("GITHUB_STEP_SUMMARY"):
                with Path(env["GITHUB_STEP_SUMMARY"]).open("a") as output:
                    output.write(f"Codex subscription: [verified published post]({url})\n")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
