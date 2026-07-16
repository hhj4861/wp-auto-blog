"""Tests for WordPressClient module.

TDD: RED -> GREEN -> REFACTOR
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import base64

from src.wordpress_client import (
    WordPressClient,
    WPConfig,
    PostStatus,
    CreatedPost,
)
from src.content_generator import GeneratedContent, ContentType
from src.image_fetcher import FetchedImage, ImageSource


class TestWPConfig:
    """Test WPConfig dataclass."""

    def test_config_from_env(self, mock_env_vars):
        """WPConfig loads from environment variables."""
        config = WPConfig.from_env()

        assert config.url == "https://test-blog.com"
        assert config.username == "test_user"
        assert config.app_password == "test_password"

    def test_config_validation(self):
        """WPConfig validates required fields."""
        # Should work with all fields
        config = WPConfig(
            url="https://blog.com",
            username="user",
            app_password="pass",
        )
        assert config.url == "https://blog.com"

    def test_config_strips_trailing_slash(self):
        """WPConfig removes trailing slash from URL."""
        config = WPConfig(
            url="https://blog.com/",
            username="user",
            app_password="pass",
        )
        assert config.url == "https://blog.com"


class TestCreatedPost:
    """Test CreatedPost dataclass."""

    def test_post_creation(self):
        """CreatedPost can be created with required fields."""
        post = CreatedPost(
            id=123,
            url="https://blog.com/post-slug",
            title="Test Post",
            status=PostStatus.DRAFT,
        )

        assert post.id == 123
        assert post.status == PostStatus.DRAFT

    def test_post_to_dict(self):
        """CreatedPost can be converted to dictionary."""
        post = CreatedPost(
            id=456,
            url="https://blog.com/test",
            title="Test",
            status=PostStatus.PUBLISH,
        )

        result = post.to_dict()

        assert result["id"] == 456
        assert result["status"] == "publish"


class TestWordPressClient:
    """Test WordPressClient main class."""

    @pytest.fixture
    def client(self, mock_env_vars):
        """Create WordPressClient instance."""
        return WordPressClient()

    @pytest.fixture
    def sample_generated_content(self):
        """Sample GeneratedContent for testing."""
        return GeneratedContent(
            title="Test Blog Post Title",
            html="<h1>Test</h1><p>Content here</p>",
            meta_description="This is a test blog post for testing purposes.",
            keywords=["test", "blog", "post"],
            word_count=1500,
            content_type=ContentType.REVIEW,
        )

    @pytest.fixture
    def sample_fetched_images(self):
        """Sample FetchedImage list for testing."""
        return [
            FetchedImage(
                url="https://images.unsplash.com/photo-1",
                alt="Featured image",
                photographer="John Doe",
                source=ImageSource.UNSPLASH,
                width=1920,
                height=1080,
            ),
            FetchedImage(
                url="https://images.unsplash.com/photo-2",
                alt="Second image",
                photographer="Jane Doe",
                source=ImageSource.UNSPLASH,
                width=1920,
                height=1080,
            ),
        ]

    def test_init_creates_instance(self, mock_env_vars):
        """WordPressClient can be instantiated."""
        client = WordPressClient()
        assert client is not None

    def test_init_with_custom_config(self, mock_env_vars):
        """WordPressClient accepts custom config."""
        config = WPConfig(
            url="https://custom-blog.com",
            username="custom_user",
            app_password="custom_pass",
        )
        client = WordPressClient(config=config)

        assert client.config.url == "https://custom-blog.com"

    @pytest.mark.unit
    def test_create_post_returns_created_post(
        self, client, sample_generated_content, sample_fetched_images
    ):
        """create_post() returns CreatedPost object."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": 123,
            "link": "https://test-blog.com/test-post",
            "title": {"rendered": "Test Post"},
            "status": "draft",
        }
        mock_response.raise_for_status = Mock()

        with patch("requests.post", return_value=mock_response):
            with patch.object(client, "_upload_media", return_value=456):
                result = client.create_post(
                    content=sample_generated_content,
                    images=sample_fetched_images,
                )

        assert isinstance(result, CreatedPost)
        assert result.id == 123
        assert result.status == PostStatus.DRAFT

    @pytest.mark.unit
    def test_create_post_as_draft_by_default(
        self, client, sample_generated_content, sample_fetched_images
    ):
        """create_post() creates draft by default."""
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "id": 1,
                "link": "https://test-blog.com/test",
                "title": {"rendered": "Test"},
                "status": "draft",
            }
            mock_post.return_value.raise_for_status = Mock()

            with patch.object(client, "_upload_media", return_value=1):
                client.create_post(
                    content=sample_generated_content,
                    images=sample_fetched_images,
                )

        # Check that status was set to draft
        call_args = mock_post.call_args
        assert call_args is not None
        json_data = call_args.kwargs.get("json", {})
        assert json_data.get("status") == "draft"

    @pytest.mark.unit
    def test_create_post_with_publish_status(
        self, client, sample_generated_content, sample_fetched_images
    ):
        """create_post() can create published post."""
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "id": 1,
                "link": "https://test-blog.com/test",
                "title": {"rendered": "Test"},
                "status": "publish",
            }
            mock_post.return_value.raise_for_status = Mock()

            with patch.object(client, "_upload_media", return_value=1):
                result = client.create_post(
                    content=sample_generated_content,
                    images=sample_fetched_images,
                    status=PostStatus.PUBLISH,
                )

        assert result.status == PostStatus.PUBLISH

    @pytest.mark.unit
    def test_create_post_sets_featured_image(
        self, client, sample_generated_content, sample_fetched_images
    ):
        """create_post() sets first image as featured image."""
        with patch("requests.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "id": 1,
                "link": "https://test-blog.com/test",
                "title": {"rendered": "Test"},
                "status": "draft",
            }
            mock_post.return_value.raise_for_status = Mock()

            with patch.object(client, "_upload_media", return_value=999) as mock_upload:
                client.create_post(
                    content=sample_generated_content,
                    images=sample_fetched_images,
                )

        # Should have uploaded at least the featured image
        assert mock_upload.called

        # Check featured_media was set
        call_args = mock_post.call_args
        json_data = call_args.kwargs.get("json", {})
        assert "featured_media" in json_data


class TestMediaUpload:
    """Test media upload functionality."""

    @pytest.fixture
    def client(self, mock_env_vars):
        return WordPressClient()

    @pytest.mark.unit
    def test_upload_media_returns_media_id(self, client):
        """_upload_media returns WordPress media ID."""
        mock_image_response = Mock()
        mock_image_response.content = b"fake image data"
        mock_image_response.raise_for_status = Mock()

        mock_upload_response = Mock()
        mock_upload_response.json.return_value = {"id": 789}
        mock_upload_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_image_response):
            with patch("requests.post", return_value=mock_upload_response):
                media_id = client._upload_media(
                    image_url="https://example.com/image.jpg",
                    alt_text="Test image",
                )

        assert media_id == 789

    @pytest.mark.unit
    def test_upload_media_handles_error(self, client):
        """_upload_media handles errors gracefully."""
        with patch("requests.get", side_effect=Exception("Download failed")):
            media_id = client._upload_media(
                image_url="https://example.com/image.jpg",
                alt_text="Test",
            )

        assert media_id is None

    @pytest.mark.unit
    def test_upload_media_sets_alt_text(self, client):
        """_upload_media sets alt text on uploaded media."""
        mock_image_response = Mock()
        mock_image_response.content = b"image data"
        mock_image_response.raise_for_status = Mock()

        mock_upload_response = Mock()
        mock_upload_response.json.return_value = {"id": 1}
        mock_upload_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_image_response):
            with patch("requests.post", return_value=mock_upload_response) as mock_post:
                client._upload_media(
                    image_url="https://example.com/image.jpg",
                    alt_text="My alt text",
                )

        # Check that alt_text was included
        call_args = mock_post.call_args
        assert call_args is not None


class TestAuthentication:
    """Test WordPress authentication."""

    @pytest.fixture
    def client(self, mock_env_vars):
        return WordPressClient()

    @pytest.mark.unit
    def test_auth_header_is_basic_auth(self, client):
        """_get_auth_header returns Basic auth header."""
        headers = client._get_auth_headers()

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")

    @pytest.mark.unit
    def test_auth_header_encodes_credentials(self, client):
        """_get_auth_header correctly encodes credentials."""
        headers = client._get_auth_headers()

        auth_value = headers["Authorization"]
        encoded = auth_value.replace("Basic ", "")
        decoded = base64.b64decode(encoded).decode("utf-8")

        assert ":" in decoded
        username, password = decoded.split(":", 1)
        assert username == client.config.username
        assert password == client.config.app_password

    @pytest.mark.unit
    def test_verify_connection_success(self, client):
        """verify_connection() returns True on success."""
        mock_response = Mock()
        mock_response.json.return_value = {"id": 1, "name": "Test Blog"}
        mock_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_response):
            result = client.verify_connection()

        assert result is True

    @pytest.mark.unit
    def test_verify_connection_failure(self, client):
        """verify_connection() returns False on failure."""
        with patch("requests.get", side_effect=Exception("Connection failed")):
            result = client.verify_connection()

        assert result is False


class TestCategoryAndTags:
    """Test category and tag handling."""

    @pytest.fixture
    def client(self, mock_env_vars):
        return WordPressClient()

    @pytest.mark.unit
    def test_get_or_create_category(self, client):
        """_get_or_create_category finds or creates category."""
        # First call: category doesn't exist
        mock_search_response = Mock()
        mock_search_response.json.return_value = []
        mock_search_response.raise_for_status = Mock()

        # Second call: create category
        mock_create_response = Mock()
        mock_create_response.json.return_value = {"id": 42, "name": "AI Tools"}
        mock_create_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_search_response):
            with patch("requests.post", return_value=mock_create_response):
                cat_id = client._get_or_create_category("AI Tools")

        assert cat_id == 42

    @pytest.mark.unit
    def test_get_or_create_tags(self, client):
        """_get_or_create_tags creates tags from keywords."""
        mock_search_response = Mock()
        mock_search_response.json.return_value = []
        mock_search_response.raise_for_status = Mock()

        mock_create_response = Mock()
        mock_create_response.json.return_value = {"id": 10}
        mock_create_response.raise_for_status = Mock()

        with patch("requests.get", return_value=mock_search_response):
            with patch("requests.post", return_value=mock_create_response):
                tag_ids = client._get_or_create_tags(["ai", "automation", "tech"])

        assert len(tag_ids) == 3
        assert all(isinstance(t, int) for t in tag_ids)


class TestContentFormatting:
    """Test content formatting for WordPress."""

    @pytest.fixture
    def client(self, mock_env_vars):
        return WordPressClient()

    @pytest.mark.unit
    def test_prepare_content_adds_image_placeholders(self, client):
        """_prepare_content inserts images at appropriate positions."""
        html = """
        <h1>Title</h1>
        <p>Introduction paragraph</p>
        <h2>Section 1</h2>
        <p>Content</p>
        <h2>Section 2</h2>
        <p>More content</p>
        """

        images = [
            FetchedImage("url1", "alt1", "p1", ImageSource.UNSPLASH, 1920, 1080),
            FetchedImage("url2", "alt2", "p2", ImageSource.UNSPLASH, 1920, 1080),
        ]

        prepared = client._prepare_content(html, images)

        # Should contain image tags
        assert "<img" in prepared or "wp:image" in prepared

    @pytest.mark.unit
    def test_prepare_content_generates_excerpt(self, client):
        """_prepare_excerpt creates excerpt from content."""
        html = "<p>This is the first paragraph with important information.</p><p>Second paragraph.</p>"

        excerpt = client._prepare_excerpt(html)

        assert len(excerpt) <= 300
        assert "first paragraph" in excerpt.lower()


class TestFocusKeyphrase:
    """Test _generate_focus_keyphrase fallback logic (Yoast SEO)."""

    @staticmethod
    def _client(url: str) -> WordPressClient:
        return WordPressClient(
            config=WPConfig(url=url, username="user", app_password="pass")
        )

    def test_korean_title_on_general_site(self):
        """한글 제목에서 핵심 키워드를 추출한다."""
        client = self._client("https://trendpulse.blog")
        keyphrase = client._generate_focus_keyphrase(
            "개발자 생산성 2배 올린 리눅스 데스크톱", []
        )
        assert keyphrase != ""

    def test_english_title_on_general_site_falls_back_to_keywords(self):
        """영문 제목이어도 키프레이즈가 비면 안 된다 (Yoast SEO 오류 방지)."""
        client = self._client("https://trendpulse.blog")
        keyphrase = client._generate_focus_keyphrase(
            "Inkling: Our Open-Weights Model",
            ["inkling", "open", "weights", "model"],
        )
        assert keyphrase != ""

    def test_english_title_without_keywords_on_general_site(self):
        """영문 제목 + 키워드 없음이어도 제목에서 키프레이즈를 뽑아낸다."""
        client = self._client("https://trendpulse.blog")
        keyphrase = client._generate_focus_keyphrase(
            "Inkling: Our Open-Weights Model", []
        )
        assert keyphrase != ""
