"""Regression coverage for TrendPulse's evidence and safe update boundaries."""
import copy
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from bs4 import BeautifulSoup
from src.editorial import fetch_source, reader_layout, review_evidence, repair_evidence, EvidenceRepairError, is_official_url, editorial_checks
from src.pipeline import rank_related_posts, BlogPipeline, PipelineConfig
from src.content_generator import GeneratedContent, ContentType
from src.trend_detector import Topic, TrendSource
from scripts.apply_editorial_updates import apply_entry, validate_entry
from scripts.refresh_search_winners import select_candidates

SOURCE = dict(url="https://news.samsung.com/kr/test", original_url="https://news.samsung.com/kr/test",
              title="Official announcement", checked_on="2026-09-08", sha256="abc", excerpt="GSAT is in October.")

REPAIR_HTML = ('<div class="wpab-article"><section id="quick-answer"><p>GSAT 일정은 10월입니다.</p></section>'
               '<h2 id="dates">일정</h2><p>검증되지 않은 설명입니다.</p>'
               '<h2 id="faq">FAQ</h2><h3 id="when">언제인가요?</h3><p>10월입니다.</p></div>')


def test_evidence_repair_uses_one_call_and_only_supplied_context():
    corrected = REPAIR_HTML.replace('검증되지 않은 설명입니다.',
                                    f'<a href="{SOURCE["url"]}">공식 안내</a>에서 10월 일정을 확인하세요.')
    writer = Mock(return_value=corrected)
    with patch('src.editorial.requests.get', side_effect=AssertionError('No repair research')):
        result = repair_evidence(REPAIR_HTML, [SOURCE], writer, ['근거 없는 설명을 삭제하세요.'], keyword='GSAT')
    assert '검증되지 않은 설명' not in result
    assert SOURCE['url'] in result
    writer.assert_called_once()
    prompt = writer.call_args.args[0]
    assert 'Do not browse' in prompt and 'remove or narrow' in prompt
    data = json.loads(prompt.split('\n', 1)[1])
    assert data['sources'] == [{key: SOURCE[key] for key in ('url', 'checked_on', 'excerpt')}]
    assert data['issues'] == ['근거 없는 설명을 삭제하세요.']
    assert data['keyword'] == 'GSAT'


@pytest.mark.parametrize('response', [
    None, '', '보완했습니다.', '```html\n' + REPAIR_HTML + '\n```',
    REPAIR_HTML.replace('</p>', '', 1),
    REPAIR_HTML.replace('id="quick-answer"', 'id="answer"'),
    REPAIR_HTML.replace('class="wpab-article"', 'class="other"'),
    REPAIR_HTML.replace('GSAT', '다른 검색어'),
    REPAIR_HTML.replace('id="dates"', 'id="new-dates"'),
    REPAIR_HTML.replace('</div>', '<script>alert(1)</script></div>'),
    REPAIR_HTML.replace('<p>10월입니다.</p>', '<p onclick="alert(1)">10월입니다.</p>'),
    REPAIR_HTML.replace('10월입니다.</p></div>', '<a href="https://www.niddk.nih.gov/new">새 근거</a></p></div>'),
])
def test_evidence_repair_rejects_invalid_html_without_retry(response):
    writer = Mock(return_value=response)
    with pytest.raises(RuntimeError, match='근거 보완 실패'):
        repair_evidence(REPAIR_HTML, [SOURCE], writer, ['근거 보완'], keyword='GSAT')
    writer.assert_called_once()


def test_evidence_repair_preserves_protected_markup_without_sending_it_to_writer():
    style = '<style id="wpab-reading-styles">.wpab-article{color:white}</style>'
    script = '<script type="application/ld+json">{"name":"original"}</script>'

    def revise(prompt):
        article = json.loads(prompt.split('\n', 1)[1])['article']
        assert '.wpab-article{color:white}' not in article
        assert '"name":"original"' not in article
        assert article.count('wpab-protected-') == 2
        return article.replace('검증되지 않은 설명입니다.', '공식 자료에 나온 일정입니다.')

    result = repair_evidence(style + REPAIR_HTML + script, [SOURCE], Mock(side_effect=revise), ['근거 보완'], keyword='GSAT')
    soup = BeautifulSoup(result, 'html.parser')
    assert str(soup.style) == style
    assert str(soup.script) == script
    assert 'wpab-protected-' not in result
    assert soup.select_one('.wpab-article #quick-answer')


@pytest.mark.parametrize('duplicate', [False, True])
def test_evidence_repair_rejects_missing_or_duplicate_protected_placeholder(duplicate):
    def revise(prompt):
        article = json.loads(prompt.split('\n', 1)[1])['article']
        soup = BeautifulSoup(article, 'html.parser')
        comment = next(node for node in soup.descendants if isinstance(node, str) and 'wpab-protected-' in node)
        return article + '<!--' + str(comment) + '-->' if duplicate else article.replace('<!--' + str(comment) + '-->', '')
    writer = Mock(side_effect=revise)
    with pytest.raises(RuntimeError, match='근거 보완 실패'):
        repair_evidence('<style>p{color:white}</style>' + REPAIR_HTML, [SOURCE], writer, ['근거 보완'], keyword='GSAT')
    writer.assert_called_once()


def test_evidence_repair_failure_hides_raw_model_error():
    writer = Mock(side_effect=RuntimeError('private response or credential'))
    with pytest.raises(RuntimeError, match='근거 보완 실패') as error:
        repair_evidence(REPAIR_HTML, [SOURCE], writer, ['근거 보완'], keyword='GSAT')
    assert 'private' not in str(error.value)
    writer.assert_called_once()


@pytest.mark.parametrize(('response', 'reason'), [
    ('', 'empty_response'),
    (REPAIR_HTML.replace('</div>', ''), 'unbalanced_html'),
    (REPAIR_HTML.replace('GSAT', '다른말'), 'keyword_missing'),
    (REPAIR_HTML.replace('id="quick-answer"', 'id="lost"'), 'template_changed'),
    (REPAIR_HTML.replace('</div>', '<a href="https://www.niddk.nih.gov/new">새자료</a></div>'), 'new_url'),
])
def test_evidence_repair_exposes_only_fixed_failure_code(response, reason):
    with pytest.raises(EvidenceRepairError) as error:
        repair_evidence(REPAIR_HTML, [SOURCE], Mock(return_value=response), ['근거 보완'], keyword='GSAT')
    assert error.value.reason == reason
    assert str(error.value) == f'근거 보완 실패 — 자동 발행 보류 ({reason})'


def test_evidence_repair_requires_actual_source_excerpt_before_call():
    writer = Mock()
    with pytest.raises(RuntimeError, match='근거 보완 실패'):
        repair_evidence(REPAIR_HTML, [{**SOURCE, 'excerpt': ''}], writer, ['근거 보완'], keyword='GSAT')
    writer.assert_not_called()

@pytest.mark.parametrize("url", ["https://samsung.com.evil.test/a", "https://samsung.com@evil.test/", "http://samsung.com/", "https://samsung.com:123/a"])
def test_source_host_spoof_rejected(url):
    assert not is_official_url(url)
    with patch("src.editorial.requests.get") as get:
        assert fetch_source(url) is None
        get.assert_not_called()


KCCI_GUIDE_URLS = [
    "https://license.korcham.net/co/examguide.do?cd=0103&mm=21",
    "https://ml.korcham.net/co/examguide.do?cd=01&jmcd=0103",
]


def _source_response(html, content_type="text/html; charset=utf-8"):
    response = Mock(status_code=200, headers={"Content-Type": content_type})
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.iter_content.return_value = [html.encode()]
    return response


@pytest.mark.parametrize("url", KCCI_GUIDE_URLS)
def test_kcci_official_guide_is_read_as_evidence_with_existing_html_rules(url):
    # Reduced fixture with the mobile guide's main/table structure. Retrieval
    # makes the source available to review; it does not certify article claims.
    html = '''<html><head><title>Korcham Pass(대한상공회의소)</title></head><body>
    <header>HEADER-SENTINEL</header><nav>NAV-SENTINEL</nav>
    <main><h3>컴퓨터활용능력 (국가기술자격)</h3>
    <p>공식 시험안내에서 등급별 시험과목과 시험방법, 응시자격, 합격결정기준을 확인할 수 있습니다.
    필기시험 안내와 실기시험 안내는 서로 구분해서 확인해야 하며, 아래의 표는 안내 본문에
    포함된 등급별 항목의 예시입니다. 접수와 시험장 선택은 해당 기관의 별도 안내를 확인합니다.</p>
    <table><tr><th>등급</th><th>시험방법</th><th>시험시간</th></tr>
    <tr><td>2급</td><td>필기시험 객관식40문항</td><td>40분</td></tr></table>
    <h4>합격결정기준</h4><p>필기 과목별 기준과 평균 기준을 함께 확인하세요.</p></main>
    <footer>FOOTER-SENTINEL</footer><script>SCRIPT-SENTINEL</script></body></html>'''
    with patch("src.editorial.requests.get", return_value=_source_response(html)) as get:
        source = fetch_source(url)
    assert is_official_url(url)
    get.assert_called_once_with(url, timeout=15, allow_redirects=False, stream=True)
    assert source is not None
    assert source["url"] == source["original_url"] == url
    assert source["title"] == "Korcham Pass(대한상공회의소)"
    assert len(source["excerpt"]) >= 200 and len(source["sha256"]) == 64
    assert all(marker in source["excerpt"] for marker in ("컴퓨터활용능력", "2급", "객관식40문항", "40분"))
    assert "SENTINEL" not in source["excerpt"]


@pytest.mark.parametrize("url", [
    "https://license.korcham.net.evil.test/guide",
    "https://evilkorcham.net/guide",
    "https://korcham.net@evil.test/guide",
    "https://user:password@license.korcham.net/guide",
    "http://license.korcham.net/guide",
    "ftp://ml.korcham.net/guide",
    "https://license.korcham.net:444/guide",
    "https://evil.test/?next=https://license.korcham.net/guide",
])
def test_kcci_lookalikes_credentials_and_other_schemes_never_request(url):
    assert not is_official_url(url)
    with patch("src.editorial.requests.get") as get:
        assert fetch_source(url) is None
        get.assert_not_called()


@pytest.mark.parametrize("html,content_type", [
    ("<main>컴퓨터활용능력 시험안내</main>", "text/html"),
    ("<main>" + "본문" * 150 + "</main>", "application/pdf"),
    ("x" * 1_000_001, "text/html"),
])
def test_kcci_allowlist_does_not_bypass_body_or_media_limits(html, content_type):
    with patch("src.editorial.requests.get", return_value=_source_response(html, content_type)):
        assert fetch_source(KCCI_GUIDE_URLS[1]) is None


def test_kcci_redirect_cannot_escape_official_https_hosts():
    response = Mock(status_code=302, headers={"Location": "https://korcham.net.evil.test/guide"})
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    with patch("src.editorial.requests.get", return_value=response) as get:
        assert fetch_source(KCCI_GUIDE_URLS[1]) is None
        get.assert_called_once()


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


def test_research_retry_is_bounded_and_transient_only():
    from src.editorial import retry_research
    busy = RuntimeError("busy")
    busy.code = 503
    call = Mock(side_effect=[busy, busy, "success"])
    with patch("src.editorial.time.sleep"):
        assert retry_research(call) == "success"
        assert call.call_count == 3
        bad = Mock(side_effect=ValueError("bad credentials"))
        with pytest.raises(ValueError):
            retry_research(bad)
        assert bad.call_count == 1


def test_source_failure_stops_generation_before_paid_writer(mock_env_vars):
    from src.content_generator import ContentGenerator
    generator = ContentGenerator()
    with patch.object(generator, "research_with_grounding", return_value=""), \
         patch.object(generator, "_call_llm") as writer:
        with pytest.raises(RuntimeError, match="원문 확보 실패"):
            generator.generate("삼성 GSAT", ["GSAT"], ContentType.GUIDE, category="취업", mode="general")
    writer.assert_not_called()


def test_inline_official_urls_are_fetched_not_trusted():
    from types import SimpleNamespace
    from src.editorial import collect_research_sources
    response = SimpleNamespace(candidates=[], text='[자료](https://www.work24.go.kr/guide) https://evil.test/fake')
    with patch('src.editorial.fetch_source', return_value=SOURCE) as fetch:
        assert collect_research_sources(response) == [SOURCE]
        fetch.assert_called_once_with('https://www.work24.go.kr/guide')
    with patch('src.editorial.fetch_source', return_value=None):
        assert collect_research_sources(response) == []


def test_missing_grounding_triggers_one_focused_retry(mock_env_vars):
    from types import SimpleNamespace
    from src.content_generator import ContentGenerator
    generator = ContentGenerator()
    response = SimpleNamespace(candidates=[], text='No readable sources')
    generator._gemini_client = Mock()
    generator._gemini_client.models.generate_content.return_value = response
    assert generator.research_with_grounding('면접 준비', [], 'ko', '취업') == response.text
    assert generator._gemini_client.models.generate_content.call_count == 2
    assert generator._research_sources == []


def test_cleaner_preserves_answer_before_title(mock_env_vars):
    from src.content_generator import ContentGenerator
    html = '<section id="quick-answer">10월 시험</section><h1>GSAT</h1><h2>일정</h2>'
    assert ContentGenerator()._clean_html("Here is the article: " + html).startswith('<section id="quick-answer">')


def test_refresh_related_links_exclude_same_id_after_title_change(mock_env_vars):
    pipeline = BlogPipeline(PipelineConfig(mode="general", dry_run=True))
    pipeline.wp_client = Mock()
    pipeline.wp_client.config.url = "https://trendpulse.blog"
    pipeline.wp_client.get_recent_posts.return_value = [
        {"id": 1, "title": "이전 GSAT 일정", "slug": "gsat-old"},
        {"id": 2, "title": "GSAT 준비 방법", "slug": "gsat-study"}]
    related = pipeline._get_related_posts(exclude_title="새 GSAT 일정", keywords=["GSAT"], exclude_post_id=1)
    assert [r["url"] for r in related] == ["https://trendpulse.blog/gsat-study/"]
