"""Tests for config module."""

import pytest
from pathlib import Path

from src.config import AppConfig, APIKeys, WordPressConfig, load_config


class TestAppConfig:
    """Test AppConfig dataclass."""

    def test_default_config(self):
        """AppConfig has sensible defaults."""
        config = AppConfig()

        assert config.debug is False
        assert config.log_level == "INFO"
        assert isinstance(config.data_dir, Path)

    def test_data_directories_created(self, tmp_path):
        """AppConfig creates data directories."""
        config = AppConfig(data_dir=tmp_path / "test_data")

        assert (config.data_dir / "cache").exists()
        assert (config.data_dir / "logs").exists()


class TestAPIKeys:
    """Test APIKeys dataclass."""

    def test_from_env(self, mock_env_vars):
        """APIKeys loads from environment."""
        keys = APIKeys.from_env()

        assert keys.google_ai == "test_google_key"
        assert keys.openai == "test_openai_key"
        assert keys.unsplash == "test_unsplash_key"

    def test_validate_with_all_keys(self, mock_env_vars):
        """APIKeys validates successfully with all keys."""
        keys = APIKeys.from_env()
        is_valid, missing = keys.validate()

        assert is_valid is True
        assert len(missing) == 0

    def test_validate_missing_ai_keys(self):
        """APIKeys validates missing AI keys."""
        keys = APIKeys(
            google_ai=None,
            openai=None,
            unsplash="key",
        )
        is_valid, missing = keys.validate()

        assert is_valid is False
        assert any("AI" in m.upper() for m in missing)

    def test_validate_missing_image_keys(self):
        """APIKeys validates missing image keys."""
        keys = APIKeys(
            google_ai="key",
            unsplash=None,
            pexels=None,
        )
        is_valid, missing = keys.validate()

        assert is_valid is False
        assert any("UNSPLASH" in m.upper() or "PEXELS" in m.upper() for m in missing)


class TestWordPressConfig:
    """Test WordPressConfig dataclass."""

    def test_from_env(self, mock_env_vars):
        """WordPressConfig loads from environment."""
        config = WordPressConfig.from_env()

        assert config.url == "https://test-blog.com"
        assert config.username == "test_user"
        assert config.app_password == "test_password"

    def test_validate_with_all_fields(self, mock_env_vars):
        """WordPressConfig validates successfully with all fields."""
        config = WordPressConfig.from_env()
        is_valid, missing = config.validate()

        assert is_valid is True
        assert len(missing) == 0

    def test_validate_missing_url(self):
        """WordPressConfig validates missing URL."""
        config = WordPressConfig(
            url=None,
            username="user",
            app_password="pass",
        )
        is_valid, missing = config.validate()

        assert is_valid is False
        assert "WP_URL" in missing

    def test_validate_missing_credentials(self):
        """WordPressConfig validates missing credentials."""
        config = WordPressConfig(
            url="https://blog.com",
            username=None,
            app_password=None,
        )
        is_valid, missing = config.validate()

        assert is_valid is False
        assert "WP_USERNAME" in missing
        assert "WP_APP_PASSWORD" in missing


class TestLoadConfig:
    """Test load_config function."""

    def test_load_config_returns_tuple(self, mock_env_vars):
        """load_config returns tuple of configs."""
        app_config, api_keys, wp_config = load_config()

        assert isinstance(app_config, AppConfig)
        assert isinstance(api_keys, APIKeys)
        assert isinstance(wp_config, WordPressConfig)

    def test_load_config_loads_env_vars(self, mock_env_vars):
        """load_config loads environment variables."""
        app_config, api_keys, wp_config = load_config()

        assert api_keys.google_ai == "test_google_key"
        assert wp_config.url == "https://test-blog.com"
