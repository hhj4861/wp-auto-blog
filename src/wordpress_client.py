"""WordPress Client module for posting content via REST API.

Handles authentication, post creation, media upload, and taxonomy management.

FR-005: WordPress Publishing
"""

from __future__ import annotations

import base64
import os
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

import requests
from loguru import logger

from src.content_generator import GeneratedContent
from src.image_fetcher import FetchedImage

# Some WAFs (Cloudflare, Wordfence, Sucuri) block the default
# `python-requests/X.Y.Z` User-Agent as a suspected bot; pose as a desktop
# browser to clear those rules from GitHub Actions runners.
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


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
            mode: Blog mode - "tech", "general", or "kculture"

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

        # 취업: 외항사/항공사 취업 정보 (면접, 기출, 채용)
        "취업": [
            "취업", "면접", "채용", "합격", "외항사", "항공사", "승무원",
            "자소서", "자기소개서", "기출문제", "족보", "면접후기",
            "에미레이트", "싱가포르항공", "카타르항공", "대한항공", "아시아나",
        ],

        # === bytepulse.io 니치 카테고리 ===
        "AI Tools": ["AI", "Machine Learning", "LLM", "Automation", "GPT", "Claude", "Gemini", "OpenAI"],
        "Dev Productivity": ["Developer Tools", "IDE", "Workflow", "Coding", "Efficiency", "VS Code", "Vim"],
        "SaaS Reviews": ["SaaS", "Software Review", "Cloud", "Business Tools", "Startup", "Notion", "Obsidian"],
        "Web3 Security": ["Web3", "Blockchain", "Security", "Crypto", "Smart Contracts", "DeFi"],
        "Frontend Dev": ["Frontend", "React", "JavaScript", "CSS", "UI/UX", "TypeScript", "Next.js"],
        "Backend Dev": ["Backend", "API", "Database", "DevOps", "Server", "Python", "Node.js"],
        "Startup Tools": ["Startup", "MVP", "Growth", "Founder", "Business", "SaaS", "Indie Hacker"],

        # === k-pulse.blog K-Culture 카테고리 (US 시장 타겟) ===
        "K-Beauty": [
            "K-Beauty", "Korean Skincare", "Korean Beauty", "Skincare Routine",
            "K-Skincare", "Glass Skin", "Dewy Skin", "Korean Cosmetics",
            "COSRX", "Innisfree", "Laneige", "Beauty of Joseon", "Anua",
            "Serum", "Essence", "Toner", "Sunscreen", "Sheet Mask",
        ],
        "K-Pop": [
            "K-Pop", "Korean Pop", "Kpop", "BTS", "BLACKPINK", "NewJeans",
            "Stray Kids", "TWICE", "aespa", "IVE", "LE SSERAFIM", "SEVENTEEN",
            "Idol", "Korean Music", "Album", "Concert", "Comeback",
            "Photocard", "Lightstick", "Fandom", "Music Video",
        ],
        "K-Food": [
            "K-Food", "Korean Food", "Korean Cuisine", "Korean Recipe",
            "Kimchi", "Korean BBQ", "Tteokbokki", "Bibimbap", "Ramyeon",
            "Buldak", "Korean Snacks", "Soju", "Korean Drinks", "Banchan",
            "Gochujang", "Korean Cooking", "Asian Food", "Spicy Food",
        ],
        "K-Fashion": [
            "K-Fashion", "Korean Fashion", "Korean Style", "Streetwear",
            "Korean Streetwear", "Minimalist Fashion", "Airport Fashion",
            "Kdrama Fashion", "Korean Outfit", "Seoul Fashion", "Musinsa",
            "Korean Brands", "Asian Fashion", "Trendy", "OOTD",
        ],
    }

    # Category hierarchy: child -> parent mapping
    # bytepulse.io unified structure
    CATEGORY_HIERARCHY = {
        # Tech sub-categories
        "AI Tools": "Tech",
        "Dev Productivity": "Tech",
        "SaaS Reviews": "Tech",
        "Web3 Security": "Tech",
        "Frontend Dev": "Tech",
        "Backend Dev": "Tech",
        "Startup Tools": "Tech",
        # K-Culture sub-categories
        "K-Pop": "K-Culture",
        "K-Beauty": "K-Culture",
        "K-Food": "K-Culture",
        "K-Fashion": "K-Culture",
    }

    def __init__(self, config: Optional[WPConfig] = None) -> None:
        """Initialize WordPressClient.

        Args:
            config: Optional configuration. Loads from env if not provided.
        """
        self.config = config or WPConfig.from_env()
        self._api_base = f"{self.config.url}/wp-json/wp/v2"

        # Optional egress proxy. The host WAF (e.g. Hostinger hCDN) blocks
        # GitHub Actions datacenter IPs with 403; routing through a fixed
        # clean-IP proxy permanently bypasses that. Set WP_PROXY (preferred,
        # scopes the proxy to WordPress traffic only) or rely on the standard
        # HTTPS_PROXY/HTTP_PROXY env vars that `requests` honours natively.
        proxy = os.getenv("WP_PROXY", "").strip()
        self._proxies: Optional[dict] = (
            {"http": proxy, "https": proxy} if proxy else None
        )
        if self._proxies:
            logger.info("WordPress requests routed through WP_PROXY")

    def verify_connection(self) -> bool:
        """Verify connection to WordPress site.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            response = self._request_with_retry(
                "GET",
                f"{self._api_base}/users/me",
                headers=self._get_auth_headers(),
                timeout=30,
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
        section_images: Optional[dict[str, FetchedImage]] = None,
        skip_hero_image: bool = False,
        content_type: str = "review",
    ) -> CreatedPost:
        """Create a new WordPress post.

        Args:
            content: Generated content to post
            images: Images to include (first one as hero/featured)
            status: Post status (default: draft)
            category: Category name (optional)
            section_images: Dict mapping H2 text to relevant FetchedImage
            skip_hero_image: If True, don't add hero image in content (for tech mode)
            content_type: Type of content for slug generation (review, comparison, guide, list, news)

        Returns:
            CreatedPost object with post details
        """
        logger.info(f"Creating post: {content.title}")

        # Upload featured image first (WordPress thumbnail)
        featured_media_id = None
        featured_media_url = None
        if images:
            featured_media_id, featured_media_url = self._upload_media(
                image_url=images[0].url,
                alt_text=images[0].alt,
            )
            # Preserve original URL for YouTube link detection
            original_hero_url = images[0].url
            # Update first image URL to use WordPress media URL (avoid CDN blocking)
            if featured_media_url:
                images[0].url = featured_media_url
                logger.info(f"Using WordPress media URL for hero: {featured_media_url[:60]}...")

        # Preserve original URLs for YouTube link detection
        original_urls = {img.url: img.url for img in images}  # Map new URL -> original
        if 'original_hero_url' in dir():
            original_urls[images[0].url] = original_hero_url

        # Also preserve section image original URLs
        section_original_urls = {}
        if section_images:
            for h2_text, img in section_images.items():
                section_original_urls[h2_text] = img.url  # Store original URL

        # Prepare content with images (hero + section images)
        # Pass all images for hero image (first image) and remaining for sections
        prepared_html = self._prepare_content(
            content.html,
            images,  # Pass all images - first for hero, rest for sections
            section_images=section_images,
            skip_hero_image=skip_hero_image,
            original_urls=original_urls,
            section_original_urls=section_original_urls,
        )

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
        # Focus keyphrase: LLM이 생성한 것 우선 사용, 없으면 제목에서 추출
        focus_keyword = ""
        if hasattr(content, 'focus_keyphrase') and content.focus_keyphrase:
            focus_keyword = content.focus_keyphrase
            logger.debug(f"Using LLM-generated focus keyphrase: {focus_keyword}")
        else:
            focus_keyword = self._generate_focus_keyphrase(content.title, content.keywords)

        # Excerpt: 카드에 표시될 요약 (meta_description보다 길게)
        # meta_description은 SEO용 150-160자, excerpt는 카드 표시용 300자
        excerpt = self._prepare_excerpt(content.html)

        # 카테고리별 색상 클래스 추가
        category_class = ""
        if category:
            category_slug = category.lower().replace(" ", "-")
            category_class = f"category-{category_slug}"

        # 콘텐츠를 카테고리 wrapper로 감싸기
        wrapped_html = f'<div class="post-content {category_class}" data-category="{category or ""}">\n{prepared_html}\n</div>'

        # Generate SEO-friendly slug
        slug = self._generate_slug(content.title, content_type)

        post_data = {
            "title": content.title,
            "slug": slug,  # SEO-optimized URL
            "content": wrapped_html,
            "excerpt": excerpt,
            "status": status.value,
            "meta": {
                # Yoast SEO 메타 설정
                "_yoast_wpseo_metadesc": content.meta_description,
                "_yoast_wpseo_focuskw": focus_keyword,
                "_yoast_wpseo_title": f"{content.title} | {self._get_site_name()}",
                # Robots 설정: 0 = index (검색엔진에 노출), 1 = noindex
                "_yoast_wpseo_meta-robots-noindex": "0",
                "_yoast_wpseo_meta-robots-nofollow": "0",
            },
        }

        if featured_media_id:
            post_data["featured_media"] = featured_media_id

        if category_ids:
            post_data["categories"] = category_ids

        if tag_ids:
            post_data["tags"] = tag_ids

        try:
            response = self._request_with_retry(
                "POST",
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

            # Yoast SEO 분석 트리거를 위해 재저장 (PUT 요청)
            try:
                requests.put(
                    f"{self._api_base}/posts/{created_post.id}",
                    headers=self._get_auth_headers(),
                    json={"id": created_post.id},
                    timeout=10,
                )
                logger.debug("Triggered Yoast SEO analysis via re-save")
            except Exception as e:
                logger.warning(f"Failed to trigger Yoast analysis: {e}")

            return created_post

        except Exception as e:
            logger.error(f"Failed to create post: {e}")
            raise

    def get_post_by_slug(self, slug: str) -> Optional[dict]:
        """Find a post by its slug.

        Args:
            slug: The post slug (URL-friendly name)

        Returns:
            Post data dict if found, None otherwise
        """
        try:
            response = self._request_with_retry(
                "GET",
                f"{self._api_base}/posts",
                headers=self._get_auth_headers(),
                params={"slug": slug, "status": "any"},
                timeout=30,
            )
            response.raise_for_status()
            posts = response.json()

            if posts:
                logger.info(f"Found post by slug '{slug}': ID {posts[0]['id']}")
                return posts[0]
            return None

        except Exception as e:
            logger.error(f"Failed to find post by slug: {e}")
            return None

    def get_posts(self, per_page: int = 100, status: str = "any") -> list[dict]:
        """Get all posts from WordPress.

        Args:
            per_page: Number of posts per page (max 100)
            status: Post status filter (any, publish, draft, etc.)

        Returns:
            List of post data dicts
        """
        all_posts = []
        page = 1

        try:
            while True:
                response = self._request_with_retry(
                    "GET",
                    f"{self._api_base}/posts",
                    headers=self._get_auth_headers(),
                    params={"per_page": per_page, "page": page, "status": status},
                    timeout=30,
                )
                response.raise_for_status()
                posts = response.json()

                if not posts:
                    break

                all_posts.extend(posts)
                page += 1

                # Check if there are more pages
                total_pages = int(response.headers.get("X-WP-TotalPages", 1))
                if page > total_pages:
                    break

            logger.info(f"Retrieved {len(all_posts)} posts from WordPress")
            return all_posts

        except Exception as e:
            logger.error(f"Failed to get posts: {e}")
            return all_posts

    def update_post(
        self,
        post_id: int,
        content: GeneratedContent,
        images: Optional[list[FetchedImage]] = None,
        category: Optional[str] = None,
        section_images: Optional[dict[str, FetchedImage]] = None,
        skip_hero_image: bool = False,
        content_type: str = "review",
    ) -> CreatedPost:
        """Update an existing WordPress post.

        Args:
            post_id: WordPress post ID to update
            content: New generated content
            images: New images (optional, keeps existing if None)
            category: Category name (optional)
            section_images: Dict mapping H2 text to relevant FetchedImage
            skip_hero_image: If True, don't add hero image in content
            content_type: Type of content for slug generation

        Returns:
            Updated CreatedPost object
        """
        logger.info(f"Updating post ID {post_id}: {content.title}")

        # Upload new featured image if provided
        featured_media_id = None
        if images:
            featured_media_id, featured_media_url = self._upload_media(
                image_url=images[0].url,
                alt_text=images[0].alt,
            )
            if featured_media_url:
                images[0].url = featured_media_url

        # Prepare content
        prepared_html = self._prepare_content(
            content.html,
            images or [],
            section_images=section_images,
            skip_hero_image=skip_hero_image,
        )

        # Get/create category
        category_ids = []
        if category:
            cat_id = self._get_or_create_category(category)
            if cat_id:
                category_ids.append(cat_id)

        # Build tags
        all_tags = list(content.keywords) if content.keywords else []
        if category and category in self.CATEGORY_TAGS:
            all_tags.extend(self.CATEGORY_TAGS[category])

        tag_ids = self._get_or_create_tags(all_tags)

        # Focus keyphrase
        focus_keyword = ""
        if hasattr(content, 'focus_keyphrase') and content.focus_keyphrase:
            focus_keyword = content.focus_keyphrase
        else:
            focus_keyword = self._generate_focus_keyphrase(content.title, content.keywords)

        # Excerpt
        excerpt = self._prepare_excerpt(content.html)

        # Category wrapper
        category_class = f"category-{category.lower().replace(' ', '-')}" if category else ""
        wrapped_html = f'<div class="post-content {category_class}" data-category="{category or ""}">\n{prepared_html}\n</div>'

        # Build update data
        post_data = {
            "title": content.title,
            "content": wrapped_html,
            "excerpt": excerpt,
            "meta": {
                "_yoast_wpseo_metadesc": content.meta_description,
                "_yoast_wpseo_focuskw": focus_keyword,
                "_yoast_wpseo_title": f"{content.title} | {self._get_site_name()}",
                "_yoast_wpseo_meta-robots-noindex": "0",
                "_yoast_wpseo_meta-robots-nofollow": "0",
            },
        }

        if featured_media_id:
            post_data["featured_media"] = featured_media_id

        if category_ids:
            post_data["categories"] = category_ids

        if tag_ids:
            post_data["tags"] = tag_ids

        try:
            response = requests.put(
                f"{self._api_base}/posts/{post_id}",
                headers=self._get_auth_headers(),
                json=post_data,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            updated_post = CreatedPost(
                id=data["id"],
                url=data["link"],
                title=data["title"]["rendered"],
                status=PostStatus(data["status"]),
            )

            logger.info(f"Post updated: {updated_post.url}")
            return updated_post

        except Exception as e:
            logger.error(f"Failed to update post {post_id}: {e}")
            raise

    def _upload_media(
        self,
        image_url: str,
        alt_text: str,
    ) -> tuple[Optional[int], Optional[str]]:
        """Upload media to WordPress.

        Args:
            image_url: URL of image to upload
            alt_text: Alt text for the image

        Returns:
            Tuple of (WordPress media ID, WordPress media URL) or (None, None) on failure
        """
        try:
            # Download image with proper headers (for CDNs like Olive Young)
            download_headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://global.oliveyoung.com/",
            }
            img_response = requests.get(image_url, headers=download_headers, timeout=30)
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

            response = self._request_with_retry(
                "POST",
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

            # Get the source URL from WordPress response
            media_url = data.get("source_url") or data.get("guid", {}).get("rendered", "")

            logger.debug(f"Uploaded media: {media_id} -> {media_url}")
            return media_id, media_url

        except Exception as e:
            logger.error(f"Failed to upload media: {e}")
            return None, None

    def _get_site_name(self) -> str:
        """Get site name from URL.

        Returns:
            Site name (e.g., 'BytePulse', 'TrendPulse')
        """
        url = self.config.url.lower()
        if "bytepulse" in url:
            return "BytePulse"
        elif "trendpulse" in url:
            return "TrendPulse"
        else:
            # Extract domain name as fallback
            import re
            match = re.search(r'//([^/]+)', url)
            if match:
                domain = match.group(1).split('.')[0]
                return domain.title()
            return "Blog"

    def _get_auth_headers(self) -> dict:
        """Get authentication headers.

        Returns:
            Headers dict with Basic auth + browser-like headers (WAF bypass).

        Includes Sec-Fetch-* headers that real browsers send but bots usually
        skip; many WAFs (Cloudflare, Wordfence) use their absence as a bot
        signal.
        """
        credentials = f"{self.config.username}:{self.config.app_password}"
        encoded = base64.b64encode(credentials.encode()).decode()

        origin = self.config.url.rstrip("/")

        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
            "User-Agent": _BROWSER_UA,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Origin": origin,
            "Referer": f"{origin}/wp-admin/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "X-Requested-With": "XMLHttpRequest",
        }

    def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        retry_statuses: tuple = (429, 500, 502, 503, 504),
        waf_statuses: tuple = (403,),
        max_retries: int = 5,
        waf_quick_retries: int = 1,
        **kwargs,
    ) -> requests.Response:
        """HTTP request with retry. Transient errors back off; WAF blocks fail fast.

        - 429/5xx are genuinely transient: exponential backoff
          (5s, 15s, 30s, 60s, 120s) lets rate-limit windows clear.
        - 403 is a host edge-WAF block (e.g. Hostinger hCDN flagging the
          GitHub Actions IP). It persists for the whole run on a given IP, so
          long same-IP retries only burn the 30-min job budget. We do one quick
          retry then fail fast — the workflow re-runs failed jobs on a fresh
          runner (new IP), which is what actually clears the block.

        A small random jitter breaks synchronized retry patterns when multiple
        jobs hit the WAF at once.
        """
        import random

        fn = getattr(requests, method.lower())
        if self._proxies is not None:
            kwargs.setdefault("proxies", self._proxies)
        base_delays = [5, 15, 30, 60, 120, 120]
        delays = [base_delays[i] + random.uniform(0, 5) for i in range(max_retries)]
        response: Optional[requests.Response] = None

        for attempt in range(max_retries + 1):
            try:
                response = fn(url, **kwargs)
            except requests.RequestException as exc:
                if attempt == max_retries:
                    raise
                logger.warning(
                    f"{method.upper()} {url} raised {type(exc).__name__}; "
                    f"retrying in {delays[attempt]:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(delays[attempt])
                continue

            status = getattr(response, "status_code", None)

            # WAF block: one quick retry, then fail fast (do not burn the budget).
            if isinstance(status, int) and status in waf_statuses:
                if attempt < waf_quick_retries:
                    logger.warning(
                        f"{method.upper()} {url} -> {status} (WAF?); "
                        f"quick retry in 5s (attempt {attempt + 1}/{waf_quick_retries})"
                    )
                    time.sleep(5)
                    continue
                logger.error(
                    f"{method.upper()} {url} -> {status} (edge WAF block); failing "
                    "fast so the workflow can retry on a fresh runner IP"
                )
                return response

            if (
                isinstance(status, int)
                and status in retry_statuses
                and attempt < max_retries
            ):
                logger.warning(
                    f"{method.upper()} {url} -> {status}; "
                    f"retrying in {delays[attempt]:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(delays[attempt])
                continue

            # WAF/CDN often returns 200 with an HTML challenge page instead of
            # the expected JSON. Detect that case so we retry too — checking
            # Content-Type catches both HTML challenges and gzip/brotli
            # decoding mishaps.
            ctype = (response.headers.get("Content-Type") or "").lower()
            expects_json = "/wp-json/" in url
            looks_like_json = "json" in ctype
            if (
                expects_json
                and not looks_like_json
                and attempt < max_retries
            ):
                body_preview = (response.text or "")[:200].replace("\n", " ")
                logger.warning(
                    f"{method.upper()} {url} -> {status} but Content-Type={ctype!r} "
                    f"(expected JSON); body[:200]={body_preview!r}; "
                    f"retrying in {delays[attempt]:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(delays[attempt])
                continue

            return response

        return response  # type: ignore[return-value]

    def _get_or_create_category(self, name: str, parent_id: Optional[int] = None) -> Optional[int]:
        """Get or create a category with optional parent.

        Automatically handles parent category creation based on CATEGORY_HIERARCHY.

        Args:
            name: Category name
            parent_id: Parent category ID (optional, auto-detected from hierarchy)

        Returns:
            Category ID or None
        """
        try:
            # Check if this category has a defined parent in hierarchy
            parent_name = self.CATEGORY_HIERARCHY.get(name)
            if parent_name and parent_id is None:
                # Recursively ensure parent exists first
                parent_id = self._get_or_create_category(parent_name)
                if parent_id:
                    logger.debug(f"Using parent category '{parent_name}' (ID: {parent_id}) for '{name}'")

            # Search for existing category (with WAF-aware retry)
            response = self._request_with_retry(
                "GET",
                f"{self._api_base}/categories",
                headers=self._get_auth_headers(),
                params={"search": name, "per_page": 100},
                timeout=30,
            )
            response.raise_for_status()
            categories = response.json()

            for cat in categories:
                if cat["name"].lower() == name.lower():
                    # If parent_id specified, verify it matches
                    if parent_id and cat.get("parent") != parent_id:
                        # Update category to have correct parent
                        logger.info(f"Updating category '{name}' to have parent ID {parent_id}")
                        update_response = self._request_with_retry(
                            "POST",
                            f"{self._api_base}/categories/{cat['id']}",
                            headers=self._get_auth_headers(),
                            json={"parent": parent_id},
                            timeout=30,
                        )
                        update_response.raise_for_status()
                    return cat["id"]

            # Create new category with parent if specified
            category_data = {"name": name}
            if parent_id:
                category_data["parent"] = parent_id

            response = self._request_with_retry(
                "POST",
                f"{self._api_base}/categories",
                headers=self._get_auth_headers(),
                json=category_data,
                timeout=30,
            )
            response.raise_for_status()
            new_cat = response.json()
            logger.info(f"Created category '{name}' (ID: {new_cat['id']}, parent: {parent_id or 'none'})")
            return new_cat["id"]

        except Exception as e:
            logger.warning(f"Failed to get/create category '{name}': {e}")
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
                # Search for existing tag (with WAF-aware retry)
                response = self._request_with_retry(
                    "GET",
                    f"{self._api_base}/tags",
                    headers=self._get_auth_headers(),
                    params={"search": keyword},
                    timeout=30,
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
                    response = self._request_with_retry(
                        "POST",
                        f"{self._api_base}/tags",
                        headers=self._get_auth_headers(),
                        json={"name": keyword},
                        timeout=30,
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
        section_images: Optional[dict[str, FetchedImage]] = None,
        skip_hero_image: bool = False,
        original_urls: Optional[dict[str, str]] = None,
        section_original_urls: Optional[dict[str, str]] = None,
    ) -> str:
        """Prepare content with hero image and section-relevant images.

        Inserts a hero image at the top and relevant images after H2 sections
        when section_images are provided.

        Args:
            html: Original HTML content
            images: Images to insert (first one used as hero)
            section_images: Dict mapping H2 text to relevant FetchedImage
            skip_hero_image: If True, skip adding hero image (for tech mode)

        Returns:
            HTML with images inserted
        """
        if not images and not section_images:
            return html

        result = html
        original_urls = original_urls or {}
        section_original_urls = section_original_urls or {}

        # Insert section images after H2s (if provided)
        if section_images:
            for h2_text, img in section_images.items():
                # Find the H2 tag containing this text
                h2_pattern = rf'(<h2[^>]*>.*?{re.escape(h2_text[:30])}.*?</h2>)'
                match = re.search(h2_pattern, result, re.IGNORECASE | re.DOTALL)

                if match:
                    h2_tag = match.group(1)

                    # Check if YouTube thumbnail - use original URL for link extraction
                    original_url = section_original_urls.get(h2_text, img.url)
                    youtube_link = self._extract_youtube_link(original_url)
                    if youtube_link:
                        img_html = f'''
<figure class="wp-block-image aligncenter size-large section-image" style="max-width:700px;margin:20px auto 30px auto;">
    <a href="{youtube_link}" target="_blank" rel="noopener noreferrer" title="Watch on YouTube">
    <img src="{img.url}" alt="{img.alt}" style="width:100%;max-width:700px;height:auto;border-radius:10px;cursor:pointer;"/>
    </a>
    <figcaption style="text-align:center;font-size:0.8em;color:#888;margin-top:8px;">📺 {img.photographer} - <a href="{youtube_link}" target="_blank" rel="noopener noreferrer" style="color:#ff0000;">Watch Video</a></figcaption>
</figure>
'''
                    else:
                        img_html = f'''
<figure class="wp-block-image aligncenter size-large section-image" style="max-width:700px;margin:20px auto 30px auto;">
    <img src="{img.url}" alt="{img.alt}" style="width:100%;max-width:700px;height:auto;border-radius:10px;"/>
    <figcaption style="text-align:center;font-size:0.8em;color:#888;margin-top:8px;">Photo by {img.photographer}</figcaption>
</figure>
'''
                    result = result.replace(h2_tag, h2_tag + img_html, 1)
                    logger.debug(f"Inserted section image for: {h2_text[:40]}...")

        # Add hero image at the very beginning (skip for tech mode)
        if images and not skip_hero_image:
            img = images[0]

            # Check if YouTube thumbnail - use original URL for link extraction
            original_url = original_urls.get(img.url, img.url)
            youtube_link = self._extract_youtube_link(original_url)
            if youtube_link:
                hero_html = f'''
<figure class="wp-block-image aligncenter size-large hero-image" style="max-width:800px;margin:0 auto 30px auto;">
    <a href="{youtube_link}" target="_blank" rel="noopener noreferrer" title="Watch on YouTube">
    <img src="{img.url}" alt="{img.alt}" style="width:100%;max-width:800px;height:auto;border-radius:12px;cursor:pointer;"/>
    </a>
    <figcaption style="text-align:center;font-size:0.85em;color:#888;margin-top:10px;">📺 {img.photographer} - <a href="{youtube_link}" target="_blank" rel="noopener noreferrer" style="color:#ff0000;">Watch Video</a></figcaption>
</figure>
'''
            else:
                hero_html = f'''
<figure class="wp-block-image aligncenter size-large hero-image" style="max-width:800px;margin:0 auto 30px auto;">
    <img src="{img.url}" alt="{img.alt}" style="width:100%;max-width:800px;height:auto;border-radius:12px;"/>
    <figcaption style="text-align:center;font-size:0.85em;color:#888;margin-top:10px;">Photo by {img.photographer}</figcaption>
</figure>
'''
            result = hero_html + result

        return result

    def _extract_youtube_link(self, url: str) -> Optional[str]:
        """Extract YouTube video link from thumbnail URL.

        Args:
            url: Image URL (may be YouTube thumbnail or WordPress uploaded)

        Returns:
            YouTube video URL if detected, None otherwise
        """
        # Check for YouTube thumbnail URL pattern
        # Format: https://img.youtube.com/vi/VIDEO_ID/maxresdefault.jpg
        # Or WordPress uploaded: .../maxresdefault.jpg (originally from YouTube)
        match = re.search(r'/vi/([a-zA-Z0-9_-]{11})/', url)
        if match:
            video_id = match.group(1)
            return f"https://www.youtube.com/watch?v={video_id}"

        # Check for WordPress uploaded YouTube thumbnails (filename pattern)
        # Format: maxresdefault.jpg, hqdefault.jpg, etc.
        if "maxresdefault" in url or "hqdefault" in url or "sddefault" in url:
            # These are likely YouTube thumbnails uploaded to WordPress
            # Try to find video ID in alt text or return None
            return None

        return None

    def _generate_slug(self, title: str, content_type: str = "review") -> str:
        """Generate SEO-friendly slug from title.

        Rules by content type:
        - comparison (vs): {product1}-vs-{product2}-{year}
        - review: {product}-review-{year}
        - guide: {topic}-guide-{year}
        - news: {topic}-{year}
        - list: best-{topic}-{year}

        Args:
            title: Post title
            content_type: Type of content (review, comparison, guide, list, news)

        Returns:
            SEO-optimized slug (max 60 chars)
        """
        import datetime
        year = datetime.datetime.now().year

        # Check for VS comparison pattern FIRST (before cleaning)
        vs_match = re.search(
            r'([A-Za-z0-9]+(?:\s+[A-Za-z0-9]+)?)\s+vs\.?\s+([A-Za-z0-9]+(?:\s+[A-Za-z0-9]+)?)',
            title,
            re.IGNORECASE
        )
        if vs_match:
            product1 = vs_match.group(1).strip().lower().replace(' ', '-')
            product2 = vs_match.group(2).strip().lower().replace(' ', '-')
            return f"{product1}-vs-{product2}-{year}"

        # Clean title: lowercase, remove special chars
        clean = title.lower()
        clean = re.sub(r'[^\w\s-]', '', clean)  # Keep alphanumeric, spaces, hyphens
        clean = re.sub(r'\s+', '-', clean)  # Replace spaces with hyphens

        # Remove common filler words
        filler_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'this', 'that', 'which', 'what', 'how', 'why', 'when', 'where',
            'complete', 'ultimate', 'comprehensive', 'definitive', 'essential',
            'top', 'best', 'worst', 'most', 'all', 'every', 'any',
            'you', 'your', 'our', 'their', 'his', 'her', 'its',
            'make', 'makes', 'made', 'developers', 'developer',
            'mistake', 'mistakes', 'year', 'years',
            'review', 'guide', 'tutorial', 'tips', 'tricks',
        }

        # Remove filler words
        words = clean.split('-')
        words = [w for w in words if w and w not in filler_words and not w.isdigit()]

        # Build slug based on content type
        if content_type == "comparison":
            slug = '-'.join(words[:4]) + f"-comparison-{year}"
        elif content_type == "review":
            slug = '-'.join(words[:3]) + f"-review-{year}"
        elif content_type == "guide":
            slug = '-'.join(words[:3]) + f"-guide-{year}"
        elif content_type == "list":
            slug = "best-" + '-'.join(words[:3]) + f"-{year}"
        elif content_type == "news":
            slug = '-'.join(words[:4]) + f"-{year}"
        else:
            slug = '-'.join(words[:5]) + f"-{year}"

        # Clean up
        slug = re.sub(r'-+', '-', slug)  # Remove double hyphens
        slug = slug.strip('-')

        # Max 60 chars for SEO
        if len(slug) > 60:
            parts = slug.rsplit('-', 1)
            if parts[-1].isdigit():
                year_part = f"-{parts[-1]}"
                main_part = parts[0][:60 - len(year_part)]
                main_part = main_part.rsplit('-', 1)[0]
                slug = main_part + year_part
            else:
                slug = slug[:60].rsplit('-', 1)[0]

        logger.debug(f"Generated slug: {slug} (from: {title[:50]}...)")
        return slug

    def _generate_focus_keyphrase(self, title: str, keywords: list[str]) -> str:
        """Generate focus keyphrase for Yoast SEO.

        Args:
            title: Post title
            keywords: List of keywords

        Returns:
            Focus keyphrase string
        """
        site_name = self._get_site_name()

        if site_name == "BytePulse":
            # Tech mode (English): VS 패턴 추출 또는 키워드 조합
            vs_match = re.search(r'^([A-Za-z0-9]+(?:\s+vs\s+[A-Za-z0-9]+)+)', title, re.IGNORECASE)
            if vs_match:
                return vs_match.group(1).strip()
            # English keywords
            if keywords and len(keywords) >= 2:
                return f"{keywords[0]} {keywords[1]}"
            elif keywords:
                return keywords[0]
        else:
            # General mode (Korean): 제목에서 핵심 키워드 추출
            # 한국어 제목에서 주요 명사구 추출 (첫 2-3 단어)
            # 예: "개발자 생산성 2배 올린 리눅스 데스크톱" -> "리눅스 데스크톱"
            import re as regex
            # 한글 단어 추출
            korean_words = regex.findall(r'[가-힣]+', title)
            if korean_words:
                # 핵심 키워드 2-3개 조합 (짧은 조사 제외)
                key_words = [w for w in korean_words if len(w) >= 2]
                if len(key_words) >= 2:
                    return f"{key_words[0]} {key_words[1]}"
                elif key_words:
                    return key_words[0]

            # 영문 제목 폴백: 한글이 없으면 키워드 조합 사용
            # (해외 트렌드 토픽은 제목이 영문일 수 있음 — 빈 키프레이즈면 Yoast SEO 오류)
            if keywords and len(keywords) >= 2:
                return f"{keywords[0]} {keywords[1]}"
            elif keywords:
                return keywords[0]

            # 최후 폴백: 제목에서 영문 단어 추출
            english_words = [w for w in regex.findall(r'[A-Za-z0-9]+', title) if len(w) >= 2]
            if len(english_words) >= 2:
                return f"{english_words[0]} {english_words[1]}"
            elif english_words:
                return english_words[0]

        return ""

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
                response = self._request_with_retry(
                    "GET",
                    f"{self._api_base}/posts",
                    headers=self._get_auth_headers(),
                    params={
                        "per_page": per_page,
                        "page": page,
                        "status": "any",  # Include drafts and published
                        "_fields": "id,title,slug",  # Only fetch needed fields
                    },
                    retry_statuses=(403, 429, 500, 502, 503, 504),
                    timeout=30,
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
