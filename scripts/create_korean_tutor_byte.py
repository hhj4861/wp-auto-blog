#!/usr/bin/env python3
"""Korean tutoring promo (bytepulse.io, English, K-Culture) — 사용자 본인 Preply 튜터 홍보.

hanmadi 앱(무료 5분 레슨·개인 노트·레벨테스트·학습팩) 기능 기반. 1인칭 정직 홍보(본인 서비스,
조작 아님). 제휴 아님 → 올리브영/Amazon 없음. CTA: hanmadi 무료레슨 + Preply 프로필 + 30% 추천.
포맷: bytepulse 캐논(post-content·히어로·보라 그라디언트 H2·FAQ). 가짜 저자박스 제외. 로컬 발행. 멱등.
결제·예약은 Preply 안에서만 유도(외부 결제 금지).
"""

import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.monetization import check_quality  # noqa: E402

SLUG = "learn-korean-free-5-minute-lesson-2026"
TITLE = "Learn Korean, One Phrase at a Time — Try a Free 5-Minute Lesson (2026)"
META_DESC = (
    "Learning Korean feels huge, but it doesn't have to. Try a free 5-minute interactive "
    "lesson (no sign-up), then book 1:1 lessons that end with your own personal notes page."
)
FOCUS_KW = "learn Korean"
CAT_ID = 207  # K-Culture

TRIAL_URL = "https://hanmadi-lake.vercel.app/trial"
MEET_URL = "https://hanmadi-lake.vercel.app/meet"
PREPLY_URL = "https://preply.com/en/tutor/8265428"
REFERRAL_URL = "https://preply.com/ko/?pref=MzEzMDEzOTU=&id=1785312403.457966&ep=w1"

# K-Culture(언어/문화) 보라-인디고 그라디언트
H2 = ('<h2 style="font-size:1.5em;margin:40px auto 20px auto;max-width:800px;'
      'background:linear-gradient(135deg,#a78bfa,#818cf8);-webkit-background-clip:text;'
      '-webkit-text-fill-color:transparent;background-clip:text;">')
P = '<p style="max-width:800px;margin:20px auto;text-align:left;line-height:1.8;color:#cbd5e1;">'
UL = '<ul style="max-width:800px;margin:20px auto;line-height:1.8;color:#cbd5e1;padding-left:24px;">'
LI = '<li style="margin-bottom:8px;">'


def cta(url: str, label: str, primary: bool = False) -> str:
    bg = "#8b5cf6" if primary else "#2d2d3a"
    color = "#fff" if primary else "#c4b5fd"
    border = "" if primary else "border:1px solid #6d5bd0;"
    return (
        f'<p style="max-width:800px;margin:16px auto;"><a href="{url}" target="_blank" '
        f'rel="noopener" style="display:inline-block;background:{bg};color:{color};{border}'
        f'padding:14px 28px;border-radius:10px;text-decoration:none;font-weight:bold;'
        f'font-size:1.02em;">{label}</a></p>'
    )


def faq_section_en(pairs: list) -> str:
    boxes = []
    styles = [("#2d2d3a", "#c4b5fd"), ("#252532", "#93c5fd")]
    for i, (q, a) in enumerate(pairs):
        bg, qc = styles[i % 2]
        boxes.append(
            f'<div style="background:{bg};padding:20px;border-radius:10px;margin-bottom:15px;">'
            f'<p style="color:{qc};font-weight:bold;margin:0 0 10px 0;">{q}</p>'
            f'<p style="color:#cbd5e1;margin:0;line-height:1.8;">{a}</p></div>'
        )
    return (f"{H2}Frequently Asked Questions</h2>\n"
            f'<div style="max-width:800px;margin:20px auto;">\n' + "\n".join(boxes) + "\n</div>")


FAQ = [
    ("Do I need to know Hangul (the Korean alphabet) first?",
     "Not at all. If you're starting from zero, we begin with Hangul — and the free lesson "
     "literally has you <strong style=\"color:#c4b5fd\">build your first Korean letter</strong> "
     "by picking a consonant and a vowel and hearing the sound."),
    ("Is the free 5-minute lesson really free?",
     "Yes — <strong style=\"color:#c4b5fd\">no sign-up, no card, just tap</strong>. It's a real "
     "taste of how lessons feel: you read a phrase, say it out loud, and build a sentence. If it "
     "clicks, you can book a full lesson."),
    ("How do the paid lessons work?",
     "They're <strong style=\"color:#93c5fd\">1:1 video lessons on Preply</strong>. The part "
     "students love: I type everything in real time, so every lesson ends with your own "
     "<strong style=\"color:#c4b5fd\">personal notes page</strong> — corrections and new phrases "
     "you can review anytime (a few minutes a day is perfect)."),
    ("I'm a total beginner and pretty busy — is that okay?",
     "That's exactly who this is for. The whole idea is <em>one phrase at a time</em> — even "
     "5 focused minutes a day adds up. We find your level first, then build from there."),
]

ARTICLE = f"""
{P}Learning Korean can feel enormous — a new alphabet, unfamiliar grammar, and that nagging
"am I even saying this right?" I teach Korean <strong>1:1 on Preply</strong>, and I built a small
free tool so you can <em>feel</em> what a lesson is like before spending anything. The idea is
simple: <strong>Korean, one phrase at a time (한마디씩)</strong>.</p>

{cta(TRIAL_URL, "▶ Try a free 5-minute Korean lesson (no sign-up)", primary=True)}

{H2}Try a real 5-minute lesson right now</h2>
{P}No account, no card — just tap. In about five minutes you'll:</p>
{UL}
{LI}Tap a word and realize you just <strong>read your first Korean</strong> (만나서 반가워요 —
"nice to meet you")</li>
{LI}Pick <strong>how you feel</strong> and say it out loud</li>
{LI}Build a <strong>Hangul letter</strong> yourself — choose a consonant, then a vowel, and hear
the sound appear</li>
{LI}<strong>Assemble a sentence</strong> by tapping the pieces in order</li>
</ul>
{P}Everything you make is collected at the end so you can tap any phrase to hear it again. It's the
gentlest possible on-ramp — reading Korean in five minutes, out loud.</p>

{H2}Every lesson ends with your own notes page</h2>
{P}Here's what makes the 1:1 lessons different: <strong>I type everything you say in real time</
strong> — what you said, the corrected version, and every new phrase — into a personal page that's
yours to keep. No frantic note-taking mid-conversation; you just <em>talk</em>, and afterward you
have a clean review page. Come back to it a few minutes a day and the phrases stick.</p>

{H2}A clear path from zero to conversation</h2>
{P}You won't wander. We start with a quick <strong>level check</strong> that places you honestly —
absolute beginner (start with Hangul), building everyday phrases and basic grammar, or ready to
grow into real conversations. From there we work through focused <strong>learning packs</strong>
(Hangul basics, essential phrases, and more), each built around speaking, not memorizing tables.</p>

{H2}Who this is for</h2>
{UL}
{LI}<strong>K-pop / K-drama fans</strong> who want to understand without subtitles</li>
{LI}<strong>Travelers</strong> heading to Korea who want to actually be understood</li>
{LI}<strong>Absolute beginners</strong> intimidated by thick textbooks</li>
{LI}Anyone who learns better by <strong>speaking out loud</strong> than by cramming grammar</li>
</ul>

{H2}How to start</h2>
{P}Three easy steps — start wherever you like:</p>
{cta(TRIAL_URL, "1 · Try the free 5-minute lesson", primary=True)}
{cta(PREPLY_URL, "2 · Book a trial lesson with me on Preply →")}
{cta(REFERRAL_URL, "3 · New to Preply? Get 30% off your first lesson")}
<p style="max-width:800px;margin:10px auto;text-align:left;line-height:1.8;color:#94a3b8;font-size:0.9em;">
Booking, messaging, and payment all happen safely inside Preply — you're never asked to pay
anywhere else.</p>

{H2}The bottom line</h2>
{P}You don't need to master grammar tables before you can speak Korean. Start with a single phrase,
said out loud, today. Try the <strong>free 5-minute lesson</strong> — and if it clicks, book a
trial, where every lesson leaves you with notes you'll actually keep.</p>
<p style="max-width:800px;margin:20px auto;text-align:left;line-height:1.8;color:#94a3b8;font-size:0.9em;">
<em>About: I'm a Korean tutor on Preply, and <a href="{MEET_URL}" target="_blank" rel="noopener"
style="color:#a78bfa;">Hanmadi</a> is the free companion app I built for my students.</em></p>

{faq_section_en(FAQ)}
"""


def fetch_hero(api: str, auth: tuple) -> tuple:
    key = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
    if not key:
        print("UNSPLASH key absent — skipping hero")
        return None, ""
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": "learning language study korean notebook", "per_page": 1,
                    "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {key}"}, timeout=20,
        )
        r.raise_for_status()
        photo = r.json()["results"][0]
        alt = photo.get("alt_description") or "learning Korean"
        credit = photo["user"]["name"]
        img = requests.get(photo["urls"]["regular"], timeout=30)
        img.raise_for_status()
        up = requests.post(
            f"{api}/media", auth=auth,
            headers={"Content-Disposition": 'attachment; filename="learn-korean-hero.jpg"',
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
        f'<div class="post-content category-k-culture" data-category="K-Culture">\n'
        f'{hero}{ARTICLE.strip()}\n</div>'
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
