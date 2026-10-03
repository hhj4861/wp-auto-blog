"""Run the actual PHP cron logic with a fake GitHub boundary; never send a dispatch."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PHP = shutil.which("php")
SCRIPT = Path(__file__).resolve().parents[1] / "scripts/hostinger_posting_timer.php"
pytestmark = pytest.mark.skipif(not PHP, reason="PHP CLI is required for hosting timer tests")


def php(code, directory, *args):
    """Execute PHP and decode its bounded JSON result."""
    result = subprocess.run(
        [PHP, "-r", "require $argv[1]; " + code, str(SCRIPT), str(directory), *args],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def tick(directory, times, *, ledger=None, apply=True, failure=False):
    """Exercise the real state machine with an isolated fake API."""
    return php(
        """
        $config = json_decode($argv[3], true);
        $calls = []; $results = []; $pending = [];
        $api = function($method,$path,$payload) use (&$calls,&$pending,$config,$argv) {
            $calls[] = [$method,$path,$payload];
            if ($method === 'GET') return $config['ledger'];
            $state = tp_local($argv[2].'/timer-state.json');
            $pending[] = $state['slots'][$payload['inputs']['scheduled_target']]['status'];
            if ($config['failure']) throw new RuntimeException('secret-must-not-appear');
            return '';
        };
        foreach ($config['times'] as $time) {
            try {
                $results[] = tp_tick(new DateTimeImmutable($time),$argv[2],$api,$config['apply']);
            }
            catch (Throwable $e) { $results[] = ['error'=>true]; }
        }
        echo json_encode(['results'=>$results,'calls'=>$calls,'pending'=>$pending]);
    """,
        directory,
        json.dumps(
            {
                "times": times,
                "ledger": ledger or '{"schema_version":2,"runs":{}}',
                "apply": apply,
                "failure": failure,
            }
        ),
    )


def at(time):
    """Return a fixed Korean timestamp for deterministic scheduling."""
    return f"2026-10-03T{time}:00+09:00"


@pytest.mark.parametrize(
    "time,slot",
    [
        ("08:59", None),
        ("09:00", "morning"),
        ("17:59", "morning"),
        ("18:00", "evening"),
        ("23:59", "evening"),
    ],
)
def test_kst_boundaries_independent_of_server_timezone(tmp_path, time, slot):
    """Resolve both server UTC and Korean time to the same slot."""
    result = php(
        """$now = new DateTimeImmutable($argv[3]);
        echo json_encode([tp_target($now),tp_target($now->setTimezone(new DateTimeZone('UTC')))]);
    """,
        tmp_path,
        at(time),
    )
    expected = f"2026-10-03:{slot}" if slot else None
    assert result == [expected, expected]


def test_readonly_and_before_slot_do_not_mutate(tmp_path):
    """Keep inspection mode free of state writes and POST requests."""
    result = tick(tmp_path, [at("08:59"), at("09:00")], apply=False)
    assert [r["status"] for r in result["results"]] == ["before_first_slot", "would_dispatch"]
    assert [c[0] for c in result["calls"]] == ["GET"]
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("status", ["started", "success", "failure", "cancelled"])
def test_any_remote_attempt_stops_dispatch_and_caches_claim(tmp_path, status):
    """Preserve durable claims even when an earlier attempt failed."""
    ledger = {
        "schema_version": 2,
        "runs": {
            "2026-10-03:morning": {
                "run_id": "123",
                "status": status,
                "slot": "morning",
                "category": "생활정보",
                "claimed_at": at("09:00"),
            }
        },
    }
    result = tick(tmp_path, [at("09:00"), at("09:01")], ledger=json.dumps(ledger))
    assert [r["status"] for r in result["results"]] == ["already_attempted", "already_claimed"]
    assert len(result["calls"]) == 1


@pytest.mark.parametrize("failure", [False, True])
def test_ambiguous_response_waits_caps_retries_and_isolates_next_slot(tmp_path, failure):
    """Persist intent before dispatch and bound retries per slot."""
    result = tick(
        tmp_path,
        [at(t) for t in ["09:00", "09:01", "09:15", "09:30", "09:45", "18:00"]],
        failure=failure,
    )
    dispatch = "dispatch_unconfirmed" if failure else "dispatch_accepted"
    assert [r["status"] for r in result["results"]] == [
        dispatch,
        "awaiting_claim",
        dispatch,
        dispatch,
        "unconfirmed_dispatch_limit",
        dispatch,
    ]
    posts = [c for c in result["calls"] if c[0] == "POST"]
    assert len(posts) == 4 and result["pending"] == ["pending"] * 4
    assert posts[-1][2] == {
        "ref": "main",
        "inputs": {
            "mode": "queue",
            "writer_provider": "codex",
            "publish": True,
            "scheduled_recovery": True,
            "scheduled_target": "2026-10-03:evening",
        },
    }
    assert "secret-must-not-appear" not in json.dumps(result)
    assert (tmp_path / "timer-state.json").stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "ledger",
    [
        "{",
        "{}",
        '{"schema_version":2,"runs":[]}',
        '{"schema_version":3,"runs":{}}',
        '{"schema_version":2,"runs":{"2026-02-30:morning":{}}}',
    ],
)
def test_corrupt_remote_fails_without_dispatch(tmp_path, ledger):
    """Never publish when remote claim state is unreadable."""
    result = tick(tmp_path, [at("09:00")], ledger=ledger)
    assert result["results"] == [{"error": True}]
    assert [c[0] for c in result["calls"]] == ["GET"]
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "stamp",
    [
        "tomorrow",
        "2026-10-03T09:00:00",
        "2026-02-30T09:00:00+09:00",
        "2026-10-03T25:00:00Z",
        "2026-10-03T09:00:00+99:99",
    ],
)
def test_invalid_timestamp_rejected(tmp_path, stamp):
    """Reject normalized invalid dates and timezone-free timestamps."""
    assert php(
        """try { tp_stamp($argv[3]); echo 'false'; }
        catch (Throwable $e) { echo 'true'; }""",
        tmp_path,
        stamp,
    )


@pytest.mark.parametrize("change", ["bad_json", "invalid_date", "bad_attempts", "symlink"])
def test_corrupt_local_state_never_contacts_github(tmp_path, change):
    """Stop before network access when local state cannot be trusted."""
    path = tmp_path / "timer-state.json"
    data = {
        "version": 1,
        "slots": {
            "2026-10-03:morning": {"attempts": 1, "status": "pending", "last_attempt": at("09:00")}
        },
    }
    if change == "invalid_date":
        data["slots"]["2026-02-30:morning"] = data["slots"].pop("2026-10-03:morning")
    if change == "bad_attempts":
        data["slots"]["2026-10-03:morning"]["attempts"] = 4
    if change == "symlink":
        path.symlink_to(tmp_path / "absent")
    else:
        path.write_text("{" if change == "bad_json" else json.dumps(data))
    result = tick(tmp_path, [at("09:00")])
    assert result["results"] == [{"error": True}] and not result["calls"]


def test_reduced_polling_after_first_half_hour(tmp_path):
    """Reduce unclaimed-slot reads after the initial scheduling window."""
    result = tick(tmp_path, [at("09:31"), at("09:35")], apply=False)
    assert [r["status"] for r in result["results"]] == ["waiting_for_check", "would_dispatch"]
    assert len(result["calls"]) == 1


@pytest.mark.parametrize("mode", ["missing", "public", "broad_token", "symlink", "private"])
def test_token_requires_private_scoped_file(tmp_path, mode):
    """Reject shared permissions, symlinks, and broad token formats."""
    path = tmp_path / "github-token.txt"
    if mode == "symlink":
        path.symlink_to(tmp_path / "absent")
    elif mode != "missing":
        path.write_text(("ghp_" if mode == "broad_token" else "github_pat_") + "dummy" * 10)
        path.chmod(0o644 if mode == "public" else 0o600)
    result = php(
        """try { tp_token($argv[2]); echo 'true'; }
        catch (Throwable $e) { echo 'false'; }""",
        tmp_path,
    )
    assert result is (mode == "private")


def test_http_rejects_unexpected_method_or_endpoint_without_network(tmp_path):
    """Keep HTTP calls restricted to the two intended operations."""
    assert (
        php(
            """$errors = 0;
        foreach ([['POST','contents/data/scheduled_post_runs.json?ref=main'],
                  ['GET','actions/workflows/auto-post.yml/dispatches'],
                  ['POST','https://example.com']] as [$method,$path]) {
            try { tp_http($argv[2],$method,$path,null); }
            catch (Throwable $e) { if ($e->getMessage() === 'invalid_request') $errors++; }
        } echo json_encode($errors);""",
            tmp_path,
        )
        == 3
    )


def test_actual_cli_rejects_arguments_and_missing_credentials_without_network(tmp_path):
    """Report configuration errors through real CLI exit codes."""
    copied = tmp_path / "timer.php"
    shutil.copyfile(SCRIPT, copied)
    for args, reason in [
        (["--invalid"], "invalid_arguments"),
        (["--apply"], "private_token_file_required"),
    ]:
        proc = subprocess.run([PHP, str(copied), *args], capture_output=True, text=True, timeout=10)
        assert proc.returncode == 1
        assert json.loads(proc.stdout)["reason"] == reason


def test_actual_cli_lock_collision_exits_without_dispatch(tmp_path):
    """Respect a lock held by an independent process before any network call."""
    import fcntl

    copied = tmp_path / "timer.php"
    shutil.copyfile(SCRIPT, copied)
    token = tmp_path / "github-token.txt"
    token.write_text("github_pat_" + "dummy" * 10)
    token.chmod(0o600)
    with (tmp_path / "timer.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        proc = subprocess.run(
            [PHP, str(copied), "--apply"], capture_output=True, text=True, timeout=10
        )
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["status"] == "another_timer_running"
