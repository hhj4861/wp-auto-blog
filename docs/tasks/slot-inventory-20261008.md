# 정규 슬롯 실패의 구조 수정: 검증 재고 + 카테고리 대체 발행

- 목표/담당: Claude. 사용자 결정(2026-10-08): 재고 기반 전환 + 새는 관문 수정 먼저, PR #91(최신 이슈 필수화)은 보류(draft 전환·사유 코멘트).
- 기준: main c593d60. 작업 브랜치 `fix/slot-inventory-20261008`.

## 원인

- 이번 주 정규 슬롯 7회 중 1회 성공. 실패 6회 중 5회가 `selection held (no_candidate_passed)`: 슬롯 시각에 후보 3~9개만 평가하고 여러 관문을 연달아 모두 통과해야 하며, 0건 통과면 회차가 빈다.
- 후보 34개 탈락 내역: 공식 근거 검토(`source_missing_detail`/`category_mismatch`) 약 14, 검색 품질 판정 약 12, 보류 6(`missing_topic_suitability` 등).
- 미리 검증한 재고가 없다. 큐의 `pending` 19건 중 17건은 옛 형식이라 `fresh_market_item` 불통과. 사전 조사(07:30·16:30)는 그 회차 카테고리 하나의 보고서만 만든다.
- 9/28 이후 선정 실패 사례별 수정 PR 약 30개(#61~#90)에도 주별 슬롯 성공률은 2/7 → 5/14 → 9/14 → 1/7. 사례 단위 수정으로는 회차 공백을 막지 못한다.
- 정정: `native_search` 수집 실패는 이번 주 71회 중 6회(대부분 10/5 한 실행)로 주원인이 아니다. 검색 품질 탈락은 받은 결과에 대한 실제 판정이다. 이번 범위에서 수정하지 않는다.

## 변경

1. 재고 보충: `Blog Keyword Select` 예약을 03:00·07:00·13:00·16:00 KST `inventory` 모드로 변경. 재고가 빈 카테고리를 다가오는 3회차 순, 그다음 나머지 순으로 최대 2개(`SELECT_INVENTORY_LIMIT`) 탐색해 통과 주제를 큐에 적재·커밋. 모두 재고가 있으면 조사하지 않는다. 하나라도 적재하면 성공, 모두 보류면 실패로 표시.
2. 슬롯 소비: 예약 회차는 `pick_slot_category.py`로 회차 카테고리 재고를 먼저 쓴다. 없으면 기존처럼 즉석 탐색, 그것도 보류되면 다른 카테고리 중 점수가 가장 높은 신선 재고를 발행. 재고가 전혀 없을 때만 실패. 수동 실행(카테고리 명시)은 대체하지 않는다.
3. 기록: `scheduled_post_runs.json`의 `category`는 순환 그대로, 실제 발행 카테고리는 `published_category`.
4. `facets_list`: 심사 프롬프트에 `required_facets는 1~8개` 제한을 명시. 재시도 안내를 "인용 구절 번호 선택"에서 개수 안내로 교체하되 supported=false 핵심 질문을 빼거나 바꾸지 말라고 명시. 9개 이상을 잘라내 통과시키지 않는다.

## 불변 조건

- 재고도 발행 직전에 `fresh_market_item`(36시간·근거·적합성·우선순위)으로 다시 검증한다. 옛 형식 `pending`은 재고로 세지 않는다.
- 관문 기준은 완화하지 않았다. 통과율이 아니라 공백 회차를 줄이는 변경이다.
- 큐 적재는 재고가 0인 카테고리에서만 일어나므로 `enqueue_report`의 기존 `superseded` 처리로 신선 재고를 잃지 않는다.

## 검증

- 신규/수정 테스트: `tests/test_topic_inventory.py`(9), `test_codex_actions.py` 슬롯 셸 실행 5, `test_market_topics.py` 재고 CLI 3·워크플로 단언, `test_scheduled_post.py` 기록 2·워크플로 단언, `test_topic_suitability.py` 2. 모두 실패 확인 후 구현.
- 워크플로 셸 블록: `bash -n` 통과, 가짜 `python`으로 재고 있음 / 대체 발행 / 재고 없음 3경로 실행 확인.
- 실제 큐로 `pick_slot_category.py --preferred 테크` → `테크`(10/8 선정 `윈도우재설치`가 유효 재고).
- 전체 테스트(로컬 Python 3.11): 3,401개 중 23개 실패 → 이 중 4개는 슬롯 셸 블록을 옛 동작으로 고정한 `tests/test_codex_actions.py` 단언이어서 새 동작(재고 사용 / 대체 발행 / 재고 없음 실패)으로 교체, 해당 파일 35개 통과. 남은 19개(`test_main.py` 13, `test_internal_links.py` 3, `test_codex_client.py` 2, `test_image_fetcher.py` 1)는 수정 전 코드에서도 동일하게 실패하는 기존 결함이다. 전체 테스트 통과라고 주장하지 않는다.

## 남은 것

- 운영 효과는 머지 후 실제 슬롯으로 확인해야 한다. Codex 호출은 재고가 빈 카테고리에서만 늘어나며 상한은 하루 최대 8개 카테고리 조사.
- 공식 근거 탐색이 주제와 무관한 공공·기업정보 페이지를 가져오는 문제(제안 3번)는 별도 작업.
- PR #91은 상시 주제 카테고리를 제외하는 범위로 재검토 필요.

## E2E 경로 (`mode=slot_test`)

- Codex 인증은 기본 브랜치의 `workflow_dispatch`/`schedule`에서만 허용되므로 Actions E2E는 머지 후에만 가능하다(인증 제한은 변경하지 않음).
- 수동 실행은 슬롯을 claim하지 않아 기존 경로를 탄다. `workflow_dispatch` 입력은 이미 10개 상한이므로 `mode`에 `slot_test`를 추가했다. post-queue 잡만 반응하며, 회차 기록 없이 예약 회차와 같은 재고 사용 → 즉석 탐색 → 다른 카테고리 대체 경로를 `category` 입력으로 실행한다. `publish=false`면 `--dry-run`이라 WordPress 클라이언트를 만들지 않는다.

## E2E에서 발견한 결함: 중복 재고 (2026-10-08)

- `slot_test` 생활정보(37753649624): 생활정보 재고 없음 → 즉석 조사 보류 → 테크 대체 선택까지 의도대로 진행했다. 그런데 테크의 유일한 재고 `윈도우재설치`가 같은 날 함께 선정된 `윈도우11설치` 글과 겹쳐 작성 단계에서 `skipped_duplicate`가 됐고, `No fresh verified market topic`으로 실패했다(artifact `pipeline.log` 09:17:55~09:18:10).
- 원인: 재고 판정(`fresh_market_item`)은 WordPress 기존 글과의 중복을 보지 않고, 중복 검사는 작성 직전에만 한다. 함께 선정된 후보는 1위가 발행되면 중복이 된다.
- 수정: `pick_slot_category.py`와 재고 보충의 재고 집계에 작성 단계와 같은 `existing_titles` + `duplicate` 검사를 적용했다. 중복 재고는 재고로 세지 않고, 대체 카테고리로도 고르지 않는다.
