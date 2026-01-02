---
project: wp-auto-blog
created: 2026-01-02
type: mvp-strategy
phase: pre-development
duration: 5 weeks
---

# MVP 테스트 전략 - 워드프레스 자동 블로그

## Executive Summary

| 항목 | 내용 |
|------|------|
| **목표** | 애드센스 승인 획득 + 자동화 전 검증 |
| **기간** | 5주 |
| **산출물** | 20개 고품질 글 + 승인된 블로그 |
| **성공 지표** | 애드센스 승인 + 일 100 PV |

---

## 1. MVP 테스트 타임라인

```
┌─────────────────────────────────────────────────────────────────────┐
│                        5주 MVP 테스트 플랜                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Week 1: 기반 구축                                                  │
│  ─────────────────                                                  │
│  □ Day 1: 도메인 구매 + WordPress 설치                              │
│  □ Day 2: 테마 설정 + 필수 플러그인                                 │
│  □ Day 3-4: 필수 페이지 작성 (About, Contact, Privacy)             │
│  □ Day 5-7: 첫 5개 글 작성                                          │
│                                                                     │
│  Week 2: 콘텐츠 집중                                                │
│  ─────────────────                                                  │
│  □ Day 8-14: 10개 글 추가 작성 (총 15개)                            │
│  □ SEO 최적화 (메타, 내부 링크)                                     │
│  □ Google Search Console 등록                                       │
│                                                                     │
│  Week 3: 승인 준비 + 신청                                           │
│  ─────────────────                                                  │
│  □ Day 15-18: 5개 글 추가 (총 20개)                                 │
│  □ Day 19: 최종 체크리스트 검토                                     │
│  □ Day 20-21: 애드센스 신청                                         │
│                                                                     │
│  Week 3-5: 개발 병행 + 승인 대기                                    │
│  ─────────────────                                                  │
│  □ 자동화 파이프라인 개발 착수                                       │
│  □ 트래픽 모니터링 및 글 보강                                        │
│  □ 애드센스 승인 대기 (5-14일)                                      │
│                                                                     │
│  Week 5+: 결과 확인                                                  │
│  ─────────────────                                                  │
│  □ 승인 시 → 자동화 시작                                            │
│  □ 거절 시 → 피드백 반영 후 재신청                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 애드센스 승인 체크리스트

### 2.1 필수 요건 (Must Have)

| # | 요건 | 기준 | 체크 |
|---|------|------|------|
| 1 | **고유 콘텐츠** | 100% 오리지널, 복사/스핀 금지 | □ |
| 2 | **최소 글 수** | 15-20개 이상 | □ |
| 3 | **글 길이** | 1,500+ 단어/글 | □ |
| 4 | **사이트 연령** | 최소 2-4주 (일부 국가) | □ |
| 5 | **필수 페이지** | About, Contact, Privacy Policy | □ |
| 6 | **네비게이션** | 명확한 메뉴, 카테고리 구조 | □ |
| 7 | **모바일 최적화** | 반응형 디자인 | □ |
| 8 | **SSL 인증서** | HTTPS 필수 | □ |
| 9 | **로딩 속도** | 3초 이내 | □ |
| 10 | **저작권 이미지** | Unsplash/Pexels 또는 직접 제작 | □ |

### 2.2 품질 요건 (Quality)

| # | 요건 | 기준 | 체크 |
|---|------|------|------|
| 1 | **E-E-A-T** | 경험, 전문성, 권위, 신뢰 표현 | □ |
| 2 | **가치 제공** | 독자에게 실질적 도움 | □ |
| 3 | **글 구조** | H1 > H2 > H3, 목차 포함 | □ |
| 4 | **시각 자료** | 글당 3-5개 이미지/표 | □ |
| 5 | **내부 링크** | 관련 글 2-3개 링크 | □ |
| 6 | **외부 링크** | 신뢰할 수 있는 출처 인용 | □ |
| 7 | **저자 정보** | Author Bio, 소셜 링크 | □ |
| 8 | **댓글 활성화** | 커뮤니티 신호 | □ |

### 2.3 금지 사항 (Instant Rejection)

```yaml
절대_금지:
  - AI 생성 티가 나는 저품질 콘텐츠
  - 다른 사이트 복사/스크래핑
  - 저작권 침해 이미지
  - 성인/폭력/도박 콘텐츠
  - 약물/의료 조언 (비전문가)
  - 클릭베이트 제목
  - 숨겨진 텍스트/링크
  - 과도한 광고 공간 예약
```

---

## 3. 콘텐츠 전략

### 3.1 타겟 니치 구체화

```yaml
메인_니치: AI Tools & Software

서브_니치 (20개 글 분배):
  1. AI_Writing_Tools (5개):
     - "Best AI Writing Tools 2025"
     - "ChatGPT vs Claude vs Gemini: Honest Comparison"
     - "How to Use ChatGPT for Blog Writing"
     - "Jasper AI Review: Worth $49/month?"
     - "Free AI Writing Tools That Actually Work"

  2. AI_Productivity (5개):
     - "Best AI Tools for Productivity in 2025"
     - "How AI Assistants Can Save You 10 Hours/Week"
     - "Notion AI vs Obsidian AI: Which is Better?"
     - "AI Meeting Assistants: Complete Guide"
     - "Automate Your Workflow with AI: Beginner's Guide"

  3. AI_Image_Generation (4개):
     - "Midjourney vs DALL-E 3 vs Stable Diffusion"
     - "How to Create AI Art: Complete Tutorial"
     - "Best Free AI Image Generators 2025"
     - "AI Image Generation for Business: Use Cases"

  4. AI_Coding_Tools (3개):
     - "GitHub Copilot vs Cursor vs Cody: Developer's Guide"
     - "Best AI Coding Assistants 2025"
     - "How AI is Changing Software Development"

  5. AI_Business (3개):
     - "AI Tools for Small Business Owners"
     - "How to Start an AI-Powered Side Hustle"
     - "AI Automation for Entrepreneurs: Getting Started"
```

### 3.2 키워드 리서치 방법

```yaml
Step_1_시드_키워드:
  도구: Google Trends (무료)
  방법:
    1. "AI tools" 검색
    2. 관련 검색어 확인
    3. 급상승 토픽 식별

Step_2_롱테일_확장:
  도구: Ubersuggest (무료 3회/일) 또는 KeywordTool.io
  방법:
    1. 시드 키워드 입력
    2. 검색량 500-5,000 필터
    3. KD (Keyword Difficulty) 30 이하 우선

Step_3_경쟁_분석:
  도구: Google 검색
  방법:
    1. 키워드 직접 검색
    2. 1페이지 경쟁자 확인
    3. 약한 경쟁자 (포럼, 오래된 글) 있으면 기회

Step_4_의도_분류:
  정보형 (How to, What is): 트래픽용
  비교형 (vs, Best): 고 CPC
  리뷰형 (Review): 제휴 마케팅 연계

추천_키워드_템플릿:
  - "[Tool Name] review 2025"
  - "[Tool A] vs [Tool B]"
  - "best [category] tools 2025"
  - "how to use [Tool Name]"
  - "[Tool Name] alternatives"
  - "free [category] tools"
```

### 3.3 CPC 높은 키워드 예시

| 키워드 | 예상 CPC | 검색량 | 난이도 |
|--------|---------|--------|--------|
| "best AI writing software" | $8-15 | 2,400 | 중 |
| "Jasper AI pricing" | $10-18 | 1,900 | 중 |
| "ChatGPT alternatives" | $5-10 | 8,100 | 중-고 |
| "AI tools for business" | $6-12 | 3,600 | 중 |
| "GitHub Copilot review" | $4-8 | 4,400 | 중 |
| "Midjourney tutorial" | $3-6 | 12,100 | 중 |

---

## 4. 글 작성 템플릿

### 4.1 리뷰형 글 템플릿 (Review)

```markdown
# [Tool Name] Review 2025: Is It Worth It? (Honest Opinion)

> Quick Verdict: [한 줄 결론]

## What is [Tool Name]?
[간단한 소개 - 2-3 문단]

## Key Features
### Feature 1: [기능명]
[설명 + 스크린샷]

### Feature 2: [기능명]
[설명 + 스크린샷]

### Feature 3: [기능명]
[설명 + 스크린샷]

## Pricing
| Plan | Price | Features |
|------|-------|----------|
| Free | $0 | ... |
| Pro | $X/mo | ... |
| Team | $Y/mo | ... |

## Pros and Cons
### What I Liked
- Pro 1
- Pro 2
- Pro 3

### What Could Be Better
- Con 1
- Con 2

## Who Should Use [Tool Name]?
- Best for: [타겟 사용자]
- Not for: [맞지 않는 사용자]

## [Tool Name] Alternatives
1. [Alternative 1] - [한 줄 설명]
2. [Alternative 2] - [한 줄 설명]
3. [Alternative 3] - [한 줄 설명]

## Final Verdict
[최종 평가 - 2-3 문단]

**Rating: X/10**

## FAQ
### Q1: [자주 묻는 질문]
A: [답변]

### Q2: [자주 묻는 질문]
A: [답변]
```

### 4.2 비교형 글 템플릿 (vs Comparison)

```markdown
# [Tool A] vs [Tool B]: Which One Should You Choose in 2025?

> TL;DR: [한 줄 결론 - 누구에게 뭐가 좋은지]

## Quick Comparison Table
| Feature | [Tool A] | [Tool B] |
|---------|----------|----------|
| Price | $X/mo | $Y/mo |
| Best For | ... | ... |
| Free Plan | Yes/No | Yes/No |
| Key Strength | ... | ... |

## [Tool A] Overview
[소개 + 핵심 기능 - 3-4 문단]

## [Tool B] Overview
[소개 + 핵심 기능 - 3-4 문단]

## Head-to-Head Comparison

### 1. Features
[상세 비교]

### 2. Pricing
[가격 비교 표 + 분석]

### 3. Ease of Use
[사용성 비교]

### 4. Performance
[성능 비교]

### 5. Customer Support
[지원 비교]

## When to Choose [Tool A]
- Scenario 1
- Scenario 2
- Scenario 3

## When to Choose [Tool B]
- Scenario 1
- Scenario 2
- Scenario 3

## My Recommendation
[개인 의견 + 근거]

## Conclusion
[최종 정리]
```

### 4.3 가이드형 글 템플릿 (How-to)

```markdown
# How to [달성 목표]: Complete Guide (2025)

> In this guide, you'll learn [배울 내용 요약]

## Table of Contents
1. [섹션 1]
2. [섹션 2]
3. [섹션 3]
...

## What You'll Need
- Requirement 1
- Requirement 2
- Time: X minutes

## Step 1: [첫 번째 단계]
[상세 설명]

![Screenshot](image-url)

**Pro Tip:** [팁]

## Step 2: [두 번째 단계]
[상세 설명]

## Step 3: [세 번째 단계]
[상세 설명]

...

## Common Mistakes to Avoid
1. Mistake 1: [설명]
2. Mistake 2: [설명]
3. Mistake 3: [설명]

## Troubleshooting
### Problem: [문제]
**Solution:** [해결책]

## Next Steps
- [다음 할 일 1]
- [다음 할 일 2]

## Conclusion
[요약 + CTA]

## FAQ
...
```

---

## 5. 품질 기준 (Quality Standards)

### 5.1 글당 필수 체크리스트

| # | 항목 | 기준 | 체크 |
|---|------|------|------|
| 1 | **단어 수** | 1,500-2,500 단어 | □ |
| 2 | **H2/H3 구조** | H2 5개+, H3 적절히 | □ |
| 3 | **목차** | Table of Contents 포함 | □ |
| 4 | **이미지** | 3-5개 (저작권 준수) | □ |
| 5 | **내부 링크** | 2-3개 관련 글 링크 | □ |
| 6 | **외부 링크** | 1-2개 권위 있는 출처 | □ |
| 7 | **메타 설명** | 150-160자, 키워드 포함 | □ |
| 8 | **Featured Image** | 1200x630 이상 | □ |
| 9 | **가독성** | 짧은 문단 (3-4문장) | □ |
| 10 | **CTA** | 명확한 행동 유도 | □ |

### 5.2 SEO 최적화 체크리스트

| # | 항목 | 기준 | 체크 |
|---|------|------|------|
| 1 | **Title Tag** | 키워드 포함, 60자 이내 | □ |
| 2 | **URL Slug** | 짧고 키워드 포함 | □ |
| 3 | **H1** | 1개만, 키워드 포함 | □ |
| 4 | **키워드 밀도** | 1-2% (자연스럽게) | □ |
| 5 | **첫 100단어** | 키워드 자연스럽게 포함 | □ |
| 6 | **Alt Text** | 모든 이미지에 설명 | □ |
| 7 | **Schema Markup** | Article, FAQ 스키마 | □ |

### 5.3 E-E-A-T 강화 방법

```yaml
Experience (경험):
  - "I tested [Tool] for 2 weeks..."
  - "In my experience with..."
  - 직접 사용 스크린샷 포함
  - 개인적인 사용 사례 공유

Expertise (전문성):
  - 기술적 세부사항 설명
  - 정확한 용어 사용
  - 데이터/통계 인용
  - 심층 분석 제공

Authoritativeness (권위):
  - Author Bio 상세히 작성
  - 소셜 프로필 링크
  - 다른 글에서 자기 인용
  - 신뢰할 수 있는 출처 링크

Trustworthiness (신뢰):
  - 장단점 균형 있게
  - 투명한 공개 (제휴 링크 등)
  - 최신 정보 유지 (날짜 표시)
  - 댓글 응답 (engagement)
```

---

## 6. 성공 지표 (KPIs)

### 6.1 Week 1-3 (콘텐츠 작성 기간)

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| **글 수** | 20개 | WordPress 대시보드 |
| **평균 글 길이** | 1,800+ 단어 | Yoast/RankMath |
| **이미지 수** | 글당 4개+ | 수동 확인 |
| **내부 링크** | 글당 2개+ | 수동 확인 |

### 6.2 Week 3-5 (승인 대기 기간)

| 지표 | 목표 | 측정 방법 |
|------|------|----------|
| **일일 PV** | 50-100 | Google Analytics |
| **인덱싱률** | 80%+ | Search Console |
| **평균 체류시간** | 2분+ | GA4 |
| **이탈률** | 70% 이하 | GA4 |

### 6.3 성공/실패 기준

```yaml
성공_기준:
  필수:
    - 애드센스 승인 ✅
    - 20개 글 발행 완료
  권장:
    - 일 100 PV 달성
    - 인덱싱 80%+

실패_시_대응:
  애드센스_거절:
    1. 거절 사유 확인
    2. 해당 이슈 수정 (보통 콘텐츠 품질)
    3. 추가 글 5-10개 작성
    4. 2주 후 재신청

  트래픽_부족:
    1. 키워드 재검토
    2. 소셜 공유 (Reddit, Twitter)
    3. 내부 링크 강화
    4. 기존 글 업데이트
```

---

## 7. 필수 페이지 템플릿

### 7.1 About Page

```markdown
# About [Blog Name]

## Who We Are
[Blog Name] is your go-to resource for [니치 주제].
We help [타겟 독자] to [제공 가치].

## Our Mission
[미션 설명 - 2-3 문장]

## What We Cover
- Topic 1: [설명]
- Topic 2: [설명]
- Topic 3: [설명]

## Meet the Author
**[Your Name]**

[짧은 자기소개 - 경험, 자격, 관심사]

[Photo - optional but recommended]

**Connect with me:**
- Twitter: @handle
- LinkedIn: /in/handle
- Email: email@domain.com

## Why Trust Us?
- [신뢰 요소 1]
- [신뢰 요소 2]
- [신뢰 요소 3]
```

### 7.2 Privacy Policy (필수)

```markdown
# Privacy Policy

Last updated: [날짜]

## Information We Collect
...

## How We Use Your Information
...

## Cookies and Tracking
This website uses Google Analytics and Google AdSense.
...

## Third-Party Services
...

## Contact Us
[연락처 정보]
```

### 7.3 Contact Page

```markdown
# Contact Us

Have a question or suggestion? We'd love to hear from you!

## Get in Touch
**Email:** contact@yourblog.com

## Response Time
We typically respond within 24-48 hours.

[Contact Form - optional]
```

---

## 8. 기술 설정 가이드

### 8.1 WordPress 필수 설정

```yaml
테마:
  추천: Astra (무료), GeneratePress (무료)
  이유: 빠름, SEO 최적화, 깔끔

필수_플러그인:
  SEO:
    - RankMath (무료) 또는 Yoast (무료)
  보안:
    - Wordfence (무료)
  성능:
    - LiteSpeed Cache 또는 WP Super Cache
  이미지:
    - ShortPixel (무료 100장/월)
  기타:
    - UpdraftPlus (백업)

설정_체크리스트:
  □ Permalink: Post name (/blog-post-title/)
  □ Timezone: 타겟 지역 (US/Eastern 등)
  □ Comments: 활성화 (승인 후 표시)
  □ Search Engine Visibility: 체크 해제
```

### 8.2 Google 도구 연동

```yaml
Google_Search_Console:
  1. 사이트 소유권 확인 (HTML 파일 또는 DNS)
  2. 사이트맵 제출 (yourblog.com/sitemap.xml)
  3. 인덱싱 요청

Google_Analytics_4:
  1. GA4 속성 생성
  2. 측정 ID 복사 (G-XXXXXXXX)
  3. RankMath에 ID 입력 또는 테마에 코드 삽입

Google_AdSense:
  1. 계정 생성 (기존 Gmail 사용)
  2. 사이트 추가
  3. 코드 삽입 (RankMath 또는 테마)
  4. 심사 요청
```

---

## 9. 20개 글 작성 일정

### Week 1: Day 1-7

| Day | 글 # | 주제 | 유형 | 예상 시간 |
|-----|------|------|------|----------|
| 3 | 1 | Best AI Writing Tools 2025 | List | 3시간 |
| 4 | 2 | ChatGPT vs Claude: Honest Comparison | vs | 3시간 |
| 5 | 3 | How to Use ChatGPT for Blog Writing | Guide | 2.5시간 |
| 6 | 4 | Jasper AI Review 2025 | Review | 3시간 |
| 7 | 5 | Free AI Writing Tools That Work | List | 2.5시간 |

### Week 2: Day 8-14

| Day | 글 # | 주제 | 유형 | 예상 시간 |
|-----|------|------|------|----------|
| 8 | 6 | Best AI Productivity Tools 2025 | List | 3시간 |
| 9 | 7 | How AI Saves 10 Hours/Week | Guide | 2.5시간 |
| 10 | 8 | Notion AI vs Obsidian AI | vs | 3시간 |
| 11 | 9 | AI Meeting Assistants Guide | Guide | 2.5시간 |
| 12 | 10 | Automate Workflow with AI | Guide | 2.5시간 |
| 13 | 11 | Midjourney vs DALL-E 3 | vs | 3시간 |
| 14 | 12 | How to Create AI Art Tutorial | Guide | 3시간 |

### Week 3: Day 15-21

| Day | 글 # | 주제 | 유형 | 예상 시간 |
|-----|------|------|------|----------|
| 15 | 13 | Best Free AI Image Generators | List | 2.5시간 |
| 16 | 14 | AI Image for Business Use Cases | Guide | 2.5시간 |
| 17 | 15 | GitHub Copilot vs Cursor vs Cody | vs | 3시간 |
| 18 | 16 | Best AI Coding Assistants 2025 | List | 2.5시간 |
| 19 | 17 | AI Changing Software Development | Opinion | 2시간 |
| 20 | 18 | AI Tools for Small Business | List | 2.5시간 |
| 21 | 19 | AI-Powered Side Hustle Guide | Guide | 2.5시간 |
|    | 20 | AI Automation for Entrepreneurs | Guide | 2.5시간 |

**총 예상 시간**: 약 55시간 (3주)

---

## 10. 다음 단계: 자동화 요구사항

### 10.1 자동화 파이프라인 요구사항 (PRD 초안)

```yaml
기능_요구사항:

  FR-001_트렌드_감지:
    설명: 핫 토픽 자동 수집
    소스: Google Trends, HN, Reddit
    빈도: 일 2-3회
    출력: 토픽 리스트 (제목, 키워드, 우선순위)

  FR-002_콘텐츠_생성:
    설명: AI 기반 블로그 글 생성
    입력: 토픽, 키워드, 템플릿
    LLM: Gemini Flash (기본), GPT-4o-mini (백업)
    출력: 완성된 글 (HTML 형식)
    품질: 1,500+ 단어, SEO 최적화

  FR-003_이미지_추가:
    설명: 관련 이미지 자동 첨부
    소스: Unsplash, Pexels
    수량: 글당 3-5개
    출력: 이미지 URL + Alt 텍스트

  FR-004_품질_검증:
    설명: 발행 전 품질 체크
    체크: 글자 수, 키워드 밀도, 중복
    결과: Pass/Fail + 피드백

  FR-005_WordPress_발행:
    설명: 자동 포스팅
    상태: Draft (검수 후 Publish)
    메타: 카테고리, 태그, Featured Image

  FR-006_알림:
    설명: 작업 완료 알림
    채널: 이메일 또는 Slack
    내용: 발행된 글 링크, 에러 로그

비기능_요구사항:

  NFR-001_비용:
    AI API: 월 $1 이하
    호스팅: 월 $5 이하 (파이프라인)

  NFR-002_안정성:
    가동률: 99%
    에러 복구: 자동 재시도 3회

  NFR-003_확장성:
    다중 블로그 지원 (Phase 2)
    다중 니치 지원
```

### 10.2 MVP 후 로드맵

```
Phase 1 (완료): MVP 테스트
  - 수동 20개 글
  - 애드센스 승인

Phase 2: 자동화 v1
  - 기본 파이프라인 구축
  - 주 7개 자동 발행
  - 수동 검수

Phase 3: 자동화 v2
  - 품질 자동 검증 강화
  - 검수 최소화 (5분/글)
  - 다중 카테고리

Phase 4: 스케일
  - 다중 블로그
  - 제휴 마케팅 연동
  - 트래픽 분석 자동화
```

---

## 11. 결론

### MVP 테스트 성공 기준

```yaml
필수_성공:
  □ 20개 고품질 글 발행
  □ 애드센스 승인 획득

권장_성공:
  □ 일 100 PV 달성
  □ 인덱싱률 80%+
  □ 평균 체류시간 2분+

타임라인:
  Week 1-2: 콘텐츠 작성
  Week 3: 승인 신청
  Week 3-5: 개발 병행 + 대기
  Week 5+: 자동화 시작
```

### 핵심 성공 요인

1. **품질 우선**: 20개 글 모두 1,500+ 단어, E-E-A-T 반영
2. **일관성**: 매일 1-2개 글 작성 (주말 포함)
3. **SEO 기본기**: 키워드 연구 → 구조화 → 최적화
4. **빠른 시작**: Day 1에 도메인+WordPress 완료

---

*Strategy Document generated by Product Director Agent*
*Date: 2026-01-02*
