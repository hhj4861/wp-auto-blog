"""Credential isolation, archive boundaries and fallback for the CAK transport."""
from datetime import datetime, timezone
from contextlib import nullcontext
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import zipfile

import pytest
import requests

spec = importlib.util.spec_from_file_location("cak_fetch", Path(__file__).parents[1] / "scripts/fetch_cak_candidates.py")
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)
NOW = datetime(2026, 9, 10, 1, tzinfo=timezone.utc)


class Response:
    def __init__(self, status=200, payload=None, headers=None, content=b""):
        self.status_code, self.payload = status, payload
        self.headers, self.content = headers or {}, content
        self.closed = False

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload

    def close(self):
        self.closed = True

    def iter_content(self, chunk_size):
        yield from (self.content[i:i + chunk_size] for i in range(0, len(self.content), chunk_size))


class Session:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def archive(payload=None, names=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
        for name in names or [fetch.FILENAME]:
            target.writestr(name, json.dumps(payload or {"schemaVersion": 1, "kind": "cak_keyword_candidates", "items": []}))
    return output.getvalue()


def run(**overrides):
    return {"id": 123, "conclusion": "success", "status": "completed", "head_branch": "main",
            "event": "schedule", "path": ".github/workflows/keyword-intel-sync.yml",
            "head_repository": {"full_name": fetch.REPOSITORY}, "head_sha": "a" * 40,
            "created_at": "2026-09-10T00:00:00Z", **overrides}


def pipeline(data=None, run_override=None, artifact_override=None, location=None):
    data = archive() if data is None else data
    artifact = {"id": 456, "name": fetch.ARTIFACT, "size_in_bytes": len(data), "expired": False,
                "expires_at": "2026-09-11T00:05:00Z", "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
                **(artifact_override or {})}
    return Session([Response(payload={"workflow_runs": [run(**(run_override or {}))]}),
                    Response(payload={"artifacts": [artifact]}),
                    Response(302, headers={"Location": location or "https://example.blob.core.windows.net/artifact?signature=secret"}),
                    Response(content=data)])


def execute(tmp_path, session, token="example-token"):
    output, status = tmp_path / "candidates.json", tmp_path / "status.json"
    output.write_text("stale previous file")
    status.write_text("stale previous status")
    result = fetch.fetch_candidates(output, status, token, session=session, now=NOW)
    assert json.loads(status.read_text()) == result
    if result["status"] not in {"ok", "empty"}:
        assert not output.exists()
    return result, output


def test_download_never_forwards_authorization_and_records_provenance(tmp_path):
    session = pipeline()
    result, output = execute(tmp_path, session)
    assert result == {"status": "empty", "reason": "downloaded", "sourceRunId": 123,
                      "headSha": "a" * 40, "artifactId": 456, "sourceRunCreatedAt": "2026-09-10T00:00:00Z"}
    assert json.loads(output.read_text())["items"] == []
    assert all(call[1]["allow_redirects"] is False for call in session.calls)
    assert all(call[1]["headers"]["Authorization"] == "Bearer example-token" for call in session.calls[:3])
    assert "Authorization" not in session.calls[3][1]["headers"]
    assert "signature" not in json.dumps(result) and "example-token" not in json.dumps(result)


@pytest.mark.parametrize("override", [
    {"event": "pull_request"}, {"head_branch": "feature"}, {"status": "in_progress"},
    {"conclusion": "failure"}, {"head_repository": {"full_name": "attacker/fork"}},
    {"path": ".github/workflows/unrelated.yml"}, {"created_at": "2026-09-08T23:59:59Z"},
    {"created_at": "2026-09-11T00:00:00Z"}, {"head_sha": "untrusted"},
])
def test_only_recent_successful_main_producer_runs(tmp_path, override):
    session = pipeline(run_override=override)
    result, _ = execute(tmp_path, session)
    assert result["reason"] == "no_recent_run"
    assert len(session.calls) == 1


@pytest.mark.parametrize("url", ["http://example.blob.core.windows.net/x", "https://evil.test/x",
    "https://example.blob.core.windows.net.evil.test/x", "https://u:p@example.blob.core.windows.net/x",
    "https://example.blob.core.windows.net:444/x", "file:///tmp/artifact"])
def test_reject_untrusted_redirect_without_visiting_it(tmp_path, url):
    session = pipeline(location=url)
    result, _ = execute(tmp_path, session)
    assert result["reason"] == "untrusted_redirect"
    assert len(session.calls) == 3


@pytest.mark.parametrize("names", [["../blog-keyword-candidates.json"], ["other.json"],
                                    [fetch.FILENAME, "extra.json"], [fetch.FILENAME, fetch.FILENAME]])
def test_reject_wrong_duplicate_and_additional_zip_entries(tmp_path, names):
    with pytest.warns(UserWarning) if len(set(names)) < len(names) else nullcontext():
        data = archive(names=names)
    result, _ = execute(tmp_path, pipeline(data=data))
    assert result["reason"] == "invalid_archive"


@pytest.mark.parametrize("override,reason", [
    ({"expired": True}, "artifact_expired"), ({"expires_at": "2026-09-10T00:00:00Z"}, "artifact_expired"),
    ({"size_in_bytes": fetch.MAX_BYTES + 1}, "artifact_too_large"),
    ({"digest": "sha256:bad"}, "digest_mismatch"),
])
def test_reject_expired_oversized_or_corrupt_artifact(tmp_path, override, reason):
    result, _ = execute(tmp_path, pipeline(artifact_override=override))
    assert result["reason"] == reason


def test_compressed_small_expanded_oversize_rejected(tmp_path):
    data = archive({"schemaVersion": 1, "kind": "cak_keyword_candidates", "items": [], "padding": "x" * fetch.MAX_BYTES})
    assert len(data) < fetch.MAX_BYTES
    result, _ = execute(tmp_path, pipeline(data=data))
    assert result["reason"] == "artifact_too_large"


def test_stream_size_limit_independent_of_metadata(tmp_path):
    session = pipeline()
    session.responses[-1] = Response(content=b"x" * (fetch.MAX_BYTES + 1))
    result, _ = execute(tmp_path, session)
    assert result["reason"] == "artifact_too_large"


def test_api_failure_is_fixed_diagnostic_and_removes_old_input(tmp_path):
    session = Session([requests.ConnectionError("private token and signed url")])
    result, _ = execute(tmp_path, session)
    assert result == {"status": "unavailable", "reason": "api_unavailable"}


def test_missing_token_removes_old_input_without_network(tmp_path):
    session = Session([])
    result, _ = execute(tmp_path, session, token="")
    assert result == {"status": "unavailable", "reason": "no_token"}
    assert session.calls == []


@pytest.mark.parametrize('status_code,reason', [(401, 'api_unauthorized'), (403, 'api_forbidden')])
@pytest.mark.parametrize('stage', ['metadata', 'archive'])
def test_github_access_failure_distinguishes_auth_and_permissions(tmp_path, status_code, reason, stage):
    session = pipeline()
    session.responses[0 if stage == 'metadata' else 2] = Response(status_code)
    result, _ = execute(tmp_path, session)
    assert result['reason'] == reason and result['status'] == 'unavailable'


def test_malformed_api_json_uses_safe_fallback(tmp_path):
    result, _ = execute(tmp_path, Session([Response(payload=ValueError("private response"))]))
    assert result["reason"] == "api_unavailable"


def test_searches_previous_run_when_new_run_has_no_candidate_artifact(tmp_path):
    session = pipeline()
    session.responses[0] = Response(payload={"workflow_runs": [run(id=124, created_at="2026-09-10T00:30:00Z"), run()]})
    session.responses.insert(1, Response(payload={"artifacts": []}))
    result, _ = execute(tmp_path, session)
    assert result["sourceRunId"] == 123


def test_deep_json_cannot_interrupt_fallback(tmp_path):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as target:
        target.writestr(fetch.FILENAME, "[" * 2000 + "0" + "]" * 2000)
    result, _ = execute(tmp_path, pipeline(data=output.getvalue()))
    assert result["reason"] in {"invalid_archive", "invalid_payload"}


def test_selection_and_publication_both_import_but_auth_probes_do_not():
    import yaml
    selection = yaml.safe_load(Path('.github/workflows/blog-keyword-select.yml').read_text())
    steps = selection['jobs']['select']['steps']
    imported = next(step for step in steps if step.get('name') == 'Import measured CAK keyword candidates')
    assert 'inputs.auth_check_only != true' in imported['if']
    assert 'inputs.research_check_only != true' in imported['if']
    assert steps.index(imported) < next(i for i, step in enumerate(steps) if step.get('name') == 'Discover and verify category topics')
    posting = yaml.safe_load(Path('.github/workflows/auto-post.yml').read_text())
    steps = posting['jobs']['post-queue']['steps']
    imported = next(step for step in steps if step.get('name') == 'Import measured CAK keyword candidates')
    assert steps.index(imported) < next(i for i, step in enumerate(steps) if step.get('name', '').startswith('Run pipeline (Queue'))
    for step in steps:
        if step.get('name', '').startswith('Run pipeline (Queue'):
            assert 'GH_TOKEN' not in step.get('env', {})


def test_candidate_probe_has_no_codex_report_or_publication_side_effects():
    import yaml
    selection = yaml.safe_load(Path('.github/workflows/blog-keyword-select.yml').read_text())
    probe = selection['jobs']['candidate-check']
    assert 'inputs.candidate_check_only == true' in probe['if']
    assert 'inputs.auth_check_only != true' in probe['if']
    assert 'inputs.research_check_only != true' in probe['if']
    serialized = json.dumps(probe)
    assert 'CODEX_AUTH_JSON' not in serialized
    assert 'scripts/select_blog_keywords.py' not in serialized
    assert 'src.main' not in serialized and 'git push' not in serialized
    assert '--require' in serialized
