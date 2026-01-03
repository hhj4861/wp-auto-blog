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


# Post registry file path
POST_REGISTRY_PATH = Path(__file__).parent.parent / "data" / "post_registry.json"


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

        # 스케줄된 카테고리 사용 (CLI에서 명시적으로 지정하지 않은 경우)
        target_category = self.config.category
        if not target_category and self.config.use_scheduled_category:
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
            )

            logger.debug(f"Generated content: {content.word_count} words")

            # Fetch images - pass topic as fallback for Korean topics
            images = self.image_fetcher.fetch(
                keywords=topic.keywords,
                topic=topic.topic,
            )
            logger.debug(f"Fetched {len(images)} images")

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
                post = self.wp_client.create_post(
                    content=content,
                    images=images,
                    status=status,
                    category=category,
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

    def _filter_duplicates(self, topics: list[Topic]) -> list[Topic]:
        """Filter out topics that are similar to previously published posts.

        Uses local JSON registry instead of WordPress API for efficiency.

        Args:
            topics: List of topics to filter

        Returns:
            Filtered list of topics
        """
        # Load existing posts from local registry
        registry = self._load_post_registry()
        mode_posts = registry.get(self.config.mode, [])

        if not mode_posts:
            logger.info(f"No existing posts in registry for mode '{self.config.mode}', skipping duplicate check")
            return topics

        logger.info(f"Checking against {len(mode_posts)} existing posts in registry")

        # Extract keywords from existing posts
        existing_keywords_list = []
        for post in mode_posts:
            keywords = self._extract_keywords(post.get("title", "") + " " + post.get("topic", ""))
            existing_keywords_list.append({
                "title": post.get("title", ""),
                "topic": post.get("topic", ""),
                "keywords": set(keywords),
            })

        filtered_topics = []
        for topic in topics:
            topic_words = set(self._extract_keywords(topic.topic))

            is_duplicate = False
            for existing in existing_keywords_list:
                if not topic_words or not existing["keywords"]:
                    continue

                # Calculate Jaccard similarity
                intersection = topic_words & existing["keywords"]
                union = topic_words | existing["keywords"]

                if union:
                    similarity = len(intersection) / len(union)
                    if similarity >= 0.3:  # 30% similarity threshold
                        logger.warning(
                            f"Skipping duplicate topic: '{topic.topic}' "
                            f"(similar to '{existing['title']}', similarity: {similarity:.2f})"
                        )
                        is_duplicate = True
                        break

            if not is_duplicate:
                filtered_topics.append(topic)

        skipped_count = len(topics) - len(filtered_topics)
        if skipped_count > 0:
            logger.info(f"Filtered out {skipped_count} duplicate topics, {len(filtered_topics)} remaining")

        return filtered_topics

    def _load_post_registry(self) -> dict:
        """Load the post registry from JSON file.

        Returns:
            Dictionary with mode as key and list of posts as value
        """
        if not POST_REGISTRY_PATH.exists():
            return {}

        try:
            with open(POST_REGISTRY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load post registry: {e}")
            return {}

    def _save_to_registry(self, topic: str, title: str, keywords: list[str], category: str) -> None:
        """Save a published post to the local registry.

        Args:
            topic: Original topic
            title: Published post title
            keywords: Keywords used
            category: Post category
        """
        # Ensure directory exists
        POST_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Load existing registry
        registry = self._load_post_registry()

        # Initialize mode list if not exists
        if self.config.mode not in registry:
            registry[self.config.mode] = []

        # Add new post entry
        registry[self.config.mode].append({
            "topic": topic,
            "title": title,
            "keywords": keywords,
            "category": category,
            "created_at": datetime.now().isoformat(),
        })

        # Save registry
        try:
            with open(POST_REGISTRY_PATH, "w", encoding="utf-8") as f:
                json.dump(registry, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved post to registry: {title}")
        except Exception as e:
            logger.error(f"Failed to save post registry: {e}")

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
