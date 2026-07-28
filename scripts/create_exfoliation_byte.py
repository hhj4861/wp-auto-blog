#!/usr/bin/env python3
"""Exfoliation / Korean peeling guide (bytepulse.io, English, K-Beauty).

검색모듈 1위 키워드 '각질 필링'(opp 73) 영문판. bytepulse K-Beauty 실측 포맷 일치:
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

SLUG = "korean-exfoliation-peeling-guide-2026"
TITLE = "Korean Exfoliation Guide: Peeling Gels, AHA, BHA & PHA Explained (2026)"
META_DESC = (
    "Confused by peeling gels, AHA, BHA and PHA? Here's what each does, which suits your "
    "skin, how often to exfoliate, and the mistakes to avoid — 2026 K-beauty guide."
)
FOCUS_KW = "korean exfoliation"
CAT_ID = 213  # K-Beauty
OLIVE = ("https://global.oliveyoung.com/display/search?query="
         + quote("peeling gel") + "&rwardCode=HHJZ4861&utm_source=influencers")
AMAZON = "https://amzn.to/4fy1vBm"  # SiteStripe 검색링크(korean peeling gel), tag=bytepulse08-20

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
    ("How often should I exfoliate?",
     "For most people, <strong style=\"color:#f9a8d4\">1–2 times a week</strong> is the sweet "
     "spot. Daily exfoliation breaks down your skin barrier and causes redness, stinging, and "
     "dryness. If skin feels tight or thin, cut back."),
    ("Physical scrub or chemical acids — which is better?",
     "Neither wins outright. Scrubs work instantly but risk <strong style=\"color:#c084fc\">"
     "micro-tears</strong>; AHA/BHA/PHA acids are more even and gentle. Sensitive skin should "
     "start with a low-strength <strong style=\"color:#f9a8d4\">PHA</strong>."),
    ("What do I apply after exfoliating?",
     "Freshly exfoliated skin loses water fast, so follow with <strong style=\"color:#f9a8d4\">"
     "hydration (hyaluronic acid, panthenol)</strong>, and always use <strong style=\"color:"
     "#c084fc\">SPF</strong> by day — exfoliated skin is more sun-sensitive."),
    ("Can I use it with retinol?",
     "Not both at full strength at once. <strong style=\"color:#c084fc\">Alternate nights</strong> "
     "or start one at a low concentration. If you sting or keep flaking, reduce frequency first."),
]
SOURCES = [
    "(American Academy of Dermatology) Exfoliation and skin-barrier guidance",
    "(U.S. FDA) AHA/BHA cosmetic ingredient and sun-sensitivity information",
    "(Cleveland Clinic) Skin exfoliation general information",
]

ARTICLE = f"""
{P}Smooth, glowy skin usually starts with <strong>exfoliation</strong> — but overdo it and it
backfires. Between scrubs, peeling gels, and acids (AHA, BHA, PHA), it's hard to know what to
pick. This K-beauty guide breaks down how each method works, which suits your skin, and how to
exfoliate without wrecking your barrier — <strong>evidence first</strong>.</p>

{H2}What Exfoliation Actually Does</h2>
{P}Your skin renews on roughly a <strong>28-day turnover cycle</strong> — old dead cells shed as
new ones surface. Age, dryness, and UV slow that cycle, letting <em>dead skin</em> pile up into
dullness, rough texture, and clogged pores. Exfoliation clears that buildup to improve
<strong>absorption, tone, and texture</strong>. The key isn't "remove more" — it's <em>the right
amount</em>.</p>

{H2}Physical vs. Chemical — The Difference</h2>
{P}Two broad families, different personalities.</p>
{UL}
{LI}<strong>Physical</strong> — scrubs, gommage, peeling gels that <em>buff</em> dead skin off.
Instant, but grit and friction can cause <em>micro-tears</em>, so pressure control matters.</li>
{LI}<strong>Chemical</strong> — acids that <em>dissolve</em> the bonds holding dead cells, so they
shed evenly and more gently: <strong>AHA</strong> (surface/dry), <strong>BHA</strong>
(pores/oily), <strong>PHA</strong> (low-irritation/sensitive).</li>
</ul>
<table style="max-width:800px;width:100%;margin:20px auto;border-collapse:collapse;color:#cbd5e1;">
<tr style="background:#2d2d3a;color:#fff;"><th style="padding:10px;">Ingredient</th><th style="padding:10px;">Targets</th><th style="padding:10px;">Notes</th><th style="padding:10px;">Best for</th></tr>
<tr><td style="padding:10px;">AHA (glycolic, lactic)</td><td style="padding:10px;">Surface, tone</td><td style="padding:10px;">Water-soluble</td><td style="padding:10px;">Dry, dull</td></tr>
<tr><td style="padding:10px;">BHA (salicylic)</td><td style="padding:10px;">Pore oil</td><td style="padding:10px;">Oil-soluble</td><td style="padding:10px;">Oily, breakouts</td></tr>
<tr><td style="padding:10px;">PHA (gluconolactone)</td><td style="padding:10px;">Surface</td><td style="padding:10px;">Larger molecule, gentle</td><td style="padding:10px;">Sensitive, beginners</td></tr>
</table>

{H2}Which One Fits Your Skin</h2>
{UL}
{LI}<strong>Dry / dull</strong> → AHA or a gentle peeling gel (tone &amp; texture)</li>
{LI}<strong>Oily / clogged pores / blackheads</strong> → BHA (salicylic) toner or pads</li>
{LI}<strong>Sensitive / beginner</strong> → start with <strong>PHA</strong>, skip harsh scrubs</li>
{LI}<strong>Combination</strong> → BHA on the T-zone, AHA/PHA on cheeks</li>
</ul>

{H2}How to Use It — and How Often</h2>
{P}Simple routine: ① <strong>1–2× per week</strong>, at night after cleansing ② apply the
exfoliant (follow its timing) ③ <strong>moisturize</strong> well ④ <strong>SPF</strong> by day,
always. Start at <em>once a week, low strength</em> and build up as skin adapts. More often does
NOT mean smoother — <strong>overdoing it breaks the barrier.</strong></p>

{H2}How to Choose — Compare on Olive Young</h2>
{P}Keep it simple: ① an acid/format that matches your skin type (AHA/BHA/PHA), ② minimal
fragrance/alcohol irritants, ③ a size and price for <em>1–2× weekly</em> use. Korean brands offer
some of the best-formulated peeling gels, acid toners, and pads — compare them on
{olive_link("Olive Young Global")} (ships internationally), or browse a wider selection of
peeling gels and AHA/BHA toners on {amazon_link("Amazon")}.</p>

{H2}Cautions — Over-Exfoliating Is the Real Risk</h2>
{P}Three rules. First, <strong>never exfoliate daily</strong> — stinging or redness means you've
already gone too far. Second, don't <strong>stack retinol and strong acids</strong> at once;
alternate. Third, exfoliation and <strong>SPF are a set</strong> — freshly exfoliated skin is far
more sensitive to sun and irritation.</p>

{H2}Bottom Line</h2>
{P}In short: ① match the method to your skin (sensitive? start with PHA), ② begin 1–2× weekly at
low strength, ③ always follow with moisture and daytime SPF. Exfoliation isn't about scrubbing
harder — it's about <strong>restoring your skin's rhythm</strong>, and that's where the glow
comes from.</p>

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
            params={"query": "skincare exfoliation face routine", "per_page": 1,
                    "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {key}"}, timeout=20,
        )
        r.raise_for_status()
        photo = r.json()["results"][0]
        alt = photo.get("alt_description") or "skincare exfoliation routine"
        credit = photo["user"]["name"]
        img = requests.get(photo["urls"]["regular"], timeout=30)
        img.raise_for_status()
        up = requests.post(
            f"{api}/media", auth=auth,
            headers={"Content-Disposition": 'attachment; filename="exfoliation-hero.jpg"',
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
