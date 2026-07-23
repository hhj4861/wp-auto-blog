#!/usr/bin/env python3
"""시즌성 토픽에 demand_peak / publish_by를 태깅한다.

색인 리드타임(신규 도메인 2~6주)을 고려해 수요 정점 약 6주 전을 publish_by로 잡는다.
main.py의 큐 선택이 이 필드를 읽어 '아직 시기 아님'은 뒤로, '시기 도래'는 최우선 처리.

키워드 매칭 기반이라 새 토픽이 들어와도 재실행하면 자동 태깅된다.
DRY_RUN=true면 대상만 출력.
"""

import json
import os
import re

QUEUE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "topic_queue_general.json")
DRY_RUN = (os.environ.get("DRY_RUN", "true").lower() != "false")

# (정규식, demand_peak, publish_by) — publish_by는 정점 약 6주 전
# 기준: 오늘 2026-07 이후의 정점만. 지난 것은 이듬해로 넘긴다.
SEASON_RULES = [
    (r"추석.*기차표|추석.*예매|기차표.*예매", "2026-09", "2026-08-10"),   # 추석 9월 하순, 예매 8월 말
    (r"종합소득세.*중간예납|중간예납",         "2026-11", "2026-10-01"),   # 11월 납부
    (r"연말정산.*미리보기|연말정산",           "2026-11", "2026-10-05"),   # 미리보기 10~11월
    (r"연금저축.*세액공제|IRP.*세액공제|세액공제.*환급", "2026-12", "2026-10-25"),  # 연말정산 대비
    (r"자동차세.*연납",                       "2027-01", "2026-12-10"),   # 1월 연납 신청
    (r"양도소득세.*신고|해외주식.*양도",       "2027-05", "2027-04-01"),   # 5월 신고
    (r"독감.*예방접종|인플루엔자.*접종",       "2026-10", "2026-09-01"),   # 가을 접종
]


def main():
    with open(QUEUE_PATH, encoding="utf-8") as f:
        queue = json.load(f)

    tagged = 0
    for item in queue:
        if item.get("status") != "pending":
            continue
        topic = item.get("topic", "")
        for pattern, peak, pub_by in SEASON_RULES:
            if re.search(pattern, topic):
                if item.get("publish_by") == pub_by and item.get("demand_peak") == peak:
                    break
                item["demand_peak"] = peak
                item["publish_by"] = pub_by
                tagged += 1
                print(f"  [{item.get('category','')[:4]:4}] {topic[:42]:44} "
                      f"→ 정점 {peak}, 발행 {pub_by}")
                break

    print(f"\n시즌 태깅: {tagged}건")
    if DRY_RUN:
        print("DRY_RUN — 변경 없음")
        return
    with open(QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)
    print("큐 저장 완료")


if __name__ == "__main__":
    main()
