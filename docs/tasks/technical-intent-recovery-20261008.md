# 운영 재검증 후 기술 기획 복구

- 목표/담당: 현 Codex 단독. PR #89 운영 반영 후 실패의 추가 원인 수정.
- 기준: main 48d8071, 실행 37720998428, PR #89 머지 440862d.
- 실제 결과: 570개 수요 확인, 240개 shortlist 제시, 6개 심사, 5개 탈락/1개 보류, 미발행. 제조사 조회는 정상이나 `집와이파이설치`를 증폭기 설치로 좁혔다. 4개 후보는 검색 품질 탈락, 인터넷이전설치는 카테고리 불일치.
- 결함: 리뷰 전용 제외 지시가 다른 카테고리의 shortlist에도 들어감. 새 출처로 기획을 다시 만드는 복구가 리뷰에만 적용됨. 넓은 시드의 광고 연관어가 상품/가입 후보에 치우침. `인터넷`을 TP-Link로 고정하는 #89의 과도한 도메인 힌트가 실제 LGU+ 문서를 배제함.
- 수정: 리뷰 지시 분리, 테크도 새 근거로 원래 질문 전체를 재기획하고 독립 심사, 기술 사용법 시드 6개 추가(실측 수요 필수), 인터넷 일반어의 라우터 제조사 고정 제거.
- 완료 기준: 실제 보류 사례 재현 및 음성/양성 회귀, 관련 검사, 커밋·push·새 PR. #89 머지 승인은 별도 추가 PR의 승인이 아니므로 운영 반영은 다음 승인 후.
- 현재: 구현 및 관련 회귀 1,505개 통과. 사용자 승인 후 PR #90을 머지했고, 운영 자동 선정 → 동적 썸네일 → 공개 발행 재검증 성공(아래 결과).


## 검증 근거와 남은 단계

- 2026-10-08 운영 실행 37720998428: 12:04:51 KST 시작, post-queue 6분 48초 실행 후 선정 단계 실패. 본문/썸네일/WordPress 발행 전 종료. 오전 실패와 달리 정상 제조사 본문을 확보했다는 점까지 확인했다.
- 기획 복구 회귀는 실제 `집와이파이설치` 보류 보고서와 같은 날 HTTP로 확보한 TP-Link 초기 설치 원문으로 재현했다. 외부 검색·모델 판단은 테스트 대역이다. 원래 실측 검색어·수요·검색 결과를 유지한 채 새 본문과 두 심사 바인딩을 검증한다. 실제 운영에서 모델이 통과할지는 새 실행으로 확인해야 한다.
- 음성 사례: 동일 본문, 잘못된 제공자, 여전히 좁은 기획, 존재하지 않는 인용, 기획 불승인, 독립 출처 심사 불승인, 복구 예산 소진 모두 보류 유지.
- 관련 회귀 **1,505개 통과(11.13초)**, `git diff --check` 통과. 로그: iCloud `gpt 작업/wp-auto-blog/selection-root-cause-20261008/intent-pytest.log`.
- 기존 전체 테스트의 이미지 기본값 불일치 및 WordPress 재시도 대기는 #89 조사 문서에 기록했으며 이번 관련 검사 통과를 전체 테스트 통과로 표현하지 않는다.
- 검색 품질에서 탈락한 4개 후보를 강제 통과시키지 않는다. 사용법 시드를 추가해 다른 수요를 실측하고, 원래 질문 전체에 답하는 기획만 허용한다. YouTube 키 무효는 여전히 별도 미해결.
- 당시 다음 단계: 추가 PR 승인 후 운영 재검증. 아래 13:34 KST 결과로 갱신한다.


## PR #90 운영 반영 및 실제 발행 — 2026-10-08

- 사용자 명시 승인 후 PR #90 머지: `55491cf50b7d1684ca7e05b6fb95fc12c850bec6`, 13:17:30 KST.
- 운영 실행 `37726795459`: `mode=queue`, `category=테크`, `writer_provider=codex`, `publish=true`, `scheduled_recovery=false`. 키워드를 수동 지정하거나 기존 실패 이력을 지우지 않았다. post-queue 17분 7초, 최종 success.
- 선정: 실측 수요 672개 → 연구 후보군 149개 → shortlist 누적 120개 → 심사 12개. 통과 4개 중 상위 2개 선정, 1개 보류, 7개 탈락. 전체 672개를 심사했다는 뜻이 아니다.
- 선정 1위 `윈도우11설치`(81.7점), 2위 `윈도우재설치`(74.29점). `윈도우10초기화`, `자동차블루투스연결`도 적격이나 선정 개수 제한으로 미선정.
- 실제 공개: [윈도우11설치 방법: 업그레이드와 USB 새 설치 상세가이드](https://trendpulse.blog/windows-eleven-install-guide-2026/), 공개 시각 13:34:42 KST. 자동 실행은 1편을 처리했다. 2위 후보가 공개됐다는 뜻은 아니다.
- 실증된 복구: 선정 1위의 최초 독립 심사는 USB 설치 미디어 제작 근거 부족을 지적했다. Microsoft 공식 설치 미디어 문서를 새로 확보한 후 `coverage_recovery.outcome=review_passed`, `scope=full_keyword`, 필수 질문 8개 모두 근거 확인. 좁은 기획을 다시 만드는 새 분기 자체가 성공한 운영 증거와는 구분한다.
- 확인한 출처:
  - https://support.microsoft.com/ko-kr/windows/deployment/install-upgrade/ways-to-install-windows-11
  - https://support.microsoft.com/ko-kr/windows/deployment/install-upgrade/get-help-with-windows-upgrade-and-installation-errors
  - https://support.microsoft.com/ko-kr/windows/deployment/install-upgrade/reinstall-windows-with-the-installation-media
- 썸네일: 로그 `Dynamic thumbnail ready (provider=codex_imagegen)`. 공개 페이지의 og:image는 `https://trendpulse.blog/wp-content/uploads/2026/10/article-c895a855e747bf6b4260.jpg`; HTTP 200, image/jpeg, 66,288바이트 확인.
- 발행 검증: 워크플로의 WordPress API 재조회 `VERIFIED CODEX PUBLISHED`, 공개 글 HTTP 200 및 제목·게시시각 확인. 자동 실행과 모니터 명령 모두 실제 종료했다.
- 남은 오류: `아이폰공장초기화`는 올바른 Apple 지원 문서로 복구했으나 독립 심사 응답이 두 차례 `invalid_schema / facets_list`여서 `missing_topic_suitability`로 보류됐다. 다른 적격 후보를 계속 심사해 발행은 성공했다. 모든 후보의 오류가 해결됐다고 주장하지 않는다. YouTube API 키 무효도 별도 미해결이다.
- 탈락 7개: 카카오톡백업·갤럭시초기화·아이폰아이클라우드백업·와이파이비밀번호·아이폰외장하드연결은 검색 관련성/출처 다양성 기준 탈락. 아이패드초기화방법·아이폰사진옮기기는 기획 또는 공식 근거 심사 탈락. 상세 결과는 이 실행에서 저장한 `data/category_market_topics.json`의 테크 보고서에 있다.
- 다음 개선 후보: 독립 심사의 `facets_list` 응답 형식 오류 재현 및 복구. 이번 운영 반영과 1편 발행 검증은 완료했으나, 모든 미래 실행의 성공을 보장하지 않는다.
