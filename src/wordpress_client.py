"""WordPress Client module for posting content via REST API.

Handles authentication, post creation, media upload, and taxonomy management.

FR-005: WordPress Publishing
"""

from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

import requests
from loguru import logger

from src.content_generator import GeneratedContent
from src.image_fetcher import FetchedImage


class PostStatus(Enum):
    """WordPress post status."""

    DRAFT = "draft"
    PUBLISH = "publish"
    PENDING = "pending"
    PRIVATE = "private"


@dataclass
class WPConfig:
    """WordPress connection configuration.

    Attributes:
        url: WordPress site URL
        username: WordPress username
        app_password: Application password (not user password)
    """

    url: str
    username: str
    app_password: str

    def __post_init__(self) -> None:
        """Clean up URL after initialization."""
        self.url = self.url.rstrip("/")

    @classmethod
    def from_env(cls) -> "WPConfig":
        """Create config from environment variables.

        Returns:
            WPConfig instance

        Raises:
            ValueError: If required env vars are missing
        """
        url = os.getenv("WP_URL")
        username = os.getenv("WP_USERNAME")
        app_password = os.getenv("WP_APP_PASSWORD")

        if not all([url, username, app_password]):
            raise ValueError("Missing WordPress configuration in environment")

        return cls(
            url=url,  # type: ignore
            username=username,  # type: ignore
            app_password=app_password,  # type: ignore
        )


@dataclass
class CreatedPost:
    """Represents a created WordPress post.

    Attributes:
        id: WordPress post ID
        url: Post URL
        title: Post title
        status: Post status
    """

    id: int
    url: str
    title: str
    status: PostStatus

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "status": self.status.value,
        }


class WordPressClient:
    """Client for WordPress REST API.

    Example:
        >>> client = WordPressClient()
        >>> if client.verify_connection():
        ...     post = client.create_post(content, images)
        ...     print(f"Created: {post.url}")
    """

    def __init__(self, config: Optional[WPConfig] = None) -> None:
        """Initialize WordPressClient.

        Args:
            config: Optional configuration. Loads from env if not provided.
        """
        self.config = config or WPConfig.from_env()
        self._api_base = f"{self.config.url}/wp-json/wp/v2"

    def verify_connection(self) -> bool:
        """Verify connection to WordPress site.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = requests.get(
                f"{self._api_base}/users/me",
                headers=self._get_auth_headers(),
                timeout=10,
            )
            response.raise_for_status()
            user_data = response.json()
            logger.info(f"Connected to WordPress as: {user_data.get('name', 'Unknown')}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to WordPress: {e}")
            return False

    def create_post(
        self,
        content: GeneratedContent,
        images: list[FetchedImage],
        status: PostStatus = PostStatus.DRAFT,
        category: Optional[str] = None,
    ) -> CreatedPost:
        """Create a new WordPress post.

        Args:
            content: Generated content to post
            images: Images to include
            status: Post status (default: draft)
            category: Category name (optional)

        Returns:
            CreatedPost object with post details
        """
        logger.info(f"Creating post: {content.title}")

        # Upload featured image first
        featured_media_id = None
        if images:
            featured_media_id = self._upload_media(
                image_url=images[0].url,
                alt_text=images[0].alt,
            )

        # Prepare content with images
        prepared_html = self._prepare_content(content.html, images[1:] if len(images) > 1 else [])

        # Get/create category
        category_ids = []
        if category:
            cat_id = self._get_or_create_category(category)
            if cat_id:
                category_ids.append(cat_id)

        # Get/create tags from keywords
        tag_ids = self._get_or_create_tags(content.keywords)

        # Create post
        post_data = {
            "title": content.title,
            "content": prepared_html,
            "excerpt": self._prepare_excerpt(content.html),
            "status": status.value,
            "meta": {
                "_yoast_wpseo_metadesc": content.meta_description,
            },
        }

        if featured_media_id:
            post_data["featured_media"] = featured_media_id

        if category_ids:
            post_data["categories"] = category_ids

        if tag_ids:
            post_data["tags"] = tag_ids

        try:
            response = requests.post(
                f"{self._api_base}/posts",
                headers=self._get_auth_headers(),
                json=post_data,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            created_post = CreatedPost(
                id=data["id"],
                url=data["link"],
                title=data["title"]["rendered"],
                status=PostStatus(data["status"]),
            )

            logger.info(f"Post created: {created_post.url}")
            return created_post

        except Exception as e:
            logger.error(f"Failed to create post: {e}")
            raise

    def _upload_media(
        self,
        image_url: str,
        alt_text: str,
    ) -> Optional[int]:
        """Upload media to WordPress.

        Args:
            image_url: URL of image to upload
            alt_text: Alt text for the image

        Returns:
            WordPress media ID or None on failure
        """
        try:
            # Download image
            img_response = requests.get(image_url, timeout=30)
            img_response.raise_for_status()

            # Get filename from URL
            parsed = urlparse(image_url)
            filename = os.path.basename(parsed.path) or "image.jpg"
            if not filename.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
                filename += ".jpg"

            # Upload to WordPress
            headers = self._get_auth_headers()
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'
            headers["Content-Type"] = "image/jpeg"

            response = requests.post(
                f"{self._api_base}/media",
                headers=headers,
                data=img_response.content,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()

            media_id = data["id"]

            # Update alt text
            try:
                requests.post(
                    f"{self._api_base}/media/{media_id}",
                    headers=self._get_auth_headers(),
                    json={"alt_text": alt_text},
                    timeout=10,
                )
            except Exception:
                pass  # Alt text update is not critical

            logger.debug(f"Uploaded media: {media_id}")
            return media_id

        except Exception as e:
            logger.error(f"Failed to upload media: {e}")
            return None

    def _get_auth_headers(self) -> dict:
        """Get authentication headers.

        Returns:
            Headers dict with Basic auth
        """
        credentials = f"{self.config.username}:{self.config.app_password}"
        encoded = base64.b64encode(credentials.encode()).decode()

        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
        }

    def _get_or_create_category(self, name: str) -> Optional[int]:
        """Get or create a category.

        Args:
            name: Category name

        Returns:
            Category ID or None
        """
        try:
            # Search for existing category
            response = requests.get(
                f"{self._api_base}/categories",
                headers=self._get_auth_headers(),
                params={"search": name},
                timeout=10,
            )
            response.raise_for_status()
            categories = response.json()

            for cat in categories:
                if cat["name"].lower() == name.lower():
                    return cat["id"]

            # Create new category
            response = requests.post(
                f"{self._api_base}/categories",
                headers=self._get_auth_headers(),
                json={"name": name},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()["id"]

        except Exception as e:
            logger.warning(f"Failed to get/create category: {e}")
            return None

    def _get_or_create_tags(self, keywords: list[str]) -> list[int]:
        """Get or create tags from keywords.

        Args:
            keywords: List of keywords to use as tags

        Returns:
            List of tag IDs
        """
        tag_ids: list[int] = []

        for keyword in keywords[:5]:  # Limit to 5 tags
            try:
                # Search for existing tag
                response = requests.get(
                    f"{self._api_base}/tags",
                    headers=self._get_auth_headers(),
                    params={"search": keyword},
                    timeout=10,
                )
                response.raise_for_status()
                tags = response.json()

                found = False
                for tag in tags:
                    if tag["name"].lower() == keyword.lower():
                        tag_ids.append(tag["id"])
                        found = True
                        break

                if not found:
                    # Create new tag
                    response = requests.post(
                        f"{self._api_base}/tags",
                        headers=self._get_auth_headers(),
                        json={"name": keyword},
                        timeout=10,
                    )
                    response.raise_for_status()
                    tag_ids.append(response.json()["id"])

            except Exception as e:
                logger.warning(f"Failed to get/create tag '{keyword}': {e}")
                continue

        return tag_ids

    def _prepare_content(
        self,
        html: str,
        images: list[FetchedImage],
    ) -> str:
        """Prepare content with embedded images.

        Args:
            html: Original HTML content
            images: Images to insert

        Returns:
            HTML with images inserted
        """
        if not images:
            return html

        # Find H2 tags and insert images after some of them
        h2_pattern = re.compile(r"(</h2>)", re.IGNORECASE)
        h2_matches = list(h2_pattern.finditer(html))

        if not h2_matches:
            return html

        # Insert images after every 2nd H2
        result = html
        offset = 0
        image_idx = 0

        for i, match in enumerate(h2_matches):
            if i % 2 == 1 and image_idx < len(images):
                img = images[image_idx]
                img_html = f'\n<figure class="wp-block-image size-large"><img src="{img.url}" alt="{img.alt}"/><figcaption>Photo by {img.photographer}</figcaption></figure>\n'

                insert_pos = match.end() + offset
                result = result[:insert_pos] + img_html + result[insert_pos:]
                offset += len(img_html)
                image_idx += 1

        return result

    def _prepare_excerpt(self, html: str) -> str:
        """Prepare excerpt from content.

        Args:
            html: HTML content

        Returns:
            Plain text excerpt (max 300 chars)
        """
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", html)
        # Clean whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Get first ~300 chars
        if len(text) > 300:
            text = text[:297] + "..."

        return text
