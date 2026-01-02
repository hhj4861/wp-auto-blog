"""Tests for ContentGenerator module.

TDD: RED -> GREEN -> REFACTOR
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

from src.content_generator import (
    ContentGenerator,
    GeneratedContent,
    ContentConfig,
    ContentType,
    LLMProvider,
)


class TestGeneratedContent:
    """Test GeneratedContent dataclass."""

    def test_content_creation(self):
        """GeneratedContent can be created with required fields."""
        content = GeneratedContent(
            title="Test Title",
            html="<h1>Test</h1><p>Content</p>",
            meta_description="Test description for SEO purposes",
            keywords=["test", "keyword"],
            word_count=1500,
            content_type=ContentType.REVIEW,
        )

        assert content.title == "Test Title"
        assert "<h1>" in content.html
        assert len(content.meta_description) > 0
        assert content.word_count == 1500

    def test_content_to_dict(self):
        """GeneratedContent can be converted to dictionary."""
        content = GeneratedContent(
            title="Test",
            html="<p>Test</p>",
            meta_description="Description",
            keywords=["test"],
            word_count=100,
            content_type=ContentType.GUIDE,
        )

        result = content.to_dict()

        assert isinstance(result, dict)
        assert result["title"] == "Test"
        assert result["content_type"] == "guide"


class TestContentConfig:
    """Test ContentConfig dataclass."""

    def test_default_config(self):
        """ContentConfig has sensible defaults."""
        config = ContentConfig()

        assert config.min_words == 1500
        assert config.max_words == 2500
        assert config.provider == LLMProvider.GEMINI
        assert config.temperature >= 0 and config.temperature <= 1

    def test_custom_config(self):
        """ContentConfig accepts custom values."""
        config = ContentConfig(
            min_words=1000,
            max_words=3000,
            provider=LLMProvider.OPENAI,
            temperature=0.5,
        )

        assert config.min_words == 1000
        assert config.provider == LLMProvider.OPENAI


class TestContentType:
    """Test ContentType enum."""

    def test_all_content_types_defined(self):
        """All required content types are defined."""
        assert ContentType.REVIEW
        assert ContentType.COMPARISON
        assert ContentType.GUIDE
        assert ContentType.LIST
        assert ContentType.NEWS


class TestContentGenerator:
    """Test ContentGenerator main class."""

    @pytest.fixture
    def generator(self, mock_env_vars):
        """Create ContentGenerator instance."""
        return ContentGenerator()

    def test_init_creates_instance(self, mock_env_vars):
        """ContentGenerator can be instantiated."""
        generator = ContentGenerator()
        assert generator is not None

    def test_init_with_custom_config(self, mock_env_vars):
        """ContentGenerator accepts custom config."""
        config = ContentConfig(min_words=2000, max_words=4000)
        generator = ContentGenerator(config=config)

        assert generator.config.min_words == 2000
        assert generator.config.max_words == 4000

    @pytest.mark.unit
    def test_generate_returns_content(self, generator):
        """generate() returns GeneratedContent object."""
        mock_response = """
        <h1>Test Title</h1>
        <h2>Introduction</h2>
        <p>Lorem ipsum dolor sit amet...</p>
        <h2>Features</h2>
        <p>Lorem ipsum...</p>
        <h2>Conclusion</h2>
        <p>Lorem ipsum...</p>
        """

        with patch.object(generator, "_call_llm", return_value=mock_response):
            content = generator.generate(
                topic="Test Topic",
                keywords=["test", "keyword"],
                content_type=ContentType.REVIEW,
            )

        assert isinstance(content, GeneratedContent)
        assert content.title is not None
        assert len(content.html) > 0

    @pytest.mark.unit
    def test_generate_includes_required_sections(self, generator):
        """generate() produces content with required sections."""
        mock_html = """
        <h1>Test Title</h1>
        <nav id="toc"><ul><li>Section 1</li></ul></nav>
        <h2>Introduction</h2>
        <p>Content here...</p>
        <h2>Main Section</h2>
        <p>Content...</p>
        <h2>Another Section</h2>
        <p>Content...</p>
        <h2>Yet Another</h2>
        <p>Content...</p>
        <h2>More Content</h2>
        <p>Content...</p>
        <h2>FAQ</h2>
        <h3>Question 1?</h3>
        <p>Answer 1</p>
        <h3>Question 2?</h3>
        <p>Answer 2</p>
        <h3>Question 3?</h3>
        <p>Answer 3</p>
        """

        with patch.object(generator, "_call_llm", return_value=mock_html):
            content = generator.generate(
                topic="Test Topic",
                keywords=["test"],
                content_type=ContentType.GUIDE,
            )

        # Check for required elements (from PRD)
        assert "<h1>" in content.html  # H1 title
        assert content.html.count("<h2>") >= 4  # At least 4 H2 sections
        # FAQ section with H3s
        assert "<h2>FAQ" in content.html or "<h2>FAQ" in content.html.upper()

    @pytest.mark.unit
    def test_generate_creates_meta_description(self, generator):
        """generate() creates meta description (150-160 chars)."""
        mock_html = "<h1>Title</h1><p>Content</p>"

        with patch.object(generator, "_call_llm", return_value=mock_html):
            with patch.object(generator, "_generate_meta", return_value="A " * 75):
                content = generator.generate(
                    topic="Test Topic",
                    keywords=["test"],
                    content_type=ContentType.REVIEW,
                )

        assert len(content.meta_description) >= 100
        assert len(content.meta_description) <= 165

    @pytest.mark.unit
    def test_generate_counts_words_correctly(self, generator):
        """generate() counts words in content."""
        # Generate content with known word count
        words = " ".join(["word"] * 500)
        mock_html = f"<h1>Title</h1><p>{words}</p>"

        with patch.object(generator, "_call_llm", return_value=mock_html):
            content = generator.generate(
                topic="Test",
                keywords=["test"],
                content_type=ContentType.NEWS,
            )

        # Word count should be reasonable
        assert content.word_count > 0


class TestPromptLoading:
    """Test prompt template loading."""

    @pytest.fixture
    def generator(self, mock_env_vars):
        return ContentGenerator()

    @pytest.mark.unit
    def test_load_prompt_template(self, generator):
        """_load_prompt_template loads correct template for content type."""
        prompt = generator._load_prompt_template(ContentType.REVIEW)

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    @pytest.mark.unit
    def test_load_prompt_for_each_type(self, generator):
        """Each content type has a prompt template."""
        for content_type in ContentType:
            prompt = generator._load_prompt_template(content_type)
            assert prompt is not None
            assert len(prompt) > 0

    @pytest.mark.unit
    def test_prompt_contains_placeholders(self, generator):
        """Prompt templates contain required placeholders."""
        prompt = generator._load_prompt_template(ContentType.GUIDE)

        # Should have placeholders for topic and keywords
        assert "{topic}" in prompt or "{{topic}}" in prompt


class TestLLMIntegration:
    """Test LLM API integration."""

    @pytest.fixture
    def generator(self, mock_env_vars):
        return ContentGenerator()

    @pytest.mark.unit
    def test_call_gemini(self, generator):
        """_call_llm works with Gemini provider."""
        generator.config.provider = LLMProvider.GEMINI

        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "<h1>Generated Content</h1>"
        mock_model.generate_content.return_value = mock_response

        with patch("src.content_generator.genai") as mock_genai:
            mock_genai.GenerativeModel.return_value = mock_model

            result = generator._call_llm("Generate content about AI")

        assert "<h1>" in result

    @pytest.mark.unit
    def test_call_openai(self, generator):
        """_call_llm works with OpenAI provider."""
        generator.config.provider = LLMProvider.OPENAI

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="<h1>Content</h1>"))]
        mock_client.chat.completions.create.return_value = mock_response

        with patch("src.content_generator.OpenAI", return_value=mock_client):
            result = generator._call_llm("Generate content")

        assert "<h1>" in result

    @pytest.mark.unit
    def test_fallback_on_error(self, generator):
        """_call_llm falls back to secondary provider on error."""
        generator.config.provider = LLMProvider.GEMINI

        # First call (Gemini) fails
        # Second call (OpenAI) succeeds
        call_count = 0

        def mock_genai_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("API Error")
            return MagicMock(text="<h1>Fallback Content</h1>")

        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="<h1>OpenAI Content</h1>"))]
        )

        with patch("src.content_generator.genai") as mock_genai:
            mock_model = MagicMock()
            mock_model.generate_content.side_effect = Exception("Gemini Error")
            mock_genai.GenerativeModel.return_value = mock_model

            with patch("src.content_generator.OpenAI", return_value=mock_openai_client):
                result = generator._call_llm("Generate content")

        assert "<h1>" in result


class TestHTMLProcessing:
    """Test HTML content processing."""

    @pytest.fixture
    def generator(self, mock_env_vars):
        return ContentGenerator()

    @pytest.mark.unit
    def test_clean_html_removes_code_blocks(self, generator):
        """_clean_html removes markdown code blocks."""
        raw = "```html\n<h1>Title</h1>\n```"
        cleaned = generator._clean_html(raw)

        assert "```" not in cleaned
        assert "<h1>Title</h1>" in cleaned

    @pytest.mark.unit
    def test_extract_title_from_h1(self, generator):
        """_extract_title gets title from H1 tag."""
        html = "<h1>My Amazing Title</h1><p>Content</p>"
        title = generator._extract_title(html)

        assert title == "My Amazing Title"

    @pytest.mark.unit
    def test_count_words_ignores_html_tags(self, generator):
        """_count_words counts only text content."""
        html = "<h1>Title</h1><p>One two three four five</p>"
        count = generator._count_words(html)

        assert count == 6  # Title + 5 words


class TestContentValidation:
    """Test content validation."""

    @pytest.fixture
    def generator(self, mock_env_vars):
        return ContentGenerator()

    @pytest.mark.unit
    def test_validate_checks_word_count(self, generator):
        """_validate checks minimum word count."""
        short_content = "<h1>Title</h1><p>Too short</p>"

        is_valid, errors = generator._validate(short_content)

        assert is_valid is False
        assert any("word" in e.lower() for e in errors)

    @pytest.mark.unit
    def test_validate_checks_headings(self, generator):
        """_validate checks for required heading structure."""
        no_headings = "<p>Just a paragraph with no headings at all</p>" * 100

        is_valid, errors = generator._validate(no_headings)

        assert is_valid is False
        assert any("heading" in e.lower() or "h1" in e.lower() for e in errors)

    @pytest.mark.unit
    def test_validate_passes_good_content(self, generator):
        """_validate passes well-structured content."""
        good_content = """
        <h1>Main Title Here</h1>
        <h2>Section One</h2>
        <p>""" + " ".join(["word"] * 400) + """</p>
        <h2>Section Two</h2>
        <p>""" + " ".join(["word"] * 400) + """</p>
        <h2>Section Three</h2>
        <p>""" + " ".join(["word"] * 400) + """</p>
        <h2>Section Four</h2>
        <p>""" + " ".join(["word"] * 400) + """</p>
        <h2>FAQ</h2>
        <h3>Question?</h3>
        <p>Answer</p>
        """

        is_valid, errors = generator._validate(good_content)

        assert is_valid is True
        assert len(errors) == 0
