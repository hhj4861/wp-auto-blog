"""Integration tests for the complete pipeline.

TDD: Tests for the full workflow from trend detection to WordPress publishing.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.trend_detector import TrendDetector, Topic, TrendSource, TrendConfig
from src.content_generator import ContentGenerator, ContentType, GeneratedContent
from src.image_fetcher import ImageFetcher, FetchedImage, ImageSource
from src.wordpress_client import WordPressClient, PostStatus, CreatedPost
from src.pipeline import BlogPipeline, PipelineConfig, PipelineResult


class TestBlogPipeline:
    """Test the complete blog pipeline."""

    @pytest.fixture
    def mock_env_vars(self, monkeypatch):
        """Set up mock environment variables."""
        env_vars = {
            "REDDIT_CLIENT_ID": "test_client_id",
            "REDDIT_CLIENT_SECRET": "test_client_secret",
            "REDDIT_USER_AGENT": "test_user_agent",
            "OPENAI_API_KEY": "test_openai_key",
            "GOOGLE_AI_API_KEY": "test_google_key",
            "UNSPLASH_ACCESS_KEY": "test_unsplash_key",
            "PEXELS_API_KEY": "test_pexels_key",
            "WP_URL": "https://test-blog.com",
            "WP_USERNAME": "test_user",
            "WP_APP_PASSWORD": "test_password",
            "NOTIFICATION_EMAIL": "test@example.com",
        }
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)
        return env_vars

    @pytest.fixture
    def pipeline(self, mock_env_vars):
        """Create BlogPipeline instance."""
        return BlogPipeline()

    def test_pipeline_init(self, mock_env_vars):
        """Pipeline can be initialized."""
        pipeline = BlogPipeline()
        assert pipeline is not None
        assert pipeline.trend_detector is not None
        assert pipeline.content_generator is not None
        assert pipeline.image_fetcher is not None
        assert pipeline.wp_client is not None

    @pytest.mark.integration
    def test_full_pipeline_execution(self, pipeline):
        """Test complete pipeline from trend to post."""
        # Mock trend detection
        mock_topics = [
            Topic(
                topic="New AI Tool Released",
                keywords=["ai", "tool", "productivity"],
                source=TrendSource.HACKER_NEWS,
                score=85,
                suggested_title="New AI Tool Review: Complete Guide",
            )
        ]

        # Mock content generation
        mock_content = GeneratedContent(
            title="New AI Tool Review: Complete Guide",
            html="<h1>Title</h1><h2>Section</h2>" + "<p>Content</p>" * 300,
            meta_description="Review of the new AI tool for productivity.",
            keywords=["ai", "tool", "productivity"],
            word_count=1800,
            content_type=ContentType.REVIEW,
        )

        # Mock images
        mock_images = [
            FetchedImage(
                url="https://images.unsplash.com/photo-1",
                alt="AI technology concept",
                photographer="John Doe",
                source=ImageSource.UNSPLASH,
                width=1920,
                height=1080,
            ),
            FetchedImage(
                url="https://images.unsplash.com/photo-2",
                alt="Productivity tools",
                photographer="Jane Doe",
                source=ImageSource.UNSPLASH,
                width=1920,
                height=1080,
            ),
        ]

        # Mock created post
        mock_post = CreatedPost(
            id=123,
            url="https://test-blog.com/new-ai-tool-review",
            title="New AI Tool Review: Complete Guide",
            status=PostStatus.DRAFT,
        )

        with patch.object(pipeline.trend_detector, "collect", return_value=mock_topics):
            with patch.object(pipeline.content_generator, "generate", return_value=mock_content):
                with patch.object(pipeline.image_fetcher, "fetch", return_value=mock_images):
                    with patch.object(pipeline.wp_client, "create_post", return_value=mock_post):
                        results = pipeline.run()

        assert len(results) == 1
        assert results[0].success is True
        assert results[0].post.id == 123

    @pytest.mark.integration
    def test_pipeline_handles_no_trends(self, pipeline):
        """Pipeline handles case when no trends found."""
        with patch.object(pipeline.trend_detector, "collect", return_value=[]):
            results = pipeline.run()

        assert len(results) == 0

    @pytest.mark.integration
    def test_pipeline_handles_content_generation_failure(self, pipeline):
        """Pipeline handles content generation failure gracefully."""
        mock_topics = [
            Topic("Topic 1", ["kw"], TrendSource.HACKER_NEWS, 80, "Title 1"),
        ]

        with patch.object(pipeline.trend_detector, "collect", return_value=mock_topics):
            with patch.object(
                pipeline.content_generator, "generate", side_effect=Exception("LLM Error")
            ):
                results = pipeline.run()

        # Should have result with failure
        assert len(results) == 1
        assert results[0].success is False
        assert "LLM Error" in results[0].error

    @pytest.mark.integration
    def test_pipeline_continues_on_single_failure(self, pipeline):
        """Pipeline continues processing after single topic fails."""
        mock_topics = [
            Topic("Topic 1", ["kw1"], TrendSource.HACKER_NEWS, 90, "Title 1"),
            Topic("Topic 2", ["kw2"], TrendSource.HACKER_NEWS, 85, "Title 2"),
        ]

        mock_content = GeneratedContent(
            title="Title 2",
            html="<h1>Title</h1><p>Content</p>" * 100,
            meta_description="Description",
            keywords=["kw2"],
            word_count=1500,
            content_type=ContentType.NEWS,
        )

        mock_images = [
            FetchedImage("url", "alt", "photo", ImageSource.UNSPLASH, 1920, 1080)
        ]

        mock_post = CreatedPost(
            id=2, url="https://blog.com/title-2", title="Title 2", status=PostStatus.DRAFT
        )

        call_count = 0

        def generate_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("First topic failed")
            return mock_content

        with patch.object(pipeline.trend_detector, "collect", return_value=mock_topics):
            with patch.object(
                pipeline.content_generator, "generate", side_effect=generate_side_effect
            ):
                with patch.object(pipeline.image_fetcher, "fetch", return_value=mock_images):
                    with patch.object(pipeline.wp_client, "create_post", return_value=mock_post):
                        results = pipeline.run()

        # Should have 2 results: one failure, one success
        assert len(results) == 2
        assert results[0].success is False
        assert results[1].success is True


class TestPipelineConfig:
    """Test PipelineConfig."""

    def test_default_config(self):
        """PipelineConfig has sensible defaults."""
        config = PipelineConfig()

        assert config.max_posts_per_run > 0
        assert config.content_type == ContentType.REVIEW
        assert config.auto_publish is False

    def test_custom_config(self):
        """PipelineConfig accepts custom values."""
        config = PipelineConfig(
            max_posts_per_run=10,
            content_type=ContentType.GUIDE,
            auto_publish=True,
        )

        assert config.max_posts_per_run == 10
        assert config.content_type == ContentType.GUIDE
        assert config.auto_publish is True


class TestPipelineResult:
    """Test PipelineResult."""

    def test_success_result(self):
        """PipelineResult for successful operation."""
        post = CreatedPost(1, "url", "title", PostStatus.DRAFT)
        result = PipelineResult(
            topic="Test Topic",
            success=True,
            post=post,
            error=None,
        )

        assert result.success is True
        assert result.post is not None
        assert result.error is None

    def test_failure_result(self):
        """PipelineResult for failed operation."""
        result = PipelineResult(
            topic="Failed Topic",
            success=False,
            post=None,
            error="Something went wrong",
        )

        assert result.success is False
        assert result.post is None
        assert result.error is not None

    def test_result_to_dict(self):
        """PipelineResult can be converted to dict."""
        result = PipelineResult(
            topic="Topic",
            success=True,
            post=CreatedPost(1, "url", "title", PostStatus.DRAFT),
            error=None,
        )

        d = result.to_dict()

        assert isinstance(d, dict)
        assert d["topic"] == "Topic"
        assert d["success"] is True


class TestDryRun:
    """Test dry run mode."""

    @pytest.fixture
    def pipeline(self, mock_env_vars):
        config = PipelineConfig(dry_run=True)
        return BlogPipeline(config=config)

    @pytest.mark.integration
    def test_dry_run_does_not_publish(self, pipeline, mock_env_vars):
        """Dry run mode does not actually publish."""
        mock_topics = [
            Topic("Topic", ["kw"], TrendSource.HACKER_NEWS, 80, "Title"),
        ]

        mock_content = GeneratedContent(
            title="Title",
            html="<h1>Title</h1><p>Content</p>" * 100,
            meta_description="Desc",
            keywords=["kw"],
            word_count=1500,
            content_type=ContentType.REVIEW,
        )

        mock_images = [
            FetchedImage("url", "alt", "photo", ImageSource.UNSPLASH, 1920, 1080)
        ]

        with patch.object(pipeline.trend_detector, "collect", return_value=mock_topics):
            with patch.object(pipeline.content_generator, "generate", return_value=mock_content):
                with patch.object(pipeline.image_fetcher, "fetch", return_value=mock_images):
                    with patch.object(pipeline.wp_client, "create_post") as mock_create:
                        results = pipeline.run()

        # create_post should NOT be called in dry run
        mock_create.assert_not_called()

        # But should still return results
        assert len(results) == 1
        assert results[0].success is True
