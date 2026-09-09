# Codex 구독 기반 작성 연결

`--writer-provider codex` 또는 `BLOG_WRITER_PROVIDER=codex`로 글 작성과 LLM 검수를 Codex CLI에 연결한다. 기본값은 기존 `anthropic`이다. Python은 프롬프트를 stdin으로 전달하고 Codex의 최종 응답 파일을 읽는다. 기존 출처 검증·편집 규칙·게시 전 검사는 그대로 적용된다.

## 인증과 실행 위치

ChatGPT 로그인은 구독의 Codex 사용 한도를 이용한다. `openai` 제공자는 별도 API 키 과금 경로이다. Codex 오류·한도 초과 시 다른 제공자로 자동 전환하지 않는다. 조사용 Gemini, 이미지 등 다른 단계의 기존 API 사용까지 구독으로 바뀌는 것은 아니다.

이 저장소는 공개 저장소다. OpenAI 문서는 ChatGPT 인증을 저장하는 CI 흐름을 공개/오픈소스 저장소에 사용하지 않도록 안내한다. Codex 작성은 전용 비공개 서버 또는 비공개 저장소의 기본 브랜치 `workflow_dispatch`에서만 허용한다. 공개 Actions는 비공개 작업 실행을 요청하고 실제 완료 결과를 기다린다. 인증 파일은 공개 저장소·로그·artifact로 전달하지 않는다.

## GitHub Actions 작성 옵션

`Auto Blog Post`의 `writer_provider=codex`는 TrendPulse general/queue에 적용한다.
기존 Claude는 `anthropic`으로 선택할 수 있다. 수동 실행 기본 선택은 codex이며,
예약 실행은 저장소 변수 `BLOG_WRITER_PROVIDER`를 따른다(미설정 시 기존 anthropic 유지).
BytePulse 작성 모델은 변경하지 않는다. 인증 오류, 한도 초과, 출처 검증 실패 시
다른 모델로 전환하거나 같은 발행을 자동 재요청하지 않는다.

연결 순서:

1. `hhj4861/trendpulse-codex-worker` 비공개 저장소를 만들고 이 프로젝트의
   `.github/workflows/codex-worker.yml`을 해당 저장소 기본 브랜치에 배치한다.
   작업은 공개 원본의 main 코드를 가져와 실행한다. PR이나 임의 브랜치 실행은 허용하지 않는다.
2. 전용 Codex 로그인으로 만든 `auth.json`을 비공개 저장소의 `CODEX_AUTH_JSON` Secret에 저장한다.
   개발 중인 현재 세션과 같은 인증 파일을 여러 머신에서 공유하지 않는다.
3. 비공개 저장소에 기존 `GOOGLE_AI_API_KEY`, `WP_GENERAL_URL`, `WP_GENERAL_USERNAME`,
   `WP_GENERAL_APP_PASSWORD`, `NAVER_AD_API_KEY`, `NAVER_AD_SECRET_KEY`,
   `NAVER_AD_CUSTOMER_ID`를 설정한다.
4. 비공개 저장소에 `WORKER_ADMIN_TOKEN`(해당 비공개 저장소 Secrets 읽기/쓰기),
   `BLOG_SOURCE_TOKEN`(공개 원본 Contents 읽기/쓰기)을 설정한다.
   `WORKER_ADMIN_TOKEN`으로 CLI가 갱신한 인증 파일을 Secret에 다시 저장한다.
   인증을 사용하는 작업은 concurrency로 직렬화하고 종료 시 runner의 인증 파일을 삭제한다.
5. 공개 원본에 변수 `CODEX_WORKER_REPOSITORY=hhj4861/trendpulse-codex-worker`,
   Secret `CODEX_WORKER_TOKEN`(비공개 작업 저장소 Actions 읽기/쓰기)을 설정한다.
6. `Auto Blog Post`를 `mode=general`, `writer_provider=codex`, `topic=검증할 주제`,
   `category=취업`, `publish=true`로 실행한다. 비공개 작업 로그의
   `Content generated using: Codex CLI (ChatGPT subscription)` 및
   `VERIFIED CODEX PUBLISHED` URL을 확인한다. WordPress 재조회에서 공개 상태까지 확인해야 성공이다.
7. 실제 발행 확인 후 공개 저장소 변수 `BLOG_WRITER_PROVIDER=codex`로 예약 실행도 전환한다.

공개 요청 작업은 비공개 실행의 성공·실패를 그대로 전달한다. 초안 저장·빈 큐는 공개 발행 성공으로
간주하지 않는다. 요청 응답이 불명확하거나 대기 시간이 초과되면 비공개 Actions와 WordPress를
확인한 뒤 재실행한다. 포스팅은 성공했지만 인증 갱신 저장이나 큐 저장이 실패한 경우도 포함한다.

2026-09-09 구현 검증 시 현재 GitHub 연결 계정은 `socar-hyunz`, 원본 권한은 WRITE였으며,
`hhj4861` 아래 비공개 저장소 생성은 GitHub가 거부했다. 따라서 코드 준비와 로컬 테스트는
실제 비공개 실행 환경 연결·구독 작성·발행 성공 증거를 대신하지 않는다.

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
