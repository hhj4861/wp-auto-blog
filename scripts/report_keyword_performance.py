#!/usr/bin/env python3
"""Read-only, per-published-keyword GSC cohorts. Pending data is never a zero score."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PACIFIC = ZoneInfo('America/Los_Angeles')


def build_report(ledger, query, inspect, now=None, *, on_progress=None, time_budget_seconds=480,
                 monotonic=time.monotonic):
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(PACIFIC).date()
    if not isinstance(ledger, list):
        raise ValueError('Invalid published keyword ledger')
    reports, seen = [], set()
    deadline = monotonic() + time_budget_seconds
    report = {'generated_at': now.isoformat(), 'complete': False, 'site': 'https://trendpulse.blog/',
              'reporting_timezone': 'America/Los_Angeles', 'data_delay_buffer_days': 3,
              'scope': 'latest_60_market_posts_published_within_90_days',
              'notes': 'Per-URL 7/28-day cohorts. Missing/pending data is not zero traffic; '
                       'reported metrics alone do not establish a causal uplift.', 'posts': reports}

    def save_progress():
        if on_progress is not None:
            on_progress(report)

    save_progress()
    # Bounded read-only API usage. Each window is aligned with GSC reporting dates.
    for item in reversed(ledger):
        try:
            published = datetime.fromisoformat(item['published_at'])
            page = urlsplit(item['url'])
            if (published.tzinfo is None or page.scheme != 'https' or page.hostname != 'trendpulse.blog'
                    or page.username or page.password or page.port or page.query or page.fragment
                    or not page.path.strip('/') or not isinstance(item.get('keyword'), str)):
                raise ValueError()
            day = published.astimezone(PACIFIC).date()
            age = (today - day).days
            if not 0 <= age <= 90 or item['url'] in seen:
                continue
        except (KeyError, TypeError, ValueError):
            raise ValueError('Invalid published keyword ledger') from None
        seen.add(item['url'])
        row = {key: item.get(key) for key in ('keyword', 'category', 'post_id', 'url', 'published_at',
            'selection_version', 'monthly_search', 'score', 'score_components', 'trend_status')}
        row.update(age_days=age, windows={}, index={'status': 'not_checked'})
        reports.append(row)
        filters = [{'dimension': 'page', 'operator': 'equals', 'expression': item['url']}]
        for days in (7, 28):
            end = day + timedelta(days=days - 1)
            window = {'start': day.isoformat(), 'end': end.isoformat(), 'data_state': 'final',
                      'status': 'query_pending', 'metrics': None, 'queries': []}
            row['windows'][str(days)] = window
            if today < end + timedelta(days=3):
                window.update(status='collecting', metrics=None, queries=[])
                save_progress()
                continue
            if deadline - monotonic() < 125:  # Two queries, each with a 60-second timeout.
                window.update(status='unavailable', reason='time_budget')
                save_progress()
                continue
            save_progress()  # A killed request still leaves an honest partial artifact.
            try:
                totals = query(day.isoformat(), end.isoformat(), [], row_limit=1,
                               filters=filters, data_state='final')
                queries = query(day.isoformat(), end.isoformat(), ['query'], row_limit=20,
                                filters=filters, data_state='final')
                metrics = ({key: totals[0][key] for key in ('clicks', 'impressions', 'ctr', 'position')}
                           if totals else None)
                window.update(status='reported' if metrics else 'no_reported_rows',
                              metrics=metrics, queries=queries)
            except (Exception, SystemExit):
                window.update(status='unavailable', metrics=None, queries=[])
            save_progress()
        if age < 3:
            row['index'] = {'status': 'collecting'}
        elif deadline - monotonic() < 210:  # Existing inspection helper includes bounded retries.
            row['index'] = {'status': 'unavailable', 'reason': 'time_budget'}
        else:
            try:
                result = inspect(item['url'])
                row['index'] = ({'status': 'unavailable'} if result.get('error') else
                    {'status': 'reported', **{key: result.get(key) for key in
                        ('verdict', 'coverageState', 'lastCrawlTime', 'googleCanonical', 'userCanonical')}})
            except (Exception, SystemExit):
                row['index'] = {'status': 'unavailable'}
        save_progress()
        if len(reports) == 60:
            break
    report['complete'] = True
    save_progress()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger', type=Path, default=ROOT / 'data/posted_market_keywords.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from src.gsc_client import query, inspect_url
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save(report):
        temp = args.output.with_suffix('.tmp')
        temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        temp.replace(args.output)

    report = build_report(json.loads(args.ledger.read_text()), query, inspect_url, on_progress=save)
    print(json.dumps({'posts': len(report['posts']), 'statuses': [
        {'keyword': row['keyword'], '7d': row['windows']['7']['status'],
         '28d': row['windows']['28']['status'], 'index': row['index']['status']}
        for row in report['posts']]}, ensure_ascii=False))
    return int(any(window['status'] == 'unavailable' for row in report['posts']
                   for window in row['windows'].values()) or any(
                   row['index']['status'] == 'unavailable' for row in report['posts']))


if __name__ == '__main__':
    raise SystemExit(main())
