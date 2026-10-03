# Hostinger 독립 포스팅 타이머

## 적용 상태 — 2026-10-03

Mac이 꺼져 있어도 예약을 요청하도록 Hostinger Business Web Hosting의 PHP CLI cron을 사용한다.
글 생성과 WordPress 발행은 기존 GitHub Actions `main`에서 수행한다. 서버에 WordPress나
Codex 인증을 복사하지 않는다. GitHub cron은 보조 트리거로 유지한다.

현재는 구현 브랜치의 준비 단계다. Hostinger 로그인, PHP 8.3 표시, Cron Jobs 화면과
홈 디렉터리 접근은 확인했다. 브라우저 연결이 끊겨 **서버 업로드·cron 설치·서버 실행은 미완료**다.
기존 Mac LaunchAgent는 서버 검증이 끝날 때까지 유지한다. 로컬 PHP 8.4 검증이
호스팅 PHP 8.3에서 실행됐다는 의미는 아니다.

## 실행 계약

- `scripts/hostinger_posting_timer.php`는 PHP 8.3 이상과 cURL 확장이 있는 CLI에서 실행한다.
- 기본 실행은 읽기 전용이다. `--probe`는 시간과 무관하게 공개 원격 회차 이력을 읽는다.
  토큰 내용은 읽지 않으며 `token_file_present`는 인증 성공을 의미하지 않는다.
- `--apply`만 실제 요청을 보낸다. 매분 호출하되 내부에서 Asia/Seoul 09:00·18:00 회차를
  판정한다. 첫 30분은 매분, 이후는 5분 간격으로 원격 상태를 확인한다.
- 요청 대상은 `hhj4861/wp-auto-blog`, `auto-post.yml`, `ref=main`으로 고정한다.
  입력은 queue/codex/publish/scheduled_recovery와 고정된 날짜·회차다.
- 원격 이력이 started/success/failure/cancelled 중 하나면 더 요청하지 않는다.
  서버 잠금, POST 전 pending 기록, 15분 대기, 회차당 3회 제한으로 응답 불명도 처리한다.
  최종 중복 방지는 기존 Actions concurrency와 main의 회차 선점 기록이 담당한다.
- 조회·이력 검증 실패 시 발행하지 않는다. POST HTTP 상태 코드는 남기지만 응답 본문,
  인증 헤더나 예외 전문은 로그에 쓰지 않는다. 리다이렉트는 따르지 않고 HTTPS 검증을 유지한다.
- 접수 성공은 발행 성공이 아니다. 서버/GitHub 네트워크나 runner 장애까지 없애지는 못한다.
  목표는 09시·18시 발행 작업 요청이며 공개 완료 시각 보장은 아니다.

## 배포와 인증

1. 이 구현 PR의 명시적 머지 승인을 받고 main의 동일 파일을 배포한다.
2. Hostinger File Manager에서 **Access all files of Business Web Hosting**으로 홈에 접근한다.
   `/home/u573050372/trendpulse-posting-timer/`를 만든다. `domains`, `public_html` 등
   모든 사이트의 공개 문서 루트 밖이어야 한다. 폴더 권한은 700, PHP 파일은 600으로 둔다.
   스크립트를 실행하는 PHP 사용자가 파일 소유자인지 실제 probe로 확인한다.
3. 비밀값 없이 우선 다음 명령을 일회 점검 cron으로 실행하고 View Output의 `probe_ok`를 확인한다.

   ```sh
   /usr/bin/php /home/u573050372/trendpulse-posting-timer/hostinger_posting_timer.php --probe
   ```

4. GitHub에서 전용 fine-grained PAT를 준비한다. 대상은 **이 저장소 하나**,
   repository permission **Actions: Read and write**와 기본 Metadata read다.
   이 권한은 해당 저장소의 Actions 관리/실행 권한이며 단일 워크플로만으로 제한된 권한은 아니다.
   현재 공개 저장소의 이력 읽기에는 토큰이 필요 없어 Contents write나 계정 전체 권한은 부여하지 않는다.
   새 접근 부여와 Hostinger 저장은 사용자 확인 후 진행하고, 실제 값은 채팅·Git·로그로 받지 않는다.
5. 사용자가 전용 토큰을 서버의 같은 비공개 폴더 `github-token.txt`에 직접 입력한다.
   파일 권한은 **600**, 링크 파일은 허용하지 않는다. 개인 `gh` OAuth/기존 광범위 토큰이나
   Codex 인증을 가져오지 않는다. 만료 날짜와 교체 담당을 사용자와 정해 비밀값 없이 기록한다.
   토큰 만료/회수 시 발행 요청은 실패하므로 만료 전 교체와 확인이 필요하다.
6. probe 작업을 제거하고 다음 명령을 `* * * * *`로 등록한다. Hostinger cron은 UTC지만
   매분 실행과 스크립트 내부 KST 계산으로 시간대를 분리한다. 명령에 비밀값·리다이렉트를 넣지 않는다.

   ```sh
   /usr/bin/php /home/u573050372/trendpulse-posting-timer/hostinger_posting_timer.php --apply
   ```

7. 서버 출력, 실제 main Actions 실행, durable 회차 기록, 실행 종료, 공개 URL을 순서대로 확인한다.
   이미 시도한 회차의 `already_attempted`만으로 토큰의 실행 권한까지 검증했다고 하지 않는다.
   다음 미시도 회차의 실제 dispatch와 종료를 확인한다. 이력을 지우거나 현재 회차를 강제 재발행하지 않는다.
8. 서버 검증 후 Mac의 `blog.trendpulse.posting-timer` LaunchAgent를 중단/해제한다.
   Mac을 끈 다음 회차에서도 서버 호출을 확인해야 Mac 독립 운영 검증이 끝난다.

Hostinger의 설치/출력 절차:
[cron 설정](https://www.hostinger.com/support/1583465-how-to-set-up-a-cron-job-at-hostinger/),
[출력 확인](https://www.hostinger.com/support/5647075-how-to-check-the-output-of-a-cron-job-at-hostinger/).
토큰 권한 근거는 [GitHub workflow dispatch API](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event)다.

## 장애 확인과 중단

| 출력 | 의미와 조치 |
|---|---|
| `probe_ok` | 공개 이력 읽기만 확인됨. 인증·실제 발행은 별도 검증 |
| `dispatch_accepted` | GitHub 접수. Actions 실행/회차 결과 확인 필요 |
| `dispatch_unconfirmed` | 응답 불명 또는 거절. HTTP 코드 확인 후 15분 대기; 즉시 강제 재시도 금지 |
| `unconfirmed_dispatch_limit` | 3회 이후에도 회차 기록 없음. 토큰 만료/권한, GitHub 상태, cron 출력을 점검 |
| `already_attempted`, `already_claimed` | 이미 시도한 회차. 실패 회차도 자동 재발행하지 않음 |
| `timer_failed` | 읽기·상태·권한 등 오류. 원인을 해결하기 전 상태 파일을 임의 삭제하지 않음 |

서버 파일 `timer-state.json`, `timer.lock`은 운영 상태이며 Git이나 클라우드 로그로 옮기지 않는다.
오래된 회차 캐시는 14일 기준으로 정리한다. 타이머 자체 실패 알림은 아직 자동 발송하지 않으며
Hostinger View Output을 확인해야 한다. 기존 Actions에 진입한 후의 실패 알림은 기존 정책을 따른다.
중단 시 이 작업의 cron만 비활성화/제거하고 기존 GitHub cron과 발행 이력은 보존한다.

## 검증 근거

- 로컬 PHP 8.4.8 문법 검사 성공.
- PHP 실제 실행 기반 테스트와 기존 Python 타이머/회차 테스트 합계 130개 통과.
- KST 경계, 실패 이력 재발행 차단, 응답 불명 대기/횟수 제한, POST 전 기록,
  원격/로컬 이력 손상, 비공개 토큰 권한, 실제 별도 프로세스 잠금 충돌을 검증했다.
- 로컬 `--probe`에서 실제 원격 이력을 읽고 2026-10-03 오후 회차 success를 확인했다.
  인증 없이 조회했으며 새 발행 요청은 보내지 않았다.
- 호스팅 PHP 8.3 probe, 서버 인증 dispatch, cron 주기 실행, Mac 해제는 미검증/미적용이다.
