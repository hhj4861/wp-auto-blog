#!/usr/bin/env python3
"""Arbutin cream / brightening guide (bytepulse.io, English, K-Beauty).

검색모듈 2위 키워드 '알부틴 크림'(opp 55) 영문판. bytepulse K-Beauty 실측 포맷 일치:
post-content category-k-beauty 래퍼·Unsplash 히어로·FTC 고지 박스·핑크 그라디언트 H2·
인라인 제휴 링크(Olive Young Global rwardCode)·FAQ·참고자료. **가짜 저자박스 제외**.
수익화: 올리브영만(사용자 지시). 정직성: 성분·근거·주의 중심, 조작 없음. 로컬 발행. 멱등.
"""

import os
import sys
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.monetization import check_quality  # noqa: E402

SLUG = "arbutin-cream-brightening-guide-2026"
TITLE = "Arbutin Cream: Does This Gentle Brightener Actually Fade Dark Spots? (2026)"
META_DESC = (
    "Arbutin is the gentle, hydroquinone-alternative brightener in K-beauty. Here's how it "
    "works, alpha vs beta arbutin, how it compares to vitamin C, and how to use it — 2026 guide."
)
FOCUS_KW = "arbutin cream"
CAT_ID = 213  # K-Beauty
OLIVE = ("https://global.oliveyoung.com/display/search?query="
         + quote("arbutin") + "&rwardCode=HHJZ4861&utm_source=influencers")
AMAZON = "https://amzn.to/3TpjfYe"  # SiteStripe 검색링크(alpha arbutin cream), tag=bytepulse08-20

H2 = ('<h2 style="font-size:1.5em;margin:40px auto 20px auto;max-width:800px;'
      'background:linear-gradient(135deg,#f472b6,#ec4899);-webkit-background-clip:text;'
      '-webkit-text-fill-color:transparent;background-clip:text;">')
P = '<p style="max-width:800px;margin:20px auto;text-align:left;line-height:1.8;color:#cbd5e1;">'
UL = '<ul style="max-width:800px;margin:20px auto;line-height:1.8;color:#cbd5e1;padding-left:24px;">'
LI = '<li style="margin-bottom:8px;">'

FTC = (
    '<div class="ftc-disclosure" style="background-color: #1a1a2e; border-left: 4px solid '
    '#f472b6; padding: 15px 20px; margin-bottom: 25px; border-radius: 4px; font-size: 14px; '
    'color: #cbd5e1;">\n<strong style="color: #f9a8d4;">Transparency Note:</strong> This post '
    'contains affiliate links. If you purchase through these links, we may earn a small '
    'commission at no extra cost to you. This helps support our content. Thank you!\n</div>'
)


def olive_link(text: str) -> str:
    return (f'<a href="{OLIVE}" target="_blank" rel="nofollow sponsored" '
            f'style="color:#9b59b6;font-weight:600;">{text}</a>')


def amazon_link(text: str) -> str:
    return (f'<a href="{AMAZON}" target="_blank" rel="nofollow sponsored" '
            f'style="color:#ff6b9d;font-weight:600;">{text}</a>')


def faq_section_en(pairs: list) -> str:
    boxes = []
    styles = [("#2d2d3a", "#f9a8d4"), ("#252532", "#c084fc")]
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
        'max-width:800px;"><h3 style="color:#f9a8d4;margin-top:0;">📚 References</h3>'
        f'<ul style="color:#94a3b8;padding-left:20px;line-height:1.8;">{lis}</ul></div>'
    )


FAQ = [
    ("Arbutin or vitamin C — which is better?",
     "They work through <strong style=\"color:#f9a8d4\">different pathways</strong>, so they pair "
     "well. Arbutin inhibits tyrosinase (the enzyme that makes melanin), while vitamin C adds "
     "antioxidant brightening. If you pick one, arbutin is usually the <strong style=\"color:"
     "#c084fc\">gentler starting point</strong>."),
    ("Is arbutin safe during pregnancy?",
     "Arbutin is considered a relatively mild brightener, but <strong style=\"color:#c084fc\">not "
     "every ingredient suits every person</strong> — check with your OB-GYN or dermatologist "
     "before using it while pregnant or nursing."),
    ("How long until I see results?",
     "Pigment fades slowly. Expect <strong style=\"color:#c084fc\">4–8 weeks of consistent use</"
     "strong> before tone and spots visibly shift — and none of it holds without daily "
     "<strong style=\"color:#f9a8d4\">SPF</strong>, since UV re-triggers melanin."),
    ("How is it different from hydroquinone?",
     "Hydroquinone is stronger but carries irritation and depigmentation risks, so it's largely "
     "a <strong style=\"color:#c084fc\">prescription-tier</strong> ingredient. Arbutin is its "
     "gentler, over-the-counter alternative."),
]
SOURCES = [
    "(American Academy of Dermatology) Hyperpigmentation and skin-brightening guidance",
    "(U.S. FDA) Cosmetic ingredient safety and OTC skin-lightening information",
    "(Cleveland Clinic) Melasma and dark-spot general information",
]

ARTICLE = f"""
{P}If dark spots, melasma, or uneven tone are on your mind, you've probably seen
<strong>arbutin</strong> on a K-beauty label. It's marketed as a "gentle brightener" — a milder
alternative to hydroquinone. This guide breaks down how arbutin actually fades pigment, how it
compares to hydroquinone and vitamin C, and how to use it — <strong>evidence first</strong>.</p>

{H2}What Arbutin Is — and Why It Brightens</h2>
{P}When skin meets UV or irritation, it produces <strong>melanin</strong> to protect itself. Too
much melanin becomes dark spots, melasma, and uneven tone. Arbutin works by <strong>inhibiting
tyrosinase</strong>, the key enzyme in melanin production — so less new pigment forms. It's a
plant-derived derivative of hydroquinone that's far gentler. The key mindset: arbutin is less
about <em>erasing</em> existing spots and more about <em>slowing new ones</em>.</p>

{H2}Arbutin vs. Hydroquinone vs. Vitamin C</h2>
{P}Brighteners differ in strength, safety, and role.</p>
{UL}
{LI}<strong>Hydroquinone</strong> — the strongest, but irritation/depigmentation risks make it
largely a <em>prescription</em> ingredient.</li>
{LI}<strong>Arbutin</strong> — a <em>gentler derivative</em> of hydroquinone; low irritation, good
for daily brightening care.</li>
{LI}<strong>Vitamin C</strong> — antioxidant + brightening; a <em>different pathway</em>, so it
pairs with arbutin (watch for oxidation/irritation).</li>
</ul>
<table style="max-width:800px;width:100%;margin:20px auto;border-collapse:collapse;color:#cbd5e1;">
<tr style="background:#2d2d3a;color:#fff;"><th style="padding:10px;">Ingredient</th><th style="padding:10px;">Strength</th><th style="padding:10px;">Irritation</th><th style="padding:10px;">Best for</th></tr>
<tr><td style="padding:10px;">Hydroquinone</td><td style="padding:10px;">High</td><td style="padding:10px;">High (Rx)</td><td style="padding:10px;">Doctor-supervised</td></tr>
<tr><td style="padding:10px;">Arbutin</td><td style="padding:10px;">Medium</td><td style="padding:10px;">Low</td><td style="padding:10px;">Daily / beginners</td></tr>
<tr><td style="padding:10px;">Vitamin C</td><td style="padding:10px;">Medium</td><td style="padding:10px;">Medium</td><td style="padding:10px;">Antioxidant pairing</td></tr>
</table>

{H2}Alpha vs. Beta Arbutin</h2>
{P}You'll see both on ingredient lists — knowing the difference makes shopping easier.</p>
{UL}
{LI}<strong>Alpha (α) arbutin</strong> — more <em>stable and efficient</em>, generally preferred
for brightening. Usually pricier.</li>
{LI}<strong>Beta (β) arbutin</strong> — cheaper, but less stable and efficient than alpha.</li>
</ul>
{P}Don't shop on price alone — check for a stated <strong>alpha arbutin</strong> content.</p>

{H2}Who Should Try Arbutin</h2>
{UL}
{LI}Anyone bothered by <strong>dark spots, melasma, or uneven tone</strong></li>
{LI}People who find hydroquinone too harsh and want a <strong>gentle brightener</strong></li>
{LI}<strong>Sensitive skin</strong> that reacts to stronger actives</li>
{LI}Those managing <strong>post-inflammatory hyperpigmentation (PIH)</strong> from acne</li>
</ul>

{H2}How to Use It</h2>
{P}Simple routine: ① cleanse → toner → <strong>arbutin cream/serum</strong> → moisturizer,
② morning and night, ③ <strong>daytime SPF is non-negotiable</strong>, ④ give it at least 4–8
weeks. Half of any brightening routine is <strong>sun protection</strong> — arbutin without
sunscreen is pouring water into a leaky bucket.</p>

{H2}How to Choose — Compare on Olive Young</h2>
{P}Keep it simple: ① a stated <strong>alpha arbutin</strong> content, ② minimal fragrance/alcohol
irritants, ③ a texture and price you'll use daily. Korean brands offer well-formulated arbutin
creams, serums, and ampoules — compare them on {olive_link("Olive Young Global")} (ships
internationally), or browse alpha arbutin creams and serums on {amazon_link("Amazon")}.</p>

{H2}Cautions — SPF Is Half the Job</h2>
{P}Three things. First, <strong>without sunscreen the effect cancels out</strong> — UV just makes
new pigment. Second, don't <strong>stack strong acids or retinol</strong> with it at once;
alternate. Third, if 2–3 months bring <strong>no change or darker patches</strong>, see a
dermatologist — some melasma needs professional treatment.</p>

{H2}Bottom Line</h2>
{P}In short: ① arbutin is a gentle brightener that <em>slows</em> new pigment, ② look for alpha
arbutin and start low, ③ stay consistent for 4–8 weeks with daily SPF. No cream simply "erases"
spots — but arbutin is a <strong>dependable pillar of steady tone care</strong>.</p>

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
            params={"query": "skincare cream face brightening", "per_page": 1,
                    "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {key}"}, timeout=20,
        )
        r.raise_for_status()
        photo = r.json()["results"][0]
        alt = photo.get("alt_description") or "skincare brightening cream"
        credit = photo["user"]["name"]
        img = requests.get(photo["urls"]["regular"], timeout=30)
        img.raise_for_status()
        up = requests.post(
            f"{api}/media", auth=auth,
            headers={"Content-Disposition": 'attachment; filename="arbutin-hero.jpg"',
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
        f'<div class="post-content category-k-beauty" data-category="K-Beauty">\n'
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
