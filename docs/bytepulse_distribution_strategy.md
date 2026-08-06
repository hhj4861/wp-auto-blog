# bytepulse 레버 B — 배포·크롤수요 전략

## 문제 재정의
색인 7/469. 사이트맵·robots 정상, 기사 전부 `index,follow`. 그런데 Google이 개별 페이지를
크롤하지 않음 = **크롤 수요 0**. 근본 원인 = **외부 신호(트래픽·링크) 0** + 대량 AI 품질.

## 원칙 (중요)
- ❌ **하지 않을 것**: PBN, 유료 링크팜, 디렉토리 블라스트, 댓글/포럼 스팸, 자동 대량 프로필.
  → Google 페널티 + 효과 없음 + 계정 밴 리스크.
- ✅ **할 것**: "링크"가 아니라 **배포**. 콘텐츠가 실제로 맞는 플랫폼에 올려 **진짜 사람 유입**을
  만든다. 유입 트래픽 자체가 Google에 "이 사이트는 살아있다 → 크롤할 가치 있다"는 신호.
- 전제: **K-콘텐츠(비주얼·트렌드)가 bytepulse의 최강점**(K-Beauty 66·K-Pop 62·K-Fashion 48).
  경쟁 심한 테크보다 **비주얼 플랫폼(Pinterest·숏폼)에서 이길 확률이 높다.** 레버를 여기 집중.

## 채널 매트릭스 (적합도·효과 순)
| # | 채널 | 적합 카테고리 | 효과 | 자동화 | 필요한 사용자 셋업 |
|---|---|---|---|---|---|
| 1 | **Pinterest** | K-Beauty·K-Fashion·K-Food·K-Pop | ★★★ 백링크+실유입 (영미권 여성층) | 발행 시 자동 핀 생성 | 비즈니스 계정 + API 토큰 |
| 2 | **Bing Webmaster + IndexNow** | 전체 | ★★ Bing 색인(구글보다 빠름)+일부 트래픽 | 이미 코드 있음(setup_indexnow.py) | Bing WMT에 사이트 추가(1회) |
| 3 | **숏폼 비디오**(TikTok/YT Shorts/Reels) | K-Pop·K-Beauty | ★★★ 실유입 큼 | commerce-automation-kit 비디오 파이프라인 활용 | 계정 + 업로드 채널 |
| 4 | **owned 네트워크 상호링크** | 전체 | ★ 크롤 브리지 | 코드로 삽입 가능 | 없음(내가 구현) |
| 5 | **dev.to / Medium 신디케이션** | AI Tools·Dev | ★★ 백링크+테크 유입 | 발행 시 canonical 크로스포스트 | dev.to/Medium API 키 |
| 6 | **Reddit/니치 커뮤니티**(r/KBeauty·r/kpop) | K-콘텐츠 | ★★ 고품질 유입 | 불가(수동, 진정성 필수) | 계정 + 진짜 참여 |

## 단계별 실행
**Phase 1 — 빠른 착수 (이번 주, 저비용)**
- **Bing Webmaster + IndexNow 정비**: 사용자가 Bing WMT에 bytepulse 추가 → 내가 IndexNow를
  bytepulse에 확실히 배선(현재 setup_indexnow.py 점검). Bing이 크롤/색인 시작 = 첫 외부 크롤 신호.
- **owned 상호링크**: trendpulse의 관련 글 → bytepulse(토픽 맞을 때), hanmadi 앱 푸터 → bytepulse.
  내가 코드로 삽입. (자기 네트워크라 안전, 크롤 브리지.)

**Phase 2 — 최강 레버 (K-콘텐츠 배포)**
- **Pinterest 자동 핀**: 사용자가 비즈니스 계정+API 발급 → 발행 파이프라인에 "핀 생성" 스텝 추가
  (히어로 이미지+제목+링크, 카테고리별 보드). 내가 구현. K-Beauty/Fashion/Food/Pop에 최적.
- **숏폼 1채널 집중**: K-Pop 트렌드(예: 오늘 BTS 글) 30초 영상 → 설명란 bytepulse 링크.
  기존 shopshorts 인프라 재사용.

**Phase 3 — 테크 신디케이션 (선택)**
- dev.to/Medium에 AI Tools 글 canonical 크로스포스트(자동). 테크 유입+백링크.

## 내가 바로 구현 가능 vs 사용자 셋업 필요
- **내가 구현**: IndexNow bytepulse 배선 점검, owned 상호링크 삽입, (계정 생기면) Pinterest 자동핀·
  dev.to 신디케이션 파이프라인 스텝.
- **사용자 셋업(계정/토큰)**: Bing WMT 사이트 추가, Pinterest 비즈니스+API, 숏폼 채널, dev.to 키.

## 솔직한 기대치
- 배포는 **느리다**(수주~수개월) + **계정·꾸준함이 필요한 사람 작업**이 핵심. 자동화는 증폭기일 뿐.
- **콘텐츠가 매력 없으면 배포도 저조**. K-비주얼은 AI 보조여도 이미지·훅이 좋으면 통함 → 여기 집중.
- Phase 1(Bing/IndexNow+상호링크)이 **첫 외부 크롤 신호**를 만드는 최소 비용 진입점.
- 이 레버는 [[레버 A: GSC 색인요청]]과 **병행** — A는 강제 크롤, B는 지속 크롤수요.
