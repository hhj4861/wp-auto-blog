"""Tests for main module."""

import pytest
from unittest.mock import patch, MagicMock
import sys


class TestParseArgs:
    """Test command line argument parsing."""

    def test_default_args(self):
        """Default arguments are set correctly."""
        from src.main import parse_args

        with patch.object(sys, "argv", ["main.py"]):
            args = parse_args()

        assert args.topic is None
        assert args.content_type == "review"
        assert args.max_posts == 3
        assert args.auto_publish is False
        assert args.dry_run is False
        assert args.verbose is False

    def test_topic_arg(self):
        """Topic argument is parsed correctly."""
        from src.main import parse_args

        with patch.object(sys, "argv", ["main.py", "--topic", "Test Topic"]):
            args = parse_args()

        assert args.topic == "Test Topic"

    def test_dry_run_flag(self):
        """Dry run flag is parsed correctly."""
        from src.main import parse_args

        with patch.object(sys, "argv", ["main.py", "--dry-run"]):
            args = parse_args()

        assert args.dry_run is True

    def test_auto_publish_flag(self):
        """Auto publish flag is parsed correctly."""
        from src.main import parse_args

        with patch.object(sys, "argv", ["main.py", "--auto-publish"]):
            args = parse_args()

        assert args.auto_publish is True

    def test_content_type_options(self):
        """Content type options are parsed correctly."""
        from src.main import parse_args

        for content_type in ["review", "comparison", "guide", "list", "news"]:
            with patch.object(sys, "argv", ["main.py", "--content-type", content_type]):
                args = parse_args()
            assert args.content_type == content_type

    def test_max_posts_arg(self):
        """Max posts argument is parsed correctly."""
        from src.main import parse_args

        with patch.object(sys, "argv", ["main.py", "--max-posts", "5"]):
            args = parse_args()

        assert args.max_posts == 5

    def test_verbose_flag(self):
        """Verbose flag is parsed correctly."""
        from src.main import parse_args

        with patch.object(sys, "argv", ["main.py", "-v"]):
            args = parse_args()

        assert args.verbose is True

    def test_keywords_arg(self):
        """Keywords argument is parsed correctly."""
        from src.main import parse_args

        with patch.object(
            sys, "argv", ["main.py", "--topic", "Test", "--keywords", "ai", "ml", "tech"]
        ):
            args = parse_args()

        assert args.keywords == ["ai", "ml", "tech"]

    def test_category_arg(self):
        """Category argument is parsed correctly."""
        from src.main import parse_args

        with patch.object(sys, "argv", ["main.py", "--category", "Technology"]):
            args = parse_args()

        assert args.category == "Technology"


class TestSetupLogging:
    """Test logging setup."""

    def test_setup_logging_default(self, tmp_path):
        """Setup logging with default settings."""
        from src.main import setup_logging

        # Should not raise
        setup_logging(verbose=False)

    def test_setup_logging_verbose(self, tmp_path):
        """Setup logging with verbose settings."""
        from src.main import setup_logging

        # Should not raise
        setup_logging(verbose=True)


class TestMain:
    """Test main function."""

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

    def test_main_dry_run_no_topics(self, mock_env_vars):
        """Main returns 0 when no topics found in dry run."""
        from src.main import main
        from src.pipeline import BlogPipeline

        with patch.object(sys, "argv", ["main.py", "--dry-run"]):
            with patch.object(BlogPipeline, "run", return_value=[]):
                result = main()

        assert result == 0

    def test_main_with_topic(self, mock_env_vars):
        """Main handles single topic mode."""
        from src.main import main
        from src.pipeline import BlogPipeline, PipelineResult
        from src.wordpress_client import CreatedPost, PostStatus

        mock_result = PipelineResult(
            topic="Test Topic",
            success=True,
            post=CreatedPost(1, "https://blog.com/test", "Test", PostStatus.DRAFT),
        )

        with patch.object(sys, "argv", ["main.py", "--topic", "Test Topic", "--dry-run"]):
            with patch.object(BlogPipeline, "run_single", return_value=mock_result):
                result = main()

        assert result == 0

    def test_main_with_failures(self, mock_env_vars):
        """Main returns 1 when there are failures."""
        from src.main import main
        from src.pipeline import BlogPipeline, PipelineResult

        mock_result = PipelineResult(
            topic="Failed Topic",
            success=False,
            error="Test error",
        )

        with patch.object(sys, "argv", ["main.py", "--dry-run"]):
            with patch.object(BlogPipeline, "run", return_value=[mock_result]):
                result = main()

        assert result == 1

    def test_main_pipeline_exception(self, mock_env_vars):
        """Main returns 1 when pipeline raises exception."""
        from src.main import main
        from src.pipeline import BlogPipeline

        with patch.object(sys, "argv", ["main.py", "--dry-run"]):
            with patch.object(BlogPipeline, "run", side_effect=Exception("Pipeline error")):
                result = main()

        assert result == 1
