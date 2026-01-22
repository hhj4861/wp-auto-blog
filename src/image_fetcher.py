"""Image Fetcher module for retrieving images from stock photo APIs.

Fetches relevant images from Unsplash and Pexels.

FR-003: Image Addition
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests
from loguru import logger


class ImageSource(Enum):
    """Image source platforms."""

    UNSPLASH = "unsplash"
    PEXELS = "pexels"


@dataclass
class FetchedImage:
    """Represents a fetched image.

    Attributes:
        url: Direct URL to the image
        alt: Alt text for accessibility
        photographer: Photographer name for attribution
        source: Source platform
        width: Image width in pixels
        height: Image height in pixels
    """

    url: str
    alt: str
    photographer: str
    source: ImageSource
    width: int
    height: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "url": self.url,
            "alt": self.alt,
            "photographer": self.photographer,
            "source": self.source.value,
            "width": self.width,
            "height": self.height,
        }


@dataclass
class ImageConfig:
    """Configuration for image fetching.

    Attributes:
        images_per_post: Number of images per blog post
        min_width: Minimum image width
        min_height: Minimum image height
        primary_source: Primary image source
        orientation: Preferred orientation (landscape, portrait, squarish)
    """

    images_per_post: int = 3  # Only need hero image + backup
    min_width: int = 1200
    min_height: int = 800
    primary_source: ImageSource = ImageSource.UNSPLASH
    orientation: str = "landscape"


class ImageFetcher:
    """Fetches images from stock photo APIs.

    Example:
        >>> fetcher = ImageFetcher()
        >>> images = fetcher.fetch(keywords=["ai", "technology"])
        >>> for img in images:
        ...     print(f"{img.url} - {img.alt}")
    """

    UNSPLASH_API = "https://api.unsplash.com"
    PEXELS_API = "https://api.pexels.com/v1"

    def __init__(self, config: Optional[ImageConfig] = None) -> None:
        """Initialize ImageFetcher.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or ImageConfig()
        self._unsplash_key = os.getenv("UNSPLASH_ACCESS_KEY")
        self._pexels_key = os.getenv("PEXELS_API_KEY")

    def fetch(
        self,
        keywords: list[str],
        topic: Optional[str] = None,
    ) -> list[FetchedImage]:
        """Fetch images for given keywords.

        Args:
            keywords: List of search keywords
            topic: Optional topic string as fallback for image search

        Returns:
            List of FetchedImage objects
        """
        logger.info(f"Fetching images for keywords: {keywords}, topic: {topic}")

        all_images: list[FetchedImage] = []

        # Korean to English translation map for image search
        korean_to_english = {
            "다이어트": "diet food healthy",
            "식단": "meal plan food",
            "홈오피스": "home office workspace",
            "인테리어": "interior design",
            "생산성": "productivity work",
            "앱": "mobile app technology",
            "트렌드": "trend modern",
            "건강": "health wellness",
            "운동": "exercise fitness",
            "요리": "cooking food",
            "여행": "travel vacation",
            "패션": "fashion style",
            "뷰티": "beauty cosmetics",
            "테크": "technology gadget",
            "금융": "finance money",
            "부동산": "real estate home",
            "자기계발": "self improvement",
            "독서": "reading books",
            "음악": "music listening",
            "영화": "movie cinema",
            "리뷰": "product review",
            "추천": "recommendation best",
            "비교": "comparison versus",
            # 취업/항공 관련
            "외항사": "flight attendant airline",
            "승무원": "cabin crew stewardess",
            "항공사": "airline aviation",
            "채용": "job interview career",
            "면접": "interview professional",
            "취업": "career job office",
            "에미레이트": "emirates airline dubai",
            "카타르": "qatar airways doha",
            "싱가포르": "singapore airlines",
            "에티하드": "etihad airways",
            "캐세이": "cathay pacific",
        }

        # K-Culture brand/product to search query mapping
        kculture_mapping = {
            # K-Beauty brands
            "cosrx": "korean skincare serum",
            "snail mucin": "skincare essence serum",
            "beauty of joseon": "korean skincare glow",
            "laneige": "korean beauty hydration",
            "innisfree": "korean natural skincare",
            "etude": "korean makeup cosmetics",
            "missha": "korean skincare beauty",
            "sulwhasoo": "luxury korean skincare",
            "anua": "korean toner skincare",
            "torriden": "korean hydrating serum",
            "numbuzin": "korean skincare glass skin",
            "tirtir": "korean cushion foundation",
            "rom&nd": "korean lip tint makeup",
            # K-Food (specific food photography keywords)
            "gochujang": "korean red pepper paste cooking",
            "kimchi": "korean kimchi fermented cabbage dish",
            "tteokbokki": "korean spicy rice cakes street food",
            "bibimbap": "korean bibimbap rice bowl colorful",
            "samgyeopsal": "korean bbq grilled pork belly",
            "soju": "korean soju bottle glass drink",
            "ramyeon": "korean instant ramen noodles spicy bowl",
            "ramen": "asian ramen noodles soup bowl",
            "korean food": "korean cuisine dishes table spread",
            "korean recipe": "korean cooking ingredients kitchen",
            "korean snacks": "korean snack food colorful packaging",
            "buldak": "korean spicy fire noodles bowl",
            "korean noodles": "korean noodles soup bowl chopsticks",
            "banchan": "korean side dishes small plates",
            "korean bbq": "korean barbecue grilled meat restaurant",
            "cheese": "korean cheese corn dog melted stretchy",
            "korean cheese": "korean cheese corn dog melted stretchy",
            "corn dog": "korean corn dog cheese hot dog street food",
            "hotdog": "korean corn dog cheese fried crispy",
            "fried chicken": "korean fried chicken crispy golden",
            "chimaek": "korean fried chicken beer combo",
            "tteok": "korean rice cake dessert colorful",
            "korean dessert": "korean sweet treats bingsu cafe",
            "bingsu": "korean shaved ice dessert fruit",
            # K-Pop
            "bts": "kpop concert performance",
            "blackpink": "kpop girl group performance",
            "twice": "kpop dance performance",
            "newjeans": "kpop modern performance",
            "stray kids": "kpop boy group concert",
            "aespa": "kpop futuristic performance",
            "seventeen": "kpop choreography performance",
            # K-Fashion
            "korean fashion": "korean streetwear style",
            "k-fashion": "korean style clothing",
            "hanbok": "korean traditional dress",
            # K-Drama
            "k-drama": "korean drama scene",
            "kdrama": "korean tv series",
        }

        # Build search query
        query = None
        search_text = " ".join(keywords[:5]) if keywords else (topic or "")
        search_lower = search_text.lower()

        # First, check K-Culture mappings (brand/product specific)
        for kculture_key, kculture_query in kculture_mapping.items():
            if kculture_key.lower() in search_lower:
                query = kculture_query
                logger.debug(f"K-Culture mapping: '{kculture_key}' -> '{query}'")
                break

        # If no K-Culture match, try to find English words
        if not query:
            import re
            english_words = re.findall(r"[a-zA-Z]{3,}", search_text)
            if english_words:
                query = " ".join(english_words[:3])

        # If still no query, translate Korean keywords
        if not query:
            query_parts = []
            for kr, en in korean_to_english.items():
                if kr in search_text:
                    query_parts.append(en.split()[0])  # Take first English word
                    if len(query_parts) >= 3:
                        break
            if query_parts:
                query = " ".join(query_parts)

        # Fallback
        if not query:
            query = "lifestyle modern"

        logger.info(f"Image search query: {query}")

        # Try primary source first
        if self.config.primary_source == ImageSource.UNSPLASH:
            all_images.extend(self._fetch_unsplash(query))
            if len(all_images) < self.config.images_per_post:
                all_images.extend(self._fetch_pexels(query))
        else:
            all_images.extend(self._fetch_pexels(query))
            if len(all_images) < self.config.images_per_post:
                all_images.extend(self._fetch_unsplash(query))

        # Filter images
        filtered = self._filter_images(all_images)

        # Limit to config count
        result = filtered[: self.config.images_per_post]

        logger.info(f"Returning {len(result)} images")
        return result

    def _fetch_unsplash(self, query: str) -> list[FetchedImage]:
        """Fetch images from Unsplash API.

        Args:
            query: Search query

        Returns:
            List of FetchedImage objects
        """
        images: list[FetchedImage] = []

        if not self._unsplash_key:
            logger.warning("Unsplash API key not configured")
            return images

        try:
            response = requests.get(
                f"{self.UNSPLASH_API}/search/photos",
                params={
                    "query": query,
                    "per_page": self.config.images_per_post * 2,
                    "orientation": self.config.orientation,
                },
                headers={
                    "Authorization": f"Client-ID {self._unsplash_key}",
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            for photo in data.get("results", []):
                url = photo.get("urls", {}).get("regular", "")
                if not url:
                    continue

                alt_original = photo.get("alt_description")
                photographer = photo.get("user", {}).get("name", "Unknown")
                width = photo.get("width", 0)
                height = photo.get("height", 0)

                # Generate alt text
                alt = self._generate_alt(alt_original, query.split())

                images.append(
                    FetchedImage(
                        url=url,
                        alt=alt,
                        photographer=photographer,
                        source=ImageSource.UNSPLASH,
                        width=width,
                        height=height,
                    )
                )

            logger.info(f"Fetched {len(images)} images from Unsplash")

        except Exception as e:
            logger.error(f"Failed to fetch from Unsplash: {e}")

        return images

    def _fetch_pexels(self, query: str) -> list[FetchedImage]:
        """Fetch images from Pexels API.

        Args:
            query: Search query

        Returns:
            List of FetchedImage objects
        """
        images: list[FetchedImage] = []

        if not self._pexels_key:
            logger.warning("Pexels API key not configured")
            return images

        try:
            response = requests.get(
                f"{self.PEXELS_API}/search",
                params={
                    "query": query,
                    "per_page": self.config.images_per_post * 2,
                    "orientation": self.config.orientation,
                },
                headers={
                    "Authorization": self._pexels_key,
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            for photo in data.get("photos", []):
                url = photo.get("src", {}).get("large", "")
                if not url:
                    continue

                alt_original = photo.get("alt")
                photographer = photo.get("photographer", "Unknown")
                width = photo.get("width", 0)
                height = photo.get("height", 0)

                # Generate alt text
                alt = self._generate_alt(alt_original, query.split())

                images.append(
                    FetchedImage(
                        url=url,
                        alt=alt,
                        photographer=photographer,
                        source=ImageSource.PEXELS,
                        width=width,
                        height=height,
                    )
                )

            logger.info(f"Fetched {len(images)} images from Pexels")

        except Exception as e:
            logger.error(f"Failed to fetch from Pexels: {e}")

        return images

    def _generate_alt(
        self,
        original_alt: Optional[str],
        keywords: list[str],
    ) -> str:
        """Generate SEO-friendly alt text.

        Args:
            original_alt: Original alt text from API
            keywords: Search keywords

        Returns:
            Generated alt text (max 125 chars)
        """
        # Use original if available and reasonable
        if original_alt and len(original_alt) > 5:
            alt = original_alt.strip()
        else:
            # Generate from keywords
            if keywords:
                alt = f"Image related to {', '.join(keywords[:3])}"
            else:
                alt = "Blog post illustration"

        # Truncate if too long
        if len(alt) > 125:
            alt = alt[:122] + "..."

        return alt

    def _filter_images(self, images: list[FetchedImage]) -> list[FetchedImage]:
        """Filter images by size and remove duplicates.

        Args:
            images: List of images to filter

        Returns:
            Filtered list of images
        """
        seen_urls: set[str] = set()
        filtered: list[FetchedImage] = []

        for img in images:
            # Skip duplicates
            if img.url in seen_urls:
                continue

            # Check dimensions
            if img.width < self.config.min_width:
                continue
            if img.height < self.config.min_height:
                continue

            seen_urls.add(img.url)
            filtered.append(img)

        return filtered

    def fetch_single(self, query: str, exclude_urls: Optional[set[str]] = None) -> Optional[FetchedImage]:
        """Fetch a single image for a specific search query.

        Used for fetching section-relevant images based on H2 text.

        Args:
            query: Search query string
            exclude_urls: URLs to exclude (already used images)

        Returns:
            Single FetchedImage or None if not found
        """
        exclude_urls = exclude_urls or set()
        logger.debug(f"Fetching single image for query: {query}")

        images: list[FetchedImage] = []

        # Try Unsplash first
        if self._unsplash_key:
            images.extend(self._fetch_unsplash(query))

        # Fallback to Pexels if no results
        if not images and self._pexels_key:
            images.extend(self._fetch_pexels(query))

        # Filter and exclude already used URLs
        for img in images:
            if img.url not in exclude_urls:
                if img.width >= self.config.min_width and img.height >= self.config.min_height:
                    return img

        return None
