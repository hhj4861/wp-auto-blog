#!/usr/bin/env python3
"""사이트 단위 상업신호 축소 — 글당 쇼핑·제휴 링크를 상한까지 줄인다.

배경(2026-08-25 실측): bytepulse 발행 133건을 content.raw 전수 파싱한 결과,
생애 기사 노출 552는 전량 쇼핑 링크 비중 0~4% 코호트(20건)에서 나왔고
비중 30~100% 코호트(113건)의 노출은 정확히 0이었다. 발행 시기를 통제해도
(2026-01 버스트: K-* 16건 노출 0 / 테크 9건이 552 전량) 결과가 갈린다.
구글이 유일하게 색인한 기사(tailwind, pos 8.0)의 쇼핑 링크도 0개다.

처치: 초과분은 **링크만 해제하고 텍스트는 남긴다**(<a href=shop>text</a> -> text).
산문을 재작성하지 않으므로 결정적 변환이며 실패 모드가 없다. E-E-A-T 정규식이
6~7회 시도 후에도 62% 잔존한 것과 다른 점이 이것이다.

⚠️ 인과는 미측정이다. 상관은 실측이지만 "링크를 줄이면 재크롤이 온다"는
아무도 재지 않았다. 이건 처방이 아니라 확인 실험의 처치군이다.

가역: 변경 전 content.raw 를 data/backup/decomm_<날짜>/<id>.html 로 먼저 저장한다.
멱등: 실행 후 잔존이 상한 이하이므로 재실행해도 변경 0.

사용:
    DRY_RUN=true  python scripts/decommercialize.py     # 기본 — 보고만
    DRY_RUN=false python scripts/decommercialize.py     # 실제 적용
    SHOP_LINK_CAP=3 DECOMM_WORKERS=6 ...                # 조정
    python scripts/decommercialize.py --restore data/backup/decomm_2026-08-25
"""

import datetime
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.monetization import _DIRECT_SHOP_DOMAINS  # noqa: E402

ROOT = Path(__file__).parent.parent
CAP = int(os.getenv("SHOP_LINK_CAP", "3"))
WORKERS = int(os.getenv("DECOMM_WORKERS", "6"))
DRY = os.getenv("DRY_RUN", "true").lower() not in ("false", "0", "no")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

# monetization의 소매몰 정의를 재사용하고, 코드에 없는 제휴 호스트만 보강한다.
SHOP_HOSTS = tuple(_DIRECT_SHOP_DOMAINS) + (
    "coupang.com",          # link.coupang.com / www.coupang.com
    "oliveyoung.co.kr",     # 국내 올리브영(글로벌과 별개 호스트)
    "awin1.com",            # Awin 딥링크
    "amzn.to",
)

# <a ...href="...">inner</a> — 중첩 없는 단순 앵커. WP 본문은 이 형태만 쓴다.
ANCHOR = re.compile(r'<a\b[^>]*?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                    re.IGNORECASE | re.DOTALL)


def is_shop(href: str) -> bool:
    h = href.lower()
    return any(host in h for host in SHOP_HOSTS)


def decommercialize(html: str, cap: int = CAP) -> tuple[str, int, int]:
    """상한 초과 쇼핑 링크를 언랩. (새 HTML, 원래 쇼핑링크 수, 제거 수) 반환."""
    seen = 0

    def repl(m: re.Match) -> str:
        nonlocal seen
        if not is_shop(m.group(1)):
            return m.group(0)
        seen += 1
        if seen <= cap:
            return m.group(0)
        return m.group(2)          # 링크만 해제, 텍스트 유지

    out = ANCHOR.sub(repl, html)
    return out, seen, max(0, seen - cap)


def _api_auth():
    load_dotenv(str(ROOT / ".env"))
    return (os.environ["WP_URL"].rstrip("/") + "/wp-json/wp/v2",
            (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"]))


def _published_ids(api, auth) -> list[int]:
    ids, page = [], 1
    while True:
        r = requests.get(f"{api}/posts", auth=auth, headers=UA,
                         params={"per_page": 100, "page": page,
                                 "status": "publish", "_fields": "id"}, timeout=60)
        if r.status_code != 200 or not r.json():
            break
        ids += [p["id"] for p in r.json()]
        page += 1
    return ids


def main() -> int:
    api, auth = _api_auth()
    backup_dir = ROOT / "data" / "backup" / f"decomm_{datetime.date.today().isoformat()}"
    ids = _published_ids(api, auth)
    print(f"발행글 {len(ids)}개 · 쇼핑링크 상한 {CAP} · "
          f"{'DRY RUN(변경 없음)' if DRY else '실제 적용'}", flush=True)
    if not DRY:
        backup_dir.mkdir(parents=True, exist_ok=True)
        print(f"백업 위치: {backup_dir}", flush=True)

    def work(pid: int):
        try:
            raw = requests.get(f"{api}/posts/{pid}", auth=auth, headers=UA,
                               params={"context": "edit", "_fields": "id,slug,content.raw"},
                               timeout=40).json()
            html = raw["content"]["raw"]
            slug = raw.get("slug", "")
            new, total, removed = decommercialize(html)
            if removed == 0:
                return ("same", pid, slug, total, 0)
            if DRY:
                return ("would", pid, slug, total, removed)
            (backup_dir / f"{pid}.html").write_text(html, encoding="utf-8")
            r = requests.post(f"{api}/posts/{pid}", auth=auth, headers=UA,
                              json={"content": new}, timeout=60)
            r.raise_for_status()
            return ("changed", pid, slug, total, removed)
        except Exception as e:  # noqa: BLE001
            return ("error", pid, str(e)[:80], 0, 0)

    rows, errors = [], []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for fut in as_completed([ex.submit(work, p) for p in ids]):
            tag, pid, slug, total, removed = fut.result()
            if tag == "error":
                errors.append((pid, slug))
            elif tag != "same":
                rows.append((pid, slug, total, removed))

    rows.sort(key=lambda r: -r[3])
    print(f"\n대상 {len(rows)}건 · 제거 예정 링크 {sum(r[3] for r in rows)}개")
    print(f"{'id':>6}  {'쇼핑링크':>6} {'제거':>5}  slug")
    for pid, slug, total, removed in rows[:25]:
        print(f"{pid:>6}  {total:>6} {removed:>5}  {slug[:56]}")
    if len(rows) > 25:
        print(f"  … 외 {len(rows) - 25}건")
    if errors:
        print(f"\n실패 {len(errors)}건: {errors[:5]}")
    if DRY:
        print("\n[DRY] 아무것도 변경하지 않았다. 적용하려면 DRY_RUN=false")
    return 1 if errors else 0


def restore(backup: str) -> int:
    """백업 디렉터리의 content.raw를 그대로 되돌린다."""
    api, auth = _api_auth()
    files = sorted(Path(backup).glob("*.html"))
    if not files:
        sys.exit(f"백업 파일 없음: {backup}")
    print(f"원복 대상 {len(files)}건 ← {backup}")
    ok = fail = 0
    for f in files:
        pid = int(f.stem)
        r = requests.post(f"{api}/posts/{pid}", auth=auth, headers=UA,
                          json={"content": f.read_text(encoding="utf-8")}, timeout=60)
        if r.status_code == 200:
            ok += 1
        else:
            fail += 1
            print(f"  실패 #{pid} HTTP {r.status_code}")
    print(f"원복 완료: 성공 {ok} · 실패 {fail}")
    return 1 if fail else 0


if __name__ == "__main__":
    if "--restore" in sys.argv:
        sys.exit(restore(sys.argv[sys.argv.index("--restore") + 1]))
    sys.exit(main())
