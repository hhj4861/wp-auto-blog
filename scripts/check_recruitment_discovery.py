"""Read-only current vacancies + exact demand + saved cooldown diagnostic.

No Codex invocation, WordPress calls, queue writes or publication.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from time import monotonic
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import market_topics as market, recruitment_discovery
from src.selection_feedback import load_history, deferred_keywords


def main():
    now = datetime.now(timezone.utc)
    stats, audit = recruitment_discovery.prepare({}, market.demand_candidates,
        now.astimezone(ZoneInfo('Asia/Seoul')).date(), deadline=monotonic() + 240)
    stats = {k: r for k, r in stats.items() if r.get('recruitment_notices')}
    old = json.loads(market.REPORT.read_text()).get('취업', {})
    history = load_history(old, '취업', now)
    pool, retries, _ = market._selection_pool(stats, market.historical_terms(), '취업', set(),
        deferred_keywords(history, now), {market.measurement_key(r['keyword']): r for r in history})
    print(json.dumps({'checked_at': now.isoformat(), 'acquisition': audit,
        'eligible_after_saved_history': len(pool), 'retry_count': len(retries),
        'candidates': [{'keyword': r['keyword'], 'monthly_search': r['monthly'],
            'notices': [{k: n[k] for k in ('title', 'url', 'deadline')}
                        for n in r['recruitment_notices']]} for r in pool],
        'note': 'Acquisition and measurement only. Live duplicate inventory, search, independent plan, article and publication gates remain.'}, ensure_ascii=False))
    return 0 if pool else 1


if __name__ == '__main__':
    raise SystemExit(main())
