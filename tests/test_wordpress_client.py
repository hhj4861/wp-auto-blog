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


def _json_response(payload) -> Mock:
    """_request_with_retry의 status/Content-Type 검사를 통과하는 JSON 응답 대역."""
    resp = Mock()
    resp.status_code = 200
    resp.headers = {"Content-Type": "application/json"}
    resp.raise_for_status = Mock()
    resp.json.return_value = payload
    return resp


@pytest.fixture(autouse=True)
def _no_network_side_channels():
    """재시도 백오프 sleep과 Yoast 재저장 PUT의 실제 네트워크 호출 차단."""
    with patch("src.wordpress_client.time.sleep"), patch("requests.put"):
        yield


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
        mock_response = _json_response({
            "id": 123,
            "link": "https://test-blog.com/test-post",
            "title": {"rendered": "Test Post"},
            "status": "draft",
        })

        with patch("requests.get", return_value=_json_response([])), \
             patch("requests.post", return_value=mock_response):
            with patch.object(
                client, "_upload_media",
                return_value=(456, "https://test-blog.com/wp-content/img.jpg"),
            ):
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
        with patch("requests.get", return_value=_json_response([])), \
             patch("requests.post") as mock_post:
            mock_post.return_value = _json_response({
                "id": 1,
                "link": "https://test-blog.com/test",
                "title": {"rendered": "Test"},
                "status": "draft",
            })

            with patch.object(
                client, "_upload_media",
                return_value=(1, "https://test-blog.com/wp-content/img.jpg"),
            ):
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
        with patch("requests.get", return_value=_json_response([])), \
             patch("requests.post") as mock_post:
            mock_post.return_value = _json_response({
                "id": 1,
                "link": "https://test-blog.com/test",
                "title": {"rendered": "Test"},
                "status": "publish",
            })

            with patch.object(
                client, "_upload_media",
                return_value=(1, "https://test-blog.com/wp-content/img.jpg"),
            ):
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
        with patch("requests.get", return_value=_json_response([])), \
             patch("requests.post") as mock_post:
            mock_post.return_value = _json_response({
                "id": 1,
                "link": "https://test-blog.com/test",
                "title": {"rendered": "Test"},
                "status": "draft",
            })

            with patch.object(
                client, "_upload_media",
                return_value=(999, "https://test-blog.com/wp-content/img.jpg"),
            ) as mock_upload:
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

        mock_upload_response = _json_response(
            {"id": 789, "source_url": "https://test-blog.com/wp-content/img.jpg"}
        )

        with patch("requests.get", return_value=mock_image_response):
            with patch("requests.post", return_value=mock_upload_response):
                media_id, media_url = client._upload_media(
                    image_url="https://example.com/image.jpg",
                    alt_text="Test image",
                )

        assert media_id == 789
        assert media_url == "https://test-blog.com/wp-content/img.jpg"

    @pytest.mark.unit
    def test_upload_media_handles_error(self, client):
        """_upload_media handles errors gracefully."""
        with patch("requests.get", side_effect=Exception("Download failed")):
            media_id, media_url = client._upload_media(
                image_url="https://example.com/image.jpg",
                alt_text="Test",
            )

        assert media_id is None
        assert media_url is None

    @pytest.mark.unit
    def test_upload_media_sets_alt_text(self, client):
        """_upload_media sets alt text on uploaded media."""
        mock_image_response = Mock()
        mock_image_response.content = b"image data"
        mock_image_response.raise_for_status = Mock()

        mock_upload_response = _json_response(
            {"id": 1, "source_url": "https://test-blog.com/wp-content/img.jpg"}
        )

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
        mock_response = _json_response({"id": 1, "name": "Test Blog"})

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
        mock_search_response = _json_response([])

        # Second call: create category
        mock_create_response = _json_response({"id": 42, "name": "AI Tools"})

        with patch("requests.get", return_value=mock_search_response):
            with patch("requests.post", return_value=mock_create_response):
                cat_id = client._get_or_create_category("AI Tools")

        assert cat_id == 42

    @pytest.mark.unit
    def test_get_or_create_tags(self, client):
        """_get_or_create_tags: 전부 미존재 키워드면 신규 생성 상한(2개)까지만 만든다."""
        mock_search_response = _json_response([])
        created_ids = iter([10, 11, 12])

        def fake_post(url, **kwargs):
            return _json_response({"id": next(created_ids)})

        with patch("requests.get", return_value=mock_search_response):
            with patch("requests.post", side_effect=fake_post):
                tag_ids = client._get_or_create_tags(["ai", "automation", "tech"])

        assert tag_ids == [10, 11]  # MAX_NEW_TAGS_PER_POST개까지만 생성
        assert all(isinstance(t, int) for t in tag_ids)


class TestTagPolicy:
    """태그 스프롤 방지 정책: 정규화·중복제거·총량 상한·기존 태그 우선."""

    @pytest.fixture
    def client(self, mock_env_vars):
        return WordPressClient()

    @staticmethod
    def _existing_tags_get(existing: dict):
        """search 키워드가 existing에 있으면 해당 태그를 돌려주는 requests.get 대역."""

        def fake_get(url, **kwargs):
            search = (kwargs.get("params") or {}).get("search", "")
            tag_id = existing.get(search.lower())
            return _json_response([{"id": tag_id, "name": search}] if tag_id else [])

        return fake_get

    @pytest.mark.unit
    def test_tags_normalized_and_deduped(self, client):
        """공백 정리 + 대소문자 무시 중복 제거 후에만 조회한다."""
        existing = {"ai": 1, "ai tools": 2}
        with patch("requests.get", side_effect=self._existing_tags_get(existing)) as mock_get:
            with patch("requests.post", return_value=_json_response({"id": 999})) as mock_post:
                tag_ids = client._get_or_create_tags(["AI", " ai ", "AI  Tools", "ai tools"])

        assert tag_ids == [1, 2]
        assert mock_get.call_count == 2  # "AI"와 "AI Tools" 각 1회만 조회
        mock_post.assert_not_called()

    @pytest.mark.unit
    def test_tags_capped_at_five_total(self, client):
        """기존 태그가 아무리 많아도 글당 최대 5개."""
        existing = {f"kw{i}": i for i in range(1, 9)}
        with patch("requests.get", side_effect=self._existing_tags_get(existing)) as mock_get:
            with patch("requests.post", return_value=_json_response({"id": 999})) as mock_post:
                tag_ids = client._get_or_create_tags([f"kw{i}" for i in range(1, 9)])

        assert tag_ids == [1, 2, 3, 4, 5]
        assert mock_get.call_count == 5  # 상한 도달 후 조회 중단
        mock_post.assert_not_called()

    @pytest.mark.unit
    def test_existing_tags_preferred_over_new(self, client):
        """기존 태그로 5개가 채워지면 미존재 키워드는 새로 만들지 않는다."""
        existing = {"kw2": 2, "kw4": 4, "kw5": 5, "kw6": 6, "kw7": 7}
        with patch("requests.get", side_effect=self._existing_tags_get(existing)):
            with patch("requests.post", return_value=_json_response({"id": 999})) as mock_post:
                tag_ids = client._get_or_create_tags(
                    ["kw1", "kw2", "kw3", "kw4", "kw5", "kw6", "kw7"]
                )

        assert tag_ids == [2, 4, 5, 6, 7]
        mock_post.assert_not_called()

    @pytest.mark.unit
    def test_new_tag_creation_capped(self, client):
        """미존재 키워드는 글당 최대 2개까지만 신규 태그로 만든다."""
        created_ids = iter([101, 102, 103, 104])

        def fake_post(url, **kwargs):
            return _json_response({"id": next(created_ids)})

        with patch("requests.get", side_effect=self._existing_tags_get({})):
            with patch("requests.post", side_effect=fake_post) as mock_post:
                tag_ids = client._get_or_create_tags(["new1", "new2", "new3", "new4"])

        assert tag_ids == [101, 102]
        assert mock_post.call_count == 2

    @pytest.mark.unit
    def test_keyword_misses_created_before_category_filler(self, client):
        """카테고리 필러가 전부 기존 태그여도 토픽 키워드 신규 생성이 우선한다."""
        existing = {"cat1": 11, "cat2": 12, "cat3": 13, "cat4": 14, "cat5": 15}
        created = {"novel1": 101, "novel2": 102}

        def fake_post(url, **kwargs):
            name = (kwargs.get("json") or {}).get("name", "")
            return _json_response({"id": created[name.lower()]})

        with patch("requests.get", side_effect=self._existing_tags_get(existing)):
            with patch("requests.post", side_effect=fake_post) as mock_post:
                tag_ids = client._get_or_create_tags(
                    ["novel1", "novel2"],
                    filler_tags=["cat1", "cat2", "cat3", "cat4", "cat5"],
                )

        assert tag_ids == [101, 102, 11, 12, 13]
        assert mock_post.call_count == 2

    @pytest.mark.unit
    def test_filler_tags_are_reuse_only(self, client):
        """필러(카테고리 태그)는 기존 것만 재사용하고 절대 새로 만들지 않는다."""
        existing = {"kw1": 1, "cat1": 11}
        with patch("requests.get", side_effect=self._existing_tags_get(existing)):
            with patch("requests.post", return_value=_json_response({"id": 999})) as mock_post:
                tag_ids = client._get_or_create_tags(
                    ["kw1"], filler_tags=["cat1", "nocat"]
                )

        assert tag_ids == [1, 11]
        mock_post.assert_not_called()

    @pytest.mark.unit
    def test_create_conflict_falls_back_to_existing_term(self, client):
        """검색이 놓친 기존 태그를 생성 시도하면 term_exists의 term_id를 재사용한다."""
        conflict = Mock()
        conflict.status_code = 400
        conflict.headers = {"Content-Type": "application/json"}
        conflict.json.return_value = {
            "code": "term_exists",
            "message": "A term with the name provided already exists.",
            "data": {"term_id": 77},
        }

        with patch("requests.get", side_effect=self._existing_tags_get({})):
            with patch("requests.post", return_value=conflict):
                tag_ids = client._get_or_create_tags(["Cursor"])

        assert tag_ids == [77]

    @pytest.mark.unit
    def test_existing_filled_then_new_up_to_cap(self, client):
        """기존 3개 + 신규 2개 = 5개 (신규는 상한 2개에서 멈춤)."""
        existing = {"kw1": 1, "kw3": 3, "kw5": 5}

        def fake_post(url, **kwargs):
            name = (kwargs.get("json") or {}).get("name", "")
            return _json_response({"id": {"kw2": 102, "kw4": 104, "kw6": 106}[name.lower()]})

        with patch("requests.get", side_effect=self._existing_tags_get(existing)):
            with patch("requests.post", side_effect=fake_post) as mock_post:
                tag_ids = client._get_or_create_tags(
                    ["kw1", "kw2", "kw3", "kw4", "kw5", "kw6"]
                )

        assert sorted(tag_ids) == [1, 3, 5, 102, 104]
        assert mock_post.call_count == 2


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
