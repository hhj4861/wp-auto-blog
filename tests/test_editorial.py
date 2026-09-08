"""Regression coverage for TrendPulse's evidence and safe update boundaries."""
import copy
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from bs4 import BeautifulSoup
from src.editorial import fetch_source, reader_layout, review_evidence, is_official_url, editorial_checks
from src.pipeline import rank_related_posts, BlogPipeline, PipelineConfig
from src.content_generator import GeneratedContent, ContentType
from src.trend_detector import Topic, TrendSource
from scripts.apply_editorial_updates import apply_entry, validate_entry
from scripts.refresh_search_winners import select_candidates

SOURCE = dict(url="https://news.samsung.com/kr/test", original_url="https://news.samsung.com/kr/test",
              title="Official announcement", checked_on="2026-09-08", sha256="abc", excerpt="GSAT is in October.")

@pytest.mark.parametrize("url", ["https://samsung.com.evil.test/a", "https://samsung.com@evil.test/", "http://samsung.com/", "https://samsung.com:123/a"])
def test_source_host_spoof_rejected(url):
    assert not is_official_url(url)
    with patch("src.editorial.requests.get") as get:
        assert fetch_source(url) is None
        get.assert_not_called()


def test_grounding_redirect_must_end_at_official_host():
    res = Mock(status_code=302, headers={"Location": "https://untrusted.test/"})
    res.__enter__ = Mock(return_value=res)
    res.__exit__ = Mock(return_value=False)
    with patch("src.editorial.requests.get", return_value=res) as get:
        assert fetch_source("https://vertexaisearch.cloud.google.com/grounding-api-redirect/test") is None
        assert get.call_count == 1


@pytest.mark.parametrize("response", ['{"issues": []}', '```json\n{"issues": []}\n```'])
def test_review_accepts_valid_empty_issues(response):
    assert review_evidence("<p>GSAT is in October.</p>", [SOURCE], lambda p: response) == []


@pytest.mark.parametrize("response", ['{}', 'yes', '{"issues": "none"}', '{"issues": [""]}'])
def test_review_fails_closed(response):
    assert review_evidence("article", [SOURCE], lambda p: response)


def test_missing_evidence_never_calls_writer():
    writer = Mock()
    assert review_evidence("article", [], writer)
    writer.assert_not_called()
    assert editorial_checks('<section id="quick-answer">answer</section>', "취업", [])


def test_reader_layout_is_repeatable_and_preserves_links():
    raw = '<figure><img src="a"><img src="b"></figure><h2 id="dates">일정</h2><table><tr><td>10월</td></tr></table><section id="quick-answer">10월 시험</section>'
    result = reader_layout(reader_layout(raw, [SOURCE]), [SOURCE])
    soup = BeautifulSoup(result, "html.parser")
    assert soup.find().get("id") == "quick-answer"
    assert not soup.find("img")
    assert len(soup.select("#article-toc")) == 1
    assert len(soup.select("#verified-sources")) == 1
    assert len(soup.select("[data-table-scroll]")) == 1
    assert soup.select_one('a[href="#dates"]')
    assert soup.select_one('a[href="#source-list"]')
    assert result.count("wpab-editorial") == 1


def test_unrelated_posts_omitted_even_in_same_category():
    posts = [{"title": "연금 신청 2026", "slug": "pension", "categories": [1]}]
    assert rank_related_posts(posts, ["여권", "신청", "2026"], category_id=1, require_keyword=True) == []


def test_candidate_selection_excludes_home_and_wrong_site():
    rows = [dict(page=u, clicks=10, impressions=100, position=5) for u in
            ["https://trendpulse.blog/", "https://bytepulse.io/post/", "https://trendpulse.blog/category/jobs/", "https://trendpulse.blog/gsat/"]]
    assert [r["page"] for r in select_candidates(rows)] == ["https://trendpulse.blog/gsat/"]


def test_reviewed_manifest_validates():
    root = Path(__file__).resolve().parents[1] / "data/editorial/2026-09-08"
    for entry in json.loads((root / "manifest.json").read_text())["posts"]:
        html = validate_entry(entry, root)
        assert html.index('id="quick-answer"') < html.index('id="article-toc"')


def test_apply_refuses_concurrent_edit_and_saves_backup(tmp_path):
    post = dict(id=1, slug="gsat", status="publish", modified_gmt="old", title={"raw":"old"}, content={"raw":"old"}, featured_media=2)
    changed = dict(post, modified_gmt="new")
    session = Mock()
    session.get.side_effect = [Mock(json=lambda:[post]), Mock(json=lambda:changed)]
    entry = dict(slug="gsat", title="new", meta_description="new", focus_keyphrase="GSAT")
    with pytest.raises(RuntimeError, match="changed"):
        apply_entry(session, "https://trendpulse.blog/wp-json/wp/v2", entry, "new", tmp_path, apply=True)
    session.post.assert_not_called()
    assert json.loads((tmp_path / "1-before.json").read_text()) == post


def test_failed_evidence_preserves_existing_post(mock_env_vars):
    pipeline = BlogPipeline(PipelineConfig(mode="general", category="취업", auto_publish=True, use_llm_topics=False))
    content = GeneratedContent(title="삼성 GSAT 일정", html='<section id="quick-answer">10월</section><h2>일정</h2><p>본문</p>',
                               meta_description="설명"*40, keywords=["GSAT"], word_count=1000, content_type=ContentType.GUIDE,
                               sources=[SOURCE], editorial_issues=["시험일 근거 없음"])
    topic = Topic(topic="삼성 GSAT 일정", keywords=["GSAT"], source=TrendSource.HACKER_NEWS, score=80, suggested_title=content.title, category="취업")
    with patch.object(pipeline.content_generator, "generate", return_value=content), \
         patch.object(pipeline, "_get_related_posts", return_value=[]), \
         patch.object(pipeline.wp_client, "update_post") as update, \
         patch("src.pipeline.check_quality", return_value=[]), \
         patch("src.pipeline.validate_identity", return_value=[]):
        result = pipeline._process_topic(topic, refresh_post_id=123)
    assert not result.success
    assert "시험일 근거 없음" in result.error
    update.assert_not_called()


def test_wp_update_guard_prevents_stale_write(mock_env_vars):
    from src.wordpress_client import WordPressClient
    client = WordPressClient()
    content = GeneratedContent(title="삼성 GSAT", html="<p>본문</p>", meta_description="설명", keywords=[], word_count=2, content_type=ContentType.GUIDE)
    with patch.object(client, "_get_or_create_tags", return_value=[]), \
         patch("src.wordpress_client.requests.get", return_value=Mock(json=lambda:{"modified_gmt":"new", "status":"publish"})), \
         patch("src.wordpress_client.requests.put") as put:
        with pytest.raises(RuntimeError, match="덮어쓰기"):
            client.update_post(1, content, expected_modified_gmt="old", clear_featured_image=True)
    put.assert_not_called()
