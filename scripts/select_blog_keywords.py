#!/usr/bin/env python3
"""Select measured market topics per category; enqueue only on explicit request."""
import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from src.market_topics import (CATEGORIES, REPORT, ROOT, select_category,
                               fresh_market_item, existing_titles, duplicate, enqueue_report)


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--category', choices=['all', *CATEGORIES], default='all')
    parser.add_argument('--enqueue', action='store_true')
    parser.add_argument('--reuse', action='store_true', help='Reuse a verified report up to 36 hours old')
    args = parser.parse_args()
    top_n = int(os.getenv('SELECT_TOP_N') or '2')
    if not 1 <= top_n <= 5:
        raise ValueError('SELECT_TOP_N must be between 1 and 5')
    if args.enqueue and args.category == 'all':
        raise ValueError('Enqueue requires a specific scheduled category')
    reports = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    categories = list(CATEGORIES) if args.category == 'all' else [args.category]
    failures = []
    titles = existing_titles()
    for category in categories:
        try:
            previous = reports.get(category, {})
            usable = [x for x in previous.get('selected', [])
                      if fresh_market_item(x, category) and not duplicate(x['keyword'], x['topic'], titles)]
            if args.reuse and usable:
                report = {**previous, 'selected': usable[:top_n]}
            else:
                report = select_category(category, top_n, titles)
            reports[category] = report
            REPORT.parent.mkdir(parents=True, exist_ok=True)
            temp = REPORT.with_suffix('.tmp')
            temp.write_text(json.dumps(reports, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            temp.replace(REPORT)
            print(json.dumps(report, ensure_ascii=False), flush=True)
            if not report['selected']:
                raise RuntimeError('No candidate passed all checks')
            if args.enqueue:
                path = ROOT / 'data/topic_queue_general.json'
                queue = json.loads(path.read_text())
                queue = enqueue_report(queue, report)
                temp = path.with_suffix('.tmp')
                temp.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                temp.replace(path)
        except Exception as exc:
            failures.append(category)
            print(f'{category}: selection held ({type(exc).__name__}: {exc})', file=sys.stderr, flush=True)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
