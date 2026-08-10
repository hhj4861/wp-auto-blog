#!/usr/bin/env python3
"""레버 A — bytepulse 급진 프루닝 A1 스코어러 → 검수 manifest 생성.

전략: 테크(AI Tools·Dev·SaaS·Content Tools) 강하게 축소, K-*는 큐레이션.
KEEP 화이트리스트(머니글) 절대 보존 + 중복 클러스터 1개만 유지 + 카테고리 차등 목표치.
삭제하지 않는다 — data/prune/prune_manifest_<date>.json 로 유지/제거 분류만 산출.
사람 검수·승인 후 별도 실행 스크립트가 draft 강등.

목표(권장): 테크 유지 ~20, K 유지 ~110.
    TECH_KEEP / K_KEEP 환경변수로 시나리오 조정 가능.
"""

import os
import re
import sys
import json
import html as htmllib
import datetime
from collections import Counter, defaultdict
from pathlib import Path

import requests

BASE = os.environ["WP_URL"].rstrip("/")
AUTH = (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])
API = f"{BASE}/wp-json/wp/v2"

TECH_CATS = {"AI Tools", "Dev Productivity", "SaaS Reviews", "Content Tools"}
K_CATS = {"K-Beauty", "K-Pop", "K-Fashion", "K-Food", "K-Culture"}
MONEY_SLUGS = ("bakuchiol", "arbutin", "exfoliat", "greek", "yogurt", "psyllium",
               "korean-tutor", "learn-korean", "bts-grammy", "toner-pads", "olive-young")
AFF_MARKERS = ("amzn.to", "link.coupang.com", "rwardcode", "preply.com/", "yesstyle", "musinsa")

# 톱티어 K-Pop 아티스트/그룹 — 제목 매치 시 keep 가점(수요 기반 선별). 짧은 약칭은 단어경계.
POP_RE = re.compile("|".join([
    r"\bbts\b", r"blackpink", r"\btwice\b", r"stray\s*kids", r"seventeen", r"newjeans",
    r"le\s*sserafim", r"\bive\b", r"aespa", r"\(g\)i-dle|gi-dle|\bidle\b", r"\bitzy\b",
    r"ateez", r"enhypen", r"\btxt\b|tomorrow x together", r"\bnct\b", r"red\s*velvet",
    r"g-dragon|bigbang", r"\biu\b", r"\briize\b", r"illit", r"babymonster",
    r"zerobaseone|\bzb1\b", r"treasure", r"nmixx", r"kiss of life", r"\bday6\b",
    r"\btws\b", r"izna", r"boynextdoor", r"kep1er", r"\bexo\b", r"\bgot7\b", r"\bidle\b",
]), re.I)

# 카테고리별 유지 목표(권장 시나리오, 합계 ~128) — 각 K 니치가 Pinterest 배포 가능한
# 최소량은 남기도록 균형. 없는 카테고리(Uncategorized 등)는 0=전량 제거.
CATEGORY_TARGETS = {
    "K-Beauty": 36, "K-Fashion": 30, "K-Pop": 30, "K-Food": 12, "K-Culture": 1,
    "AI Tools": 12, "Dev Productivity": 4, "SaaS Reviews": 3, "Content Tools": 0,
}

BOILERPLATE = [r"<script\b.*?</script>", r"<style\b.*?</style>", r"<table\b.*?</table>"]


def real_prose_words(html: str) -> int:
    h = html
    for pat in BOILERPLATE:
        h = re.sub(pat, " ", h, flags=re.S | re.I)
    paras = re.findall(r"<p\b[^>]*>(.*?)</p>", h, flags=re.S | re.I)
    text = " ".join(re.sub(r"<[^>]+>", " ", p) for p in paras)
    return len(re.sub(r"\s+", " ", text).strip().split())


def title_stem(title: str) -> str:
    t = re.sub(r"<[^>]+>", "", title).lower()
    t = re.sub(r"20\d\d|vs\.?|review|guide|best|complete", " ", t)
    t = re.sub(r"[^a-z가-힣0-9 ]", " ", t)
    return " ".join(t.split()[:4])


def fetch_cat_names() -> dict:
    out = {}
    page = 1
    while True:
        r = requests.get(f"{API}/categories", auth=AUTH,
                         params={"per_page": 100, "page": page, "_fields": "id,name"}, timeout=40)
        if r.status_code != 200 or not r.json():
            break
        for c in r.json():
            out[c["id"]] = c["name"]
        page += 1
    return out


def fetch_posts() -> list[dict]:
    posts, page = [], 1
    while True:
        r = requests.get(f"{API}/posts", auth=AUTH,
                         params={"status": "publish", "per_page": 100, "page": page,
                                 "_fields": "id,slug,link,date,categories,title,content"}, timeout=90)
        if r.status_code != 200 or not r.json():
            break
        posts += r.json()
        page += 1
    return posts


def primary_cat(cat_names: set) -> str:
    """대표 카테고리: K 우선(겸할 경우 K로 보존 유리) → 테크 → 그 외 첫 카테고리."""
    for c in sorted(cat_names & K_CATS):
        return c
    for c in sorted(cat_names & TECH_CATS):
        return c
    return next(iter(sorted(cat_names)), "(없음)")


def bucket_of(cat: str) -> str:
    if cat in K_CATS:
        return "k"
    if cat in TECH_CATS:
        return "tech"
    return "other"


def main() -> int:
    catmap = fetch_cat_names()
    posts = fetch_posts()
    rows = []
    for p in posts:
        content = p.get("content", {}).get("rendered", "")
        title = htmllib.unescape(re.sub(r"<[^>]+>", "", p["title"]["rendered"])).strip()
        cats = {catmap.get(c, "") for c in p.get("categories", [])}
        prim = primary_cat(cats)
        rows.append({
            "id": p["id"], "slug": p["slug"], "link": p["link"], "date": p["date"][:10],
            "title": title, "cats": sorted(c for c in cats if c),
            "primary": prim, "bucket": bucket_of(prim),
            "words": real_prose_words(content),
            "money": any(s in p["slug"] for s in MONEY_SLUGS),
            "aff": any(m in content.lower() for m in AFF_MARKERS),
            "pop": bool(POP_RE.search(title)),
            "stem": title_stem(title),
        })

    # 중복 클러스터(어간 3+) — 클러스터당 최상위 1개만 유지
    stem_counts = Counter(r["stem"] for r in rows if r["stem"])
    dup_stems = {s for s, n in stem_counts.items() if n >= 3}

    def keep_score(r: dict) -> float:
        return (
            (1000 if r["money"] else 0)
            + (0 if r["stem"] in dup_stems else 300)
            + min(r["words"], 1500) / 10.0
            + (200 if r["aff"] else 0)
            + (300 if r["pop"] else 0)   # 톱티어 아티스트 수요 가점(K-Pop 선별 핵심)
            + int(r["date"].replace("-", "")) / 1e7  # 최신 미세 가점(동점 tiebreak)
        )

    for r in rows:
        r["keep_score"] = round(keep_score(r), 2)

    # 중복 클러스터 패자 = 강제 프루닝
    dup_losers = set()
    by_stem = defaultdict(list)
    for r in rows:
        if r["stem"] in dup_stems:
            by_stem[r["stem"]].append(r)
    for stem, grp in by_stem.items():
        grp.sort(key=lambda r: r["keep_score"], reverse=True)
        for r in grp[1:]:
            if not r["money"]:
                dup_losers.add(r["id"])

    # 카테고리별 목표치로 KEEP 선정 (머니글 강제 유지, 중복 패자 제외)
    keep_ids = set()
    for cat in set(CATEGORY_TARGETS) | {r["primary"] for r in rows}:
        tgt = CATEGORY_TARGETS.get(cat, 0)
        cands = [r for r in rows if r["primary"] == cat and r["id"] not in dup_losers]
        cands.sort(key=lambda r: r["keep_score"], reverse=True)
        forced = [r for r in cands if r["money"]]
        keep_ids.update(r["id"] for r in forced)
        room = max(tgt - len(forced), 0)
        for r in [r for r in cands if not r["money"]][:room]:
            keep_ids.add(r["id"])

    for r in rows:
        if r["id"] in keep_ids:
            r["decision"] = "keep"
            r["reason"] = ("머니글" if r["money"] else "카테고리 상위")
        else:
            r["decision"] = "prune"
            rs = []
            if r["id"] in dup_losers:
                rs.append(f"중복클러스터({stem_counts[r['stem']]})")
            if r["bucket"] == "tech":
                rs.append("테크(초경쟁·트래픽0)")
            if r["bucket"] == "other":
                rs.append("미분류")
            if not rs:
                rs.append("카테고리 목표 초과(하위)")
            r["reason"] = "·".join(rs)

    # 요약
    def tally(bucket):
        b = [r for r in rows if r["bucket"] == bucket]
        k = sum(1 for r in b if r["decision"] == "keep")
        return len(b), k, len(b) - k

    today = datetime.date.today().isoformat()
    keep = [r for r in rows if r["decision"] == "keep"]
    prune = [r for r in rows if r["decision"] == "prune"]
    manifest = {
        "generated": today, "targets": CATEGORY_TARGETS,
        "total": len(rows), "keep": len(keep), "prune": len(prune),
        "dup_clusters": len(dup_stems),
        "by_bucket": {b: dict(zip(("total", "keep", "prune"), tally(b)))
                      for b in ("tech", "k", "other")},
        "keep_ids": sorted(keep_ids),
        "prune_list": [{"id": r["id"], "title": r["title"], "cats": r["cats"],
                        "reason": r["reason"], "words": r["words"], "slug": r["slug"]}
                       for r in sorted(prune, key=lambda r: r["keep_score"])],
        "keep_list": [{"id": r["id"], "title": r["title"], "cats": r["cats"],
                       "reason": r["reason"]} for r in sorted(keep, key=lambda r: -r["keep_score"])],
    }
    dest = Path(__file__).parent.parent / "data" / "prune" / f"prune_manifest_{today}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 콘솔 요약
    print(f"총 {len(rows)}개 → 유지 {len(keep)} · 제거 {len(prune)} (중복 클러스터 {len(dup_stems)})")
    print(f"카테고리 목표 합계: {sum(CATEGORY_TARGETS.values())}\n")
    print(f"{'버킷':<8}{'전체':>6}{'유지':>6}{'제거':>6}")
    for b in ("tech", "k", "other"):
        t, k, pr = tally(b)
        print(f"{b:<8}{t:>6}{k:>6}{pr:>6}")
    # 카테고리별 상세
    print("\n[카테고리별 유지/제거]")
    catrows = defaultdict(lambda: [0, 0])
    for r in rows:
        for c in (r["cats"] or ["(없음)"]):
            catrows[c][0 if r["decision"] == "keep" else 1] += 1
    for c, (k, pr) in sorted(catrows.items(), key=lambda x: -(x[1][0] + x[1][1])):
        print(f"  {c:<18} 유지 {k:>4} · 제거 {pr:>4}")
    print(f"\n제거 예시(하위 8):")
    for r in manifest["prune_list"][:8]:
        print(f"  #{r['id']} [{','.join(r['cats']) or '-'}] {r['reason']} — {r['title'][:44]}")
    print(f"\n저장: {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
