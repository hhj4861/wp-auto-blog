# Phase 2 — Pinterest 자동 핀 설계 (bytepulse)

## 왜 Pinterest인가
- bytepulse 최강점 = **K-비주얼**(K-Beauty 66·K-Pop 62·K-Fashion 48·K-Food 15).
- Pinterest 주 사용자 = **영미권 여성** → K-뷰티/패션/푸드 타깃과 정확히 일치.
- 핀 1개 = **팔로우 백링크 + 실유입 + 에버그린**(핀은 Pinterest 검색에 수개월 노출, 트래픽 누적).
- 실유입이 곧 Google 크롤수요 신호 → 레버 B의 핵심.

## 아키텍처 (배치 방식 — 파이프라인과 디커플)
```
data/pin_registry.json  ← 이미 핀한 post_id 추적(중복 방지)
        │
scripts/pinterest_sync.py  ── K-* 미핀 글 조회(WP REST) → 핀 생성 → registry 갱신
        │  (일 N건 rate 제한)
src/pinterest.py  ── 클라이언트: 토큰 갱신·보드 확보·create_pin
        │
.github/workflows/pinterest-sync.yml  ── 매일 스케줄(N핀/일)
```
- **배치+스케줄**을 택한 이유: 발행 파이프라인과 분리 → 기존 456개 백필 가능, Pinterest 장애에 강함, rate 제어 쉬움, 실패해도 발행에 영향 없음.

## 핀 콘텐츠 스펙 (Pinterest API v5)
| 필드 | 값 | 비고 |
|---|---|---|
| board_id | 카테고리→보드 매핑 | K-Beauty/K-Fashion/K-Food/K-Pop 보드 |
| title | 글 제목 | ≤100자 |
| description | 메타설명 + 해시태그 | ≤500자. Pinterest 검색은 description 사용 → 핵심 |
| link | 글 URL | **백링크+유입** |
| media_source | `{source_type:"image_url", url: 히어로이미지}` | 기존 발행 히어로 재사용 |

- **해시태그 예**: K-Beauty→`#KBeauty #KoreanSkincare #KBeautyRoutine`, K-Pop→`#KPop #KPopNews`, K-Fashion→`#KFashion #KoreanStyle`, K-Food→`#KFood #KoreanFood`.
- **보드 매핑**: category name → board. 최초 실행 시 없으면 자동 생성(`POST /v5/boards`).

## API·인증 (Pinterest v5)
- **엔드포인트**: `POST https://api.pinterest.com/v5/pins`, `GET/POST /v5/boards`.
- **스코프**: `pins:write`, `boards:read`, `boards:write`, `user_accounts:read`.
- **토큰 수명**: access token ~30일, refresh token ~1년 → 클라이언트가 **매 실행 시 refresh로 access 재발급**(PINTEREST_REFRESH_TOKEN + APP_ID/SECRET).
- **이미지**: v5는 `image_url` 소스 지원 → WP 히어로 URL 그대로 전달(업로드 불필요).

## 사용자 셋업 (1회, ~15분)
1. **Pinterest 비즈니스 계정** 전환/생성 (무료): business.pinterest.com
2. **developer 앱 생성**: developers.pinterest.com → App → **App ID / App secret** 발급, redirect URI 등록
3. **OAuth 1회 인증** → refresh token 획득 (제가 `scripts/pinterest_oauth.py` 헬퍼 제공 — 로컬에서 URL 열고 코드 붙여넣으면 refresh token 출력)
4. **시크릿 등록**: `PINTEREST_APP_ID` · `PINTEREST_APP_SECRET` · `PINTEREST_REFRESH_TOKEN` (GitHub Secret + 로컬 .env)

## 내가 구현 (계정/토큰 준비되면)
- `src/pinterest.py` — 토큰 갱신, 보드 확보/생성, `create_pin()`
- `scripts/pinterest_oauth.py` — refresh token 발급 헬퍼(1회용)
- `scripts/pinterest_sync.py` — K-* 미핀 글 배치 핀 + `data/pin_registry.json` 갱신
- `.github/workflows/pinterest-sync.yml` — 매일 N핀(초기 백필은 며칠에 나눠서)
- 테스트: 매핑·dedup·해시태그·rate 상한

## 가드레일
- **중복 방지**: pin_registry로 이미 핀한 글 스킵.
- **rate 상한**: 일 5~10핀(스팸 플래그 회피). 456개 백필은 수주에 걸쳐 분산.
- **대상 한정**: K-* 카테고리만(테크는 Pinterest 부적합 → 제외).
- **정직**: 제목/설명 과장 금지, 실제 글 내용 반영.

## 단계
- **2a (MVP)**: 위 배치 파이프라인 — 히어로 이미지 그대로 사용. **바로 실유입 시작.**
- **2b (개선)**: **세로 2:3 핀 이미지**(1000×1500 캔버스에 제목 오버레이) 생성 — Pinterest CTR 크게 향상. 현재 히어로는 가로라 준최적. PIL/이미지 파이프라인으로 별도 생성.

## 솔직한 기대치
- Pinterest는 **에버그린**이라 초기 수주는 조용하다가 핀이 쌓이고 검색에 잡히며 트래픽이 누적됩니다(즉효 아님).
- **2b 세로 이미지가 성패를 크게 가름** — 가로 히어로는 클릭률이 낮음. MVP로 시작하되 2b를 빨리 붙이는 걸 권장.
- 레버 A(색인요청)·IndexNow와 병행. Pinterest 유입이 쌓이면 Google 크롤수요로 이어짐.
