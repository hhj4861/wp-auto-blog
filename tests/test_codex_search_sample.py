import io
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest
import yaml

from scripts import check_codex_search_sample as probe


def item_event(item=None, *, method="item/completed", thread="thread-1", turn="turn-1"):
    return {"method": method, "params": {"threadId": thread, "turnId": turn,
        "item": item or {"id": "search-1", "type": "webSearch",
            "action": {"type": "search", "query": probe.QUERY},
            "results": [{"type": "text_result", "url": "https://example.org/page",
                         "title": "private title", "snippet": "private snippet"}]}}}


def completion(*, thread="thread-1", turn="turn-1", status="completed", error=None):
    return {"method": "turn/completed", "params": {"threadId": thread,
        "turn": {"id": turn, "status": status, "error": error}}}


def handshake():
    return [{"id": 1, "result": {}}, {"id": 2, "result": {
        "thread": {"id": "thread-1", "ephemeral": True},
        "approvalPolicy": "never", "sandbox": {"type": "readOnly", "networkAccess": False},
        "modelProvider": "openai"}}, {"id": 3, "result": {"turn": {"id": "turn-1"}}}]


class InputPipe(io.BytesIO):
    def close(self):
        self.messages = [json.loads(line) for line in self.getvalue().splitlines()]
        super().close()


class FakeProcess:
    """OS pipe exercises the actual selector/JSONL reader without a subprocess."""
    def __init__(self, events, *, hanging=False, raw=None):
        read_fd, write_fd = os.pipe()
        self.stdout = os.fdopen(read_fd, "rb", buffering=0)
        self.stdin = InputPipe()
        self.pid = 99999999
        self.hanging = hanging
        self.returncode = None
        self.wait_calls = []
        data = raw if raw is not None else b"".join(
            (json.dumps(event, ensure_ascii=True) + "\n").encode() for event in events)
        os.write(write_fd, data)
        os.close(write_fd)

    def wait(self, timeout):
        self.wait_calls.append(timeout)
        if self.hanging:
            raise subprocess.TimeoutExpired("private command", timeout)
        self.returncode = 0
        return 0

    def kill(self):
        self.hanging = False
        self.returncode = -9


@pytest.fixture
def setup(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    home = tmp_path / "dedicated-codex"
    home.mkdir()
    monkeypatch.setenv("BLOG_CODEX_HOME", str(home))
    monkeypatch.setenv("BLOG_CODEX_MODEL", "gpt-5.4")
    monkeypatch.setattr("src.codex_client.shutil.which", lambda _: "/mock/codex")
    created = []

    def install(events=None, **kwargs):
        process = FakeProcess(events or [], **kwargs)
        created.append(process)
        popen = Mock(return_value=process)
        monkeypatch.setattr(probe.subprocess, "Popen", popen)
        monkeypatch.setattr(probe.os, "killpg", lambda pid, sig: process.kill())
        return process, popen

    yield home, install
    for process in created:
        if not process.stdin.closed:
            process.stdin.close()
        process.stdout.close()


def test_success_uses_bound_native_dto_and_never_prints_text(setup, monkeypatch, capsys):
    home, install = setup
    # The script must not consume or change auth; Codex alone owns refresh state.
    auth = home / "auth.json"
    auth.write_text("fake auth fixture")
    for name in ("OPENAI_API_KEY", "GOOGLE_SEARCH_API_KEY", "WORDPRESS_PASSWORD", "CODEX_ACCESS_TOKEN"):
        monkeypatch.setenv(name, "SECRET-SENTINEL")
    monkeypatch.setenv("CODEX_HOME", "/private/default-that-must-not-be-used")
    final = item_event({"id": "msg", "type": "agentMessage", "text": "SECRET-SENTINEL final URLs"})
    process, popen = install(handshake() + [item_event(), final, completion()])
    assert probe.main() == 0
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert report["reason"] == "ok"
    assert report["matching_search_actions"] == report["url_title_body_count"] == 1
    assert report["snippet_count"] == 1
    assert output.err == ""
    assert all(type(value) is int for key, value in report.items() if key != "reason")
    assert not any(text in output.out for text in ("SECRET", "private", "http", "ITQ"))
    assert auth.read_text() == "fake auth fixture"
    args, kwargs = popen.call_args
    command = args[0]
    for option in ('features.standalone_web_search=true', 'web_search="live"',
                   'forced_login_method="chatgpt"', 'cli_auth_credentials_store="file"',
                   'features.shell_tool=false', 'features.hooks=false',
                   'features.plugins=false', 'features.apps=false'):
        assert option in command
    assert command[-2:] == ["app-server", "--stdio"]
    assert "--ignore-user-config" not in command  # Not supported by app-server.
    assert set(kwargs["env"]) <= {"PATH", "HOME", "LANG", "SSL_CERT_FILE", "CODEX_HOME"}
    assert kwargs["env"]["CODEX_HOME"] == str(home)
    assert kwargs["stderr"] == subprocess.DEVNULL
    assert kwargs["start_new_session"] is True
    assert not Path(kwargs["cwd"]).exists()
    requests = process.stdin.messages
    assert [request["method"] for request in requests] == [
        "initialize", "initialized", "thread/start", "turn/start"]
    assert requests[0]["params"]["capabilities"]["experimentalApi"] is True
    params = requests[2]["params"]
    assert params["environments"] == params["selectedCapabilityRoots"] == []
    assert params["sandbox"] == "read-only" and params["approvalPolicy"] == "never"
    assert params["ephemeral"] is True and params["model"] == "gpt-5.4"
    assert requests[3]["params"]["input"] == [
        {"type": "text", "text": probe.PROMPT, "text_elements": []}]
    assert process.stdin.closed and process.stdout.closed and process.wait_calls


@pytest.mark.parametrize("results,reason,field", [
    (None, "structured_results_unavailable", "results_null_items"),
    ([], "empty_structured_results", "results_array_items"),
    ({"url": "private"}, "invalid_results_shape", "results_invalid_items"),
    ([{"url": "https://example.org/", "title": "title"}],
     "structured_fields_incomplete", "results_array_items"),
])
def test_results_absent_empty_and_partial_are_not_success(setup, capsys, results, reason, field):
    _, install = setup
    event = item_event()
    event["params"]["item"]["results"] = results
    install(handshake() + [event, completion()])
    assert probe.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["reason"] == reason and report[field] == 1


def test_missing_results_stays_distinct_from_null(setup, capsys):
    _, install = setup
    event = item_event()
    del event["params"]["item"]["results"]
    install(handshake() + [event, completion()])
    assert probe.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["results_missing_items"] == 1
    assert report["results_null_items"] == 0


def test_unbound_started_model_and_duplicate_events_cannot_inflate_results(setup, capsys):
    _, install = setup
    events = [item_event(thread="other"), item_event(turn="other"),
              item_event(method="item/started"), item_event(), item_event(),
              item_event({"type": "agentMessage", "id": "msg", "text": json.dumps(item_event())}),
              completion(thread="other"), completion(turn="other"), completion()]
    install(handshake() + events)
    assert probe.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["completed_web_items"] == report["result_count"] == 1


def test_turn_notifications_before_rpc_reply_are_bound_after_reply(setup, capsys):
    _, install = setup
    start = handshake()
    install(start[:2] + [item_event(), completion()] + start[2:])
    assert probe.main() == 0
    assert json.loads(capsys.readouterr().out)["matching_search_actions"] == 1


@pytest.mark.parametrize("action,reason", [
    ({"type": "openPage", "url": "https://example.org/"}, "unexpected_web_activity"),
    ({"type": "search", "query": "other"}, "unexpected_search_query"),
    ({"type": "search", "query": probe.QUERY, "queries": ["other"]}, "unexpected_search_query"),
    ({"type": "search", "queries": [probe.QUERY, "other"]}, "unexpected_search_query"),
    (None, "unexpected_web_activity"),
])
def test_only_single_exact_search_query_is_accepted(setup, capsys, action, reason):
    _, install = setup
    event = item_event()
    event["params"]["item"]["action"] = action
    process, _ = install(handshake() + [event, completion()])
    assert probe.main() == 1
    assert json.loads(capsys.readouterr().out)["reason"] == reason
    assert process.stdin.closed and process.stdout.closed


def test_search_queries_singleton_and_known_content_fields_are_counted():
    report = probe.empty_report()
    counts = probe.SearchCounts(report, "thread-1", "turn-1")
    event = item_event()
    event["params"]["item"]["action"] = {"type": "search", "queries": [probe.QUERY]}
    event["params"]["item"]["results"] = [
        {"url": "https://example.org/", "title": "t", "content": "c"},
        {"url": "https://example.org/2", "title": "t", "text": "t"},
        {"url": "https://user:password@example.org/", "title": "t", "snippet": "s"},
        {"url": "http://127.0.0.1/", "title": "t", "text": "s"},
        {"url": "https://example.org/3", "title": " ", "content": {"text": "not a string"}},
        "not an object",
    ]
    counts.consume(event)
    assert report["result_count"] == 6 and report["result_object_count"] == 5
    assert report["url_count"] == 3 and report["url_title_body_count"] == 2
    assert report["content_count"] == 1 and report["text_count"] == 2


@pytest.mark.parametrize("method", ["item/started", "item/completed"])
def test_second_search_is_refused(setup, capsys, method):
    _, install = setup
    first, second = item_event(method=method), item_event(method=method)
    second["params"]["item"]["id"] = "search-2"
    install(handshake() + [first, second, completion()])
    assert probe.main() == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "unexpected_web_activity"


@pytest.mark.parametrize("kind", ["commandExecution", "fileChange", "mcpToolCall", "dynamicToolCall"])
def test_other_tool_activity_fails_closed(setup, capsys, kind):
    _, install = setup
    install(handshake() + [item_event({"type": kind, "id": "tool", "text": "SECRET"})])
    assert probe.main() == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "unexpected_tool_activity"


def test_permission_request_is_rejected_without_exposing_payload(setup, capsys):
    _, install = setup
    event = {"id": 99, "method": "item/commandExecution/requestApproval",
             "params": {"command": "SECRET-SENTINEL"}}
    process, _ = install(handshake() + [event])
    assert probe.main() == 1
    output = capsys.readouterr().out
    assert json.loads(output)["reason"] == "server_request_denied"
    assert "SECRET" not in output
    rejection = process.stdin.messages[-1]
    assert rejection["id"] == 99 and rejection["error"]["code"] == -32601
    assert "result" not in rejection


@pytest.mark.parametrize("failure", ["rpc", "turn"])
def test_auth_failure_is_classified_without_any_raw_error(setup, capsys, failure):
    _, install = setup
    error = {"message": "refresh_token_revoked SECRET-SENTINEL", "data": {"key": "SECRET"}}
    events = ([{"id": 1, "error": error}] if failure == "rpc"
              else handshake() + [completion(status="failed", error=error)])
    install(events)
    assert probe.main() == 1
    output = capsys.readouterr().out
    assert json.loads(output)["reason"] == "refresh_token_revoked"
    assert "SECRET" not in output


@pytest.mark.parametrize("raw,reason", [(b"private invalid json\n", "invalid_protocol"),
    (b"[]\n", "invalid_protocol"), (b"", "unexpected_eof"),
    (b"x" * 65, "output_limit")])
def test_malformed_or_bounded_streams_fail_safely(setup, monkeypatch, capsys, raw, reason):
    _, install = setup
    monkeypatch.setattr(probe, "MAX_LINE_BYTES", 64)
    process, _ = install(raw=raw)
    assert probe.main() == 1
    output = capsys.readouterr().out
    assert json.loads(output)["reason"] == reason and "private" not in output
    assert process.stdin.closed and process.stdout.closed


def test_total_byte_limit_is_enforced(setup, monkeypatch, capsys):
    _, install = setup
    monkeypatch.setattr(probe, "MAX_STREAM_BYTES", 10)
    install(handshake())
    assert probe.main() == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "output_limit"


def test_timeout_cleans_process_group_and_does_not_log(setup, monkeypatch, capsys):
    _, install = setup
    process, _ = install(hanging=True)
    monkeypatch.setattr(probe.time, "monotonic", Mock(side_effect=[0, 238, 239, 239.5]))
    assert probe.main() == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "timeout"
    assert process.stdin.closed and process.stdout.closed
    assert process.returncode == 0 and len(process.wait_calls) == 2
    assert process.wait_calls == [1, 0.5]


def test_silent_stdout_uses_same_total_deadline(setup, monkeypatch, capsys):
    _, install = setup
    process, _ = install(hanging=True)
    selector = Mock()
    selector.select.return_value = []
    monkeypatch.setattr(probe.selectors, "DefaultSelector", Mock(return_value=selector))
    monkeypatch.setattr(probe.time, "monotonic", Mock(side_effect=[0, 0, 0, 238, 239, 239.5]))
    assert probe.main() == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "timeout"
    selector.select.assert_called_once_with(1.0)
    selector.close.assert_called_once()
    assert process.stdin.closed and process.stdout.closed
    assert process.wait_calls == [1, 0.5]


@pytest.mark.parametrize("field,value", [("approvalPolicy", "on-request"),
    ("sandbox", {"type": "workspaceWrite"}), ("modelProvider", "other"),
    ("sandbox", {"type": "readOnly", "networkAccess": True}),
    ("thread", {"id": "thread-1", "ephemeral": False})])
def test_server_must_confirm_safe_thread_before_any_model_turn(setup, capsys, field, value):
    _, install = setup
    events = handshake()
    events[1]["result"][field] = value
    process, _ = install(events)
    assert probe.main() == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "unsafe_thread_configuration"
    assert not any(event.get("method") == "turn/start" for event in process.stdin.messages)


@pytest.mark.parametrize("name", ["config.toml", ".env", "AGENTS.md", "AGENTS.override.md"])
def test_home_configuration_is_refused_without_reading(setup, capsys, name):
    home, install = setup
    (home / name).write_text("SECRET-SENTINEL")
    _, popen = install()
    assert probe.main() == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "unexpected_home_configuration"
    popen.assert_not_called()


def test_untrusted_actions_and_default_home_never_launch(setup, monkeypatch, capsys, tmp_path):
    _, install = setup
    _, popen = install()
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    event = tmp_path / "event.json"
    event.write_text(json.dumps({"repository": {"private": True,
        "full_name": "owner/repo", "default_branch": "main"}}))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    assert probe.main() == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "probe_failed"
    monkeypatch.delenv("GITHUB_ACTIONS")
    monkeypatch.setenv("BLOG_CODEX_HOME", str(Path.home() / ".codex"))
    assert probe.main() == 1
    popen.assert_not_called()
    assert json.loads(capsys.readouterr().out)["reason"] == "probe_failed"


def test_no_search_and_unknown_exception_do_not_become_success(setup, monkeypatch, capsys):
    _, install = setup
    install(handshake() + [completion()])
    assert probe.main() == 1
    assert json.loads(capsys.readouterr().out)["reason"] == "no_observed_search"
    monkeypatch.setattr(probe, "CodexSubscriptionClient", Mock(side_effect=RuntimeError("SECRET")))
    assert probe.main() == 1
    output = capsys.readouterr()
    assert json.loads(output.out)["reason"] == "probe_failed"
    assert output.err == "" and "SECRET" not in output.out


def test_actions_diagnostic_is_manual_main_only_and_reuses_serial_auth_lifecycle():
    path = Path(".github/workflows/codex-search-sample.yml")
    source = path.read_text()
    workflow = yaml.safe_load(source)
    # PyYAML's YAML 1.1 loader interprets the Actions 'on' key as True.
    triggers = workflow.get("on", workflow.get(True))
    assert triggers == {"workflow_dispatch": None}
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"] == {
        "group": "trendpulse-general-posting", "cancel-in-progress": False}
    assert set(workflow["jobs"]) == {"sample"}
    job = workflow["jobs"]["sample"]
    assert job["if"] == "github.ref == 'refs/heads/main'"
    assert job["timeout-minutes"] == 10
    assert "strategy" not in job
    assert job["env"] == {"BLOG_CODEX_PUBLIC_AUTOMATION": "1"}
    steps = job["steps"]
    named = {step.get("name"): step for step in steps if "name" in step}
    assert named["Install pinned Codex analyst"]["run"] == "npm install -g @openai/codex@0.153.4"
    restore = named["Restore dedicated Codex authentication"]
    inspect = named["Inspect native search result field counts"]
    persist = named["Persist refreshed Codex auth and clean up"]
    assert steps.index(restore) < steps.index(inspect) < steps.index(persist)
    assert restore["env"] == {
        "CODEX_AUTH_JSON": "${{ secrets.CODEX_AUTH_JSON }}",
        "WORKER_ADMIN_TOKEN": "${{ secrets.CODEX_SECRET_WRITE_TOKEN }}"}
    assert "BLOG_CODEX_HOME=$RUNNER_TEMP/trendpulse-codex" in restore["run"]
    assert restore["run"].count("python scripts/codex_worker_auth.py restore") == 1
    assert inspect["run"] == "python scripts/check_codex_search_sample.py"
    assert "env" not in inspect
    assert persist["if"] == "always()"
    assert persist["run"] == "python scripts/codex_worker_auth.py persist"
    assert persist["env"] == {"GH_TOKEN": "${{ secrets.CODEX_SECRET_WRITE_TOKEN }}"}
    for name in ("GOOGLE_", "NAVER_", "OPENAI_API_KEY", "ANTHROPIC_", "WORDPRESS_", "WP_PASSWORD"):
        assert name not in source
    assert "upload-artifact" not in source and "main.py" not in source
