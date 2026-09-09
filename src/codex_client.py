"""Subscription-authenticated Codex CLI transport for a private writing worker."""

import os
import json
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile


def failure_reason(stderr):
    """Return only fixed categories; CLI output may contain credentials or prompts."""
    text = stderr.lower() if isinstance(stderr, str) else ''
    categories = (
        ('refresh_token_reused', ('refresh_token_reused', 'refresh token was already used',
            'refresh token has already been used', 'refresh token has been used')),
        ('refresh_token_expired', ('refresh_token_expired', 'refresh token has expired',
            'refresh token is expired')),
        ('refresh_token_revoked', ('refresh_token_revoked', 'refresh token was revoked',
            'refresh token has been revoked')),
        ('invalid_grant', ('invalid_grant',)),
        ('token_invalidated', ('token_invalidated', 'authentication token has been invalidated')),
        ('access_token_expired', ('token_expired', 'authentication token has expired',
            'access token has expired')),
        ('account_deactivated', ('account_deactivated', 'account has been deactivated')),
        ('refresh_failed', ('token refresh failed', 'failed to refresh', 'could not be refreshed')),
        ('unauthorized', ('401 unauthorized', 'status: 401', 'status code 401', 'unauthorized')),
        ('authentication_required', ('refresh token',
            'please log in', 'please login', 'not logged in', 'authentication token')),
        ('usage_limit', ('usage limit', 'usage_limit', 'rate_limit_exceeded',
            'rate limit', 'quota exceeded', '429 too many requests')),
        ('model_unavailable', ('model_not_found', 'model is not supported',
            'model does not exist', 'unsupported model')),
        ('prompt_too_large', ('context_length_exceeded', 'context window', 'too many tokens')),
        ('cli_incompatible', ('unexpected argument', 'unrecognized option', 'unknown flag')),
        ('network_or_service', ('connection refused', 'connection reset', 'failed to lookup',
            'name resolution', 'dns error', 'error sending request', '503 service', '502 bad gateway')),
    )
    for reason, markers in categories:
        if any(marker in text for marker in markers):
            return reason
    return 'unclassified'


class CodexRequestError(RuntimeError):
    """Only the classified reason, never the underlying CLI diagnostic."""

    def __init__(self, returncode, stderr):
        self.reason = failure_reason(stderr)
        super().__init__(
            f"Codex subscription request failed (exit {returncode}, reason={self.reason}); "
            "check the classified failure before changing authentication"
        )


def require_private_actions():
    """Allow private CI or the explicitly authorized repository's automation."""
    if os.getenv("GITHUB_ACTIONS", "").lower() != "true":
        return
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
        repo = event["repository"]
        allowed_repo = (repo.get("private") is True or (
            os.environ.get("BLOG_CODEX_PUBLIC_AUTOMATION") == "1"
            and repo.get("full_name") == "hhj4861/wp-auto-blog"))
        trusted = (allowed_repo
                   and repo.get("full_name") == os.environ.get("GITHUB_REPOSITORY")
                   and os.environ.get("GITHUB_EVENT_NAME") in {"workflow_dispatch", "schedule"}
                   and os.environ.get("GITHUB_REF") == "refs/heads/" + repo["default_branch"])
    except (KeyError, OSError, ValueError, TypeError):
        trusted = False
    if not trusted:
        raise RuntimeError("Codex requires a private worker or authorized automation on the default branch")


class CodexSubscriptionClient:
    """Use a dedicated ChatGPT login; never fall back to API-key billing."""

    def __init__(self, *, home: str, model: str = "", timeout: int = 600):
        require_private_actions()
        if not home or not Path(home).expanduser().is_absolute():
            raise ValueError("BLOG_CODEX_HOME must be an absolute path to a dedicated Codex login directory")
        self.home = Path(home).expanduser().resolve()
        if self.home.is_relative_to(Path(__file__).resolve().parent.parent):
            raise ValueError("BLOG_CODEX_HOME must be outside the project checkout")
        if self.home == (Path.home() / ".codex").resolve():
            raise ValueError("BLOG_CODEX_HOME must use a dedicated login, not the default Codex home")
        if not self.home.is_dir():
            raise ValueError("BLOG_CODEX_HOME does not exist; provision the private worker and log in first")
        if timeout <= 0:
            raise ValueError("Codex timeout must be positive")
        self.executable = shutil.which("codex")
        if not self.executable:
            raise RuntimeError("Codex CLI is not installed or is missing from PATH")
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        if not prompt.strip():
            raise ValueError("Codex prompt must not be empty")
        # Do not forward WordPress secrets, API keys, or another agent's OAuth token.
        env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "SSL_CERT_FILE") if key in os.environ}
        env["CODEX_HOME"] = str(self.home)
        with tempfile.TemporaryDirectory(prefix="blog-codex-") as workdir:
            output = Path(workdir) / "response.txt"
            command = [
                self.executable,
                "-c", 'forced_login_method="chatgpt"',
                "-c", 'cli_auth_credentials_store="file"',
                "-c", 'model_provider="openai"',
                "-a", "never", "exec",
                "--sandbox", "read-only", "--skip-git-repo-check",
                "--ephemeral", "--ignore-user-config",
                "--output-last-message", str(output),
            ]
            if self.model:
                command.extend(["--model", self.model])
            command.append("-")
            process = subprocess.Popen(
                command, cwd=workdir, env=env, stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", start_new_session=True,
            )
            try:
                captured = process.communicate(prompt, timeout=self.timeout)
            except subprocess.TimeoutExpired:
                if os.name == "posix":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                else:
                    process.kill()
                process.communicate()
                raise RuntimeError("Codex subscription request timed out; no provider fallback was attempted") from None
            if process.returncode:
                stderr = captured[1] if isinstance(captured, tuple) and len(captured) == 2 else ''
                raise CodexRequestError(process.returncode, stderr)
            result = output.read_text(encoding="utf-8").strip() if output.is_file() else ""
            if not result:
                raise RuntimeError("Codex returned no final message")
            return result
