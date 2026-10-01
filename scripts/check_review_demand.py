"""Read-only Naver discovery check; no Codex, WordPress, report writes or publication."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import market_topics as market, review_discovery as review
from src.selection_feedback import load_history, deferred_keywords

PROBES = ('SSD', '외장SSD', '17인치노트북', 'DDR4')


def main():
    report = json.loads(market.REPORT.read_text()).get('리뷰', {})
    now = datetime.now(timezone.utc)
    history = load_history(report, '리뷰', now)
    deferred = deferred_keywords(history, now)
    old_rejections = {row['keyword'] for row in report.get('discovery_rejections', [])}
    stats, lookups = {}, []
    for seed in PROBES:
        try:
            rows = market.demand_candidates([seed])
        except market.NoMeasuredDemand:
            rows = {}
        except (RuntimeError, OSError, ValueError):
            print(json.dumps({'status': 'lookup_unavailable', 'seed': seed}))
            return 1
        stats.update(rows)
        lookups.append({'seed': seed, 'measured_count': len(rows)})
    pool, _, _ = market._selection_pool(stats, market.historical_terms(), '리뷰', set(),
        deferred, {market.measurement_key(row['keyword']): row for row in history}, retry_keys=set())
    print(json.dumps({'status': 'measured' if stats else 'no_measured_demand',
        'checked_at': now.isoformat(), 'lookups': lookups, 'eligible_count': len(pool),
        'note': 'Discovery only; live WordPress inventory, search intent and source/publication gates are not run.',
        'candidates': [{'keyword': row['keyword'], 'monthly_search': row['monthly'],
            'previously_pruned': row['keyword'] in old_rejections,
            'requirements': review.requirements(row['keyword'])} for row in pool]}, ensure_ascii=False))
    return 0 if pool else 1


if __name__ == '__main__':
    raise SystemExit(main())
