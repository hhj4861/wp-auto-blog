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

    images_per_post: int = 8  # More images for image-centric posts
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

        # Build search query - use keywords or fallback to topic
        if keywords:
            query = " ".join(keywords[:3])  # Use first 3 keywords
        elif topic:
            # Extract English words from topic for image search
            import re
            english_words = re.findall(r"[a-zA-Z]+", topic)
            if english_words:
                query = " ".join(english_words[:3])
            else:
                # Translate common Korean terms to English for image search
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
                }
                query_parts = []
                for kr, en in korean_to_english.items():
                    if kr in topic:
                        query_parts.append(en)
                query = " ".join(query_parts[:2]) if query_parts else "lifestyle modern"
        else:
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
