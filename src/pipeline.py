"""Blog Pipeline module - orchestrates the full automation workflow.

Coordinates trend detection, content generation, image fetching, and publishing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from loguru import logger

from src.trend_detector import TrendDetector, Topic, TrendConfig
from src.content_generator import ContentGenerator, ContentType, ContentConfig
from src.image_fetcher import ImageFetcher, ImageConfig
from src.wordpress_client import WordPressClient, WPConfig, PostStatus, CreatedPost


@dataclass
class PipelineConfig:
    """Configuration for the blog pipeline.

    Attributes:
        max_posts_per_run: Maximum posts to create per run
        content_type: Type of content to generate
        auto_publish: Whether to publish immediately (vs draft)
        dry_run: If True, don't actually publish
        category: Default category for posts
    """

    max_posts_per_run: int = 3
    content_type: ContentType = ContentType.REVIEW
    auto_publish: bool = False
    dry_run: bool = False
    category: Optional[str] = None

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
        self.wp_client = WordPressClient()

        logger.info("BlogPipeline initialized")

    def run(self) -> list[PipelineResult]:
        """Run the complete pipeline.

        Returns:
            List of PipelineResult objects
        """
        logger.info("Starting pipeline run...")
        results: list[PipelineResult] = []

        # Step 1: Collect trending topics
        topics = self.trend_detector.collect()

        if not topics:
            logger.warning("No trending topics found")
            return results

        logger.info(f"Found {len(topics)} topics to process")

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
            # Generate content
            content = self.content_generator.generate(
                topic=topic.topic,
                keywords=topic.keywords,
                content_type=self.config.content_type,
            )

            logger.debug(f"Generated content: {content.word_count} words")

            # Fetch images
            images = self.image_fetcher.fetch(keywords=topic.keywords)
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
                    category=self.config.category,
                )

            duration = (datetime.now() - start_time).total_seconds()

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
