"""Dispatch trusted private CI and propagate its real completion status."""
import os
import re
import time
import uuid
from pathlib import Path

import requests


def worker_inputs(env):
    mode = env.get("BLOG_MODE", "queue")
    if mode not in {"general", "queue", "both"}:
        raise ValueError("Codex worker supports TrendPulse general/queue only")
    category = env.get("BLOG_CATEGORY", "")
    schedule = env.get("BLOG_SCHEDULE", "")
    if not category and schedule:
        category = {"0 2 * * 2,4": "취업", "0 2 * * 6": "건강"}.get(schedule, "생활정보")
    return {"request_id": "blog-" + uuid.uuid4().hex,
            "mode": "queue" if schedule or mode == "queue" else "general",
            "topic": env.get("BLOG_TOPIC", ""), "category": category,
            "publish": "true" if schedule else env.get("BLOG_PUBLISH", "false"),
            "codex_model": env.get("BLOG_CODEX_MODEL", "")}


def dispatch_and_wait(session, repo, inputs, *, timeout=2700, sleep=time.sleep, clock=time.monotonic):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Configure CODEX_WORKER_REPOSITORY as owner/private-repo")
    base = f"https://api.github.com/repos/{repo}"
    info = session.get(base, timeout=30)
    info.raise_for_status()
    metadata = info.json()
    if metadata.get("private") is not True:
        raise RuntimeError("Codex worker repository must be private")
    branch = metadata["default_branch"]
    endpoint = base + "/actions/workflows/codex-worker.yml"
    # Never retry an ambiguous dispatch: it might already have started publishing.
    response = session.post(endpoint + "/dispatches", json={"ref": branch, "inputs": inputs}, timeout=30)
    response.raise_for_status()
    deadline = clock() + timeout
    while clock() < deadline:
        response = session.get(endpoint + "/runs", params={"event": "workflow_dispatch", "branch": branch, "per_page": 100}, timeout=30)
        response.raise_for_status()
        runs = [r for r in response.json()["workflow_runs"] if r["display_title"] == inputs["request_id"]]
        if len(runs) > 1:
            raise RuntimeError("Ambiguous worker runs; inspect before retrying")
        if runs:
            run = runs[0]
            if run["status"] == "completed":
                print("Codex worker:", run["html_url"], flush=True)
                if run["conclusion"] != "success":
                    raise RuntimeError("Codex worker failed; no provider fallback or automatic redispatch")
                return run["html_url"]
        sleep(15)
    raise TimeoutError("Worker status timeout; inspect private Actions before retrying (it may still be running)")


def main():
    token = os.environ.get("CODEX_WORKER_TOKEN", "")
    if not token:
        raise RuntimeError("Configure CODEX_WORKER_TOKEN with private worker Actions read/write access")
    session = requests.Session()
    session.headers.update({"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json"})
    url = dispatch_and_wait(session, os.environ.get("CODEX_WORKER_REPOSITORY", ""), worker_inputs(os.environ))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as output:
            output.write(f"Codex subscription writing and pipeline completed: [private worker]({url})\n")


if __name__ == "__main__":
    main()
