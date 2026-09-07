#!/usr/bin/env python3
"""Yoast 아카이브 색인 설정을 원격(REST)으로 전환한다 — 카테고리/태그/저자/날짜.

Yoast는 이 설정(wpseo_titles의 noindex-*)을 REST로 노출하지 않는다. 서버에
`wordpress/mu-plugins/wpab-rest-settings.php`(v1.1+)가 설치돼 있어야 동작하며,
없으면 설치 안내만 출력하고 종료한다(exit 2).

사용:
  python scripts/set_archive_index.py --site https://trendpulse.blog --category on
  python scripts/set_archive_index.py --site https://trendpulse.blog --show

전환 후 실제 아카이브 HTML의 robots 메타를 캐시버스터로 재확인해 결과를 증명한다.
"""

import argparse
import os
import sys
import time
import urllib.parse

import requests

SETTING = "wpab_archive_index"
KEYS = ("category", "post_tag", "author", "date")
UA = {"User-Agent": "Mozilla/5.0 (wpab-archive-index)"}


def _auth():
    user = os.environ.get("WP_GENERAL_USERNAME") or os.environ.get("WP_USERNAME") or ""
    pw = os.environ.get("WP_GENERAL_APP_PASSWORD") or os.environ.get("WP_APP_PASSWORD") or ""
    if not user or not pw:
        sys.exit("자격증명 없음 — WP_USERNAME/WP_APP_PASSWORD (또는 WP_GENERAL_*) 필요")
    return (user, pw)


def _robots_meta(url: str) -> str:
    """캐시를 우회해 실제 서빙되는 robots 메타를 읽는다."""
    r = requests.get(f"{url}?nc={int(time.time())}", headers=UA, timeout=30)
    for quote in ("'", '"'):
        marker = f"<meta name={quote}robots{quote} content={quote}"
        i = r.text.find(marker)
        if i != -1:
            rest = r.text[i + len(marker):]
            return rest.split(quote, 1)[0]
    return "(robots 메타 없음)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=os.environ.get("WP_GENERAL_URL") or os.environ.get("WP_URL"))
    ap.add_argument("--show", action="store_true", help="현재 상태만 출력")
    for key in KEYS:
        ap.add_argument(f"--{key}", choices=("on", "off"),
                        help=f"{key} 아카이브 색인 on(검색결과 노출)/off(noindex)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    base = (args.site or "").rstrip("/")
    if not base:
        sys.exit("--site 또는 WP_URL 필요")
    auth = _auth()
    api = f"{base}/wp-json/wp/v2/settings"

    cur = requests.get(api, auth=auth, headers=UA, timeout=30)
    cur.raise_for_status()
    settings = cur.json()
    if SETTING not in settings:
        print(f"[중단] {base} 에 설정 브릿지가 없습니다.\n"
              f"       wordpress/mu-plugins/wpab-rest-settings.php (v1.1+)를\n"
              f"       hPanel → 파일 관리자 → public_html/wp-content/mu-plugins/ 에 업로드하세요.\n"
              f"       (mu-plugins 폴더가 없으면 생성. 활성화 절차 없음)")
        return 2

    # 옵션 행이 아직 없으면 WP가 등록 기본값(빈 배열)을 그대로 돌려준다 — 값 없음으로 취급.
    current = settings[SETTING] if isinstance(settings[SETTING], dict) else {}
    print(f"[현재] {base} 아카이브 색인 상태 (true=검색결과 노출)")
    for key in KEYS:
        print(f"  {key:<9} {current.get(key, '(미기록 — 최초 전환 시 Yoast 실제값이 채워짐)')}")

    desired = {k: (getattr(args, k) == "on") for k in KEYS if getattr(args, k)}
    if args.show or not desired:
        return 0

    print(f"\n[변경] {desired}")
    if args.dry_run:
        print("  (dry-run — 전송 안 함)")
        return 0

    res = requests.post(api, auth=auth, headers=UA, json={SETTING: desired}, timeout=30)
    res.raise_for_status()
    after = res.json().get(SETTING, {})
    if not isinstance(after, dict):
        after = {}
    print(f"[적용 후] {dict((k, after.get(k)) for k in KEYS)}")

    for key, want in desired.items():
        if bool(after.get(key)) is not want:
            print(f"[실패] {key} 가 {after.get(key)} 로 남았습니다.")
            return 1

    if "category" in desired:
        cats = requests.get(f"{base}/wp-json/wp/v2/categories?per_page=100&_fields=slug,count",
                            auth=auth, headers=UA, timeout=30).json()
        print("\n[라이브 검증] 카테고리 아카이브 robots 메타")
        for c in sorted(cats, key=lambda x: -x["count"])[:8]:
            url = f"{base}/category/{c['slug']}/"
            print(f"  {c['count']:>4}글  {urllib.parse.unquote(c['slug']):<14} {_robots_meta(url)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
