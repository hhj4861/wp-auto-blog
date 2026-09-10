"""Print fixed native-search field counts, never model/tool text or credentials."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.codex_search import inspect_native_search

QUERY = "ITQ자격증조회"


def main():
    report = inspect_native_search(QUERY)
    print(json.dumps(report, sort_keys=True))
    return 0 if report["reason"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
