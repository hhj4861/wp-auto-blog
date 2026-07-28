#!/usr/bin/env python3
"""허위 E-E-A-T 일괄 제거 — 병렬판(순차본은 대량 글에서 환경이 프로세스를 조기 종료).

src.monetization.strip_fabricated_eeat 재사용, 단건 GET(context=edit)로 CDN 캐시 회피,
스레드풀로 GET→strip→변경분 POST. 멱등. 완료 시 변경/실패/잔존 요약.
"""
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.monetization import strip_fabricated_eeat  # noqa: E402

WORKERS = int(os.getenv("BACKFILL_WORKERS", "8"))


def main() -> int:
    load_dotenv(str(Path(__file__).parent.parent / ".env"))
    api = os.environ["WP_URL"].rstrip("/") + "/wp-json/wp/v2"
    auth = (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])

    ids, page = [], 1
    while True:
        r = requests.get(f"{api}/posts", auth=auth,
                         params={"per_page": 100, "page": page,
                                 "status": "publish", "_fields": "id"}, timeout=60)
        if r.status_code != 200 or not r.json():
            break
        ids += [p["id"] for p in r.json()]
        page += 1
    print(f"발행글 {len(ids)}개 병렬 백필 (동시 {WORKERS})", flush=True)

    def work(pid):
        try:
            raw = requests.get(f"{api}/posts/{pid}", auth=auth,
                               params={"context": "edit", "_fields": "id,content.raw"},
                               timeout=30).json()["content"]["raw"]
            new = strip_fabricated_eeat(raw)
            if new == raw:
                return ("same", pid)
            requests.post(f"{api}/posts/{pid}", auth=auth,
                          json={"content": new}, timeout=60).raise_for_status()
            return ("changed", pid)
        except Exception as e:  # noqa: BLE001
            return ("error", (pid, str(e)[:80]))

    changed = same = errors = 0
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for i, fut in enumerate(as_completed([ex.submit(work, p) for p in ids]), 1):
            tag, payload = fut.result()
            if tag == "changed":
                changed += 1
            elif tag == "same":
                same += 1
            else:
                errors += 1
                print(f"  실패 #{payload[0]}: {payload[1]}", flush=True)
            if i % 100 == 0:
                print(f"  ...{i}/{len(ids)}", flush=True)

    print(f"\n완료: 변경 {changed} · 무변경 {same} · 실패 {errors}", flush=True)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
