# Claude 실제 검색 옵션 호환성

- 목표/소유: 사용자 실제 전환 확인 요청의 후속 수정. /root 단독, transport/parser와 회귀 테스트만 변경.
- 기준: main 22672a2 (PR #120 운영 반영 및 비발행 검증 후).
- 관찰: 로컬 기존 Claude 구독으로 모의 Codex 한도 → 실제 Claude JSON 생성과 후속 호출 성공. 토큰 저장/변경 없음. CI 저장 secret과 동일성은 확인하지 않음.
- 원인: SDK 0.2.173 번들 CLI의 실제 WebSearch 입력은 query가 정확히 일치하고 필터도 없지만 `mode=standard`가 추가됨. 기존 허용 목록이 이 인자를 거부해 unexpected_search_query 발생.
- 변경: 실측한 standard 모드만 추가 허용. 정확한 검색어/단일 검색/도메인 필터 금지/알 수 없는 옵션 금지/실제 도구 결과 요구는 유지.
- 완료 기준: 기존+standard 회귀 통과, 실제 Claude 검색 결과 수집, 작업 브랜치 commit/push 및 검토 PR. 운영 반영은 새 PR 승인 전 미적용.
- 현재: 수정본 실제 Claude 생성·후속 호출·검색·공식 페이지 열기 및 관련 회귀 통과. 다음: PR 검토/머지 승인 후 운영 secret으로 전용 진단 실행.

- 첫 회귀 실행은 산출물 상위 폴더 미생성으로 tmp_path fixture에서 중단(902 setup errors). 제품 코드 테스트는 실행되지 않음. 상위 폴더를 생성하고 fail-fast/짧은 traceback으로 재검증.

- 실계정 수정본 검증 성공: Codex client.generate에서 모의 usage_limit 후 실제 Claude JSON 생성, native_search adapter에서 claude_native_search 결과 9건(snippet 합성 없음), client.research에서 claude_web 검색 관측 및 WebFetch 열기 1건 성공. 전체 과정의 Codex 시도는 최초 모의 1회뿐.
- 관련 6개 파일 회귀: 902개 전부 통과(15.43초).
- 운영 secret 검증을 위한 별도 읽기 전용 workflow 추가: contents:read, checkout 자격 유지 안 함, Claude OAuth secret만 주입. WordPress/Telegram/API 키/발행 기능 없음. 기본 브랜치에서만 실행하고 한도 오류가 모의임을 명시. 새 PR 승인/머지 후 이 진단을 실행할 수 있음.

- 진단 회귀에서 macOS /var→/private/var 별칭으로 한도 상태 키가 달라지는 문제 발견. 진단용 임시 home을 resolve하고 unit fixture는 실제 Codex transport를 명시적으로 금지하도록 보정.

- 최종 회귀: 관련 7개 테스트 파일 908개 전부 통과(12.00초), git diff --check 통과.
- 새 진단 자체의 로컬 실계정 실행도 status=ok: generation=true, sticky_followup=true, primary_calls=1, claude_native_search 결과 9건, claude_web의 실제 검색 및 열기 1건. Codex usage_limit만 모의이고 Claude 응답·도구는 실제.
- 운영 상태: 이 수정/진단은 작업 브랜치에만 존재. CI 저장 secret을 사용한 실행은 새 PR 명시 승인/머지 후 `gh workflow run claude-fallback-check.yml --ref main`으로 진행. 글 발행·초안 생성·Telegram 및 인증 설정 변경 없음.
