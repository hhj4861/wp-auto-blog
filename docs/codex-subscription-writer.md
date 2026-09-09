# Codex 구독 기반 작성 연결

`--writer-provider codex` 또는 `BLOG_WRITER_PROVIDER=codex`로 글 작성과 LLM 검수를 Codex CLI에 연결한다. 기본값은 기존 `anthropic`이다. Python은 프롬프트를 stdin으로 전달하고 Codex의 최종 응답 파일을 읽는다. 기존 출처 검증·편집 규칙·게시 전 검사는 그대로 적용된다.

## 인증과 실행 위치

ChatGPT 로그인은 구독의 Codex 사용 한도를 이용한다. `openai` 제공자는 별도 API 키 과금 경로이다. Codex 오류·한도 초과 시 다른 제공자로 자동 전환하지 않는다. 조사용 Gemini, 이미지 등 다른 단계의 기존 API 사용까지 구독으로 바뀌는 것은 아니다.

## GitHub Actions: 직접 작성과 발행

2026-09-09 사용자가 기존 `hhj4861/wp-auto-blog`의 `CODEX_AUTH_JSON`을 사용한
수동 실행과 이후 예약 실행의 Codex 전환을 명시적으로 요청했다.
기존 비공개 worker 중계 대신 해당 저장소 기본 브랜치에서만 실행되는 직접 경로를 사용한다.
공식 OpenAI 문서는 구독 인증 CI를 비공개 실행 환경에 권장하므로, 이 공개 저장소 경로는
사용자의 명시적 운영 선택이며 일반적인 권장 배포 방식으로 확대하지 않는다.

- `Auto Blog Post` 수동 입력 `writer_provider=codex`와 `mode=general/queue`를 사용한다.
- 예약 실행은 변수 `BLOG_WRITER_PROVIDER=codex`로 전환한다. 기존 시간·카테고리는 유지한다.
- `CODEX_AUTH_JSON`은 runner 임시 디렉터리에 0600 권한으로 복원한다.
- `CODEX_SECRET_WRITE_TOKEN`은 인증 복원 전 갱신 저장 준비 확인과 종료 후
  `CODEX_AUTH_JSON` 갱신 저장에만 사용한다. 작성 프로세스에는 전달하지 않는다.
  이 토큰에는 해당 저장소 Secrets 읽기/쓰기 권한이 필요하다.
- Codex CLI 작성·별도 사실 검토 → 공통 본문 템플릿 → WordPress 발행 →
  인증된 REST 재조회에서 공개 상태와 URL 확인 순서로 처리한다.
- 동시 인증 사용을 막기 위해 Codex 작업은 직렬화한다. 종료 시 갱신본을 Secret에 저장하고
  runner의 인증 파일을 제거한다. 인증은 로그나 artifact에 업로드하지 않는다.
- PR, 임의 브랜치, 다른 공개 저장소에서는 실행하지 않는다. API 과금이나 Claude로 자동 전환하지 않는다.
- 빈 큐·초안 저장은 공개 발행 성공으로 보고하지 않는다. 자동 재발행은 하지 않는다.
  작업 실패 시 WordPress와 실행 로그를 먼저 확인한다. 발행 이후 인증 저장/큐 저장이 실패했을 수도 있다.

수동 예시:

```bash
gh workflow run auto-post.yml --ref main -f mode=general -f writer_provider=codex \
  -f category=취업 -f publish=true -f topic='면접 1분 자기소개 예시와 작성 체크리스트'
```

로그의 `Content generated using: Codex CLI (ChatGPT subscription)`과
`VERIFIED CODEX PUBLISHED` URL을 확인한다. 수동 실발행 검증 후 예약 실행 변수도 전환한다.

서버의 실행 계정으로 Codex CLI를 설치하고 로그인한다. 아래 작업은 운영자가 서버에서 한 번 수행한다. 계정 설정에서 device-code 로그인을 허용해야 할 수 있다.

```bash
npm install -g @openai/codex
export BLOG_CODEX_HOME="$HOME/.trendpulse-codex"
mkdir -p "$BLOG_CODEX_HOME"
chmod 700 "$BLOG_CODEX_HOME"
CODEX_HOME="$BLOG_CODEX_HOME" codex -c 'cli_auth_credentials_store="file"' -c 'forced_login_method="chatgpt"' login --device-auth
CODEX_HOME="$BLOG_CODEX_HOME" codex login status
```

인증 파일은 비밀번호처럼 취급한다. 저장소·로그·Actions artifact에 넣지 않는다. 실행 중 갱신되는 인증을 유지할 수 있도록 디렉터리는 실행 계정에 쓰기 가능해야 한다. 개발자의 기존 Codex 홈을 재사용하지 않는다. 전용 계정에는 필요한 파일만 둔다. read-only sandbox는 모든 로컬 파일의 읽기까지 차단하는 격리 수단은 아니다.

설치한 CLI의 `codex exec --help`에 `--ignore-user-config`, `--ephemeral`, `--output-last-message`가 있는지 확인한다. 모델을 지정하지 않으면 CLI 기본 모델을 사용한다. 선택하려면 계정에서 이용 가능한 모델 ID를 `BLOG_CODEX_MODEL` 또는 `--codex-model`에 지정한다.

## 연결 확인과 자동 포스팅

네트워크 호출 없이 도움말과 테스트로 구현을 검증했다. 실제 구독 인증·응답은 서버 로그인 후 아래처럼 별도로 확인한다. 이 첫 명령은 블로그 파이프라인이나 WordPress를 호출하지 않는다.

```bash
export BLOG_CODEX_HOME="$HOME/.trendpulse-codex"
venv/bin/python - <<'PY'
import os
from src.codex_client import CodexSubscriptionClient
client = CodexSubscriptionClient(home=os.environ['BLOG_CODEX_HOME'])
print(client.generate('한국어 HTML 문단 하나로 검색 의도의 의미를 설명해줘.'))
PY

venv/bin/python -m src.main --mode general --writer-provider codex \
  --topic '검증할 주제' --keywords '대상 키워드' --content-type guide \
  --no-llm-topics --dry-run
```

실제 예약 실행에는 같은 서버 계정과 환경변수를 설정하고 기존 큐 명령을 사용한다. 서버의 기존 Claude 작업을 대체할 때는 중복 실행되지 않도록 기존 스케줄을 함께 조정한다. 아래 명령은 실제 게시하므로 초안/드라이런 검토 후 사용한다.

```bash
export BLOG_WRITER_PROVIDER=codex
export BLOG_CODEX_TIMEOUT=600
venv/bin/python -m src.main --mode general --from-queue --no-llm-topics --auto-publish
```

`--no-llm-topics`는 별도 주제 분석 LLM 호출을 끈다. 작성·검수 프롬프트, 조사와 품질 기준은 제공자와 독립적이다. 모델 교체만으로 글 품질이나 검색 유입 향상을 보장하지 않는다.

요청은 임시 작업 디렉터리, 읽기 전용 sandbox, 승인 요청 없음, 사용자 config 무시, 세션 기록 없음으로 실행한다. WordPress 비밀번호와 API 키 등은 자식 프로세스 환경에 전달하지 않는다. 기본 제한 시간은 600초이며 초과 시 프로세스 그룹을 종료한다. 실패 메시지는 원본 CLI 출력이나 토큰을 기록하지 않는다. 오류가 나면 서버에서 CLI 버전, `login status`, 구독 사용 한도를 확인하고 필요 시 재로그인한다.

공식 자료: [인증](https://learn.chatgpt.com/docs/auth), [비대화형 실행 및 CI 인증](https://learn.chatgpt.com/docs/non-interactive-mode).
