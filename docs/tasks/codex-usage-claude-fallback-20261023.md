# Codex 한도 → Claude 구독 폴백

- 목표: 사용량 한도 오류만 Claude 구독으로 복구. 인증/네트워크/검증 실패는 기존 정책 유지.
- 범위/소유: 이 worktree의 호출 transport, 검색 provenance, Actions 설정/테스트. root의 미완료 파일 보존.
- 기준: main 96dfdf56a8899e604552a1a58c165d269a320fc9.
- 완료 기준: 생성/중복/공식조사/검색 한도 폴백, 실행 내 한도 기억, 기존 품질 검증 유지, 관련 테스트 통과, 작업 브랜치 commit/push와 PR 준비.
- 현재: 구현 및 관련 회귀 검증 통과. 로컬 Claude auth status는 로그인이나 격리된 실제 호출은 authentication_required 반환. 인증 설정은 변경하지 않음. CI는 기존 CLAUDE_CODE_OAUTH_TOKEN secret 사용.
- 다음: 작업 브랜치 commit/push와 PR 검토. 실제 운영 적용은 해당 PR의 명시적 머지 승인 후.

- 1차 검증: 303 통과, 9 실패. 모두 기존 Codex research dict에 provider 키를 추가한 API shape 변경 때문. Codex 응답 shape는 유지하고 Claude 응답에만 실제 provider를 추가하도록 수정.
- GitHub secret 이름 조회: CLAUDE_CODE_OAUTH_TOKEN 존재 확인(값 조회/변경 없음). 로컬 OAuth token 미설정이므로 실제 Claude 성공 호출은 미확인.

- 2차 검증: 1,266 통과, 원격 계약 테스트의 신규 인자 기대값 1개 갱신. Actions runner context는 job env에서 지원되지 않아 기존 인증 복원 step의 GITHUB_ENV 설정으로 이동. SDK는 검증한 0.2.173 이상으로 명시.

- 최종 검증: 관련 13개 테스트 파일 1,268개 전부 통과(32.08초), `git diff --check` 통과. 실제 subprocess stand-in으로 Codex 비정상 종료/usage_limit → Claude stdin/격리 환경 → JSON validator 성공까지 실행. 실계정 Claude 응답 및 운영 발행은 미실행.
- 제공자 경계: API 과금 전환 없음, 원격 고정 runtime 계약은 명시적으로 유지. Claude native 검색의 빈 snippet은 합성하지 않고 기존 관련성·사이트 수·근거 검증을 적용.
- 실제 CLI/OAuth 성공은 머지 후 비발행 slot_test로 확인할 항목. 기존 root checkout의 다른 세션 삭제 변경은 보존.
- 참고: [Claude WebSearch/WebFetch DTO](https://code.claude.com/docs/en/agent-sdk/python#websearch), [Actions context availability](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#context-availability).
