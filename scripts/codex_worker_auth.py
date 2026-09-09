"""CI credential lifecycle; never print or upload authentication as artifacts."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.codex_client import require_private_actions


def validate_auth(raw):
    data = json.loads(raw)
    if data.get("auth_mode") != "chatgpt" or not data.get("tokens", {}).get("refresh_token"):
        raise ValueError("A dedicated managed ChatGPT login is required")
    return raw


def main():
    require_private_actions()
    home = Path(os.environ["RUNNER_TEMP"]) / "trendpulse-codex"
    auth = home / "auth.json"
    if sys.argv[1] == "restore":
        if not os.environ.get("WORKER_ADMIN_TOKEN"):
            raise RuntimeError("WORKER_ADMIN_TOKEN required to persist refreshed auth")
        raw = validate_auth(os.environ.get("CODEX_AUTH_JSON", "{}"))
        home.mkdir(mode=0o700, exist_ok=False)
        auth.touch(mode=0o600)
        auth.write_text(raw, encoding="utf-8")
    elif sys.argv[1] == "persist":
        try:
            if auth.exists():
                raw = validate_auth(auth.read_text())
                subprocess.run(["gh", "secret", "set", "CODEX_AUTH_JSON", "--repo", os.environ["GITHUB_REPOSITORY"]],
                               input=raw, text=True, check=True, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=60)
        finally:
            if home.exists():
                shutil.rmtree(home)
    else:
        raise ValueError("Expected restore or persist")


if __name__ == "__main__":
    main()
