"""Exercise restored CI auth without publishing or disclosing credentials."""
import base64
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.codex_client import CodexRequestError, CodexSubscriptionClient, require_private_actions


def auth_metadata(raw):
    """Allowlist only presence flags and parsed times; never emit arbitrary claims."""
    data = json.loads(raw)
    tokens = data.get("tokens") or {}
    result = {f"has_{key}": bool(tokens.get(key))
              for key in ("access_token", "id_token", "refresh_token")}
    result["chatgpt_auth"] = data.get("auth_mode") == "chatgpt"
    result["last_refresh_utc"] = None
    try:
        stamp = datetime.fromisoformat(data["last_refresh"].replace("Z", "+00:00"))
        if stamp.tzinfo is not None:
            result["last_refresh_utc"] = stamp.astimezone(timezone.utc).isoformat()
    except (KeyError, TypeError, ValueError, AttributeError):
        pass
    result["access_token_expired"] = None
    try:
        payload = tokens["access_token"].split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        expiry = claims.get("exp")
        if type(expiry) in (int, float):
            result["access_token_expired"] = expiry <= datetime.now(timezone.utc).timestamp()
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        pass
    return result


def main():
    require_private_actions()
    home = Path(os.environ["BLOG_CODEX_HOME"])
    auth = home / "auth.json"
    # Let the CLI perform refresh/retry; do not call OAuth endpoints ourselves.
    before = auth.read_text(encoding="utf-8")
    report = {"before": auth_metadata(before)}
    try:
        CodexSubscriptionClient(home=str(home), timeout=120).generate(
            "Reply with OK only. Do not use tools."
        )
        report["reason"] = "ok"
    except CodexRequestError as exc:
        report["reason"] = exc.reason
    except Exception:
        report["reason"] = "auth_probe_failed"
    finally:
        after = auth.read_text(encoding="utf-8") if auth.is_file() else "{}"
        report["after"] = auth_metadata(after)
        report["auth_file_changed"] = before != after
        print(json.dumps(report, sort_keys=True))
    return 0 if report["reason"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
