#!/usr/bin/env python3
"""선정 키워드 → 캐논 발행 스크립트 **스캘폴드** 자동생성 (C안).

data/blog_targets.json 의 선정 키워드마다 trendpulse(한글)+bytepulse(영문) 발행 스크립트를
생성한다. **배관(imports·포맷·올리브영 제휴·쿠팡 고지·히어로·발행·네이버 export)은 전부 완성**돼
있고, 본문·FAQ·출처·제목·슬러그만 `[[TODO]]` 로 남는다 — 사람/AI가 내용만 채우면 바로 발행.

이렇게 하면 '대량 LLM 자동생성'의 품질저하 없이, 선정~배관은 자동이고 콘텐츠는 검수 품질을 유지한다.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
TARGETS = ROOT / "data" / "blog_targets.json"

# 간이 로마자(슬러그 후보용) — 없으면 keyword-N 로 폴백. 사람이 최종 슬러그를 정한다.
ROMAN = {
    "나이아신아마이드": "niacinamide", "알룰로스": "allulose", "비타민b": "vitamin-b",
    "비오틴": "biotin", "종합비타민": "multivitamin", "프로바이오틱스": "probiotics",
    "수분크림": "hydrating-cream", "히알루론산앰플": "hyaluronic-acid-ampoule",
    "기미크림": "dark-spot-cream", "pdrn앰플": "pdrn-ampoule", "탈모샴푸": "hair-loss-shampoo",
}


def slugify(keyword: str) -> str:
    key = re.sub(r"\s+", "", keyword).lower()
    return ROMAN.get(key, "todo-slug") + "-guide-2026"


TREND_TEMPLATE = '''#!/usr/bin/env python3
"""{keyword} 가이드 (trendpulse, 한글) — [[스캘폴드: 본문 TODO 채우기]].
검색모듈 블로그용 선정 키워드(월검색량 {volume:,}). 캐논 포맷·올리브영·쿠팡고지·네이버 export 배선 완료.
"""
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.monetization import (  # noqa: E402
    COUPANG_DISCLOSURE, add_coupang_disclosure, check_quality, insert_monetization,
)
from src.post_format import H2_GRADIENT as H2, P, UL, LI, faq_section, sources_section  # noqa: E402
from src.naver_format import save_naver_export  # noqa: E402

SLUG = "{slug}"
TITLE = "[[TODO 제목]] — {keyword} (2026)"
META_DESC = "[[TODO 메타설명 150자 내외]]"
FOCUS_KW = "{keyword}"
OLIVE = ("https://global.oliveyoung.com/display/search?query="
         + quote("{keyword}") + "&rwardCode=HHJZ4861&utm_source=influencers")
COUPANG = None  # [[TODO 쿠팡 딥링크 있으면 "https://link.coupang.com/a/XXXX"]]

DISCLOSURE = (
    '<div style="background:#2d2d3a;border-left:4px solid #10b981;padding:14px 18px;'
    'margin:0 auto 22px auto;max-width:800px;border-radius:6px;font-size:0.9em;color:#cbd5e1;">'
    '<strong style="color:#6ee7b7;">제휴 안내:</strong> 이 글의 일부 링크는 제휴 링크로, '
    '구매 시 소정의 수수료를 받을 수 있습니다(구매자 추가 부담 없음).</div>'
)


def olive_link(label):
    return (f'<p style="max-width:800px;margin:24px auto;"><a href="{{OLIVE}}" target="_blank" '
            f'rel="nofollow sponsored" style="display:inline-block;background:#a259c4;color:#fff;'
            f'padding:12px 26px;border-radius:8px;text-decoration:none;font-weight:bold;">'
            f'🫒 {{label}} 올리브영에서 보기 →</a></p>')


def product_button(label, url):
    return (f'<p style="max-width:800px;margin:24px auto;"><a href="{{url}}" target="_blank" '
            f'rel="nofollow sponsored" style="display:inline-block;background:#e84c3d;color:#fff;'
            f'padding:12px 26px;border-radius:8px;text-decoration:none;font-weight:bold;">'
            f'🛒 {{label}} 쿠팡 최저가 보기 →</a></p>')


# [[TODO: 실제 성분 근거로 4개 Q&A 작성 — 지어내지 말 것]]
FAQ = [
    ("Q1. [[TODO]]", "[[TODO 답변]]"),
    ("Q2. [[TODO]]", "[[TODO 답변]]"),
    ("Q3. [[TODO]]", "[[TODO 답변]]"),
    ("Q4. [[TODO]]", "[[TODO 답변]]"),
]
# [[TODO: 공신력 출처만 — (기관) 설명]]
SOURCES = [
    "(식품의약품안전처) [[TODO]]",
    "(질병관리청 국가건강정보포털) [[TODO]]",
    "(대한[[TODO]]학회) [[TODO]]",
]

# [[TODO: 아래 섹션 본문을 성분·근거·주의 중심으로 작성(조작 없음). 기존 발행글(바쿠치올/알부틴) 참고.]]
ARTICLE = f"""
{{P}}[[TODO 인트로: {keyword} 가 뭐고 왜 관심인지]]</p>

{{H2}}[[TODO 소제목 1]]</h2>
{{P}}[[TODO 본문]]</p>

{{H2}}[[TODO 소제목 2 — 비교/차이]]</h2>
{{P}}[[TODO 본문]]</p>

{{H2}}이런 사람에게 맞다</h2>
{{UL}}
{{LI}}[[TODO]]</li>
</ul>

{{H2}}어떻게 고르나</h2>
{{P}}[[TODO 고르는 기준]]</p>
{{product_button("{keyword}", COUPANG) if COUPANG else ""}}
{{olive_link("{keyword}")}}

{{H2}}주의사항</h2>
{{P}}[[TODO 주의]]</p>

{{H2}}결론</h2>
{{P}}[[TODO 결론]]</p>

{{faq_section(FAQ)}}

{{sources_section(SOURCES)}}
"""


def fetch_hero(api, auth):
    key = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
    if not key:
        return None, ""
    try:
        r = requests.get("https://api.unsplash.com/search/photos",
                         params={{"query": "[[TODO unsplash query]] healthy", "per_page": 1,
                                  "orientation": "landscape"}},
                         headers={{"Authorization": f"Client-ID {{key}}"}}, timeout=20)
        r.raise_for_status()
        photo = r.json()["results"][0]
        img = requests.get(photo["urls"]["regular"], timeout=30); img.raise_for_status()
        up = requests.post(f"{{api}}/media", auth=auth,
                           headers={{"Content-Disposition": 'attachment; filename="{slug}.jpg"',
                                     "Content-Type": "image/jpeg"}}, data=img.content, timeout=60)
        up.raise_for_status(); media = up.json()
        requests.post(f"{{api}}/media/{{media['id']}}", auth=auth,
                      json={{"alt_text": photo.get("alt_description") or "{keyword}"}}, timeout=20)
        fig = ('<figure class="wp-block-image aligncenter size-large hero-image" '
               'style="max-width:800px;margin:0 auto 30px auto;">'
               f'<img src="{{media.get("source_url","")}}" alt="{keyword}" '
               'style="width:100%;max-width:800px;height:auto;border-radius:12px;"/>'
               f'<figcaption style="text-align:center;font-size:0.85em;color:#888;margin-top:10px;">'
               f'Photo by {{photo["user"]["name"]}}</figcaption></figure>\\n')
        return media["id"], fig
    except Exception as e:
        print(f"히어로 실패(생략): {{e}}"); return None, ""


def main():
    base = os.environ["WP_GENERAL_URL"].rstrip("/")
    auth = (os.environ["WP_GENERAL_USERNAME"], os.environ["WP_GENERAL_APP_PASSWORD"])
    api = f"{{base}}/wp-json/wp/v2"
    if "[[TODO" in ARTICLE or "[[TODO" in TITLE:
        print("스캘폴드 미완성([[TODO]] 잔존) — 본문 채운 뒤 발행하세요."); return 1
    media_id, hero = fetch_hero(api, auth)
    html = insert_monetization(ARTICLE.strip(), related_posts=[])
    if COUPANG:
        html = add_coupang_disclosure(html); assert COUPANG_DISCLOSURE in html
    html = f'<div class="post-content category-건강" data-category="건강">\\n{{hero}}{{DISCLOSURE}}\\n{{html}}\\n</div>'
    issues = check_quality(title=TITLE, html=html, focus_keyphrase=FOCUS_KW,
                           meta_description=META_DESC, require_korean=True)
    if issues:
        print(f"품질 게이트 실패: {{issues}}"); return 1
    cat = requests.get(f"{{api}}/categories", auth=auth,
                       params={{"search": "건강", "_fields": "id,name"}}, timeout=30).json()
    cat_ids = [c["id"] for c in cat if c["name"] == "건강"][:1]
    body = {{"title": TITLE, "slug": SLUG, "content": html, "excerpt": META_DESC,
            "status": "publish", "categories": cat_ids,
            "meta": {{"_yoast_wpseo_metadesc": META_DESC, "_yoast_wpseo_focuskw": FOCUS_KW,
                     "_yoast_wpseo_title": f"{{TITLE}} | TrendPulse"}}}}
    if media_id:
        body["featured_media"] = media_id
    dup = requests.get(f"{{api}}/posts", auth=auth,
                       params={{"slug": SLUG, "status": "publish,draft", "_fields": "id"}}, timeout=30).json()
    if dup:
        r = requests.post(f"{{api}}/posts/{{dup[0]['id']}}", auth=auth, json=body, timeout=60)
    else:
        r = requests.post(f"{{api}}/posts", auth=auth, json=body, timeout=60)
    r.raise_for_status(); print(f"발행 완료: {{r.json()['link']}}")
    save_naver_export(SLUG, TITLE, ARTICLE, coupang_url=COUPANG)
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def main() -> int:
    if not TARGETS.exists():
        print(f"{TARGETS} 없음 — 먼저 select_blog_keywords.py 실행")
        return 1
    data = json.loads(TARGETS.read_text(encoding="utf-8"))
    made = []
    for item in data.get("selected", []):
        kw = item["keyword"]
        vol = item.get("volume", 0)
        slug = slugify(kw)
        code = TREND_TEMPLATE.format(keyword=kw, slug=slug, volume=vol)
        dest = ROOT / "scripts" / f"draft_{slug.replace('-guide-2026','')}_trend.py"
        dest.write_text(code, encoding="utf-8")
        made.append(str(dest.relative_to(ROOT)))
    print(f"스캘폴드 {len(made)}개 생성 (본문 [[TODO]] 채운 뒤 발행):")
    for m in made:
        print(f"  - {m}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
