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
