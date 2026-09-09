"""Codex transport contracts; no subscription requests or credentials required."""
from pathlib import Path
import subprocess
from unittest.mock import MagicMock

import pytest

from src.codex_client import CodexSubscriptionClient, failure_reason
from src.content_generator import ContentConfig, ContentGenerator, LLMProvider


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr("src.codex_client.shutil.which", lambda name: "/bin/codex")
    return CodexSubscriptionClient(home=str(tmp_path), model="test-model", timeout=2)


def test_transport_uses_stdin_final_file_and_isolated_environment(client, monkeypatch):
    for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "WP_APP_PASSWORD"):
        monkeypatch.setenv(key, "secret-must-not-reach-child")
    seen = {}

    def launch(command, **kwargs):
        seen.update(command=command, **kwargs)
        output = Path(command[command.index("--output-last-message") + 1])
        process = MagicMock(returncode=0)
        process.communicate.side_effect = lambda prompt, timeout: output.write_text("<p>한국어 본문</p>", encoding="utf-8")
        seen["process"] = process
        return process

    monkeypatch.setattr("src.codex_client.subprocess.Popen", launch)
    prompt = "Write HTML; literal $(do-not-execute)"
    assert client.generate(prompt) == "<p>한국어 본문</p>"
    assert prompt not in seen["command"]
    seen["process"].communicate.assert_called_once_with(prompt, timeout=2)
    assert seen["env"]["CODEX_HOME"] == str(client.home)
    assert "secret-must-not-reach-child" not in seen["env"].values()
    assert 'forced_login_method="chatgpt"' in seen["command"]
    assert "--ignore-user-config" in seen["command"]
    assert "read-only" in seen["command"]
    assert "test-model" in seen["command"]
    assert seen["command"][-1] == "-"
    assert not Path(seen["cwd"]).exists()


@pytest.mark.parametrize("returncode", [0, 1, 127])
def test_missing_output_or_failed_process_is_not_success(client, monkeypatch, returncode):
    monkeypatch.setattr("src.codex_client.subprocess.Popen", lambda *a, **k: MagicMock(returncode=returncode))
    with pytest.raises(RuntimeError, match="no final message|request failed"):
        client.generate("prompt")


def test_timeout_kills_process_group_and_reaps(client, monkeypatch):
    process = MagicMock(pid=123)
    process.communicate.side_effect = [subprocess.TimeoutExpired("codex", 2), (None, None)]
    monkeypatch.setattr("src.codex_client.subprocess.Popen", lambda *a, **k: process)
    kill = MagicMock()
    monkeypatch.setattr("src.codex_client.os.killpg", kill)
    with pytest.raises(RuntimeError, match="timed out"):
        client.generate("prompt")
    kill.assert_called_once()
    assert process.communicate.call_count == 2


def test_actions_rejected_before_auth_or_process_access(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(RuntimeError, match="private worker"):
        CodexSubscriptionClient(home="")


@pytest.mark.parametrize("home", ["", "relative/path", "/nonexistent/blog-codex-home"])
def test_requires_explicit_existing_absolute_home(monkeypatch, home):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    with pytest.raises(ValueError, match="BLOG_CODEX_HOME"):
        CodexSubscriptionClient(home=home)


def test_subscription_errors_never_fall_back_to_paid_api(client, monkeypatch):
    generator = ContentGenerator.__new__(ContentGenerator)
    generator.config = ContentConfig(provider=LLMProvider.CODEX)
    generator._codex_client = MagicMock()
    generator._codex_client.generate.side_effect = RuntimeError("usage limit")
    for name in ("_call_openai", "_call_gemini", "_call_claude_agent_sdk"):
        monkeypatch.setattr(generator, name, MagicMock(side_effect=AssertionError("unexpected fallback")))
    with pytest.raises(RuntimeError, match="usage limit"):
        generator._call_llm("prompt")
    generator._call_openai.assert_not_called()
    generator._call_gemini.assert_not_called()
    generator._call_claude_agent_sdk.assert_not_called()


def test_environment_configuration_and_cli_selection(monkeypatch):
    from src.main import parse_args
    monkeypatch.setenv("BLOG_WRITER_PROVIDER", "codex")
    monkeypatch.setenv("BLOG_CODEX_HOME", "/srv/blog-auth")
    assert ContentConfig().provider == LLMProvider.CODEX
    assert ContentConfig().codex_home == "/srv/blog-auth"
    monkeypatch.setattr("sys.argv", ["blog", "--mode", "general", "--writer-provider", "codex", "--codex-model", "test-model"])
    args = parse_args()
    assert args.writer_provider == "codex"
    assert args.codex_model == "test-model"
    monkeypatch.delenv("BLOG_WRITER_PROVIDER")
    assert ContentConfig().provider == LLMProvider.ANTHROPIC


def test_generator_initializes_subscription_transport(client, monkeypatch):
    monkeypatch.setattr(ContentGenerator, "_setup_apis", lambda self: None)
    generator = ContentGenerator(ContentConfig(provider=LLMProvider.CODEX, codex_home=str(client.home)))
    monkeypatch.setattr(generator._codex_client, "generate", lambda prompt: "reviewed HTML")
    assert generator._call_llm("source-verified prompt") == "reviewed HTML"


def test_real_subprocess_round_trip_without_network(tmp_path, monkeypatch):
    import sys
    # A local stand-in verifies actual pipes, UTF-8, output handling and cleanup.
    executable = tmp_path / "codex"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import sys\nfrom pathlib import Path\n"
        "prompt = sys.stdin.read()\n"
        "Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(prompt, encoding='utf-8')\n",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr("src.codex_client.shutil.which", lambda name: str(executable))
    client = CodexSubscriptionClient(home=str(tmp_path))
    assert client.generate("<p>한글\n본문 $literal</p>") == "<p>한글\n본문 $literal</p>"


def test_rejects_checkout_and_default_auth_home(monkeypatch):
    import src.codex_client as module
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    for home in (Path(module.__file__).resolve().parent.parent, Path.home() / ".codex"):
        with pytest.raises(ValueError, match="outside|dedicated"):
            CodexSubscriptionClient(home=str(home))


@pytest.mark.parametrize('diagnostic,reason', [
    ('refresh_token_reused; secret=do-not-print', 'refresh_token_reused'),
    ('401 Unauthorized: Your refresh token was already used. Please log in.', 'refresh_token_reused'),
    ('refresh_token_expired: please login', 'refresh_token_expired'),
    ('refresh token has been revoked', 'refresh_token_revoked'),
    ('Token refresh failed: invalid_grant', 'invalid_grant'),
    ('Your authentication token has been invalidated', 'token_invalidated'),
    ('Your authentication token has expired', 'access_token_expired'),
    ('Token refresh failed: 401 Unauthorized', 'refresh_failed'),
    ('401 Unauthorized', 'unauthorized'),
    ('not logged in', 'authentication_required'),
    ('You have hit your usage limit', 'usage_limit'),
    ('429 Too Many Requests', 'usage_limit'),
    ('model_not_found', 'model_unavailable'),
    ('context_length_exceeded', 'prompt_too_large'),
    ('unexpected argument --unknown', 'cli_incompatible'),
    ('error sending request', 'network_or_service'),
    ('secret=do-not-print, unrecognized error', 'unclassified'),
])
def test_failure_reason_never_echoes_raw_diagnostics(client, monkeypatch, diagnostic, reason):
    process = MagicMock(returncode=1)
    process.communicate.return_value = (None, diagnostic)
    monkeypatch.setattr('src.codex_client.subprocess.Popen', lambda *a, **kw: process)
    with pytest.raises(RuntimeError) as caught:
        client.generate('private prompt')
    assert f'reason={reason}' in str(caught.value)
    assert diagnostic not in str(caught.value)
    assert 'do-not-print' not in str(caught.value)
    assert 'private prompt' not in str(caught.value)


def test_unknown_diagnostics_are_not_exposed():
    assert failure_reason(None) == 'unclassified'
