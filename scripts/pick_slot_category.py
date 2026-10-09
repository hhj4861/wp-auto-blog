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
    category = topic_inventory.pick_category(queue, args.preferred, datetime.now(timezone.utc),
        fresh=lambda row, category, now: (fresh_market_item(row, category, now)
                                          and not duplicate(row['keyword'], row['topic'], titles)
                                          and (not args.latest_only or latest_issues.required(row))))
    if category is None:
        print(f'No verified stock for {args.preferred} or any fallback category', file=sys.stderr)
        return 1
    if category != args.preferred:
        print(f'{args.preferred} has no verified stock; publishing {category} instead', file=sys.stderr)
    print(category)
    return 0


if __name__ == '__main__':
    sys.exit(main())
