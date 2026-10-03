"""Image transport contracts: no credentials or live provider calls."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.codex_client import CodexResponseError, CodexSubscriptionClient, _generated_image_path

THREAD = "12345678-1234-1234-1234-123456789abc"
EVENT = json.dumps({"type": "thread.started", "thread_id": THREAD})


def artifact(home):
    p = home / "generated_images" / THREAD / "native.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"image-bytes" * 200)
    return p


def test_native_image_transport_isolated_and_does_not_trust_final_path(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr("src.codex_client.shutil.which", lambda _: "/bin/codex")
    monkeypatch.setenv("OPENAI_API_KEY", "never-forward")
    monkeypatch.setenv("WP_GENERAL_APP_PASSWORD", "never-forward")
    seen = {}
    expected = artifact(tmp_path)

    def launch(command, **kwargs):
        seen.update(command=command, **kwargs)
        Path(command[command.index("--output-last-message") + 1]).write_text("/etc/passwd")
        proc = MagicMock(returncode=0)
        proc.communicate.return_value = (EVENT, "")
        return proc

    monkeypatch.setattr("src.codex_client.subprocess.Popen", launch)
    client = CodexSubscriptionClient(home=str(tmp_path))
    assert client.generate_image("Make one image") == expected
    assert "--json" in seen["command"]
    assert "features.image_generation=true" in seen["command"]
    assert "features.shell_tool=false" in seen["command"]
    assert "features.apps=false" in seen["command"]
    assert 'web_search="disabled"' in seen["command"]
    assert "never-forward" not in seen["env"].values()
    assert "read-only" in seen["command"]


@pytest.mark.parametrize(
    "stdout", ["", "{}", json.dumps({"type": "thread.started", "thread_id": "../../secrets"})]
)
def test_missing_or_unsafe_thread_rejected(tmp_path, stdout):
    artifact(tmp_path)
    with pytest.raises(CodexResponseError, match="one CLI thread"):
        _generated_image_path(stdout, tmp_path)


def test_missing_multiple_and_symlink_artifacts_rejected(tmp_path):
    with pytest.raises(CodexResponseError):
        _generated_image_path(EVENT, tmp_path)
    p = artifact(tmp_path)
    second = p.with_name("second.png")
    second.write_bytes(p.read_bytes())
    with pytest.raises(CodexResponseError):
        _generated_image_path(EVENT, tmp_path)
    second.unlink()
    p.unlink()
    p.symlink_to(tmp_path / "auth.json")
    with pytest.raises(CodexResponseError):
        _generated_image_path(EVENT, tmp_path)
