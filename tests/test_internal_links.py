"""내부 링크(관련 글) 기능 테스트.

bytepulse(tech/kculture) 미색인 개선: 모든 모드에서 관련도 기반
내부 링크 박스를 삽입한다.
"""

import pytest
from unittest.mock import Mock, patch

from src.content_generator import ContentType, GeneratedContent
from src.monetization import _related_box, fix_shop_links, insert_related_box
from src.pipeline import BlogPipeline, PipelineConfig, rank_related_posts
from src.trend_detector import Topic, TrendSource
from src.wordpress_client import CreatedPost, PostStatus


class TestRankRelatedPosts:
    """rank_related_posts: 제목/슬러그 키워드 겹침 기반 관련도 랭킹."""

    POSTS = [
        {"title": "Notion vs Obsidian 2026", "slug": "notion-vs-obsidian-2026"},
        {"title": "Cursor AI review", "slug": "cursor-ai-review"},
        {"title": "Best Korean skincare", "slug": "best-korean-skincare"},
        {"title": "Cursor vs Copilot benchmark", "slug": "cursor-vs-copilot-benchmark"},
    ]

    @pytest.mark.unit
    def test_keyword_overlap_ranks_higher(self):
        """키워드가 더 많이 겹치는 글이 최신 글보다 앞선다."""
        ranked = rank_related_posts(self.POSTS, ["cursor", "copilot"], count=2)
        assert ranked[0]["slug"] == "cursor-vs-copilot-benchmark"  # 2개 일치
        assert ranked[1]["slug"] == "cursor-ai-review"  # 1개 일치

    @pytest.mark.unit
    def test_zero_hits_falls_back_to_recency(self):
        """겹치는 키워드가 없으면 입력 순서(최신순)를 유지한다."""
        ranked = rank_related_posts(self.POSTS, ["quantum"], count=2)
        assert [p["slug"] for p in ranked] == [
            "notion-vs-obsidian-2026",
            "cursor-ai-review",
        ]

    @pytest.mark.unit
    def test_count_respected(self):
        ranked = rank_related_posts(self.POSTS, [], count=3)
        assert len(ranked) == 3

    @pytest.mark.unit
    def test_empty_inputs(self):
        assert rank_related_posts([], ["ai"], count=3) == []

    @pytest.mark.unit
    def test_keyword_match_requires_word_boundary(self):
        """'ai'가 'chairs' 같은 단어 일부에 오탐 매칭되면 안 된다."""
        posts = [
            {"title": "Best Office Chairs for Devs", "slug": "best-office-chairs"},
            {"title": "AI coding assistants", "slug": "ai-coding-assistants"},
        ]
        ranked = rank_related_posts(posts, ["ai"], count=1)
        assert ranked[0]["slug"] == "ai-coding-assistants"


class TestInsertRelatedBox:
    """insert_related_box: 관련 글 박스를 마지막 H2(결론) 앞에 삽입."""

    HTML = (
        "<p>intro</p>"
        "<h2>Section 1</h2><p>a</p>"
        "<h2>Section 2</h2><p>b</p>"
        "<h2>Conclusion</h2><p>c</p>"
    )
    POSTS = [{"title": "Related one", "url": "https://bytepulse.io/related-one/"}]

    @pytest.mark.unit
    def test_box_inserted_before_last_h2(self):
        result = insert_related_box(self.HTML, self.POSTS)
        assert "related-one" in result
        assert result.index("related-one") < result.index("<h2>Conclusion</h2>")
        assert result.index("related-one") > result.index("<h2>Section 2</h2>")

    @pytest.mark.unit
    def test_english_heading_default(self):
        result = insert_related_box(self.HTML, self.POSTS)
        assert "Related Posts" in result
        assert "함께 보면 좋은 글" not in result

    @pytest.mark.unit
    def test_empty_posts_returns_unchanged(self):
        assert insert_related_box(self.HTML, []) == self.HTML

    @pytest.mark.unit
    def test_single_h2_appends_at_end(self):
        html = "<p>intro</p><h2>Only</h2><p>body</p>"
        result = insert_related_box(html, self.POSTS)
        assert result == html + _related_box(self.POSTS, "📌 Related Posts")


class TestGetRelatedPostsByMode:
    """_get_related_posts: 모드별 언어 필터 + 키워드 관련도."""

    RECENT = [
        {"id": 1, "title": "Cursor vs Copilot benchmark", "slug": "cursor-vs-copilot"},
        {"id": 2, "title": "커서 리뷰", "slug": "cursor-korean"},
        {"id": 3, "title": "Best Korean skincare", "slug": "best-korean-skincare"},
        {"id": 4, "title": "Notion review 2026", "slug": "notion-review-2026"},
    ]

    def _pipeline(self, mode: str, mock_env_vars) -> BlogPipeline:
        pipeline = BlogPipeline(config=PipelineConfig(dry_run=True, mode=mode))
        wp = Mock()
        wp.get_recent_posts.return_value = list(self.RECENT)
        wp.config.url = "https://bytepulse.io"
        pipeline.wp_client = wp
        return pipeline

    @pytest.mark.unit
    def test_tech_mode_includes_english_titles(self, mock_env_vars):
        pipeline = self._pipeline("tech", mock_env_vars)
        related = pipeline._get_related_posts(keywords=["cursor", "copilot"])
        assert related, "tech 모드에서 영어 글이 관련 글로 잡혀야 한다"
        assert related[0]["title"] == "Cursor vs Copilot benchmark"
        assert related[0]["url"] == "https://bytepulse.io/cursor-vs-copilot/"

    @pytest.mark.unit
    def test_general_mode_keeps_korean_only_filter(self, mock_env_vars):
        pipeline = self._pipeline("general", mock_env_vars)
        related = pipeline._get_related_posts()
        assert [r["title"] for r in related] == ["커서 리뷰"]

    @pytest.mark.unit
    def test_excludes_current_title(self, mock_env_vars):
        pipeline = self._pipeline("tech", mock_env_vars)
        related = pipeline._get_related_posts(
            exclude_title="Cursor vs Copilot benchmark", keywords=["cursor"]
        )
        assert related, "제외 후에도 다른 관련 글은 남아야 한다"
        assert all(r["title"] != "Cursor vs Copilot benchmark" for r in related)

    @pytest.mark.unit
    def test_excludes_current_title_with_html_entities(self, mock_env_vars):
        """WP가 텍스처라이즈한 제목(&#8217; 등)도 원본 제목과 매칭해 제외한다."""
        pipeline = self._pipeline("tech", mock_env_vars)
        pipeline.wp_client.get_recent_posts.return_value = [
            {"id": 1, "title": "Apple&#8217;s M5 Review", "slug": "apples-m5"},
            {"id": 2, "title": "Notion Review 2026", "slug": "notion-review-2026"},
        ]
        related = pipeline._get_related_posts(exclude_title="Apple's M5 Review")
        assert related
        assert all("apples-m5" not in r["url"] for r in related)


class TestPipelineRelatedBoxWiring:
    """_process_topic 배선: tech 모드에서 박스가 게이트 이후·발행 전에 삽입되는지."""

    HTML = (
        "<h1>t</h1><h2>A</h2>" + "<p>content</p>" * 120
        + "<h2>B</h2><p>y</p><h2>Conclusion</h2><p>z</p>"
    )

    @pytest.mark.unit
    def test_tech_mode_inserts_box_after_quality_gate(self, mock_env_vars):
        pipeline = BlogPipeline(
            config=PipelineConfig(mode="tech", auto_publish=False, use_llm_topics=False)
        )
        content = GeneratedContent(
            title="New Post",
            html=self.HTML,
            meta_description="d" * 60,
            keywords=["cursor"],
            word_count=1500,
            content_type=ContentType.REVIEW,
            focus_keyphrase="cursor",
        )
        topic = Topic(
            topic="Cursor deep dive",
            keywords=["cursor"],
            source=TrendSource.HACKER_NEWS,
            score=80,
            suggested_title="New Post",
        )
        recent = [{"id": 1, "title": "Cursor benchmark", "slug": "cursor-benchmark"}]

        with patch.object(pipeline.content_generator, "generate", return_value=content), \
             patch.object(pipeline.image_fetcher, "fetch", return_value=[]), \
             patch.object(pipeline.wp_client, "get_recent_posts", return_value=recent), \
             patch.object(pipeline.wp_client, "_find_category_id", return_value=10), \
             patch.object(
                 pipeline.wp_client, "create_post",
                 return_value=CreatedPost(1, "u", "t", PostStatus.DRAFT),
             ) as mock_create, \
             patch("src.pipeline.check_quality", return_value=[]) as mock_gate:
            result = pipeline._process_topic(topic)

        assert result.success, f"pipeline failed: {result.error}"
        published_html = mock_create.call_args.kwargs["content"].html
        assert "cursor-benchmark" in published_html  # 관련 글 박스 삽입됨
        # 품질 게이트는 박스 삽입 전의 본문을 평가해야 한다
        assert "cursor-benchmark" not in mock_gate.call_args.kwargs["html"]


class TestCategoryAwareRanking:
    """관련도 랭킹: 같은 카테고리 보너스로 크로스 니치 링크를 억제한다."""

    POSTS = [
        {"title": "Qwen vs DeepSeek LLM", "slug": "qwen-deepseek", "categories": [10]},
        {"title": "Best Korean Toner Guide", "slug": "best-korean-toner", "categories": [20]},
        {"title": "Seoul Fashion Week Recap", "slug": "seoul-fashion-week", "categories": [30]},
    ]

    @pytest.mark.unit
    def test_same_category_beats_recency_on_zero_keyword_hits(self):
        """키워드가 안 겹칠 때 최신 tech 글 대신 같은 카테고리 글을 고른다."""
        ranked = rank_related_posts(self.POSTS, ["eye patches"], count=2, category_id=20)
        assert ranked[0]["slug"] == "best-korean-toner"

    @pytest.mark.unit
    def test_keyword_hit_beats_category_bonus(self):
        """키워드 일치(가중 2)가 카테고리 보너스(가중 1)보다 우선한다."""
        ranked = rank_related_posts(self.POSTS, ["fashion"], count=1, category_id=20)
        assert ranked[0]["slug"] == "seoul-fashion-week"

    @pytest.mark.unit
    def test_get_related_posts_uses_category(self, mock_env_vars):
        pipeline = BlogPipeline(config=PipelineConfig(dry_run=True, mode="kculture"))
        wp = Mock()
        wp.get_recent_posts.return_value = list(self.POSTS)
        wp.config.url = "https://bytepulse.io"
        wp._find_category_id.return_value = 20
        pipeline.wp_client = wp
        related = pipeline._get_related_posts(keywords=["eye patches"], category="K-Beauty")
        assert related[0]["url"].endswith("/best-korean-toner/")

    @pytest.mark.unit
    def test_fetches_category_recents_when_absent_from_recent(self, mock_env_vars):
        """최근 목록에 같은 카테고리 글이 없으면 카테고리로 직접 조회해 합친다."""
        pipeline = BlogPipeline(config=PipelineConfig(dry_run=True, mode="kculture"))
        wp = Mock()
        tech_recent = [{"id": 1, "title": "Tech A", "slug": "tech-a", "categories": [10]}]
        kfood_posts = [{"id": 2, "title": "Kimchi Guide", "slug": "kimchi-guide", "categories": [40]}]
        wp.get_recent_posts.side_effect = [tech_recent, kfood_posts]
        wp.config.url = "https://bytepulse.io"
        wp._find_category_id.return_value = 40
        pipeline.wp_client = wp
        related = pipeline._get_related_posts(keywords=[], category="K-Food")
        assert related[0]["url"].endswith("/kimchi-guide/")


class TestFixShopLinks:
    """fix_shop_links: LLM이 남긴 쇼핑 링크 플레이스홀더를 코드로 강제 수리."""

    @pytest.mark.unit
    def test_plain_placeholder_gets_linked(self):
        """href 없는 '(Shop on Musinsa Global →)' 텍스트를 실제 검색 링크로 치환."""
        html = '<span>(Shop on Musinsa Global →)</span>'
        out = fix_shop_links(html, "Korean Varsity Jacket")
        assert 'global.musinsa.com/us/search?keyword=Korean%20Varsity%20Jacket' in out
        assert '(Shop on Musinsa Global →)' not in out
        assert 'rel="nofollow"' in out

    @pytest.mark.unit
    def test_broken_prefix_before_anchor_removed(self):
        """'(Shop on<a ...>' 같은 깨진 접두 텍스트를 제거한다."""
        html = '(Shop on<a href="https://www.yesstyle.com/en/search?q=x">YesStyle →</a>'
        out = fix_shop_links(html, "x")
        assert out.startswith('<a href=')

    @pytest.mark.unit
    def test_existing_anchor_untouched(self):
        html = '<a href="https://www.yesstyle.com/en/search?q=x" rel="nofollow">Shop on YesStyle →</a>'
        assert fix_shop_links(html, "x") == html

    @pytest.mark.unit
    def test_unknown_shop_placeholder_removed(self):
        out = fix_shop_links('before (Shop on RandomMall →) after', "q")
        assert 'RandomMall' not in out

    @pytest.mark.unit
    def test_word_glued_anchor_gets_space(self):
        html = 'Jackets on<a href="u">YesStyle →</a>'
        out = fix_shop_links(html, "x")
        assert 'on <a' in out

    @pytest.mark.unit
    def test_title_with_markdown_bold_fails_gate(self):
        """'**제목**' 같은 마크다운 잔존 제목은 품질 게이트에서 걸린다."""
        from src.monetization import check_quality
        issues = check_quality(
            title="**Korean Dress Styling Guide**",
            html="<p>" + "x" * 1200 + "</p>",
            focus_keyphrase="korean dress",
            meta_description="d" * 60,
            require_korean=False,
        )
        assert any("제목" in i for i in issues)
