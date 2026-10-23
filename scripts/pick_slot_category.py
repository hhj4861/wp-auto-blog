#!/usr/bin/env python3
"""Print the category a scheduled slot publishes from verified stock; exit 1 without stock."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from src.market_topics import CATEGORIES, ROOT, duplicate, existing_titles, fresh_market_item
from src import latest_issues, topic_inventory
from src import market_topics as market

QUEUE = ROOT / 'data/topic_queue_general.json'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preferred', choices=sorted(CATEGORIES), required=True)
    parser.add_argument('--latest-only', action='store_true',
                        help='Consider only latest-issue stock (evergreen stock must not skip latest research)')
    args = parser.parse_args(argv)
    load_dotenv()
    queue = json.loads(QUEUE.read_text())
    titles = existing_titles()
    # The writer skips stock that duplicates a post published after selection;
    # never pick a category whose only stock would be skipped.
    now = datetime.now(timezone.utc)
    while True:
        category = topic_inventory.pick_category(queue, args.preferred, now,
            fresh=lambda row, category, now: (fresh_market_item(row, category, now)
                and not duplicate(row['keyword'], row['topic'], titles)
                and (not args.latest_only or latest_issues.required(row))))
        if category is None:
            break
        candidates = [row for row in queue if row.get('category') == category
            and fresh_market_item(row, category, now)
            and not duplicate(row['keyword'], row['topic'], titles)
            and (not args.latest_only or latest_issues.required(row))]
        candidate = max(candidates, key=latest_issues.priority)
        if not market.review_candidate(candidate, titles):
            break
        candidate.update(status='skipped_duplicate', skipped_at=now.isoformat())
        temp = QUEUE.with_suffix('.tmp')
        temp.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + '\n')
        temp.replace(QUEUE)
        print('Semantic duplicate removed from stock; selecting another topic', file=sys.stderr)
    if category is None:
        print(f'No verified stock for {args.preferred} or any fallback category', file=sys.stderr)
        return 1
    if category != args.preferred:
        print(f'{args.preferred} has no verified stock; publishing {category} instead', file=sys.stderr)
    print(category)
    return 0


if __name__ == '__main__':
    sys.exit(main())
