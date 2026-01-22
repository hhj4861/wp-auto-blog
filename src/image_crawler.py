"""Image Crawler module for K-Culture product images.

Crawls product images from Korean e-commerce sites:
- Olive Young Global (K-Beauty, K-Food) - Uses official API
- Daiso Korea (K-Beauty, lifestyle)
- Musinsa (K-Fashion)

For K-Pop content, use youtube_fetcher.py instead (copyright safety).

NOTE: Olive Young Global API is now the primary source for K-Beauty products.
Other sites may have bot detection issues.
"""

from __future__ import annotations

import os
import re
import urllib.parse
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger

# Playwright for JS-rendered pages
try:
    from playwright.sync_api import sync_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Run: pip install playwright && playwright install chromium")


@dataclass
class CrawledImage:
    """Represents a crawled product image.

    Attributes:
        url: Direct URL to the image
        product_name: Product name
        brand: Brand name
        source: Source site (oliveyoung, daiso, musinsa)
        price: Price string (optional)
    """

    url: str
    product_name: str
    brand: str
    source: str
    price: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "url": self.url,
            "product_name": self.product_name,
            "brand": self.brand,
            "source": self.source,
            "price": self.price,
        }


class ImageCrawler:
    """Crawls product images from Korean e-commerce sites.

    Uses Playwright for JavaScript-rendered pages (Olive Young, Musinsa).

    Example:
        >>> crawler = ImageCrawler()
        >>> image = crawler.search_oliveyoung("COSRX Snail Mucin")
        >>> if image:
        ...     print(f"Found: {image.product_name} - {image.url}")
    """

    def __init__(self, use_playwright: bool = True):
        """Initialize crawler.

        Args:
            use_playwright: Whether to use Playwright for JS rendering (default: True)
        """
        self.use_playwright = use_playwright and PLAYWRIGHT_AVAILABLE
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self._browser = None
        self._playwright = None

    def _get_browser(self):
        """Get or create Playwright browser instance."""
        if not PLAYWRIGHT_AVAILABLE:
            return None
        if self._browser is None:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)
        return self._browser

    def _close_browser(self):
        """Close Playwright browser."""
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    def __del__(self):
        """Cleanup on deletion."""
        self._close_browser()

    def _fetch_with_playwright(self, url: str, wait_selector: str = None) -> Optional[str]:
        """Fetch page content using Playwright (for JS-rendered pages).

        Args:
            url: URL to fetch
            wait_selector: CSS selector to wait for before extracting content

        Returns:
            Page HTML content or None on failure
        """
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not available for JS rendering")
            return None

        try:
            browser = self._get_browser()
            page = browser.new_page()
            page.set_extra_http_headers({
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            })

            logger.debug(f"Playwright fetching: {url}")
            page.goto(url, wait_until="networkidle", timeout=30000)

            # Wait for specific selector if provided
            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    logger.debug(f"Wait selector '{wait_selector}' not found, continuing...")

            # Small delay for dynamic content
            page.wait_for_timeout(2000)

            content = page.content()
            page.close()
            return content

        except Exception as e:
            logger.error(f"Playwright fetch failed: {e}")
            return None

    def search_oliveyoung(self, query: str) -> Optional[CrawledImage]:
        """Search for product image on Olive Young Global.

        Uses Olive Young Global API to fetch bestseller products and find matches.

        Args:
            query: Product name or search query (e.g., "COSRX Snail Mucin")

        Returns:
            CrawledImage if found, None otherwise
        """
        # Olive Young Global API endpoint
        api_url = "https://global.oliveyoung.com/display/product/best-seller/order-best"
        params = {
            "curLangCode": "en",
            "pageIdx": 1,
            "pageSize": 100,  # Get more products to search through
        }

        try:
            response = self.session.get(api_url, params=params, timeout=15)
            response.raise_for_status()
            products = response.json()

            if not isinstance(products, list):
                logger.warning("Olive Young API returned unexpected format")
                return None

            # Search for matching product
            query_lower = query.lower()
            query_words = query_lower.split()

            best_match = None
            best_score = 0

            for product in products:
                product_name = product.get("prdtName", "")
                brand_name = product.get("brandName", "")
                combined = f"{product_name} {brand_name}".lower()

                # Calculate match score
                score = 0
                for word in query_words:
                    if len(word) >= 3 and word in combined:
                        score += 1

                if score > best_score:
                    best_score = score
                    best_match = product

            if best_match and best_score >= 1:
                img_path = best_match.get("imagePath", "")
                img_url = f"https://cdn-image.oliveyoung.com/{img_path}" if img_path else ""

                # Format price as USD
                sale_amt = best_match.get("saleAmt")
                if sale_amt:
                    try:
                        price = f"${float(sale_amt):.2f}"
                    except (ValueError, TypeError):
                        price = f"${sale_amt}"
                else:
                    price = None

                logger.info(f"Found Olive Young product: {best_match.get('prdtName', '')[:50]}")
                return CrawledImage(
                    url=img_url,
                    product_name=best_match.get("prdtName", query),
                    brand=best_match.get("brandName", ""),
                    source="oliveyoung_global",
                    price=price,
                )

            logger.warning(f"No matching product found on Olive Young for: {query}")
            return None

        except Exception as e:
            logger.error(f"Failed to fetch from Olive Young API: {e}")

    def search_oliveyoung_multiple(
        self, query: str, max_results: int = 5
    ) -> list[CrawledImage]:
        """Search for multiple product images on Olive Young Global.

        Returns multiple matching products for section images.

        Args:
            query: Product name or search query (e.g., "Vitamin C Serum")
            max_results: Maximum number of results to return

        Returns:
            List of CrawledImage objects
        """
        api_url = "https://global.oliveyoung.com/display/product/best-seller/order-best"
        params = {
            "curLangCode": "en",
            "pageIdx": 1,
            "pageSize": 100,
        }

        try:
            response = self.session.get(api_url, params=params, timeout=15)
            response.raise_for_status()
            products = response.json()

            if not isinstance(products, list):
                return []

            # Search for matching products
            query_lower = query.lower()
            query_words = [w for w in query_lower.split() if len(w) >= 3]

            # Score all products
            scored_products = []
            for product in products:
                product_name = product.get("prdtName", "")
                brand_name = product.get("brandName", "")
                combined = f"{product_name} {brand_name}".lower()

                score = sum(1 for word in query_words if word in combined)
                if score >= 1:
                    scored_products.append((score, product))

            # Sort by score descending
            scored_products.sort(key=lambda x: x[0], reverse=True)

            # Convert to CrawledImage
            results = []
            seen_urls = set()

            for _, product in scored_products[:max_results * 2]:  # Get more to filter duplicates
                img_path = product.get("imagePath", "")
                if not img_path or img_path in seen_urls:
                    continue

                seen_urls.add(img_path)
                img_url = f"https://cdn-image.oliveyoung.com/{img_path}"

                sale_amt = product.get("saleAmt")
                price = None
                if sale_amt:
                    try:
                        price = f"${float(sale_amt):.2f}"
                    except (ValueError, TypeError):
                        price = f"${sale_amt}"

                results.append(CrawledImage(
                    url=img_url,
                    product_name=product.get("prdtName", query),
                    brand=product.get("brandName", ""),
                    source="oliveyoung_global",
                    price=price,
                ))

                if len(results) >= max_results:
                    break

            logger.info(f"Found {len(results)} Olive Young products for: {query}")
            return results

        except Exception as e:
            logger.error(f"Failed to fetch multiple from Olive Young API: {e}")
            return []

    def fetch_oliveyoung_product_detail(
        self, product_no: str, product_name: str = "", brand: str = ""
    ) -> list[CrawledImage]:
        """Fetch all images from Olive Young product detail page.

        Gets multiple product images (main + gallery) from a single product.
        Uses the product detail API for efficient image extraction.

        Args:
            product_no: Product number (prdtNo from API)
            product_name: Product name for image metadata
            brand: Brand name for image metadata

        Returns:
            List of CrawledImage objects with different product images
        """
        if not product_no:
            return []

        # Try product detail API first
        detail_api_url = f"https://global.oliveyoung.com/product/product-detail"
        params = {
            "prdtNo": product_no,
            "curLangCode": "en",
        }

        try:
            response = self.session.get(detail_api_url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                images = []
                seen_urls = set()

                # Extract main image
                main_img = data.get("imagePath", "")
                if main_img and main_img not in seen_urls:
                    seen_urls.add(main_img)
                    images.append(CrawledImage(
                        url=f"https://cdn-image.oliveyoung.com/{main_img}",
                        product_name=product_name or data.get("prdtName", ""),
                        brand=brand or data.get("brandName", ""),
                        source="oliveyoung_global",
                    ))

                # Extract additional images from gallery
                add_images = data.get("addImageList", [])
                for img in add_images:
                    img_path = img.get("imagePath", "") if isinstance(img, dict) else img
                    if img_path and img_path not in seen_urls:
                        seen_urls.add(img_path)
                        images.append(CrawledImage(
                            url=f"https://cdn-image.oliveyoung.com/{img_path}",
                            product_name=product_name or data.get("prdtName", ""),
                            brand=brand or data.get("brandName", ""),
                            source="oliveyoung_global",
                        ))

                # Also check for detail description images
                detail_images = data.get("detailImageList", [])
                for img in detail_images[:3]:  # Limit detail images
                    img_path = img.get("imagePath", "") if isinstance(img, dict) else img
                    if img_path and img_path not in seen_urls:
                        seen_urls.add(img_path)
                        images.append(CrawledImage(
                            url=f"https://cdn-image.oliveyoung.com/{img_path}",
                            product_name=product_name or data.get("prdtName", ""),
                            brand=brand or data.get("brandName", ""),
                            source="oliveyoung_global",
                        ))

                if images:
                    logger.info(f"Found {len(images)} images for product: {product_name[:40]}...")
                    return images

        except Exception as e:
            logger.debug(f"Product detail API failed, trying HTML: {e}")

        # Fallback: Scrape HTML page
        detail_url = f"https://global.oliveyoung.com/product/detail?prdtNo={product_no}"
        try:
            response = self.session.get(detail_url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            images = []
            seen_urls = set()

            # Find product gallery images
            gallery_imgs = soup.select("img.prd-img, .prd-gallery img, .thumb-list img")
            for img_tag in gallery_imgs:
                src = img_tag.get("src") or img_tag.get("data-src") or ""
                if src and "cdn-image.oliveyoung.com" in src and src not in seen_urls:
                    seen_urls.add(src)
                    images.append(CrawledImage(
                        url=src,
                        product_name=product_name,
                        brand=brand,
                        source="oliveyoung_global",
                    ))

            # Find main product image
            main_img = soup.select_one(".prd-main-img img, .product-img img")
            if main_img:
                src = main_img.get("src") or main_img.get("data-src") or ""
                if src and "cdn-image.oliveyoung.com" in src and src not in seen_urls:
                    seen_urls.add(src)
                    images.insert(0, CrawledImage(
                        url=src,
                        product_name=product_name,
                        brand=brand,
                        source="oliveyoung_global",
                    ))

            if images:
                logger.info(f"Found {len(images)} images from HTML for: {product_name[:40]}...")
            return images

        except Exception as e:
            logger.warning(f"Failed to fetch product detail: {e}")
            return []

    def search_oliveyoung_with_detail(
        self, query: str, max_images: int = 5
    ) -> list[CrawledImage]:
        """Search for product and get multiple images from detail page.

        Combines bestseller API search with detail page image extraction
        to get diverse images of the same product.

        Args:
            query: Product name or search query
            max_images: Maximum number of images to return

        Returns:
            List of CrawledImage objects from the matched product
        """
        # First, find matching product from bestseller API
        api_url = "https://global.oliveyoung.com/display/product/best-seller/order-best"
        params = {
            "curLangCode": "en",
            "pageIdx": 1,
            "pageSize": 100,
        }

        try:
            response = self.session.get(api_url, params=params, timeout=15)
            response.raise_for_status()
            products = response.json()

            if not isinstance(products, list):
                return []

            # Find best matching product
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
                logger.warning(f"No matching product for detail images: {query}")
                return []

            # Get product number and fetch detail images
            product_no = best_match.get("prdtNo", "")
            product_name = best_match.get("prdtName", query)
            brand = best_match.get("brandName", "")

            if not product_no:
                # Return just the main image
                img_path = best_match.get("imagePath", "")
                if img_path:
                    return [CrawledImage(
                        url=f"https://cdn-image.oliveyoung.com/{img_path}",
                        product_name=product_name,
                        brand=brand,
                        source="oliveyoung_global",
                    )]
                return []

            # Fetch detail page images
            detail_images = self.fetch_oliveyoung_product_detail(
                product_no, product_name, brand
            )

            if detail_images:
                return detail_images[:max_images]

            # Fallback to main image only
            img_path = best_match.get("imagePath", "")
            if img_path:
                return [CrawledImage(
                    url=f"https://cdn-image.oliveyoung.com/{img_path}",
                    product_name=product_name,
                    brand=brand,
                    source="oliveyoung_global",
                )]

            return []

        except Exception as e:
            logger.error(f"Failed to search with detail: {e}")
            return []

    def search_amazon_kfood(self, query: str) -> Optional[CrawledImage]:
        """Search for K-Food product image on Amazon.

        Args:
            query: Product name or search query (e.g., "Buldak ramen", "Korean snacks")

        Returns:
            CrawledImage if found, None otherwise
        """
        # Enhance query for K-Food
        kfood_keywords = ["korean", "k-food", "samyang", "buldak", "ramyeon", "ramen"]
        query_lower = query.lower()

        # Add "korean" to query if not already food-related
        if not any(kw in query_lower for kw in kfood_keywords):
            query = f"korean {query}"

        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.amazon.com/s?k={encoded_query}&i=grocery"

        try:
            # Use custom headers to avoid bot detection
            amazon_headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Cache-Control": "max-age=0",
                "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"macOS"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            }

            response = requests.get(search_url, headers=amazon_headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Find product cards
            products = soup.select('[data-component-type="s-search-result"]')

            if not products:
                # Try alternative selectors
                products = soup.select('.s-result-item[data-asin]')

            if not products:
                logger.warning(f"No Amazon products found for: {query}")
                return None

            # Get first valid product
            for product in products[:5]:  # Check first 5 products
                # Skip sponsored/ads
                if product.select_one('.s-sponsored-label-info-icon'):
                    continue

                # Extract image
                img_tag = product.select_one('img.s-image')
                if not img_tag:
                    continue

                img_url = img_tag.get('src', '')
                if not img_url or 'placeholder' in img_url.lower():
                    continue

                # Get higher resolution image by modifying URL
                # Amazon uses _AC_UL320_ for thumbnails, replace with larger
                img_url = re.sub(r'_AC_U[LS]\d+_', '_AC_SL1500_', img_url)

                # Extract product name
                name_tag = product.select_one('h2 a span') or product.select_one('.a-text-normal')
                product_name = name_tag.text.strip() if name_tag else query

                # Extract brand
                brand_tag = product.select_one('.a-row.a-size-base a') or product.select_one('[data-cy="brand"]')
                brand = brand_tag.text.strip() if brand_tag else "Amazon"

                # Extract price
                price_tag = product.select_one('.a-price .a-offscreen')
                price = price_tag.text.strip() if price_tag else None

                logger.info(f"Found Amazon K-Food: {product_name[:50]}...")
                return CrawledImage(
                    url=img_url,
                    product_name=product_name,
                    brand=brand,
                    source="amazon",
                    price=price,
                )

            logger.warning(f"No valid Amazon product image for: {query}")
            return None

        except Exception as e:
            logger.error(f"Failed to crawl Amazon: {e}")
            return None

    def search_amazon_kfood_multiple(
        self, query: str, max_results: int = 5
    ) -> list[CrawledImage]:
        """Search for multiple K-Food product images on Amazon.

        Args:
            query: Product name or search query
            max_results: Maximum number of results to return

        Returns:
            List of CrawledImage objects
        """
        # Enhance query for K-Food
        kfood_keywords = ["korean", "k-food", "samyang", "buldak", "ramyeon", "ramen", "kimchi"]
        query_lower = query.lower()

        if not any(kw in query_lower for kw in kfood_keywords):
            query = f"korean {query}"

        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.amazon.com/s?k={encoded_query}&i=grocery"

        try:
            amazon_headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"macOS"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Upgrade-Insecure-Requests": "1",
            }

            response = requests.get(search_url, headers=amazon_headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")
            products = soup.select('[data-component-type="s-search-result"]')

            if not products:
                products = soup.select('.s-result-item[data-asin]')

            results = []
            seen_urls = set()

            for product in products:
                if len(results) >= max_results:
                    break

                # Skip sponsored
                if product.select_one('.s-sponsored-label-info-icon'):
                    continue

                img_tag = product.select_one('img.s-image')
                if not img_tag:
                    continue

                img_url = img_tag.get('src', '')
                if not img_url or 'placeholder' in img_url.lower() or img_url in seen_urls:
                    continue

                # Get higher resolution
                img_url = re.sub(r'_AC_U[LS]\d+_', '_AC_SL1500_', img_url)
                seen_urls.add(img_url)

                name_tag = product.select_one('h2 a span') or product.select_one('.a-text-normal')
                product_name = name_tag.text.strip() if name_tag else query

                brand_tag = product.select_one('.a-row.a-size-base a')
                brand = brand_tag.text.strip() if brand_tag else "Amazon"

                price_tag = product.select_one('.a-price .a-offscreen')
                price = price_tag.text.strip() if price_tag else None

                results.append(CrawledImage(
                    url=img_url,
                    product_name=product_name,
                    brand=brand,
                    source="amazon",
                    price=price,
                ))

            logger.info(f"Found {len(results)} Amazon K-Food products for: {query}")
            return results

        except Exception as e:
            logger.error(f"Failed to fetch multiple from Amazon: {e}")
            return []

    def search_daiso(self, query: str) -> Optional[CrawledImage]:
        """Search for product image on Daiso Korea Mall.

        Args:
            query: Product name or search query

        Returns:
            CrawledImage if found, None otherwise
        """
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.daisomall.co.kr/goods/goods_search.php?keyword={encoded_query}"

        try:
            # Use Playwright for JS rendering
            if self.use_playwright:
                html = self._fetch_with_playwright(search_url, wait_selector=".item_list")
                if not html:
                    # Fallback to requests
                    response = self.session.get(search_url, timeout=15)
                    response.raise_for_status()
                    html = response.text
            else:
                response = self.session.get(search_url, timeout=15)
                response.raise_for_status()
                html = response.text

            soup = BeautifulSoup(html, "html.parser")

            # Find first product
            product = (
                soup.select_one(".item_list li") or
                soup.select_one(".goods_item") or
                soup.select_one(".product-item")
            )
            if not product:
                logger.warning(f"No product found on Daiso for: {query}")
                return None

            # Extract image
            img_tag = product.select_one("img")
            img_url = ""
            if img_tag:
                img_url = img_tag.get("src") or img_tag.get("data-src") or img_tag.get("data-original") or ""
                if img_url and not img_url.startswith("http"):
                    img_url = "https://www.daisomall.co.kr" + img_url

            # Extract name
            name_tag = (
                product.select_one(".item_name") or
                product.select_one(".goods_name") or
                product.select_one("a[title]")
            )
            if name_tag:
                product_name = name_tag.get("title") or name_tag.text.strip()
            else:
                product_name = query

            # Extract price
            price_tag = product.select_one(".item_price") or product.select_one(".price")
            price = price_tag.text.strip() if price_tag else None

            if not img_url:
                logger.warning(f"No Daiso image URL for: {query}")
                return None

            logger.info(f"Found Daiso image: {product_name}")
            return CrawledImage(
                url=img_url,
                product_name=product_name,
                brand="Daiso",
                source="daiso",
                price=price,
            )

        except Exception as e:
            logger.error(f"Failed to crawl Daiso: {e}")
            return None

    def search_musinsa(self, query: str) -> Optional[CrawledImage]:
        """Search for fashion image on Musinsa.

        Uses Playwright for JS-rendered content.

        Args:
            query: Product name or search query

        Returns:
            CrawledImage if found, None otherwise
        """
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.musinsa.com/search/goods?keyword={encoded_query}&keywordType=keyword"

        try:
            # Musinsa requires Playwright (heavy JS)
            if self.use_playwright:
                html = self._fetch_with_playwright(search_url, wait_selector=".search-list")
                if not html:
                    logger.warning(f"Playwright failed for Musinsa: {query}")
                    return None
            else:
                response = self.session.get(search_url, timeout=15)
                response.raise_for_status()
                html = response.text

            soup = BeautifulSoup(html, "html.parser")

            # Musinsa product selectors
            product = (
                soup.select_one(".search-list__item") or
                soup.select_one(".li_inner") or
                soup.select_one("[data-goods-no]") or
                soup.select_one(".goods-list__item")
            )

            if not product:
                logger.warning(f"No product found on Musinsa for: {query}")
                return None

            # Extract image
            img_tag = product.select_one("img")
            img_url = ""
            if img_tag:
                img_url = (
                    img_tag.get("src") or
                    img_tag.get("data-src") or
                    img_tag.get("data-original") or
                    img_tag.get("data-lazy-src") or
                    ""
                )
                if img_url and not img_url.startswith("http"):
                    img_url = "https:" + img_url if img_url.startswith("//") else "https://www.musinsa.com" + img_url

            # Extract name
            name_tag = (
                product.select_one(".search-list__title") or
                product.select_one(".list_info a") or
                product.select_one(".goods_name")
            )
            if name_tag:
                product_name = name_tag.get("title") or name_tag.text.strip()
            else:
                product_name = query

            # Extract brand
            brand_tag = (
                product.select_one(".search-list__brand") or
                product.select_one(".brand")
            )
            brand = brand_tag.text.strip() if brand_tag else ""

            # Extract price
            price_tag = (
                product.select_one(".search-list__price") or
                product.select_one(".price")
            )
            price = price_tag.text.strip() if price_tag else None

            if not img_url:
                logger.warning(f"No Musinsa image URL for: {query}")
                return None

            logger.info(f"Found Musinsa image: {product_name}")
            return CrawledImage(
                url=img_url,
                product_name=product_name,
                brand=brand,
                source="musinsa",
                price=price,
            )

        except Exception as e:
            logger.error(f"Failed to crawl Musinsa: {e}")
            return None

    def search_by_category(self, query: str, category: str) -> Optional[CrawledImage]:
        """Search appropriate source based on category.

        Args:
            query: Product name or search query
            category: K-Culture category (K-Beauty, K-Food, K-Fashion, K-Pop)

        Returns:
            CrawledImage if found, None otherwise
        """
        category_lower = category.lower()

        if category_lower in ("k-beauty", "kbeauty"):
            # Try Olive Young first, then Daiso
            result = self.search_oliveyoung(query)
            if not result:
                result = self.search_daiso(query)
            return result

        elif category_lower in ("k-food", "kfood"):
            # Amazon has better K-Food products (ramen, snacks, etc.)
            return self.search_amazon_kfood(query)

        elif category_lower in ("k-fashion", "kfashion"):
            return self.search_musinsa(query)

        elif category_lower in ("k-pop", "kpop"):
            # K-Pop should use YouTube thumbnails instead (copyright safety)
            logger.warning("K-Pop images should use YouTube thumbnails. Use youtube_fetcher.py")
            return None

        else:
            # Default to Olive Young
            return self.search_oliveyoung(query)

    def search_multiple(self, queries: list[str], category: str) -> list[CrawledImage]:
        """Search for multiple products.

        Args:
            queries: List of product names
            category: K-Culture category

        Returns:
            List of CrawledImage objects
        """
        results = []
        for query in queries:
            image = self.search_by_category(query, category)
            if image:
                results.append(image)
        return results


def generate_image_credit(source: str, product_name: str = "") -> str:
    """Generate image credit HTML.

    Args:
        source: Source site name
        product_name: Optional product name

    Returns:
        HTML string for image credit
    """
    credits = {
        "oliveyoung": "Olive Young",
        "oliveyoung_global": "Olive Young Global",
        "amazon": "Amazon",
        "daiso": "Daiso Korea",
        "musinsa": "Musinsa",
        "youtube": "YouTube",
    }
    credit_name = credits.get(source, source.title())
    return f'<p class="image-credit" style="font-size: 12px; color: #888; margin-top: 4px;">Image: {credit_name}</p>'
