#!/usr/bin/env python3
"""Read-only API check: no model, demand lookup, topic writes, or publication."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.youtube_discovery import discover


def main():
    _, audit = discover('리뷰', datetime.now(timezone.utc), lambda _: {'seeds': []})
    print(json.dumps({key: audit[key] for key in ('provider', 'status', 'checked_at', 'error')
                      if key in audit} | {'verified_video_count': len(audit['videos'])}, ensure_ascii=False))
    return 1 if audit['status'] in {'not_configured', 'api_unavailable'} else 0


if __name__ == '__main__':
    raise SystemExit(main())
