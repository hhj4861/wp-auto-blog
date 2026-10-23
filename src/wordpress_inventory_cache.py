"""Complete snapshots confined to one serialized Actions run; never a stale fallback."""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
_REFRESH = ContextVar('refresh_wordpress_inventory', default=False)
TTL_SECONDS = 180

def binding():
    run, name, root = (os.getenv(k, '') for k in
        ('GITHUB_RUN_ID', 'BLOG_INVENTORY_PATH', 'RUNNER_TEMP'))
    if not run.isdigit() or not name or not root:
        return None
    path = Path(name).resolve()
    if not path.is_relative_to(Path(root).resolve()):
        return None
    credentials = [os.getenv(k, '') for k in
        ('WP_GENERAL_URL', 'WP_GENERAL_USERNAME', 'WP_GENERAL_APP_PASSWORD')]
    return path, run, hashlib.sha256(json.dumps(credentials).encode()).hexdigest()

def load():
    config = binding()
    if not config or _REFRESH.get():
        return None
    path, run, digest = config
    try:
        row = json.loads(path.read_text())
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(row['fetched_at'])).total_seconds()
        titles = row['titles']
        if (row['run_id'] == run and row['binding'] == digest and row['complete'] is True
                and 0 <= age <= TTL_SECONDS and isinstance(titles, list)
                and len(titles) <= 100_000 and all(isinstance(t, str) for t in titles)):
            return titles
    except (OSError, ValueError, TypeError, KeyError):
        pass
    return None

def save(titles):
    config = binding()
    if not config:
        return
    path, run, digest = config
    row = {'run_id': run, 'binding': digest, 'complete': True,
           'fetched_at': datetime.now(timezone.utc).isoformat(), 'titles': titles}
    temporary = path.with_suffix('.tmp')
    try:
        temporary.write_text(json.dumps(row, ensure_ascii=False), encoding='utf-8')
        temporary.chmod(0o600)
        temporary.replace(path)
    except OSError:
        pass

@contextmanager
def fresh_read():
    token = _REFRESH.set(True)
    try:
        yield
    finally:
        _REFRESH.reset(token)
