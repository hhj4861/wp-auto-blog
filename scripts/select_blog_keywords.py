#!/usr/bin/env python3
"""Select measured market topics per category; enqueue only on explicit request."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from src.editorial import fetch_source, source_fetch_scope
from src.posting_schedule import KST, SLOTS, category_for_date
from src.selection_feedback import load_history
from src.topic_inventory import near_posting_slot, refill_categories
from src import latest_issues, latest_listings
import src.market_topics as market_module
from src.analysis_runtime import error_code
from src.market_topics import (CATEGORIES, REPORT, ROOT, select_category,
                               fresh_market_item, existing_titles, duplicate, enqueue_report)


WRITER_DONE = ('skipped_duplicate', 'completed', 'held_draft')


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


@source_fetch_scope()
def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--category', choices=['all', 'scheduled', 'inventory', *CATEGORIES], default='all')
    parser.add_argument('--slot', choices=SLOTS, default='morning', help='Slot for scheduled category research')
    parser.add_argument('--enqueue', action='store_true')
    parser.add_argument('--reuse', action='store_true', help='Reuse a verified report up to 36 hours old')
    parser.add_argument('--recover-slot', action='store_true',
        help='Try other categories after an empty selection; stop at the first verified stock')
    args = parser.parse_args()
    if args.recover_slot and (not args.enqueue or args.category not in CATEGORIES):
        raise ValueError('Slot recovery requires --enqueue and a specific category')
    if args.category == 'scheduled':
        args.category = category_for_date(datetime.now(KST).date(), args.slot)
    top_n = int(os.getenv('SELECT_TOP_N') or '2')
    if not 1 <= top_n <= 5:
        raise ValueError('SELECT_TOP_N must be between 1 and 5')
    if args.enqueue and args.category == 'all':
        raise ValueError('Enqueue requires a specific scheduled category')
    if args.category == 'inventory' and not args.enqueue:
        raise ValueError('Inventory refill requires --enqueue')
    if (args.category == 'inventory' and os.getenv('SELECT_SLOT_GUARD') == '1'
            and near_posting_slot(datetime.now(timezone.utc))):
        # A late GitHub schedule must never hold the posting concurrency group at a slot.
        print('Inventory refill skipped: started near a posting slot', flush=True)
        return 0
    reports = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    titles = existing_titles()
    if args.category == 'inventory':
        # Keep two reserves per category, nearest slots first, so a slot never
        # depends on a single just-in-time selection.
        limit = int(os.getenv('SELECT_INVENTORY_LIMIT') or '2')
        queue = json.loads((ROOT / 'data/topic_queue_general.json').read_text())
        # Stock that duplicates a later post is not stock: the writer would skip it.
        categories = refill_categories(queue, datetime.now(timezone.utc), limit,
            fresh=lambda row, category, now: (fresh_market_item(row, category, now)
                                              and not duplicate(row['keyword'], row['topic'], titles)
                                              and not market_module.review_candidate(row, titles)), target=2)
        print(f'Inventory refill categories: {categories or "none (stocked)"}', flush=True)
    else:
        categories = list(CATEGORIES) if args.category == 'all' else [args.category]
    if args.recover_slot:
        categories = [args.category, *(category for category in CATEGORIES if category != args.category)]
    recovery_deadline = monotonic() + 12 * 60
    original_budget = market_module.MAX_RESEARCH_SECONDS
    failures = []
    stocked = False
    # The writer's verdict is final: never revive a topic it skipped as a
    # (semantic) duplicate or already used, even if the report still lists it.
    queue_path = ROOT / 'data/topic_queue_general.json'
    original_queue = json.loads(queue_path.read_text()) if queue_path.exists() else []
    writer_done = {row['keyword'] for row in original_queue
                   if isinstance(row, dict) and row.get('status') in WRITER_DONE and row.get('keyword')}
    source_cache = {}  # Share successful and failed URL checks across this one run.
    for category in categories:
        if args.recover_slot:
            remaining = recovery_deadline - monotonic()
            if remaining <= 0:
                break
            market_module.MAX_RESEARCH_SECONDS = min(original_budget, 180, remaining)
        diagnostics = None
        previous = reports.get(category, {})
        try:
            if args.recover_slot and category != args.category:
                # Prefer existing screened reserves before spending another research pass.
                if any(fresh_market_item(row, row.get('category'))
                       and not duplicate(row['keyword'], row['topic'], titles)
                       and not market_module.review_candidate(row, titles)
                       for row in original_queue):
                    stocked = True
                    break
            history = load_history(previous, category, datetime.now(timezone.utc))
            selection_options = {'failure_history': history} if history else {}
            # Apply writer verdicts to NEW research too, not only report reuse.
            excluded = set(writer_done)
            if args.category == 'inventory':
                excluded.update(row['keyword'] for row in queue
                    if fresh_market_item(row, row.get('category')))
            if excluded:
                selection_options['excluded_keywords'] = sorted(excluded)
            # With latest-issue selection, only reuse latest items: an evergreen report
            # must not stop today's listing from being read.
            latest_mode = market_module.LATEST_LISTING_SELECTION and category in latest_listings.SOURCES
            usable = [x for x in previous.get('selected', [])
                      if fresh_market_item(x, category) and not duplicate(x['keyword'], x['topic'], titles)
                      and x['keyword'] not in excluded
                      and (not latest_mode or latest_issues.required(x))]
            if args.reuse and usable:
                diagnostics = {'checked_at': datetime.now(timezone.utc).isoformat(),
                               'failed_candidates': [], 'reused_keywords': [], 'outcome': 'checking_sources'}
                accessible = []
                for item in usable:
                    available = _sources_accessible(item, source_cache)
                    semantic_duplicate = available and market_module.review_candidate(item, titles, accessible)
                    if available and not semantic_duplicate:
                        accessible.append(item)
                        if len(accessible) == top_n:
                            break
                    else:
                        diagnostics['failed_candidates'].append({
                            'keyword': item['keyword'], 'reason': ('semantic_duplicate' if semantic_duplicate
                                                                  else 'required_source_unavailable'),
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
                    selection_options['excluded_keywords'] = sorted(excluded | {
                        row['keyword'] for row in diagnostics['failed_candidates']})
                    report = select_category(category, top_n, titles, **selection_options)
                    diagnostics['outcome'] = 'reselected' if report['selected'] else 'no_candidate_passed'
                    report = {**report, 'reuse_source_diagnostics': diagnostics}
            else:
                report = select_category(category, top_n, titles, **selection_options)
            reports[category] = report
            _write_reports(reports)
            print(json.dumps(report, ensure_ascii=False), flush=True)
            if not report['selected']:
                failures.append(category)
                print(f'{category}: selection held ({report.get("selection_outcome", "no_candidate_passed")}); '
                      f'rejected={len(report.get("rejected", []))} '
                      f'held={len(report.get("held", []))} '
                      f'evaluated={report.get("evaluated_candidates", 0)}/'
                      f'measured={report.get("measured_candidates", 0)} '
                      f'stop={report.get("research_stop_reason", "unknown")}', file=sys.stderr, flush=True)
                if args.recover_slot and report.get('operational_error') in market_module.runtime.FATAL:
                    break
                continue
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
                stocked = True
                if args.recover_slot:
                    break
        except Exception as error:
            failures.append(category)
            reports[category] = {"category": category, "selected_at": datetime.now(timezone.utc).isoformat(),
                "selected": [], "held": [], "rejected": [],
                "failure_history": load_history(previous, category, datetime.now(timezone.utc)),
                "research_stop_reason": "selection_failed", "operational_error": error_code(error)}
            _write_reports(reports)
            if diagnostics is not None and diagnostics['outcome'] == 'selecting_replacement':
                diagnostics['outcome'] = 'selection_failed'
                reports[category]["reuse_source_diagnostics"] = diagnostics
                _write_reports(reports)
            print(f'{category}: selection held (selection_failed: {error_code(error)})', file=sys.stderr, flush=True)
        finally:
            market_module.MAX_RESEARCH_SECONDS = original_budget
    if args.recover_slot:
        return 0 if stocked else 1
    if args.category == 'inventory':
        # A held category is normal; fail only when no requested refill succeeded.
        return 1 if categories and len(failures) == len(categories) else 0
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
