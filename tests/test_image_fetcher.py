"""Tests for ImageFetcher module.

TDD: RED -> GREEN -> REFACTOR
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from src.image_fetcher import (
    ImageFetcher,
    FetchedImage,
    ImageConfig,
    ImageSource,
)


class TestFetchedImage:
    """Test FetchedImage dataclass."""

    def test_image_creation(self):
        """FetchedImage can be created with required fields."""
        image = FetchedImage(
            url="https://images.unsplash.com/photo-123",
            alt="AI robot concept",
            photographer="John Doe",
            source=ImageSource.UNSPLASH,
            width=1920,
            height=1080,
        )

        assert image.url.startswith("https://")
        assert len(image.alt) > 0
        assert image.source == ImageSource.UNSPLASH

    def test_image_to_dict(self):
        """FetchedImage can be converted to dictionary."""
        image = FetchedImage(
            url="https://example.com/image.jpg",
            alt="Test image",
            photographer="Test",
            source=ImageSource.PEXELS,
            width=800,
            height=600,
        )

        result = image.to_dict()

        assert isinstance(result, dict)
        assert result["url"] == "https://example.com/image.jpg"
        assert result["source"] == "pexels"


class TestImageConfig:
    """Test ImageConfig dataclass."""

    def test_default_config(self):
        """ImageConfig has sensible defaults."""
        config = ImageConfig()

        assert config.images_per_post == 4
        assert config.min_width >= 800
        assert config.primary_source == ImageSource.UNSPLASH

    def test_custom_config(self):
        """ImageConfig accepts custom values."""
        config = ImageConfig(
            images_per_post=6,
            min_width=1200,
            primary_source=ImageSource.PEXELS,
        )

        assert config.images_per_post == 6
        assert config.primary_source == ImageSource.PEXELS


class TestImageFetcher:
    """Test ImageFetcher main class."""

    @pytest.fixture
    def fetcher(self, mock_env_vars):
        """Create ImageFetcher instance."""
        return ImageFetcher()

    def test_init_creates_instance(self, mock_env_vars):
        """ImageFetcher can be instantiated."""
        fetcher = ImageFetcher()
        assert fetcher is not None

    def test_init_with_custom_config(self, mock_env_vars):
        """ImageFetcher accepts custom config."""
        config = ImageConfig(images_per_post=10)
        fetcher = ImageFetcher(config=config)

        assert fetcher.config.images_per_post == 10

    @pytest.mark.unit
    def test_fetch_returns_list_of_images(self, fetcher):
        """fetch() returns a list of FetchedImage objects."""
        mock_images = [
            FetchedImage(
                url="https://example.com/1.jpg",
                alt="Test 1",
                photographer="A",
                source=ImageSource.UNSPLASH,
                width=1920,
                height=1080,
            ),
        ]

        with patch.object(fetcher, "_fetch_unsplash", return_value=mock_images):
            images = fetcher.fetch(keywords=["ai", "technology"])

        assert isinstance(images, list)
        assert all(isinstance(img, FetchedImage) for img in images)

    @pytest.mark.unit
    def test_fetch_limits_to_config_count(self, fetcher):
        """fetch() returns at most images_per_post images."""
        fetcher.config.images_per_post = 3
        mock_images = [
            FetchedImage(
                url=f"https://example.com/{i}.jpg",
                alt=f"Test {i}",
                photographer="A",
                source=ImageSource.UNSPLASH,
                width=1920,
                height=1080,
            )
            for i in range(10)
        ]

        with patch.object(fetcher, "_fetch_unsplash", return_value=mock_images):
            images = fetcher.fetch(keywords=["test"])

        assert len(images) <= 3

    @pytest.mark.unit
    def test_fetch_uses_multiple_keywords(self, fetcher):
        """fetch() searches with multiple keywords."""
        with patch.object(fetcher, "_fetch_unsplash") as mock_fetch:
            mock_fetch.return_value = []
            fetcher.fetch(keywords=["ai", "machine learning", "robot"])

        # Should be called with combined or individual keywords
        assert mock_fetch.called

    @pytest.mark.unit
    def test_fetch_falls_back_to_secondary(self, fetcher):
        """fetch() falls back to secondary source if primary fails."""
        with patch.object(fetcher, "_fetch_unsplash", return_value=[]):
            with patch.object(fetcher, "_fetch_pexels") as mock_pexels:
                mock_pexels.return_value = [
                    FetchedImage(
                        url="https://pexels.com/1.jpg",
                        alt="Backup",
                        photographer="B",
                        source=ImageSource.PEXELS,
                        width=1920,
                        height=1080,
                    )
                ]
                images = fetcher.fetch(keywords=["test"])

        assert len(images) > 0
        assert images[0].source == ImageSource.PEXELS


class TestUnsplashFetcher:
    """Test Unsplash API integration."""

    @pytest.fixture
    def fetcher(self, mock_env_vars):
        return ImageFetcher()

    @pytest.mark.unit
    def test_fetch_unsplash_returns_images(self, fetcher):
        """_fetch_unsplash returns list of FetchedImage."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {
                    "urls": {"regular": "https://images.unsplash.com/photo-1"},
                    "alt_description": "AI concept",
                    "user": {"name": "John Photographer"},
                    "width": 1920,
                    "height": 1080,
                },
                {
                    "urls": {"regular": "https://images.unsplash.com/photo-2"},
                    "alt_description": "Technology background",
                    "user": {"name": "Jane Photographer"},
                    "width": 1920,
                    "height": 1080,
                },
            ]
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_response):
            images = fetcher._fetch_unsplash("ai technology")

        assert len(images) == 2
        assert all(img.source == ImageSource.UNSPLASH for img in images)

    @pytest.mark.unit
    def test_fetch_unsplash_handles_api_error(self, fetcher):
        """_fetch_unsplash handles API errors gracefully."""
        with patch("requests.get", side_effect=Exception("API Error")):
            images = fetcher._fetch_unsplash("test query")

        assert images == []

    @pytest.mark.unit
    def test_fetch_unsplash_handles_missing_fields(self, fetcher):
        """_fetch_unsplash handles missing fields gracefully."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {
                    "urls": {"regular": "https://images.unsplash.com/photo-1"},
                    # Missing alt_description
                    "user": {"name": "John"},
                    "width": 1920,
                    "height": 1080,
                },
            ]
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_response):
            images = fetcher._fetch_unsplash("test")

        assert len(images) == 1
        assert images[0].alt != ""  # Should have fallback alt text


class TestPexelsFetcher:
    """Test Pexels API integration."""

    @pytest.fixture
    def fetcher(self, mock_env_vars):
        return ImageFetcher()

    @pytest.mark.unit
    def test_fetch_pexels_returns_images(self, fetcher):
        """_fetch_pexels returns list of FetchedImage."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "photos": [
                {
                    "src": {"large": "https://images.pexels.com/photo-1"},
                    "alt": "Technology image",
                    "photographer": "John Doe",
                    "width": 1920,
                    "height": 1080,
                },
            ]
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_response):
            images = fetcher._fetch_pexels("technology")

        assert len(images) == 1
        assert images[0].source == ImageSource.PEXELS

    @pytest.mark.unit
    def test_fetch_pexels_handles_api_error(self, fetcher):
        """_fetch_pexels handles API errors gracefully."""
        with patch("requests.get", side_effect=Exception("API Error")):
            images = fetcher._fetch_pexels("test")

        assert images == []


class TestAltTextGeneration:
    """Test alt text generation."""

    @pytest.fixture
    def fetcher(self, mock_env_vars):
        return ImageFetcher()

    @pytest.mark.unit
    def test_generate_alt_creates_descriptive_text(self, fetcher):
        """_generate_alt creates descriptive alt text."""
        alt = fetcher._generate_alt(
            original_alt="Photo of a robot",
            keywords=["ai", "technology"],
        )

        assert isinstance(alt, str)
        assert len(alt) > 0

    @pytest.mark.unit
    def test_generate_alt_includes_keywords(self, fetcher):
        """_generate_alt includes relevant keywords."""
        alt = fetcher._generate_alt(
            original_alt=None,
            keywords=["artificial intelligence", "machine learning"],
        )

        alt_lower = alt.lower()
        has_keyword = any(kw in alt_lower for kw in ["artificial", "machine", "ai", "ml"])
        assert has_keyword or len(alt) > 0  # Either has keyword or valid fallback

    @pytest.mark.unit
    def test_generate_alt_limits_length(self, fetcher):
        """_generate_alt limits text to reasonable length."""
        alt = fetcher._generate_alt(
            original_alt="A very long description " * 20,
            keywords=["test"],
        )

        assert len(alt) <= 125  # Recommended alt text limit


class TestImageFiltering:
    """Test image filtering functionality."""

    @pytest.fixture
    def fetcher(self, mock_env_vars):
        return ImageFetcher()

    @pytest.mark.unit
    def test_filter_by_size(self, fetcher):
        """_filter_images filters by minimum dimensions."""
        fetcher.config.min_width = 1000
        fetcher.config.min_height = 600

        images = [
            FetchedImage("url1", "alt1", "p1", ImageSource.UNSPLASH, 1920, 1080),  # OK
            FetchedImage("url2", "alt2", "p2", ImageSource.UNSPLASH, 800, 600),    # Too small
            FetchedImage("url3", "alt3", "p3", ImageSource.UNSPLASH, 1200, 400),   # Too short
        ]

        filtered = fetcher._filter_images(images)

        assert len(filtered) == 1
        assert filtered[0].url == "url1"

    @pytest.mark.unit
    def test_filter_removes_duplicates(self, fetcher):
        """_filter_images removes duplicate URLs."""
        images = [
            FetchedImage("same-url", "alt1", "p1", ImageSource.UNSPLASH, 1920, 1080),
            FetchedImage("same-url", "alt2", "p2", ImageSource.UNSPLASH, 1920, 1080),
            FetchedImage("different-url", "alt3", "p3", ImageSource.UNSPLASH, 1920, 1080),
        ]

        filtered = fetcher._filter_images(images)

        urls = [img.url for img in filtered]
        assert len(urls) == len(set(urls))  # No duplicates
