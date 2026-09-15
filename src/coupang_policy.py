"""Coupang links require an explicit editorial product-promotion designation.

Missing/unknown intent is informational. Category names, mentions of products,
health foods and recommendation keywords never implicitly enable promotion.
"""
from html import unescape
import re
import unicodedata
from urllib.parse import unquote, urlsplit
from bs4 import BeautifulSoup


def is_product_promotion(brief):
    return isinstance(brief, dict) and brief.get('article_type') == 'product_promotion'


def no_coupang_content(html):
    """Reject residual links/placeholders; do not silently erase unknown markup."""
    from src.monetization import COUPANG_DISCLOSURE

    if not isinstance(html, str) or not html.strip():
        return False
    value = html
    # Inspect encoded attributes and JSON-LD URLs too, not just visible anchors.
    for _ in range(3):
        value = unquote(unescape(value))
    # Browsers normalize full-width host characters and remove URL tabs/newlines.
    value = re.sub(r'[\x00-\x20\x7f]', '', unicodedata.normalize('NFKC', value).casefold())
    value = value.replace('\\/', '/')
    # This mode promises no Coupang links, including ordinary commerce links;
    # a plain brand mention in an informational article is not a product link.
    for raw_url in re.findall(r'(?:https?:)?//[^<>"\']+', value):
        try:
            host = (urlsplit(raw_url).hostname or '').rstrip('.')
        except ValueError:
            return False
        if host == 'coupang.com' or host.endswith('.coupang.com') or host == 'coupa.ng':
            return False
    visible = BeautifulSoup(html, 'html.parser').get_text(' ', strip=True)
    return (not re.search(r'coupang[-_](?:products[-_]block|prep[-_]box|disclosure)', value)
            and not re.search(r'쿠팡\s*(?:파트너스\s*)?링크.{0,30}(?:입력|삽입|여기에|대기)', visible)
            and COUPANG_DISCLOSURE not in visible)

