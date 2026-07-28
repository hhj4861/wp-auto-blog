#!/usr/bin/env python3
"""Bakuchiol serum review (bytepulse.io, English, K-Beauty).

'바쿠치올 세럼' 검색 1위 대응 영문판. bytepulse K-Beauty 실측 포맷 일치:
post-content category-k-beauty 래퍼·Unsplash 히어로·FTC 고지 박스·핑크 그라디언트 H2·
인라인 제휴 링크(Amazon tag / Olive Young Global rwardCode)·FAQ·참고자료.
**조작 저자박스(K-Pulse Beauty Team 등)는 의도적으로 제외** (AdSense E-E-A-T 위반 회피).
정직성: 성분·근거·주의 중심, 가격·후기 조작 없음. 로컬 실행(WP_URL=bytepulse). 멱등.
"""

import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.monetization import check_quality  # noqa: E402

SLUG = "bakuchiol-serum-retinol-alternative-2026"
TITLE = "Bakuchiol Serum: The Gentle Retinol Alternative Everyone's Searching (2026)"
META_DESC = (
    "Bakuchiol is trending as a natural retinol alternative. Here's the evidence, "
    "how it compares to retinol, who it's for, and how to use it — 2026 guide."
)
FOCUS_KW = "bakuchiol serum"
CAT_ID = 213  # K-Beauty

AMAZON = "https://amzn.to/4fZzSCs"  # SiteStripe 검색링크(bakuchiol serum), tag=bytepulse08-20
OLIVE = (
    "https://global.oliveyoung.com/display/search?query="
    + quote("bakuchiol") + "&rwardCode=HHJZ4861&utm_source=influencers"
)

# --- bytepulse K-Beauty 캐논 상수 (실측: post 2730) ---
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


def amazon_link(text: str) -> str:
    return (f'<a href="{AMAZON}" target="_blank" rel="nofollow sponsored" '
            f'style="color:#ff6b9d;font-weight:600;">{text}</a>')


def olive_link(text: str) -> str:
    return (f'<a href="{OLIVE}" target="_blank" rel="nofollow sponsored" '
            f'style="color:#9b59b6;font-weight:600;">{text}</a>')


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
    ("How is bakuchiol different from retinol?",
     "Retinol has the deepest clinical track record but often causes irritation, redness, "
     "and flaking. Bakuchiol is a plant-derived compound that, in a 2019 study, showed "
     "<strong style=\"color:#f9a8d4\">comparable improvement in wrinkles and pigmentation</strong> "
     "with less irritation. Think of it as a gentler retinol alternative."),
    ("Is bakuchiol safe during pregnancy?",
     "Retinoids are generally avoided in pregnancy, which is why bakuchiol is often suggested "
     "as an alternative. Still, <strong style=\"color:#c084fc\">not every ingredient is right for "
     "every person</strong> — always check with your OB-GYN or dermatologist before using it while "
     "pregnant or nursing."),
    ("When and how do I apply it?",
     "Cleanse → toner → <strong style=\"color:#f9a8d4\">bakuchiol serum</strong> → moisturizer, "
     "morning and night. Unlike retinol it's less prone to light degradation, but always finish "
     "your daytime routine with <strong style=\"color:#c084fc\">SPF</strong>."),
    ("How long until I see results?",
     "Because skin turns over on a multi-week cycle, expect <strong style=\"color:#c084fc\">4–8 "
     "weeks of consistent use</strong> before texture and tone shift. Start low and build up as "
     "your skin adapts."),
]
SOURCES = [
    "(American Academy of Dermatology) Anti-aging skincare ingredient guidance",
    "(British Journal of Dermatology, 2019) Bakuchiol vs. retinol for photoaging — comparison study",
    "(U.S. FDA) Cosmetics labeling and safety information",
]

ARTICLE = f"""
{P}If you've been curious about <strong>retinol</strong> but scared off by the peeling and
redness, you've probably run into its trendy cousin: <strong>bakuchiol serum</strong>. It's one
of the fastest-rising searches in skincare right now. This guide breaks down what bakuchiol
actually is, how it compares to retinol, who should use it, and how to pick one —
<strong>evidence first, hype second</strong>.</p>

{H2}What Is Bakuchiol — and Why the Sudden Hype?</h2>
{P}Bakuchiol is a plant-derived compound (from the babchi seed) marketed as a
"natural retinol alternative." Its chemistry is different from retinol, but it appears to trigger
<strong>similar skin signals</strong> — supporting collagen and cell turnover. The appeal is
simple: <em>retinol-like goals, with far less irritation</em>.</p>

{H2}Retinol vs. Bakuchiol — The Evidence</h2>
{P}Both target signs of aging, but they behave differently.</p>
{UL}
{LI}<strong>Retinol</strong> — the deepest clinical evidence for wrinkles and pigmentation, but
frequent early <em>irritation</em> (redness, flaking, dryness) means a break-in period.</li>
{LI}<strong>Bakuchiol</strong> — a 2019 comparison study reported <em>similar wrinkle and
pigmentation improvement</em> to retinol with less stinging and redness. The evidence base is
thinner than retinol's, but <em>gentleness</em> is its edge.</li>
</ul>
<table style="max-width:800px;width:100%;margin:20px auto;border-collapse:collapse;color:#cbd5e1;">
<tr style="background:#2d2d3a;color:#fff;"><th style="padding:10px;">&nbsp;</th><th style="padding:10px;">Retinol</th><th style="padding:10px;">Bakuchiol</th></tr>
<tr><td style="padding:10px;">Evidence depth</td><td style="padding:10px;">Very strong</td><td style="padding:10px;">Growing</td></tr>
<tr><td style="padding:10px;">Irritation</td><td style="padding:10px;">Common</td><td style="padding:10px;">Low</td></tr>
<tr><td style="padding:10px;">Time of use</td><td style="padding:10px;">Mostly PM</td><td style="padding:10px;">AM &amp; PM</td></tr>
<tr><td style="padding:10px;">Best for</td><td style="padding:10px;">Tolerant skin</td><td style="padding:10px;">Sensitive / beginners</td></tr>
</table>

{H2}Who Should Reach for Bakuchiol</h2>
{UL}
{LI}<strong>Sensitive skin</strong> that stings or flakes on retinol</li>
{LI}<strong>Beginners</strong> easing into anti-aging care without the harsh adjustment</li>
{LI}Anyone wanting an active they can use in the <strong>morning</strong> too</li>
{LI}Those avoiding retinoids in <strong>pregnancy</strong> — but only after talking to a doctor</li>
</ul>

{H2}How to Choose One — Where to Buy</h2>
{P}Keep it simple: ① look for a stated <strong>bakuchiol concentration</strong>, ② fewer
unnecessary fragrance/dye irritants, and ③ a size and price you'll actually use daily. Korean
beauty brands have some of the best-formulated options — you can compare bakuchiol serums on
{olive_link("Olive Young Global")} (ships internationally), or browse a wider range on
{amazon_link("Amazon")}.</p>

{H2}A Few Cautions — Gentle Still Means "Patch Test"</h2>
{P}Three things. First, "gentle" varies by person, so <strong>patch test</strong> on your inner
arm before your face. Second, don't <strong>overload it alongside retinol or strong acids</strong>
(AHA/BHA) at once — alternate instead. Third, <strong>daytime SPF is non-negotiable</strong>; half
of anti-aging is sun protection.</p>

{H2}Bottom Line</h2>
{P}In short: ① if retinol was too harsh, bakuchiol is a gentler on-ramp; ② check the concentration
and start low; ③ stay consistent for 4–8 weeks and always wear SPF. A serum isn't magic — it's
<strong>one pillar of a consistent routine</strong>, and that's where results actually come from.</p>

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
            params={"query": "skincare serum dropper bottle", "per_page": 1,
                    "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {key}"}, timeout=20,
        )
        r.raise_for_status()
        photo = r.json()["results"][0]
        alt = photo.get("alt_description") or "skincare serum dropper bottle"
        credit = photo["user"]["name"]
        img = requests.get(photo["urls"]["regular"], timeout=30)
        img.raise_for_status()
        up = requests.post(
            f"{api}/media", auth=auth,
            headers={"Content-Disposition": 'attachment; filename="bakuchiol-hero.jpg"',
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
