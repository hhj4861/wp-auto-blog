# GA4·AdSense 실제 연결 — 2026-10-15

- 목표: 기존 Google 태그와 올바른 TrendPulse 속성을 대조하고 독자 이벤트의 실제 수신 및 수익 연동을 확인한다.
- 범위/소유: 현재 Codex 단독, workers/Claude OFF. 코드 변경 없이 이미 머지된 PR #117의 reader 자산을 기존 지원 13편에 갱신하고 기존 GA4 관리 UI를 사용한다. 원문/광고/메타데이터 보존 및 백업을 전제로 한다.
- 기준: main 19f55cb. 기존 다른 세션의 docs/design/trendpulse-reading-concept.html 삭제는 보존한다.
- 완료 기준: 정확한 도메인·속성·태그 대조, 실제 요약/메뉴/섹션 수신, 이벤트 범위 맞춤 정의, 승인된 AdSense 연결, 데이터 표시 대기/미확인 구분, 자체 문서 검증·커밋·push.
- 현재: 메뉴형 지원 글 13편 모두 실제 적용·백업·저장 후 검증·공개 HTTP 200·계측 코드 확인 완료. GA4에서 실제 요약/메뉴/섹션 이벤트 수신 및 글 ID 1894 확인. 맞춤 측정기준 5개 저장 완료. 사용자의 최종 연결 승인 후 AdSense의 ‘링크 만들기’를 실행했고 연결 목록에 정확한 TrendPulse 속성, GA4 유형, 2026-10-15 연결일이 표시됨을 확인했다. 연결 설정과 계측 적용은 완료했으며 실제 수익 데이터 행은 아직 미확인이다.
- 원격 저장소가 공개이므로 AdSense 잔액/수입·원본 계정 보고서·계정 이메일·인증정보는 Git과 공개 산출물에 기록하지 않는다. 공개 글 ID/태그 및 구성 상태·검증 실행만 기록한다.

## 확인과 판단 수정

- 기본 GA4 진입은 다른 속성이어서 그 값을 TrendPulse로 사용하지 않았다. AdSense 속성 목록과 TrendPulse 웹 스트림 URL을 대조했다. 공개 Google 태그 GT-W6JVZFTH와 GA4 G-MR4Z0HZ1M7의 연결을 Google 태그 UI에서 확인했다. 태그 품질 ‘아주 좋음’, 최근 48시간 데이터 수집 활성.
- 제한된 브라우저 읽기 환경의 typeof window.gtag 결과와 HTML 문자열 검색만으로 gtag 결함을 의심했으나, LiteSpeed가 google_gtagjs-js-after를 base64 data: 스크립트로 변환한 것을 확인해 판단을 철회했다. 실제 소스에는 표준 dataLayer/gtag/config 초기화가 있다. 새로운 태그·큐·fallback은 구현하지 않았다. 생성했던 빈 구현 worktree와 로컬 작업 브랜치는 소유·무변경 확인 후 정상 정리했다.
- 확실한 차이는 기존 13편의 인라인 reader가 이전 코드였다는 점이다. 대표 1894에 이미 머지된 코드를 적용해 공개 스크립트에서 measurement-v1/summary_view를 확인했다.
- GA4 이벤트 범위 맞춤 정의: article_id(글 ID), article_category(글 카테고리), section_id(읽기 섹션), reader_version(읽기 포맷 버전), view_mode(보기 모드). 0개에서 5개로 저장·목록 확인. 글 ID는 값이 많아질 경우 표준 페이지 경로를 우선 활용하며 불필요한 추가 고유 ID 차원을 만들지 않는다.
- 대표 원문 미리보기: https://github.com/hhj4861/wp-auto-blog/actions/runs/38701858601 success.
- 대표 실제 적용: https://github.com/hhj4861/wp-auto-blog/actions/runs/38702323730 success, post 1894, 원문 백업 artifact 11957230354. 사용자 요청 범위 안에서 기존 코드를 적용했으며 새 PR 머지/본문 재작성/광고 클릭은 수행하지 않았다.

## 계정 연결과 데이터 해석

AdSense 연결은 [공식 절차](https://support.google.com/adsense/answer/6084409?hl=en)에 따라 TrendPulse 속성만 선택했다. 연결 전 해당 계정은 GA4 미연결 상태였다. 데이터가 GA4에 나타나기까지 최대 24시간이 걸릴 수 있으며, 연결 설정 성공과 수익 행의 실제 확보를 구분한다. [연결 후 보고서 위치](https://support.google.com/adsense/answer/98148?hl=en)는 수익 창출의 게시자 광고/탐색이다. 기존 승인 사용자에게 수익 데이터와 연결 사용자 이메일이 표시될 수 있다는 안내를 사용자에게 알렸으며 2026-10-15 사용자의 최종 ‘응’ 승인 후 연결을 실행했다.

검증 방문과 이벤트는 운영자 QA이며 실제 독자의 증가나 수익 개선으로 해석하지 않는다. 개인 체크, URL 쿼리, 광고 클릭의 추가 수집 경로는 없다. 서비스 계정·새 토큰·새 API 비밀번호는 생성하지 않았다. AdSense → GA4 데이터 공유는 사용자 최종 승인 후 기존 계정 UI에서 연결했다.

## 실제 수신과 13편 적용 검증

- GA4 속성 517601979, 웹 스트림 13232384858. 보고 시간대는 대한민국 GMT+09:00, 통화는 USD로 확인했으며 변경하지 않았다.
- 실시간 보고서에서 summary_view / reader_menu_select / reader_section_view가 각각 QA 1건 수신됨을 확인했다. reader_menu_select의 article_id 매개변수 값을 열어 1894를 확인했다. 코드에 이벤트 이름이 존재한다는 검사와 실제 GA 서버 수신을 구분했다.
- 대표 글 및 나머지 12편 모두 먼저 exact ID/slug dry-run을 통과했다. 기존 posting 동시성 잠금으로 직렬 적용했으며 13개 실행 모두 completed/success 및 verified=True다.
- 13편 각각 reader-reflow-backups 실행 artifact가 만료되지 않았고 0바이트가 아님을 확인했다. 백업 보존 기간은 90일이다. 기존 원문·광고·메타데이터 보존 검사와 저장 후 원문 재조회 검증을 사용했다.
- 공개 URL 13개 모두 HTTP 200, wpab-category-reader 스크립트 1개, base64 해제 후 measurement-v1 / summary_view / reader_menu_select / reader_section_view 포함 확인.
- 새 글 작성, 기존 본문 재작성, 새로운 광고 배치, 광고 클릭, 애플리케이션 코드 변경은 수행하지 않았다. 구형 일반 글 381편은 이번 적용 범위에 포함하지 않았다.

| 글 | 적용 실행 | 원본 백업 artifact |
|---|---|---|
| [한국언론진흥재단](https://trendpulse.blog/kpf-recruitment-2026/) | 38702323730 | 11957230354 |
| [도시가스 채용](https://trendpulse.blog/citygas-recruitment-2026/) | 38703817672 | 11957163322 |
| [엑셀 차트](https://trendpulse.blog/excel-chart-guide/) | 38703803025 | 11957955574 |
| [온디바이스 AI](https://trendpulse.blog/on-device-ai-npu-2026/) | 38703838203 | 11957641376 |
| [자궁경부암 검진](https://trendpulse.blog/cervical-screening-guide-2026/) | 38703799227 | 11956858568 |
| [PT 면접](https://trendpulse.blog/pt-interview-preparation/) | 38703826843 | 11957113714 |
| [산업안전기사](https://trendpulse.blog/industrial-safety-engineer-2026/) | 38703821721 | 11957950793 |
| [AI 창업 세제](https://trendpulse.blog/ai-startup-tax-support-2026/) | 38703806487 | 11957720956 |
| [전세사기 피해 결정](https://trendpulse.blog/jeonse-victim-decision-2026/) | 38703814560 | 11956838725 |
| [러시아 폐렴](https://trendpulse.blog/russia-pneumonia-korea-2026/) | 38703795502 | 11956838464 |
| [화재 안전 사업](https://trendpulse.blog/fire-safety-project-2026/) | 38703810371 | 11957910782 |
| [Ask Play](https://trendpulse.blog/ask-play-app-comparison-2026/) | 38703834329 | 11957676265 |
| [Game Finder](https://trendpulse.blog/game-finder-launch-korea-2026/) | 38703830475 | 11958030732 |

## 연결 완료와 측정 대기

- AdSense에서 trendpulse.blog / 517601979 연결을 최종 사용자 승인 후 실행했다. 실제 연결 목록은 총 1개이며 계정/속성 trendpulse.blog, 속성 ID 517601979, 유형 Google 애널리틱스 4, 연결일 2026-10-15를 표시한다. 연결 전 미연결 목록에서 이 행이 생성된 것을 확인했다. 수익 행의 실제 확보와 수익 개선은 아직 확인하지 않았으며 표시에는 최대 24시간이 걸릴 수 있다.
- 계정 화면의 iCloud 캡처 저장은 자동 승인 검토에서 거절됐다. 개인정보 열을 제외한 연결 결과도 계정 연결 메타데이터 동기화 우려로 저장이 거절되어 파일을 저장하지 않았다. 실제 연결 결과는 브라우저 목록에서 확인했고 결과 탭을 유지한다.
- 기존 일일 GSC 리포트는 검색 측정 보고서다. 이번 GA4 UI 설정만으로 GSC JSON에 GA4/AdSense 자동 API 수집이 추가됐다고 주장하지 않는다.
- 다음 판단은 운영자 QA를 제외한 실제 유입·읽기 행동과 연결 후 확보되는 글별 수익 데이터를 비교하는 것이다. 계측 설치는 수익 증가나 최적화 완료를 의미하지 않는다.
