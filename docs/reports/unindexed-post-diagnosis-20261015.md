# 미색인 98편 원인 진단 — 2026-10-15

현재 공통적인 공개 설정 오류는 발견하지 못했다. 미색인 98편 모두 HTTP 200, noindex 없음, 자기 URL canonical, 사이트맵 포함이다. 남은 진단은 미발견/수집 전 86편과 수집 후 미색인 12편으로 나눠 진행한다. 검색 수요가 없거나 본문이 부실해서라고 확정할 근거는 없다.

다음 권고는 색인된 엑셀 글 2편에서 미색인 상시 글 3편으로 문맥상 필요한 본문 링크를 추가하는 제한적 실험이다. 이번 작업은 조사와 문서화만 수행했으며 실제 글·사이트맵·보안 설정·색인 요청은 변경하지 않았다.

## 실제 확인 범위

- 기준 인벤토리·URL Inspection: [main 측정 실행 38694928294](https://github.com/hhj4861/wp-auto-blog/actions/runs/38694928294), 2026-10-15 15:51 KST경 조회한 공개 394편. 296 색인, 98 미색인.
- 공개 HTML 394편을 일반 감사 User-Agent(TrendPulseReadOnlyAudit/1.0)로 GET, 전부 HTTP 200. 원문은 저장하지 않고 링크 그래프·선택 영역의 텍스트 지표만 집계했다.
- 미색인 98편 전부와 색인 대조 24편의 robots meta/응답 헤더/canonical/본문 영역 존재 확인: 122편 모두 200, noindex 없음, 자기 URL canonical. 대조는 카테고리·월별 첫 글을 택한 기술 검사 표본이며 인과 비교군이 아니다.
- 공개 robots.txt: HTTP 200, User-agent *에 Disallow 비어 있음. sitemap_index.xml 명시. 사이트맵의 X-Robots-Tag: noindex,follow는 XML 자체 응답의 값으로 기사 98편의 noindex가 아니다.
- 사이트맵 index/post/page/category 모두 200. post-sitemap 395개는 공개 기사 394편과 홈페이지 1개다. 누락 기사 0, 초안이 섞인 증거 0.
- [GSC 사이트맵 조회 38696040367](https://github.com/hhj4861/wp-auto-blog/actions/runs/38696040367): 성공. sitemap_index.xml은 마지막 다운로드 2026-10-11T00:30:19.728Z, post-sitemap.xml은 2026-10-11T09:58:44.541Z, 둘 다 오류/경고 0·대기 아님. 현재 파일에는 모두 포함되지만 Google이 내려받은 10/11 시점의 파일 내용까지 현재와 같았다고 단정하지 않는다.
- 이전 runner의 403은 이번 로컬/runner 재확인에서 재현되지 않았다. 과거 특정 환경의 403만으로 현재 Googlebot 차단을 주장하지 않는다.

## Google Search Console 화면에서 추가 확인

[크롤링 통계](https://search.google.com/search-console/settings/crawl-stats?resource_id=https%3A%2F%2Ftrendpulse.blog%2F)와 [호스트 상태](https://search.google.com/search-console/settings/crawl-stats/host-status?resource_id=https%3A%2F%2Ftrendpulse.blog%2F)를 기존 로그인으로 읽기만 했다. 데이터 최종 업데이트 2026-10-13, 차트 범위 7/17~10/13.

- 총 요청은 UI 표시 약 3.83천, 평균 응답 715ms. 성공 200 94%, 301 4%, 404 1%; 여러 Googlebot 종류와 리소스를 합친 값이므로 기사 방문 횟수·스마트폰 색인 크롤링 횟수로 바꾸어 해석하지 않는다.
- 최근에는 사이트 크롤링 문제가 없지만 과거에는 있었다고 표시한다. robots.txt 가져오기·서버 연결은 과거 높은 실패율/최근 수용 가능, DNS는 수용 가능이다. 과거 문제가 98편 미색인의 직접 원인이라는 URL별 시간 상관은 아직 입증되지 않았다.
- [직접 조치](https://search.google.com/search-console/manual-actions?resource_id=https%3A%2F%2Ftrendpulse.blog%2F): 감지된 문제 없음.
- [보안 문제](https://search.google.com/search-console/security-issues?resource_id=https%3A%2F%2Ftrendpulse.blog%2F): 감지된 문제 없음. 이 결과가 자동 순위 평가·개별 콘텐츠 품질 문제까지 부정하는 것은 아니다.
- sitemap API 출력의 indexed=0은 실제 URL Inspection의 색인 296편과 일치하지 않는다. 이 필드는 Google 공식 문서에서도 deprecated/do not use로 명시돼 있으므로 현재 색인 총수로 사용하지 않는다. [Sitemaps API 필드 정의](https://developers.google.com/webmaster-tools/v1/sitemaps).

## 상태·기간별 분리

| Google 상태 | 편수 | 발행 30일 이상 | 발행 후 경과 중앙값 |
|---|---:|---:|---:|
| Google에는 아직 알려지지 않은 URL입니다. | 75 | 69 | 203.8일 |
| 발견됨 - 현재 색인이 생성되지 않음 | 11 | 4 | 15.1일 |
| 크롤링됨 - 현재 색인이 생성되지 않음 | 12 | 9 | 167.3일 |

미발견 75편 중 69편은 발행 30일이 넘었다. 따라서 신규 글 며칠의 정상 대기만으로 전체 현상을 설명할 수 없다. 반대로 발행 직후 글을 오래된 미색인과 같은 실패 기준으로 판단하지 않는다. 미발견은 현재 Google 기록의 상태이지 과거 한 번도 방문하지 않았다는 서버 로그 증명이 아니다.

수집 후 미색인 12편은 Google 기록상 robots ALLOWED/INDEXING_ALLOWED다. 8개 오래된 글의 마지막 수집은 8/19에 몰려 있고, 나머지는 8/26·9/23·10/2·10/4다. 현재 본문과 이전 수집 당시 본문이 같다는 보장은 없다. Google 문서도 이 상태의 미래 색인을 보장하지 않으며, 동일 URL의 반복 수집 요청을 해결책으로 권고하지 않는다. [상태 정의](https://support.google.com/webmasters/answer/7440203?hl=en).

## 내부 링크와 본문 길이 비교

본문 집계는 .entry-content(없으면 article)의 다른 공개 기사 정규 URL을 가리키는 a[href] 기준이다. 전체 페이지 집계는 이전/다음 글 등 테마 링크까지 포함한다. 쿼리형 단축 URL·외부 백링크·현재 목록 밖의 페이지는 이 집계 범위 밖이다. 텍스트 글자 수는 제목·작성자 등 선택 영역을 포함할 수 있어 품질/유용성 점수가 아니다.

| 비교 | 색인 296편 | 미색인 98편 |
|---|---:|---:|
| 다른 기사 본문에서 들어오는 링크 0 | 240 | 91 |
| 테마 포함 다른 기사에서 들어오는 링크 0 | 0 | 0 |
| 본문 선택 영역 글자 수 중앙값 | 5,010.5 | 5,304.5 |

본문 유입 링크가 없는 비율은 미색인 92.9%, 색인 81.1%다. 강화할 여지가 있지만 색인된 글에도 널리 존재하므로 단독 원인/인과효과를 입증하지 않는다. 테마 포함 링크 0은 양쪽 모두 없고, 98편 모두 이미 색인된 기사에서 오는 페이지 내 링크가 최소 하나 있다. 완전 고아 글이라고 부르지 않는다. 실제 Google이 해당 링크가 추가된 뒤 출발 글을 재수집했는지는 미확인이다.

미색인 글이 단순히 짧다는 패턴도 없다. 글을 길게 늘리는 처방은 이 자료로 정당화되지 않는다. 카테고리/시기/주제/포맷 변경이 섞인 관찰 자료다. 메뉴형은 13편 중 6편 색인·7편 미색인이지만, 발행 시점과 변경 이력이 달라 메뉴가 원인이라는 결론을 낼 수 없다.

## 다음 검증 실험 — 아직 적용하지 않음

1. [엑셀 틀 고정](https://trendpulse.blog/excel-freeze-panes/), [엑셀 매크로](https://trendpulse.blog/excel-macro-workflow-2026/) 중 문맥이 맞는 곳에서 아래 3편으로 실제 도움이 되는 본문 링크를 추가한다. 두 출발 글은 현재 색인돼 있다. 일괄 무관 링크·본문 길이 늘리기·사이트맵 반복 재제출은 하지 않는다.
2. 제목/본문 구조/URL 등 다른 변수를 동시에 바꾸지 않고 변경일과 출발 URL을 기록한다. 기존 메뉴형 글 13편은 당일 포맷 변경 이력이 있으므로 효과 비교에 섞지 않는다.
3. 7~14일 동안 출발 글·도착 글의 마지막 수집일과 미색인 상태 변화를 먼저 본다. 완결 28일 실적은 별도로 관찰한다. 수집이 갱신되지 않거나 표본이 부족하면 효과 미확인으로 남기며, 색인/방문/수익 증가를 보장하지 않는다.

| 우선 후보 | 현재 상태 | 현재 본문 유입 링크 |
|---|---|---:|
| [엑셀조건부서식 사용법: 셀 자동 색칠부터 수식 설정까지](https://trendpulse.blog/excel-conditional-formatting-2026/) | 크롤링됨 - 현재 색인이 생성되지 않음 | 0 |
| [VLOOKUP 사용법: 기본 수식부터 일치 방식과 오류 해결까지](https://trendpulse.blog/vlookup-excel-guide-2026/) | 크롤링됨 - 현재 색인이 생성되지 않음 | 0 |
| [엑셀표만들기: 표 생성·서식·머리글과 정렬·필터링 상세 가이드](https://trendpulse.blog/excel-table-format-filter-2026/) | 발견됨 - 현재 색인이 생성되지 않음 | 0 |

노션 사용법(1772)·채용 2편(1894/1897)도 본문 유입 링크가 없지만, 노션은 적합한 출발 허브가 필요하고 채용은 기한/현재 모집 사실을 먼저 공식 출처로 재검증해야 하므로 이번 상시 엑셀 실험과 분리한다. 건강 글의 내용 개선은 공식 근거와 안전성 검토를 함께 해야 하며, SEO 이유만으로 의료 표현을 확대하지 않는다.

남은 불확실성: Googlebot 서버/방화벽 로그와 URL별 재수집 이력, 시장 검색 수요, 경쟁 검색 결과 대비 고유한 정보 가치, 외부 링크, 실제 독자 행동/수익은 이번 진단으로 확정하지 못했다. HTTP 200·색인 허용·사이트맵 포함은 색인 보장이 아니다. [Google 크롤링 문제 진단](https://developers.google.com/search/docs/crawling-indexing/troubleshoot-crawling-errors), [사이트맵의 역할과 한계](https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview).

## 미색인 98편 전체 목록

전부 사이트맵 포함·HTTP 200·noindex 없음·자기 URL canonical을 확인했다. 아래 경과일은 조회 시각 기준이며, 본문 링크 수는 위의 현재 정규 URL 그래프 기준이다.

| ID | 글 | 카테고리 | Google 상태 | 경과일 | 본문 유입 링크 |
|---:|---|---|---|---:|---:|
| 195 | [개발자 생산성 2배 올린 리눅스 데스크톱 실전 세팅법](https://trendpulse.blog/%EA%B0%9C%EB%B0%9C%EC%9E%90-%EC%83%9D%EC%82%B0%EC%84%B1-2%EB%B0%B0-%EC%98%AC%EB%A6%B0-%EB%A6%AC%EB%88%85%EC%8A%A4-%EB%8D%B0%EC%8A%A4%ED%81%AC%ED%86%B1-%EC%8B%A4%EC%A0%84-%EC%84%B8%ED%8C%85%EB%B2%95/) | 테크 | 미발견 | 284.5 | 0 |
| 257 | [2026 실리콘밸리 개발자들이 초가공식품 끊은 이유](https://trendpulse.blog/%EC%8B%A4%EB%A6%AC%EC%BD%98%EB%B0%B8%EB%A6%AC-%EA%B0%9C%EB%B0%9C%EC%9E%90%EB%93%A4%EC%9D%B4-%EC%B4%88%EA%B0%80%EA%B3%B5%EC%8B%9D%ED%92%88-review-2026/) | 건강 | 미발견 | 279.8 | 0 |
| 283 | [200줄로 만드는 Claude Code](https://trendpulse.blog/200%EC%A4%84%EB%A1%9C-%EB%A7%8C%EB%93%9C%EB%8A%94-claude-review-2026/) | 생산성 | 수집 후 미색인 | 278.3 | 0 |
| 286 | [2026년 루팅폰 금융앱 차단 In 베트남](https://trendpulse.blog/2026%EB%85%84-%EB%A3%A8%ED%8C%85%ED%8F%B0-%EA%B8%88%EC%9C%B5%EC%95%B1-review-2026/) | 테크 | 수집 후 미색인 | 277.8 | 0 |
| 301 | [2026년 AI 도입이 드러낸 시장 재편](https://trendpulse.blog/2026%EB%85%84-ai-%EB%8F%84%EC%9E%85%EC%9D%B4-review-2026/) | 비즈니스 | 미발견 | 276.8 | 0 |
| 310 | [2026 맥OS 창 크기 조절로 멀티태스킹 효율 3배](https://trendpulse.blog/%EB%A7%A5os-%EC%B0%BD-%ED%81%AC%EA%B8%B0-review-2026/) | 생산성 | 미발견 | 275.8 | 0 |
| 322 | [Bandcamp AI 생성 음악을 플랫폼에서 전면 금지](https://trendpulse.blog/ai-generated-music-review-2026/) | 테크 | 발견·수집 전 | 274.2 | 0 |
| 333 | [Claude Code Cowork 신기능: 멀티 에이전트 협업 사용법과 활용사례](https://trendpulse.blog/claude-code-cowork-review-2026/) | 테크 | 미발견 | 273.6 | 0 |
| 347 | [2026년 개발자 주목! CPU만으로 돌리는 고품질 TTS 도구 Pocket TTS](https://trendpulse.blog/2026%EB%85%84-%EA%B0%9C%EB%B0%9C%EC%9E%90-%EC%A3%BC%EB%AA%A9-review-2026/) | 생산성 | 수집 후 미색인 | 271.8 | 0 |
| 350 | [2026 Cloudflare의 Astro 인수, 웹 개발자가 알아야 할 3가지](https://trendpulse.blog/cloudflare%EC%9D%98-astro-%EC%9D%B8%EC%88%98-review-2026/) | 테크 | 미발견 | 271.3 | 0 |
| 353 | [Cursor AI 브라우저 실험의 진실, 개발자가 알아야 할 것들](https://trendpulse.blog/cursor-ai-%EB%B8%8C%EB%9D%BC%EC%9A%B0%EC%A0%80-review-2026/) | 테크 | 미발견 | 270.8 | 0 |
| 359 | [2026년 개발자가 알아야 할 ASCII 렌더링 기술의 모든 것](https://trendpulse.blog/2026%EB%85%84-%EA%B0%9C%EB%B0%9C%EC%9E%90%EA%B0%80-%EC%95%8C%EC%95%84%EC%95%BC-review-2026/) | 테크 | 미발견 | 269.3 | 0 |
| 362 | [ASCII 렌더링 원리 완벽 해부: 픽셀이 아닌 문자의 세계](https://trendpulse.blog/ascii-%EB%A0%8C%EB%8D%94%EB%A7%81-%EC%9B%90%EB%A6%AC-review-2026/) | 테크 | 미발견 | 268.8 | 0 |
| 372 | [2026년 순수 C로 구현한 AI 이미지 생성, Flux 2 Klein 실전 분석](https://trendpulse.blog/2026%EB%85%84-%EC%88%9C%EC%88%98-c%EB%A1%9C-review-2026/) | 테크 | 미발견 | 267.8 | 0 |
| 381 | [2026 데이터 시각화 혁명, WebGPU 기반 차트 라이브러리](https://trendpulse.blog/%EB%8D%B0%EC%9D%B4%ED%84%B0-%EC%8B%9C%EA%B0%81%ED%99%94-%ED%98%81%EB%AA%85-review-2026/) | 테크 | 미발견 | 266.3 | 0 |
| 440 | [2026 자세 교정 앱으로 거북목 예방하는 개발자들의 비밀](https://trendpulse.blog/%EC%9E%90%EC%84%B8-%EA%B5%90%EC%A0%95-%EC%95%B1%EC%9C%BC%EB%A1%9C-review-2026/) | 건강 | 미발견 | 262.3 | 0 |
| 443 | [2026년 설득 글쓰기의 핵심, 먼저 관심을 사로잡는 법](https://trendpulse.blog/2026%EB%85%84-%EC%84%A4%EB%93%9D-%EA%B8%80%EC%93%B0%EA%B8%B0%EC%9D%98-review-2026/) | 생산성 | 미발견 | 261.8 | 0 |
| 458 | [2026 신형 애플 에어태그 2세대 성능 비교 및 구매 가이드](https://trendpulse.blog/%EC%8B%A0%ED%98%95-%EC%95%A0%ED%94%8C-%EC%97%90%EC%96%B4%ED%83%9C%EA%B7%B8-review-2026/) | 리뷰 | 미발견 | 260.8 | 0 |
| 473 | [2026 아마존 1만 6천명 감원, 테크업계 구조조정 시그널](https://trendpulse.blog/%EC%95%84%EB%A7%88%EC%A1%B4-1%EB%A7%8C-6%EC%B2%9C%EB%AA%85-review-2026/) | 비즈니스 | 미발견 | 258.8 | 0 |
| 488 | [2026 건축 렌더링 과도한 광택 제거하는 Antirender 프로젝트](https://trendpulse.blog/%EA%B1%B4%EC%B6%95-%EB%A0%8C%EB%8D%94%EB%A7%81-%EA%B3%BC%EB%8F%84%ED%95%9C-review-2026/) | 테크 | 미발견 | 256.8 | 0 |
| 500 | [2026 오픈소스 제로트러스트 네트워킹 Netbird 완벽 가이드](https://trendpulse.blog/%EC%98%A4%ED%94%88%EC%86%8C%EC%8A%A4-%EC%A0%9C%EB%A1%9C%ED%8A%B8%EB%9F%AC%EC%8A%A4%ED%8A%B8-%EB%84%A4%ED%8A%B8%EC%9B%8C%ED%82%B9-review-2026/) | 테크 | 미발견 | 254.8 | 0 |
| 506 | [2026 개발자들이 주목하는 Codex 앱, 코드 관리 생산성 3배 높이는 법](https://trendpulse.blog/%EA%B0%9C%EB%B0%9C%EC%9E%90%EB%93%A4%EC%9D%B4-%EC%A3%BC%EB%AA%A9%ED%95%98%EB%8A%94-codex-review-2026/) | 생산성 | 미발견 | 253.8 | 0 |
| 518 | [2026 FBI도 뚫지 못한 아이폰 잠금 모드 완벽 설정법](https://trendpulse.blog/fbi%EB%8F%84-%EB%9A%AB%EC%A7%80-%EB%AA%BB%ED%95%9C-review-2026/) | 테크 | 미발견 | 252.3 | 0 |
| 530 | [2026 Claude Opus 4.6 실사용 리뷰, AI 생산성 도구 완벽 분석](https://trendpulse.blog/claude-opus-%EC%8B%A4%EC%82%AC%EC%9A%A9-review-2026/) | 생산성 | 미발견 | 250.8 | 0 |
| 548 | [2026년 개발자 신원인증 플랫폼 Vouch, 취업시장을 바꾸는 이유](https://trendpulse.blog/2026%EB%85%84-%EA%B0%9C%EB%B0%9C%EC%9E%90-%EC%8B%A0%EC%9B%90%EC%9D%B8%EC%A6%9D-review-2026/) | 테크 | 미발견 | 247.3 | 0 |
| 566 | [Ladybird 브라우저가 Rust를 선택한 이유, 2026년 웹브라우저 판도 변화](https://trendpulse.blog/ladybird-%EB%B8%8C%EB%9D%BC%EC%9A%B0%EC%A0%80%EA%B0%80-rust%EB%A5%BC-review-2026/) | 테크 | 미발견 | 232.8 | 0 |
| 569 | [개발자가 학교에서 못 배운 실무 CS 기술, 2026년 완벽 가이드 (핵심키워드](https://trendpulse.blog/%EA%B0%9C%EB%B0%9C%EC%9E%90%EA%B0%80-%ED%95%99%EA%B5%90%EC%97%90%EC%84%9C-%EB%AA%BB-review-2026/) | 생산성 | 미발견 | 232.3 | 1 |
| 572 | [em대시가 많을수록 AI가 쓴 글? 2026년 콘텐츠 진정성을 지키는 글쓰기 원칙](https://trendpulse.blog/em%EB%8C%80%EC%8B%9C%EA%B0%80-%EB%A7%8E%EC%9D%84%EC%88%98%EB%A1%9D-ai%EA%B0%80-review-2026/) | 생산성 | 미발견 | 231.0 | 0 |
| 575 | [.online 도메인 선택하면 안 되는 이유와 올바른 도메인 선택 가이드](https://trendpulse.blog/online-%EB%8F%84%EB%A9%94%EC%9D%B8-%EC%84%A0%ED%83%9D%ED%95%98%EB%A9%B4-review-2026/) | 비즈니스 | 미발견 | 230.8 | 0 |
| 581 | [2026 스쿠트 항공 승무원 채용 합격 스펙 및 면접 전략 총정리](https://trendpulse.blog/%EC%8A%A4%EC%BF%A0%ED%8A%B8-%ED%95%AD%EA%B3%B5-%EC%8A%B9%EB%AC%B4%EC%9B%90-review-2026/) | 비즈니스 | 미발견 | 230.2 | 0 |
| 587 | [2026 운영체제 연령인증 의무화](https://trendpulse.blog/%EC%9A%B4%EC%98%81%EC%B2%B4%EC%A0%9C-%EC%97%B0%EB%A0%B9%EC%9D%B8%EC%A6%9D-%EC%9D%98%EB%AC%B4%ED%99%94-review-2026/) | 테크 | 미발견 | 229.3 | 0 |
| 590 | [스마트폰 압수수색과 디지털 프라이버시 권리 보호 완벽 가이드](https://trendpulse.blog/%EC%8A%A4%EB%A7%88%ED%8A%B8%ED%8F%B0-%EC%95%95%EC%88%98%EC%88%98%EC%83%89%EA%B3%BC-%EB%94%94%EC%A7%80%ED%84%B8-review-2026/) | 테크 | 미발견 | 228.8 | 0 |
| 617 | [위키피디아 관리자 계정 대규모 탈취 사태, 우리가 배워야 할 보안 교훈](https://trendpulse.blog/%EC%9C%84%ED%82%A4%ED%94%BC%EB%94%94%EC%95%84-%EA%B4%80%EB%A6%AC%EC%9E%90-%EA%B3%84%EC%A0%95-review-2026/) | 테크 | 미발견 | 223.3 | 0 |
| 623 | [맥북네오 리뷰: 기존 맥북과 무엇이 달라졌나, 2026 성능 비교 분석](https://trendpulse.blog/%EB%A7%A5%EB%B6%81%EB%84%A4%EC%98%A4-%EB%A6%AC%EB%B7%B0-%EA%B8%B0%EC%A1%B4-review-2026/) | 리뷰 | 미발견 | 222.8 | 0 |
| 635 | [AST 기반으로 코드 구조를 직접 편집하는 Ki Editor 완벽 가이드](https://trendpulse.blog/ast-%EA%B8%B0%EB%B0%98%EC%9C%BC%EB%A1%9C-%EC%BD%94%EB%93%9C-review-2026/) | 테크 | 미발견 | 220.8 | 0 |
| 641 | [2026 FrameBook 실사용 리뷰: 생산성 작업자를 위한 노트 도구의 새로운 기준](https://trendpulse.blog/framebook-%EC%8B%A4%EC%82%AC%EC%9A%A9-%EB%A6%AC%EB%B7%B0-review-2026/) | 리뷰 | 수집 후 미색인 | 219.8 | 0 |
| 644 | [내 손글씨를 전문 폰트로 만드는 법, FontCrafter 완벽 활용 가이드](https://trendpulse.blog/%EB%82%B4-%EC%86%90%EA%B8%80%EC%94%A8%EB%A5%BC-%EC%A0%84%EB%AC%B8-review-2026/) | 생산성 | 미발견 | 219.3 | 1 |
| 653 | [JavaScript 날짜 처리 9년의 혁명, Temporal API 완벽 정리](https://trendpulse.blog/javascript-%EB%82%A0%EC%A7%9C-%EC%B2%98%EB%A6%AC-review-2026/) | 테크 | 미발견 | 217.3 | 0 |
| 659 | [자동화가 일자리를 없앤다는 통념의 반전, ATM과 스마트폰이 증명한 진실](https://trendpulse.blog/%EC%9E%90%EB%8F%99%ED%99%94%EA%B0%80-%EC%9D%BC%EC%9E%90%EB%A6%AC%EB%A5%BC-%EC%97%86%EC%95%A4%EB%8B%A4%EB%8A%94-review-2026/) | 비즈니스 | 미발견 | 216.3 | 0 |
| 692 | [내 웹사이트 없이 개인 브랜딩은 없다, 2026년 소유형 미디어 전략](https://trendpulse.blog/%EB%82%B4-%EC%9B%B9%EC%82%AC%EC%9D%B4%ED%8A%B8-%EC%97%86%EC%9D%B4-review-2026/) | 비즈니스 | 미발견 | 210.8 | 0 |
| 695 | [2026년 Mistral Forge 완벽 가이드](https://trendpulse.blog/2026%EB%85%84-mistral-forge-review-2026/) | 테크 | 미발견 | 210.3 | 0 |
| 707 | [2026 안드로이드 미인증 앱 설치, 구글 새 24시간 사이드로딩 정책 완벽 정리](https://trendpulse.blog/%EC%95%88%EB%93%9C%EB%A1%9C%EC%9D%B4%EB%93%9C-%EB%AF%B8%EC%9D%B8%EC%A6%9D-%EC%95%B1-review-2026/) | 테크 | 미발견 | 208.3 | 0 |
| 734 | [버티컬 SaaS 창업 전략, 직접 현장에 뛰어들어 시장을 검증하는 법](https://trendpulse.blog/%EB%B2%84%ED%8B%B0%EC%BB%AC-saas-%EC%B0%BD%EC%97%85-review-2026/) | 비즈니스 | 미발견 | 203.8 | 0 |
| 737 | [2026년 Sora 실망기, 전문가들이 갈아탄 영상 제작 도구 비교](https://trendpulse.blog/2026%EB%85%84-sora-%EC%8B%A4%EB%A7%9D%EA%B8%B0-review-2026/) | 테크 | 미발견 | 203.3 | 0 |
| 752 | [Tailscale macOS 앱 완벽 가이드](https://trendpulse.blog/tailscale-macos-%EC%95%B1-review-2026/) | 생산성 | 수집 후 미색인 | 195.3 | 0 |
| 758 | [스웨덴 교실에서 스마트기기를 없앤 이유와 집중력 향상 효과 3가지](https://trendpulse.blog/%EC%8A%A4%EC%9B%A8%EB%8D%B4-%EA%B5%90%EC%8B%A4%EC%97%90%EC%84%9C-%EC%8A%A4%EB%A7%88%ED%8A%B8%EA%B8%B0%EA%B8%B0%EB%A5%BC-review-2026/) | 생산성 | 미발견 | 194.8 | 1 |
| 803 | [WireGuard 윈도우 최신판 출시](https://trendpulse.blog/wireguard-%EC%9C%88%EB%8F%84%EC%9A%B0-%EC%B5%9C%EC%8B%A0%ED%8C%90-review-2026/) | 테크 | 미발견 | 186.8 | 0 |
| 809 | [초저비용 창업 실전: 월 3만 원 기술 스택으로 수익형 사업 여럿 운영하는 법](https://trendpulse.blog/%EC%B4%88%EC%A0%80%EB%B9%84%EC%9A%A9-%EC%B0%BD%EC%97%85-%EC%8B%A4%EC%A0%84-review-2026/) | 비즈니스 | 미발견 | 185.3 | 0 |
| 815 | [워드프레스 플러그인 30개에 백도어](https://trendpulse.blog/%EC%9B%8C%EB%93%9C%ED%94%84%EB%A0%88%EC%8A%A4-%ED%94%8C%EB%9F%AC%EA%B7%B8%EC%9D%B8-30%EA%B0%9C%EC%97%90-review-2026/) | 테크 | 수집 후 미색인 | 184.3 | 0 |
| 821 | [2026 대한항공 신입 승무원 채용 합격 스펙 및 면접 전략 총정리](https://trendpulse.blog/%EB%8C%80%ED%95%9C%ED%95%AD%EA%B3%B5-%EC%8B%A0%EC%9E%85-%EC%8A%B9%EB%AC%B4%EC%9B%90-review-2026/) | 비즈니스 | 미발견 | 183.2 | 0 |
| 857 | [2026 프레임워크 랩탑 13 Pro 리뷰: 모듈형 노트북, 살 만한가?](https://trendpulse.blog/%ED%94%84%EB%A0%88%EC%9E%84%EC%9B%8C%ED%81%AC-%EB%9E%A9%ED%83%91-pro-review-2026/) | 리뷰 | 미발견 | 175.8 | 0 |
| 860 | [반값 트랙터로 시장 뒤집은 캐나다 스타트업의 역발상 전략](https://trendpulse.blog/%EB%B0%98%EA%B0%92-%ED%8A%B8%EB%9E%99%ED%84%B0%EB%A1%9C-%EC%8B%9C%EC%9E%A5-review-2026/) | 비즈니스 | 미발견 | 175.3 | 0 |
| 894 | [2026 아시아나항공 신입 승무원 채용 합격 스펙 및 면접 전략 총정리](https://trendpulse.blog/%EC%95%84%EC%8B%9C%EC%95%84%EB%82%98%ED%95%AD%EA%B3%B5-%EC%8B%A0%EC%9E%85-%EC%8A%B9%EB%AC%B4%EC%9B%90-review-2026/) | 비즈니스 | 미발견 | 164.2 | 0 |
| 897 | [BYOMesh 로라 메시 완벽 분석](https://trendpulse.blog/byomesh-%EB%A1%9C%EB%9D%BC-%EB%A9%94%EC%8B%9C-review-2026/) | 테크 | 미발견 | 163.8 | 0 |
| 900 | [헬스장에서 낯선 사람과 대화하면 운동 효율이 오르는 이유](https://trendpulse.blog/%ED%97%AC%EC%8A%A4%EC%9E%A5%EC%97%90%EC%84%9C-%EB%82%AF%EC%84%A0-%EC%82%AC%EB%9E%8C%EA%B3%BC-review-2026/) | 건강 | 미발견 | 163.3 | 0 |
| 909 | [2026 진에어 신입 승무원 채용 합격 스펙 및 면접 전략 총정리](https://trendpulse.blog/%EC%A7%84%EC%97%90%EC%96%B4-%EC%8B%A0%EC%9E%85-%EC%8A%B9%EB%AC%B4%EC%9B%90-review-2026/) | 비즈니스 | 미발견 | 162.2 | 0 |
| 963 | [2026년 신간으로 보는 스티브 잡스의 NeXT: 추방 이후 10년의 리더십 비밀](https://trendpulse.blog/2026%EB%85%84-%EC%8B%A0%EA%B0%84%EC%9C%BC%EB%A1%9C-%EB%B3%B4%EB%8A%94-review-2026/) | 비즈니스 | 미발견 | 152.3 | 0 |
| 972 | [2026년 프로젝트 구텐베르크 완벽 활용법, 무료 전자책 170만 권 이렇게 쓴다](https://trendpulse.blog/2026%EB%85%84-%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8-%EA%B5%AC%ED%85%90%EB%B2%A0%EB%A5%B4%ED%81%AC-review-2026/) | 생산성 | 미발견 | 151.3 | 0 |
| 975 | [2026년 AI 과의존 조직문화의 징후 5가지와 탈출 전략](https://trendpulse.blog/2026%EB%85%84-ai-%EA%B3%BC%EC%9D%98%EC%A1%B4-review-2026/) | 비즈니스 | 미발견 | 150.8 | 0 |
| 978 | [VPN이 필수 보안 도구가 된 이유: 2026년 온라인 프라이버시 완전 가이드](https://trendpulse.blog/vpn%EC%9D%B4-%ED%95%84%EC%88%98-%EB%B3%B4%EC%95%88-review-2026/) | 테크 | 수집 후 미색인 | 150.3 | 0 |
| 981 | [티웨이항공이 뽑는 승무원 인재상 5가지와 합격 자기소개서 전략](https://trendpulse.blog/%ED%8B%B0%EC%9B%A8%EC%9D%B4%ED%95%AD%EA%B3%B5%EC%9D%B4-%EB%BD%91%EB%8A%94-%EC%8A%B9%EB%AC%B4%EC%9B%90-review-2026/) | 비즈니스 | 미발견 | 150.2 | 0 |
| 984 | [2026년 기술 투자 전략: SaaS 구매보다 역량 구축이 맞는 순간](https://trendpulse.blog/2026%EB%85%84-%EA%B8%B0%EC%88%A0-%ED%88%AC%EC%9E%90-review-2026/) | 비즈니스 | 미발견 | 149.8 | 0 |
| 1014 | [6천만원 GPU 서버 직접 운영 1년, 솔직한 투자 수익 후기](https://trendpulse.blog/6%EC%B2%9C%EB%A7%8C%EC%9B%90-gpu-%EC%84%9C%EB%B2%84-review-2026/) | 테크 | 미발견 | 145.3 | 0 |
| 1032 | [SSD 활동 분석으로 방문자 추적하는 신기술, 개인정보 보호 대응법](https://trendpulse.blog/ssd-%ED%99%9C%EB%8F%99-%EB%B6%84%EC%84%9D%EC%9C%BC%EB%A1%9C-review-2026/) | 테크 | 미발견 | 135.8 | 0 |
| 1041 | [깃허브 계정 토큰 탈취 방지법: 개발자라면 지금 확인할 보안 설정 체크리스트](https://trendpulse.blog/%EA%B9%83%ED%97%88%EB%B8%8C-%EA%B3%84%EC%A0%95-%ED%86%A0%ED%81%B0-review-2026/) | 테크 | 미발견 | 133.8 | 0 |
| 1053 | [마우스 없이 맥·윈도우 완전 제어하는 키보드 생산성 툴 실전 가이드](https://trendpulse.blog/%EB%A7%88%EC%9A%B0%EC%8A%A4-%EC%97%86%EC%9D%B4-%EB%A7%A5%EC%9C%88%EB%8F%84%EC%9A%B0-review-2026/) | 생산성 | 미발견 | 131.3 | 0 |
| 1068 | [2026 영국 감시법 논란으로 본 디지털 프라이버시 완전 정리](https://trendpulse.blog/%EC%98%81%EA%B5%AD-%EA%B0%90%EC%8B%9C%EB%B2%95-%EB%85%BC%EB%9E%80%EC%9C%BC%EB%A1%9C-review-2026/) | 테크 | 미발견 | 128.3 | 0 |
| 1092 | [자율 에이전트 하나가 운영 계정을 파산시킨 실제 사례 분석](https://trendpulse.blog/%EC%9E%90%EC%9C%A8-%EC%97%90%EC%9D%B4%EC%A0%84%ED%8A%B8-%ED%95%98%EB%82%98%EA%B0%80-review-2026/) | 테크 | 미발견 | 124.3 | 0 |
| 1116 | [2026 EU 채팅감시법 논란, 메시지 보안 어떻게 바뀌나](https://trendpulse.blog/eu-%EC%B1%84%ED%8C%85%EA%B0%90%EC%8B%9C%EB%B2%95-%EB%85%BC%EB%9E%80-review-2026/) | 테크 | 미발견 | 108.1 | 0 |
| 1125 | [2026년 무료 아이콘 사이트 완전 정복: 북마크하면 후회 없는 리소스 총모음](https://trendpulse.blog/2026%EB%85%84-%EB%AC%B4%EB%A3%8C-%EC%95%84%EC%9D%B4%EC%BD%98-review-2026/) | 리뷰 | 미발견 | 106.8 | 0 |
| 1131 | [소니가 삭제한 영화 551편, 우리가 구매한 디지털 콘텐츠는 진짜 내 것인가](https://trendpulse.blog/%EC%86%8C%EB%8B%88%EA%B0%80-%EC%82%AD%EC%A0%9C%ED%95%9C-%EC%98%81%ED%99%94-review-2026/) | 테크 | 미발견 | 105.3 | 0 |
| 1173 | [타입스크립트7 출시, 네이티브 컴파일러로 속도 10배 향상](https://trendpulse.blog/%ED%83%80%EC%9E%85%EC%8A%A4%ED%81%AC%EB%A6%BD%ED%8A%B87-%EC%B6%9C%EC%8B%9C-%EB%84%A4%EC%9D%B4%ED%8B%B0%EB%B8%8C-review-2026/) | 테크 | 수집 후 미색인 | 97.7 | 0 |
| 1187 | [드론도 잡고 벽 너머 와이파이도 보는 RF 레이더 QuadRF](https://trendpulse.blog/%EB%93%9C%EB%A1%A0%EB%8F%84-%EC%9E%A1%EA%B3%A0-%EB%B2%BD-review-2026/) | 테크 | 미발견 | 96.3 | 0 |
| 1190 | [2026년 GPT-5.6 공개, AI 모델 경쟁 어디까지 왔나](https://trendpulse.blog/2026%EB%85%84-gpt-%EA%B3%B5%EA%B0%9C-review-2026/) | 테크 | 미발견 | 95.8 | 0 |
| 1245 | [LG 모니터 소프트웨어 몰래 설치 문제 총정리: 확인·삭제 방법](https://trendpulse.blog/lg-%EB%AA%A8%EB%8B%88%ED%84%B0-%EC%86%8C%ED%94%84%ED%8A%B8%EC%9B%A8%EC%96%B4-review-2026/) | 테크 | 미발견 | 88.2 | 4 |
| 1508 | [수면 영양제 뭐부터 시작할까? 멜라토닌·테아닌·유산균 실전 조합 가이드](https://trendpulse.blog/sleep-supplement-combo-guide-2026/) | 건강 | 발견·수집 전 | 83.7 | 1 |
| 1673 | [폐렴구균 예방접종 무료 대상과 접종 방법 총정리 (만 65세 이상, 2026년 기준)](https://trendpulse.blog/pneumococcal-vaccine-free-65-2026/) | 건강 | 수집 후 미색인 | 54.2 | 2 |
| 1694 | [2026 청년일자리도약장려금 지원 자격](https://trendpulse.blog/youth-job-leap-incentive-2026-checklist/) | 취업 | 미발견 | 44.0 | 0 |
| 1707 | [2026 현대자동차 9월 신입채용 지원자격·어학성적 체크리스트](https://trendpulse.blog/hyundai-september-2026-recruitment-eligibility/) | 취업 | 발견·수집 전 | 37.0 | 0 |
| 1713 | [면접 1분 자기소개: 신입·경력 작성법과 예시 점검](https://trendpulse.blog/%EB%A9%B4%EC%A0%91-1%EB%B6%84-%EC%9E%90%EA%B8%B0%EC%86%8C%EA%B0%9C-guide-2026/) | 취업 | 미발견 | 36.2 | 0 |
| 1743 | [2026 산업기사시험일정: 회차별 필기·실기 접수와 합격발표](https://trendpulse.blog/industrial-engineer-exam-2026/) | 취업 | 발견·수집 전 | 34.7 | 0 |
| 1748 | [2026 전기기사시험일정: 회차별 접수·발표와 남은 3회 일정](https://trendpulse.blog/electrical-engineer-exam-2026/) | 취업 | 미발견 | 34.2 | 0 |
| 1760 | [콜레스테롤낮추는방법: 식단·운동·생활습관 관리 핵심 가이드](https://trendpulse.blog/cholesterol-lowering-habits/) | 건강 | 발견·수집 전 | 26.1 | 0 |
| 1766 | [엑셀조건부서식 사용법: 셀 자동 색칠부터 수식 설정까지](https://trendpulse.blog/excel-conditional-formatting-2026/) | 생산성 | 수집 후 미색인 | 23.8 | 0 |
| 1772 | [노션사용법 상세 가이드: 첫 페이지부터 정리·템플릿 활용까지](https://trendpulse.blog/notion-page-template-guide-2026/) | 생산성 | 미발견 | 21.2 | 0 |
| 1787 | [엑셀표만들기: 표 생성·서식·머리글과 정렬·필터링 상세 가이드](https://trendpulse.blog/excel-table-format-filter-2026/) | 생산성 | 발견·수집 전 | 15.1 | 0 |
| 1799 | [고지혈증원인: 유전·식습관·비만과 관련 질환 핵심정리](https://trendpulse.blog/hyperlipidemia-causes-guide/) | 건강 | 수집 후 미색인 | 12.8 | 0 |
| 1808 | [VLOOKUP 사용법: 기본 수식부터 일치 방식과 오류 해결까지](https://trendpulse.blog/vlookup-excel-guide-2026/) | 생산성 | 수집 후 미색인 | 11.9 | 0 |
| 1829 | [한국수력원자력 채용: 2026년 체험형 청년인턴 지원 가이드](https://trendpulse.blog/khnp-intern-recruitment-2026/) | 취업 | 발견·수집 전 | 9.2 | 0 |
| 1840 | [OpenAI Dots란? AI 에이전트 기능·이용 조건·업무 활용 가이드](https://trendpulse.blog/openai-dots-ai-agent-guide/) | 테크 | 발견·수집 전 | 8.9 | 2 |
| 1886 | [2027년부터 달라지는 저소득층 구분모집: 대상·요건 핵심정리](https://trendpulse.blog/low-income-recruitment-2027/) | 취업 | 발견·수집 전 | 6.0 | 0 |
| 1894 | [2026 한국언론진흥재단 채용: 정규직 신입 지원·일정 총정리](https://trendpulse.blog/kpf-recruitment-2026/) | 취업 | 미발견 | 5.4 | 0 |
| 1897 | [2026 도시가스 대졸 신입 채용: 코원·충청·강원·전남 비교](https://trendpulse.blog/citygas-recruitment-2026/) | 취업 | 미발견 | 5.4 | 0 |
| 1907 | [엑셀차트만들기: 데이터 선택부터 종류별 차트·제목 편집 가이드](https://trendpulse.blog/excel-chart-guide/) | 생산성 | 발견·수집 전 | 4.7 | 0 |
| 1919 | [자궁경부암검사 방법과 준비사항, 세포검사·HPV검사 결과 이해](https://trendpulse.blog/cervical-screening-guide-2026/) | 건강 | 미발견 | 4.1 | 0 |
| 1927 | [2026 산업안전기사 응시자격과 시험 일정·필기·실기 준비](https://trendpulse.blog/industrial-safety-engineer-2026/) | 취업 | 발견·수집 전 | 4.0 | 0 |
| 1953 | [러시아 원인불명 폐렴(폐페스트 의심): 국내 위험도와 입국자 수칙](https://trendpulse.blog/russia-pneumonia-korea-2026/) | 건강 | 미발견 | 1.3 | 0 |
| 1962 | [게임 파인더(Game finder) 10월 14일 미국 출시 시작: 추천 기능](https://trendpulse.blog/game-finder-launch-korea-2026/) | 테크 | 미발견 | 0.3 | 0 |

집계 산출물: 사용자 지정 iCloud 작업 루트의 wp-auto-blog/index-diagnosis-20261015/diagnosis.json, unindexed-98.csv. 전체 HTML·전체 본문·비밀정보·계정 식별자는 저장하지 않았다. 조사 문서만 Git에 기록하며 운영 변경은 적용하지 않았다.
