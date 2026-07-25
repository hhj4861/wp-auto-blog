# commerce-automation-kit 키워드 브릿지 (소비자 측)

commerce-automation-kit(`~/workSpace/commerce-automation-kit`, TypeScript)의
`keyword-intel` 원자가 생산하는 키워드/질문 시그널을, 이 저장소(Python)의
발행 큐로 받아오는 **단방향 데이터 브릿지**의 소비자 구현이다.

설계 원본:
- 소비자(여기): `architecture/modules/03-question-mining-search.md` §4/§8
- 생산자(kit): `packages/keyword-intel/docs/QUESTION-MINING.md` §8

## 왜 코드 통합이 아니라 브릿지인가 (ADR 요약)

kit의 `QUESTION-MINING.md §2` ADR이 "wp-auto-blog까지 코드 통합"을 **기각**했다:
언어 경계(TS↔Python), 컴플라이언스 체제 상충(kit=silent-drop 금지 / 블로그=fail-open),
kit엔 콘텐츠 생성 원자 없음(범위 밖). 따라서 **kit에 블로그 모듈을 만들지 않고**,
블로그가 kit의 export를 소비만 한다. 두 저장소는 서로 다른 법체계로 분리 유지한다.

## 데이터 흐름 (단방향, 엄격→느슨)

```
keyword-intel (kit, 생산)
  └─ analyze --profile blog-kr --json  (schemaVersion + compliance 포함 export)
        │  (파일 전달 — HTTP/DB 직접연결 아님. 코드·저장·게이트 통합 금지)
        ▼
scripts/ingest_keyword_intel.py (이 저장소, 소비)
  └─ data/topic_queue_general.json 에 source="cak_keyword_intel" pending append
        ▼
python -m src.main --mode general --from-queue
  └─ dedup(_is_duplicate) + keyword_gate.evaluate() 재통과 → 발행
```

## 소비자가 강제하는 거버넌스 의무 (코드로)

| 의무 | 구현 |
|---|---|
| schemaVersion·compliance 필수·타입검증 | `validate_export()` — 누락/타입위반 시 `IngestError`로 거부(cacheTtlHours는 양의 정수) |
| **재표현 보수모드 상시** (질문 원문 비저장) | `build_queue_item()` — `source_questions`를 **절대 큐에 싣지 않음**. 파이프라인이 소비하지도 않으므로 저장=부채. 이걸 저장 배제로 강제 |
| **항목 삭제 없음** (topic 등 가공물 보존) | `purge_stale_questions()` — TTL 경과 시 legacy `source_questions` **필드만** 제거, 항목은 유지(§8 "가공물은 유지") |
| dedup 유지 (재작성 안 함) | 큐 중복(completed·pending 모두)을 정규화 비교로 차단, 하드 게이트는 발행 시 파이프라인 |
| 게이트 재통과 | `--from-queue` 발행 경로가 `keyword_gate.evaluate()` 자동 재실행 |
| 네이티브 항목 보호 | purge/삭제는 `source=="cak_keyword_intel"`만 대상, 블로그 자체 항목 불가침 |
| 배치 견고성 | null/숫자/빈 topic은 항목만 스킵(배치 전체를 죽이지 않음), 큐가 list 아니면 거부 |

### 왜 verbatim(질문 원문) 저장을 안 하나

발행 파이프라인(`run_single`)은 `topic/keywords/category`만 소비한다 —
`source_questions`는 어디서도 읽히지 않는다. 따라서 큐에 원문을 저장하면
기능 이득은 0이고 "제3자 질문 원문이 수신측 저장소에 남는" 컴플라이언스
부채만 생긴다(§8이 TTL purge를 요구하는 바로 그 대상). 그래서 **저장 자체를
배제**해 §8 재표현 게이트를 가장 강한 형태(never-persist)로 만족시킨다.
verbatim이 실제로 필요한 건 FAQ 주입 소비자가 생길 때이며, 그건 전용
하드-TTL 저장소 + 발행시점 purge 훅과 함께 별도 설계해야 한다(현재 범위 밖).

## 사용법

```bash
# 질문 원문 미저장, 재표현된 topic + 파생지표만 큐로 (상시 보수모드)
python scripts/ingest_keyword_intel.py <export.json>

# 환경변수로 경로 지정
CAK_KEYWORD_INTEL_EXPORT=/path/export.json python scripts/ingest_keyword_intel.py
```

export 계약 예시: `data/cak_export.sample.json`.

## 착수 상태 / 주의

- **소비자만 구현됨. 생산자(kit `analyze --profile blog-kr --json`)는 미구현**
  — kit CLI의 `analyze`는 현재 사람용 표(console.table)만 출력하며 `--json` 없음.
  이 브릿지가 실제 흐르려면 kit 측 export 구현이 필요하다(별도 저장소 작업).
- 이 스크립트는 export 파일이 있고 **수동 실행할 때만** 동작한다.
  자동 발행(`auto-post.yml`)엔 배선하지 않았다 — 지금은 아무 발행 동작 변화 없음.
- 착수 트리거(§7): GSC 색인 20건+ / 큐 3주 미만 / GSC 노출 증거 중 하나.
  현재 병목은 소재가 아니라 색인이므로, 실사용은 색인 회복 후 권장.
