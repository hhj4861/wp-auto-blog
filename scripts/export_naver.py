#!/usr/bin/env python3
"""create_*.py 스크립트의 본문을 네이버 블로그용으로 변환·저장.

사용:  python scripts/export_naver.py scripts/create_greekyogurt_trend.py [...]
각 스크립트에서 TITLE/SLUG/ARTICLE(+COUPANG 있으면)을 읽어 naver_export/<slug>.html 생성.
trendpulse(한글) 스크립트가 대상 — 네이버 블로그는 한국어라 한글 본문을 쓴다.
"""

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.naver_format import save_naver_export  # noqa: E402


def _load(path: str):
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    targets = sys.argv[1:]
    if not targets:
        print("사용법: python scripts/export_naver.py scripts/create_greekyogurt_trend.py [...]")
        return 1
    for path in targets:
        m = _load(path)
        coup = getattr(m, "COUPANG", None)
        save_naver_export(m.SLUG, m.TITLE, m.ARTICLE, coupang_url=coup)
    return 0


if __name__ == "__main__":
    sys.exit(main())
