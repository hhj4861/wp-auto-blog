---
project: wp-auto-blog
created: 2026-01-02
version: 1.0
status: draft
type: prd
---

# PRD: 워드프레스 자동 블로그 파이프라인

## 1. 제품 개요

### 1.1 제품 비전

> **AI 기반 자동화로 패시브 인컴을 창출하는 블로그 시스템**

수동 블로그 운영의 시간적 제약을 해결하고, 트렌드 감지부터 발행까지 자동화하여 1인 운영자가 월 100만원+ 수익을 달성할 수 있는 파이프라인.

### 1.2 핵심 가치 제안

| 기존 방식 | 우리 솔루션 |
|----------|------------|
| 글당 2-3시간 소요 | 글당 5분 검수 |
| 트렌드 수동 모니터링 | 자동 감지 + 알림 |
| 일관성 유지 어려움 | 자동 스케줄 발행 |
| 월 10-20개 한계 | 월 30-50개 가능 |

### 1.3 성공 지표

| 지표 | 목표 | 측정 |
|------|------|------|
| **월 발행량** | 30개+ | WordPress 통계 |
| **글당 검수 시간** | 5분 이하 | 시간 측정 |
| **8개월 월 수익** | $900+ | 애드센스 리포트 |
| **자동화율** | 80%+ | 수동 개입 비율 |

---

## 2. 사용자 정의

### 2.1 타겟 사용자

```yaml
Primary_Persona:
  이름: 테크 블로거 Kim
  역할: 1인 개발자/콘텐츠 크리에이터
  목표: 본업 외 패시브 인컴 구축
  Pain_Points:
    - 블로그 운영할 시간 부족
    - 트렌드 놓치면 트래픽 급감
    - 글쓰기 일관성 유지 어려움
  기술_수준: Python 기초 가능
```

### 2.2 사용자 저니

```
[트렌드 발생] → [자동 감지] → [AI 글 생성] → [검수 알림]
                                                  ↓
[수익 발생] ← [트래픽 유입] ← [SEO 인덱싱] ← [발행/수정]
```

---

## 3. 기능 요구사항

### 3.1 핵심 기능 (P0 - Must Have)

#### FR-001: 트렌드 감지

| 항목 | 상세 |
|------|------|
| **설명** | 핫 토픽 자동 수집 및 필터링 |
| **소스** | Google Trends, Hacker News, Reddit |
| **빈도** | 일 2-3회 (6시, 12시, 18시) |
| **필터** | 니치 관련성, 검색량, 경쟁도 |
| **출력** | 토픽 리스트 (제목, 키워드, 점수) |

```python
# 예시 출력
{
  "topic": "Claude 3.5 Sonnet Released",
  "keywords": ["claude 3.5", "sonnet", "anthropic"],
  "source": "hacker_news",
  "score": 85,
  "suggested_title": "Claude 3.5 Sonnet Review: Everything You Need to Know"
}
```

#### FR-002: 콘텐츠 생성

| 항목 | 상세 |
|------|------|
| **설명** | AI 기반 블로그 글 생성 |
| **입력** | 토픽, 타겟 키워드, 글 유형 |
| **LLM** | Gemini Flash (기본), GPT-4o-mini (백업) |
| **출력** | HTML 형식 완성 글 |
| **품질** | 1,500-2,500 단어, SEO 구조 |

```yaml
글_유형:
  - review: 도구 리뷰
  - comparison: A vs B 비교
  - guide: How-to 가이드
  - list: Best X tools 리스트
  - news: 뉴스 분석

필수_포함:
  - H1 제목 (키워드 포함)
  - H2/H3 구조 (5개+ 섹션)
  - 목차 (Table of Contents)
  - FAQ 섹션 (3개+)
  - 메타 설명 (150-160자)
```

#### FR-003: 이미지 추가

| 항목 | 상세 |
|------|------|
| **설명** | 관련 이미지 자동 첨부 |
| **소스** | Unsplash API (기본), Pexels (백업) |
| **수량** | 글당 3-5개 |
| **출력** | 이미지 URL + Alt 텍스트 |
| **위치** | Featured Image + 본문 삽입 |

#### FR-004: 품질 검증

| 항목 | 상세 |
|------|------|
| **설명** | 발행 전 자동 품질 체크 |
| **체크 항목** | 글자 수, 키워드 밀도, 중복, 구조 |
| **결과** | Pass/Fail + 상세 피드백 |
| **임계값** | 아래 표 참조 |

```yaml
품질_기준:
  word_count:
    min: 1500
    target: 2000
  keyword_density:
    min: 0.5%
    max: 2.5%
  headings:
    h2_min: 4
    h3_min: 2
  images:
    min: 3
  internal_links:
    min: 2
  external_links:
    min: 1
```

#### FR-005: WordPress 발행

| 항목 | 상세 |
|------|------|
| **설명** | 완성 글 자동 포스팅 |
| **API** | WordPress REST API |
| **인증** | Application Password |
| **기본 상태** | Draft (검수 대기) |
| **메타데이터** | 카테고리, 태그, Featured Image |

```yaml
발행_옵션:
  auto_draft: true  # 기본값
  auto_publish: false  # 검수 후 수동 발행
  schedule: null  # 또는 예약 시간

category_mapping:
  ai_tools: 3
  productivity: 5
  coding: 7

tag_extraction: auto  # 키워드에서 자동 추출
```

#### FR-006: 알림

| 항목 | 상세 |
|------|------|
| **설명** | 작업 완료/에러 알림 |
| **채널** | 이메일 (기본), Slack (선택) |
| **트리거** | 글 생성 완료, 발행 완료, 에러 발생 |
| **내용** | 글 제목, 링크, 상태, 에러 로그 |

---

### 3.2 부가 기능 (P1 - Should Have)

#### FR-007: 대시보드 (CLI)

```yaml
설명: 파이프라인 상태 모니터링
기능:
  - 오늘 처리된 토픽 리스트
  - 발행된/대기 중인 글 수
  - 에러 로그 조회
  - 수동 실행 트리거
인터페이스: CLI (Python)
```

#### FR-008: 프롬프트 관리

```yaml
설명: 글 유형별 프롬프트 템플릿 관리
기능:
  - 템플릿 CRUD
  - 변수 치환 ({{topic}}, {{keywords}})
  - 버전 관리
저장: YAML 파일
```

#### FR-009: 키워드 캐싱

```yaml
설명: 중복 토픽 방지 및 API 최적화
기능:
  - 최근 발행 키워드 저장
  - 유사도 체크 (70% 이상 = 중복)
  - 캐시 만료 (30일)
저장: JSON 또는 SQLite
```

---

### 3.3 향후 기능 (P2 - Nice to Have)

| 기능 | 설명 | 예상 시기 |
|------|------|----------|
| 웹 대시보드 | Streamlit 기반 UI | Phase 3 |
| 다중 블로그 | 여러 WP 사이트 관리 | Phase 3 |
| 성과 분석 | GA4 연동, RPM 추적 | Phase 3 |
| 자동 업데이트 | 오래된 글 자동 갱신 | Phase 4 |
| A/B 테스트 | 제목/메타 테스트 | Phase 4 |

---

## 4. 비기능 요구사항

### 4.1 성능 (Performance)

| 항목 | 요구사항 |
|------|----------|
| 트렌드 수집 | 5분 이내 |
| 글 생성 | 2분 이내/글 |
| 이미지 수집 | 30초 이내/글 |
| 전체 파이프라인 | 10분 이내/글 |

### 4.2 안정성 (Reliability)

| 항목 | 요구사항 |
|------|----------|
| 가동률 | 99% (일 14분 이하 다운타임) |
| 에러 복구 | 자동 재시도 3회 |
| 데이터 백업 | 일 1회 (설정 파일) |
| 로깅 | 모든 작업 기록, 7일 보관 |

### 4.3 비용 (Cost)

| 항목 | 한도 |
|------|------|
| AI API | $1/월 이하 |
| 파이프라인 서버 | $5/월 이하 |
| 총 운영비 | $25/월 이하 |

### 4.4 보안 (Security)

```yaml
필수:
  - API 키: 환경변수 저장 (.env)
  - WP 인증: Application Password (별도 계정)
  - Git: .env 제외 (.gitignore)

권장:
  - 파이프라인 서버: SSH 키 인증
  - 로그: 민감정보 마스킹
```

---

## 5. 시스템 아키텍처

### 5.1 컴포넌트 다이어그램

```
┌─────────────────────────────────────────────────────────────────────┐
│                         wp-auto-blog                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐           │
│  │   Trend     │     │   Content   │     │   Image     │           │
│  │  Detector   │────▶│  Generator  │────▶│  Fetcher    │           │
│  └─────────────┘     └─────────────┘     └─────────────┘           │
│        │                   │                   │                    │
│        │                   │                   │                    │
│        ▼                   ▼                   ▼                    │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐           │
│  │   Google    │     │   OpenAI    │     │  Unsplash   │           │
│  │   Trends    │     │   Gemini    │     │   Pexels    │           │
│  │   HN API    │     │             │     │             │           │
│  │   Reddit    │     │             │     │             │           │
│  └─────────────┘     └─────────────┘     └─────────────┘           │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      Quality Checker                        │   │
│  │   [Word Count] [Keywords] [Structure] [Duplicates]          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     WordPress Client                         │   │
│  │   [Posts API] [Media API] [Categories] [Tags]               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                       Notifier                               │   │
│  │   [Email] [Slack (optional)]                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                       Scheduler                              │   │
│  │   [Cron] or [schedule library]                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.2 데이터 흐름

```
1. Scheduler 트리거 (일 2-3회)
   │
2. TrendDetector.collect()
   │ → Google Trends API
   │ → Hacker News API
   │ → Reddit API
   │ → 필터링 + 점수화
   │ → 상위 N개 토픽 선정
   │
3. for each topic:
   │
   ├─ ContentGenerator.generate(topic)
   │   │ → 프롬프트 템플릿 로드
   │   │ → LLM API 호출
   │   │ → HTML 콘텐츠 생성
   │   │
   ├─ ImageFetcher.fetch(keywords)
   │   │ → Unsplash 검색
   │   │ → 이미지 URL + Alt 수집
   │   │
   ├─ QualityChecker.check(content)
   │   │ → 글자 수, 키워드, 구조 검증
   │   │ → Pass/Fail 판정
   │   │
   ├─ if Pass:
   │   │ WordPressClient.create_post(content, images)
   │   │ → 미디어 업로드
   │   │ → Draft 포스트 생성
   │   │
   └─ Notifier.send(result)
       → 이메일/Slack 알림
```

---

## 6. 기술 스택

### 6.1 확정 기술

| 카테고리 | 기술 | 버전 | 비고 |
|----------|------|------|------|
| **언어** | Python | 3.11+ | 타입 힌트 사용 |
| **HTTP** | requests | 2.31+ | API 호출 |
| **트렌드** | pytrends | 4.9+ | Google Trends |
| **Reddit** | praw | 7.7+ | Reddit API |
| **AI** | openai | 1.12+ | GPT-4o-mini |
| **AI** | google-generativeai | 0.3+ | Gemini Flash |
| **환경변수** | python-dotenv | 1.0+ | .env 관리 |
| **로깅** | loguru | 0.7+ | 구조화 로깅 |
| **스케줄** | schedule | 1.2+ | 또는 Cron |

### 6.2 프로젝트 구조

```
wp-auto-blog/
├── src/
│   ├── __init__.py
│   ├── config.py              # 설정 관리
│   ├── trend_detector.py      # 트렌드 감지
│   ├── content_generator.py   # AI 콘텐츠 생성
│   ├── image_fetcher.py       # 이미지 수집
│   ├── quality_checker.py     # 품질 검증
│   ├── wordpress_client.py    # WP API 클라이언트
│   ├── notifier.py            # 알림
│   ├── scheduler.py           # 스케줄러
│   └── main.py                # 진입점
├── templates/
│   └── prompts/
│       ├── review.yaml
│       ├── comparison.yaml
│       ├── guide.yaml
│       └── list.yaml
├── data/
│   ├── cache/                 # 키워드 캐시
│   └── logs/                  # 로그 파일
├── tests/
│   ├── test_trend_detector.py
│   ├── test_content_generator.py
│   └── ...
├── .env.example
├── .gitignore
├── requirements.txt
├── setup.py
└── README.md
```

---

## 7. 개발 로드맵

### Phase 1: MVP 테스트 (현재 - 5주)

```yaml
목표: 애드센스 승인 획득

산출물:
  - 20개 수동 작성 글
  - WordPress 설정 완료
  - Google 도구 연동

담당: 사용자 (수동)
```

### Phase 2: 자동화 v1 (Week 3-5)

```yaml
목표: 기본 파이프라인 구축

기능:
  - FR-001 트렌드 감지
  - FR-002 콘텐츠 생성
  - FR-003 이미지 추가
  - FR-005 WordPress 발행

산출물:
  - 작동하는 파이프라인
  - CLI 실행 가능

예상_기간: 2주
```

### Phase 3: 자동화 v2 (Week 6-8)

```yaml
목표: 품질 강화 + 스케줄링

기능:
  - FR-004 품질 검증
  - FR-006 알림
  - FR-007 대시보드 (CLI)
  - 스케줄러 연동

산출물:
  - 자동 실행 파이프라인
  - 주 7회 자동 발행

예상_기간: 2주
```

### Phase 4: 최적화 (Month 3+)

```yaml
목표: 효율화 + 확장

기능:
  - 프롬프트 튜닝
  - 성과 분석 연동
  - 다중 블로그 지원 (선택)

예상_기간: 지속적
```

---

## 8. 테스트 계획

### 8.1 단위 테스트

| 모듈 | 테스트 케이스 |
|------|--------------|
| TrendDetector | API 연결, 필터링, 점수화 |
| ContentGenerator | 프롬프트 로드, LLM 호출, HTML 생성 |
| ImageFetcher | API 연결, 이미지 검색, URL 추출 |
| QualityChecker | 각 기준별 Pass/Fail |
| WordPressClient | 인증, 포스트 생성, 미디어 업로드 |

### 8.2 통합 테스트

```yaml
E2E_시나리오:
  1. 트렌드 감지 → 토픽 1개 선정
  2. 콘텐츠 생성 → 1,500+ 단어 확인
  3. 이미지 추가 → 3개+ 이미지
  4. 품질 검증 → Pass
  5. WordPress 발행 → Draft 생성 확인
  6. 알림 → 이메일 수신 확인
```

### 8.3 수동 테스트

| 테스트 | 빈도 | 담당 |
|--------|------|------|
| 글 품질 검수 | 매 발행 | 사용자 |
| SEO 최적화 확인 | 주 1회 | 사용자 |
| 트래픽 모니터링 | 일 1회 | 사용자 |

---

## 9. 리스크 및 대응

### 9.1 기술 리스크

| 리스크 | 확률 | 대응 |
|--------|------|------|
| API Rate Limit | 중 | 캐싱, 백업 API |
| AI 품질 불안정 | 중 | 프롬프트 버전 관리 |
| WP API 변경 | 낮 | 버전 고정 |

### 9.2 비즈니스 리스크

| 리스크 | 확률 | 대응 |
|--------|------|------|
| 애드센스 거절 | 20% | 품질 강화, 재신청 |
| 트래픽 부족 | 30% | 키워드 최적화 |
| 구글 정책 변경 | 10% | 다중 수익원 |

---

## 10. 부록

### 10.1 용어 정의

| 용어 | 정의 |
|------|------|
| **RPM** | Revenue Per Mille (1,000 PV당 수익) |
| **CPC** | Cost Per Click (클릭당 비용) |
| **E-E-A-T** | Experience, Expertise, Authoritativeness, Trustworthiness |
| **SEO** | Search Engine Optimization |

### 10.2 참조 문서

- `wp-auto-blog-analysis.md` - 시장 분석
- `wp-auto-blog-validation.md` - 투자 검증
- `feasibility-auto-blog-pipeline.md` - 기술 검증
- `cost-estimate.md` - 비용 분석
- `mvp-test-strategy.md` - MVP 테스트 전략

---

*PRD generated by Product Director Agent*
*Date: 2026-01-02*
*Version: 1.0*
