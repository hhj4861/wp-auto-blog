"""Provider-independent TrendPulse formatting for generated and reviewed posts."""
import re

from bs4 import BeautifulSoup

from .editorial import reader_layout
from .post_format import to_canon_headings
from .monetization import (
    add_coupang_disclosure, add_policy_disclaimers, insert_faq_schema,
    insert_monetization, strip_placeholders,
)


def normalize_article_styles(html: str) -> str:
    """Supply the canonical dark-theme styles when the writer omitted them."""
    soup = BeautifulSoup(html, "html.parser")
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
    return insert_faq_schema(html)
