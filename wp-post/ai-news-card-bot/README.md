# 한국어 AI 기술 카드뉴스 Telegram 봇

기존 WordPress 실행과 독립된 일일 브리핑입니다. 기존 `OPENAI_API_KEY`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`를 재사용하며 새 서비스나 Secret은 필요 없습니다.
`GITHUB_TOKEN`은 Actions가 자동 발급합니다. API 사용료는 기존 OpenAI 계정에 발생합니다.

## 실행

- 워크플로: `.github/workflows/wp-post-ai-card-news.yml`
- 매일 UTC 23:00 = 다음 날 08:00 KST. GitHub 스케줄은 지연되거나 누락될 수 있습니다.
- Actions → WP Post - AI Tech Telegram Cards → Run workflow → `dry_run=true`로 검증.
- `dry_run=false`는 실제 기존 채팅방에 앨범을 전송합니다.
- 생성한 1080×1350 JPEG, 출처/요약 `news.json`, 성공 증거 `delivery.json`을 14일 Artifact 보관.
- 테스트: `python -m unittest -v test_main` (Noto CJK 필요).
- 로컬에서는 `CARD_FONT`, `CARD_BOLD_FONT`로 한국어 폰트 경로를 지정할 수 있습니다.

공식 GitHub 프로젝트의 안정 릴리스와 OpenAI 공식 RSS만 수집합니다.
릴리스의 `published_at` / RSS의 `published`를 사용하며 수정일로 신선도를 부풀리지 않습니다.
최근 24시간 우선, 부족할 때 72시간까지 확장하고 프로젝트/URL/제목을 중복 제거합니다.
목표는 5~7건이며 검증 가능한 뉴스가 부족하면 실제 건수만 보내고, 없으면 보내지 않습니다.
GitHub 인기 프로젝트는 코드의 명시적 소스 목록으로 관리하며 실시간 인기 순위라고 주장하지 않습니다.
Skills/Plugins 변화는 Claude Code 등 관련 공식 릴리스에 명시된 경우에만 소개합니다.

카드는 표지 → 핵심 업데이트 → 뉴스별 변경점·개발자 가치·실무 적용 제안 → TOP 3입니다.
뉴스별 카테고리가 Claude/Codex/오픈소스/Agent/MCP를 구분합니다. 없는 카테고리를 채우지 않습니다.
한 번에 최대 10장(뉴스 7건+3장)을 전송하며 원문 URL은 각 뉴스 이미지 캡션에 표시합니다.
한글 요약 필드 길이와 출처 매핑을 검증하고, 이미지 영역에 들어가지 않으면 발송 전에 실패합니다.
확인되지 않은 설치 명령은 생성하지 않습니다. 제안은 실제 검증 결과가 아닙니다.

## 중복 방지와 복구

워크플로 concurrency와 저장소의 영구 Git ref를 함께 사용합니다.
`refs/tags/ai-card-claimed/YYYY-MM-DD`를 전송 직전에 원자적으로 생성하며,
Telegram 성공 응답 후 `refs/tags/ai-card-sent/YYYY-MM-DD`를 기록합니다.
키는 실행 시작 시 KST 날짜이며 수동 실행과 스케줄이 공유합니다. 드라이런은 기록하지 않습니다.
태그는 실행한 코드 SHA만 가리키며 Secret이나 채팅방 정보를 저장하지 않습니다.
`contents: write`는 이 발송 기록에 필요합니다. main 파일을 변경하지 않습니다.

- sent 있음: 이미 발송했으므로 정상 종료.
- claimed만 있음: 타임아웃/실패/중단으로 결과 불확실. 자동 재전송하지 않고 실패 처리.
- 렌더링·수집·요약 실패: claim 생성 전이므로 수정 후 재실행 가능.

Telegram API에는 idempotency key가 없어 외부 전송과 Git 기록을 원자적으로 묶을 수 없습니다.
따라서 장애 상황에서 정확히 한 번의 전달을 보장하는 대신 **최대 한 번 시도**를 선택합니다.
claimed만 남으면 해당 실행 로그/Artifact/실제 채팅방을 확인하십시오.
실제로 미발송임을 확인한 운영자만 해당 날짜 claimed 태그를 삭제한 뒤 재실행해야 합니다.
이미 발송됐으면 claim을 보존하십시오. 무조건 삭제하면 중복 발송될 수 있습니다.

Secret 값/Telegram 요청 URL/응답 원문은 로그에 기록하지 않습니다.
Secret 누락은 이름만 출력합니다. API 실패는 HTTP 상태/단계로 확인합니다.
