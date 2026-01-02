"""Content Generator module for AI-powered blog content creation.

Generates SEO-optimized blog posts using LLM APIs.

FR-002: Content Generation
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    import google.generativeai as genai
except ImportError:
    genai = None  # type: ignore

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore


class ContentType(Enum):
    """Types of blog content."""

    REVIEW = "review"
    COMPARISON = "comparison"
    GUIDE = "guide"
    LIST = "list"
    NEWS = "news"


class LLMProvider(Enum):
    """LLM API providers."""

    GEMINI = "gemini"
    OPENAI = "openai"


@dataclass
class GeneratedContent:
    """Represents generated blog content.

    Attributes:
        title: The blog post title
        html: Full HTML content
        meta_description: SEO meta description (150-160 chars)
        keywords: Target keywords
        word_count: Total word count
        content_type: Type of content generated
    """

    title: str
    html: str
    meta_description: str
    keywords: list[str]
    word_count: int
    content_type: ContentType

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "html": self.html,
            "meta_description": self.meta_description,
            "keywords": self.keywords,
            "word_count": self.word_count,
            "content_type": self.content_type.value,
        }


@dataclass
class ContentConfig:
    """Configuration for content generation.

    Attributes:
        min_words: Minimum word count
        max_words: Maximum word count
        provider: Primary LLM provider
        temperature: LLM temperature (0-1)
        model_gemini: Gemini model name
        model_openai: OpenAI model name
    """

    min_words: int = 1500
    max_words: int = 2500
    provider: LLMProvider = LLMProvider.GEMINI
    temperature: float = 0.7
    model_gemini: str = "gemini-2.0-flash-exp"
    model_openai: str = "gpt-4o-mini"


class ContentGenerator:
    """Generates blog content using LLM APIs.

    Example:
        >>> generator = ContentGenerator()
        >>> content = generator.generate(
        ...     topic="AI Tools for Developers",
        ...     keywords=["ai", "developer", "tools"],
        ...     content_type=ContentType.REVIEW,
        ... )
        >>> print(content.title)
    """

    # Default prompt templates (embedded for simplicity)
    DEFAULT_PROMPTS = {
        ContentType.REVIEW: """
Write a comprehensive review blog post about: {topic}

Target keywords: {keywords}

Requirements:
- Write in HTML format
- Include H1 title with the main keyword
- Include 5+ H2 sections
- Include at least 2 H3 subsections
- Include a Table of Contents at the beginning
- Include a FAQ section with 3+ questions (using H3 for questions)
- Write 1500-2500 words
- Be informative and engaging
- Include pros and cons if applicable
- End with a clear conclusion

Structure:
1. H1: Title
2. Table of Contents
3. Introduction
4. Main review sections (H2)
5. Pros and Cons (if applicable)
6. FAQ (H2 with H3 questions)
7. Conclusion

Output only the HTML content, no markdown.
""",
        ContentType.COMPARISON: """
Write a comparison blog post about: {topic}

Target keywords: {keywords}

Requirements:
- Write in HTML format
- Compare 2 or more items/tools/services
- Include H1 title
- Include 5+ H2 sections
- Include comparison tables where appropriate
- Include a FAQ section with 3+ questions
- Write 1500-2500 words
- Be objective and balanced
- Include a recommendation at the end

Output only the HTML content, no markdown.
""",
        ContentType.GUIDE: """
Write a how-to guide blog post about: {topic}

Target keywords: {keywords}

Requirements:
- Write in HTML format
- Include H1 title with "How to" or "Guide"
- Include 5+ H2 sections for steps/sections
- Include numbered or bulleted lists
- Include a FAQ section with 3+ questions
- Write 1500-2500 words
- Be clear and actionable
- Include prerequisites if applicable
- Include tips and warnings

Output only the HTML content, no markdown.
""",
        ContentType.LIST: """
Write a listicle blog post about: {topic}

Target keywords: {keywords}

Requirements:
- Write in HTML format
- Include H1 title with number (e.g., "10 Best...")
- Each list item should be an H2
- Include brief descriptions for each item
- Include a FAQ section with 3+ questions
- Write 1500-2500 words
- Include pros/cons or key features for each item
- End with a summary

Output only the HTML content, no markdown.
""",
        ContentType.NEWS: """
Write a news analysis blog post about: {topic}

Target keywords: {keywords}

Requirements:
- Write in HTML format
- Include H1 title
- Include 5+ H2 sections
- Cover: What happened, Why it matters, Impact, What's next
- Include a FAQ section with 3+ questions
- Write 1500-2500 words
- Be factual and informative
- Include expert perspectives if relevant

Output only the HTML content, no markdown.
""",
    }

    def __init__(self, config: Optional[ContentConfig] = None) -> None:
        """Initialize ContentGenerator.

        Args:
            config: Optional configuration. Uses defaults if not provided.
        """
        self.config = config or ContentConfig()
        self._setup_apis()

    def _setup_apis(self) -> None:
        """Setup LLM API clients."""
        # Setup Gemini
        if genai is not None:
            api_key = os.getenv("GOOGLE_AI_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
                logger.info("Gemini API configured")

        # OpenAI client is created on-demand

    def generate(
        self,
        topic: str,
        keywords: list[str],
        content_type: ContentType,
    ) -> GeneratedContent:
        """Generate blog content for a topic.

        Args:
            topic: The topic to write about
            keywords: Target SEO keywords
            content_type: Type of content to generate

        Returns:
            GeneratedContent object with the generated post
        """
        logger.info(f"Generating {content_type.value} content for: {topic}")

        # Load and format prompt
        prompt_template = self._load_prompt_template(content_type)
        prompt = prompt_template.format(
            topic=topic,
            keywords=", ".join(keywords),
        )

        # Generate content with LLM
        raw_html = self._call_llm(prompt)

        # Clean and process HTML
        html = self._clean_html(raw_html)

        # Extract title
        title = self._extract_title(html) or topic

        # Generate meta description
        meta_description = self._generate_meta(topic, keywords, html)

        # Count words
        word_count = self._count_words(html)

        # Validate content
        is_valid, errors = self._validate(html)
        if not is_valid:
            logger.warning(f"Content validation warnings: {errors}")

        return GeneratedContent(
            title=title,
            html=html,
            meta_description=meta_description,
            keywords=keywords,
            word_count=word_count,
            content_type=content_type,
        )

    def _load_prompt_template(self, content_type: ContentType) -> str:
        """Load prompt template for content type.

        Args:
            content_type: Type of content

        Returns:
            Prompt template string
        """
        # First, try to load from file
        templates_dir = Path(__file__).parent.parent / "templates" / "prompts"
        template_file = templates_dir / f"{content_type.value}.yaml"

        if template_file.exists():
            try:
                import yaml
                with open(template_file) as f:
                    data = yaml.safe_load(f)
                    return data.get("prompt", self.DEFAULT_PROMPTS[content_type])
            except Exception as e:
                logger.debug(f"Failed to load template file: {e}")

        # Fall back to default
        return self.DEFAULT_PROMPTS[content_type]

    def _call_llm(self, prompt: str) -> str:
        """Call LLM API to generate content.

        Tries primary provider first, falls back to secondary on error.

        Args:
            prompt: The prompt to send

        Returns:
            Generated text response
        """
        providers = [self.config.provider]

        # Add fallback provider
        if self.config.provider == LLMProvider.GEMINI:
            providers.append(LLMProvider.OPENAI)
        else:
            providers.append(LLMProvider.GEMINI)

        last_error = None

        for provider in providers:
            try:
                if provider == LLMProvider.GEMINI:
                    return self._call_gemini(prompt)
                else:
                    return self._call_openai(prompt)
            except Exception as e:
                logger.warning(f"{provider.value} failed: {e}")
                last_error = e
                continue

        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")

    def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API.

        Args:
            prompt: The prompt

        Returns:
            Generated text
        """
        if genai is None:
            raise ImportError("google-generativeai not installed")

        model = genai.GenerativeModel(self.config.model_gemini)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=self.config.temperature,
            ),
        )
        return response.text

    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API.

        Args:
            prompt: The prompt

        Returns:
            Generated text
        """
        if OpenAI is None:
            raise ImportError("openai not installed")

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=self.config.model_openai,
            messages=[
                {"role": "system", "content": "You are a professional blog writer."},
                {"role": "user", "content": prompt},
            ],
            temperature=self.config.temperature,
        )
        return response.choices[0].message.content

    def _clean_html(self, raw: str) -> str:
        """Clean raw LLM output to valid HTML.

        Args:
            raw: Raw LLM response

        Returns:
            Cleaned HTML
        """
        # Remove markdown code blocks
        cleaned = re.sub(r"```html\s*", "", raw)
        cleaned = re.sub(r"```\s*", "", cleaned)

        # Remove leading/trailing whitespace
        cleaned = cleaned.strip()

        return cleaned

    def _extract_title(self, html: str) -> Optional[str]:
        """Extract title from H1 tag.

        Args:
            html: HTML content

        Returns:
            Title text or None
        """
        match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
        if match:
            # Remove any nested tags
            title = re.sub(r"<[^>]+>", "", match.group(1))
            return title.strip()
        return None

    def _generate_meta(
        self,
        topic: str,
        keywords: list[str],
        html: str,
    ) -> str:
        """Generate meta description.

        Args:
            topic: The topic
            keywords: Target keywords
            html: Full HTML content

        Returns:
            Meta description (150-160 chars)
        """
        # Try to extract first paragraph
        match = re.search(r"<p[^>]*>(.*?)</p>", html, re.IGNORECASE | re.DOTALL)
        if match:
            text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
            # Truncate to ~155 chars
            if len(text) > 155:
                text = text[:152] + "..."
            elif len(text) < 100:
                # Too short, generate from topic
                text = f"Learn everything about {topic}. " + text
            return text[:160]

        # Fallback: generate from topic and keywords
        base = f"Comprehensive guide to {topic}. "
        if keywords:
            base += f"Learn about {', '.join(keywords[:3])}."
        return base[:160]

    def _count_words(self, html: str) -> int:
        """Count words in HTML content.

        Args:
            html: HTML content

        Returns:
            Word count
        """
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", " ", html)
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text).strip()
        # Count words
        words = text.split()
        return len(words)

    def _validate(self, html: str) -> tuple[bool, list[str]]:
        """Validate generated content.

        Args:
            html: HTML content

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors: list[str] = []

        # Check word count
        word_count = self._count_words(html)
        if word_count < self.config.min_words:
            errors.append(f"Word count {word_count} below minimum {self.config.min_words}")

        # Check for H1
        if not re.search(r"<h1[^>]*>", html, re.IGNORECASE):
            errors.append("Missing H1 heading")

        # Check for H2 sections (need at least 4)
        h2_count = len(re.findall(r"<h2[^>]*>", html, re.IGNORECASE))
        if h2_count < 4:
            errors.append(f"Only {h2_count} H2 headings, need at least 4")

        # Check for FAQ section
        if not re.search(r"<h2[^>]*>\s*FAQ", html, re.IGNORECASE):
            errors.append("Missing FAQ section")

        is_valid = len(errors) == 0
        return is_valid, errors
