"""Subscription-authenticated Codex CLI transport for a private writing worker."""

import os
import json
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile


def require_private_actions():
    """Managed subscription auth is restricted to private, default-branch CI."""
    if os.getenv("GITHUB_ACTIONS", "").lower() != "true":
        return
    try:
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
        repo = event["repository"]
        trusted = (repo.get("private") is True
                   and repo.get("full_name") == os.environ.get("GITHUB_REPOSITORY")
                   and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
                   and os.environ.get("GITHUB_REF") == "refs/heads/" + repo["default_branch"])
    except (KeyError, OSError, ValueError, TypeError):
        trusted = False
    if not trusted:
        raise RuntimeError("Codex subscription writer requires a private worker on its default branch")


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
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                text=True, encoding="utf-8", start_new_session=True,
            )
            try:
                process.communicate(prompt, timeout=self.timeout)
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
                raise RuntimeError(
                    f"Codex subscription request failed (exit {process.returncode}); "
                    "check CLI version, ChatGPT login and usage limits on the private worker"
                )
            result = output.read_text(encoding="utf-8").strip() if output.is_file() else ""
            if not result:
                raise RuntimeError("Codex returned no final message")
            return result
