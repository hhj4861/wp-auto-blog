"""Tests for ContentGenerator module.

TDD: RED -> GREEN -> REFACTOR
"""

import pytest
import json
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

        assert config.min_words == 800  # Substantial but scannable content
        assert config.max_words == 1500
        assert config.provider == LLMProvider.ANTHROPIC  # Claude CLI is default
        assert config.temperature >= 0 and config.temperature <= 1
        assert config.use_cli is True  # CLI mode by default

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


class TestMarketEvidenceRepair:
    """Market articles get one source-only correction and the same evidence gate again."""

    @pytest.fixture
    def setup_writer(self, mock_env_vars, monkeypatch):
        monkeypatch.setenv('BLOG_WRITER_PROVIDER', 'anthropic')
        monkeypatch.delenv('BLOG_OFFICIAL_SOURCE_URLS', raising=False)
        with patch.object(ContentGenerator, '_setup_apis'):
            generator = ContentGenerator(config=ContentConfig(language='ko'))
        source = {
            'url': 'https://www.gccity.go.kr/ghc/guide', 'original_url': 'https://www.gccity.go.kr/ghc/guide',
            'title': '공식 안내', 'checked_on': '2026-09-10', 'sha256': 'verified',
            'excerpt': '당화혈색소 정상수치는 5.7% 미만입니다.',
        }
        brief = {'keyword': '당화혈색소정상수치', 'topic': '당화혈색소정상수치: 기준 확인',
                 'intent': '정상 기준은 무엇인가요?', 'gap': '정상 기준 설명',
                 'source_url': source['url'], 'verified_sources': [source]}
        article = (
            '---SEO-META---\nFOCUS_KEYPHRASE: 당화혈색소정상수치\n'
            'META_DESCRIPTION: 당화혈색소정상수치를 제공된 공식 자료의 정상 기준으로 확인합니다.\n'
            'SLUG: hba1c-normal-range\n---CONTENT---\n'
            '<h1>당화혈색소정상수치: 기준 확인</h1>'
            '<section id="quick-answer"><p>당화혈색소정상수치를 확인하세요.</p></section>'
            '<h2 id="normal">정상 기준</h2><p>제공되지 않은 NIDDK 주장입니다.</p>'
            '<h2 id="faq">FAQ</h2><h3 id="what">무엇인가요?</h3><p>확인한 기준을 정리합니다.</p>'
        )
        monkeypatch.setattr('src.market_topics.fresh_market_item', lambda *args: True)
        monkeypatch.setattr('src.content_generator.fetch_source', lambda *args: dict(source))
        monkeypatch.setattr(generator, '_validate', lambda html: (True, []))
        monkeypatch.setattr(generator, 'research_with_grounding', Mock(side_effect=AssertionError('No extra research')))
        return generator, source, brief, article

    @pytest.mark.parametrize('remaining_issues', [[], ['아직 제공되지 않은 주장']])
    def test_market_evidence_repair_rechecks_once_and_keeps_remaining_issues(self, setup_writer, remaining_issues):
        generator, source, brief, article = setup_writer
        reviews = iter([['제공되지 않은 NIDDK 주장 삭제'], remaining_issues])
        prompts = []

        def writer(prompt):
            prompts.append(prompt)
            if prompt.startswith('You are a conservative Korean editorial fact checker.'):
                return json.dumps({'issues': next(reviews)}, ensure_ascii=False)
            if prompt.startswith('You are correcting an existing Korean article'):
                data = json.loads(prompt.split('\n', 1)[1])
                assert data['issues'] == ['제공되지 않은 NIDDK 주장 삭제']
                assert data['sources'][0]['excerpt'] == source['excerpt']
                return data['article'].replace('제공되지 않은 NIDDK 주장입니다.', source['excerpt'])
            return article

        with patch.object(generator, '_call_llm', side_effect=writer):
            content = generator.generate(brief['topic'], [brief['keyword']], ContentType.GUIDE,
                                         category='건강', market_brief=brief)

        assert len(prompts) == 4  # initial writer, review, one correction, final review
        assert 'NIDDK' not in content.html
        assert source['excerpt'] in content.html
        assert content.editorial_issues == remaining_issues
        assert content.word_count == generator._count_words(content.html)
        assert content.focus_keyphrase == brief['keyword']

    def test_market_evidence_repair_failure_preserves_original_draft_issues(self, setup_writer):
        generator, _, brief, article = setup_writer
        with patch.object(generator, '_call_llm', side_effect=[
            article, '{"issues":["제공되지 않은 주장"]}', 'not HTML',
        ]) as writer:
            content = generator.generate(brief['topic'], [brief['keyword']], ContentType.GUIDE,
                                         category='건강', market_brief=brief)
        assert writer.call_count == 3
        assert 'NIDDK' in content.html
        assert content.editorial_issues == ['제공되지 않은 주장', '근거 보완 실패 — 자동 발행 보류 (invalid_html)']

    def test_market_evidence_repair_reviews_metadata_both_times_without_changing_it(self, setup_writer):
        generator, source, brief, article = setup_writer
        article = article.replace('당화혈색소정상수치를 제공된 공식 자료의 정상 기준으로 확인합니다.',
                                  '제공되지 않은 <특별효과> & 주장입니다.')
        reviewed = []

        def writer(prompt):
            if prompt.startswith('You are a conservative Korean editorial fact checker.'):
                reviewed.append(json.loads(prompt.split('\n', 1)[1])['article'])
                return '{"issues":["메타 설명의 효과는 제공된 근거에 없음"]}'
            if prompt.startswith('You are correcting an existing Korean article'):
                data = json.loads(prompt.split('\n', 1)[1])
                assert 'data-review-metadata' not in data['article']
                return data['article'].replace('제공되지 않은 NIDDK 주장입니다.', source['excerpt'])
            return article

        with patch.object(generator, '_call_llm', side_effect=writer) as call:
            content = generator.generate(brief['topic'], [brief['keyword']], ContentType.GUIDE,
                                         category='건강', market_brief=brief)
        assert call.call_count == 4
        assert len(reviewed) == 2
        assert all('제목: 당화혈색소정상수치: 기준 확인' in value for value in reviewed)
        assert all('메타 설명: 제공되지 않은 &lt;특별효과&gt; &amp; 주장입니다.' in value for value in reviewed)
        assert content.editorial_issues == ['메타 설명의 효과는 제공된 근거에 없음']
        assert 'data-review-metadata' not in content.html

    def test_market_evidence_repair_skipped_when_initial_review_passes(self, setup_writer):
        generator, _, brief, article = setup_writer
        with patch.object(generator, '_call_llm', side_effect=[article, '{"issues":[]}']) as writer, \
             patch('src.content_generator.repair_evidence') as repair:
            content = generator.generate(brief['topic'], [brief['keyword']], ContentType.GUIDE,
                                         category='건강', market_brief=brief)
        assert writer.call_count == 2
        repair.assert_not_called()
        assert content.editorial_issues == []

    def test_market_evidence_repair_does_not_change_nonmarket_writer(self, setup_writer):
        generator, source, brief, article = setup_writer

        def research(**kwargs):
            generator._research_sources = [source]
            return ''

        with patch.object(generator, 'research_with_grounding', side_effect=research), \
             patch.object(generator, '_call_llm', side_effect=[article, '{"issues":["검수 이슈"]}']) as writer, \
             patch('src.content_generator.repair_evidence') as repair:
            content = generator.generate(brief['topic'], [brief['keyword']], ContentType.GUIDE, category='건강')
        assert writer.call_count == 2
        repair.assert_not_called()
        assert content.editorial_issues == ['검수 이슈']


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
        """_call_llm works with Gemini provider (new google.genai API)."""
        generator.config.provider = LLMProvider.GEMINI

        # Mock the new google.genai client
        mock_response = MagicMock()
        mock_response.text = "<h1>Generated Content</h1>"

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        generator._gemini_client = mock_client

        result = generator._call_llm("Generate content about AI")

        assert "<h1>" in result
        mock_client.models.generate_content.assert_called_once()

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

        # Mock Gemini client to fail
        mock_gemini_client = MagicMock()
        mock_gemini_client.models.generate_content.side_effect = Exception("Gemini Error")
        generator._gemini_client = mock_gemini_client

        # Mock Anthropic CLI to also fail (so it falls back to OpenAI)
        mock_cli_fail = MagicMock(side_effect=Exception("CLI not available"))

        # Mock OpenAI to succeed
        mock_openai_client = MagicMock()
        mock_openai_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="<h1>OpenAI Content</h1>"))]
        )

        with patch.object(generator, "_call_anthropic_cli", mock_cli_fail):
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


class TestGeneralModeSEOBlock:
    """general(ko) 모드 SEO-META 블록 생성/파싱 테스트."""

    @pytest.fixture
    def generator(self, mock_env_vars):
        return ContentGenerator(config=ContentConfig(language="ko"))

    def test_ko_review_prompt_includes_seo_meta_block(self, generator):
        """ko REVIEW 프롬프트에 SEO-META 출력 형식이 포함된다."""
        prompt = generator._load_prompt_template(ContentType.REVIEW)
        assert "---SEO-META---" in prompt
        assert "FOCUS_KEYPHRASE" in prompt
        assert "META_DESCRIPTION" in prompt

    def test_generate_parses_seo_block_in_general_mode(self, generator):
        """general 모드에서 SEO-META 블록을 파싱해 focus_keyphrase를 채운다."""
        mock_response = (
            "---SEO-META---\n"
            "FOCUS_KEYPHRASE: 리눅스 데스크톱\n"
            "META_DESCRIPTION: 리눅스 데스크톱으로 개발 생산성을 높이는 실전 방법을 "
            "정리했습니다. 설치부터 활용 팁까지 한 번에 확인하세요.\n"
            "---CONTENT---\n"
            "<h1>리눅스 데스크톱 완벽 가이드</h1>\n"
            "<h2>리눅스 데스크톱 소개</h2><p>내용</p>\n"
            "<h2>설치 방법</h2><p>내용</p>\n"
            "<h2>리눅스 데스크톱 활용 팁</h2><p>내용</p>\n"
            "<h2>FAQ</h2><p>질문과 답변</p>\n"
        )
        with patch.object(generator, "research_with_grounding", return_value=""), \
             patch.object(generator, "_call_llm", return_value=mock_response):
            content = generator.generate(
                topic="리눅스 데스크톱",
                keywords=["리눅스", "데스크톱"],
                content_type=ContentType.REVIEW,
                mode="general",
            )

        assert content.focus_keyphrase == "리눅스 데스크톱"
        assert "---SEO-META---" not in content.html
        assert "FOCUS_KEYPHRASE" not in content.html


class TestShortenTitle:
    """_shorten_title: 영어 제목의 최후 fallback이 단어 경계로 최대한 채워야 한다."""

    @pytest.fixture
    def generator(self, mock_env_vars):
        return ContentGenerator()

    @pytest.mark.unit
    def test_english_title_fills_to_max_length(self, generator):
        """앞 3~4단어 절단('7 Best Korean Eye')이 아니라 상한까지 채운다."""
        title = "7 Best Korean Eye Patches for Depuffing & Glowing Skin in 2026"
        result = generator._shorten_title(title, max_length=50)
        assert len(result) <= 50
        assert result.startswith("7 Best Korean Eye Patches"), result
        assert len(result) >= 30, f"너무 짧게 잘림: {result!r}"

    @pytest.mark.unit
    def test_no_trailing_connector_word(self, generator):
        """축약 결과가 for/&/in 같은 연결어로 끝나지 않는다."""
        title = "10 Amazing Korean Street Food Spots for Late Night Eating in Seoul 2026"
        result = generator._shorten_title(title, max_length=45)
        assert len(result) <= 45
        assert result.split()[-1].lower() not in {"for", "&", "and", "in", "with", "to", "of", "the"}, result

    @pytest.mark.unit
    def test_short_title_unchanged(self, generator):
        assert generator._shorten_title("Short Title 2026", max_length=50) == "Short Title 2026"
