"""Blog Pipeline module - orchestrates the full automation workflow.

Coordinates trend detection, content generation, image fetching, and publishing.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger


# 요일/시간별 카테고리 스케줄 (수익 우선순위 기반)
# 리뷰(7회) > 건강(3회) > 생산성(2회) > 테크(2회) > 비즈니스(1회)
# 오전: 00:00 UTC (09:00 KST), 오후: 12:00 UTC (21:00 KST)
CATEGORY_SCHEDULE = {
    # (요일, 시간대): 카테고리
    # 요일: 0=월, 1=화, 2=수, 3=목, 4=금, 5=토, 6=일
    # 시간대: "morning" (00:00-11:59 UTC), "evening" (12:00-23:59 UTC)
    (0, "morning"): "리뷰",      # 월 오전
    (0, "evening"): "건강",      # 월 오후
    (1, "morning"): "리뷰",      # 화 오전
    (1, "evening"): "생산성",    # 화 오후
    (2, "morning"): "리뷰",      # 수 오전
    (2, "evening"): "테크",      # 수 오후
    (3, "morning"): "건강",      # 목 오전
    (3, "evening"): "리뷰",      # 목 오후
    (4, "morning"): "생산성",    # 금 오전
    (4, "evening"): "리뷰",      # 금 오후
    (5, "morning"): "테크",      # 토 오전
    (5, "evening"): "리뷰",      # 토 오후
    (6, "morning"): "비즈니스",  # 일 오전
    (6, "evening"): "건강",      # 일 오후
}


def get_scheduled_category() -> Optional[str]:
    """현재 시간 기준 스케줄된 카테고리 반환.

    Returns:
        스케줄된 카테고리명 또는 None
    """
    now = datetime.utcnow()
    weekday = now.weekday()  # 0=월요일
    time_slot = "morning" if now.hour < 12 else "evening"

    category = CATEGORY_SCHEDULE.get((weekday, time_slot))
    if category:
        logger.info(f"Scheduled category: {category} (weekday={weekday}, slot={time_slot})")
    return category

from src.trend_detector import TrendDetector, Topic, TrendConfig
from src.content_generator import ContentGenerator, ContentType, ContentConfig
from src.image_fetcher import ImageFetcher, ImageConfig
from src.wordpress_client import WordPressClient, WPConfig, PostStatus, CreatedPost


# Post registry base directory
POST_REGISTRY_DIR = Path(__file__).parent.parent / "data"


def get_registry_path(mode: str) -> Path:
    """Get the registry file path for a specific mode.

    Args:
        mode: 'general' or 'tech'

    Returns:
        Path to the mode-specific registry file
    """
    return POST_REGISTRY_DIR / f"post_registry_{mode}.json"


@dataclass
class PipelineConfig:
    """Configuration for the blog pipeline.

    Attributes:
        max_posts_per_run: Maximum posts to create per run
        content_type: Type of content to generate
        auto_publish: Whether to publish immediately (vs draft)
        dry_run: If True, don't actually publish
        category: Default category for posts
        mode: Blog mode - 'tech' or 'general' for WordPress site selection
    """

    max_posts_per_run: int = 3
    content_type: ContentType = ContentType.REVIEW
    auto_publish: bool = False
    dry_run: bool = False
    category: Optional[str] = None
    mode: str = "general"  # 'tech' for bytepulse.io, 'general' for trendpulse.blog
    use_llm_topics: bool = True  # Use LLM to analyze and prioritize topics
    use_scheduled_category: bool = True  # 요일/시간별 카테고리 스케줄 사용

    # Sub-configs (optional)
    trend_config: Optional[TrendConfig] = None
    content_config: Optional[ContentConfig] = None
    image_config: Optional[ImageConfig] = None


@dataclass
class PipelineResult:
    """Result of processing a single topic.

    Attributes:
        topic: The topic that was processed
        success: Whether processing succeeded
        post: Created post (if successful)
        error: Error message (if failed)
        duration_seconds: Processing time
    """

    topic: str
    success: bool
    post: Optional[CreatedPost] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "topic": self.topic,
            "success": self.success,
            "post": self.post.to_dict() if self.post else None,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
        }


class BlogPipeline:
    """Orchestrates the complete blog automation pipeline.

    Example:
        >>> pipeline = BlogPipeline()
        >>> results = pipeline.run()
        >>> for result in results:
        ...     if result.success:
        ...         print(f"Created: {result.post.url}")
        ...     else:
        ...         print(f"Failed: {result.error}")
    """

    def __init__(self, config: Optional[PipelineConfig] = None) -> None:
        """Initialize BlogPipeline.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or PipelineConfig()

        # Initialize components
        self.trend_detector = TrendDetector(config=self.config.trend_config)
        self.content_generator = ContentGenerator(config=self.config.content_config)
        self.image_fetcher = ImageFetcher(config=self.config.image_config)

        # Only initialize WordPress client if not in dry-run mode
        if not self.config.dry_run:
            wp_config = WPConfig.from_env(mode=self.config.mode)
            self.wp_client = WordPressClient(config=wp_config)
        else:
            self.wp_client = None  # type: ignore

        logger.info("BlogPipeline initialized")

    def run(self) -> list[PipelineResult]:
        """Run the complete pipeline.

        Returns:
            List of PipelineResult objects
        """
        logger.info("Starting pipeline run...")
        results: list[PipelineResult] = []

        # Step 1: Collect trending topics (optionally with LLM analysis)
        if self.config.use_llm_topics:
            logger.info("Using LLM-based topic analysis...")
            topics = self.trend_detector.collect_with_llm(use_llm=True)
        else:
            topics = self.trend_detector.collect()

        if not topics:
            logger.warning("No trending topics found")
            return results

        logger.info(f"Found {len(topics)} topics to process")

        # 스케줄된 카테고리 사용 (general 모드에서만, CLI에서 명시적으로 지정하지 않은 경우)
        # tech 모드(bytepulse.io)는 한국어 카테고리 스케줄 사용 안함
        target_category = self.config.category
        if not target_category and self.config.use_scheduled_category and self.config.mode == "general":
            target_category = get_scheduled_category()
            if target_category:
                logger.info(f"Using scheduled category: {target_category}")

        # Filter by category if specified
        if target_category:
            filtered_topics = [
                t for t in topics
                if t.category == target_category
            ]
            if filtered_topics:
                logger.info(f"Filtered to {len(filtered_topics)} topics matching category: {target_category}")
                topics = filtered_topics
            else:
                logger.warning(f"No topics match category '{target_category}', using all topics")

        # Filter out duplicate topics using local registry
        topics = self._filter_duplicates(topics)

        if not topics:
            logger.warning("No topics remaining after duplicate filtering")
            return results

        # Limit to max_posts_per_run
        topics_to_process = topics[: self.config.max_posts_per_run]

        # Step 2: Process each topic
        for topic in topics_to_process:
            result = self._process_topic(topic)
            results.append(result)

        # Summary
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        logger.info(f"Pipeline complete: {successful} successful, {failed} failed")

        return results

    def _process_topic(self, topic: Topic) -> PipelineResult:
        """Process a single topic through the pipeline.

        Args:
            topic: Topic to process

        Returns:
            PipelineResult
        """
        start_time = datetime.now()
        logger.info(f"Processing topic: {topic.topic}")

        try:
            # Category priority: CLI flag > LLM analysis > auto-detect
            category = self.config.category
            if not category and topic.category:
                # Use LLM-analyzed category (more accurate)
                category = topic.category
                logger.info(f"Using LLM-analyzed category: {category}")
            elif not category:
                # Fallback to auto-detect
                category = TrendDetector.detect_category(
                    topic=topic.topic,
                    mode=self.config.mode,
                )
                logger.info(f"Auto-detected category: {category}")

            # Generate content with category context
            content = self.content_generator.generate(
                topic=topic.topic,
                keywords=topic.keywords,
                content_type=self.config.content_type,
                category=category,
                mode=self.config.mode,
            )

            logger.debug(f"Generated content: {content.word_count} words")

            # Fetch hero image - pass topic as fallback for Korean topics
            images = self.image_fetcher.fetch(
                keywords=topic.keywords,
                topic=topic.topic,
            )
            logger.debug(f"Fetched {len(images)} hero images")

            # Fetch section-relevant images for H2s (general mode only)
            # Tech mode uses tables/charts/diagrams instead of stock photos
            section_images = {}
            if self.config.mode != "tech":
                section_images = self._fetch_section_images(
                    html=content.html,
                    exclude_urls={img.url for img in images},
                )
                logger.debug(f"Fetched {len(section_images)} section images")
            else:
                logger.debug("Tech mode: skipping section images (using visual elements instead)")

            # Create post (or simulate in dry run)
            if self.config.dry_run:
                logger.info("[DRY RUN] Would create post - skipping actual publish")
                post = CreatedPost(
                    id=0,
                    url="[DRY RUN]",
                    title=content.title,
                    status=PostStatus.DRAFT,
                )
            else:
                status = PostStatus.PUBLISH if self.config.auto_publish else PostStatus.DRAFT
                # Tech mode: skip hero image (TL;DR summary comes first)
                skip_hero = self.config.mode == "tech"
                post = self.wp_client.create_post(
                    content=content,
                    images=images,
                    status=status,
                    category=category,
                    section_images=section_images,
                    skip_hero_image=skip_hero,
                )

            duration = (datetime.now() - start_time).total_seconds()

            # Save to local registry for duplicate detection
            self._save_to_registry(
                topic=topic.topic,
                title=content.title,
                keywords=topic.keywords,
                category=category or "",
            )

            return PipelineResult(
                topic=topic.topic,
                success=True,
                post=post,
                duration_seconds=duration,
            )

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Failed to process topic '{topic.topic}': {e}")

            return PipelineResult(
                topic=topic.topic,
                success=False,
                error=str(e),
                duration_seconds=duration,
            )

    def run_single(
        self,
        topic: str,
        keywords: Optional[list[str]] = None,
    ) -> PipelineResult:
        """Run pipeline for a single manually-specified topic.

        Args:
            topic: Topic to write about
            keywords: Optional keywords (auto-extracted if not provided)

        Returns:
            PipelineResult
        """
        from src.trend_detector import TrendSource

        # Check for duplicates first
        if self._is_duplicate(topic):
            logger.warning(f"Skipping duplicate topic: {topic}")
            return PipelineResult(
                topic=topic,
                success=False,
                error="Duplicate topic - already exists in registry",
            )

        # Create a Topic object
        if keywords is None:
            keywords = self.trend_detector._extract_keywords(topic)

        topic_obj = Topic(
            topic=topic,
            keywords=keywords,
            source=TrendSource.HACKER_NEWS,  # Placeholder
            score=100,  # Manual topics get max score
            suggested_title=self.trend_detector._generate_title(topic, keywords),
        )

        return self._process_topic(topic_obj)

    def _is_duplicate(self, topic: str) -> bool:
        """Check if a topic is duplicate of existing posts.

        Args:
            topic: Topic string to check

        Returns:
            True if duplicate, False otherwise
        """
        mode_posts = self._load_post_registry()

        if not mode_posts:
            return False

        topic_words = set(self._extract_keywords(topic))
        if not topic_words:
            return False

        # 핵심 식별자 추출 (토픽에서 고유명사/브랜드명)
        # 예: "2026 카타르 항공 승무원" → "카타르"
        topic_identifier = self._extract_identifier(topic)

        for post in mode_posts:
            existing_text = post.get("title", "") + " " + post.get("topic", "")
            existing_keywords = set(self._extract_keywords(existing_text))

            # 저장된 identifier 사용, 없으면 추출
            existing_identifier = post.get("identifier") or self._extract_identifier(existing_text)

            if not existing_keywords:
                continue

            # 핵심 식별자가 다르면 중복 아님 (예: 카타르 vs 싱가포르)
            if topic_identifier and existing_identifier:
                if topic_identifier != existing_identifier:
                    continue  # 다른 시리즈이므로 스킵

            # Calculate Jaccard similarity
            intersection = topic_words & existing_keywords
            union = topic_words | existing_keywords

            if union:
                similarity = len(intersection) / len(union)

                # Jaccard 유사도 50% 이상 (더 엄격하게)
                if similarity >= 0.50:
                    logger.warning(
                        f"Duplicate detected: '{topic}' similar to '{post.get('title')}' "
                        f"(similarity: {similarity:.2f})"
                    )
                    return True

        return False

    def _extract_identifier(self, text: str) -> Optional[str]:
        """Extract core identifier (brand/company name) from text.

        For tech mode: extracts full VS comparison pattern (e.g., "cursor vs github copilot")
        For general mode: extracts first unique Korean word (e.g., "카타르")

        Args:
            text: Text to extract identifier from

        Returns:
            Identifier string or None
        """
        import re
        import regex

        # Tech 모드: VS 비교 패턴 전체 추출
        # "Cursor vs GitHub Copilot 2026: Which AI Wins" → "cursor vs github copilot"
        # "Vercel vs Netlify Free Tier Limits 2026" → "vercel vs netlify free tier limits"
        vs_match = re.search(
            r'^([A-Za-z0-9_!]+(?:\s+vs\s+[A-Za-z0-9_!]+)+(?:\s+[A-Za-z]+)*?)(?:\s+\d{4}|\s*:|\s*-|$)',
            text,
            re.IGNORECASE
        )
        if vs_match:
            vs_pattern = vs_match.group(1).strip().lower()
            # 불필요한 접미사 제거 (for, which, the 등)
            vs_pattern = re.sub(r'\s+(for|which|the|in|on|at|to|a|an)\s*$', '', vs_pattern, flags=re.IGNORECASE)
            return vs_pattern

        # 일반적인 단어 (식별자에서 제외)
        common_words = {
            # 취업 관련
            "승무원", "채용", "면접", "합격", "스펙", "시험", "일정", "총정리",
            "취업", "입사", "공채", "경력", "신입", "기출", "문제", "후기",
            "자소서", "자기소개서", "연봉", "복지", "정규직", "인턴",
            # 일반
            "항공", "회사", "기업", "그룹", "전자", "물산", "생명", "화재",
            "가이드", "방법", "전략", "비법", "노하우", "팁",
            # 년도
            "2024", "2025", "2026", "2027",
        }

        # 한글 고유명사 추출 (일반 단어 제외)
        korean_words = regex.findall(r'[가-힣]{2,}', text)
        for word in korean_words:
            if word not in common_words:
                return word.lower()

        # 영문 브랜드/회사명 추출 (VS 패턴이 없는 경우)
        english_words = re.findall(r'[A-Za-z]{2,}', text)
        for word in english_words:
            word_lower = word.lower()
            if word_lower not in {"the", "and", "for", "top", "best", "vs", "how", "what", "why"}:
                return word_lower

        return None

    def _filter_duplicates(self, topics: list[Topic]) -> list[Topic]:
        """Filter out topics that are similar to previously published posts.

        Uses identifier-based duplicate detection for accuracy.

        Args:
            topics: List of topics to filter

        Returns:
            Filtered list of topics
        """
        filtered_topics = []

        for topic in topics:
            if self._is_duplicate(topic.topic):
                continue
            filtered_topics.append(topic)

        skipped_count = len(topics) - len(filtered_topics)
        if skipped_count > 0:
            logger.info(f"Filtered out {skipped_count} duplicate topics, {len(filtered_topics)} remaining")

        return filtered_topics

    def _load_post_registry(self) -> list:
        """Load the post registry from mode-specific JSON file.

        Returns:
            List of posts for the current mode
        """
        registry_path = get_registry_path(self.config.mode)
        if not registry_path.exists():
            return []

        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load post registry: {e}")
            return []

    def _save_to_registry(self, topic: str, title: str, keywords: list[str], category: str) -> None:
        """Save a published post to the mode-specific registry.

        Args:
            topic: Original topic
            title: Published post title
            keywords: Keywords used
            category: Post category
        """
        registry_path = get_registry_path(self.config.mode)

        # Ensure directory exists
        registry_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing registry (list format)
        posts = self._load_post_registry()

        # Extract identifier for duplicate detection
        identifier = self._extract_identifier(topic) or self._extract_identifier(title)

        # Add new post entry
        posts.append({
            "topic": topic,
            "title": title,
            "keywords": keywords,
            "category": category,
            "identifier": identifier,
            "created_at": datetime.now().isoformat(),
        })

        # Save registry
        try:
            with open(registry_path, "w", encoding="utf-8") as f:
                json.dump(posts, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved post to registry ({self.config.mode}): {title}")
        except Exception as e:
            logger.error(f"Failed to save post registry: {e}")

    def _fetch_section_images(
        self,
        html: str,
        exclude_urls: set[str],
        max_sections: int = 4,
    ) -> dict[str, "FetchedImage"]:
        """Fetch relevant images for H2 sections.

        Extracts H2 texts, creates search queries, and fetches matching images.

        Args:
            html: Generated HTML content
            exclude_urls: URLs to exclude (already used)
            max_sections: Max number of section images to fetch

        Returns:
            Dict mapping H2 text to FetchedImage
        """
        from src.image_fetcher import FetchedImage

        section_images: dict[str, FetchedImage] = {}

        # Extract H2 texts from HTML
        h2_pattern = r'<h2[^>]*>(.*?)</h2>'
        h2_matches = re.findall(h2_pattern, html, re.IGNORECASE | re.DOTALL)

        if not h2_matches:
            return section_images

        # Clean HTML tags from H2 text
        h2_texts = []
        for match in h2_matches[:max_sections]:
            clean_text = re.sub(r'<[^>]+>', '', match).strip()
            if clean_text and len(clean_text) > 3:
                h2_texts.append(clean_text)

        logger.info(f"Found {len(h2_texts)} H2 sections for image matching")

        # Fetch image for each H2
        for h2_text in h2_texts:
            # Create search query from H2 text
            query = self._h2_to_search_query(h2_text)
            if not query:
                continue

            logger.debug(f"Searching image for H2: '{h2_text[:40]}...' -> query: '{query}'")

            img = self.image_fetcher.fetch_single(query, exclude_urls)
            if img:
                section_images[h2_text] = img
                exclude_urls.add(img.url)
                logger.debug(f"Found image for section: {h2_text[:30]}...")

        return section_images

    def _h2_to_search_query(self, h2_text: str) -> str:
        """Convert H2 text to image search query.

        Extracts meaningful English keywords for image search.
        Prioritizes product/tool names for relevant stock photos.

        Args:
            h2_text: H2 section title

        Returns:
            Search query string
        """
        h2_lower = h2_text.lower()

        # Product/tool name mappings (prioritize these for relevant images)
        product_image_queries = {
            'linux': 'linux penguin operating system terminal',
            'windows': 'windows computer desktop microsoft',
            'macos': 'macbook apple computer',
            'docker': 'container ship cargo technology',
            'kubernetes': 'container orchestration cloud',
            'node': 'nodejs javascript programming',
            'python': 'python programming code',
            'react': 'react javascript web development',
            'cursor': 'code editor programming IDE',
            'copilot': 'AI coding assistant programming',
            'github': 'code repository developer',
            'notion': 'productivity workspace organization',
            'obsidian': 'note taking knowledge graph',
            'linear': 'project management agile board',
            'jira': 'project management scrum board',
            'asana': 'task management teamwork',
            'figma': 'design interface UI UX',
            'vscode': 'code editor programming IDE',
            'vim': 'terminal code editor programming',
        }

        # Check for product names first
        found_products = []
        for product, query in product_image_queries.items():
            if product in h2_lower:
                found_products.append(query)

        # Section type mappings (visual context)
        section_mappings = {
            'pricing': 'money finance pricing business chart',
            'price': 'money dollar cost finance',
            'cost': 'budget money calculator finance',
            'speed': 'speedometer fast performance race',
            'performance': 'chart graph analytics dashboard',
            'features': 'checklist features software interface',
            'comparison': 'versus compare side by side chart',
            'compare': 'versus compare balance scale',
            'quick comparison': 'comparison chart infographic data',
            'winner': 'trophy gold medal success champion',
            'verdict': 'gavel decision judge choice',
            'conclusion': 'finish line goal checkered flag',
            'developer': 'programmer coding laptop developer',
            'experience': 'user interface UX design screen',
            'workflow': 'flowchart process workflow diagram',
            'migration': 'moving transfer data arrow migration',
            'guide': 'roadmap guide compass direction',
            'setup': 'installation setup configuration gear',
            'install': 'download installation setup arrow',
            'terminal': 'terminal command line code black',
            'shell': 'terminal bash command line',
            'package': 'package box delivery software',
            'git': 'version control branch merge code',
            'cloud': 'cloud computing server network',
            'devops': 'automation deployment pipeline CI CD',
            'mistake': 'warning error alert caution',
            'action': 'action step checklist todo',
            'key features': 'key unlock features important',
        }

        # Check section type
        section_query = ''
        for section_key, query in section_mappings.items():
            if section_key in h2_lower:
                section_query = query
                break

        # Build final query
        if found_products and section_query:
            # Combine product context with section type
            # e.g., "linux terminal" + "comparison chart"
            return f"{found_products[0].split()[0]} {section_query}"
        elif found_products:
            # Use product-specific query
            return found_products[0]
        elif section_query:
            return section_query

        # Fallback: extract English words
        english_words = re.findall(r'[A-Za-z][A-Za-z0-9+#.]*', h2_text)
        skip_words = {
            'vs', 'and', 'or', 'the', 'for', 'with', 'how', 'what', 'why',
            'which', 'best', 'top', 'in', 'on', 'to', 'is', 'are', 'our',
            'your', 'their', 'it', 'do', 'does', 'can', 'will', 'should',
            'TL', 'DR', 'FAQ', 'TLDR', 'Section', 'Quick', 'Final',
        }
        keywords = [w for w in english_words if w.lower() not in skip_words and len(w) > 2]

        if keywords:
            return ' '.join(keywords[:3]) + ' technology'

        return ''

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
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
