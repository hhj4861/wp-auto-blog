"""Provider-independent TrendPulse formatting for generated and reviewed posts."""
import re

from bs4 import BeautifulSoup

from .editorial import reader_layout
from .post_format import to_canon_headings
from .monetization import (
    add_coupang_disclosure, add_policy_disclaimers, insert_faq_schema,
    insert_monetization, strip_placeholders,
)

READING_CSS = """
.wpab-article{max-width:800px;margin:auto;font-size:17px;line-height:1.8;word-break:keep-all;overflow-wrap:break-word}
.single-post .entry .wpab-article{max-width:800px!important;width:100%}
.single-post:has(.wpab-article) .entry{max-width:800px;margin:auto}
.wpab-article p,.wpab-article li,.wpab-article td{font-weight:400}
.wpab-article #quick-answer{padding:8px 20px;border-left:3px solid #2dd4bf;background:#292f33}
.wpab-article #article-toc summary{cursor:pointer;color:#e2e8f0;font-weight:600}
.wpab-article [data-visual]>li::marker{content:""}
.wpab-article [data-visual="steps"]>li{display:grid;grid-template-columns:32px 1fr;gap:14px;padding:14px 0;margin:0;border-bottom:1px solid #4b5563}
.wpab-article [data-step-number]{display:flex;align-items:center;justify-content:center;width:30px;height:30px;border-radius:50%;background:#204744;color:#b5f5e8;font-size:15px;font-weight:600}
.wpab-article [data-visual-copy] strong{display:block;color:#f8fafc;font-weight:600;margin-bottom:3px}
.wpab-article [data-visual-copy]{min-width:0;color:#cbd5e1}
.wpab-article [data-visual="checklist"]>li{display:block;padding:12px 0;margin:0;border-bottom:1px solid #4b5563}
.wpab-article [data-visual="checklist"] [data-visual-copy]{display:grid;grid-template-columns:90px 1fr;gap:12px}
.single-post:has(.wpab-article) .blog-card-single-head .blog-card-right:has(>.blog-card-right-inner[style*="url('')"]):not(:has(ins,iframe)){height:80px;min-height:0}
.single-post:has(.wpab-article) .blog-card-single-head:has(.blog-card-right-inner[style*="url('')"]):not(:has(ins,iframe)){height:auto;min-height:0}
.single-post:has(.wpab-article) .blog-card-single-head:has(.blog-card-right-inner[style*="url('')"]):not(:has(ins,iframe)) .blog-card-inner{height:auto;min-height:0}
.single-post:has(.wpab-article) .blog-card-single-head:has(.blog-card-right-inner[style*="url('')"]):not(:has(ins,iframe)) .blog-card-right{width:100%;float:none}
.single-post:has(.wpab-article) .blog-card-single-head:has(.blog-card-right-inner[style*="url('')"]):not(:has(ins,iframe)) .blog-card-bottom{width:100%;float:none}
.single-post:has(.wpab-article) .entry-header{max-width:800px;margin:0 auto 24px}
.single-post:has(.wpab-article) .entry-header h1{font-size:clamp(24px,3vw,38px);line-height:1.4;word-break:keep-all}
@media(max-width:600px){
.wpab-article{font-size:16px;line-height:1.75}
.wpab-article p,.wpab-article li{font-size:16px!important}
.wpab-article #quick-answer{padding:4px 14px}
.wpab-article [data-visual="steps"]>li{gap:10px;padding:12px 0}
.single-post:has(.wpab-article) .blog-card-single-head .blog-card-right:has(>.blog-card-right-inner[style*="url('')"]):not(:has(ins,iframe)){height:68px;min-height:0}
}
"""


def finish_reading_layout(html: str) -> str:
    """Keep answers before navigation and scope theme repairs to these articles."""
    soup = BeautifulSoup(html, "html.parser")
    toc = soup.select_one('#article-toc')
    if toc:
        toc.name = 'details'
        label = toc.find('p', recursive=False)
        if label:
            label.name = 'summary'
            label.string = '목차 · 필요한 내용 바로 찾기'
    notice, sources = soup.select_one('#policy-notice'), soup.select_one('#verified-sources')
    if notice and sources:
        sources.insert_before(notice.extract())
    return '<style id="wpab-reading-styles">' + READING_CSS + '</style><div class="wpab-article">' + str(soup) + '</div>'


def normalize_article_styles(html: str) -> str:
    """Supply the canonical dark-theme styles when the writer omitted them."""
    soup = BeautifulSoup(html, "html.parser")
    # Explicit semantic lists: readable without images, JS, or horizontal scrolling.
    for visual in soup.select('ol[data-visual="steps"], ul[data-visual="checklist"]'):
        items = visual.find_all("li", recursive=False)
        if not 2 <= len(items) <= 6:
            continue
        visual["style"] = "max-width:800px;margin:24px auto;padding:0;list-style:none;"
        for index, item in enumerate(items, 1):
            item["style"] = "list-style:none;min-width:0;"
            if not item.select_one('[data-visual-copy]'):
                copy = soup.new_tag("div", attrs={"data-visual-copy": "1"})
                for child in list(item.contents):
                    copy.append(child.extract())
                item.append(copy)
            if visual.name == "ol" and not item.select_one('[data-step-number]'):
                badge = soup.new_tag("span", attrs={"data-step-number": "1", "aria-hidden": "true"})
                badge.string = str(index)
                item.insert(0, badge)
    defaults = {
        "p": "max-width:800px;margin:20px auto;text-align:left;line-height:1.8;color:#cbd5e1;",
        "ul": "max-width:800px;margin:20px auto;padding-left:24px;line-height:1.8;color:#cbd5e1;",
        "ol": "max-width:800px;margin:20px auto;padding-left:24px;line-height:1.8;color:#cbd5e1;",
        "li": "margin-bottom:8px;",
        "table": "width:100%;border-collapse:collapse;background:#252532;color:#e0e0e0;",
        "th": "padding:12px;border:1px solid #64748b;text-align:left;background:#2d2d3a;color:#ffffff;",
        "td": "padding:12px;border:1px solid #64748b;text-align:left;",
    }
    for tag, style in defaults.items():
        for element in soup.find_all(tag):
            if not element.get("style"):
                # Respect explicitly styled callouts, whose background may be light.
                if tag in {"p", "ul", "ol"} and element.find_parent(style=True):
                    continue
                element["style"] = style
    for heading in soup.find_all("h2"):
        if not re.search(r"FAQ|자주\s*묻는|자주하는\s*질문", heading.get_text(), re.I):
            continue
        index = 0
        for node in list(heading.find_next_siblings()):
            if node.name == "h2":
                break
            if node.name != "h3":
                continue
            answer = node.find_next_sibling()
            if not answer or answer.name != "p":
                continue
            card = soup.new_tag("div", attrs={"data-faq-card": "1"})
            bg, accent = (("#2d2d3a", "#a78bfa"), ("#252532", "#60a5fa"))[index % 2]
            card["style"] = f"max-width:800px;margin:0 auto 15px;background:{bg};padding:20px;border-radius:10px;"
            node.insert_before(card)
            node["style"] = f"color:{accent};font-weight:bold;font-size:1em;margin:0 0 10px;"
            card.append(node.extract())
            answer["style"] = "color:#cbd5e1;margin:0;line-height:1.8;"
            card.append(answer.extract())
            index += 1
    return str(soup)


def format_general_article(html: str, *, sources=None, category="", topic="",
                           official_link="", related_posts=None) -> str:
    """Format unrendered content once, before publishing, regardless of LLM."""
    html = normalize_article_styles(strip_placeholders(html))
    html = reader_layout(to_canon_headings(html), sources or [])
    html = add_coupang_disclosure(html)
    html = add_policy_disclaimers(html, category=category, topic=topic)
    html = insert_monetization(html, official_link=official_link, related_posts=related_posts)
    return finish_reading_layout(insert_faq_schema(html))
