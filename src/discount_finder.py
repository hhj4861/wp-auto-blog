"""Discount Finder module for K-Culture products.

Finds discount information and deals for K-Beauty, K-Food, K-Fashion products.
Sources:
- Olive Young Global API (real-time prices) - K-Beauty
- Amazon (K-Food, ramen, snacks, etc.)
- General discount tips by category
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from typing import Optional
import requests
from bs4 import BeautifulSoup
from loguru import logger


@dataclass
class DiscountInfo:
    """Discount information for a product.

    Attributes:
        original_price: Original/normal price in USD
        sale_price: Current sale price in USD
        discount_percent: Discount percentage (e.g., 54.0 for 54% off)
        has_coupon: Whether additional coupons are available
        has_gift: Whether free gifts are included
        source: Where this deal is from
        deal_url: URL to the deal
        tips: List of discount tips
    """

    original_price: Optional[float] = None
    sale_price: Optional[float] = None
    discount_percent: Optional[float] = None
    has_coupon: bool = False
    has_gift: bool = False
    source: str = ""
    deal_url: str = ""
    tips: list[str] = None

    def __post_init__(self):
        if self.tips is None:
            self.tips = []

    @property
    def savings(self) -> Optional[float]:
        """Calculate savings amount."""
        if self.original_price and self.sale_price:
            return self.original_price - self.sale_price
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "original_price": self.original_price,
            "sale_price": self.sale_price,
            "discount_percent": self.discount_percent,
            "savings": self.savings,
            "has_coupon": self.has_coupon,
            "has_gift": self.has_gift,
            "source": self.source,
            "deal_url": self.deal_url,
            "tips": self.tips,
        }


class DiscountFinder:
    """Finds discount information for K-Culture products.

    Example:
        >>> finder = DiscountFinder()
        >>> discount = finder.find_discount("COSRX Snail Mucin", category="K-Beauty")
        >>> if discount:
        ...     print(f"Save {discount.discount_percent}%!")
    """

    # Category-specific discount tips
    DISCOUNT_TIPS = {
        "K-Beauty": [
            "🛒 **Amazon Subscribe & Save**: Get 5-15% off with recurring delivery",
            "🎁 **Olive Young Global**: Free shipping over $60, frequent flash sales",
            "💰 **YesStyle**: Use code 'YESSTYLE' for 10% off first order",
            "📦 **iHerb**: K-Beauty section often has 20-30% off sales",
            "🔔 **Price Alert**: Set up CamelCamelCamel alerts for Amazon price drops",
            "🎯 **Bundle Deals**: Buy sets instead of singles for better value",
        ],
        "K-Food": [
            "🛒 **Amazon Subscribe & Save**: 5-15% off pantry staples",
            "🏪 **H Mart/Asian Grocery**: Often cheaper than online for fresh items",
            "📦 **Costco/Sam's Club**: Bulk K-Food items at wholesale prices",
            "🎯 **Weee! App**: Asian grocery delivery with frequent promotions",
            "💰 **Amazon Fresh**: Check for Korean food section deals",
        ],
        "K-Fashion": [
            "💰 **YesStyle**: Seasonal sales up to 70% off",
            "🎁 **Olive Young Global**: K-Fashion accessories section",
            "📦 **W Concept**: Premium Korean fashion with sales events",
            "🔔 **Sign up for newsletters**: Get exclusive discount codes",
            "🎯 **End of season sales**: Best time to buy Korean fashion",
        ],
        "K-Pop": [
            "💿 **Official Fan Clubs**: Member-only discounts on merchandise",
            "🛒 **Weverse Shop**: Official merch with global shipping",
            "📦 **Ktown4u/Kpoptown**: Bulk order discounts for albums",
            "🎯 **Pre-order**: Often includes exclusive photocards/benefits",
            "💰 **Group Orders**: Join group orders on Twitter/Reddit for shared shipping",
        ],
    }

    def __init__(self):
        """Initialize DiscountFinder."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        })
        self._oliveyoung_cache = None

    def _fetch_oliveyoung_bestsellers(self) -> list[dict]:
        """Fetch and cache Olive Young bestsellers."""
        if self._oliveyoung_cache is not None:
            return self._oliveyoung_cache

        try:
            url = "https://global.oliveyoung.com/display/product/best-seller/order-best"
            params = {"curLangCode": "en", "pageIdx": 1, "pageSize": 100}
            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            self._oliveyoung_cache = resp.json()
            return self._oliveyoung_cache
        except Exception as e:
            logger.error(f"Failed to fetch Olive Young data: {e}")
            return []

    def find_oliveyoung_deal(self, query: str) -> Optional[DiscountInfo]:
        """Find discount info from Olive Young Global.

        Args:
            query: Product name or search query

        Returns:
            DiscountInfo if found, None otherwise
        """
        products = self._fetch_oliveyoung_bestsellers()
        if not products:
            return None

        query_lower = query.lower()
        query_words = [w for w in query_lower.split() if len(w) >= 3]

        best_match = None
        best_score = 0

        for product in products:
            product_name = product.get("prdtName", "")
            brand_name = product.get("brandName", "")
            combined = f"{product_name} {brand_name}".lower()

            score = sum(1 for word in query_words if word in combined)

            if score > best_score:
                best_score = score
                best_match = product

        if not best_match or best_score < 1:
            return None

        # Extract discount info
        original_price = best_match.get("nrmlAmt")
        sale_price = best_match.get("saleAmt")
        discount_rate = best_match.get("eventSlprcDscntRt")
        has_coupon = best_match.get("cpnYn", "N") == "Y"
        has_gift = best_match.get("giftYn", "N") == "Y"

        # Build deal URL
        product_no = best_match.get("prdtNo", "")
        deal_url = f"https://global.oliveyoung.com/product/detail?prdtNo={product_no}" if product_no else ""

        # Parse prices
        try:
            original_price = float(original_price) if original_price else None
            sale_price = float(sale_price) if sale_price else None
            discount_rate = float(discount_rate) if discount_rate else None
        except (ValueError, TypeError):
            pass

        tips = []
        if has_gift:
            tips.append("🎁 **Free Gift**: This product includes a free gift!")
        if has_coupon:
            tips.append("🎟️ **Coupon Available**: Additional coupon discount available!")
        if discount_rate and discount_rate >= 30:
            tips.append(f"🔥 **Hot Deal**: {discount_rate:.0f}% off - grab it before it's gone!")

        return DiscountInfo(
            original_price=original_price,
            sale_price=sale_price,
            discount_percent=discount_rate,
            has_coupon=has_coupon,
            has_gift=has_gift,
            source="Olive Young Global",
            deal_url=deal_url,
            tips=tips,
        )

    def get_category_tips(self, category: str) -> list[str]:
        """Get discount tips for a category.

        Args:
            category: K-Culture category

        Returns:
            List of discount tip strings
        """
        return self.DISCOUNT_TIPS.get(category, self.DISCOUNT_TIPS.get("K-Beauty", []))

    def find_amazon_kfood_deal(self, query: str) -> Optional[DiscountInfo]:
        """Generate Amazon K-Food deal link.

        Instead of scraping prices (which is unreliable due to geo-location),
        we generate a search URL with relevant K-Food keywords.

        Args:
            query: Product name or search query (e.g., "buldak ramen")

        Returns:
            DiscountInfo with Amazon search URL and tips
        """
        # Extract K-Food related keywords from query
        kfood_keywords = {
            "buldak": "samyang buldak ramen",
            "ramen": "korean ramen noodles",
            "ramyeon": "korean ramyeon instant",
            "kimchi": "korean kimchi",
            "gochujang": "korean gochujang paste",
            "tteokbokki": "korean tteokbokki rice cake",
            "samyang": "samyang korean noodles",
            "nongshim": "nongshim korean ramen",
            "snack": "korean snacks",
            "soju": "korean soju",
        }

        query_lower = query.lower()

        # Find the best matching K-Food keyword
        search_query = query
        for keyword, amazon_query in kfood_keywords.items():
            if keyword in query_lower:
                search_query = amazon_query
                break

        # If no specific match, add "korean" prefix
        if search_query == query and "korean" not in query_lower:
            search_query = f"korean {query}"

        # Generate Amazon search URL
        encoded_query = urllib.parse.quote(search_query)
        deal_url = f"https://www.amazon.com/s?k={encoded_query}&i=grocery"

        tips = [
            "🛒 **Amazon Subscribe & Save**: Get 5-15% off with recurring delivery",
            "📦 **Prime Members**: Free fast shipping on eligible items",
            "🔔 **Price Alerts**: Use CamelCamelCamel to track price drops",
        ]

        logger.info(f"Generated Amazon K-Food link: {search_query}")

        return DiscountInfo(
            original_price=None,
            sale_price=None,
            discount_percent=None,
            has_coupon=False,
            has_gift=False,
            source="Amazon",
            deal_url=deal_url,
            tips=tips,
        )

    def find_discount(
        self,
        query: str,
        category: str = "K-Beauty",
        brand: str = "",
    ) -> DiscountInfo:
        """Find comprehensive discount information.

        Uses appropriate source based on category:
        - K-Beauty: Olive Young Global
        - K-Food: Amazon (ramen, snacks, etc.)
        - Others: General tips

        Args:
            query: Product name
            category: K-Culture category
            brand: Brand name (optional)

        Returns:
            DiscountInfo with all available discount data
        """
        # Start with category tips
        tips = self.get_category_tips(category)[:4]  # Top 4 tips

        search_query = f"{brand} {query}".strip() if brand else query
        deal = None

        # Use appropriate source based on category
        if category == "K-Food":
            # Amazon for K-Food (ramen, snacks, Korean food)
            deal = self.find_amazon_kfood_deal(search_query)
            if deal:
                logger.info(f"Found Amazon K-Food deal for: {search_query[:40]}")
        elif category == "K-Beauty":
            # Olive Young for K-Beauty
            deal = self.find_oliveyoung_deal(search_query)
            if deal:
                logger.info(f"Found Olive Young deal for: {search_query[:40]}")

        if deal:
            # Merge deal with category tips
            combined_tips = deal.tips + tips
            return DiscountInfo(
                original_price=deal.original_price,
                sale_price=deal.sale_price,
                discount_percent=deal.discount_percent,
                has_coupon=deal.has_coupon,
                has_gift=deal.has_gift,
                source=deal.source,
                deal_url=deal.deal_url,
                tips=combined_tips[:6],  # Limit to 6 tips
            )

        # Return generic discount info with category tips
        return DiscountInfo(
            source="General",
            tips=tips,
        )


def generate_discount_html(discount: DiscountInfo, product_name: str = "") -> str:
    """Generate HTML for discount section in blog post.

    Args:
        discount: DiscountInfo object
        product_name: Product name for display

    Returns:
        HTML string for discount section
    """
    html_parts = []

    # Deal box with price info
    if discount.sale_price and discount.original_price:
        savings = discount.savings or 0
        deal_link = f'<a href="{discount.deal_url}" target="_blank" rel="nofollow sponsored" style="display: inline-block !important; background: #ffffff !important; color: #667eea !important; padding: 12px 30px !important; border-radius: 25px !important; text-decoration: none !important; font-weight: bold !important; margin-top: 15px !important;">Get This Deal →</a>' if discount.deal_url else ''
        html_parts.append(f'<div class="deal-box" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important; color: #ffffff !important; padding: 25px !important; border-radius: 12px !important; margin: 25px 0 !important; text-align: center !important;">'
            f'<div style="font-size: 14px !important; color: rgba(255,255,255,0.9) !important; text-decoration: line-through !important;">Regular Price: ${discount.original_price:.2f}</div>'
            f'<div style="font-size: 36px !important; font-weight: bold !important; margin: 10px 0 !important; color: #ffffff !important;">${discount.sale_price:.2f}</div>'
            f'<div style="margin: 10px 0 !important;"><span style="display: inline-block !important; font-size: 16px !important; background: #ff6b6b !important; color: #ffffff !important; padding: 6px 16px !important; border-radius: 20px !important; font-weight: bold !important;">{discount.discount_percent:.0f}% OFF</span></div>'
            f'<div style="font-size: 16px !important; color: rgba(255,255,255,0.9) !important; margin-top: 5px !important;">You Save: ${savings:.2f}</div>'
            f'{deal_link}</div>')

    # Deal box without price info (just link)
    elif discount.deal_url:
        source_name = discount.source or "Shop"
        html_parts.append(f'<div class="deal-box" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important; color: #ffffff !important; padding: 25px !important; border-radius: 12px !important; margin: 25px 0 !important; text-align: center !important;">'
            f'<div style="font-size: 20px !important; font-weight: bold !important; margin-bottom: 15px !important; color: #ffffff !important;">🛒 Shop on {source_name}</div>'
            f'<div style="font-size: 14px !important; color: rgba(255,255,255,0.9) !important; margin-bottom: 15px !important;">Compare prices and find the best deals</div>'
            f'<a href="{discount.deal_url}" target="_blank" rel="nofollow sponsored" style="display: inline-block !important; background: #ffffff !important; color: #667eea !important; padding: 12px 30px !important; border-radius: 25px !important; text-decoration: none !important; font-weight: bold !important;">Browse Products →</a></div>')

    # Tips section
    if discount.tips:
        tips_html = "".join(f'<li style="color: #212529 !important;">{tip}</li>' for tip in discount.tips)
        html_parts.append(f'<div class="discount-tips" style="background-color: #f8f9fa !important; padding: 20px !important; border-radius: 8px !important; margin: 20px 0 !important;">'
            f'<h4 style="margin-top: 0 !important; color: #495057 !important;">💡 How to Get the Best Price</h4>'
            f'<ul style="margin-bottom: 0 !important; line-height: 1.8 !important; color: #212529 !important;">{tips_html}</ul></div>')

    return "\n".join(html_parts)
