"""Configuration management for wp-auto-blog.

Handles loading and validating configuration from environment variables and files.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from loguru import logger


@dataclass
class AppConfig:
    """Application-wide configuration.

    Attributes:
        debug: Enable debug mode
        log_level: Logging level
        data_dir: Directory for data storage
    """

    debug: bool = False
    log_level: str = "INFO"
    data_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent / "data")

    def __post_init__(self) -> None:
        """Ensure data directories exist."""
        (self.data_dir / "cache").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "logs").mkdir(parents=True, exist_ok=True)


@dataclass
class APIKeys:
    """API keys configuration.

    Attributes:
        google_ai: Google AI API key
        openai: OpenAI API key
        unsplash: Unsplash API key
        pexels: Pexels API key
        reddit_client_id: Reddit client ID
        reddit_client_secret: Reddit client secret
    """

    google_ai: Optional[str] = None
    openai: Optional[str] = None
    unsplash: Optional[str] = None
    pexels: Optional[str] = None
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None

    @classmethod
    def from_env(cls) -> "APIKeys":
        """Load API keys from environment."""
        return cls(
            google_ai=os.getenv("GOOGLE_AI_API_KEY"),
            openai=os.getenv("OPENAI_API_KEY"),
            unsplash=os.getenv("UNSPLASH_ACCESS_KEY"),
            pexels=os.getenv("PEXELS_API_KEY"),
            reddit_client_id=os.getenv("REDDIT_CLIENT_ID"),
            reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        )

    def validate(self) -> tuple[bool, list[str]]:
        """Validate required API keys are present.

        Returns:
            Tuple of (is_valid, list of missing keys)
        """
        missing = []

        # At least one AI key required
        if not self.google_ai and not self.openai:
            missing.append("GOOGLE_AI_API_KEY or OPENAI_API_KEY")

        # At least one image API key required
        if not self.unsplash and not self.pexels:
            missing.append("UNSPLASH_ACCESS_KEY or PEXELS_API_KEY")

        return len(missing) == 0, missing


@dataclass
class WordPressConfig:
    """WordPress configuration.

    Attributes:
        url: WordPress site URL
        username: WordPress username
        app_password: Application password
    """

    url: Optional[str] = None
    username: Optional[str] = None
    app_password: Optional[str] = None

    @classmethod
    def from_env(cls) -> "WordPressConfig":
        """Load WordPress config from environment."""
        return cls(
            url=os.getenv("WP_URL"),
            username=os.getenv("WP_USERNAME"),
            app_password=os.getenv("WP_APP_PASSWORD"),
        )

    def validate(self) -> tuple[bool, list[str]]:
        """Validate WordPress configuration.

        Returns:
            Tuple of (is_valid, list of missing values)
        """
        missing = []

        if not self.url:
            missing.append("WP_URL")
        if not self.username:
            missing.append("WP_USERNAME")
        if not self.app_password:
            missing.append("WP_APP_PASSWORD")

        return len(missing) == 0, missing


def load_config() -> tuple[AppConfig, APIKeys, WordPressConfig]:
    """Load all configuration.

    Returns:
        Tuple of (AppConfig, APIKeys, WordPressConfig)
    """
    # Load .env file
    load_dotenv()

    app_config = AppConfig(
        debug=os.getenv("DEBUG", "").lower() == "true",
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )

    api_keys = APIKeys.from_env()
    wp_config = WordPressConfig.from_env()

    # Validate
    api_valid, api_missing = api_keys.validate()
    wp_valid, wp_missing = wp_config.validate()

    if not api_valid:
        logger.warning(f"Missing API keys: {api_missing}")

    if not wp_valid:
        logger.warning(f"Missing WordPress config: {wp_missing}")

    return app_config, api_keys, wp_config
