"""Fetch the short-lived CAK candidate artifact; never expose GitHub credentials.

Failure removes the previous input and records a fixed diagnostic so the normal
Naver discovery path can continue. This script neither researches nor publishes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlparse
import zipfile
import zlib

import requests

REPOSITORY = "hhj4861/commerce-automation-kit"
WORKFLOW = "keyword-intel-sync.yml"
ARTIFACT = "blog-keyword-candidates"
FILENAME = "blog-keyword-candidates.json"
API = f"https://api.github.com/repos/{REPOSITORY}"
MAX_BYTES = 2 * 1024 * 1024


class FetchError(Exception):
    def __init__(self, reason: str, status: str = "unavailable"):
        self.reason, self.status = reason, status


def _timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (AttributeError, TypeError, ValueError):
        return None


def _positive_id(value):
    return type(value) is int and value > 0


def _api_failure(status_code, fallback):
    return FetchError({401: "api_unauthorized", 403: "api_forbidden"}.get(status_code, fallback))


def _atomic_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, allow_nan=False)
            handle.write("\n")
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def _api_json(session, path, token, params=None):
    response = session.get(
        API + path, params=params, timeout=(10, 30), allow_redirects=False,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"},
    )
    try:
        if response.status_code != 200:
            raise _api_failure(response.status_code, "api_unavailable")
        try:
            value = response.json()
        except ValueError:
            raise FetchError("api_unavailable") from None
        if not isinstance(value, dict):
            raise FetchError("api_unavailable")
        return value
    finally:
        response.close()


def _select_artifact(session, token, now):
    runs = _api_json(session, f"/actions/workflows/{WORKFLOW}/runs", token,
                     {"branch": "main", "status": "completed", "per_page": 20}).get("workflow_runs", [])
    if not isinstance(runs, list):
        raise FetchError("api_unavailable")
    eligible = []
    for run in runs:
        if not isinstance(run, dict):
            continue
        created = _timestamp(run.get("created_at"))
        if (run.get("conclusion") == "success" and run.get("status") == "completed"
                and run.get("head_branch") == "main" and run.get("event") in {"schedule", "workflow_dispatch"}
                and run.get("path") == f".github/workflows/{WORKFLOW}"
                and isinstance(run.get("head_repository"), dict)
                and run["head_repository"].get("full_name") == REPOSITORY
                and _positive_id(run.get("id")) and isinstance(run.get("head_sha"), str)
                and re.fullmatch(r"[a-fA-F0-9]{40}", run["head_sha"])
                and created and now - timedelta(hours=24) <= created <= now):
            eligible.append((created, run))
    if not eligible:
        raise FetchError("no_recent_run", "stale")
    expired = False
    for _, run in sorted(eligible, key=lambda pair: pair[0], reverse=True)[:5]:
        artifacts = _api_json(session, f"/actions/runs/{run['id']}/artifacts", token,
                             {"per_page": 100}).get("artifacts", [])
        if not isinstance(artifacts, list):
            raise FetchError("api_unavailable")
        named = [a for a in artifacts if isinstance(a, dict) and a.get("name") == ARTIFACT]
        if len(named) > 1:
            raise FetchError("invalid_archive", "malformed")
        if not named:
            continue
        artifact = named[0]
        expiry = _timestamp(artifact.get("expires_at"))
        if artifact.get("expired") is not False or not expiry or expiry <= now:
            expired = True
            continue
        if not _positive_id(artifact.get("id")):
            raise FetchError("invalid_archive", "malformed")
        size = artifact.get("size_in_bytes")
        if type(size) is not int or not 0 < size <= MAX_BYTES:
            raise FetchError("artifact_too_large", "malformed")
        return run, artifact
    raise FetchError("artifact_expired" if expired else "no_artifact", "stale" if expired else "unavailable")


def _trusted_download(url):
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        return (parsed.scheme == "https" and parsed.port in {None, 443}
                and not parsed.username and not parsed.password
                and any(host.endswith(suffix) for suffix in (".blob.core.windows.net", ".githubusercontent.com")))
    except ValueError:
        return False


def _download(session, token, artifact):
    # Build the API URL ourselves, never send a token to a URL from metadata.
    response = session.get(
        f"{API}/actions/artifacts/{artifact['id']}/zip", timeout=(10, 30),
        allow_redirects=False, stream=True,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"},
    )
    try:
        if response.status_code != 302:
            raise _api_failure(response.status_code, "download_failed")
        location = response.headers.get("Location", "")
        if not _trusted_download(location):
            raise FetchError("untrusted_redirect")
    finally:
        response.close()
    # Explicitly no Authorization; signed artifact URLs are already credentials.
    response = session.get(location, timeout=(10, 30), allow_redirects=False, stream=True,
                           headers={"Accept": "application/zip"})
    try:
        if response.status_code != 200:
            raise FetchError("download_failed")
        length = response.headers.get("Content-Length")
        if length and (not length.isdigit() or int(length) > MAX_BYTES):
            raise FetchError("artifact_too_large", "malformed")
        chunks, size = [], 0
        for chunk in response.iter_content(chunk_size=65536):
            size += len(chunk)
            if size > MAX_BYTES:
                raise FetchError("artifact_too_large", "malformed")
            chunks.append(chunk)
        data = b"".join(chunks)
    finally:
        response.close()
    digest = artifact.get("digest")
    if digest is not None and (not isinstance(digest, str)
            or digest != "sha256:" + hashlib.sha256(data).hexdigest()):
        raise FetchError("digest_mismatch", "malformed")
    return data


def _unpack(data):
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            files = archive.infolist()
            if len(files) != 1 or files[0].filename != FILENAME:
                raise FetchError("invalid_archive", "malformed")
            info = files[0]
            if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                raise FetchError("invalid_archive", "malformed")
            if info.file_size > MAX_BYTES or info.compress_size > MAX_BYTES:
                raise FetchError("artifact_too_large", "malformed")
            if info.flag_bits & 1 or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise FetchError("invalid_archive", "malformed")
            with archive.open(info) as handle:
                raw = handle.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise FetchError("artifact_too_large", "malformed")
            payload = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if (not isinstance(payload, dict) or type(payload.get("schemaVersion")) is not int
                    or payload["schemaVersion"] != 1 or payload.get("kind") != "cak_keyword_candidates"
                    or not isinstance(payload.get("items"), list) or len(payload["items"]) > 80):
                raise FetchError("invalid_payload", "malformed")
            return payload
    except FetchError:
        raise
    except (zipfile.BadZipFile, ValueError, UnicodeError, RuntimeError, NotImplementedError,
            EOFError, zlib.error, RecursionError):
        raise FetchError("invalid_archive", "malformed") from None


def fetch_candidates(output: Path, status_file: Path, token: str, *, session=None, now=None):
    """Return safe diagnostics. Metric freshness/consistency is checked by the consumer."""
    now = now or datetime.now(timezone.utc)
    status = {"status": "unavailable", "reason": "no_token"}
    owned_session = session is None
    session = session or requests.Session()
    if owned_session:
        session.trust_env = False  # no implicit netrc auth on the signed URL
    try:
        output.unlink(missing_ok=True)
        status_file.unlink(missing_ok=True)
        if not token:
            raise FetchError("no_token")
        run, artifact = _select_artifact(session, token, now)
        status.update(sourceRunId=run["id"], headSha=run["head_sha"], artifactId=artifact["id"],
                      sourceRunCreatedAt=run["created_at"])
        payload = _unpack(_download(session, token, artifact))
        _atomic_json(output, payload)
        status.update(status="ok" if payload["items"] else "empty", reason="downloaded")
    except FetchError as exc:
        status.update(status=exc.status, reason=exc.reason)
    except requests.RequestException:
        status.update(status="unavailable", reason="api_unavailable")
    except OSError:
        status.update(status="unavailable", reason="write_failed")
    finally:
        if owned_session:
            session.close()
    _atomic_json(status_file, status)
    return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--status-file", type=Path, required=True)
    parser.add_argument("--require", action="store_true", help="Fail instead of allowing normal Naver fallback")
    args = parser.parse_args()
    if args.output.resolve() == args.status_file.resolve():
        parser.error("output and status-file must differ")
    result = fetch_candidates(args.output, args.status_file, os.environ.get("GH_TOKEN", "").strip())
    print("CAK candidate import: " + json.dumps(result, ensure_ascii=False))
    return int(args.require and result["status"] not in {"ok", "empty"})


if __name__ == "__main__":
    raise SystemExit(main())
