import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image

from src import dynamic_thumbnail as dynamic
from src import editorial_thumbnail as editorial
from src.codex_client import CodexResponseError


@pytest.fixture
def rendering(tmp_path, monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    home = tmp_path / "auth-home"
    home.mkdir()
    (home / "auth.json").write_text("{}")
    monkeypatch.setenv("BLOG_CODEX_HOME", str(home))
    monkeypatch.setenv("BLOG_THUMBNAIL_PROVIDER", "codex")
    monkeypatch.setattr(editorial, "OUTPUT", tmp_path / "out")
    image = tmp_path / "art.png"
    Image.new("RGB", (1200, 900), "#789987").save(image)
    client = Mock()
    client.generate_image.return_value = image
    monkeypatch.setattr(dynamic, "CodexSubscriptionClient", Mock(return_value=client))
    return client, tmp_path / "out"


def test_default_path_generates_scene_uploadable_jpeg_and_caches_success(rendering, monkeypatch):
    monkeypatch.delenv("BLOG_THUMBNAIL_PROVIDER")
    client, _ = rendering
    first = editorial.create_editorial_thumbnail(
        "폐암 초기증상: 확인하기", "<p>폐와 기침에 대한 정보</p>", "건강"
    )
    p = Path(first.url)
    assert Image.open(p).format == "JPEG"
    assert Image.open(p).size == (1200, 900)
    audit = json.loads(p.with_suffix(".json").read_text())
    assert audit["provider"] == "codex_imagegen"
    assert all(
        150 <= x0 < x1 <= 1050 and 150 < y0 < y1 < 730
        for x0, y0, x1, y1 in audit["headline_bounds"]
    )
    assert (
        editorial.create_editorial_thumbnail(
            "폐암 초기증상: 확인하기", "<p>폐와 기침에 대한 정보</p>", "건강"
        ).url
        == first.url
    )
    assert client.generate_image.call_count == 1
    prompt = client.generate_image.call_args.args[0]
    assert "폐암 초기증상" in prompt and "폐와 기침" in prompt
    # A corrupt successful cache must regenerate, never upload invalid bytes.
    p.write_bytes(b"corrupt")
    editorial.create_editorial_thumbnail(
        "폐암 초기증상: 확인하기", "<p>폐와 기침에 대한 정보</p>", "건강"
    )
    assert client.generate_image.call_count == 2


def test_subject_and_body_change_scene_request(rendering):
    client, _ = rendering
    results = [
        editorial.create_editorial_thumbnail(t, b, c).url
        for t, b, c in [
            ("폐암 초기증상", "<p>기침과 폐</p>", "건강"),
            ("위암 초기증상", "<p>위와 소화</p>", "건강"),
            ("엑셀 조건부 서식", "<p>셀에 색상 표시</p>", "생산성"),
            ("엑셀 조건부 서식", "<p>중복된 항목 강조</p>", "생산성"),
        ]
    ]
    assert len(set(results)) == 4
    prompts = [call.args[0] for call in client.generate_image.call_args_list]
    assert len(set(prompts)) == 4
    assert "기침과 폐" in prompts[0] and "위와 소화" in prompts[1]


def test_failure_is_audited_and_not_cached_as_generation_success(rendering):
    client, _ = rendering
    client.generate_image.side_effect = CodexResponseError("usage_limit", "private provider detail")
    first = editorial.create_editorial_thumbnail("엑셀 사용법", "<h2>조건부 서식</h2>", "생산성")
    audit = json.loads(Path(first.url).with_suffix(".json").read_text())
    assert audit["provider"] == "editorial_fallback"
    assert audit["fallback_reason"] == "usage_limit"
    assert "private provider detail" not in json.dumps(audit)
    editorial.create_editorial_thumbnail("엑셀 사용법", "<h2>조건부 서식</h2>", "생산성")
    assert client.generate_image.call_count == 2


def test_invalid_image_falls_back_before_upload(rendering):
    client, _ = rendering
    Path(client.generate_image.return_value).write_text("not an image")
    p = Path(editorial.create_editorial_thumbnail("본문 확인", "", "건강").url)
    assert Image.open(p).size == (1200, 900)
    assert json.loads(p.with_suffix(".json").read_text())["provider"] == "editorial_fallback"


def test_offline_provider_never_calls_imagegen(rendering, monkeypatch):
    monkeypatch.setenv("BLOG_THUMBNAIL_PROVIDER", "editorial")
    editorial.create_editorial_thumbnail("면접 준비", "", "취업")
    rendering[0].generate_image.assert_not_called()


def test_prompt_removes_script_navigation_and_bounds_article():
    context = dynamic.article_context(
        "제목", "<script>secret()</script><nav>menu</nav><p>" + "본문" * 5000 + "</p>", "건강"
    )
    assert "secret" not in dynamic.build_prompt(context)
    assert "menu" not in dynamic.build_prompt(context)
    assert len(context["article_excerpt"]) == 1800


def test_workflow_uses_dynamic_provider_for_general_and_queue():
    import yaml

    workflow = yaml.safe_load(
        (Path(__file__).parents[1] / ".github/workflows/auto-post.yml").read_text()
    )
    for name in ("post-general", "post-queue"):
        assert workflow["jobs"][name]["env"]["BLOG_THUMBNAIL_PROVIDER"] == "codex"


def test_native_preview_rejects_fallback_and_preserves_diagnostic(tmp_path, monkeypatch):
    from scripts import preview_editorial_thumbnails as preview

    monkeypatch.setenv("BLOG_THUMBNAIL_PROVIDER", "editorial")
    monkeypatch.delenv("BLOG_CODEX_HOME", raising=False)
    monkeypatch.setattr(editorial, "OUTPUT", tmp_path / "out")
    monkeypatch.setattr(
        "sys.argv",
        [
            "preview",
            "--provider",
            "codex",
            "--sample",
            "lung",
            "--output",
            str(tmp_path / "preview"),
        ],
    )
    with pytest.raises(RuntimeError, match="fallback preview is not a pass"):
        preview.main()
    audit = json.loads((tmp_path / "preview/lung.json").read_text())
    assert audit["provider"] == "editorial_fallback"
    assert audit["fallback_reason"] == "image_auth_missing"


def test_thumbnail_check_has_no_wordpress_access_and_serializes_auth():
    import yaml

    workflow = yaml.safe_load(
        (Path(__file__).parents[1] / ".github/workflows/thumbnail-check.yml").read_text()
    )
    assert workflow["concurrency"]["group"] == "trendpulse-general-posting"
    text = json.dumps(workflow)
    assert "WP_GENERAL_APP_PASSWORD" not in text
    assert "OPENAI_API_KEY" not in text
    steps = workflow["jobs"]["preview"]["steps"]
    assert any("--provider codex" in step.get("run", "") for step in steps)
    assert steps[-1]["if"] == "always()"
