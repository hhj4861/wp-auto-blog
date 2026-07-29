#!/usr/bin/env python3
"""Psyllium husk in Korean gut-health / diet culture (bytepulse.io, English, K-Food).

블로그용 검색량 상위 '차전자피'의 영문판 — **'한국 장건강/다이어트 트렌드' 각도로 재구성**해
K-Food 정체성 정합. bytepulse K-Food 카테고리(172). 포맷: post-content category-k-food·히어로·
FTC·오렌지 그라디언트 H2·인라인 제휴(Amazon tag + Olive Young Global)·FAQ·References. 가짜 저자박스 제외.
정직성: 근거·주의(물·약물간섭) 중심, 조작 없음. 로컬 발행. 멱등.
"""

import os
import sys
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.monetization import check_quality  # noqa: E402

SLUG = "korean-psyllium-husk-fiber-2026"
TITLE = "Psyllium Husk: The Fiber Behind Korea's Gut-Health & Diet Craze (2026)"
META_DESC = (
    "Psyllium husk (차전자피) is a staple of Korea's gut-health and diet culture. Here's how this "
    "soluble fiber works for regularity, cholesterol and fullness — plus how to take it safely."
)
FOCUS_KW = "psyllium husk"
CAT_ID = 172  # K-Food
AMAZON = "https://www.amazon.com/s?k=" + quote("psyllium husk") + "&tag=bytepulse08-20"
OLIVE = ("https://global.oliveyoung.com/display/search?query="
         + quote("fiber") + "&rwardCode=HHJZ4861&utm_source=influencers")

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
    ("What exactly is psyllium husk (차전자피)?",
     "It's the <strong style=\"color:#fdba74\">husk of plantago (psyllium) seeds</strong> — a "
     "soluble fiber that swells into a gel when it meets water. In Korea it's a go-to for "
     "regularity, fullness, and cholesterol support."),
    ("How does it help with constipation?",
     "It absorbs water to <strong style=\"color:#fdba74\">bulk up and soften stool</strong>, easing "
     "passage. The catch: you <strong style=\"color:#fb923c\">must drink enough water</strong> — "
     "too little and it can do the opposite."),
    ("Does it help with dieting or cholesterol?",
     "The gel creates <strong style=\"color:#fdba74\">fullness</strong> that helps portion control, "
     "and soluble fiber is linked to better <strong style=\"color:#fb923c\">cholesterol and blood-"
     "sugar</strong> response. It's a diet aid, not a weight-loss drug."),
    ("Any precautions?",
     "① Always take with <strong style=\"color:#fb923c\">plenty of water</strong> (never dry — it "
     "can swell and choke), ② space it <strong style=\"color:#fb923c\">1–2 hours from medications</"
     "strong> (fiber can blunt absorption), ③ start small to adjust to gas/bloating."),
]
SOURCES = [
    "(U.S. FDA) Psyllium and soluble-fiber health-claim information",
    "(Mayo Clinic) Psyllium (fiber supplement) usage and precautions",
    "(Harvard T.H. Chan School of Public Health) Dietary fiber general guidance",
]

ARTICLE = f"""
{P}In Korea's wellness and diet scene, one humble ingredient keeps showing up for gut health and
weight management: <strong>psyllium husk</strong>, known locally as <strong>차전자피</strong>.
It's the soluble fiber people stir into water for regularity, fullness, and cholesterol support.
This guide explains how it actually works and — importantly — how to take it safely.</p>

{H2}What Psyllium Husk Is (and Why Korea Loves It)</h2>
{P}Psyllium husk is the <strong>outer coating of plantago seeds</strong>. On contact with water it
swells into a gel many times its size — a <strong>soluble fiber</strong>. In Korean gut-health and
diet routines it's valued because that gel ① bulks and softens stool for <strong>regularity</
strong>, ② creates <strong>fullness</strong>, and ③ supports <strong>cholesterol and blood-sugar</
strong> management. The theme: it's the fiber that <em>holds water</em>.</p>

{H2}What It Helps With</h2>
{UL}
{LI}<strong>Constipation</strong> — softens and bulks stool to ease passage (with enough water)</li>
{LI}<strong>Dieting</strong> — gel-driven fullness aids portion control (a diet aid, not a drug)</li>
{LI}<strong>Cholesterol / blood sugar</strong> — soluble fiber slows absorption</li>
{LI}<strong>Gut health</strong> — supports regular, comfortable digestion</li>
</ul>

{H2}How to Take It</h2>
{P}Order and dose matter: ① stir <strong>1–2 teaspoons</strong> into a <strong>full glass of
water</strong> and drink promptly, ② once or twice daily, ③ start with a <strong>small dose</
strong> to adjust, ④ increase your overall <strong>water intake</strong>. Too little water and it
can back up instead of helping. Prefer capsules or a specific powder? Compare
{amazon_link("psyllium husk powder and capsules")} on Amazon, or browse fiber inner-beauty options
on {olive_link("Olive Young Global")}.</p>

{H2}⚠️ Cautions — Water and Medication Timing</h2>
{P}Three non-negotiables. First, <strong>never take it dry</strong> — it can swell in the throat/
esophagus and choke. Second, <strong>separate it 1–2 hours from medications</strong> (fiber can
reduce drug absorption). Third, if you have <strong>swallowing issues or bowel obstruction risk</
strong>, talk to a doctor first.</p>

{H2}Bottom Line</h2>
{P}In short: psyllium husk (차전자피) is a <strong>water-loving soluble fiber</strong> behind much
of Korea's gut-health and diet routine — useful for regularity, fullness, and cholesterol. Take it
with <strong>plenty of water, spaced from meds</strong>, and treat it as a companion to good food
and hydration, not a magic fix.</p>

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
            params={"query": "fiber supplement seeds wellness", "per_page": 1,
                    "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {key}"}, timeout=20,
        )
        r.raise_for_status()
        photo = r.json()["results"][0]
        alt = photo.get("alt_description") or "fiber supplement"
        credit = photo["user"]["name"]
        img = requests.get(photo["urls"]["regular"], timeout=30)
        img.raise_for_status()
        up = requests.post(
            f"{api}/media", auth=auth,
            headers={"Content-Disposition": 'attachment; filename="psyllium-hero.jpg"',
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
