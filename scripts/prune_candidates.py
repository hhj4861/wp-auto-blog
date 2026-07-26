#!/usr/bin/env python3
"""품질 프루닝 후보 추출 (bytepulse, 로컬 콘텐츠 신호 기반).

bytepulse는 GSC 색인 ≈ 0이라 노출 데이터로 글을 변별할 수 없다. 대신 로컬에서
계산 가능한 신호로 '저가치' 후보를 랭킹한다:
  - 실제 본문 길이: 보일러플레이트(광고·관련글·출처·고지·제품버튼·표) 제외한 <p> 산문 단어수
  - 중복 주제: 제목 어간(정규화) 클러스터
  - 정체성: 테크 vs K-컬처 (테크 도메인에 K컬처 혼재 = AdSense 정체성 리스크)
읽기 전용. 아무것도 삭제하지 않고 후보 목록·요약만 출력한다.
"""
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(str(Path(__file__).parent.parent / ".env"))
API = os.environ["WP_URL"].rstrip("/") + "/wp-json/wp/v2"
AUTH = (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])

# 보일러플레이트 마커 — 이 블록들의 텍스트는 '실제 본문'에서 제외
BOILERPLATE_PATTERNS = [
    r"<script\b.*?</script>",
    r"<style\b.*?</style>",
    r"<ins\b[^>]*adsbygoogle[^>]*>.*?</ins>",
    r"<table\b.*?</table>",                       # 비교표(구조 데이터)
]


def real_prose_words(html: str) -> int:
    """광고·표·스크립트 제거 후 <p> 산문 단어수 (한글/영문 혼합 근사)."""
    h = html
    for pat in BOILERPLATE_PATTERNS:
        h = re.sub(pat, " ", h, flags=re.S | re.I)
    # 관련글/출처/고지/제품버튼 박스: 특정 문구 포함 문단 제거는 과하므로 <p>만 집계
    paras = re.findall(r"<p\b[^>]*>(.*?)</p>", h, flags=re.S | re.I)
    text = " ".join(re.sub(r"<[^>]+>", " ", p) for p in paras)
    text = re.sub(r"\s+", " ", text).strip()
    # 단어수: 공백 토큰 + 한글은 글자수/2 근사 보정 없이 공백 기준(보수적)
    return len(text.split())


def title_stem(title: str) -> str:
    """중복 클러스터용 제목 어간: 소문자·특수문자 제거·연도 제거·상위 4단어."""
    t = re.sub(r"<[^>]+>", "", title).lower()
    t = re.sub(r"20\d\d|vs\.?|review|guide|best|complete|2026", " ", t)
    t = re.sub(r"[^a-z가-힣0-9 ]", " ", t)
    return " ".join(t.split()[:4])


def main() -> int:
    cats = {}
    page = 1
    while True:
        r = requests.get(f"{API}/categories", auth=AUTH,
                         params={"per_page": 100, "page": page, "_fields": "id,name,parent"}, timeout=30)
        if r.status_code == 400:
            break
        b = r.json()
        if not b:
            break
        for c in b:
            cats[c["id"]] = c["name"]
        page += 1

    KCULTURE = {"K-Pop", "K-Beauty", "K-Food", "K-Fashion", "K-Culture"}

    posts = []
    page = 1
    while True:
        r = requests.get(f"{API}/posts", auth=AUTH, params={
            "per_page": 100, "page": page, "status": "publish",
            "_fields": "id,title,link,date,categories,content"}, timeout=120)
        if r.status_code == 400:
            break
        b = r.json()
        if not b:
            break
        posts += b
        page += 1

    rows = []
    for p in posts:
        cat_names = [cats.get(c, "") for c in (p.get("categories") or [])]
        is_kc = any(c in KCULTURE for c in cat_names)
        words = real_prose_words(p["content"]["rendered"])
        rows.append({
            "id": p["id"], "title": re.sub(r"<[^>]+>", "", p["title"]["rendered"])[:60],
            "link": p["link"], "date": p["date"][:10],
            "category": next((c for c in cat_names if c), ""),
            "kculture": is_kc, "real_words": words, "stem": title_stem(p["title"]["rendered"]),
        })

    # 중복 클러스터
    stem_counts = Counter(r["stem"] for r in rows if r["stem"])
    dup_stems = {s for s, n in stem_counts.items() if n >= 3}

    THIN = 500  # 실제 산문 500단어 미만 = 얇음
    for r in rows:
        reasons = []
        if r["real_words"] < THIN:
            reasons.append(f"얇음({r['real_words']}w)")
        if r["stem"] in dup_stems:
            reasons.append(f"중복주제({stem_counts[r['stem']]}개)")
        r["reasons"] = reasons            # 품질 문제만 (K컬처는 정체성 별도 결정)
        r["kc_flag"] = r["kculture"]
        r["prune_score"] = (
            (THIN - r["real_words"] if r["real_words"] < THIN else 0)
            + (200 if r["stem"] in dup_stems else 0)
        )

    total = len(rows)
    kc = sum(1 for r in rows if r["kculture"])
    thin = sum(1 for r in rows if r["real_words"] < THIN)
    dup = sum(1 for r in rows if r["stem"] in dup_stems)
    candidates = [r for r in rows if r["reasons"]]   # 얇음/중복만
    candidates.sort(key=lambda r: r["prune_score"], reverse=True)

    print(f"총 발행글 {total}개")
    print(f"  테크 {total-kc} / K컬처 {kc}  (K컬처는 '정체성 분리' 별도 결정 — 자동 후보 아님)")
    print(f"  얇은 글(<{THIN}w 실산문) {thin}개")
    print(f"  중복 주제(어간 3+ 클러스터) {dup}개")
    print(f"  ▶ 품질 프루닝 후보(얇음 또는 중복) {len(candidates)}개\n")
    print("=== 상위 품질 프루닝 후보 (얇음/중복, 심각도순) ===")
    for r in candidates:
        kcm = " ·K컬처" if r["kc_flag"] else ""
        print(f"  #{r['id']} [{r['category']:<14}] {r['real_words']:>4}w | {', '.join(r['reasons'])}{kcm} | {r['title']}")

    out = Path(__file__).parent.parent / "tmp" / "prune_candidates.json"
    out.parent.mkdir(exist_ok=True)
    json.dump({"total": total, "tech": total - kc, "kculture": kc,
               "thin": thin, "dup": dup,
               "quality_candidates": candidates,
               "kculture_ids": [r["id"] for r in rows if r["kculture"]]},
              open(out, "w"), ensure_ascii=False, indent=1)
    print(f"\n전체 후보 목록: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
