"""Read-only NAVER daily trend probe: no model, queue, WordPress or raw API output."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.recent_search_trend import Collector

CASES = ('엑셀틀고정', '실업급여신청방법', '외장SSD1TB')


def main():
    collector = Collector(datetime.now(timezone.utc))
    signals = collector.collect(CASES)
    print(json.dumps(collector.summary(), ensure_ascii=False))
    for index, signal in enumerate(signals.values(), 1):
        print(json.dumps({'case': index, **{key: signal[key] for key in
            ('status', 'unit', 'latest_period', 'lag_days', 'qualified_rising', 'points') if key in signal}},
            ensure_ascii=False))
    return 0 if any(signal['status'] == 'measured' for signal in signals.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
