"""Blog Pipeline module - orchestrates the full automation workflow.

Coordinates trend detection, content generation, image fetching, and publishing.
"""

from __future__ import annotations

import html as html_lib
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

# K-Culture 카테고리 스케줄 (k-pulse.blog)
# K-Pop(4회, 트래픽) > K-Beauty(3회, 수익) > K-Food(3회) > K-Fashion(2회)
KCULTURE_CATEGORY_SCHEDULE = {
    (0, "morning"): "K-Beauty",   # 월 오전
    (0, "evening"): "K-Pop",      # 월 오후
    (1, "morning"): "K-Food",     # 화 오전
    (1, "evening"): "K-Fashion",  # 화 오후
    (2, "morning"): "K-Beauty",   # 수 오전
    (2, "evening"): "K-Pop",      # 수 오후
    (3, "morning"): "K-Food",     # 목 오전
    (3, "evening"): "K-Fashion",  # 목 오후
    (4, "morning"): "K-Beauty",   # 금 오전
    (4, "evening"): "K-Pop",      # 금 오후
    (5, "morning"): "K-Food",     # 토 오전
    (5, "evening"): "K-Pop",      # 토 오후 (주말 트래픽)
    (6, "morning"): "K-Pop",      # 일 오전 (주말 트래픽)
    (6, "evening"): "K-Beauty",   # 일 오후
}


def get_scheduled_category(mode: str = "general") -> Optional[str]:
    """현재 시간 기준 스케줄된 카테고리 반환.

    Args:
        mode: 'general', 'tech', or 'kculture'

    Returns:
        스케줄된 카테고리명 또는 None
    """
    now = datetime.utcnow()
    weekday = now.weekday()  # 0=월요일
    time_slot = "morning" if now.hour < 12 else "evening"

    # mode에 따라 스케줄 선택
    if mode == "kculture":
        schedule = KCULTURE_CATEGORY_SCHEDULE
    else:
        schedule = CATEGORY_SCHEDULE

    category = schedule.get((weekday, time_slot))
    if category:
        logger.info(f"Scheduled category: {category} (mode={mode}, weekday={weekday}, slot={time_slot})")
    return category

from src.trend_detector import TrendDetector, Topic, TrendConfig
from src.content_generator import ContentGenerator, ContentType, ContentConfig
from src.image_fetcher import ImageFetcher, ImageConfig, FetchedImage
from src.indexnow import ping_urls
from src.monetization import (
    add_policy_disclaimers,
    check_quality,
    insert_monetization,
    insert_related_box,
    strip_placeholders,
)
from src.wordpress_client import WordPressClient, WPConfig, PostStatus, CreatedPost

# ImageCrawler for K-Culture product images (Olive Young API, Amazon)
try:
    from src.image_crawler import ImageCrawler, CrawledImage
    IMAGE_CRAWLER_AVAILABLE = True
except ImportError:
    IMAGE_CRAWLER_AVAILABLE = False
    ImageCrawler = None
    CrawledImage = None

# YouTubeFetcher for K-Pop and K-Fashion thumbnails
try:
    from src.youtube_fetcher import YouTubeFetcher, YouTubeVideo
    YOUTUBE_FETCHER_AVAILABLE = True
except ImportError:
    YOUTUBE_FETCHER_AVAILABLE = False
    YouTubeFetcher = None
    YouTubeVideo = None


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


def _normalize_title(title: str) -> str:
    """비교/표시용 제목 정규화: 태그 제거, HTML 엔티티 복원, 인용부호 통일.

    WP의 title.rendered는 텍스처라이즈되어(' → &#8217; 등) 원본 제목과
    문자열이 달라지므로, 양쪽을 같은 형태로 맞춰야 비교가 가능하다.
    """
    text = html_lib.unescape(re.sub(r"<[^>]+>", "", title or ""))
    for src, dst in (("‘", "'"), ("’", "'"), ("“", '"'),
                     ("”", '"'), (" ", " ")):
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text).strip()


def rank_related_posts(
    posts: list[dict], keywords: list[str], count: int = 3
) -> list[dict]:
    """제목/슬러그의 키워드 겹침 수로 관련도 순 정렬해 상위 count개 반환.

    키워드는 단어 경계로 매칭한다('ai'가 'chairs'에 오탐되지 않도록).
    동점(겹침 없음 포함)은 입력 순서(최신순)를 유지한다.
    """
    patterns = [
        re.compile(rf"(?<![a-z0-9]){re.escape(k.strip().lower())}(?![a-z0-9])")
        for k in (keywords or [])
        if k and k.strip()
    ]

    def score(post: dict) -> int:
        text = f"{post.get('title', '')} {post.get('slug', '')}".lower()
        return sum(1 for p in patterns if p.search(text))

    ranked = sorted(posts, key=score, reverse=True)  # 안정 정렬 → 동점은 최신순
    return ranked[:count]


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

        # Auto-set language based on mode if content_config not provided
        content_config = self.config.content_config
        if content_config is None:
            from src.content_generator import ContentConfig
            # tech/kculture = English, general = Korean
            language = "ko" if self.config.mode == "general" else "en"
            content_config = ContentConfig(language=language)
            logger.info(f"Auto-set content language: {language} (mode: {self.config.mode})")

        # Auto-set trend mode if trend_config not provided
        trend_config = self.config.trend_config
        if trend_config is None:
            from src.trend_detector import TrendConfig, TrendMode
            # Map mode string to TrendMode enum
            mode_to_trend = {
                "tech": TrendMode.TECH,
                "general": TrendMode.GENERAL,
                "kculture": TrendMode.KCULTURE,
            }
            trend_mode = mode_to_trend.get(self.config.mode, TrendMode.GENERAL)
            trend_config = TrendConfig(mode=trend_mode)
            logger.info(f"Auto-set trend mode: {trend_mode.value}")

        # Initialize components
        self.trend_detector = TrendDetector(config=trend_config)
        self.content_generator = ContentGenerator(config=content_config)
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

        # 스케줄된 카테고리 사용 (general/kculture 모드에서, CLI에서 명시적으로 지정하지 않은 경우)
        # tech 모드(bytepulse.io)는 카테고리 스케줄 사용 안함
        target_category = self.config.category
        if not target_category and self.config.use_scheduled_category and self.config.mode in ("general", "kculture"):
            target_category = get_scheduled_category(mode=self.config.mode)
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

            # Fetch hero image
            # For K-Culture categories, use appropriate image sources
            images = []
            if self.config.mode == "kculture":
                if category == "K-Beauty" and IMAGE_CRAWLER_AVAILABLE:
                    # Olive Young for K-Beauty products
                    images = self._fetch_kbeauty_product_image(topic.topic, topic.keywords)
                    if images:
                        logger.info(f"Fetched K-Beauty image from Olive Young: {images[0].alt[:50]}")
                elif category == "K-Food" and IMAGE_CRAWLER_AVAILABLE:
                    # Amazon for K-Food products (ramen, snacks, etc.)
                    images = self._fetch_kfood_product_image(topic.topic, topic.keywords)
                    if images:
                        logger.info(f"Fetched K-Food image from Amazon: {images[0].alt[:50]}")
                elif category == "K-Pop" and YOUTUBE_FETCHER_AVAILABLE:
                    # YouTube thumbnails for K-Pop (copyright safe)
                    images = self._fetch_youtube_hero_image(topic.topic, category)
                    if images:
                        logger.info(f"Fetched K-Pop image from YouTube: {images[0].alt[:50]}")
                elif category == "K-Fashion" and YOUTUBE_FETCHER_AVAILABLE:
                    # YouTube thumbnails for K-Fashion
                    images = self._fetch_youtube_hero_image(topic.topic, category)
                    if images:
                        logger.info(f"Fetched K-Fashion image from YouTube: {images[0].alt[:50]}")

            # Fall back to Unsplash/Pexels if no image found
            if not images:
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
                    category=category,
                    topic=topic.topic,
                )
                logger.debug(f"Fetched {len(section_images)} section images")
            else:
                logger.debug("Tech mode: skipping section images (using visual elements instead)")

            # 수익화 레이어 (general/trendpulse 전용):
            # 인아티클 광고 + 공식 사이트 CTA + 관련 글 내부 링크 박스
            if self.config.mode == "general":
                content.html = strip_placeholders(content.html)
                content.html = add_policy_disclaimers(
                    content.html, category=category or "", topic=topic.topic)
                content.html = insert_monetization(
                    content.html,
                    official_link=getattr(content, "official_link", ""),
                    related_posts=self._get_related_posts(
                        exclude_title=content.title, keywords=topic.keywords
                    ),
                )
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

                # 발행 전 품질 게이트: 결함 검출 시 자동 발행을 취소하고 draft로 강등
                gate_issues = check_quality(
                    title=content.title,
                    html=content.html,
                    focus_keyphrase=content.focus_keyphrase,
                    meta_description=content.meta_description,
                    require_korean=(self.config.mode == "general"),
                )
                if gate_issues:
                    logger.warning(f"품질 게이트 실패 {len(gate_issues)}건: {gate_issues}")
                    if status == PostStatus.PUBLISH:
                        logger.warning("자동 발행 취소 → draft로 저장 (수동 검토 필요)")
                        status = PostStatus.DRAFT
                else:
                    logger.info("품질 게이트 통과")

                # tech/kculture(bytepulse): 관련 글 내부 링크 박스 삽입
                # (색인 선택률·체류시간 개선 — GSC '크롤링됨-미색인' 대응)
                # 게이트가 생성 본문 자체를 평가하도록 게이트 이후에 삽입한다
                if self.config.mode != "general":
                    related = self._get_related_posts(
                        exclude_title=content.title, keywords=topic.keywords
                    )
                    if related:
                        content.html = insert_related_box(content.html, related)

                # Tech mode: skip hero image (TL;DR summary comes first)
                skip_hero = self.config.mode == "tech"
                post = self.wp_client.create_post(
                    content=content,
                    images=images,
                    status=status,
                    category=category,
                    section_images=section_images,
                    skip_hero_image=skip_hero,
                    content_type=self.config.content_type.value,
                )

                # 발행 즉시 IndexNow 핑 (Bing·Naver 등 참여 엔진 색인 가속)
                if (self.config.mode == "general" and status == PostStatus.PUBLISH
                        and post.url):
                    ping_urls([post.url])

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

    def _get_related_posts(
        self,
        exclude_title: str = "",
        count: int = 3,
        keywords: Optional[list[str]] = None,
    ) -> list[dict]:
        """내부 링크 박스용 관련 글 목록 (모드별 언어 필터 + 키워드 관련도 랭킹).

        general(trendpulse)은 한국어 글만, tech/kculture(bytepulse)는 영어 글을
        포함해 후보를 모은 뒤 topic 키워드 겹침이 큰 순으로 고른다.

        Returns:
            [{"title": ..., "url": ...}] 최대 count개. 실패 시 빈 리스트.
        """
        try:
            recent = self.wp_client.get_recent_posts(count=30, status="publish")
        except Exception as e:
            logger.warning(f"관련 글 조회 실패: {e}")
            return []
        base = self.wp_client.config.url.rstrip("/")
        exclude_normalized = _normalize_title(exclude_title)
        candidates = []
        for p in recent:
            title = _normalize_title(p.get("title") or "")
            if not title or title == exclude_normalized:
                continue
            if self.config.mode == "general" and not re.search(r"[가-힣]", title):
                continue
            candidates.append(
                {"title": title, "slug": p.get("slug", ""), "url": f"{base}/{p['slug']}/"}
            )
        ranked = rank_related_posts(candidates, keywords or [], count=count)
        return [{"title": c["title"], "url": c["url"]} for c in ranked]

    def run_single(
        self,
        topic: str,
        keywords: Optional[list[str]] = None,
        category: Optional[str] = None,
    ) -> PipelineResult:
        """Run pipeline for a single manually-specified topic.

        Args:
            topic: Topic to write about
            keywords: Optional keywords (auto-extracted if not provided)
            category: Optional category (큐 항목의 category 전달용)

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
            category=category,
        )

        return self._process_topic(topic_obj)

    def _is_duplicate(self, topic: str) -> bool:
        """Check if a topic is duplicate of existing posts.

        Uses LLM-based dynamic duplicate detection for accuracy.
        Falls back to keyword similarity if LLM is unavailable.

        Args:
            topic: Topic string to check

        Returns:
            True if duplicate, False otherwise
        """
        mode_posts = self._load_post_registry()

        if not mode_posts:
            return False

        # LLM 동적 중복 체크 시도
        llm_result = self._check_duplicate_with_llm(topic, mode_posts)
        if llm_result is not None:
            return llm_result

        # LLM 실패 시 키워드 기반 fallback
        logger.info("LLM duplicate check unavailable, using keyword fallback")
        return self._check_duplicate_keywords(topic, mode_posts)

    def _check_duplicate_with_llm(self, topic: str, existing_posts: list) -> Optional[bool]:
        """Use LLM to check if topic is duplicate of existing posts.

        Args:
            topic: New topic to check
            existing_posts: List of existing post dicts

        Returns:
            True if duplicate, False if not, None if LLM unavailable
        """
        try:
            from claude_agent_sdk import query as claude_agent_query, ClaudeAgentOptions
            import asyncio
        except ImportError:
            logger.debug("Claude Agent SDK not available for duplicate check")
            return None

        sdk_options = ClaudeAgentOptions(model="claude-opus-4-8")

        # 기존 포스트 목록 생성 (최근 20개)
        existing_list = "\n".join([
            f"- {p.get('title', p.get('topic', ''))}"
            for p in existing_posts[-20:]
        ])

        prompt = f"""You are a strict duplicate content detector. Check if the NEW TOPIC would create redundant content.

## EXISTING POSTS:
{existing_list}

## NEW TOPIC:
"{topic}"

## DUPLICATE Detection Rules (BE STRICT!)

### Rule 1: Same Core Subject = DUPLICATE
If the main subject/product is the same and the content would overlap significantly:
- "Claude Code 사용법" ≈ "Claude Code 활용 가이드" ≈ "Claude Code 시작하기" → DUPLICATE
- "CES 2026 하이라이트" ≈ "CES 2026 핵심 정리" ≈ "CES 2026 총정리" → DUPLICATE
- "젊음 유지하는 방법" ≈ "젊게 사는 비결" ≈ "노화 방지 습관" → DUPLICATE

### Rule 2: VS Comparison = Check Core Tools
- "Windows vs Linux" = "Windows 11 vs Linux" = "Linux vs Windows" → DUPLICATE
- Title style ("Shocking Truth" vs "Guide") doesn't matter

### Rule 3: Title Variations = Still DUPLICATE
These title patterns are just rewordings of the same content:
- "X 사용법" ≈ "X 활용법" ≈ "X 가이드" ≈ "X 완벽 가이드" → DUPLICATE
- "X 추천" ≈ "X TOP 5" ≈ "X 베스트" → DUPLICATE
- "X 팁" ≈ "X 노하우" ≈ "X 비법" → DUPLICATE

### Rule 4: Different Entity = NOT DUPLICATE (CRITICAL EXCEPTION)
**Same template + different company/airline/brand/person = NOT_DUPLICATE.**
Each entity has its own facts (salary, hiring criteria, interview questions, culture).
A reader searching "ANA 승무원 채용"은 절대 "JAL 승무원 채용" 글로 만족하지 않는다.

- "2026 진에어 승무원 채용 합격 스펙" vs "2026 티웨이항공 승무원 채용 합격 스펙"
  → **NOT_DUPLICATE** (다른 항공사 = 다른 채용 정보)
- "삼성전자 신입 공채" vs "네이버 신입 공채" → **NOT_DUPLICATE** (다른 기업)
- "에미레이트 승무원 면접" vs "카타르항공 승무원 면접" → **NOT_DUPLICATE** (다른 항공사)
- "iPhone 17 리뷰" vs "Galaxy S26 리뷰" → **NOT_DUPLICATE** (다른 제품)
- "재산세 납부 방법" vs "주민세 납부 방법" → **NOT_DUPLICATE** (다른 세목 = 다른 납부기간·대상·감면 기준)
- "근로장려금 신청" vs "자녀장려금 신청" → **NOT_DUPLICATE** (다른 제도)
- "건강보험 환급금 조회" vs "국세 환급금 조회" → **NOT_DUPLICATE** (다른 기관·다른 절차)

⚠️ 세금·지원금·행정 정보 글은 "납부/조회/신청/환급" 같은 동사와 채널(위택스·홈택스·정부24)이
겹치더라도, **세목·제도·기관이 다르면 검색 의도가 완전히 다른 새 글**이다. 채널이 같다는 이유로
DUPLICATE 판정하지 말 것.

⚠️ 단, "에미레이트 승무원 합격 스펙" vs "에미레이트 승무원 합격 노하우"는 같은 항공사 + 같은 주제 → DUPLICATE.
구조가 같아도 **고유 명사(회사·항공사·인물·제품 모델)가 다르면 본문 사실이 달라지므로 새 글**이다.

### When to mark NOT_DUPLICATE:
- Genuinely different aspects of same product (e.g., "설치" vs "고급 기능" vs "트러블슈팅")
- Different products / companies / airlines / brands entirely (see Rule 4)
- Different time periods with significant changes (e.g., "2025 버전" vs "2026 버전" if major update)

## Response:
Answer ONLY "DUPLICATE" or "NOT_DUPLICATE" with brief reason.
"""

        try:
            async def _async_query():
                messages = []
                async for msg in claude_agent_query(prompt=prompt, options=sdk_options):
                    msg_type = type(msg).__name__
                    if msg_type in ('ResultMessage', 'AssistantMessage'):
                        messages.append(msg)
                    # Skip unknown types (rate_limit_event, etc.)

                for msg in messages:
                    if type(msg).__name__ == 'ResultMessage':
                        if hasattr(msg, 'result') and msg.result:
                            return msg.result
                return ""

            result = asyncio.run(_async_query())

            if "DUPLICATE" in result.upper() and "NOT_DUPLICATE" not in result.upper():
                logger.warning(f"LLM detected duplicate: '{topic}' - {result}")
                return True
            elif "NOT_DUPLICATE" in result.upper():
                logger.info(f"LLM approved: '{topic}' - {result}")
                return False
            else:
                logger.warning(f"LLM response unclear: {result}")
                return None

        except Exception as e:
            logger.error(f"LLM duplicate check failed: {e}")
            return None

    def _check_duplicate_keywords(self, topic: str, existing_posts: list) -> bool:
        """Fallback keyword-based duplicate check.

        Args:
            topic: Topic string to check
            existing_posts: List of existing post dicts

        Returns:
            True if duplicate, False otherwise
        """
        topic_words = set(self._extract_keywords(topic))
        if not topic_words:
            return False

        topic_identifier = self._extract_identifier(topic)

        for post in existing_posts:
            existing_text = post.get("title", "") + " " + post.get("topic", "")
            existing_keywords = set(self._extract_keywords(existing_text))
            existing_identifier = post.get("identifier") or self._extract_identifier(existing_text)

            # identifier 일치 체크
            if topic_identifier and existing_identifier:
                if topic_identifier == existing_identifier:
                    logger.warning(
                        f"Duplicate detected (same identifier): '{topic}' matches '{post.get('title')}' "
                        f"(identifier: {topic_identifier})"
                    )
                    return True
                else:
                    continue

            if not existing_keywords:
                continue

            # Jaccard similarity
            intersection = topic_words & existing_keywords
            union = topic_words | existing_keywords

            if union:
                similarity = len(intersection) / len(union)
                if similarity >= 0.50:
                    logger.warning(
                        f"Duplicate detected (keyword similarity): '{topic}' similar to '{post.get('title')}' "
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
            "가이드", "방법", "전략", "비법", "노하우", "팁", "활용", "사용법",
            "신기능", "기능", "완벽", "실전", "유지", "협업", "사례",
            # 기술 관련 일반 단어
            "멀티", "에이전트", "코드", "개발", "프로그래밍",
            # 년도
            "2024", "2025", "2026", "2027",
        }

        # 영문 브랜드/제품명 우선 추출 (Claude, CES, Notion 등)
        # 대문자로 시작하는 영문 단어 찾기
        brand_match = re.search(r'\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)?)\b', text)
        if brand_match:
            brand = brand_match.group(1).lower()
            # 일반적인 영어 단어 제외
            skip_brands = {"the", "how", "what", "why", "which", "top", "best", "new", "review", "guide", "shocking", "mistakes"}
            if brand not in skip_brands:
                return brand

        # 한글 고유명사 추출 (일반 단어 제외)
        korean_words = regex.findall(r'[가-힣]{2,}', text)
        for word in korean_words:
            if word not in common_words:
                return word.lower()

        # 영문 브랜드/회사명 추출 (소문자도 포함)
        english_words = re.findall(r'[A-Za-z]{3,}', text)
        skip_words = {"the", "and", "for", "top", "best", "vs", "how", "what", "why", "which",
                      "review", "guide", "complete", "shocking", "mistakes", "killing", "productivity",
                      "use", "using", "multi", "agent", "collaboration", "feature", "truth"}
        for word in english_words:
            word_lower = word.lower()
            if word_lower not in skip_words:
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

    def _fetch_kbeauty_product_image(
        self,
        topic: str,
        keywords: list[str],
    ) -> list[FetchedImage]:
        """Fetch actual product image from Olive Young API for K-Beauty products.

        Args:
            topic: Topic/product name
            keywords: Keywords from topic

        Returns:
            List with single FetchedImage if found, empty list otherwise
        """
        if not IMAGE_CRAWLER_AVAILABLE or ImageCrawler is None:
            return []

        try:
            crawler = ImageCrawler(use_playwright=False)

            # Try topic first, then keywords
            crawled = crawler.search_oliveyoung(topic)

            if not crawled and keywords:
                # Try with keywords
                search_query = " ".join(keywords[:3])
                crawled = crawler.search_oliveyoung(search_query)

            if crawled and crawled.url:
                # Convert CrawledImage to FetchedImage format
                from src.image_fetcher import ImageSource

                fetched = FetchedImage(
                    url=crawled.url,
                    alt=f"{crawled.product_name} - {crawled.brand}",
                    photographer=f"Olive Young ({crawled.brand})",
                    source=ImageSource.UNSPLASH,  # Use UNSPLASH as placeholder
                    width=800,
                    height=800,
                )
                logger.info(f"Found Olive Young product: {crawled.product_name[:40]}")
                return [fetched]

        except Exception as e:
            logger.warning(f"Failed to fetch K-Beauty product image: {e}")

        return []

    def _fetch_kfood_product_image(
        self,
        topic: str,
        keywords: list[str],
    ) -> list[FetchedImage]:
        """Fetch actual product image from Amazon for K-Food products.

        Args:
            topic: Topic/product name
            keywords: Keywords from topic

        Returns:
            List with single FetchedImage if found, empty list otherwise
        """
        if not IMAGE_CRAWLER_AVAILABLE or ImageCrawler is None:
            return []

        try:
            crawler = ImageCrawler(use_playwright=False)

            # Try topic first
            crawled = crawler.search_amazon_kfood(topic)

            if not crawled and keywords:
                # Try with keywords
                search_query = " ".join(keywords[:3])
                crawled = crawler.search_amazon_kfood(search_query)

            # Fallback to Google Images if Amazon fails
            if not crawled:
                logger.warning(f"Amazon failed for hero, trying Google: {topic}")
                google_results = crawler.search_google_images(topic, max_results=1)
                if google_results:
                    crawled = google_results[0]

            if crawled and crawled.url:
                # Convert CrawledImage to FetchedImage format
                from src.image_fetcher import ImageSource

                fetched = FetchedImage(
                    url=crawled.url,
                    alt=f"{crawled.product_name[:60]}",
                    photographer=f"Amazon ({crawled.brand})",
                    source=ImageSource.PEXELS,  # Use PEXELS as placeholder
                    width=1500,
                    height=1500,
                )
                logger.info(f"Found Amazon K-Food product: {crawled.product_name[:40]}")
                return [fetched]

        except Exception as e:
            logger.warning(f"Failed to fetch K-Food product image: {e}")

        return []

    def _fetch_youtube_hero_image(
        self,
        topic: str,
        category: str,
    ) -> list[FetchedImage]:
        """Fetch hero image from YouTube thumbnail for K-Pop/K-Fashion.

        Args:
            topic: Topic/subject for search
            category: Content category (K-Pop or K-Fashion)

        Returns:
            List with single FetchedImage if found, empty list otherwise
        """
        if not YOUTUBE_FETCHER_AVAILABLE or YouTubeFetcher is None:
            return []

        try:
            from src.image_fetcher import ImageSource

            fetcher = YouTubeFetcher()

            video = None
            if category == "K-Pop":
                # Extract artist/song info from topic
                video = fetcher.search_kpop(artist=topic, content_type="MV")
            elif category == "K-Fashion":
                video = fetcher.search_kfashion(topic=topic, content_type="style")

            if not video:
                # Fallback to general search
                video = fetcher.search(topic)

            if video and video.thumbnail_url:
                fetched = FetchedImage(
                    url=video.thumbnail_url,
                    alt=video.title or f"{category} - {topic}",
                    photographer=f"YouTube ({video.channel})" if video.channel else "YouTube",
                    source=ImageSource.UNSPLASH,  # Placeholder enum
                    width=1280,
                    height=720,
                )
                logger.info(f"Found YouTube thumbnail: {video.title[:50]}...")
                return [fetched]

        except Exception as e:
            logger.warning(f"Failed to fetch YouTube hero image: {e}")

        return []

    def _fetch_section_images(
        self,
        html: str,
        exclude_urls: set[str],
        max_sections: int = 4,
        category: str = "",
        topic: str = "",
    ) -> dict[str, "FetchedImage"]:
        """Fetch relevant images for H2 sections.

        Extracts H2 texts, creates search queries, and fetches matching images.
        For K-Beauty, uses Olive Young product images instead of stock photos.

        Args:
            html: Generated HTML content
            exclude_urls: URLs to exclude (already used)
            max_sections: Max number of section images to fetch
            category: Content category (K-Beauty, K-Food, etc.)
            topic: Original topic for search context

        Returns:
            Dict mapping H2 text to FetchedImage
        """
        from src.image_fetcher import FetchedImage, ImageSource

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

        # For K-Culture categories, use appropriate product image sources
        if self.config.mode == "kculture":
            if category == "K-Beauty" and IMAGE_CRAWLER_AVAILABLE:
                # Olive Young for K-Beauty products
                oy_images = self._fetch_oliveyoung_section_images(
                    h2_texts, exclude_urls, topic
                )
                if oy_images:
                    return oy_images
                logger.info("No Olive Young images found, falling back to Unsplash")

            elif category == "K-Food" and IMAGE_CRAWLER_AVAILABLE:
                # Amazon for K-Food products (ramen, snacks, etc.)
                amazon_images = self._fetch_amazon_kfood_section_images(
                    h2_texts, exclude_urls, topic
                )
                if amazon_images:
                    return amazon_images
                logger.info("No Amazon K-Food images found, falling back to Unsplash")

            elif category in ("K-Pop", "K-Fashion") and YOUTUBE_FETCHER_AVAILABLE:
                # YouTube thumbnails for K-Pop/K-Fashion (copyright safe)
                yt_images = self._fetch_youtube_section_images(
                    h2_texts, exclude_urls, topic, category
                )
                if yt_images:
                    return yt_images
                logger.info(f"No YouTube images found for {category}, falling back to Unsplash")

        # Fetch image for each H2 using Unsplash/Pexels
        for h2_text in h2_texts:
            # Create search query from H2 text
            query = self._h2_to_search_query(h2_text, category=category)
            if not query:
                continue

            logger.debug(f"Searching image for H2: '{h2_text[:40]}...' -> query: '{query}'")

            img = self.image_fetcher.fetch_single(query, exclude_urls)
            if img:
                section_images[h2_text] = img
                exclude_urls.add(img.url)
                logger.debug(f"Found image for section: {h2_text[:30]}...")

        return section_images

    def _fetch_oliveyoung_section_images(
        self,
        h2_texts: list[str],
        exclude_urls: set[str],
        topic: str,
    ) -> dict[str, "FetchedImage"]:
        """Fetch Olive Young product images for H2 sections.

        Uses product detail page to get multiple images of the SAME product.
        This ensures consistency - all section images show the same product
        from different angles/views.

        Args:
            h2_texts: List of H2 section titles
            exclude_urls: URLs to exclude
            topic: Original topic for search

        Returns:
            Dict mapping H2 text to FetchedImage
        """
        from src.image_fetcher import FetchedImage, ImageSource

        section_images: dict[str, FetchedImage] = {}

        try:
            crawler = ImageCrawler(use_playwright=False)

            # Get multiple images from the matched product's detail page
            # This gives us different views/angles of the same product
            detail_images = crawler.search_oliveyoung_with_detail(
                topic, max_images=len(h2_texts) + 2
            )

            if not detail_images:
                logger.warning(f"No Olive Young detail images for sections: {topic}")
                # Fallback to multiple products
                return self._fetch_oliveyoung_section_images_fallback(
                    h2_texts, exclude_urls, topic
                )

            # Filter out already-used URLs (hero image)
            available_images = [
                img for img in detail_images
                if img.url not in exclude_urls
            ]

            if not available_images:
                logger.warning("All detail images already used, trying multiple products")
                return self._fetch_oliveyoung_section_images_fallback(
                    h2_texts, exclude_urls, topic
                )

            # Assign images to sections (one image per section)
            product_name = available_images[0].product_name if available_images else topic
            for i, h2_text in enumerate(h2_texts):
                if i >= len(available_images):
                    break

                img = available_images[i]
                fetched = FetchedImage(
                    url=img.url,
                    alt=f"{img.product_name} - {img.brand}",
                    photographer=f"Olive Young ({img.brand})",
                    source=ImageSource.UNSPLASH,  # Placeholder
                    width=800,
                    height=800,
                )
                section_images[h2_text] = fetched
                exclude_urls.add(img.url)
                logger.info(f"Section '{h2_text[:25]}...' -> {img.product_name[:35]}... (detail)")

            logger.info(f"Fetched {len(section_images)} section images from product detail")

        except Exception as e:
            logger.warning(f"Failed to fetch Olive Young section images: {e}")

        return section_images

    def _fetch_oliveyoung_section_images_fallback(
        self,
        h2_texts: list[str],
        exclude_urls: set[str],
        topic: str,
    ) -> dict[str, "FetchedImage"]:
        """Fallback: Fetch section images from multiple different products.

        Used when product detail images are not available.

        Args:
            h2_texts: List of H2 section titles
            exclude_urls: URLs to exclude
            topic: Original topic for search

        Returns:
            Dict mapping H2 text to FetchedImage
        """
        from src.image_fetcher import FetchedImage, ImageSource

        section_images: dict[str, FetchedImage] = {}

        try:
            crawler = ImageCrawler(use_playwright=False)
            products = crawler.search_oliveyoung_multiple(topic, max_results=len(h2_texts) + 2)

            if not products:
                return section_images

            # Assign different products to each section
            used_urls = set(exclude_urls)
            for h2_text in h2_texts:
                for product in products:
                    if product.url not in used_urls:
                        used_urls.add(product.url)
                        fetched = FetchedImage(
                            url=product.url,
                            alt=f"{product.product_name} - {product.brand}",
                            photographer=f"Olive Young ({product.brand})",
                            source=ImageSource.UNSPLASH,
                            width=800,
                            height=800,
                        )
                        section_images[h2_text] = fetched
                        exclude_urls.add(product.url)
                        logger.info(f"Section '{h2_text[:25]}...' -> {product.product_name[:35]}... (fallback)")
                        break

            logger.info(f"Fetched {len(section_images)} section images (fallback)")

        except Exception as e:
            logger.warning(f"Fallback section images failed: {e}")

        return section_images

    def _fetch_amazon_kfood_section_images(
        self,
        h2_texts: list[str],
        exclude_urls: set[str],
        topic: str,
    ) -> dict[str, "FetchedImage"]:
        """Fetch K-Food product images from Amazon for H2 sections.

        Uses Amazon to find Korean food products like ramen, snacks, etc.

        Args:
            h2_texts: List of H2 section titles
            exclude_urls: URLs to exclude
            topic: Original topic for search

        Returns:
            Dict mapping H2 text to FetchedImage
        """
        from src.image_fetcher import FetchedImage, ImageSource

        section_images: dict[str, FetchedImage] = {}

        try:
            crawler = ImageCrawler(use_playwright=False)

            # Get multiple K-Food products from Amazon
            products = crawler.search_amazon_kfood_multiple(
                topic, max_results=len(h2_texts) + 2
            )

            # Fallback to Google Custom Search if Amazon fails
            if not products:
                logger.warning(f"No Amazon K-Food products, trying Google Images: {topic}")
                products = crawler.search_google_images(
                    topic, max_results=len(h2_texts) + 2
                )

            if not products:
                logger.warning(f"No product images found for sections: {topic}")
                return section_images

            # Filter out already-used URLs (hero image)
            available_products = [
                p for p in products
                if p.url not in exclude_urls
            ]

            if not available_products:
                logger.warning("All Amazon K-Food images already used")
                return section_images

            # Assign images to sections
            used_urls = set(exclude_urls)
            for h2_text in h2_texts:
                for product in available_products:
                    if product.url not in used_urls:
                        used_urls.add(product.url)
                        fetched = FetchedImage(
                            url=product.url,
                            alt=f"{product.product_name[:60]}",
                            photographer=f"Amazon ({product.brand})",
                            source=ImageSource.PEXELS,  # Placeholder enum
                            width=1500,
                            height=1500,
                        )
                        section_images[h2_text] = fetched
                        exclude_urls.add(product.url)
                        logger.info(f"Section '{h2_text[:25]}...' -> Amazon: {product.product_name[:35]}...")
                        break

            logger.info(f"Fetched {len(section_images)} Amazon K-Food section images")

        except Exception as e:
            logger.warning(f"Amazon K-Food section images failed: {e}")

        return section_images

    def _fetch_youtube_section_images(
        self,
        h2_texts: list[str],
        exclude_urls: set[str],
        topic: str,
        category: str,
    ) -> dict[str, "FetchedImage"]:
        """Fetch YouTube thumbnails for H2 sections (K-Pop/K-Fashion).

        Uses YouTube search to find relevant videos for each section.

        Args:
            h2_texts: List of H2 section titles
            exclude_urls: URLs to exclude (already used)
            topic: Original topic for context
            category: Content category (K-Pop or K-Fashion)

        Returns:
            Dict mapping H2 text to FetchedImage
        """
        from src.image_fetcher import FetchedImage, ImageSource

        section_images: dict[str, FetchedImage] = {}

        if not YOUTUBE_FETCHER_AVAILABLE or YouTubeFetcher is None:
            return section_images

        try:
            fetcher = YouTubeFetcher()
            used_video_ids: set[str] = set()

            # Extract video IDs from exclude_urls that are YouTube thumbnails
            for url in exclude_urls:
                if "img.youtube.com" in url:
                    # Extract video ID from thumbnail URL
                    import re
                    match = re.search(r'/vi/([^/]+)/', url)
                    if match:
                        used_video_ids.add(match.group(1))

            for h2_text in h2_texts:
                # Search YouTube for section-relevant video
                video = fetcher.search_for_section(
                    section_title=h2_text,
                    category=category,
                    exclude_ids=used_video_ids,
                    topic=topic,  # Pass topic for artist context
                )

                if video and video.thumbnail_url and video.video_id not in used_video_ids:
                    used_video_ids.add(video.video_id)
                    fetched = FetchedImage(
                        url=video.thumbnail_url,
                        alt=video.title or f"{category} - {h2_text[:50]}",
                        photographer=f"YouTube ({video.channel})" if video.channel else "YouTube",
                        source=ImageSource.UNSPLASH,  # Placeholder enum
                        width=1280,
                        height=720,
                    )
                    section_images[h2_text] = fetched
                    exclude_urls.add(video.thumbnail_url)
                    logger.info(f"Section '{h2_text[:25]}...' -> YouTube: {video.title[:35]}...")

            logger.info(f"Fetched {len(section_images)} YouTube section images for {category}")

        except Exception as e:
            logger.warning(f"YouTube section images failed: {e}")

        return section_images

    def _h2_to_search_query(self, h2_text: str, category: str = "") -> str:
        """Convert H2 text to image search query.

        Extracts meaningful English keywords for image search.
        Category-aware mappings for K-Pop, K-Fashion, and tech content.

        Args:
            h2_text: H2 section title
            category: Content category (K-Pop, K-Fashion, etc.)

        Returns:
            Search query string
        """
        h2_lower = h2_text.lower()
        category_lower = category.lower() if category else ""

        # K-Pop specific mappings
        kpop_mappings = {
            'concert': 'kpop concert stage lights audience',
            'album': 'kpop album music cd vinyl record',
            'music video': 'music video film production camera',
            'mv': 'music video kpop dance choreography',
            'dance': 'kpop dance choreography performance stage',
            'choreography': 'dance practice studio mirror',
            'fandom': 'kpop fans lightstick concert crowd',
            'fan': 'kpop fandom lightstick cheering',
            'lightstick': 'kpop concert lightstick ocean',
            'merch': 'kpop merchandise photocard collection',
            'photocard': 'kpop photocard collection trading',
            'idol': 'kpop idol stage performance spotlight',
            'debut': 'kpop debut stage spotlight new artist',
            'comeback': 'kpop comeback stage performance',
            'music show': 'korean music show stage performance',
            'award': 'music award trophy stage ceremony',
            'streaming': 'music streaming headphones playlist',
            'chart': 'music chart billboard ranking',
            'collaboration': 'music collaboration artists duet',
            'vocal': 'singer microphone vocal performance',
            'rap': 'rapper hip hop performance stage',
            'visual': 'kpop visual aesthetic portrait',
        }

        # K-Fashion specific mappings
        kfashion_mappings = {
            'streetwear': 'korean streetwear urban fashion style',
            'street style': 'korean street fashion seoul style',
            'outfit': 'korean fashion outfit aesthetic style',
            'style': 'korean fashion style aesthetic trendy',
            'casual': 'casual korean fashion relaxed style',
            'formal': 'korean formal fashion elegant suit',
            'layering': 'fashion layering style clothing outfit',
            'accessories': 'fashion accessories korean style jewelry',
            'shoes': 'korean fashion shoes sneakers footwear',
            'bag': 'korean fashion bag handbag accessories',
            'minimal': 'minimalist korean fashion clean style',
            'trendy': 'trendy korean fashion style aesthetic',
            'vintage': 'vintage korean fashion retro style',
            'oversized': 'oversized fashion korean style relaxed',
            'seasonal': 'seasonal fashion korean style clothing',
            'spring': 'spring fashion korean style pastel',
            'summer': 'summer fashion korean style light',
            'fall': 'autumn fashion korean style layered',
            'winter': 'winter fashion korean style warm coat',
            'kdrama': 'kdrama fashion korean style celebrity',
            'celebrity': 'korean celebrity fashion style outfit',
            'brand': 'korean fashion brand designer clothing',
        }

        # K-Food specific mappings
        kfood_mappings = {
            'ramyeon': 'korean instant ramen noodles spicy bowl',
            'ramen': 'asian ramen noodles soup bowl hot',
            'noodles': 'korean noodles soup bowl chopsticks',
            'spicy': 'korean spicy food red chili',
            'taste': 'food tasting korean cuisine bowl',
            'flavor': 'korean food flavors delicious',
            'ingredients': 'korean cooking ingredients kitchen fresh',
            'recipe': 'korean recipe cooking kitchen homemade',
            'cooking': 'korean cooking kitchen stove pot',
            'kimchi': 'korean kimchi fermented cabbage side dish',
            'bbq': 'korean bbq grilled meat restaurant sizzling',
            'tteokbokki': 'korean spicy rice cakes street food',
            'bibimbap': 'korean bibimbap rice bowl colorful vegetables',
            'snacks': 'korean snacks colorful packaging variety',
            'drinks': 'korean drinks soju makgeolli beverage',
            'street food': 'korean street food market stall',
            'comparison': 'food comparison taste test variety',
            'best': 'best korean food delicious plate',
            'top': 'top korean dishes variety spread',
        }

        # Tech product mappings (existing)
        tech_mappings = {
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

        # Select appropriate mappings based on category
        if "k-pop" in category_lower or "kpop" in category_lower:
            product_mappings = kpop_mappings
            fallback_suffix = 'kpop korean music'
        elif "k-fashion" in category_lower or "kfashion" in category_lower:
            product_mappings = kfashion_mappings
            fallback_suffix = 'korean fashion style'
        elif "k-food" in category_lower or "kfood" in category_lower:
            product_mappings = kfood_mappings
            fallback_suffix = 'korean food cuisine'
        else:
            product_mappings = tech_mappings
            fallback_suffix = 'technology'

        # Check for category-specific keywords first
        found_keywords = []
        for keyword, query in product_mappings.items():
            if keyword in h2_lower:
                found_keywords.append(query)

        # General section type mappings (visual context)
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
            'guide': 'roadmap guide compass direction',
            'setup': 'installation setup configuration gear',
            'tips': 'lightbulb tips advice helpful',
            'how to': 'step by step tutorial guide',
            'best': 'trophy best award top choice',
            'top': 'ranking top list chart',
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
        if found_keywords and section_query:
            return f"{found_keywords[0].split()[0]} {section_query}"
        elif found_keywords:
            return found_keywords[0]
        elif section_query:
            return section_query

        # Fallback: extract English words and add category-appropriate suffix
        english_words = re.findall(r'[A-Za-z][A-Za-z0-9+#.]*', h2_text)
        skip_words = {
            'vs', 'and', 'or', 'the', 'for', 'with', 'how', 'what', 'why',
            'which', 'best', 'top', 'in', 'on', 'to', 'is', 'are', 'our',
            'your', 'their', 'it', 'do', 'does', 'can', 'will', 'should',
            'TL', 'DR', 'FAQ', 'TLDR', 'Section', 'Quick', 'Final',
        }
        keywords = [w for w in english_words if w.lower() not in skip_words and len(w) > 2]

        if keywords:
            return ' '.join(keywords[:3]) + ' ' + fallback_suffix

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
