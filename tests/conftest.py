"""Pytest configuration and fixtures."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing."""
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
def sample_topic():
    """Sample topic data for testing."""
    return {
        "topic": "Claude 3.5 Sonnet Released",
        "keywords": ["claude 3.5", "sonnet", "anthropic"],
        "source": "hacker_news",
        "score": 85,
        "suggested_title": "Claude 3.5 Sonnet Review: Everything You Need to Know",
    }


@pytest.fixture
def sample_content():
    """Sample content data for testing."""
    return {
        "title": "Claude 3.5 Sonnet Review: Everything You Need to Know",
        "html": """
        <h1>Claude 3.5 Sonnet Review: Everything You Need to Know</h1>
        <h2>Introduction</h2>
        <p>Lorem ipsum dolor sit amet...</p>
        <h2>Key Features</h2>
        <p>Lorem ipsum dolor sit amet...</p>
        <h2>Performance</h2>
        <p>Lorem ipsum dolor sit amet...</p>
        <h2>Pricing</h2>
        <p>Lorem ipsum dolor sit amet...</p>
        <h2>Conclusion</h2>
        <p>Lorem ipsum dolor sit amet...</p>
        <h2>FAQ</h2>
        <h3>What is Claude 3.5?</h3>
        <p>Lorem ipsum...</p>
        <h3>Is it free?</h3>
        <p>Lorem ipsum...</p>
        <h3>How to use it?</h3>
        <p>Lorem ipsum...</p>
        """,
        "meta_description": "Comprehensive review of Claude 3.5 Sonnet, Anthropic's latest AI model. Learn about features, performance, and pricing.",
        "keywords": ["claude 3.5", "sonnet", "anthropic"],
        "word_count": 2000,
    }


@pytest.fixture
def sample_images():
    """Sample image data for testing."""
    return [
        {
            "url": "https://images.unsplash.com/photo-1234",
            "alt": "AI artificial intelligence concept",
            "photographer": "John Doe",
            "source": "unsplash",
        },
        {
            "url": "https://images.unsplash.com/photo-5678",
            "alt": "Technology computer programming",
            "photographer": "Jane Doe",
            "source": "unsplash",
        },
        {
            "url": "https://images.unsplash.com/photo-9012",
            "alt": "Machine learning neural network",
            "photographer": "Bob Smith",
            "source": "unsplash",
        },
    ]
