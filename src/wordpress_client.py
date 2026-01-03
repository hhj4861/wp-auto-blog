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
    def from_env(cls, mode: str = "tech") -> "WPConfig":
        """Create config from environment variables.

        Args:
            mode: Blog mode - "tech" or "general"

        Returns:
            WPConfig instance

        Raises:
            ValueError: If required env vars are missing
        """
        mode_upper = mode.upper()

        # Try mode-specific env vars first, fall back to generic
        url = os.getenv(f"WP_{mode_upper}_URL") or os.getenv("WP_URL")
        username = os.getenv(f"WP_{mode_upper}_USERNAME") or os.getenv("WP_USERNAME")
        app_password = os.getenv(f"WP_{mode_upper}_APP_PASSWORD") or os.getenv("WP_APP_PASSWORD")

        if not all([url, username, app_password]):
            raise ValueError(f"Missing WordPress configuration for mode '{mode}' in environment")

        logger.info(f"WordPress config loaded for mode: {mode} -> {url}")

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

    # Category-to-tags mapping for automatic tagging (SEO 최적화)
    CATEGORY_TAGS = {
        # === trendpulse.blog 사일로 구조 (5개 카테고리 - 한국어) ===

        # 테크: AI, 모바일, 소프트웨어 트렌드 (트래픽 유입)
        "테크": [
            "AI", "인공지능", "ChatGPT", "신기술", "테크트렌드", "미래기술",
            "GPT", "Claude", "자동화", "개발자", "프로그래밍", "앱", "소프트웨어",
        ],

        # 비즈니스: 기업 분석, 마케팅, 경제 이슈 해설 (브랜딩)
        "비즈니스": [
            "비즈니스", "기업분석", "산업트렌드", "커리어", "마케팅", "전략",
            "스타트업", "창업", "사이드프로젝트", "부업", "수익화", "브랜딩",
        ],

        # 생산성: 업무 툴, 자기계발, 생산성 팁 (체류시간 증대)
        "생산성": [
            "생산성", "업무효율", "자동화", "노션", "자기계발", "협업툴",
            "시간관리", "습관", "루틴", "미니멀리즘", "디지털미니멀리즘",
            "가계부", "재테크", "돈관리", "Obsidian", "메모앱",
        ],

        # 리뷰: IT 기기, 책, 서비스 리뷰 (직접적인 수익 - 제휴 마케팅)
        "리뷰": [
            "리뷰", "추천", "비교분석", "가성비", "데스크테리어", "재택근무",
            "언박싱", "사용후기", "장단점", "구매가이드", "베스트", "TOP",
        ],

        # 건강: 운동, 다이어트, 웰니스 (제휴 마케팅 - 건강식품/운동기구)
        "건강": [
            "건강", "다이어트", "운동", "피트니스", "웰니스", "영양제",
            "바이오해킹", "슬립테크", "수면", "명상", "스트레스관리", "멘탈",
        ],

        # === bytepulse.io 니치 카테고리 ===
        "AI Tools": ["AI", "Machine Learning", "LLM", "Automation", "GPT", "Claude", "Gemini", "OpenAI"],
        "Dev Productivity": ["Developer Tools", "IDE", "Workflow", "Coding", "Efficiency", "VS Code", "Vim"],
        "SaaS Reviews": ["SaaS", "Software Review", "Cloud", "Business Tools", "Startup", "Notion", "Obsidian"],
        "Web3 Security": ["Web3", "Blockchain", "Security", "Crypto", "Smart Contracts", "DeFi"],
        "Frontend Dev": ["Frontend", "React", "JavaScript", "CSS", "UI/UX", "TypeScript", "Next.js"],
        "Backend Dev": ["Backend", "API", "Database", "DevOps", "Server", "Python", "Node.js"],
        "Startup Tools": ["Startup", "MVP", "Growth", "Founder", "Business", "SaaS", "Indie Hacker"],
    }

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

        # Build tag list: content keywords + category-based tags
        all_tags = list(content.keywords) if content.keywords else []
        if category and category in self.CATEGORY_TAGS:
            category_tags = self.CATEGORY_TAGS[category]
            all_tags.extend(category_tags)
            logger.info(f"Added category tags: {category_tags}")

        # Get/create tags
        tag_ids = self._get_or_create_tags(all_tags)

        # Create post with SEO optimization
        # Focus keyword: 첫 번째 키워드 사용
        focus_keyword = content.keywords[0] if content.keywords else ""

        # Excerpt: meta_description 사용 (카드에 표시될 간결한 요약)
        excerpt = content.meta_description
        if len(excerpt) < 50:
            # meta_description이 너무 짧으면 본문에서 추출
            excerpt = self._prepare_excerpt(content.html)

        # 카테고리별 색상 클래스 추가
        category_class = ""
        if category:
            category_slug = category.lower().replace(" ", "-")
            category_class = f"category-{category_slug}"

        # 콘텐츠를 카테고리 wrapper로 감싸기
        wrapped_html = f'<div class="post-content {category_class}" data-category="{category or ""}">\n{prepared_html}\n</div>'

        post_data = {
            "title": content.title,
            "content": wrapped_html,
            "excerpt": excerpt,
            "status": status.value,
            "meta": {
                # Yoast SEO 메타 설정
                "_yoast_wpseo_metadesc": content.meta_description,
                "_yoast_wpseo_focuskw": focus_keyword,
                "_yoast_wpseo_title": f"{content.title} | TrendPulse",
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

        for keyword in keywords[:12]:  # Limit to 12 tags for better SEO
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
        """Prepare content with embedded images - image-centric layout.

        Args:
            html: Original HTML content
            images: Images to insert

        Returns:
            HTML with images inserted prominently
        """
        if not images:
            return html

        result = html
        image_idx = 0

        # 1. Add hero image at the very beginning (before 3-line summary)
        # H1 is removed, so insert at the start of content
        if image_idx < len(images):
            img = images[image_idx]
            hero_html = f'''
<figure class="wp-block-image aligncenter size-large hero-image" style="max-width:800px;margin:0 auto 30px auto;">
    <img src="{img.url}" alt="{img.alt}" style="width:100%;max-width:800px;height:auto;border-radius:12px;"/>
    <figcaption style="text-align:center;font-size:0.85em;color:#888;margin-top:10px;">Photo by {img.photographer}</figcaption>
</figure>
'''
            # 콘텐츠 맨 앞에 이미지 삽입
            result = hero_html + result
            image_idx += 1

        # 2. Find all H2 sections and insert images after each one
        h2_pattern = re.compile(r"(</h2>)", re.IGNORECASE)

        # Need to re-find matches since we modified the string
        offset = 0
        for match in h2_pattern.finditer(result):
            if image_idx >= len(images):
                break

            img = images[image_idx]
            img_html = f'''
<figure class="wp-block-image aligncenter size-large" style="max-width:800px;margin:25px auto;">
    <img src="{img.url}" alt="{img.alt}" style="width:100%;max-width:800px;height:auto;border-radius:8px;"/>
    <figcaption style="text-align:center;font-size:0.85em;color:#888;margin-top:10px;">Photo by {img.photographer}</figcaption>
</figure>
'''
            # Re-calculate position with offset
            actual_pos = match.end() + offset
            result = result[:actual_pos] + img_html + result[actual_pos:]
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
        # Remove <style> tags and their content first
        text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.IGNORECASE | re.DOTALL)
        # Remove <script> tags and their content
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", text)
        # Clean whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Get first ~300 chars
        if len(text) > 300:
            text = text[:297] + "..."

        return text

    def get_recent_posts(self, count: int = 100) -> list[dict]:
        """Fetch recent posts from WordPress.

        Args:
            count: Number of posts to fetch (default: 100)

        Returns:
            List of post dictionaries with id, title, slug
        """
        posts = []
        per_page = min(count, 100)  # WordPress max is 100 per page
        page = 1

        try:
            while len(posts) < count:
                response = requests.get(
                    f"{self._api_base}/posts",
                    headers=self._get_auth_headers(),
                    params={
                        "per_page": per_page,
                        "page": page,
                        "status": "any",  # Include drafts and published
                        "_fields": "id,title,slug",  # Only fetch needed fields
                    },
                    timeout=15,
                )

                if response.status_code == 400:
                    # No more pages
                    break

                response.raise_for_status()
                page_posts = response.json()

                if not page_posts:
                    break

                for post in page_posts:
                    posts.append({
                        "id": post["id"],
                        "title": post["title"]["rendered"],
                        "slug": post["slug"],
                    })

                if len(page_posts) < per_page:
                    break

                page += 1

            logger.info(f"Fetched {len(posts)} existing posts from WordPress")
            return posts

        except Exception as e:
            logger.error(f"Failed to fetch posts: {e}")
            return []

    def is_duplicate_topic(self, topic: str, threshold: float = 0.6) -> tuple[bool, Optional[str]]:
        """Check if a topic is similar to existing posts.

        Uses keyword overlap to detect duplicates.

        Args:
            topic: Topic to check
            threshold: Similarity threshold (0-1), default 0.6

        Returns:
            Tuple of (is_duplicate, matching_title or None)
        """
        existing_posts = self.get_recent_posts(count=100)

        if not existing_posts:
            return False, None

        # Extract keywords from topic (simple tokenization)
        topic_words = set(self._extract_keywords(topic))

        for post in existing_posts:
            title = post["title"]
            title_words = set(self._extract_keywords(title))

            if not topic_words or not title_words:
                continue

            # Calculate Jaccard similarity
            intersection = topic_words & title_words
            union = topic_words | title_words

            if union:
                similarity = len(intersection) / len(union)
                if similarity >= threshold:
                    logger.warning(f"Duplicate detected: '{topic}' similar to '{title}' (similarity: {similarity:.2f})")
                    return True, title

        return False, None

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords from text for similarity comparison.

        Args:
            text: Text to extract keywords from

        Returns:
            List of lowercase keywords
        """
        # Common stopwords to ignore
        stopwords = {
            # Korean
            "의", "를", "을", "이", "가", "에", "와", "과", "으로", "로", "에서",
            "하는", "한", "할", "된", "되는", "있는", "없는", "위한", "통한",
            "대한", "관한", "따른", "같은", "다른", "모든", "어떤",
            # English
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "can", "this", "that",
            "these", "those", "what", "which", "who", "how", "why", "when", "where",
            # Common words
            "top", "best", "review", "guide", "tips", "ways", "things",
            "2024", "2025", "2026",
        }

        # Remove special characters and split
        words = re.sub(r"[^\w\s가-힣]", " ", text.lower()).split()

        # Filter short words and stopwords
        keywords = [
            w for w in words
            if len(w) >= 2 and w not in stopwords
        ]

        return keywords
