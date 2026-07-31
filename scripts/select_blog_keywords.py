#!/usr/bin/env python3
"""블로그 키워드 동적 선정 — 검색모듈(실검색량) → 필터 → 발행여부 체크 → 미발행 상위 N.

파이프라인:
  1) 니치 시드에서 네이버 검색광고 keywordstool 로 **연관 키워드 + 실검색량 + 경쟁도** 수집
     (트렌드/opportunity 아님 — 블로그 트래픽엔 절대 검색량이 맞음, 확립된 방침)
  2) 블로그 적합 필터: 경쟁 '높음' 제외(저권위라 못 이김), 브랜드/불용어 제외, 최소검색량
  3) **발행여부 체크(dedup)**: 양 블로그 WP REST 에서 그 키워드 글이 이미 있는지 확인 → 있으면 제외
  4) 미발행 블로그 적합 키워드를 검색량 순 상위 N 으로 선정 → data/blog_targets.json

출력만 하며 발행하지 않는다(발행 연결은 별도 단계). CI 에서 NAVER_AD_* + WP_* 시크릿으로 실행.
"""

import json
import os
import re
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.keyword_gate import fetch_keyword_stats  # noqa: E402

# 니치 앵커 — 여기서 네이버가 '현재' 연관 키워드+검색량을 돌려줘 동적이다(하드코딩 후보 아님).
NICHE_SEEDS = [
    "영양제", "유산균", "콜라겐", "비타민", "다이어트",   # 건강/보충제
    "세럼", "앰플", "크림", "토너", "두피",              # K-뷰티/스킨케어
]

# 브랜드·불용어(글감 아님) — 검색량 커도 제외. 필요시 확장.
BLOCK = {
    "더마팩토리", "올리브영", "쿠팡", "아이허브", "닥터지", "메디힐",
    "냄새", "세균", "콜레스테롤", "탈모", "갱년기",  # 너무 광범위/단독 헤드텀
}
MIN_VOLUME = 3000       # 이 미만은 블로그 트래픽 기여 작음
BLOCK_COMP = {"높음"}    # 경쟁 높음 = 저권위라 상위노출 어려움 → 제외


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def collect_candidates() -> dict:
    """시드 → 연관 키워드 집계 {키워드: {vol, comp}} (검색량 최대값 유지)."""
    agg: dict[str, dict] = {}
    for seed in NICHE_SEEDS:
        for r in fetch_keyword_stats(seed):
            kw = r["keyword"].strip()
            if not kw:
                continue
            if r["monthly"] > agg.get(kw, {}).get("vol", -1):
                agg[kw] = {"vol": r["monthly"], "comp": r.get("comp", "")}
    return agg


def is_blog_worthy(kw: str, meta: dict) -> bool:
    if meta["vol"] < MIN_VOLUME:
        return False
    if meta["comp"] in BLOCK_COMP:
        return False
    if norm(kw) in {norm(b) for b in BLOCK}:
        return False
    if len(kw) < 2 or not re.search(r"[가-힣A-Za-z]", kw):
        return False
    return True


def _site_has_post(base: str, auth: tuple, keyword: str) -> bool:
    """WP REST 검색으로 그 키워드 글이 이미 있는지(제목에 키워드 포함) 확인."""
    try:
        r = requests.get(
            f"{base.rstrip('/')}/wp-json/wp/v2/posts", auth=auth,
            params={"search": keyword, "status": "publish,draft", "per_page": 20,
                    "_fields": "title,slug"}, timeout=30)
        if r.status_code != 200:
            return False
        nk = norm(keyword)
        for p in r.json():
            title = re.sub(r"<[^>]+>", "", p.get("title", {}).get("rendered", ""))
            if nk in norm(title) or nk in norm(p.get("slug", "")):
                return True
        return False
    except Exception as e:  # noqa: BLE001 — dedup 실패는 치명적 아님(안전하게 미발행 취급 안 함)
        print(f"  발행체크 실패({keyword}@{base}): {e}", file=sys.stderr)
        return False


def load_sites() -> list[dict]:
    """발행 대상 사이트 크리덴셜 로드(있는 것만)."""
    sites = []
    if os.getenv("WP_GENERAL_URL"):
        sites.append({"name": "trendpulse", "base": os.environ["WP_GENERAL_URL"],
                      "auth": (os.environ["WP_GENERAL_USERNAME"],
                               os.environ["WP_GENERAL_APP_PASSWORD"])})
    if os.getenv("WP_URL"):
        sites.append({"name": "bytepulse", "base": os.environ["WP_URL"],
                      "auth": (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])})
    elif os.getenv("WP_TECH_URL"):
        sites.append({"name": "bytepulse", "base": os.environ["WP_TECH_URL"],
                      "auth": (os.environ["WP_TECH_USERNAME"],
                               os.environ["WP_TECH_APP_PASSWORD"])})
    return sites


def main() -> int:
    top_n = int(os.getenv("SELECT_TOP_N", "2"))
    print("검색모듈(네이버 검색광고) 연관 키워드 수집 중...", file=sys.stderr)
    agg = collect_candidates()
    worthy = {k: v for k, v in agg.items() if is_blog_worthy(k, v)}
    ranked = sorted(worthy.items(), key=lambda x: -x[1]["vol"])

    sites = load_sites()
    if not sites:
        print("경고: WP 크리덴셜 없음 — 발행여부 체크 생략(전부 미발행 취급)", file=sys.stderr)

    selected = []
    print("\n[블로그 적합 후보 — 실검색량 순 / 발행여부]")
    for kw, meta in ranked[:30]:
        posted_on = [s["name"] for s in sites if _site_has_post(s["base"], s["auth"], kw)]
        # 미발행 = 대상 사이트 어디에도 없음(둘 다 새 글감일 때만 선정)
        unposted = len(posted_on) == 0
        status = "미발행 ✅" if unposted else f"발행됨({','.join(posted_on)})"
        mark = ""
        if unposted and len(selected) < top_n:
            selected.append({"keyword": kw, "volume": meta["vol"], "comp": meta["comp"]})
            mark = " ← 선정"
        print(f"  {meta['vol']:>7,} 경쟁:{meta['comp']:<4} {kw}  [{status}]{mark}")

    out = {"topN": top_n, "selected": selected}
    dest = Path(__file__).parent.parent / "data" / "blog_targets.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n선정({len(selected)}): {[s['keyword'] for s in selected]}")
    print(f"저장: {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
