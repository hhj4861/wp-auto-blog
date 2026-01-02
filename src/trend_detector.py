"""Trend Detector module for discovering hot topics.

Collects trending topics from multiple sources:
- Google Trends
- Hacker News
- Reddit

FR-001: Trend Detection
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import requests
from loguru import logger

try:
    from pytrends.request import TrendReq
except ImportError:
    TrendReq = None  # type: ignore

try:
    import praw
except ImportError:
    praw = None  # type: ignore


class TrendSource(Enum):
    """Enumeration of trend sources."""

    GOOGLE_TRENDS = "google_trends"
    HACKER_NEWS = "hacker_news"
    REDDIT = "reddit"


@dataclass
class Topic:
    """Represents a trending topic.

    Attributes:
        topic: The topic title/name
        keywords: List of relevant keywords
        source: Where the topic was found
        score: Relevance score (0-100)
        suggested_title: SEO-friendly blog title suggestion
    """

    topic: str
    keywords: list[str]
    source: TrendSource
    score: int
    suggested_title: str

    def to_dict(self) -> dict:
        """Convert Topic to dictionary."""
        return {
            "topic": self.topic,
            "keywords": self.keywords,
            "source": self.source.value,
            "score": self.score,
            "suggested_title": self.suggested_title,
        }


@dataclass
class TrendConfig:
    """Configuration for trend detection.

    Attributes:
        min_score: Minimum score threshold (0-100)
        max_topics: Maximum number of topics to return
        niche_keywords: Keywords defining the niche
        hn_limit: Number of HN stories to fetch
        reddit_subreddits: Subreddits to monitor
        reddit_limit: Posts per subreddit
    """

    min_score: int = 50
    max_topics: int = 5
    niche_keywords: list[str] = field(
        default_factory=lambda: [
            "ai",
            "artificial intelligence",
            "machine learning",
            "automation",
            "productivity",
            "developer",
            "programming",
            "tech",
            "saas",
            "startup",
            "tool",
            "app",
        ]
    )
    hn_limit: int = 30
    reddit_subreddits: list[str] = field(
        default_factory=lambda: ["technology", "programming", "artificial", "MachineLearning"]
    )
    reddit_limit: int = 10


class TrendDetector:
    """Detects trending topics from multiple sources.

    Example:
        >>> detector = TrendDetector()
        >>> topics = detector.collect()
        >>> for topic in topics:
        ...     print(f"{topic.topic} (score: {topic.score})")
    """

    HN_API_BASE = "https://hacker-news.firebaseio.com/v0"
    STOP_WORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "need", "dare",
        "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
        "into", "through", "during", "before", "after", "above", "below",
        "between", "under", "again", "further", "then", "once", "here",
        "there", "when", "where", "why", "how", "all", "each", "few",
        "more", "most", "other", "some", "such", "no", "nor", "not",
        "only", "own", "same", "so", "than", "too", "very", "just",
        "and", "but", "if", "or", "because", "until", "while", "this",
        "that", "these", "those", "i", "me", "my", "myself", "we", "our",
        "you", "your", "he", "him", "his", "she", "her", "it", "its",
        "they", "them", "their", "what", "which", "who", "whom",
        "new", "show", "hn", "ask",
    }

    def __init__(self, config: Optional[TrendConfig] = None) -> None:
        """Initialize TrendDetector.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or TrendConfig()
        self._setup_reddit()

    def _setup_reddit(self) -> None:
        """Setup Reddit API client if credentials available."""
        self._reddit = None
        if praw is None:
            logger.warning("praw not installed, Reddit fetching disabled")
            return

        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = os.getenv("REDDIT_USER_AGENT", "wp-auto-blog/1.0")

        if client_id and client_secret:
            try:
                self._reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent=user_agent,
                )
                logger.info("Reddit API client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Reddit client: {e}")

    def collect(self) -> list[Topic]:
        """Collect trending topics from all sources.

        Returns:
            List of Topic objects, sorted by score (descending),
            filtered by min_score and limited to max_topics.
        """
        logger.info("Collecting trends from all sources...")

        all_topics = self._fetch_all_sources()

        # Filter by minimum score
        filtered = [t for t in all_topics if t.score >= self.config.min_score]
        logger.debug(f"Filtered {len(all_topics)} -> {len(filtered)} topics (min_score={self.config.min_score})")

        # Sort by score descending
        sorted_topics = sorted(filtered, key=lambda t: t.score, reverse=True)

        # Limit to max_topics
        result = sorted_topics[: self.config.max_topics]
        logger.info(f"Returning {len(result)} topics")

        return result

    def _fetch_all_sources(self) -> list[Topic]:
        """Fetch topics from all configured sources.

        Returns:
            Combined list of topics from all sources.
        """
        topics: list[Topic] = []

        # Fetch from each source, handling errors gracefully
        topics.extend(self._fetch_hacker_news())
        topics.extend(self._fetch_google_trends())
        topics.extend(self._fetch_reddit())

        return topics

    def _fetch_hacker_news(self) -> list[Topic]:
        """Fetch trending topics from Hacker News.

        Returns:
            List of Topics from HN top stories.
        """
        topics: list[Topic] = []

        try:
            # Get top story IDs
            response = requests.get(
                f"{self.HN_API_BASE}/topstories.json",
                timeout=10,
            )
            response.raise_for_status()
            story_ids = response.json()[: self.config.hn_limit]

            # Fetch each story
            for story_id in story_ids:
                try:
                    story_resp = requests.get(
                        f"{self.HN_API_BASE}/item/{story_id}.json",
                        timeout=5,
                    )
                    story_resp.raise_for_status()
                    story = story_resp.json()

                    if not story or "title" not in story:
                        continue

                    title = story.get("title", "")
                    source_score = story.get("score", 0)

                    # Calculate relevance score
                    score = self._calculate_score(
                        title=title,
                        source_score=source_score,
                        source=TrendSource.HACKER_NEWS,
                    )

                    # Skip if not relevant enough
                    if score < 20:
                        continue

                    keywords = self._extract_keywords(title)
                    suggested_title = self._generate_title(title, keywords)

                    topics.append(
                        Topic(
                            topic=title,
                            keywords=keywords,
                            source=TrendSource.HACKER_NEWS,
                            score=score,
                            suggested_title=suggested_title,
                        )
                    )

                except Exception as e:
                    logger.debug(f"Failed to fetch HN story {story_id}: {e}")
                    continue

            logger.info(f"Fetched {len(topics)} topics from Hacker News")

        except Exception as e:
            logger.error(f"Failed to fetch Hacker News: {e}")

        return topics

    def _fetch_google_trends(self) -> list[Topic]:
        """Fetch trending topics from Google Trends.

        Returns:
            List of Topics from Google Trends.
        """
        topics: list[Topic] = []

        if TrendReq is None:
            logger.warning("pytrends not installed, skipping Google Trends")
            return topics

        try:
            pytrends = TrendReq(hl="en-US", tz=360)
            trending = pytrends.trending_searches(pn="united_states")

            for idx, row in trending.iterrows():
                if idx >= 20:  # Limit to 20
                    break

                title = str(row[0])
                keywords = self._extract_keywords(title)

                # Calculate score based on position (higher position = higher score)
                position_score = max(0, 100 - (idx * 5))

                score = self._calculate_score(
                    title=title,
                    source_score=position_score,
                    source=TrendSource.GOOGLE_TRENDS,
                )

                if score < 20:
                    continue

                suggested_title = self._generate_title(title, keywords)

                topics.append(
                    Topic(
                        topic=title,
                        keywords=keywords,
                        source=TrendSource.GOOGLE_TRENDS,
                        score=score,
                        suggested_title=suggested_title,
                    )
                )

            logger.info(f"Fetched {len(topics)} topics from Google Trends")

        except Exception as e:
            logger.error(f"Failed to fetch Google Trends: {e}")

        return topics

    def _fetch_reddit(self) -> list[Topic]:
        """Fetch trending topics from Reddit.

        Returns:
            List of Topics from configured subreddits.
        """
        topics: list[Topic] = []

        if self._reddit is None:
            logger.debug("Reddit client not available, skipping")
            return topics

        try:
            for subreddit_name in self.config.reddit_subreddits:
                try:
                    subreddit = self._reddit.subreddit(subreddit_name)
                    for submission in subreddit.hot(limit=self.config.reddit_limit):
                        title = submission.title
                        source_score = submission.score

                        score = self._calculate_score(
                            title=title,
                            source_score=source_score,
                            source=TrendSource.REDDIT,
                        )

                        if score < 20:
                            continue

                        keywords = self._extract_keywords(title)
                        suggested_title = self._generate_title(title, keywords)

                        topics.append(
                            Topic(
                                topic=title,
                                keywords=keywords,
                                source=TrendSource.REDDIT,
                                score=score,
                                suggested_title=suggested_title,
                            )
                        )

                except Exception as e:
                    logger.debug(f"Failed to fetch r/{subreddit_name}: {e}")
                    continue

            logger.info(f"Fetched {len(topics)} topics from Reddit")

        except Exception as e:
            logger.error(f"Failed to fetch Reddit: {e}")

        return topics

    def _calculate_score(
        self,
        title: str,
        source_score: int,
        source: TrendSource,
    ) -> int:
        """Calculate relevance score for a topic.

        Score is based on:
        - Source popularity (votes/upvotes)
        - Niche keyword relevance
        - Source weight

        Args:
            title: The topic title
            source_score: Raw score from source (votes, position, etc.)
            source: The source platform

        Returns:
            Score between 0 and 100
        """
        # Base score from source (normalize to 0-50)
        if source == TrendSource.HACKER_NEWS:
            # HN scores can range from 0 to 1000+
            base_score = min(50, source_score / 20)
        elif source == TrendSource.REDDIT:
            # Reddit scores can be very high
            base_score = min(50, source_score / 100)
        else:  # Google Trends
            # Already normalized position score
            base_score = min(50, source_score / 2)

        # Niche relevance bonus (0-50)
        title_lower = title.lower()
        relevance_score = 0
        for keyword in self.config.niche_keywords:
            if keyword.lower() in title_lower:
                relevance_score += 10

        relevance_score = min(50, relevance_score)

        # Combine scores
        total_score = int(base_score + relevance_score)

        # Clamp to 0-100
        return max(0, min(100, total_score))

    def _generate_title(self, topic: str, keywords: list[str]) -> str:
        """Generate SEO-friendly blog title.

        Args:
            topic: Original topic title
            keywords: Extracted keywords

        Returns:
            SEO-optimized title (max 70 characters)
        """
        # Title templates based on content type
        templates = [
            "{topic}: Complete Guide for {year}",
            "{topic} Review: Everything You Need to Know",
            "How to Use {topic}: A Beginner's Guide",
            "{topic} Explained: What You Should Know",
            "The Ultimate Guide to {topic}",
        ]

        # Clean the topic
        clean_topic = topic.strip()

        # Remove common prefixes
        prefixes_to_remove = ["Show HN:", "Ask HN:", "[D]", "[R]", "[P]"]
        for prefix in prefixes_to_remove:
            if clean_topic.startswith(prefix):
                clean_topic = clean_topic[len(prefix):].strip()

        # Use the first template for now (could be randomized or AI-generated later)
        from datetime import datetime
        year = datetime.now().year

        title = templates[0].format(topic=clean_topic, year=year)

        # Truncate if too long
        if len(title) > 70:
            title = title[:67] + "..."

        return title

    def _extract_keywords(self, text: str) -> list[str]:
        """Extract keywords from text.

        Args:
            text: Input text

        Returns:
            List of keywords (max 5)
        """
        # Tokenize
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())

        # Remove stop words
        keywords = [w for w in words if w not in self.STOP_WORDS]

        # Get unique keywords, preserving order
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        # Limit to 5
        return unique_keywords[:5]
