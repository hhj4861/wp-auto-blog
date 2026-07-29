"""네이버 블로그용 변환 — WordPress 캐논 HTML을 SmartEditor 친화 형태로.

네이버 블로그는 공식 글쓰기 API가 없어(2017경 폐지) 자동 발행이 불가하다. 대신 이 모듈은
발행 시점에 **네이버 블로그에 붙여넣기 좋은 HTML을 로컬 파일로 저장**한다(반자동).

SmartEditor 특성:
  - 인라인 style(그라디언트 텍스트·박스 배경 등)은 대부분 무시/제거 → 걷어낸다.
  - 광고(AdSense) 불가 → 광고 슬롯은 애초에 raw ARTICLE에 없음(insert_monetization 전 단계).
  - 외부 링크(쿠팡 파트너스)는 허용되나 **의무 고지** 필요 → 명시 삽입.
  - 이미지(히어로)는 API로 못 올려 사람이 직접 업로드 → 본문엔 안내만.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# 네이버 블로그용 쿠팡 파트너스 의무 고지(짧은 표준 문구)
COUPANG_NAVER_DISCLOSURE = (
    "<p>이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.</p>"
)


def to_naver_blog(title: str, article_html: str, coupang_url: str | None = None) -> str:
    """캐논 ARTICLE HTML → 네이버 SmartEditor 친화 HTML.

    - 모든 인라인 style 제거(네이버가 어차피 제거/왜곡) → 태그 구조만 유지
    - 제목을 소제목으로 선두 배치, 이미지는 수동 업로드 안내 주석
    - 쿠팡 링크가 있으면 의무 고지문을 말미에 보장
    """
    html = article_html.strip()
    # ① 인라인 style 속성 전부 제거 (그라디언트 H2·박스 배경·색상 등)
    html = re.sub(r'\s+style="[^"]*"', "", html)
    # ② class/target/rel 등 편집기 노이즈 축소(링크의 href는 유지)
    html = re.sub(r'\s+(?:class|target|rel|loading|width|height|frameborder|allowfullscreen)="[^"]*"', "", html)
    # ③ 연속 공백/빈 속성 정리
    html = re.sub(r"<(\w+)\s+>", r"<\1>", html)

    body = [
        f"<h2>{title}</h2>",
        "<!-- 네이버 SmartEditor에 붙여넣기 · 대표 이미지는 직접 업로드하세요 -->",
        html,
    ]
    if coupang_url and COUPANG_NAVER_DISCLOSURE not in html and "쿠팡 파트너스" not in html:
        body.append(COUPANG_NAVER_DISCLOSURE)
    # 완전한 HTML 문서로 감싼다 — charset 선언이 없으면 브라우저/미리보기가 latin-1 로 열어
    # 한글이 깨진다(파일 바이트는 UTF-8 정상). 붙여넣기용 본문은 <body> 안이다.
    return (
        "<!doctype html>\n"
        '<html lang="ko"><head><meta charset="utf-8">'
        f"<title>{title}</title></head>\n<body>\n"
        + "\n".join(body)
        + "\n</body></html>\n"
    )


def save_naver_export(
    slug: str,
    title: str,
    article_html: str,
    coupang_url: str | None = None,
    outdir: str | None = None,
) -> Path:
    """네이버 블로그용 HTML을 `naver_export/<slug>.html` 로 저장(발행 시점 호출)."""
    base = Path(outdir) if outdir else Path(__file__).parent.parent / "naver_export"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{slug}.html"
    path.write_text(to_naver_blog(title, article_html, coupang_url), encoding="utf-8")
    print(f"네이버 블로그용 저장: {os.fspath(path)}")
    return path
