# 예약 포스팅과 누락 복구

예약 정의는 `.github/workflows/auto-post.yml`에 있다. **매일 09:00·18:00 KST, 주 14회** 발행을 시도한다.
요일 고정 카테고리 대신 다음 6일 주기를 반복한다. 모든 카테고리가 6일 동안 오전·오후에 각각 한 번씩 배정된다.

| 기준 날짜 | 오전 9시 | 오후 6시 |
|---|---|---|
| 2026-09-21 월 | 생활정보 | 생산성 |
| 2026-09-22 화 | 취업 | 리뷰 |
| 2026-09-23 수 | 건강 | 테크 |
| 2026-09-24 목 | 생산성 | 생활정보 |
| 2026-09-25 금 | 리뷰 | 취업 |
| 2026-09-26 토 | 테크 | 건강 |
| 2026-09-27 일 | 생활정보 | 생산성 |

9/28은 취업·리뷰이며 이후에도 6일 주기를 이어간다. 월요일마다 순서를 초기화하지 않는다.
누락·실패·재실행 여부와 관계없이 날짜와 회차로 계산하므로 연도가 바뀌어도 순서가 유지된다.
자동 키워드 조사는 03:00·07:00·13:00·16:00 KST에 재고가 빈 카테고리를 다가오는 회차 순으로 최대 2개 조사해 큐에 적재한다. 회차 카테고리에 재고와 즉석 선정이 모두 없으면 다른 카테고리의 검증 재고를 발행하고, 회차 기록의 `category`(순환)는 유지한 채 `published_category`를 남긴다.
수동 `scheduled` 조사에는 `slot=morning|evening`을 지정한다. 여섯 카테고리 또는 `all` 직접 지정도 지원한다.
리뷰는 공식 사양과 기능을 근거로 비교하며, 실제 사용·측정 경험을 지어내지 않는다.
09시·18시는 **실행 목표 시각**이다. 검색 수요·중복·출처·품질 검증을 통과한 경우만 발행하며,
상품 홍보글의 쿠팡 메시지는 WordPress 공개 발행 확인에 성공한 뒤 발송한다.

GitHub는 정각의 부하 등으로 예약 실행이 지연되거나 누락될 수 있다고
[명시한다](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
2026-09-14 12:15 KST에도 당일 Auto Blog Post 실행 기록이 없었다. 워크플로는
active였고 기본 브랜치 main에 유효한 예약식이 있었다. 실행 기록이 없어
GitHub 내부의 지연과 누락 중 어느 원인이었는지는 확정할 수 없다.

## 복구 정책

- 매일 09:17부터 22:47까지 매시 17·47분에 같은 워크플로를 깨워 현재 회차의 시도 여부를 확인한다.
  오전 회차는 09:00~17:59, 오후 회차는 18:00~23:59 KST다.
- 공유 `trendpulse-general-posting` concurrency 안에서 최신 main을 체크아웃한 뒤
  `data/scheduled_post_runs.json`에 KST 날짜+회차별 시도를 기록하고 **push를 성공시킨 후에만**
  인증 복원·키워드 선정·글 생성·메시지 발송을 시작한다.
- 먼저 도착한 기본 예약 또는 복구 실행 하나만 작업한다. 뒤늦은 기본 예약,
  후속 복구 예약, 동일 실행의 재실행은 이미 시도한 날짜+회차를 건너뛴다. 오전의 성공·실패·취소는 오후 회차를 막지 않는다.
- 날짜는 Actions run의 `created_at`으로 고정한다. concurrency 대기 중 KST 날짜
  또는 회차가 바뀌면 오래된 실행은 폐기하며, 오전 작업을 오후 글로 바꾸지 않는다.
  기본 cron은 오전/오후를 따로 식별해 늦게 생성된 오전 예약도 오후로 오인하지 않는다.
- 실패·취소·결과 불명도 시도 기록을 남긴다. 이 복구는 **시작되지 않은 예약**을
  위한 것이며, 이미 초안이나 요청을 만들었을 수 있는 실패 작업을 반복하지 않는다.
  WordPress와 큐 상태를 확인한 뒤 기존 초안 복구 절차를 사용한다.
- 보통의 수동 실행은 명시적으로 요청된 별도 작업이며 회차 기록을 소비하지 않는다.
  현재 회차를 수동 보충하려면 `mode=queue`, `publish=true`,
  `scheduled_recovery=true`로 실행한다. 주제나 기존 초안 ID를 지정할 수 없고,
  카테고리는 해당 회차의 카테고리와 일치해야 한다. 늦게 도착하는 예약과 동일한 기록을 쓴다.

기존 `schema_version=1` 날짜별 이력은 모두 오전 회차로 읽는다. 새 회차 저장 시 `schema_version=2`와 `YYYY-MM-DD:morning|evening` 키로 전환하며 과거 상태를 보존한다. 기존 이력이 있는 날의 오전 재발행은 차단하고 오후 회차만 별도로 허용한다.

## 중단 알림과 한계

예약 또는 당일 복구 작업이 실패하면 기존 Telegram 채팅으로 `[자동 포스팅 중단]`,
카테고리, 오전/오후 회차, 중단 단계, Actions 실행 링크를 보낸다. 오류 전문과 비밀정보는 보내지 않는다.
발송 결과가 불명확할 때 같은 알림을 자동 재전송하지 않는다.

실행 자체가 전혀 생성되지 않거나 runner가 강제 종료되면 해당 실행에서 알림을
보낼 수 없다. 후속 예약 역시 GitHub 스케줄러를 사용하므로 정시 실행 보장은 아니다.
정확한 시각의 실행이나 GitHub 전체 스케줄 장애 감시에는 별도 외부 스케줄러가 필요하다.

일반 정보글은 쿠팡 요청 없이 발행한다. 새 상품 홍보글도 상품 링크 없이 먼저 발행한 뒤,
텔레그램으로 글 주소와 상품 검색어를 안내한다. 답장이 오면 검수 후 같은 공개 글에 상품 링크를 추가한다.
답장 대기 시간 제한은 없으며, 답장이 없으면 공개 글을 유지한다. 기존 초안 요청의 검증 조건은 유지하고 만료 초안을 자동 복구하지 않는다.
알림 단계에서 실패했다면 글은 이미 공개됐을 수 있으므로 재발행 전에 WordPress와 큐를 확인한다.

## 독립 타이머 보완 (2026-10-03)

### 확인한 문제와 변경

2026-10-02 오전 cron(`0 0 * * *`)의 Actions 실행 `36963169588`은 13:07:36 KST에
생성돼 13:07:38에 runner가 시작했다. 09시 예약 대비 **실행 생성 단계에서 4시간 7분 지연**됐다.
09:17부터의 복구 cron도 같은 GitHub 스케줄러에 의존하므로 독립적인 장애 대책이 아니었다.

`scripts/posting_timer.py`를 GitHub 밖에서 매분 실행하면 KST 09시·18시부터 운영 원격 이력을
확인하고, 미시도 회차만 `workflow_dispatch`로 요청한다. `ref=main`, `mode=queue`,
`writer_provider=codex`, `publish=true`, `scheduled_recovery=true`는 고정이다.
기존 GitHub cron은 보조 트리거로 유지하며 작성·출처·품질 심사와 인증 정책은 그대로 따른다.

- 요청에 `scheduled_target=YYYY-MM-DD:morning|evening`을 고정한다. 서버에서는 요청 날짜와
  회차가 실제 생성 시각 및 실행 시각과 일치할 때만 처리한다. 지연 요청이 다음 회차로 바뀌지 않는다.
- 서버의 기존 공유 concurrency와 main에 먼저 push하는 회차 기록이 중복 방지의 기준이다.
  독립 타이머, 늦게 도착한 cron, 중복 dispatch가 같은 회차에 도착해도 한 번만 진행한다.
- 원격 회차가 `started/success/failure/cancelled` 중 하나면 재발행하지 않는다. 실패한 글을
  재생성하는 타이머가 아니다. 실패 복구는 기존 초안·공개 상태를 확인한 뒤 진행한다.
- 로컬 파일 잠금과 요청 전 기록으로 같은 호스트의 동시 요청을 막는다. 응답이 불명확하거나
  아직 서버 기록이 없으면 최소 15분 기다리고 회차당 최대 3회만 요청한다. 그 뒤에도 기록이
  없으면 `unconfirmed_dispatch_limit`/종료 코드 1로 남긴다. 접수 성공은 발행 성공이 아니다.
- 매 회차 첫 30분은 매분 확인하고 이후에는 5분마다 확인해 로그인/잠자기 해제 후 따라잡는다.
  오전은 17:59까지, 오후는 23:59까지이며 다음 날에 전날 글을 자동 보충하지 않는다.
- 원격 이력 조회·검증 실패는 요청 중단으로 처리한다. 인증정보/CLI 오류 원문은 출력하지 않는다.
  기존 `gh` 인증을 사용하고 새 토큰을 복사하거나 GitHub의 Codex 인증을 로컬로 내려받지 않는다.
- 새 회차 기록에는 `scheduled_for`, `run_created_at`, `start_delay_seconds`, `trigger`를
  남겨 설정 시각과 실제 시작 시각을 구분한다. 기존 이력은 보존한다.

### Mac 설치 절차 — PR 머지와 운영 위치 확정 후

2026-10-03 12:23 KST에 PR #77을 main으로 머지하고, 12:24 KST에 사용자 승인으로
이 Mac의 `blog.trendpulse.posting-timer` LaunchAgent를 등록했다. 운영 코드는
`/Users/admin/workSpace/wp-auto-blog/scripts/posting_timer.py`를 사용한다.
사용할 호스트가 상시 가동 서버라면 같은 스크립트를 해당 서버의 타이머로 매분 호출한다.
Mac LaunchAgent는 해당 사용자가 로그인한 상태에서 Mac이 깨어 있고 인터넷에 연결돼 있어야 한다.
컴퓨터를 깨우거나 부팅시키는 설정은 추가하지 않는다. GitHub runner 대기·네트워크 장애까지
없애지는 못하며 **09시 공개 완료 보장**이 아닌 **09시 발행 작업 요청**을 목표로 한다.

아래 명령은 승인된 main을 로컬 checkout에 반영한 뒤 실행한다. `python3`는 3.11 이상,
`gh`는 이 저장소의 contents 조회/actions 실행 권한이 있는 기존 인증이 필요하다.
실제 설치 전에 read-only 실행과 plist 내용을 확인한다. 구현 worktree를 영구 서비스 경로로 쓰지 않는다.

```sh
cd /Users/admin/workSpace/wp-auto-blog
TIMER_STATE="$HOME/Library/Application Support/TrendPulse/posting-timer"
TIMER_LOG='/Users/admin/Library/Mobile Documents/com~apple~CloudDocs/gpt 작업/wp-auto-blog/posting-timer-runtime'
TIMER_PLIST="$HOME/Library/LaunchAgents/blog.trendpulse.posting-timer.plist"

# 기본은 읽기 전용. 발행 요청이나 상태 파일 변경 없음.
python3 -B scripts/posting_timer.py --state-dir "$TIMER_STATE"

# 산출물은 지정된 작업 폴더, 상태는 로컬 전용 폴더.
mkdir -p "$TIMER_LOG" "$HOME/Library/LaunchAgents"
python3 -B scripts/posting_timer.py --state-dir "$TIMER_STATE" \
  --print-launchd-plist --log-dir "$TIMER_LOG" > "$TIMER_LOG/posting-timer.plist"
plutil -lint "$TIMER_LOG/posting-timer.plist"

# 기존 동일 label이 등록돼 있으면 덮어쓰기 전에 해당 서비스 소유/경로부터 확인.
cp "$TIMER_LOG/posting-timer.plist" "$TIMER_PLIST"
launchctl bootstrap "gui/$(id -u)" "$TIMER_PLIST"
launchctl print "gui/$(id -u)/blog.trendpulse.posting-timer"
```

등록 시 `RunAtLoad`가 현재 회차를 확인하므로 아직 시도하지 않은 회차라면 바로 요청한다.
plist에는 생성 시점의 Python·gh·스크립트 절대 경로를 넣으며 비밀값은 넣지 않는다.
시스템 시간대와 무관하게 매분 실행되는 스크립트가 KST 회차를 판정한다.
정시 캘린더 호출은 Mac 시간대를 따르지만 매분 호출을 함께 사용해 다른 시간대에서도 동작한다.

중단은 `launchctl bootout "gui/$(id -u)" "$TIMER_PLIST"`로 수행한다.
GitHub 기본 cron과 원격 이력은 그대로 남으므로 이미 공개된 글이나 과거 회차를 삭제하지 않는다.
매분 로그의 `dispatch_accepted` 뒤 실제 Actions 종료·회차 기록·공개 포스트 URL까지 확인해야
운영 발행 검증이 끝난다. 현재 로컬 회귀/읽기 전용 점검은 이 검증을 대신하지 않는다.

### 검증

- 예약 제어·타이머 및 관련 발행 워크플로 회귀 테스트 120개 통과: 중복 cron, 회차/날짜 경계, 응답 불명,
  요청 전 기록, 실제 별도 프로세스의 잠금 충돌, 재시도 제한, 원격 상태 오류, 실패 회차 비재시도 및 시간대 변환.
- 실제 GitHub 운영 이력 조회 성공. 10/2 오전 성공 회차에 대해 `already_attempted`를
  확인했다. read-only로 수행했으며 새 발행 요청·운영 데이터 변경은 없었다.
- 운영 main에서도 관련 테스트 120개 통과(7.28초).
- 운영 타이머 등록과 첫 실행 종료 코드 0을 확인했다. 12:25의 첫 발행 요청은 응답 불명으로
  기록됐고 15분 재시도 대기를 유지했다. 백그라운드 인증과 읽기/POST 진단은 정상 응답했다.
- 지난 날짜 회차 요청의 운영 진단 3건은 모두 성공 종료했고, `outside_requested_slot`로
  글 생성 전에 차단됐다. 진단 실행: 37093446410, 37093469969, 37093471410.
- 12:45:19 KST의 자동 재시도는 정상 접수됐다(`dispatch_accepted`). 실행 `37094260393`이
  같은 시각 생성되고 12:45:22 runner가 시작해 요청 후 약 3초 만에 실행됐다.
  원격 오전 회차는 `trigger=external_timer`, `claimed_at=12:45:30 KST`로 기록됐다.
  오늘 09시를 지난 뒤 설치했으므로 이 실행은 당일 오전 누락 복구 검증이다.
- 12:50:33 타이머가 원격 `started` 기록을 읽고 `already_attempted`로 추가 요청을 차단했다.
- 실제 발행 실행은 성공 종료됐다. 12:51:34 KST에
  [종합소득과세표준 핵심정리: 구간별 기본세율과 산출세액 계산](https://trendpulse.blog/income-tax-brackets-2026/)을 공개했다.
  `VERIFIED CODEX PUBLISHED`, 원격 회차 `success`, RSS 공개 시각, 본문 HTTP 200,
  canonical 일치, 대표 이미지 HTTP 200/image/jpeg를 확인했다.
- 이 검증은 **설치 당일 누락 복구 → 실제 공개 발행**이다. 09시/18시 정시 호출 자체는
  다음 예약 시각에 별도로 확인해야 하며, Mac의 로그인·각성·인터넷 연결 조건은 그대로다.

### Mac 전원과 무관한 서버 타이머 설치 상태

Hostinger PHP cron용 구현과 설치·검증 순서는
[서버 타이머 운영 문서](hostinger-posting-timer.md)에 있다.
2026-10-03 PR #80을 승인 후 머지하고 Hostinger에 PHP 파일·전용 토큰·매분 운영 cron을
설치했다. 서버 PHP 8.3.33에서 점검 실행이 성공했고, 21:45:02 KST 실제 운영 실행은
오늘 오후 성공 회차를 읽어 중복 요청을 차단했다. 토큰의 GitHub dispatch 권한과 다음
정시 회차의 발행 완료는 아직 미검증이다. 다음 미시도 회차인 2026-10-04 09:00 KST의
서버 요청·Actions 종료·공개 URL을 확인한 뒤 Mac LaunchAgent를 해제한다.
