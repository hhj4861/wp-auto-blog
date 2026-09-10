# CAK 검색 지표 → 블로그 주제 선정

## 자동 연결

CAK의 `keyword-intel-sync.yml`이 일별 DataLab 수집과 검색광고 조회 후
`blog-keyword-candidates.json`을 `blog-keyword-candidates` Actions artifact로 내보낸다.
WP의 09:30 선정 작업과 11시 카테고리 큐 작업이 이를 받아 기존 시장 후보 풀에 합친다.
CAK의 코드를 WP에 복사하거나 텔레그램 메시지를 파싱하지 않는다.

- 저장소: `hhj4861/commerce-automation-kit`, 워크플로: `keyword-intel-sync.yml`.
- 성공한 `main`의 예약/수동 실행만 허용한다. 최근 24시간의 최신 자료를 찾으며,
  새 실행이 진행 중이면 유효한 직전 성공 자료를 사용할 수 있다.
- JSON 계약: `schemaVersion=1`, `kind=cak_keyword_candidates`, `profile=blog-kr`.
  기존 `BlogExport` 및 opportunity 점수 의미는 유지한다.
- 원본 후보는 최대 80개다. 182개 `g2-seeds`의 건강·뷰티·이너뷰티 범위이므로
  **건강 카테고리에만** 입력한다. 취업·생활정보는 기존 시드에서 수집한다.
- GitHub artifact 보관은 1일, 지표 유효기간은 수집 시각 기준 최대 24시간이다.
  원본 신호 만료, 월검색량 측정 시각, 관측일의 KST 기준 0~3일 지연을 별도로 검사한다.
  보고서가 36시간 이내여도 CAK 근거가 만료되면 재사용하지 않는다.

다운로더는 `CODEX_SECRET_WRITE_TOKEN`을 해당 단계에서 GitHub 읽기에만 사용한다.
이 Secret에는 CAK 저장소 Actions 읽기 권한이 있어야 한다. 토큰을 분석기 환경에 전달하지 않고,
외부 서명 다운로드 URL에도 인증 헤더를 보내지 않는다. 정확한 파일명 하나만 읽고,
압축 전·후 2MB 한도를 적용한다. 다운로드 시작 전 이전 임시 입력을 지우며 성공 시 원자적으로 교체한다.

`CAK_KEYWORD_CANDIDATES_FILE`은 runner 임시 JSON 경로,
`CAK_KEYWORD_CANDIDATES_FETCH_STATUS_FILE`은 안전한 전송 진단 JSON 경로다.
보고서의 `cak_import`와 선정 항목의 `cak_provenance`에 수집 실행 번호·commit SHA·artifact ID,
관측일·원본 시드·직접/연관 관계를 남긴다. 인증 실패·파일 없음·만료·형식 오류·정상 빈 목록은 구분한다.
입력이 없거나 유효하지 않으면 사유를 기록하고 기존 네이버 후보 탐색을 계속한다.
CAK 자료 없이 통과한 결과를 CAK 기반 결과로 표시하지 않는다.

## 지표와 우선순위

1. DataLab 응답의 `timeUnit=date`가 보존된 신호만 사용한다. 과거 DB에 단위가 없으면
   현재 환경변수로 추정하지 않는다. 중복 날짜, 잘못된 지수, 실제 전일 누락을 제외한다.
2. 직전 7일 중 최소 5일을 관측해야 한다. 평균은 **관측된 날만** 계산하며 실제 0은 포함한다.
   누락을 0으로 만들지 않는다. 전일 또는 평균이 0이면 해당 상승률과 hot은 null이다.
3. hot은 기존 55/30/15 배점과 상승률 0~300% 제한을 유지한다. `dayPct`·`baselinePct`는
   퍼센트 단위이며 Google Trends의 배율과 혼용하지 않는다.
4. 검색광고 키워드는 공백 제거 후 정확히 일치해야 한다. 연도나 관련 단어를 제거하지 않는다.
   PC와 모바일이 모두 측정된 경우만 합산한다. `< 10`, 누락, 음수, 소수, 잘못된 문자열은
   상태로 남기며 0이나 임의 숫자로 바꾸지 않는다. 광고 경쟁도는 SEO 난이도로 쓰지 않는다.
5. 월검색량 500 이상인 직접 후보는 기존 상시 수요 후보 풀에 합칠 수 있다.
   **급상승 후보는 월 1,000 이상 + hot 20 이상 + 전일·7일 평균 대비 모두 상승**해야 한다.
   미발행 급상승 시드 최대 5개는 기존 네이버 연관 검색어 API로 세부 질문을 추가 수집한다.
6. 연관 검색어는 자신의 월검색량을 사용한다. 시드의 상승률을 연관 검색어의 상승률로
   복사하지 않는다. 직접 급상승 후보만 자신의 hot/10을 최대 10점으로 반영하고,
   같은 후보의 Google Trends 보너스는 중복 가산하지 않는다.
7. 급상승 직접·연관 후보와 구체적인 질문형·수요 상위 후보를 섞어 첫 조사 대상에 도달하게 한다.
   최종 선정은 기존 공식 본문·카테고리·검색 의도·기한 검증을 모두 통과해야 한다.

발행된 키워드는 영구 이력과 WordPress 제목·초안·예약 글에서 제외한다.
지표 연결은 공백만 제거하지만 **발행 중복 차단은 연도·문장부호 차이도 정규화**한다.
CAK 후보도 선정 → 캐시 → 큐 → 작성 직전 → WordPress 저장 직전의 동일한 검사를 받는다.

## 발행 없는 점검

CAK Actions의 `keyword-intel sync`를 `export_only=true`, `send_telegram=false`로 실행하면
수집·검색량 조회·artifact 생성만 수행한다. Telegram과 D1 게시를 건너뛴다.
수집은 API 호출을 사용하므로 이미 유효한 artifact가 있으면 재사용한다.
WP의 `Blog Keyword Select`는 선정 보고서만 생성하며 글을 발행하지 않는다.
`auth_check_only`·`research_check_only`에서는 CAK 다운로드도 건너뛴다.

로컬 파일만 확인할 때는 `src.cak_candidates.load_candidate_export(path)`를 사용한다.
전송을 강제 확인할 때는 아래 명령을 쓰며, `--require` 없이 실행하면 수집 불가 시 정상 네이버 경로로 대체한다.

```bash
python scripts/fetch_cak_candidates.py --output /tmp/cak-keyword-candidates.json \
  --status-file /tmp/cak-fetch-status.json --require
```

테스트는 외부 API·게시 없이 잘못된 시간 단위, 누락일, 마스킹, 만료, 지표 연결,
연관어의 별도 월량, 중복 차단, 자격 증명 분리와 ZIP 한도를 검증한다.

## 기존 수동 importer

`scripts/ingest_keyword_intel.py`와 `data/cak_export.sample.json`은 이전
`BlogExport`를 `source=cak_keyword_intel` 수동 큐에 넣는 별도 경로로 유지한다.
CAK `analyze --profile blog-kr --json`은 이 계약을 지원한다.
자동 시장 선정에는 이 importer를 연결하지 않는다. 질문 원문도 큐에 저장하지 않는다.
자동 발행은 위의 측정 지표 계약과 `category_market_v1` 검증 경로를 사용한다.

`candidate_check_only=true`는 CAK artifact의 실제 다운로드 권한과 지표 계약만 검사한다.
Codex 인증을 복원하지 않고 카테고리 보고서·큐·발행 이력을 변경하지 않는다.
인증/웹검색 점검도 선택하면 기존 점검을 우선한다.
