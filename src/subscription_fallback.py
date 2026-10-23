"""Explicit usage-limit-only fallback. No API keys or pipeline replay."""
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile

log = logging.getLogger(__name__)
_EXHAUSTED = set()


def enabled():
    return os.getenv('BLOG_CODEX_USAGE_FALLBACK') == 'claude'


def _key(home, model):
    return hashlib.sha256(json.dumps([str(home), model, os.getenv('GITHUB_RUN_ID', ''),
        os.getenv('GITHUB_RUN_ATTEMPT', '')]).encode()).hexdigest()


def _state_path():
    # Runner-local, non-secret marker shared by selection/generation subprocesses.
    root, raw = os.getenv('RUNNER_TEMP'), os.getenv('BLOG_CODEX_USAGE_STATE')
    if os.getenv('GITHUB_ACTIONS') != 'true' or not root or not raw:
        return None
    path, root = Path(raw), Path(root).resolve()
    if path.is_absolute() and path.resolve().is_relative_to(root):
        return path
    return None


def exhausted(home, model):
    if not enabled():
        return False
    key = _key(home, model)
    if key in _EXHAUSTED:
        return True
    path = _state_path()
    try:
        return path is not None and path.read_text() == key
    except OSError:
        return False


def _mark(home, model):
    key = _key(home, model)
    _EXHAUSTED.add(key)
    path = _state_path()
    if path is not None:
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as file:
                file.write(key)
                temporary = Path(file.name)
            temporary.replace(path)
        except OSError:
            log.warning('Codex usage marker unavailable; process-local fallback remains active')


def run(primary, fallback, *, home, model):
    if not exhausted(home, model):
        try:
            return primary(), 'codex'
        except Exception as error:
            # Closed transport types only: arbitrary exceptions must not trigger switching.
            from src.codex_client import CodexRequestError, CodexResponseError
            from src.codex_search import NativeSearchError
            if (not enabled() or not isinstance(error, (CodexRequestError, CodexResponseError, NativeSearchError))
                    or error.reason != 'usage_limit'):
                raise
            _mark(home, model)
            log.warning('Provider fallback: codex -> claude reason=usage_limit')
    return fallback(), 'claude'


class SearchRows(list):
    def __init__(self, rows, provider):
        super().__init__(rows)
        self.provider = provider
