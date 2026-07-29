#!/usr/bin/env python3
"""Greek yogurt as a Korean diet trend (bytepulse.io, English, K-Food).

블로그용 검색량 상위 '그릭요거트'의 영문판 — **정체성 정합을 위해 '한국 다이어트/웰니스
트렌드' 각도로 재구성**(홈메이드 그릭요거트 열풍·K-diet). bytepulse K-Food 카테고리(172).
포맷: post-content category-k-food 래퍼·Unsplash 히어로·FTC 고지·오렌지 그라디언트 H2·
인라인 제휴(Amazon tag + Olive Young Global rwardCode)·FAQ·References. **가짜 저자박스 제외**.
정직성: 영양·근거·주의 중심, 조작 없음. 로컬 발행. 멱등.
"""

import os
import sys
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.monetization import check_quality  # noqa: E402

SLUG = "korean-greek-yogurt-diet-trend-2026"
TITLE = "Why Greek Yogurt Became Korea's Favorite Diet Food (2026 K-Diet Guide)"
META_DESC = (
    "Homemade Greek yogurt is a huge Korean diet trend. Here's why — protein, gut health, "
    "how it differs from regular yogurt, and how to choose one. 2026 K-diet guide."
)
FOCUS_KW = "korean greek yogurt"
CAT_ID = 172  # K-Food
AMAZON = "https://amzn.to/4fEE2OL"  # SiteStripe, tag=bytepulse08-20
OLIVE = ("https://global.oliveyoung.com/display/search?query="
         + quote("probiotics") + "&rwardCode=HHJZ4861&utm_source=influencers")

# K-Food 카테고리 오렌지 그라디언트 (사이트 테마 category_accents 준수)
H2 = ('<h2 style="font-size:1.5em;margin:40px auto 20px auto;max-width:800px;'
      'background:linear-gradient(135deg,#fb923c,#f97316);-webkit-background-clip:text;'
      '-webkit-text-fill-color:transparent;background-clip:text;">')
P = '<p style="max-width:800px;margin:20px auto;text-align:left;line-height:1.8;color:#cbd5e1;">'
UL = '<ul style="max-width:800px;margin:20px auto;line-height:1.8;color:#cbd5e1;padding-left:24px;">'
LI = '<li style="margin-bottom:8px;">'

FTC = (
    '<div class="ftc-disclosure" style="background-color: #1a1a2e; border-left: 4px solid '
    '#fb923c; padding: 15px 20px; margin-bottom: 25px; border-radius: 4px; font-size: 14px; '
    'color: #cbd5e1;">\n<strong style="color: #fdba74;">Transparency Note:</strong> This post '
    'contains affiliate links. If you purchase through these links, we may earn a small '
    'commission at no extra cost to you. This helps support our content. Thank you!\n</div>'
)


def amazon_link(text: str) -> str:
    return (f'<a href="{AMAZON}" target="_blank" rel="nofollow sponsored" '
            f'style="color:#fb923c;font-weight:600;">{text}</a>')


def olive_link(text: str) -> str:
    return (f'<a href="{OLIVE}" target="_blank" rel="nofollow sponsored" '
            f'style="color:#9b59b6;font-weight:600;">{text}</a>')


def faq_section_en(pairs: list) -> str:
    boxes = []
    styles = [("#2d2d3a", "#fdba74"), ("#252532", "#fb923c")]
    for i, (q, a) in enumerate(pairs):
        bg, qc = styles[i % 2]
        boxes.append(
            f'<div style="background:{bg};padding:20px;border-radius:10px;margin-bottom:15px;">'
            f'<p style="color:{qc};font-weight:bold;margin:0 0 10px 0;">{q}</p>'
            f'<p style="color:#cbd5e1;margin:0;line-height:1.8;">{a}</p></div>'
        )
    return (f"{H2}Frequently Asked Questions</h2>\n"
            f'<div style="max-width:800px;margin:20px auto;">\n' + "\n".join(boxes) + "\n</div>")


def sources_section_en(items: list) -> str:
    lis = "".join(
        f'<li><span style="color:#94a3b8;font-size:0.85em;">{it}</span></li>' for it in items)
    return (
        '<div style="margin:30px auto;padding:20px;background:#2d2d3a;border-radius:8px;'
        'max-width:800px;"><h3 style="color:#fdba74;margin-top:0;">📚 References</h3>'
        f'<ul style="color:#94a3b8;padding-left:20px;line-height:1.8;">{lis}</ul></div>'
    )


FAQ = [
    ("Why is Greek yogurt so popular in Korea?",
     "Korea's health-and-diet culture loves <strong style=\"color:#fdba74\">high-protein, low-"
     "sugar</strong> foods, and homemade Greek yogurt (making it by straining regular yogurt) "
     "became a viral trend for its thick texture and macro-friendly profile."),
    ("How is Greek yogurt different from regular yogurt?",
     "It's regular yogurt with the <strong style=\"color:#fb923c\">whey strained out</strong>, so "
     "it's more concentrated — roughly <strong style=\"color:#fdba74\">double the protein</strong>, "
     "thicker, and lower in lactose. Calories per gram can be higher, so check the label."),
    ("Is it good for weight loss?",
     "The high protein keeps you <strong style=\"color:#fdba74\">full longer</strong> and supports "
     "muscle, which is why it's a diet staple. Just choose <strong style=\"color:#fb923c\">"
     "unsweetened</strong> — flavored tubs can be high in added sugar."),
    ("Can I make Greek yogurt at home?",
     "Yes — that's the Korean trend. Strain plain yogurt through a cloth/filter in the fridge for "
     "several hours; the longer you strain, the thicker it gets. Cheaper than store tubs and you "
     "control the ingredients."),
]
SOURCES = [
    "(U.S. FDA / USDA) Yogurt nutrition and dairy labeling information",
    "(Harvard T.H. Chan School of Public Health) Protein and probiotics general guidance",
    "(Cleveland Clinic) Greek yogurt and gut-health general information",
]

ARTICLE = f"""
{P}Walk through any Korean grocery aisle or health-food café and you'll see it everywhere:
<strong>Greek yogurt</strong>. In Korea it's less a Mediterranean import and more a full-blown
<strong>diet trend</strong> — including a viral wave of people <em>straining their own</em> at
home. This guide covers why it took off, how it compares to regular yogurt, and how to choose one
— <strong>nutrition first</strong>.</p>

{H2}Why Greek Yogurt Is a Korean Diet Staple</h2>
{P}Korea's wellness culture prizes <strong>high-protein, low-sugar</strong> eating, and Greek
yogurt fits perfectly. The homemade version — straining plain yogurt until it's thick and
spoon-standing — went viral for being cheap, customizable, and macro-friendly. It shows up in
diet bowls, high-protein desserts, and café menus across Seoul.</p>

{H2}Greek vs. Regular Yogurt — The Difference</h2>
{P}Greek yogurt is regular yogurt with the <strong>whey (liquid) strained out</strong>. Removing
water concentrates it, so the same serving has <strong>about double the protein</strong>, a
thicker texture, and somewhat less lactose. The trade-off: fat and calories per gram can run
higher, so the label still matters.</p>
{UL}
{LI}<strong>Protein</strong> — concentrated, roughly 2× regular yogurt (great for satiety)</li>
{LI}<strong>Texture</strong> — thick, spoon-standing</li>
{LI}<strong>Lactose</strong> — somewhat lower (often easier on sensitive stomachs)</li>
{LI}<strong>Probiotics</strong> — a fermented dairy, may support gut health (varies by product)</li>
</ul>

{H2}How to Choose (or Make) One</h2>
{P}Three checks: ① prefer <strong>unsweetened</strong> and add fruit/honey yourself, ② compare
<strong>protein per 100g</strong> (real Greek runs high), ③ keep ingredients simple (milk +
cultures, minimal thickeners). Prefer making your own? Strain plain yogurt in the fridge — longer
strain, thicker result. If you'd rather buy tubs, starters, or strainers, browse
{amazon_link("Greek yogurt and yogurt makers")} on Amazon.</p>

{H2}Want the Gut-Health Angle Too?</h2>
{P}Greek yogurt has live cultures, but processing can reduce them. If gut health is your main
goal, pairing it with a dedicated <strong>probiotic</strong> is more reliable. You can compare
inner-beauty probiotics on {olive_link("Olive Young Global")} (ships internationally).</p>

{H2}A Couple of Cautions</h2>
{P}Two things. First, "diet" tubs can be <strong>loaded with added sugar</strong> — unsweetened is
the safer default. Second, if you're <strong>lactose-sensitive</strong>, start small; Greek is
lower-lactose but not lactose-free.</p>

{H2}Bottom Line</h2>
{P}In short: Greek yogurt earned its Korean-diet fame for being <strong>high-protein, filling, and
versatile</strong>. Choose unsweetened, compare protein, and — very Korean — consider straining
your own. It's a genuinely useful protein anchor, as long as you watch the sugar.</p>

{faq_section_en(FAQ)}

{sources_section_en(SOURCES)}
"""


def fetch_hero(api: str, auth: tuple) -> tuple:
    key = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
    if not key:
        print("UNSPLASH key absent — skipping hero")
        return None, ""
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": "greek yogurt bowl healthy breakfast", "per_page": 1,
                    "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {key}"}, timeout=20,
        )
        r.raise_for_status()
        photo = r.json()["results"][0]
        alt = photo.get("alt_description") or "greek yogurt bowl"
        credit = photo["user"]["name"]
        img = requests.get(photo["urls"]["regular"], timeout=30)
        img.raise_for_status()
        up = requests.post(
            f"{api}/media", auth=auth,
            headers={"Content-Disposition": 'attachment; filename="greek-yogurt-hero.jpg"',
                     "Content-Type": "image/jpeg"},
            data=img.content, timeout=60)
        up.raise_for_status()
        media = up.json()
        requests.post(f"{api}/media/{media['id']}", auth=auth,
                      json={"alt_text": alt}, timeout=20)
        figure = (
            '<figure class="wp-block-image aligncenter size-large hero-image" '
            'style="max-width:800px;margin:0 auto 30px auto;">'
            f'<img src="{media.get("source_url","")}" alt="{alt}" '
            'style="width:100%;max-width:800px;height:auto;border-radius:12px;"/>'
            '<figcaption style="text-align:center;font-size:0.85em;color:#888;'
            f'margin-top:10px;">Photo by {credit}</figcaption></figure>\n'
        )
        print(f"hero uploaded: media #{media['id']}")
        return media["id"], figure
    except Exception as e:
        print(f"hero failed (skipping): {e}")
        return None, ""


def main() -> int:
    base = os.environ["WP_URL"].rstrip("/")
    auth = (os.environ["WP_USERNAME"], os.environ["WP_APP_PASSWORD"])
    api = f"{base}/wp-json/wp/v2"

    media_id, hero = fetch_hero(api, auth)
    body_html = (
        f'<div class="post-content category-k-food" data-category="K-Food">\n'
        f'{hero}{FTC}\n{ARTICLE.strip()}\n</div>'
    )

    issues = check_quality(
        title=TITLE, html=body_html, focus_keyphrase=FOCUS_KW,
        meta_description=META_DESC, require_korean=False,
    )
    if issues:
        print(f"quality gate failed: {issues}")
        return 1
    print("quality gate passed")

    payload = {
        "title": TITLE, "slug": SLUG, "content": body_html, "excerpt": META_DESC,
        "status": "publish", "categories": [CAT_ID],
        "meta": {"_yoast_wpseo_metadesc": META_DESC,
                 "_yoast_wpseo_focuskw": FOCUS_KW,
                 "_yoast_wpseo_title": f"{TITLE} | BytePulse"},
    }
    if media_id:
        payload["featured_media"] = media_id

    dup = requests.get(
        f"{api}/posts", auth=auth,
        params={"slug": SLUG, "status": "publish,draft", "_fields": "id"}, timeout=30,
    ).json()
    if dup:
        r = requests.post(f"{api}/posts/{dup[0]['id']}", auth=auth, json=payload, timeout=60)
        r.raise_for_status()
        print(f"updated: {r.json()['link']}")
    else:
        r = requests.post(f"{api}/posts", auth=auth, json=payload, timeout=60)
        r.raise_for_status()
        print(f"published: {r.json()['link']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
