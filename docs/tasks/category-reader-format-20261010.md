# 승인된 카테고리 메뉴 포맷 운영 준비

- 사용자 승인: 2026-10-10 “이대로해서 포멧 지정하고 각 카테고리별 실포스팅 해서 확인해보자”. 채용·생활정보 및 나머지 네 카테고리 시안 기준.
- 범위/소유: Codex 단독. 기존 feat/recruitment-reader-format-20261010 worktree와 PR #107을 전체 카테고리로 확장. 워커/Claude OFF.
- 기준: main 2a65d7b와 기존 채용 구현 59ca3ee를 작업 브랜치에서 통합. main/PR 머지는 하지 않음.
- 완료 기준: 카테고리별 작성 규칙, 흰 배경의 메뉴형 본문, 개인 체크 안내, 콘텐츠/출처/광고/스키마 보존, 실패 시 전체 본문 노출, 관련 회귀 및 실제 브라우저 확인, 커밋·push·PR 검토 준비, 승인 후 카테고리별 발행 확인.
- 구현 선택: 기존 본문 스타일/광고 스크립트 전달 경로를 사용해 전용 메뉴 JS를 삽입. WordPress가 제거하면 전체 본문과 앵커 메뉴가 남음. 실제 메뉴 작동은 저장 후 공개 화면에서 별도 검증해야 함.
- 현재: 구현 중. 실제 WordPress 글과 사이트는 아직 변경하지 않음. 공개 발행은 요청받았으나 구현 PR 머지는 별도 명시 승인 필요.
- 다음: 관련 테스트 → 운영 발행 전 준비/PR 갱신 → PR 승인 → 카테고리별 기존 품질/중복/공식출처 게이트를 통과한 실포스팅. 시안 예시를 그대로 새 글로 강제 발행하지 않음.

## 검증 및 남은 작업

- 관련 Python 회귀 372개 통과. 신규 category_format 모듈 coverage 96.33% (80% 기준 충족).
- 첫 소규모 실행은 테스트 28개 통과했으나 전체 저장소 coverage 기준 적용으로 exit 1. 영향 범위 회귀 + 신규 모듈 coverage로 정확한 검증 범위를 지정했다.
- 건강 근거 검수 fixture 6건은 새 필수 구조 미충족으로 생성 재시도가 추가된 것이 원인. fixture를 승인 구조로 보완하고 기존 근거 검수 호출/보류 의미를 그대로 검증했다.
- 실제 Chrome 및 IAB 브라우저가 현재 도구에서 unavailable로 반환되어 화면 렌더/실제 WordPress 저장 후 UI는 검증 미완료. DOM 검증은 실제 브라우저 증거를 대체하지 않는다.
- 운영 적용 및 카테고리별 실제 공개 URL 검증은 PR #107 머지 승인 후 진행. 기존 포스팅 워크플로의 공식 출처/수요/중복/품질 게이트를 유지한다.

- Node/jsdom DOM 상호작용 검증 통과: 첫 화면·해시 대상·전체 보기·키보드 Home/좌우·체크 유지·다른 본문과 상태 분리·local/session storage 미사용·중복 초기화 방지. 실행: NODE_PATH=<지정 iCloud 테스트 폴더>/dom-test/node_modules node tests/test_category_reader.cjs.

## 2026-10-10 머지 승인 후 진행

- 사용자: “응 머지 하고 실포스팅 해줘”. PR #107 명시 승인 및 6개 카테고리 1편씩 발행 승인.
- PR #107 MERGED 확인. merge commit b0b213cef387f107bfedfecacdcece481ab087a2. 현재 main에 ff-only 동기화 완료.
- Chrome 공개 글 접근 복구 확인. 새 글 발행 후 실제 메뉴 UI 확인 가능.
- 실제 발행 dispatch는 아직 하지 않았다. 기존 auto-post.yml의 queue/general 실행은 상품 소개 글 및 기존 대기 요청에 대해 Telegram 알림을 보낼 수 있으며, 이 메시지 발송 허용 여부를 사용자에게 질문했다. 실포스팅 승인을 재요청한 것은 아니다.
- 최근 재고 보충 실행 38045097667은 생활정보 공식 출처 timeout 및 no_pass_among_evaluated로 보류됐다. 새 실행에서도 기존 출처/수요/검수 기준을 유지한다.
- 다음: 텔레그램 알림 답변에 맞춰 발행 경로 확정 → 카테고리별 실행 → 공개 URL 및 메뉴/본문 검증. 운영 글은 이 후속 작업에서 아직 생성·수정하지 않았다.

## 알림 제외 실포스팅 실행 시도 및 보완

- 사용자 “실포스팅부터”에 따라 알림을 제외한 경로를 준비했다. 일회성 브랜치에서 main 소스를 checkout해도 Codex의 GITHUB_REF 기본 브랜치 제한으로 실행할 수 없었다. 이 제한은 변경하지 않는다.
- 38048497138(생산성), 38048555279(테크)는 인증 복원 단계 실패. 작성/WordPress 발행 이전이다. 나머지 38048556987, 38048558748, 38048560593, 38048562397은 취소·종료 확인.
- 최종 수정은 queue 수동 실행용 notify_telegram boolean(default true) 옵션만 추가한다. false일 때 affiliate Telegram 모드 및 register/persist-intents/notify 단계를 끈다. queue/registry 최종 저장·공식 출처·수요·검수·기본 브랜치 인증·공통 동시성은 유지한다. 예약 실행은 기존 알림 동작을 유지한다.
- tests/test_codex_actions.py 42개 통과. 실제 발행은 수정 PR 머지 승인 후 main에서 notify_telegram=false로 실행해야 한다. 6편 실포스팅은 미완료다.

## 실제 발행에서 발견한 WordPress CSS 변환 문제

- PR #108 승인 후 ceab983으로 머지. notify_telegram=false로 실행한 생산성 38057361804는 success. 실제 공개 글 #1907 https://trendpulse.blog/excel-chart-guide/ 확인.
- 실제 Chrome에서 메뉴 전환, 개인 체크 1/5, 전체 본문 표시를 확인했다. 그러나 wpautop가 CSS의 빈 줄을 </p><p>로 바꿔 메뉴 grid 및 카테고리 색 규칙이 적용되지 않는 오류를 발견했다. 390px 테스트에서는 광고 iframe의 가로 넘침도 관찰했다(광고 자체는 이번 수정 범위 아님).
- 동일 포맷 확산을 피하기 위해 나머지 실행 38057377766, 38057379677, 38057381622, 38057383670, 38057385713을 취소하고 terminal cancelled 확인. 테크 인증 정리 및 큐 저장 단계는 success.
- 수정: 신규 포맷의 전용 CSS를 한 줄로 저장. 기존 글 보정은 정확한 ID/slug 및 publish 상태를 확인하고 owned style 내부 공백만 바꾸며 나머지 본문 bytes/제목/게시일/미디어/카테고리/태그/요약을 보존한다. 변경 감지 및 인증된 readback 포함.
- 회귀 43개 통과. 공식 WordPress 6.8 formatting.php의 실제 PHP wpautop로 6개 카테고리 모두 기존 오류 재현 및 수정 후 CSS 보존 검증. source SHA256 aab325fd23d24ed19827c310d06cd3dd42bf7b1c9c70361ccaa1f707e4264ae5. 공식 문서 https://developer.wordpress.org/reference/functions/wpautop/.
- 남은 작업: #1907 스타일 보정 및 공개 브라우저 재검증, 수정 PR 승인 후 main 생성 경로 반영, 나머지 5개 카테고리 발행·검증.
