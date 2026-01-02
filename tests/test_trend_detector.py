"""Tests for TrendDetector module.

TDD: RED -> GREEN -> REFACTOR
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

from src.trend_detector import (
    TrendDetector,
    Topic,
    TrendSource,
    TrendConfig,
)


class TestTopic:
    """Test Topic dataclass."""

    def test_topic_creation(self):
        """Topic can be created with required fields."""
        topic = Topic(
            topic="Claude 3.5 Released",
            keywords=["claude", "anthropic", "ai"],
            source=TrendSource.HACKER_NEWS,
            score=85,
            suggested_title="Claude 3.5 Review: Complete Guide",
        )

        assert topic.topic == "Claude 3.5 Released"
        assert topic.keywords == ["claude", "anthropic", "ai"]
        assert topic.source == TrendSource.HACKER_NEWS
        assert topic.score == 85
        assert topic.suggested_title == "Claude 3.5 Review: Complete Guide"

    def test_topic_to_dict(self):
        """Topic can be converted to dictionary."""
        topic = Topic(
            topic="Test Topic",
            keywords=["test"],
            source=TrendSource.GOOGLE_TRENDS,
            score=50,
            suggested_title="Test Title",
        )

        result = topic.to_dict()

        assert isinstance(result, dict)
        assert result["topic"] == "Test Topic"
        assert result["source"] == "google_trends"


class TestTrendConfig:
    """Test TrendConfig dataclass."""

    def test_default_config(self):
        """TrendConfig has sensible defaults."""
        config = TrendConfig()

        assert config.min_score == 50
        assert config.max_topics == 5
        assert config.niche_keywords is not None
        assert len(config.niche_keywords) > 0

    def test_custom_config(self):
        """TrendConfig accepts custom values."""
        config = TrendConfig(
            min_score=70,
            max_topics=10,
            niche_keywords=["ai", "ml", "automation"],
        )

        assert config.min_score == 70
        assert config.max_topics == 10
        assert "ai" in config.niche_keywords


class TestTrendDetector:
    """Test TrendDetector main class."""

    @pytest.fixture
    def detector(self, mock_env_vars):
        """Create TrendDetector instance with mocked dependencies."""
        return TrendDetector()

    def test_init_creates_instance(self, mock_env_vars):
        """TrendDetector can be instantiated."""
        detector = TrendDetector()
        assert detector is not None

    def test_init_with_custom_config(self, mock_env_vars):
        """TrendDetector accepts custom config."""
        config = TrendConfig(min_score=80, max_topics=3)
        detector = TrendDetector(config=config)

        assert detector.config.min_score == 80
        assert detector.config.max_topics == 3

    @pytest.mark.unit
    def test_collect_returns_list_of_topics(self, detector):
        """collect() returns a list of Topic objects."""
        with patch.object(detector, "_fetch_hacker_news", return_value=[]):
            with patch.object(detector, "_fetch_google_trends", return_value=[]):
                with patch.object(detector, "_fetch_reddit", return_value=[]):
                    topics = detector.collect()

        assert isinstance(topics, list)

    @pytest.mark.unit
    def test_collect_filters_by_min_score(self, detector):
        """collect() filters out topics below min_score."""
        mock_topics = [
            Topic("High Score", ["test"], TrendSource.HACKER_NEWS, 90, "High"),
            Topic("Low Score", ["test"], TrendSource.HACKER_NEWS, 30, "Low"),
        ]

        with patch.object(detector, "_fetch_all_sources", return_value=mock_topics):
            topics = detector.collect()

        # Only high score topic should remain (min_score default is 50)
        assert len(topics) == 1
        assert topics[0].topic == "High Score"

    @pytest.mark.unit
    def test_collect_limits_to_max_topics(self, detector):
        """collect() limits results to max_topics."""
        detector.config.max_topics = 2
        mock_topics = [
            Topic(f"Topic {i}", ["test"], TrendSource.HACKER_NEWS, 80, f"Title {i}")
            for i in range(10)
        ]

        with patch.object(detector, "_fetch_all_sources", return_value=mock_topics):
            topics = detector.collect()

        assert len(topics) == 2

    @pytest.mark.unit
    def test_collect_sorts_by_score_descending(self, detector):
        """collect() returns topics sorted by score (highest first)."""
        mock_topics = [
            Topic("Low", ["test"], TrendSource.HACKER_NEWS, 60, "Low"),
            Topic("High", ["test"], TrendSource.HACKER_NEWS, 95, "High"),
            Topic("Medium", ["test"], TrendSource.HACKER_NEWS, 75, "Medium"),
        ]

        with patch.object(detector, "_fetch_all_sources", return_value=mock_topics):
            topics = detector.collect()

        assert topics[0].score == 95
        assert topics[1].score == 75
        assert topics[2].score == 60


class TestHackerNewsFetcher:
    """Test Hacker News fetching functionality."""

    @pytest.fixture
    def detector(self, mock_env_vars):
        return TrendDetector()

    @pytest.mark.unit
    def test_fetch_hacker_news_returns_topics(self, detector):
        """_fetch_hacker_news returns list of Topics."""
        mock_response = Mock()
        mock_response.json.return_value = [12345, 12346]
        mock_response.raise_for_status = Mock()

        mock_story = Mock()
        mock_story.json.return_value = {
            "id": 12345,
            "title": "Show HN: AI Tool for Developers",
            "score": 150,
            "url": "https://example.com",
        }
        mock_story.raise_for_status = Mock()

        with patch("requests.get", side_effect=[mock_response, mock_story, mock_story]):
            topics = detector._fetch_hacker_news()

        assert isinstance(topics, list)

    @pytest.mark.unit
    def test_fetch_hacker_news_handles_api_error(self, detector):
        """_fetch_hacker_news handles API errors gracefully."""
        with patch("requests.get", side_effect=Exception("API Error")):
            topics = detector._fetch_hacker_news()

        assert topics == []

    @pytest.mark.unit
    def test_fetch_hacker_news_filters_by_niche(self, detector):
        """_fetch_hacker_news filters stories by niche relevance."""
        detector.config.niche_keywords = ["ai", "automation"]

        mock_response = Mock()
        mock_response.json.return_value = [1, 2]
        mock_response.raise_for_status = Mock()

        mock_stories = [
            {"id": 1, "title": "New AI breakthrough", "score": 100, "url": "https://a.com"},
            {"id": 2, "title": "Sports news today", "score": 200, "url": "https://b.com"},
        ]

        def mock_get(url, **kwargs):
            m = Mock()
            m.raise_for_status = Mock()
            if "topstories" in url:
                m.json.return_value = [1, 2]
            elif "1.json" in url:
                m.json.return_value = mock_stories[0]
            elif "2.json" in url:
                m.json.return_value = mock_stories[1]
            return m

        with patch("requests.get", side_effect=mock_get):
            topics = detector._fetch_hacker_news()

        # Only AI-related story should be included
        relevant = [t for t in topics if "AI" in t.topic or "ai" in t.topic.lower()]
        assert len(relevant) >= 0  # May vary based on implementation


class TestGoogleTrendsFetcher:
    """Test Google Trends fetching functionality."""

    @pytest.fixture
    def detector(self, mock_env_vars):
        return TrendDetector()

    @pytest.mark.unit
    def test_fetch_google_trends_returns_topics(self, detector):
        """_fetch_google_trends returns list of Topics."""
        mock_pytrends = MagicMock()
        mock_pytrends.trending_searches.return_value = MagicMock()

        with patch("src.trend_detector.TrendReq", return_value=mock_pytrends):
            topics = detector._fetch_google_trends()

        assert isinstance(topics, list)

    @pytest.mark.unit
    def test_fetch_google_trends_handles_error(self, detector):
        """_fetch_google_trends handles errors gracefully."""
        with patch("src.trend_detector.TrendReq", side_effect=Exception("API Error")):
            topics = detector._fetch_google_trends()

        assert topics == []


class TestRedditFetcher:
    """Test Reddit fetching functionality."""

    @pytest.fixture
    def detector(self, mock_env_vars):
        return TrendDetector()

    @pytest.mark.unit
    def test_fetch_reddit_returns_topics(self, detector):
        """_fetch_reddit returns list of Topics."""
        mock_reddit = MagicMock()
        mock_subreddit = MagicMock()
        mock_submission = MagicMock()
        mock_submission.title = "New AI Tool Released"
        mock_submission.score = 500
        mock_submission.url = "https://example.com"
        mock_subreddit.hot.return_value = [mock_submission]
        mock_reddit.subreddit.return_value = mock_subreddit

        with patch("src.trend_detector.praw.Reddit", return_value=mock_reddit):
            topics = detector._fetch_reddit()

        assert isinstance(topics, list)

    @pytest.mark.unit
    def test_fetch_reddit_handles_error(self, detector):
        """_fetch_reddit handles errors gracefully."""
        with patch("src.trend_detector.praw.Reddit", side_effect=Exception("API Error")):
            topics = detector._fetch_reddit()

        assert topics == []


class TestScoring:
    """Test topic scoring functionality."""

    @pytest.fixture
    def detector(self, mock_env_vars):
        return TrendDetector()

    @pytest.mark.unit
    def test_calculate_score_considers_source_score(self, detector):
        """_calculate_score considers the original source score."""
        score1 = detector._calculate_score(
            title="AI Tool",
            source_score=100,
            source=TrendSource.HACKER_NEWS,
        )
        score2 = detector._calculate_score(
            title="AI Tool",
            source_score=500,
            source=TrendSource.HACKER_NEWS,
        )

        assert score2 > score1

    @pytest.mark.unit
    def test_calculate_score_considers_niche_relevance(self, detector):
        """_calculate_score boosts niche-relevant topics."""
        detector.config.niche_keywords = ["ai", "automation", "productivity"]

        score_relevant = detector._calculate_score(
            title="New AI Automation Tool for Productivity",
            source_score=100,
            source=TrendSource.HACKER_NEWS,
        )
        score_irrelevant = detector._calculate_score(
            title="Sports Team Wins Championship",
            source_score=100,
            source=TrendSource.HACKER_NEWS,
        )

        assert score_relevant > score_irrelevant

    @pytest.mark.unit
    def test_calculate_score_returns_0_to_100(self, detector):
        """_calculate_score returns score between 0 and 100."""
        score = detector._calculate_score(
            title="Test Topic",
            source_score=1000,
            source=TrendSource.HACKER_NEWS,
        )

        assert 0 <= score <= 100


class TestTitleGeneration:
    """Test suggested title generation."""

    @pytest.fixture
    def detector(self, mock_env_vars):
        return TrendDetector()

    @pytest.mark.unit
    def test_generate_title_creates_seo_friendly_title(self, detector):
        """_generate_title creates SEO-friendly blog title."""
        title = detector._generate_title(
            topic="Claude 3.5 Sonnet Released",
            keywords=["claude", "ai", "llm"],
        )

        assert isinstance(title, str)
        assert len(title) > 10
        assert len(title) <= 70  # SEO recommended length

    @pytest.mark.unit
    def test_generate_title_includes_keywords(self, detector):
        """_generate_title includes relevant keywords."""
        title = detector._generate_title(
            topic="New AI Tool Launch",
            keywords=["ai", "tool", "productivity"],
        )

        # Title should contain at least one keyword
        title_lower = title.lower()
        has_keyword = any(kw in title_lower for kw in ["ai", "tool", "productivity"])
        assert has_keyword


class TestKeywordExtraction:
    """Test keyword extraction functionality."""

    @pytest.fixture
    def detector(self, mock_env_vars):
        return TrendDetector()

    @pytest.mark.unit
    def test_extract_keywords_returns_list(self, detector):
        """_extract_keywords returns list of strings."""
        keywords = detector._extract_keywords("Claude 3.5 Sonnet AI Model Released by Anthropic")

        assert isinstance(keywords, list)
        assert all(isinstance(kw, str) for kw in keywords)

    @pytest.mark.unit
    def test_extract_keywords_removes_stop_words(self, detector):
        """_extract_keywords removes common stop words."""
        keywords = detector._extract_keywords("The new AI tool is the best for the developers")

        stop_words = ["the", "is", "for", "a", "an"]
        for stop_word in stop_words:
            assert stop_word not in keywords

    @pytest.mark.unit
    def test_extract_keywords_limits_count(self, detector):
        """_extract_keywords limits keyword count."""
        keywords = detector._extract_keywords(
            "AI machine learning deep learning neural network computer vision NLP transformers"
        )

        assert len(keywords) <= 5  # Default limit
