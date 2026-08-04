#!/usr/bin/env python3
"""BTS Grammy boycott news (bytepulse.io, English, K-Pop, cat 195).

출처 기반 뉴스 해설 — 조선일보(2026-08-03) + CNN·The Guardian 논평 인용. 1차 테스트/조작 없음,
가사 verbatim 인용 금지(가사는 일반 묘사로만). 캐논 포맷(post-content·히어로·K-Pop 그라디언트 H2·
FAQ·Sources) + 인-아티클 애드센스(영문 'Ad') + 라이트 Amazon CTA(FTC 고지). 로컬 발행, 멱등.
"""

import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.monetization import check_quality, insert_monetization  # noqa: E402

SLUG = "bts-grammy-boycott-army-aliens-2026"
TITLE = "BTS's Grammy Boycott, Explained: How ARMY Sent 'Aliens' to No. 1 in 78 Countries (2026)"
META_DESC = (
    "BTS won't submit their album 'Arirang' to the 2027 Grammys — and fans answered by pushing "
    "'Aliens' to No. 1 in 78 countries. Here's what happened and why it matters."
)
FOCUS_KW = "BTS Grammy boycott"
CAT_ID = 195  # K-Pop

# 스트리밍/앨범 라이트 CTA (env AFFILIATE_AMAZON 설정 시 태그 부착, 없으면 무해한 검색링크)
AMAZON_ALBUM = "https://www.amazon.com/s?k=BTS+Arirang+album"

# K-Pop 핑크-퍼플 그라디언트 H2 (캐논 룩, bytepulse 정체성 내 K-Pop 톤)
H2 = ('<h2 style="font-size:1.5em;margin:40px auto 20px auto;max-width:800px;'
      'background:linear-gradient(135deg,#f472b6,#a78bfa);-webkit-background-clip:text;'
      '-webkit-text-fill-color:transparent;background-clip:text;">')
P = '<p style="max-width:800px;margin:20px auto;text-align:left;line-height:1.8;color:#cbd5e1;">'
UL = '<ul style="max-width:800px;margin:20px auto;line-height:1.8;color:#cbd5e1;padding-left:24px;">'
LI = '<li style="margin-bottom:8px;">'


def cta(url: str, label: str, primary: bool = True) -> str:
    bg = "#db2777" if primary else "#2d2d3a"
    color = "#fff" if primary else "#f9a8d4"
    border = "" if primary else "border:1px solid #db2777;"
    return (
        f'<p style="max-width:800px;margin:16px auto;"><a href="{url}" target="_blank" '
        f'rel="nofollow sponsored noopener" style="display:inline-block;background:{bg};color:{color};{border}'
        f'padding:14px 28px;border-radius:10px;text-decoration:none;font-weight:bold;'
        f'font-size:1.02em;">{label}</a></p>'
    )


def faq_section_en(pairs: list) -> str:
    boxes = []
    styles = [("#2d2d3a", "#f9a8d4"), ("#252532", "#c4b5fd")]
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
        f'<li><span style="color:#94a3b8;font-size:0.9em;">{it}</span></li>' for it in items)
    return (
        '<div style="margin:30px auto;padding:20px;background:#2d2d3a;border-radius:8px;'
        'max-width:800px;">'
        '<h3 style="color:#f9a8d4;margin-top:0;">📚 Sources</h3>'
        f'<ul style="color:#94a3b8;padding-left:20px;line-height:1.8;">{lis}</ul></div>'
    )


FAQ = [
    ("Why is BTS boycotting the Grammys?",
     "BTS said they will not submit their latest album <strong>Arirang</strong> or its tracks to "
     "the 2027 Grammy Awards. The trigger was the Recording Academy's new "
     "<strong>Best Asian Pop Music Performance</strong> category, which groups K-pop and other "
     "Asian music together by region and language. In a July 29 statement, BTS said they hope music "
     "can be <em>heard and loved as music itself</em>, rather than divided by region or language."),
    ("What is the song 'Aliens' and why did it chart again?",
     "'Aliens' is a track from <strong>Arirang</strong> widely read as an indirect critique of how "
     "Western society treats Asians as outsiders. After the boycott news, fans streamed it en masse "
     "and it hit <strong>No. 1 on iTunes Top Songs in 78 countries</strong> for four days through "
     "Aug 1, 2026. Older tracks 'Come Over' (No. 47) and 2017's 'MIC Drop' (No. 25) re-entered too."),
    ("What is the #ArtHasNoAliens movement?",
     "It's a fan-led hashtag campaign. ARMY pair the phrase <strong>#ArtHasNoAliens</strong> with "
     "posts criticizing the Grammys, and some fans are unsubscribing from the Grammys' social "
     "accounts. Others plan to collectively stream BTS's Gwanghwamun Square Netflix concert during "
     "the next Grammy ceremony (Feb 7, 2027) to outdraw the broadcast."),
    ("How did Western media react?",
     "Coverage was broad. <strong>CNN</strong> framed it as BTS advocating for other K-pop artists "
     "who want an equal playing field. <strong>The Guardian</strong> called it a euphemistic but "
     "pointed critique and revisited how Asian musicians have been sidelined at the Grammys. "
     "Billboard, the AP, and Pitchfork noted earlier friction from stars like Drake and The Weeknd."),
]

ARTICLE = f"""
{P}BTS just did something almost no act at their level does: they said <strong>no</strong> to the
Grammys. The group announced they will not submit their latest album <strong>Arirang</strong> — or
any of its songs — to the 2027 Grammy Awards. Within days, their fandom answered in the loudest way
it knows how, and a four-year-old song and a brand-new one both stormed back up the global charts.</p>

{H2}What BTS actually said</h2>
{P}On July 29, BTS explained the decision in a short social-media statement: they want music to be
<em>heard and loved as music itself</em>, rather than sorted by region or language. The context is
a rule change. In June, the Recording Academy announced a new
<strong>Best Asian Pop Music Performance</strong> category that gathers K-pop and other Asian music
into a single, language-and-region-based bracket starting with the next ceremony. BTS's statement
reads as a direct pushback: a dedicated "Asian" box, they suggest, separates rather than celebrates.</p>

{H2}The chart reversal: 'Aliens' hits No. 1 in 78 countries</h2>
{P}Fans didn't just post about it — they streamed. The <strong>Arirang</strong> track
<strong>"Aliens"</strong> shot to <strong>No. 1 on the iTunes Top Songs chart in 78 countries</strong>,
holding the top spot for four days through Aug 1, 2026. The song is widely read as an indirect
commentary on how Western society casts Asians as outsiders, which made it an on-the-nose anthem for
the moment. It wasn't alone: another Arirang cut, <strong>"Come Over,"</strong> climbed to No. 47,
and BTS's 2017 single <strong>"MIC Drop"</strong> jumped back to No. 25 — both re-entering the chart
after the boycott declaration.</p>

{H2}ARMY's playbook: #ArtHasNoAliens</h2>
{P}The fan response has been organized and pointed. Supporters are attaching the hashtag
<strong>#ArtHasNoAliens</strong> to posts criticizing the Grammys, and some are unsubscribing from
the awards' social accounts outright. The most creative move is still ahead: fans are planning to
collectively stream BTS's Gwanghwamun Square concert film on Netflix during the next Grammy ceremony
on <strong>Feb 7, 2027</strong>, hoping to out-draw the telecast and underline the group's point.</p>
{P}The timing lands in the middle of a busy touring run — BTS played MetLife Stadium in New Jersey on
Aug 1 as part of the Arirang tour, keeping the story in front of a stadium-sized audience.</p>

{H2}Why the industry is paying attention</h2>
{P}What started as one group's submission decision has widened into a debate about the Grammys
themselves. <strong>CNN</strong> noted that nothing in the rules forces BTS into the Asian-pop
category, framing their stance as advocacy for other K-pop artists who want to compete on the same
starting line. <strong>The Guardian</strong> described the message as euphemistic but unmistakably
sharp, and revisited how Asian musicians have long been sidelined at the ceremony. Billboard, the
Associated Press, and Pitchfork all connected the moment to earlier friction, recalling how stars
like <strong>Drake</strong> and <strong>The Weeknd</strong> pushed back on the Grammys' opaque and
uneven judging.</p>

{H2}What happens next</h2>
{P}For now, BTS's album stays out of the 2027 race, the fan campaigns keep building, and the
Recording Academy faces uncomfortable questions about a category meant to spotlight Asian music that
some of its biggest names would rather skip. Whether the Academy adjusts the rule — or the standoff
hardens into the Feb 7 counter-programming — is the thread to watch.</p>
{P}Curious what all the streaming is about? You can hear <strong>Arirang</strong> and "Aliens" on the
major music services.</p>
{cta(AMAZON_ALBUM, "🎧 Find BTS 'Arirang' on Amazon Music →")}
<p style="max-width:800px;margin:8px auto;text-align:left;color:#94a3b8;font-size:0.85em;">
<em>Affiliate disclosure: some links may earn a small commission at no extra cost to you.</em></p>

{faq_section_en(FAQ)}

{sources_section_en([
    "(Chosun Ilbo, English edition — Aug 2026) Reporting on BTS declining to submit 'Arirang' to the 2027 Grammys and the fan 'Grammy boycott.'",
    "(CNN) Coverage framing BTS's stance as advocacy for a fair, equal field for K-pop artists.",
    "(The Guardian) Analysis of the statement and the marginalization of Asian musicians at the Grammys.",
    "(Apple / iTunes Top Songs chart) Source for the 'Aliens' No. 1 in 78 countries and re-entry positions.",
])}
"""


def fetch_hero(api: str, auth: tuple) -> tuple:
    key = os.environ.get("UNSPLASH_ACCESS_KEY", "").strip()
    if not key:
        print("UNSPLASH key absent — skipping hero")
        return None, ""
    try:
        r = requests.get(
            "https://api.unsplash.com/search/photos",
            params={"query": "concert stage lights crowd stadium", "per_page": 1,
                    "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {key}"}, timeout=20,
        )
        r.raise_for_status()
        photo = r.json()["results"][0]
        alt = photo.get("alt_description") or "concert stage"
        credit = photo["user"]["name"]
        img = requests.get(photo["urls"]["regular"], timeout=30)
        img.raise_for_status()
        up = requests.post(
            f"{api}/media", auth=auth,
            headers={"Content-Disposition": 'attachment; filename="bts-grammy-hero.jpg"',
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
            f'margin-top:10px;">Photo by {credit} · Illustrative image, not the event described</figcaption></figure>\n'
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

    # 인-아티클 애드센스(영문 'Ad') — 캐논 H2 앵커 기준 배치
    article = insert_monetization(
        ARTICLE.strip(), official_link="", related_posts=None,
        ad_label="Ad", related_heading="📌 Related Posts",
    )

    media_id, hero = fetch_hero(api, auth)
    body_html = (
        f'<div class="post-content category-k-pop" data-category="K-Pop">\n'
        f'{hero}{article}\n</div>'
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
