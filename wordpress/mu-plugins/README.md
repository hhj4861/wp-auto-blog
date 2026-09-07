# WordPress mu-plugins (수동 설치 필요)

이 디렉터리의 PHP 파일은 **WordPress 서버 쪽**에 설치해야 동작한다.
(이 repo의 파이프라인 코드가 아니라 bytepulse.io 호스팅에 올리는 파일)

## wpab-yoast-rest-meta.php

**목적:** 파이프라인이 REST로 보내는 Yoast 메타 중 WordPress가 조용히 버리는
`_yoast_wpseo_meta-robots-noindex` / `_yoast_wpseo_meta-robots-nofollow` 2종을
REST에 등록해 실제로 저장되게 한다.
(metadesc/focuskw/title 3종은 최신 Yoast가 이미 등록해줘서 저장됨 — 2026-07-21 실측)

**설치 (Hostinger hPanel 기준):**

1. hPanel → 파일 관리자 → `public_html/wp-content/` 이동
2. `mu-plugins` 폴더가 없으면 생성
3. `wpab-yoast-rest-meta.php` 업로드
4. 끝 — mu-plugin은 활성화 절차 없이 즉시 로드된다

**검증:**

```bash
python scripts/verify_yoast_meta.py
# 설치 전: FAIL (robots 2종 드롭)
# 설치 후: PASS (5종 모두 저장)
```

## wpab-rest-settings.php (v1.1)

**목적:** Yoast가 REST로 노출하지 않는 설정을 `/wp/v2/settings` 에 브릿지한다.

- `comment_moderation` / `comment_previously_approved` — 댓글 승인 정책
- `wpab_archive_index` — **아카이브 색인 여부**(`category` / `post_tag` / `author` / `date`).
  `true` = 검색결과 노출, `false` = noindex. 내부적으로 `WPSEO_Options::set()` 으로
  `noindex-tax-category` 등에 반영하며, **보낸 키만** 건드린다(다른 Yoast 설정 무영향).
  읽기는 저장값이 아니라 Yoast 실제 상태를 돌려주므로 둘이 어긋나지 않는다.

**설치:** hPanel → 파일 관리자 → `public_html/wp-content/mu-plugins/` 에 업로드 (활성화 불필요).
이미 구버전(v1.0)이 있으면 덮어쓰기.

**사용:**

```bash
python scripts/set_archive_index.py --site https://trendpulse.blog --show
python scripts/set_archive_index.py --site https://trendpulse.blog --category on
# 적용 후 카테고리 아카이브 HTML의 robots 메타까지 캐시버스터로 재확인해 출력한다
```
