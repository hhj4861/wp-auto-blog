# 리뷰 출처 수집 실패 수정 및 검증 — 2026-09-29

## 확인한 문제

운영 실행 36523341523은 후보 선별에서 실패했으며 새 포스트는 발행되지 않았다. 실패 이력을 피하는 기능은 작동했지만, 후보를 뒷받침할 공식 본문을 얻는 단계가 막혔다.

- 한국소비자원 서버가 인증서 체인에서 중간 인증서를 보내지 않아 TLS 검증이 실패했다. `openssl s_client`에서 leaf만 전달되고 issuer 확인 오류가 발생하는 것을 재현했다.
- 삼성 지원 페이지에는 태블릿 SM-P550에도 `삼성 노트북 9 Style`이라는 공통 템플릿 문구가 있었다. 메뉴와 템플릿을 포함한 본문이 다른 제품의 근거로 들어갈 수 있었다. 클라이언트 렌더링 상품 목록도 같은 문제였다.
- 로봇청소기 조사에 필요한 로보락·드리미 한국 공식 도메인이 허용 목록과 조사 대상에서 빠져 있었다. 기존 제조사에만 편중된 조사로 문턱 성능 자료를 찾지 못했다.
- 긴 제품 설명의 처음 8,000자만 남기면서 끝에 있는 시험 조건이 누락될 수 있었다.
- `흡입력좋은청소기`처럼 사양 단어는 있지만 범위가 넓은 추천 검색어가 선별 비용을 소비했다.

## 변경

- 소비자원 두 호스트에 한해 고정 중간 인증서로 체인을 완성한다. certifi의 기존 루트까지 검증하며 호스트명·유효기간 검증을 유지한다. partial-chain 신뢰를 명시적으로 끄고 인증서 파일 SHA-256이 다르면 실패 처리한다. 자동 인증서 다운로드나 검증 비활성화는 없다.
- 삼성 모델 지원 페이지는 실제 사양 표만 추출한다. 빈 상품 목록은 제외한다.
- 소비자원 게시판은 제목·등록일·실제 본문만 추출한다. 첨부파일만 있는 페이지는 제외한다. PDF/HWP 해석을 지원한다는 의미가 아니다.
- 로봇청소기의 출처 조사에 `kr.roborock.com`, `store.kr.dreametech.com`을 포함한다. 기존 조사 횟수 제한 안에서 제조사별 결과를 교차 배치하고 소비자원 검색을 유지한다. 측정 검색어·수요·검색결과 적합성·최종 근거 심사 기준은 유지한다.
- 제조사 긴 본문은 앞 4,500자와 뒤 3,400자를 남기고 중간 생략을 표시한다. 전체 본문 해시를 기록하고 8,000자 예산을 지킨다. 메뉴·일반 고객 후기 영역을 제외한다.
- 좋은/추천/순위/가성비/베스트가 포함된 무제한 추천 후보를 조사 전에 제외한다.

## 인증서 출처와 유지관리

파일: `assets/certs/sectigo-dv-r36.pem`

- Subject: Sectigo Public Server Authentication CA DV R36
- Issuer: Sectigo Public Server Authentication Root R46 (기존 certifi 루트)
- SHA-256(DER): `8c54c334b66ba4e426772af4a3f9136c19a1aec729fdb28c535c07a5a4ef22e0`
- 유효기간: 2021-03-22 ~ 2036-03-21 UTC
- 발급사 안내: <https://www.sectigo.com/knowledge-base/detail/Sectigo-Public-Intermediates-and-Roots>
- 서버 leaf의 AIA: `http://crt.sectigo.com/SectigoPublicServerAuthenticationCADVR36.crt`. 공개 인증서를 가져온 뒤 기존 certifi 루트로 `openssl verify`를 통과했으며 DER 지문을 고정했다. AIA 전송 자체를 신뢰 근거로 사용하지 않는다.
- 서버 인증서 체인이 바뀌거나 인증서 파일이 손상되면 기존처럼 연결을 거부한다. 검증을 완화하지 말고 발급사 체인과 새 지문을 재확인한다. 서버가 정상 체인을 제공하게 되면 보완 어댑터 제거를 검토한다.

## 검증 결과

2026-09-29 로컬 작업 브랜치에서 공개 HTTPS 주소를 직접 읽었다. `python scripts/check_review_sources.py` 7/7 통과. 읽은 본문을 문서에 복제하지 않고 길이·해시·판정만 출력한다.

| 공개 페이지 | 확인한 결과 |
| --- | --- |
| KCA `no=1001956093` | TLS 연결 및 본문 3,512자 추출. 2016-11-13 등록일 보존. **연결 진단용이며 현재 구매 추천 근거로 승인한 것이 아님** |
| KCA `no=1003905732` | 첨부파일만 있는 페이지 제외 |
| 삼성 SM-P550NZBEKOO | 실제 태블릿 사양 1,023자 추출, 노트북 메모리 근거로 제외 |
| 삼성 NT960XHA-KC51G | 실제 노트북 사양 959자 추출, 메모리 항목 유지 |
| 삼성 all-memory-storage | 빈 상품 목록 제외 |
| 로보락 Qrevo Curv | 7,912자 발췌, 문턱 3cm/4cm와 내부 시험 조건 유지 |
| 드리미 X50 Ultra | 2,251자 추출, 문턱 4.2cm와 매트 조건 유지 |

관련 회귀 테스트 **1,093개 통과**, 검사한 5개 모듈 커버리지 **93.51%**. TLS 테스트는 중간 인증서가 없는 로컬 서버에 실제 HTTPS 요청을 보냈다. 기존 루트로 이어질 때만 성공하고, 잘못된 호스트 및 신뢰할 수 없는 루트는 차단됐다.

```sh
python -m pytest tests/test_editorial.py tests/test_review_discovery.py tests/test_market_topics.py tests/test_selection_feedback.py tests/test_source_tls.py tests/test_source_coverage_recovery.py tests/test_market_opportunity.py tests/test_market_search.py tests/test_topic_suitability.py tests/test_editorial_thumbnail.py tests/test_official_source_probe.py tests/test_native_search_workflows.py tests/test_pipeline_duplicates.py -o addopts='' --cov=src.editorial --cov=src.source_tls --cov=src.market_topics --cov=src.review_discovery --cov=src.selection_feedback --cov-report=term-missing --cov-fail-under=80 -q
python scripts/check_review_sources.py
```

## 운영 반영 및 남은 확인

PR #64는 사용자 승인 후 **2026-09-29 15:22 KST** 운영 main에 머지됐다(`a1dde79`). 프로젝트 checkout도 해당 코드로 동기화했으며, 머지된 코드의 공개 출처 진단은 다시 7/7 통과했다.

운영 자동포스팅 실행 **36530747099**는 같은 날 15:22에 시작했다. 리뷰 후보 96개 중 발견 단계 제외 80개, 재시도 대기 31개(서로 겹치는 집계), 조사 풀 1개였다. 남은 `청소기필터`를 모델이 제안하지 않아 `pool_exhausted / no_candidate_passed`로 **선별 단계에서 실패**했다. 실제 조사 0개, 선정 0개이며 글 생성·발행 단계에는 도달하지 않았다. 새 공개 포스트는 없다.

이번 실행은 출처 수집을 호출하지 않았으므로 운영 실행에서 TLS 오류가 사라졌다고 판단할 수 없다. 확인된 것은 머지된 코드의 별도 공개 출처 진단 성공이며, 자동포스팅 전체 성공은 여전히 미확인이다. 실패 보고서는 운영 `data/category_market_topics.json`에 자동 저장됐다(`393c892`). 동일 실행을 즉시 반복해도 재시도 대기 후보가 다시 조사되지는 않는다.

기존 실패 이력은 삭제하거나 초기화하지 않았다. 마지막 운영 이력에서 `로봇청소기문턱`은 **9월 29일 19:50 KST**, `노트북램`은 **9월 30일 13:50 KST**, `노트북메모리`는 **10월 2일 13:50 KST**부터 재검토할 수 있다. 이는 새 후보의 조사를 막지 않는다. 이전 후보를 검증할 때는 보류 기간을 확인하고, 기존 검색 적합성·출처 범위·발행 검증을 그대로 통과시켜야 한다.
