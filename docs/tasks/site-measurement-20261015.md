# 전체 공개 글 측정 — 2026-10-15

- 목표: 색인/검색 성과/수요/행동/수익의 결손을 구분하고 개선 검토 후보를 만든다.
- 소유: 현재 Codex 단독, workers/Claude OFF. main의 기존 디자인 문서 삭제는 본 작업 밖.
- 기준: aaf35a1, feat/site-measurement-20261015. 설계: docs/reports/seo-demand-measurement-20261015.md.
- 범위: 인증 공개 인벤토리, 완결 GSC 기간/페이지네이션, 분할 색인·체크포인트, JSON/CSV/HTML 보고서, 선택적 외부 측정 자료 입력, reader 행동 이벤트.
- 완료 기준: 미확인/대기/실패를 0으로 채우지 않음, 공개 글 전체 포함, 누락 shard 명시, 원문/광고 불변, 의미 있는 Python/JS 테스트, branch의 실제 읽기 전용 실행, 커밋·push·PR. 머지/운영 reader 갱신/GA4 계정 변경은 별도 승인 경계.
- 현재: 구현·관련 검증·작업 브랜치 push 및 실제 읽기 전용 수집 검증 완료. GA4/AdSense/검색량 계정의 연결 및 실제 GA4 수신은 아직 확인하지 않았다.
- 다음: 구체적인 PR 머지 승인 후 운영 예약 수집 반영. 운영 reader 자산 갱신과 GA4 실제 수신 확인은 별도로 남아 있다.

- 첫 로컬 실행: reader 계측/기존 메뉴 DOM 테스트 통과. 재사용 venv에 pytest-cov가 없어 기존 pyproject의 커버리지 옵션 파싱에서 Python 테스트가 시작되지 않았다. 의존성 환경을 보완한 뒤 대상 테스트/대상 모듈 커버리지를 실행한다.

- 캐시 회귀 1건이 빈 dict를 새 dict로 바꾸는 문제를 발견했다(38 통과, 대상 모듈 커버리지 85%). None일 때만 새 캐시를 만들도록 수정해 체크포인트/재사용 계약을 복구한다.

## 구현 계약과 사용

- WordPress 인증 GET만 사용해 현재 publish 집합을 읽고 사이트맵 접근과 분리한다. 원장에만 남은 초안/이전 URL은 집합에 들어오지 않는다.
- Pacific 오늘에서 3일 여유를 둔 마지막 날짜까지 최근 7일/28일/직전 28일을 수집한다. 발행 후 7/28일 고정 창은 기존 report_keyword_performance.py의 별도 기능이며 이번 표는 rolling 기간이다.
- GSC 페이지 합계와 페이지×검색어×기기×국가를 분리한다. query_all은 페이지네이션 상한을 초과하면 truncated를 명시한다. 공개/비공개 검색어 차이 때문에 상세 행 합계와 페이지 합계가 같다고 가정하지 않는다.
- 4개 shard는 동일한 inventory_id로 결합한다. 누락 shard와 실패/대기 상태도 모든 공개 글 행에 남는다. 성공 색인은 7일, 미색인 결과는 1일 캐시하되 글 변경 시 다시 확인한다. 실패는 캐시하지 않는다.
- 100노출/2클릭 이하 같은 값은 검토 후보를 좁히는 보수적 기본값일 뿐, 제목 결함이나 수요 부족의 판정 기준이 아니다. 자동 수정/삭제 경로는 없다.
- reader는 기존 window.gtag가 있을 때만 전송하고 외부 스크립트를 로드하지 않는다. window.wpabReaderMeasurement=false로 전송을 끌 수 있다. 요약/섹션 대표 영역 50% 이상이 활성 문서에서 1초 연속 보이면 노출을 1회 기록한다. 완독/만족을 의미하지 않는다.
- GA4 event: summary_view, reader_section_view, reader_menu_select, official_source_click, related_article_click, affiliate_outbound_click. 개인 체크·URL 쿼리·링크 전문·광고 클릭은 추가 수집하지 않는다. 기존 GA4 일반 click과 의미별 이벤트를 단순 합산하지 않는다.
- 머지 후 신규 글/승인된 reader 자산 갱신부터 계측 코드가 들어간다. 현재 공개 글은 이 브랜치 작업으로 수정하지 않는다. GA4 실제 수신 및 article_id/article_category/section_id/reader_version/view_mode의 이벤트 범위 맞춤 측정기준 등록은 운영 후 확인이 필요하다. https://developers.google.com/analytics/devguides/collection/ga4/event-parameters
- GA4/AdSense/시장 검색량의 새 계정 권한은 만들지 않았다. 연결이 없는 필드는 not_connected로 남는다. 기존 도구에서 내보낸 값은 --signals JSON으로 검증 후 결합할 수 있다.

로컬/runner CLI (출력 경로는 지정 작업 폴더나 runner.temp):

    python scripts/site_measurement.py inventory --output /approved-output/inventory.json
    python scripts/site_measurement.py collect --inventory /approved-output/inventory.json --output /approved-output/shard-0.json --cache /approved-output/index-cache.json --shard 0 --shards 4
    python scripts/site_measurement.py merge --inventory /approved-output/inventory.json --parts /approved-output/parts --output /approved-output/report.json --signals /approved-output/signals.json

외부 측정 자료 예시(임의 예시이며 운영 측정값 아님):

```json
{"schema_version":1,"site":"https://trendpulse.blog","posts":[{"url":"https://trendpulse.blog/example/","demand":{"status":"reported","source":"Google Keyword Planner export","engine":"google","region":"KR","monthly_searches":100,"period_start":"2026-09-01","period_end":"2026-09-30","checked_at":"2026-10-15T00:00:00+00:00"}}]}
```

engagement는 sessions/section_views/official_clicks/affiliate_clicks, monetization은 revenue/cost와 currency를 사용한다. 모두 status/source/period_start/period_end/checked_at을 명시한다. 기간이 다른 자료는 같은 기간의 인과 비교로 취급하지 않는다. 값이 없으면 0으로 채우지 않는다.

## 로컬 검증

- 관련 Python 68개 통과, 새 src.site_measurement 모듈 커버리지 86.6%(전체 저장소 커버리지 아님). Python 3.14에서 기존 Google SDK deprecation 경고 1건.
- 계측 DOM: 활성 노출/비활성 탭·숨김 패널/중복 방지, GA 함수 호출, 링크 분류, 개인 체크 및 쿼리 비전송, 광고 보존 통과. 기존 reader DOM 회귀도 통과.
- Workflow YAML, 4분할·fail-fast=false·부분 산출물 always 보존·contents:read 확인. 실제 branch 실행 결과는 아래 기록.

- 자체 검토: URL Inspection은 shard당 시작 간격 0.5초로 제한해 4분할 합계 최대 약 480회/분으로 조절했다. 캐시 적중은 호출하지 않는다. Google 공식 제한(사이트별 600회/분, 2,000회/일): https://developers.google.com/webmaster-tools/limits . 기존 별도 작업의 일일 사용량까지 예약하는 전역 쿼터 관리자는 아니며 초과 오류는 미확인으로 보존한다.

- Chrome 실제 엔진의 로컬 가상 GA 수신기로 노출 3건·메뉴 1건·공식 링크 1건의 분류, 개인 체크 미전송과 링크 쿼리 미포함을 확인했다. 이는 GA4 서버/운영 수신 증거가 아니다. 검증용 서버/탭은 종료한다.
- 전체 shard 인증 실패 시에도 인벤토리 기준 미확인 보고서를 남기도록, report의 shard 다운로드 실패 후 merge를 계속한다. 완전 실패를 성공 수집으로 처리하지 않는다.

- 첫 실제 실행 38691585220은 394편/4개 shard/색인 394편까지 모두 수집했으나 상세 검색 성과를 unavailable로 보존해 report 단계가 실패했다. 가설: 사이트 전체 검색에는 홈 URL도 있으며, 기사 URL 정규화 예외가 전체 상세 집합을 무효화했다. 홈/타사이트 행만 건너뛰는 page-total과 같은 계약을 상세 집합에도 적용하고 회귀 테스트로 재현·수정한다. 기존 색인 캐시를 재사용해 재검증한다.

## 실제 읽기 전용 검증 결과

- 성공 실행: https://github.com/hhj4861/wp-auto-blog/actions/runs/38692181309 (코드 7cffa96, inventory/4개 collect/report 모두 success). 이전 실패 실행 38691585220은 수정 이력으로 남겼다.
- 현재 publish 394편 모두 포함: 기존 형식 381, 메뉴형 13. 4개 shard가 같은 인벤토리로 결합됐고 중복/누락 없이 색인 394편, 검색 상세 수집 상태 394편 reported다. 상세 행은 총 125개이며, 행이 없는 글은 검색어별 노출 0이라고 판정하지 않는다.
- URL Inspection: 색인 완료 296, Google 미발견 72, 발견 후 미색인 14, 크롤링 후 미색인 12. 이번 성공 실행은 앞선 실행의 394개 색인 결과를 모두 캐시로 재사용했다. 현재 판정의 조회시각은 각 글 checked_at에 남아 있다.
- 최근 28일(2026-09-14~10-11 PT): 보고 행 있음 205편, 보고 행 없음 184편, 기간 뒤 신규 글 수집 대기 5편. 보고 행 없음은 수요 0/삭제 사유가 아니다.
- 표본·발행기간 부족 검토 391편, 클릭 검토 후보 1편(ID 1661 GSAT, 103노출·1클릭·평균 6.10위). 표본 조건을 충족한 후보일 뿐 원인 확정이나 즉시 수정 대상은 아니다.
- 수요/행동/수익의 외부 자료는 이번 수집에 연결되지 않았다. Google 수요 미측정 394편을 그대로 표시한다. collection_complete는 요청한 API 수집 단계의 완료이며, 모든 검색어 공개/전체 시장수요·모든 계정 연결 완료를 뜻하지 않는다. Search Analytics 자체가 반환 가능한 상위 행과 익명화 제한을 가진다: https://developers.google.com/webmaster-tools/v1/searchanalytics/query .
- HTML/CSV/JSON: 위 실행의 measurement-report artifact(90일 보존). 로컬 사본은 사용자 지정 iCloud 작업 루트의 wp-auto-blog/site-measurement-20261015/live-run-38692181309/report.*에 저장했다. 인증정보/본문은 보고서에 저장하지 않았다.
- 최종 Python 68개, JS 2개 suite 통과. Chrome 가상 수신 검증 후 탭과 loopback 서버가 실제 종료된 것을 확인했다. Git diff --check 통과. 운영 글/광고/계정 설정은 변경하지 않았다.
