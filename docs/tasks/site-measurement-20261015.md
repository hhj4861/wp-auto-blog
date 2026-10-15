# 전체 공개 글 측정 — 2026-10-15

- 목표: 색인/검색 성과/수요/행동/수익의 결손을 구분하고 개선 검토 후보를 만든다.
- 소유: 현재 Codex 단독, workers/Claude OFF. main의 기존 디자인 문서 삭제는 본 작업 밖.
- 기준: aaf35a1, feat/site-measurement-20261015. 설계: docs/reports/seo-demand-measurement-20261015.md.
- 범위: 인증 공개 인벤토리, 완결 GSC 기간/페이지네이션, 분할 색인·체크포인트, JSON/CSV/HTML 보고서, 선택적 외부 측정 자료 입력, reader 행동 이벤트.
- 완료 기준: 미확인/대기/실패를 0으로 채우지 않음, 공개 글 전체 포함, 누락 shard 명시, 원문/광고 불변, 의미 있는 Python/JS 테스트, branch의 실제 읽기 전용 실행, 커밋·push·PR. 머지/운영 reader 갱신/GA4 계정 변경은 별도 승인 경계.
- 현재: 구현·로컬 검증 및 작업 브랜치 push 완료, 실제 수집 검증 중. GA4/AdSense/검색량 계정의 연결 및 실제 GA4 수신은 아직 확인하지 않았다.
- 다음: 구현과 로컬 검증 후 branch에서 읽기 전용 데이터 수집 E2E.

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

- 관련 Python 67개 통과, 새 src.site_measurement 모듈 커버리지 86%(전체 저장소 커버리지 아님). Python 3.14에서 기존 Google SDK deprecation 경고 1건.
- 계측 DOM: 활성 노출/비활성 탭·숨김 패널/중복 방지, GA 함수 호출, 링크 분류, 개인 체크 및 쿼리 비전송, 광고 보존 통과. 기존 reader DOM 회귀도 통과.
- Workflow YAML, 4분할·fail-fast=false·부분 산출물 always 보존·contents:read 확인. 실제 branch 실행은 다음 단계.

- 자체 검토: URL Inspection은 shard당 시작 간격 0.5초로 제한해 4분할 합계 최대 약 480회/분으로 조절했다. 캐시 적중은 호출하지 않는다. Google 공식 제한(사이트별 600회/분, 2,000회/일): https://developers.google.com/webmaster-tools/limits . 기존 별도 작업의 일일 사용량까지 예약하는 전역 쿼터 관리자는 아니며 초과 오류는 미확인으로 보존한다.

- Chrome 실제 엔진의 로컬 가상 GA 수신기로 노출 3건·메뉴 1건·공식 링크 1건의 분류, 개인 체크 미전송과 링크 쿼리 미포함을 확인했다. 이는 GA4 서버/운영 수신 증거가 아니다. 검증용 서버/탭은 종료한다.
- 전체 shard 인증 실패 시에도 인벤토리 기준 미확인 보고서를 남기도록, report의 shard 다운로드 실패 후 merge를 계속한다. 완전 실패를 성공 수집으로 처리하지 않는다.
