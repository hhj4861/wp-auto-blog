import json
from unittest.mock import Mock

import pytest
import yaml

from scripts.run_codex_worker import command, verify_published
from scripts.codex_worker_auth import validate_auth
from src.codex_client import require_private_actions


@pytest.mark.parametrize("private,event,ref,allowed", [
    (True, "workflow_dispatch", "refs/heads/main", True),
    (False, "workflow_dispatch", "refs/heads/main", False),
    (True, "pull_request", "refs/heads/main", False),
    (True, "workflow_dispatch", "refs/heads/feature", False),
])
def test_private_ci_boundary(tmp_path, monkeypatch, private, event, ref, allowed):
    path = tmp_path / "event.json"
    path.write_text(json.dumps({"repository": {"private": private, "default_branch": "main", "full_name": "owner/worker"}}))
    for key, value in {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_PATH": str(path),
                       "GITHUB_REPOSITORY": "owner/worker", "GITHUB_REF": ref,
                       "GITHUB_EVENT_NAME": event}.items():
        monkeypatch.setenv(key, value)
    if allowed:
        require_private_actions()
    else:
        with pytest.raises(RuntimeError, match="private worker"):
            require_private_actions()


def response(data):
    return Mock(json=lambda: data, raise_for_status=lambda: None)


def test_input_is_literal_argv_and_subscription_explicit():
    topic = '한글 $(touch /tmp/never) "제목"'
    args = command({"WP_GENERAL_URL": "https://trendpulse.blog", "BLOG_TOPIC": topic, "BLOG_PUBLISH": "true"})
    assert args[args.index("--topic") + 1] == topic
    assert args[args.index("--writer-provider") + 1] == "codex"
    assert "--auto-publish" in args
    assert "--dry-run" not in args
    assert "--dry-run" in command({"WP_GENERAL_URL": "https://trendpulse.blog", "BLOG_MODE": "queue"})


def test_api_auth_not_accepted_as_subscription():
    with pytest.raises(ValueError):
        validate_auth('{"auth_mode":"apikey"}')


@pytest.mark.parametrize("results", [[], [{"success": True, "status": "draft"}], [{"success": False}]])
def test_draft_or_no_post_is_not_publication_success(results):
    session = Mock()
    with pytest.raises(RuntimeError, match="one published post"):
        verify_published(results, session, "https://trendpulse.blog")
    session.get.assert_not_called()


def test_posting_requires_wordpress_confirmation():
    session = Mock()
    session.get.return_value = response({"status": "publish", "link": "https://trendpulse.blog/example/"})
    results = [{"success": True, "status": "publish", "post_id": 17, "url": "https://trendpulse.blog/example/"}]
    assert verify_published(results, session, "https://trendpulse.blog") == results[0]['url']
    session.get.return_value = response({"status": "draft", "link": results[0]['url']})
    with pytest.raises(RuntimeError, match="verification failed"):
        verify_published(results, session, "https://trendpulse.blog")


def test_main_emits_actual_result_for_worker(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import src.main as entry
    from src.wordpress_client import PostStatus
    result = SimpleNamespace(success=True, post=SimpleNamespace(
        id=17, title="한글 제목", url="https://trendpulse.blog/example/", status=PostStatus.PUBLISH))
    pipeline = Mock()
    pipeline.run_single.return_value = result
    monkeypatch.setattr(entry, "BlogPipeline", lambda config: pipeline)
    monkeypatch.setattr(entry, "load_dotenv", lambda: None)
    monkeypatch.setattr(entry, "setup_logging", lambda **kwargs: None)
    monkeypatch.setattr("sys.argv", ["blog", "--mode", "general", "--topic", "한글 제목", "--writer-provider", "codex", "--auto-publish"])
    path = tmp_path / "result.json"
    monkeypatch.setenv("BLOG_RESULT_PATH", str(path))
    assert entry.main() == 0
    assert json.loads(path.read_text()) == [{"success": True, "post_id": 17,
        "url": result.post.url, "status": "publish"}]


def test_workflow_manual_gate_and_auth_cleanup():
    from pathlib import Path
    workflow = yaml.safe_load(Path('.github/workflows/auto-post.yml').read_text())
    job = workflow['jobs']['post-codex']
    assert "workflow_dispatch" in job['if']
    assert "refs/heads/main" in job['if']
    assert "post-codex" not in workflow['jobs']['retry-on-waf-block']['needs']
    assert job['concurrency']['cancel-in-progress'] is False
    assert any(step.get('if') == 'always()' and 'persist' in step.get('run', '') for step in job['steps'])
    assert not any('upload-artifact' in step.get('uses', '') for step in job['steps'])


@pytest.mark.parametrize('repo,event,ref,opt_in,allowed', [
    ('hhj4861/wp-auto-blog', 'workflow_dispatch', 'refs/heads/main', '1', True),
    ('hhj4861/wp-auto-blog', 'schedule', 'refs/heads/main', '1', True),
    ('hhj4861/wp-auto-blog', 'pull_request', 'refs/heads/main', '1', False),
    ('hhj4861/wp-auto-blog', 'workflow_dispatch', 'refs/heads/feature', '1', False),
    ('hhj4861/wp-auto-blog', 'workflow_dispatch', 'refs/heads/main', '', False),
    ('other/repo', 'workflow_dispatch', 'refs/heads/main', '1', False),
])
def test_authorized_public_manual_boundary(tmp_path, monkeypatch, repo, event, ref, opt_in, allowed):
    path = tmp_path / 'event.json'
    path.write_text(json.dumps({'repository': {'private': False, 'default_branch': 'main', 'full_name': repo}}))
    for key, value in {'GITHUB_ACTIONS': 'true', 'GITHUB_EVENT_PATH': str(path),
                       'GITHUB_REPOSITORY': repo, 'GITHUB_EVENT_NAME': event,
                       'GITHUB_REF': ref, 'BLOG_CODEX_PUBLIC_AUTOMATION': opt_in}.items():
        monkeypatch.setenv(key, value)
    if allowed:
        require_private_actions()
    else:
        with pytest.raises(RuntimeError):
            require_private_actions()
