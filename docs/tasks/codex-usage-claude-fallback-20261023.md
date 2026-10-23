# Codex 한도 → Claude 구독 폴백

- 목표: 사용량 한도 오류만 Claude 구독으로 복구. 인증/네트워크/검증 실패는 기존 정책 유지.
- 범위/소유: 이 worktree의 호출 transport, 검색 provenance, Actions 설정/테스트. root의 미완료 파일 보존.
- 기준: main 96dfdf56a8899e604552a1a58c165d269a320fc9.
- 완료 기준: 생성/중복/공식조사/검색 한도 폴백, 실행 내 한도 기억, 기존 품질 검증 유지, 관련 테스트 통과, 작업 브랜치 commit/push와 PR 준비.
- 현재: PR #120/#121 사용자 승인으로 main/운영 반영 완료. 운영 저장 Claude OAuth로 모의 Codex 한도 후 실제 Claude 생성·후속 호출·검색·페이지 조회까지 검증 통과. 인증 설정 변경 없음.
- 다음: 기존 예약 자동화가 반영된 main을 실행. 실제 한도 발생 시 Claude 전환 로그는 별도 확인 대상이며 이번 비발행 실행에서 성공한 것으로 표시하지 않음.

- 1차 검증: 303 통과, 9 실패. 모두 기존 Codex research dict에 provider 키를 추가한 API shape 변경 때문. Codex 응답 shape는 유지하고 Claude 응답에만 실제 provider를 추가하도록 수정.
- GitHub secret 이름 조회: CLAUDE_CODE_OAUTH_TOKEN 존재 확인(값 조회/변경 없음). 로컬 OAuth token 미설정이므로 실제 Claude 성공 호출은 미확인.

- 2차 검증: 1,266 통과, 원격 계약 테스트의 신규 인자 기대값 1개 갱신. Actions runner context는 job env에서 지원되지 않아 기존 인증 복원 step의 GITHUB_ENV 설정으로 이동. SDK는 검증한 0.2.173 이상으로 명시.

- 최종 검증: 관련 13개 테스트 파일 1,268개 전부 통과(32.08초), `git diff --check` 통과. 실제 subprocess stand-in으로 Codex 비정상 종료/usage_limit → Claude stdin/격리 환경 → JSON validator 성공까지 실행. 실계정 Claude 응답 및 운영 발행은 미실행.
- 제공자 경계: API 과금 전환 없음, 원격 고정 runtime 계약은 명시적으로 유지. Claude native 검색의 빈 snippet은 합성하지 않고 기존 관련성·사이트 수·근거 검증을 적용.
- 실제 CLI/OAuth 성공은 머지 후 비발행 slot_test로 확인할 항목. 기존 root checkout의 다른 세션 삭제 변경은 보존.
- 참고: [Claude WebSearch/WebFetch DTO](https://code.claude.com/docs/en/agent-sdk/python#websearch), [Actions context availability](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#context-availability).

- 통합 검토 보정: Codex 전용 auth/research 진단은 fallback을 명시적으로 금지하여 Claude 응답을 Codex 정상으로 오인하지 않게 함. 발행 확인은 실제 글 재조회 결과를 제공자와 독립적으로 표시. 이 보정 후 관련 검증 재실행.

- 보정 후 1,278 통과/2 실패: 기존 auth probe 테스트 stand-in이 신규 allow_usage_fallback 인자를 받지 못한 TypeError. fixture에서 false 경계를 직접 검증하도록 갱신하고 중복 단순 테스트 제거 후 최종 검증.

- 최종 통합 결과: 관련 14개 파일 **1,279개 테스트 전부 통과(27.95초)**. 후속 diff 공백 검사에서 발견한 테스트 EOF 빈 줄만 정리.
- 검토 PR: https://github.com/hhj4861/wp-auto-blog/pull/120 . 사용자 머지·배포 승인 후 main에 반영됨(아래 운영 검증 기록 참조).

## 운영 반영 — 2026-10-23

- 사용자 명시 승인으로 PR #120 merge 완료: ea20aba6bf6d94cfa5a1755f824ac1cd1032591f. 자동포스팅/키워드 선정 Actions의 기본 브랜치에 폴백 설정 적용.
- 첫 비발행 검증: https://github.com/hhj4861/wp-auto-blog/actions/runs/39889147961 (`slot_test`, 건강, codex, publish=false, notify_telegram=false).
- 관찰: 11:22:39 KST WordPress inventory page 1에서 http_403. 모델 호출/작성 전에 중단되어 WordPress 생성/발행 및 Telegram 전송 없음. 인증 복원·정리는 성공.
- 재시도 가설: 직전 main 실운영 비발행 실행은 동일 자격으로 성공했고 이번 요청은 http_403이므로 runner별 접속 차단 가능성. 실제 원인은 아직 미확정. 실패 지점이 원격 변경 전임을 확인하여 동일 작업을 새 runner에서 한 번 재실행하고 결과 비교.

- main 통합 검증: 같은 14개 테스트 파일 1,279개 전부 통과(27.10초). PR head와 merge commit의 src/scripts/tests/requirements/workflow tree 일치 확인.
- 재실행 결과: [attempt 2](https://github.com/hhj4861/wp-auto-blog/actions/runs/39889147961/attempts/2) 성공. job 120205129442. 11:24:57 KST WordPress 전체 inventory 조회 성공 → 중복 검수/작성 → 11:27:55 DRY RUN 성공 1/실패 0. 본문은 Codex CLI, 썸네일은 codex_imagegen 사용.
- 원격 영향: `[DRY RUN] Would create post - skipping actual publish` 및 `No queue/registry changes to commit` 확인. WordPress 게시·초안 생성/큐·이력 변경/Telegram 전송 없음. Codex 인증은 갱신 변경 없이 정리 성공.
- 첫 403은 새 runner 재실행에서 재현되지 않았으며 차단 원인은 미확정. 인증 변경이나 검증 완화로 처리하지 않음. 이번 실행에서는 Codex 한도 오류가 없어 **실계정 Claude 폴백 성공은 미확인**.
- 운영 반영 상태: 자동포스팅/키워드 선정 기본 브랜치의 BLOG_CODEX_USAGE_FALLBACK=claude 설정을 실제 Actions env에서 확인. 별도 상주 서버 배포 없이 예약 작업이 main을 checkout하는 운영 구조.

## 추가 실계정 검증 — 2026-10-23

- 기존 로컬 Claude 구독 자격을 메모리에서만 사용(설정·토큰 저장/변경 없음). 모의 Codex usage_limit → 실제 Claude JSON 응답 성공, 같은 실행 후속 JSON 응답도 Claude 성공, Codex 재호출 0회 확인. 운영 CI의 저장된 secret 값과 동일한 자격인지는 확인하지 않음.
- 실제 Claude WebSearch 확인은 unexpected_search_query로 실패. 가설: 모델의 검색어 변경/추가 필터/복수 검색 중 어느 조건인지 도구 입력·결과의 공개 질의 메타데이터로 구분. 검증 기준을 완화하지 않고 원인을 확인 중.
- 최초 실제 검증 명령은 자동 권한 검토 시간 초과로 실행되지 않았으며, 허용된 1회 재시도에서 위 생성 검증을 수행.

## 운영 Claude 검증 완료 — 2026-10-23

- 검색 mode=standard 호환성 수정은 사용자 승인으로 PR #121 머지/운영 반영 완료(e3af2bd).
- 운영 저장 토큰을 사용한 [실행 39911440077](https://github.com/hhj4861/wp-auto-blog/actions/runs/39911440077) success. 한도 오류만 모의, 실제 Claude 생성·후속 호출·검색 9건·페이지 조회 1건 성공. 로컬 구독 자격으로 대체하지 않음.
- 운영 main 통합 회귀 908개 통과(9.03초). WordPress 발행/초안 생성·Telegram·인증 설정 변경 없음. 자세한 결과는 [후속 작업 기록](claude-websearch-mode-20261023.md)에 저장.
