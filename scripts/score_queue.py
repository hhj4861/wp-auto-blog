#!/usr/bin/env python3
"""토픽 큐를 수요·경쟁으로 재점수화한다.

각 pending 항목에 monthly_search / competition / serp_gov_ratio / verdict를 채우고,
verdict가 longtail인 항목은 파생 롱테일 토픽을 큐에 추가한 뒤 헤드 항목을
deferred(허브용 보류)로 내린다. 발행 순서는 go > longtail 파생 순으로 재정렬.

DRY_RUN=true면 결과만 출력한다.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.keyword_gate import evaluate  # noqa: E402

QUEUE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "topic_queue_general.json")
DRY_RUN = (os.environ.get("DRY_RUN", "true").lower() != "false")
LIMIT = int(os.environ.get("SCORE_LIMIT", "0"))  # 0 = 전체

# 롱테일 파생 토픽 제목 템플릿 (키워드 → 사람이 읽는 제목)
def longtail_title(keyword: str, base_category: str) -> str:
    """키워드를 자연스러운 제목으로. 키워드에 이미 있는 말을 덧붙이지 않는다."""
    kw = keyword.strip()
    has = lambda *words: any(w in kw for w in words)  # noqa: E731

    if has("방법", "법"):
        suffix = "총정리: 단계별 안내 (2026)"
    elif has("조회", "확인"):
        suffix = "방법 총정리 (2026)"
    elif has("신청"):
        suffix = "방법과 준비 서류 총정리 (2026)"
    elif has("조건", "대상", "자격"):
        suffix = "총정리: 나도 해당될까? (2026)"
    elif has("계산기", "계산"):
        suffix = "사용법과 실제 예시 (2026)"
    elif has("금액", "얼마"):
        suffix = "기준과 계산 예시 (2026)"
    elif has("기간", "일정"):
        suffix = "총정리와 놓쳤을 때 대처법 (2026)"
    else:
        suffix = "총정리 (2026)"
    return f"{kw} {suffix}"


def main():
    with open(QUEUE_PATH, encoding="utf-8") as f:
        queue = json.load(f)

    pending = [i for i in queue if i.get("status") == "pending" and "verdict" not in i]
    if LIMIT:
        pending = pending[:LIMIT]
    print(f"재점수화 대상: {len(pending)}건 (DRY_RUN={DRY_RUN})\n{'=' * 70}")

    new_items = []
    stats = {"go": 0, "longtail": 0, "skip": 0, "unknown": 0}

    for idx, item in enumerate(pending, 1):
        kws = item.get("keywords") or []
        r = evaluate(item["topic"], kws)
        v = r["verdict"]
        stats[v] += 1

        item["monthly_search"] = r["monthly"]
        item["competition"] = r["comp"]
        item["serp_gov_ratio"] = (round(r["gov_ratio"], 2)
                                  if r["gov_ratio"] is not None else None)
        item["verdict"] = v
        item["head_keyword"] = r["head_keyword"]

        tag = {"go": "✅", "longtail": "🔀", "skip": "⛔", "unknown": "❔"}[v]
        print(f"{idx:3}. {tag} [{item.get('category','')[:4]:4}] {item['topic'][:38]:40} "
              f"월{r['monthly']:>8,} {r['reason'][:42]}")

        if v == "longtail":
            # 헤드는 보류하고 롱테일 파생 3건을 큐에 추가
            item["status"] = "deferred_head"
            for lt in r["longtails"][:3]:
                title = longtail_title(lt["keyword"], item.get("category", ""))
                new_items.append({
                    "topic": title,
                    "keywords": [lt["keyword"]] + kws[:3],
                    "category": item.get("category", "생활정보"),
                    "status": "pending",
                    "monthly_search": lt["monthly"],
                    "competition": lt["comp"],
                    "verdict": "go",
                    "derived_from": item["topic"],
                })
                print(f"      └ 파생: {title[:44]:46} 월{lt['monthly']:>7,}")
        elif v == "skip":
            item["status"] = "skipped_low_demand"

        time.sleep(1.2)  # DDG·네이버 API 레이트리밋 회피

    # 발행 순서 재정렬: 검색량 큰 go 항목 우선
    done = [i for i in queue if i.get("status") not in ("pending",)]
    pend = [i for i in queue if i.get("status") == "pending"] + new_items
    pend.sort(key=lambda i: -(i.get("monthly_search") or 0))
    result = done + pend

    print(f"\n{'=' * 70}")
    print(f"판정: go {stats['go']} / 롱테일 우회 {stats['longtail']} / "
          f"저수요 제외 {stats['skip']} / 미확인 {stats['unknown']}")
    print(f"파생 토픽 추가: {len(new_items)}건 → pending 총 {len(pend)}건")
    print("\n발행 예정 상위 10건:")
    for i in pend[:10]:
        print(f"  [{i.get('category','')[:4]:4}] {i['topic'][:46]:48} "
              f"월{(i.get('monthly_search') or 0):>8,}")

    if DRY_RUN:
        print("\nDRY_RUN — 큐 변경 없음. 적용하려면 DRY_RUN=false")
        return
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\n큐 저장 완료")


if __name__ == "__main__":
    main()
