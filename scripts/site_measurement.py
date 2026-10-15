"""Generate read-only whole-site measurements and retain honest partial artifacts."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.site_measurement import SITE, fetch_inventory, collect_shard, merge_report, render_report


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['inventory','collect','merge'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('--parts', type=Path)
    parser.add_argument('--cache', type=Path)
    parser.add_argument('--signals', type=Path)
    parser.add_argument('--shard', type=int, default=0)
    parser.add_argument('--shards', type=int, default=4)
    parser.add_argument('--refresh-index', action='store_true')
    args = parser.parse_args()
    if args.phase == 'inventory':
        import requests
        if os.environ.get('WP_GENERAL_URL','').rstrip('/') != SITE:
            raise ValueError('Unexpected inventory origin')
        session = requests.Session()
        session.auth = (os.environ['WP_GENERAL_USERNAME'],os.environ['WP_GENERAL_APP_PASSWORD'])
        session.headers['User-Agent'] = 'Mozilla/5.0 (TrendPulse authenticated read-only measurements)'
        ledger_path = ROOT/'data/posted_market_keywords.json'
        ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else []
        result = fetch_inventory(session,ledger=ledger)
        save(args.output,result)
        print(json.dumps({'inventory_posts':len(result['posts']),'inventory_complete':True}))
        return 0
    inventory = json.loads(args.inventory.read_text())
    if args.phase == 'collect':
        from src.gsc_client import query_all, inspect_url, _access_token
        _access_token()  # Resolve credentials before concurrent reads.
        try:
            cache = json.loads(args.cache.read_text()) if args.cache and args.cache.exists() else {}
            if not isinstance(cache,dict): cache = {}
        except (ValueError,OSError):
            cache = {}
        def checkpoint(value):
            save(args.output,value)
            if args.cache: save(args.cache,cache)
        result = collect_shard(inventory,query_all,inspect_url,shard=args.shard,shards=args.shards,
                               cache=cache,refresh=args.refresh_index,on_progress=checkpoint)
        print(json.dumps({'shard':args.shard,'posts':len(result['posts']),
            'index_unavailable':sum(r['index']['status']!='reported' for r in result['posts'])}))
        return 0  # The merged report fails the workflow when any measurements are unavailable.
    parts = []
    for path in sorted(args.parts.rglob('shard-*.json')):
        try: parts.append(json.loads(path.read_text()))
        except (ValueError,OSError): parts.append({})
    signals = json.loads(args.signals.read_text()) if args.signals else None
    result = merge_report(inventory,parts,signals=signals)
    save(args.output,result)
    csv_text,html = render_report(result)
    args.output.with_suffix('.csv').write_text(csv_text)
    args.output.with_suffix('.html').write_text(html)
    print(json.dumps({'posts':len(result['posts']),'collection_complete':result['collection_complete'],
                      'shards_received':result['shards_received']},ensure_ascii=False))
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary,'a') as handle:
            handle.write(f'## 공개 글 측정\n\n공개 글 {len(result["posts"])}편, 전체 수집 '
                         f'{"완료" if result["collection_complete"] else "일부 미완료"}. '
                         'measurement-report artifact의 HTML/CSV/JSON에서 글별 결손과 검토 사유를 확인하세요. '
                         '미확인은 수요 0이나 삭제 근거가 아닙니다.\n')
    return 0 if result['collection_complete'] else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        # Never print response bodies, credentials, private exception strings or tracebacks.
        print('Measurement failed; inspect retained partial artifacts. No posts were changed.',file=sys.stderr)
        raise SystemExit(1)
