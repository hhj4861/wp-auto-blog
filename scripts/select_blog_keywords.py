#!/usr/bin/env python3
"""Select measured market topics per category; enqueue only on explicit request."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from src.editorial import fetch_source
from src.market_topics import (CATEGORIES, REPORT, ROOT, select_category,
                               fresh_market_item, existing_titles, duplicate, enqueue_report)


def _write_reports(reports):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    temp = REPORT.with_suffix('.tmp')
    temp.write_text(json.dumps(reports, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(REPORT)


def _sources_accessible(item, source_cache):
    """Check availability only. Saved source text/hashes remain the approved evidence."""
    urls = [item['source_url']]
    for source in item['verified_sources']:
        url = source.get('url')
        if not isinstance(url, str) or not url.strip():
            return False
        if url not in urls:
            urls.append(url)
    for url in urls:
        if url not in source_cache:
            try:
                source = fetch_source(url)
                available = (isinstance(source, dict) and isinstance(source.get('url'), str)
                             and bool(source['url'].strip())
                             and isinstance(source.get('excerpt'), str) and bool(source['excerpt'].strip()))
            except Exception:
                available = False  # Never retain or print provider exception text.
            source_cache[url] = available
        if not source_cache[url]:
            return False
    return True


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
    source_cache = {}  # Share successful and failed URL checks across this one run.
    for category in categories:
        diagnostics = None
        previous = reports.get(category, {})
        try:
            usable = [x for x in previous.get('selected', [])
                      if fresh_market_item(x, category) and not duplicate(x['keyword'], x['topic'], titles)]
            if args.reuse and usable:
                diagnostics = {'checked_at': datetime.now(timezone.utc).isoformat(),
                               'failed_candidates': [], 'reused_keywords': [], 'outcome': 'checking_sources'}
                accessible = []
                for item in usable:
                    if _sources_accessible(item, source_cache):
                        accessible.append(item)
                        if len(accessible) == top_n:
                            break
                    else:
                        diagnostics['failed_candidates'].append({
                            'keyword': item['keyword'], 'reason': 'required_source_unavailable',
                            'checked_at': datetime.now(timezone.utc).isoformat(), 'candidate': item})
                if accessible:
                    diagnostics.update(outcome='reused', reused_keywords=[x['keyword'] for x in accessible])
                    report = {**previous, 'selected': accessible, 'reuse_source_diagnostics': diagnostics}
                else:
                    # Preserve the failed originals outside the live selected list even
                    # if the following fresh selection raises or the runner stops.
                    diagnostics['outcome'] = 'selecting_replacement'
                    reports[category] = {**previous, 'selected': [], 'reuse_source_diagnostics': diagnostics}
                    _write_reports(reports)
                    excluded = [row['keyword'] for row in diagnostics['failed_candidates']]
                    report = select_category(category, top_n, titles, excluded_keywords=excluded)
                    diagnostics['outcome'] = 'reselected' if report['selected'] else 'no_candidate_passed'
                    report = {**report, 'reuse_source_diagnostics': diagnostics}
            else:
                report = select_category(category, top_n, titles)
            reports[category] = report
            _write_reports(reports)
            print(json.dumps(report, ensure_ascii=False), flush=True)
            if not report['selected']:
                raise RuntimeError('No candidate passed all checks')
            # Reserve selected keywords across this run's category reports too.
            for item in report['selected']:
                titles.extend([item['keyword'], item['topic']])
            if args.enqueue:
                path = ROOT / 'data/topic_queue_general.json'
                queue = json.loads(path.read_text())
                queue = enqueue_report(queue, report)
                temp = path.with_suffix('.tmp')
                temp.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                temp.replace(path)
        except Exception:
            failures.append(category)
            if diagnostics is not None and diagnostics['outcome'] == 'selecting_replacement':
                diagnostics['outcome'] = 'selection_failed'
                reports[category] = {**previous, 'selected': [], 'reuse_source_diagnostics': diagnostics}
                _write_reports(reports)
            print(f'{category}: selection held (selection_failed)', file=sys.stderr, flush=True)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
