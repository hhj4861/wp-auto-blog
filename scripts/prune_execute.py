#!/usr/bin/env python3
"""레버 A — A3 실행: manifest의 제거 대상을 draft로 강등(삭제 아님) + 복구맵 저장.

기본: 최신 prune_manifest_*.json 의 prune_list 를 draft 로 전환하고
data/prune/prune_plan_<date>.json 복구맵을 남긴다. 가역 — 복구는 --restore.

사용:
    python scripts/prune_execute.py            # 실행(draft 강등)
    python scripts/prune_execute.py --dry       # 미리보기만
    python scripts/prune_execute.py --restore data/prune/prune_plan_YYYY-MM-DD.json  # 원복
"""

import os
import sys
import json
import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import requests

BASE = os.environ["WP_URL"].rstrip("/")
AUTH = (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])
API = f"{BASE}/wp-json/wp/v2/posts"
PRUNE_DIR = Path(__file__).parent.parent / "data" / "prune"


def _set_status(post_id: int, status: str) -> tuple[int, bool, str]:
    try:
        r = requests.post(f"{API}/{post_id}", auth=AUTH, json={"status": status},
                          headers={"User-Agent": "Mozilla/5.0"}, timeout=40)
        return post_id, r.status_code == 200, "" if r.status_code == 200 else f"HTTP {r.status_code}"
    except Exception as e:  # noqa: BLE001
        return post_id, False, str(e)[:80]


def _bulk(ids: list[int], status: str) -> dict:
    ok, fail = [], []
    with ThreadPoolExecutor(max_workers=5) as ex:
        for pid, good, err in ex.map(lambda i: _set_status(i, status), ids):
            (ok if good else fail).append(pid if good else {"id": pid, "err": err})
    return {"ok": ok, "fail": fail}


def _latest_manifest() -> Path:
    files = sorted(PRUNE_DIR.glob("prune_manifest_*.json"))
    if not files:
        sys.exit("manifest 없음 — 먼저 prune_manifest.py 실행")
    return files[-1]


def execute(dry: bool) -> int:
    man = json.loads(_latest_manifest().read_text(encoding="utf-8"))
    prune = man["prune_list"]
    keep_ids = set(man["keep_ids"])
    prune_ids = [r["id"] for r in prune]
    # 안전: 유지 화이트리스트와 교집합 없어야 함
    overlap = keep_ids & set(prune_ids)
    if overlap:
        sys.exit(f"안전중단 — 유지/제거 교집합 {len(overlap)}건: {list(overlap)[:5]}")
    print(f"manifest: {_latest_manifest().name}")
    print(f"제거(draft 강등) 대상: {len(prune_ids)}개 / 유지: {len(keep_ids)}개")
    if dry:
        print("[DRY] 실제 변경 없음. 상위 5개 예시:")
        for r in prune[:5]:
            print(f"  #{r['id']} [{','.join(r['cats']) or '-'}] {r['title'][:50]}")
        return 0

    # 복구맵 먼저 저장(중단돼도 원복 가능) — 대상은 전부 발행상태였음
    today = datetime.date.today().isoformat()
    plan = PRUNE_DIR / f"prune_plan_{today}.json"
    plan.write_text(json.dumps({
        "generated": today, "action": "publish->draft", "prev_status": "publish",
        "restore_hint": "python scripts/prune_execute.py --restore " + str(plan),
        "ids": prune_ids,
        "items": [{"id": r["id"], "slug": r["slug"], "title": r["title"]} for r in prune],
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"복구맵 저장: {plan}")

    res = _bulk(prune_ids, "draft")
    print(f"\ndraft 강등 완료: 성공 {len(res['ok'])} · 실패 {len(res['fail'])}")
    if res["fail"]:
        print("실패 예시:", res["fail"][:5])
        (PRUNE_DIR / f"prune_failed_{today}.json").write_text(
            json.dumps(res["fail"], ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


def restore(plan_path: str) -> int:
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    ids = plan["ids"]
    print(f"원복(draft->publish) 대상: {len(ids)}개")
    res = _bulk(ids, "publish")
    print(f"원복 완료: 성공 {len(res['ok'])} · 실패 {len(res['fail'])}")
    if res["fail"]:
        print("실패 예시:", res["fail"][:5])
    return 0


if __name__ == "__main__":
    if "--restore" in sys.argv:
        sys.exit(restore(sys.argv[sys.argv.index("--restore") + 1]))
    sys.exit(execute(dry="--dry" in sys.argv))
