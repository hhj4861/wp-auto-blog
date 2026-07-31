#!/usr/bin/env python3
"""검색모듈 후보 키워드의 실제 네이버 월 검색량 조회 — '검색량 많은' 순 랭킹.

intel.db엔 절대 검색량이 없어(opportunity/상대trend만), keyword_gate의 네이버 검색광고
API(monthlyPcQcCnt+monthlyMobileQcCnt)로 실측한다. 각 시드의 정확검색량 + 연관 키워드까지
집계해 검색량 순으로 출력. 이미 발행한 키워드는 [발행됨] 표기.
"""

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.keyword_gate import fetch_keyword_stats  # noqa: E402

# 검색모듈(keyword-intel) opportunity 상위 후보들 = 시드 (2026-07-31 갱신)
SEEDS = [
    "비타민C 발포정", "스쿠알란 오일", "시트룰린", "저속노화 영양제", "티트리 스팟",
    "낫토키나제", "백수오", "아데노신 크림", "판테놀 앰플", "로즈힙 오일",
    "아쉬와간다", "어성초 토너", "유산균 분말 스틱", "이눌린", "탈모 영양제",
    "프로폴리스 앰플", "PDRN 세럼", "데오드란트",
]
POSTED = {"각질필링", "알부틴크림", "바쿠치올세럼", "두피스케일러", "그릭요거트", "차전자피"}


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def main() -> int:
    seed_vol = {}   # 시드 자체 정확검색량
    agg = {}        # 연관 포함 전체 집계(키워드→최대 검색량, comp)
    for seed in SEEDS:
        rows = fetch_keyword_stats(seed)
        ns = norm(seed)
        for r in rows:
            kw = r["keyword"]
            if r["monthly"] > agg.get(kw, (0,))[0]:
                agg[kw] = (r["monthly"], r.get("comp", ""))
            if norm(kw) == ns:
                seed_vol[seed] = r["monthly"]
    print("=" * 64)
    print("[검색모듈 후보 — 실제 월 검색량 순]")
    for seed, vol in sorted(seed_vol.items(), key=lambda x: -x[1]):
        mark = " [발행됨]" if norm(seed) in POSTED else ""
        print(f"  {vol:>8,}  {seed}{mark}")
    missing = [s for s in SEEDS if s not in seed_vol]
    if missing:
        print(f"  (검색량 데이터 없음: {', '.join(missing)})")

    print("\n[연관 키워드 포함 검색량 상위 30 — 새 글감 발굴]")
    ranked = sorted(agg.items(), key=lambda x: -x[1][0])[:30]
    for kw, (vol, comp) in ranked:
        mark = " [발행됨]" if norm(kw) in POSTED else ""
        print(f"  {vol:>8,}  경쟁:{comp:<4} {kw}{mark}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
