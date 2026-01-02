# Additional Test Scenarios - wp-auto-blog

| 항목 | 내용 |
|------|------|
| **Project** | wp-auto-blog |
| **Date** | 2026-01-02 |
| **Author** | QA Scenario Writer |
| **Status** | Recommended |

---

## 1. Integration Test Scenarios (P1)

### 1.1 Rate Limit Handling

```yaml
scenario: API_RATE_LIMIT_001
title: HN API Rate Limit 재시도
priority: P1
type: integration

preconditions:
  - TrendDetector 인스턴스 생성
  - HN API Mock 설정

steps:
  1. HN API가 429 (Too Many Requests) 응답 반환하도록 Mock 설정
  2. TrendDetector.collect() 호출
  3. 재시도 로직 확인 (최대 3회)
  4. 재시도 간격 확인 (exponential backoff)

expected:
  - 429 응답 시 자동 재시도
  - 재시도 간격: 1s -> 2s -> 4s
  - 3회 실패 후 graceful 종료
  - 에러 로깅 확인

test_data:
  mock_responses:
    - status: 429, retry_after: 1
    - status: 429, retry_after: 2
    - status: 200, data: [12345]
```

### 1.2 Network Timeout

```yaml
scenario: NETWORK_TIMEOUT_001
title: API 타임아웃 처리
priority: P1
type: integration

preconditions:
  - 각 API 클라이언트 인스턴스 생성
  - 네트워크 타임아웃 Mock 설정

steps:
  1. requests.get에 Timeout 예외 발생하도록 Mock 설정
  2. 각 Fetcher 메서드 호출
  3. 예외 처리 확인
  4. 빈 결과 반환 확인

expected:
  - Timeout 예외 catch
  - 에러 로깅
  - 빈 리스트 반환 (not raise)
  - 다른 소스 계속 시도

modules:
  - TrendDetector._fetch_hacker_news
  - TrendDetector._fetch_google_trends
  - TrendDetector._fetch_reddit
  - ImageFetcher._fetch_unsplash
  - ImageFetcher._fetch_pexels
```

### 1.3 Concurrent Pipeline Execution

```yaml
scenario: CONCURRENT_EXEC_001
title: 병렬 파이프라인 실행
priority: P2
type: integration

preconditions:
  - BlogPipeline 인스턴스 2개 생성
  - 동일 토픽 처리 시나리오

steps:
  1. 2개의 파이프라인 인스턴스 생성
  2. 동시에 run() 호출 (threading 사용)
  3. 중복 포스트 생성 확인
  4. Race condition 확인

expected:
  - 중복 포스트 방지 (또는 허용 여부 명확화)
  - Thread-safe 동작
  - 리소스 충돌 없음

notes:
  - 현재 구현에서는 지원하지 않을 수 있음
  - 향후 스케일 시 필요
```

---

## 2. Edge Case Test Scenarios (P1)

### 2.1 Unicode Topic Handling

```yaml
scenario: UNICODE_001
title: Unicode 토픽 처리 (한글, 이모지)
priority: P1
type: unit

preconditions:
  - TrendDetector 인스턴스 생성

test_cases:
  - name: Korean topic
    input: "인공지능 트렌드 2026"
    expected_keywords: ["인공지능", "트렌드"]

  - name: Emoji in topic
    input: "AI Tools for Developers 🚀"
    expected: 이모지 제거 또는 유지

  - name: Mixed unicode
    input: "Claude 3.5 は素晴らしい"
    expected: 다국어 처리

steps:
  1. Unicode 문자열로 토픽 생성
  2. _extract_keywords() 호출
  3. _generate_title() 호출
  4. 결과 검증

expected:
  - Unicode 문자 깨짐 없음
  - 키워드 추출 정상 동작
  - 제목 생성 정상 동작
```

### 2.2 Very Long Content

```yaml
scenario: LONG_CONTENT_001
title: 대용량 콘텐츠 처리 (5000+ 단어)
priority: P1
type: unit

preconditions:
  - ContentGenerator 인스턴스 생성

steps:
  1. LLM Mock이 5000+ 단어 HTML 반환하도록 설정
  2. generate() 호출
  3. 처리 시간 측정
  4. 메모리 사용량 확인 (optional)

expected:
  - 정상 처리 (에러 없음)
  - word_count 정확 계산
  - _validate() 경고 메시지 (max_words 초과)

test_data:
  content_length: 5000, 10000, 20000 단어
```

### 2.3 Empty/Null Input Handling

```yaml
scenario: EMPTY_INPUT_001
title: 빈/Null 입력 처리
priority: P1
type: unit

test_cases:
  - name: Empty topic
    input: ""
    expected: ValueError 또는 빈 결과

  - name: Null keywords
    input: None
    expected: 빈 리스트로 처리

  - name: Empty keyword list
    input: []
    expected: 정상 처리

  - name: Whitespace only topic
    input: "   "
    expected: ValueError 또는 빈 결과

modules:
  - ContentGenerator.generate()
  - ImageFetcher.fetch()
  - TrendDetector._extract_keywords()
```

### 2.4 Special Characters in HTML

```yaml
scenario: HTML_SPECIAL_001
title: HTML 특수문자 처리
priority: P1
type: unit

preconditions:
  - ContentGenerator 인스턴스 생성

test_cases:
  - name: HTML entities
    input: "<h1>A &amp; B &lt; C</h1>"
    expected: 정상 파싱

  - name: Unescaped angle brackets
    input: "<h1>Size: 5 < 10 > 3</h1>"
    expected: 이스케이프 또는 정상 처리

  - name: Quote characters
    input: '<h1>Test "title" here</h1>'
    expected: 정상 처리

steps:
  1. LLM Mock이 특수문자 포함 HTML 반환
  2. _clean_html() 호출
  3. _extract_title() 호출
  4. WordPress 포스팅 시 문제 없음 확인
```

---

## 3. Security Test Scenarios (P1)

### 3.1 HTML Injection Prevention

```yaml
scenario: SECURITY_001
title: HTML 인젝션 방지
priority: P1
type: security

preconditions:
  - 악성 HTML 포함 토픽

test_cases:
  - name: Script injection
    input:
      topic: "AI <script>alert('xss')</script> Tools"
    expected: 스크립트 태그 제거 또는 이스케이프

  - name: Event handler injection
    input:
      topic: "Review <img onerror='alert(1)' src='x'>"
    expected: 이벤트 핸들러 제거

  - name: Link injection
    input:
      topic: "Click <a href='javascript:void(0)'>here</a>"
    expected: javascript: URL 제거

steps:
  1. 악성 HTML 포함 토픽으로 콘텐츠 생성
  2. 최종 HTML 출력 검증
  3. WordPress 발행 시 sanitization 확인

expected:
  - 모든 스크립트 관련 코드 제거
  - 안전한 HTML만 포함
```

### 3.2 Credential Logging Prevention

```yaml
scenario: SECURITY_002
title: 민감정보 로깅 방지
priority: P1
type: security

preconditions:
  - 로깅 설정 활성화
  - 환경변수에 실제 API 키 설정

steps:
  1. 파이프라인 실행
  2. 로그 파일/출력 검사
  3. API 키, 비밀번호 노출 확인

expected:
  - API 키 마스킹 (****로 표시)
  - WordPress 비밀번호 미노출
  - 인증 헤더 미노출

current_status: NOT IMPLEMENTED
recommendation: loguru 필터 추가
```

### 3.3 HTTPS Enforcement

```yaml
scenario: SECURITY_003
title: WordPress HTTPS 강제
priority: P2
type: security

test_cases:
  - name: HTTP URL rejection
    input: "http://blog.example.com"
    expected: 경고 또는 거부

  - name: HTTPS URL acceptance
    input: "https://blog.example.com"
    expected: 정상 처리

steps:
  1. HTTP URL로 WPConfig 생성
  2. WordPressClient 초기화
  3. 경고/에러 확인

expected:
  - HTTP URL에 대한 경고
  - 프로덕션에서 HTTPS 강제
```

---

## 4. E2E Test Scenarios (P2)

### 4.1 Full Pipeline E2E

```yaml
scenario: E2E_001
title: 전체 파이프라인 E2E (Staging)
priority: P2
type: e2e
environment: staging

preconditions:
  - Staging WordPress 사이트 준비
  - 실제 API 키 설정 (테스트 계정)
  - Dry-run 모드 비활성화

steps:
  1. python -m src.main --max-posts 1 --dry-run false
  2. 트렌드 감지 확인 (실제 HN API)
  3. 콘텐츠 생성 확인 (실제 Gemini API)
  4. 이미지 수집 확인 (실제 Unsplash API)
  5. WordPress Draft 생성 확인
  6. Draft 내용 검증

expected:
  - 1개 포스트 Draft 생성
  - 1500+ 단어 콘텐츠
  - 3+ 이미지 포함
  - 메타 설명 설정
  - 카테고리/태그 설정

cleanup:
  - 테스트 포스트 삭제

notes:
  - 실제 API 비용 발생
  - CI/CD에서 주 1회 실행 권장
```

### 4.2 Scheduled Execution

```yaml
scenario: E2E_002
title: 스케줄러 실행 테스트
priority: P2
type: e2e

preconditions:
  - Schedule 라이브러리 설정
  - Cron 또는 schedule 사용

steps:
  1. 스케줄러 설정 (1분 간격 테스트)
  2. 스케줄러 시작
  3. 1분 대기
  4. 파이프라인 실행 확인
  5. 스케줄러 종료

expected:
  - 정해진 시간에 자동 실행
  - 에러 시 복구
  - 로그 기록

status: NOT IMPLEMENTED
recommendation: src/scheduler.py 구현 후 테스트
```

### 4.3 Draft to Publish Workflow

```yaml
scenario: E2E_003
title: Draft -> Publish 워크플로우
priority: P2
type: e2e

steps:
  1. 파이프라인 실행 (Draft 생성)
  2. WordPress Admin에서 Draft 확인
  3. 수동 검토 후 Publish
  4. 공개 URL 접근 확인
  5. SEO 설정 확인 (title, meta)

expected:
  - Draft 정상 생성
  - Admin에서 편집 가능
  - Publish 후 공개 접근 가능
  - Featured Image 표시
```

---

## 5. Performance Test Scenarios (P2)

### 5.1 API Response Time

```yaml
scenario: PERF_001
title: API 응답 시간 측정
priority: P2
type: performance

metrics:
  - HN API 응답 시간
  - Google Trends 응답 시간
  - Gemini API 응답 시간
  - Unsplash API 응답 시간
  - WordPress API 응답 시간

thresholds:
  - 단일 API 호출: < 5초
  - 전체 파이프라인: < 10분

measurement:
  - 각 API 호출 시작/종료 시간 로깅
  - 평균/최대/P95 계산
```

### 5.2 Memory Usage

```yaml
scenario: PERF_002
title: 메모리 사용량 측정
priority: P3
type: performance

steps:
  1. 파이프라인 시작 전 메모리 측정
  2. 파이프라인 실행
  3. 피크 메모리 측정
  4. 파이프라인 종료 후 메모리 측정

thresholds:
  - 피크 메모리: < 500MB
  - 메모리 누수: 없음
```

---

## 6. Implementation Notes

### 6.1 테스트 구현 우선순위

```
P1 (1주 내):
1. UNICODE_001 - Unicode 처리
2. EMPTY_INPUT_001 - 빈 입력 처리
3. SECURITY_001 - HTML 인젝션 방지
4. API_RATE_LIMIT_001 - Rate limit 처리

P2 (2주 내):
1. E2E_001 - 전체 파이프라인 E2E
2. NETWORK_TIMEOUT_001 - 타임아웃 처리
3. LONG_CONTENT_001 - 대용량 콘텐츠

P3 (백로그):
1. CONCURRENT_EXEC_001 - 병렬 실행
2. PERF_001, PERF_002 - 성능 테스트
```

### 6.2 테스트 구현 예시

```python
# tests/test_edge_cases.py

import pytest
from src.trend_detector import TrendDetector

class TestUnicodeHandling:
    """Unicode 처리 테스트."""

    @pytest.fixture
    def detector(self, mock_env_vars):
        return TrendDetector()

    @pytest.mark.unit
    def test_korean_topic_keywords(self, detector):
        """한글 토픽에서 키워드 추출."""
        keywords = detector._extract_keywords("인공지능 트렌드 분석 2026")
        # 한글 단어가 포함되어야 함
        assert len(keywords) > 0

    @pytest.mark.unit
    def test_emoji_in_topic(self, detector):
        """이모지 포함 토픽 처리."""
        title = detector._generate_title(
            topic="AI Tools 🚀 for Developers",
            keywords=["ai", "tools"],
        )
        # 이모지가 제거되거나 유지되어도 에러 없음
        assert isinstance(title, str)
        assert len(title) > 0


class TestEmptyInputHandling:
    """빈 입력 처리 테스트."""

    @pytest.fixture
    def detector(self, mock_env_vars):
        return TrendDetector()

    @pytest.mark.unit
    def test_empty_text_keywords(self, detector):
        """빈 텍스트에서 키워드 추출."""
        keywords = detector._extract_keywords("")
        assert keywords == []

    @pytest.mark.unit
    def test_whitespace_only_keywords(self, detector):
        """공백만 있는 텍스트."""
        keywords = detector._extract_keywords("   \n\t  ")
        assert keywords == []
```

---

*Scenario Document generated by QA Scenario Writer Agent*
*Date: 2026-01-02*
*Version: 1.0*
