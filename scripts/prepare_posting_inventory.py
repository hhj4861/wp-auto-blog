#!/usr/bin/env python3
"""Retry only read-only inventory transport failures before research or writing starts."""
from pathlib import Path
import sys
from time import sleep
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from src.market_topics import existing_titles, InventoryUnavailable


def main():
    load_dotenv()
    for attempt in range(3):
        try:
            existing_titles()
            print('Complete WordPress inventory ready for topic screening')
            return 0
        except InventoryUnavailable as error:
            if not error.retryable or attempt == 2:
                raise
            print(f'WordPress inventory transport unavailable; read-only recovery {attempt + 1}/2',
                  file=sys.stderr)
            sleep(15 * (attempt + 1))
    return 1


if __name__ == '__main__':
    sys.exit(main())
