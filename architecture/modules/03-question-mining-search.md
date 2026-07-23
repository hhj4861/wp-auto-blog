# 질문 마이닝 검색 모듈 설계 (Question Mining / Demand-Signal Search)

> 상태: **설계만 — 구현 보류.** 착수 조건은 §7 참조.
> 작성: 2026-07-23 · 관련: `src/trend_detector.py`, `src/keyword_gate.py`, `data/topic_queue_general.json`

## 0. 한 줄 요약

"내가 추측한 토픽"이 아니라 "사람들이 지금 실제로 묻는 질문"을 외부 소스에서
**읽기 전용**으로 긁어와, 기존 키워드 게이트를 통과한 것만 발행 큐에 넣는 별도 모듈.
알파남류 영상의 유일하게 정당한 알맹이(수요 예측)를 정책 안전하게 코드화한 것.

**핵심 경계: 읽기(질문 수집)만 한다. 쓰기(지식인 답변·링크 도배)는 절대 하지 않는다.**
자동 답변/백링크 도배는 네이버 약관·검색 스팸 위반이며 이 모듈의 범위 밖이다.

---

## 1. 왜 별도 모듈인가

현재 `trend_detector.py`는 트렌드(HN·Reddit·Google Trends) → LLM 재랭킹으로
"화제성" 토픽을 뽑는다. 질문 마이닝은 성격이 다르다:

| | 기존 trend_detector | 질문 마이닝(신규) |
|---|---|---|
| 신호 | 지금 뜨는 화제 | 지금 반복되는 **질문(검색 의도)** |
| 출처 | HN/Reddit 인기글 | 지식인 Q&A, Reddit 질문, PAA |
| 산출 | 토픽 후보 | 질문 원문 + 파생 키워드 |
| 소비처 | 큐 topic | 큐 topic **+ FAQ 실제 질문** |

trend_detector에 끼워 넣어도 되지만, (a) 소스 파싱 로직이 무겁고, (b) FAQ 주입이라는
별도 소비처가 있고, (c) 향후 온사이트 검색·PAA 확장 여지가 있어 **독립 모듈**이 깔끔하다.

권장 위치: `src/question_miner.py` (신규). trend_detector와 동급, keyword_gate에 의존.

---

## 2. 데이터 흐름

```
[소스 어댑터]  →  [정규화]  →  [키워드 게이트]  →  [큐 append]  →  [FAQ 주입]
 지식인 Q&A        질문 문장     keyword_gate       go/longtail만    content_generator
 Reddit 질문       + 명사구 추출  .evaluate()        큐에 저장         FAQ 프롬프트에
 (PAA 확장)                     (검색량+SERP)      source_questions  실제 질문 사용
                                                    필드 부착
```

핵심 재사용: **판정은 새로 만들지 않는다.** 이미 있는 `keyword_gate.evaluate(topic, keywords)`가
네이버 검색광고 월간검색량 + DuckDuckGo SERP 정부·대형매체 점유율로 go/longtail/skip을
돌려주므로, 마이닝된 질문을 그냥 이 함수에 통과시키면 저수요·레드오션은 자동 탈락한다.

---

## 3. 소스 어댑터 (읽기 전용)

각 소스는 `fetch_questions() -> list[MinedQuestion]` 인터페이스만 지킨다.
공통 반환 타입:

```python
@dataclass
class MinedQuestion:
    question: str          # 원문 질문 (예: "건강검진 안 받으면 과태료 나오나요?")
    source: str            # "naver_kin" | "reddit" | "paa"
    source_url: str        # 출처 URL (추적용, 게시 안 함)
    category_hint: str = "" # 소스 카테고리 → 우리 카테고리 매핑 힌트
```

### 3-1. 네이버 지식인 (주력)

- **대상 메뉴** (영상2에서 지목한 4곳):
  - `많이 본 Q&A` — 실검 수요 프록시
  - `답변을 기다리는 질문` — 미충족 수요(경쟁 낮음 신호)
  - `명예의 전당` — 반복 고빈도 질문
  - `추천 Q&A`
- **대상 분야**: 우리 3축과 겹치는 것만 — 경제/세금, 취업, 건강(단 YMYL 주의 §6)
- **구현**: `kin.naver.com` 카테고리 목록 페이지를 `requests` + 정규식/BeautifulSoup로
  파싱해 **질문 제목만** 수집. 공식 API 없음 → HTML 파싱.
  - `User-Agent` 브라우저 위장 (기존 `_BROWSER_UA` 재사용)
  - robots.txt 준수, 요청 간 1~2초 슬립, 페이지당 상한
  - **답변 폼 접근·작성 코드 절대 없음** (읽기 전용 강제)
- **주의**: 지식인은 스크래핑 방어가 있을 수 있음. DuckDuckGo SERP처럼
  차단 시 재시도 + 실패 시 빈 리스트(파이프라인 비차단) 원칙.

### 3-2. Reddit (이미 자격증명 있음)

- `config.py`에 `reddit_client_id/secret` 이미 존재, `trend_detector._setup_reddit`에
  praw 셋업 완료. 이걸 재사용.
- **차이**: 기존은 인기 "글"을 봤다면, 여기선 제목이 **의문문**인 것(`?`, "how", "why",
  "왜", "어떻게")만 필터. 서브레딧: bytepulse(영문) 쪽 K-Beauty/K-Pop/AI 관련.
- trendpulse(한국어)에는 Reddit 적합도 낮음 → 지식인 우선.

### 3-3. Google PAA (People Also Ask) — 확장 후순위

- 큐의 head_keyword를 구글에 검색해 "사람들이 많이 묻는 질문" 박스를 파싱.
- 구글 SERP 스크래핑은 차단됨(이미 확인) → DuckDuckGo엔 PAA 없음.
  SerpAPI 등 유료 필요 → **후순위, 지금은 설계만**.

---

## 4. 큐 통합

마이닝 → 게이트 통과분을 `data/topic_queue_general.json`에 append.
**기존 스키마에 필드 2개만 추가**(하위 호환):

```jsonc
{
  "topic": "건강검진 미수검 과태료, 얼마이고 누가 내나 (2026)",  // 질문→제목 변환
  "keywords": ["건강검진 과태료", "미수검", ...],
  "category": "건강",
  "status": "pending",
  "monthly_search": 3200, "competition": "낮음",
  "serp_gov_ratio": 0.2, "verdict": "go", "head_keyword": "건강검진 과태료",
  // ↓ 신규
  "source": "naver_kin",                     // 출처 추적
  "source_questions": [                       // FAQ 주입용 실제 질문 원문
    "건강검진 안 받으면 과태료 나오나요?",
    "직장 건강검진 안 받으면 회사가 벌금 내나요?"
  ]
}
```

- 질문 → 제목 변환은 `score_queue.py`의 `longtail_title()` 패턴 재사용(자연스러운 제목화).
- 중복 방지: 기존 큐/레지스트리의 head_keyword와 대조(이미 있는 중복 로직 활용).
- **일일 유입 상한**(예: 소스당 5건)으로 큐 폭주 방지 — 대량발행 금지 원칙과 일관.

---

## 5. FAQ 주입 (이 모듈의 차별적 가치)

현재 FAQ는 LLM이 지어낸 질문(`content_generator.py` 프롬프트 "3-4개 실용 질문").
→ 실제 검색 쿼리와 안 맞아 PAA 리치리절트 확률이 낮다.

**개선**: 큐 아이템에 `source_questions`가 있으면, `content_generator`의 FAQ 프롬프트에
그 실제 질문을 주입 → LLM은 답만 작성. 그러면 `monetization.build_faq_schema()`(이미 구현됨)가
실제 쿼리 기반 FAQPage JSON-LD를 생성 → 구글 PAA 박스 노출 확률 상승.

연결점: `content_generator.generate()`가 큐 아이템의 `source_questions`를 받도록
시그니처 확장 → FAQ 섹션 프롬프트에 `"다음 실제 질문에 답하라: {source_questions}"` 주입.

---

## 6. 정책·안전 가드레일 (코드로 강제)

[[guardrails-in-code]] 원칙에 따라 프롬프트가 아니라 코드로:

1. **읽기 전용**: 어떤 소스 어댑터도 POST/답변/댓글 API를 호출하지 않는다.
   (링크 도배 = 알파남식 스팸, 명시적 기각)
2. **게이트 필수 통과**: 마이닝 질문도 `keyword_gate.evaluate()` 없이는 큐에 못 들어감.
3. **YMYL 필터**: 지식인 건강/의료 질문 중 진단·치료·약물 상호작용성("A약 먹고 B약 먹어도
   되나요")은 **제외**. 우리는 "지원 제도·신청·과태료"성 생활정보만 다룸.
   → `keyword_gate`에 medical-advice 차단 정규식 추가 또는 마이닝 단계 사전 필터.
4. **저작권**: 질문 "제목/주제"만 신호로 쓰고, 지식인 답변 본문을 복사하지 않는다.
   (글은 우리 파이프라인이 공식 출처 그라운딩으로 새로 작성)
5. **일일 상한**: 대량발행 금지와 일관되게 소스당·일일 유입 상한.

---

## 7. 착수 조건 (지금 구현하지 않는 이유)

**지금 병목은 소재가 아니라 색인이다.** 큐엔 이미 60건(~10주) 검증 대기 중이고,
색인 ≈ 0인 상태에선 소재를 더 파도 구글에 안 보인다. 효과 측정도 불가(트래픽 0).

**착수 트리거** (아래 중 하나 충족 시):
- GSC 색인 페이지 수가 유의미하게 증가(예: 20건+ 색인) → 소재 다양화 가치 발생
- GSC 노출 데이터로 "어떤 유형이 노출되나" 파악 → 질문형 소재 필요성 검증됨
- 큐 잔량이 3주 미만으로 감소 → 소재 보충 필요

그 전까지는 이 문서만 유지. 착수 시 §2 흐름대로 `src/question_miner.py` 신설 →
지식인 어댑터 먼저(주력) → 게이트 통과 → 큐 append → FAQ 주입 순.

---

## 8. 구현 체크리스트 (착수 시)

- [ ] `src/question_miner.py`: `MinedQuestion` 데이터클래스 + 어댑터 인터페이스
- [ ] 네이버 지식인 read-only fetcher (4개 메뉴, HTML 파싱, 슬립/재시도)
- [ ] Reddit 질문 필터 (기존 praw 셋업 재사용, 의문문만)
- [ ] 질문 → keyword_gate.evaluate() → go/longtail만 통과
- [ ] 질문 → 제목 변환(longtail_title 패턴) + 중복 대조 + 큐 append
- [ ] 큐 스키마 `source`/`source_questions` 필드 (하위 호환)
- [ ] content_generator FAQ 프롬프트에 source_questions 주입
- [ ] YMYL·읽기전용·일일상한 가드레일 (코드, 유닛 테스트)
- [ ] 별도 워크플로 `.github/workflows/mine-questions.yml` (주 1~2회, dry_run 지원)
- [ ] 소스 차단·실패 시 파이프라인 비차단 확인
