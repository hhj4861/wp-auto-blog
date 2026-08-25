#!/usr/bin/env python3
"""고정 코호트 크롤 판독기 — bytepulse 회생 실험(2026-08-25 착수)의 주 계측기.

사이트맵 전수 감사(gsc_index_audit.py)와 달리 **고정 14개 URL의 lastCrawlTime
시계열**만 본다. 매주 같은 URL을 재서 전주 대비 델타를 낸다.

왜 lastCrawlTime이 주 지표인가: 크롤이 선행하지 않으면 색인은 원리적으로
불가능하다. 노출을 기다리면 몇 주를 낭비하고 나서야 알게 된다.

코호트 설계 (2-arm):
  A 요청군 — 색인 요청 O · 외부 인바운드 O
  B 무요청 대조군 — 아무 처치도 하지 않는다. **여기가 유일한 진짜 반증 장치다.**
    요청 없이 움직이는지가 popularity 명제의 검정이며, D+28 게이트 G2가 이걸 본다.
  표면 — 관찰만. 리프 카테고리는 배경 재크롤률이 높아 게이트가 아니라 공변량이다.

⚠️ Arm B에는 절대 색인 요청을 하지 마라. 요청하면 실험이 죽는다.

쿼터: 14건/회 = 속성 일일 상한(2000)의 0.7%.

사용:
    python scripts/crawl_watch.py                 # 판독 + data/crawl_watch/<날짜>.json 적재
    python scripts/crawl_watch.py --init          # 코호트 파일 생성(최초 1회)
    python scripts/crawl_watch.py --no-save       # 저장 없이 보기만
코호트 편집: data/crawl_watch/cohort.json (프로브 발행 후 URL 채워 넣기)
"""

import datetime
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault(
    "GSC_SA_JSON_PATH", str(ROOT / ".claude/scripts/mcp-test-457809-b0c43a4ec208.json"))

import src.gsc_client as g  # noqa: E402

SITE = os.getenv("GSC_SITE_URL", "https://bytepulse.io/")
OUT = ROOT / "data" / "crawl_watch"
COHORT = OUT / "cohort.json"

DEFAULT_COHORT = {
    "site": "https://bytepulse.io/",
    "baseline_date": "2026-08-25",
    "note": "프로브 발행 후 arm_a 의 PROBE 항목을 실제 URL로 교체할 것. arm_b 는 절대 건드리지 않는다.",
    "arm_a": [
        "https://bytepulse.io/tailwind-css-alternatives-review-2026/",
        "https://bytepulse.io/cursor-vs-copilot-vs-2026/",
        "https://bytepulse.io/linux-desktop-for-developers-2026-setup-guide/",
        "https://bytepulse.io/linear-vs-jira-vs-asana-apis-in-2026/",
        "PROBE_1_URL_미발행",
        "PROBE_2_URL_미발행",
    ],
    "arm_b": [
        "https://bytepulse.io/chatgpt-cognitive-debt-review-2026/",
        "https://bytepulse.io/openai-codex-vs-deepseek-harness-2026/",
        "https://bytepulse.io/netbird-vs-tailscale-vs-2026/",
        "https://bytepulse.io/astro-vs-next-2026/",
    ],
    "surface": [
        "https://bytepulse.io/",
        "https://bytepulse.io/category/tech/ai-tools/",
        "https://bytepulse.io/category/k-culture/k-pop/",
        "https://bytepulse.io/category/tech/",
    ],
    "index_requested": [],
}


def load_cohort() -> dict:
    if not COHORT.exists():
        sys.exit(f"코호트 파일 없음 — 먼저 실행: python {Path(__file__).name} --init")
    return json.loads(COHORT.read_text(encoding="utf-8"))


def init() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    if COHORT.exists():
        print(f"이미 존재: {COHORT} (덮어쓰지 않음)")
        return 0
    COHORT.write_text(json.dumps(DEFAULT_COHORT, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(f"코호트 생성: {COHORT}")
    return 0


def _prev_snapshot() -> dict:
    snaps = sorted(p for p in OUT.glob("20*.json"))
    if not snaps:
        return {}
    return {r["url"]: r for r in json.loads(snaps[-1].read_text(encoding="utf-8"))["rows"]}


def main(save: bool) -> int:
    cohort = load_cohort()
    site = cohort.get("site", SITE)
    g.SITE_URL = site
    g._access_token()  # 스레드 401 레이스 방지 — 반드시 선호출

    arms = [("A", u) for u in cohort["arm_a"]] \
        + [("B", u) for u in cohort["arm_b"]] \
        + [("표면", u) for u in cohort["surface"]]
    live = [(a, u) for a, u in arms if u.startswith("http")]
    skipped = [(a, u) for a, u in arms if not u.startswith("http")]

    def probe(item):
        arm, url = item
        r = g.inspect_url(url, site)
        return {
            "arm": arm, "url": url,
            "coverage": r.get("coverageState") or r.get("error", "")[:60],
            "lastCrawl": (r.get("lastCrawlTime") or "")[:10],
            "verdict": r.get("verdict", ""),
        }

    with ThreadPoolExecutor(max_workers=4) as ex:
        rows = list(ex.map(probe, live))

    prev = _prev_snapshot()
    today = datetime.date.today().isoformat()
    print(f"{site} · 코호트 {len(live)}건 · {today}")
    print(f"{'arm':<5} {'lastCrawl':<12} {'Δ':<3} {'coverage':<34} url")
    new_crawls = {"A": 0, "B": 0}
    for r in sorted(rows, key=lambda x: (x["arm"], x["url"])):
        before = prev.get(r["url"], {}).get("lastCrawl", "")
        delta = ""
        # 최초 실행(prev 없음)은 베이스라인이다 — 전부 NEW로 찍히면 게이트가 오발동한다.
        if prev and r["lastCrawl"] and r["lastCrawl"] != before:
            delta = "NEW"
            if r["arm"] in new_crawls:
                new_crawls[r["arm"]] += 1
        print(f"{r['arm']:<5} {r['lastCrawl'] or '—':<12} {delta:<3} "
              f"{r['coverage'][:34]:<34} {r['url'][:58]}")
    for arm, url in skipped:
        print(f"{arm:<5} {'(미발행)':<12} {'':<3} {'—':<34} {url}")

    print(f"\n신규 크롤: Arm A {new_crawls['A']} · **Arm B {new_crawls['B']}**")
    if new_crawls["B"]:
        print("  ← Arm B는 무요청 대조군이다. 여기가 움직였으면 G2(D+28) 통과 신호.")
    indexed = sum(1 for r in rows if "색인이 생성되었" in r["coverage"])
    print(f"색인 상태 URL: {indexed} / {len(rows)}")

    if save:
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / f"{today}.json"
        path.write_text(json.dumps(
            {"date": today, "site": site, "rows": rows,
             "new_crawls": new_crawls, "indexed": indexed},
            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"적재: {path}")
    return 0


if __name__ == "__main__":
    if "--init" in sys.argv:
        sys.exit(init())
    sys.exit(main(save="--no-save" not in sys.argv))
