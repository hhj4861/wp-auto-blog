#!/usr/bin/env python3
"""Independent timer -> main workflow_dispatch. Read-only unless --apply.

Run every minute from launchd or an always-on host. GitHub's durable claim,
not local cache, is the authority preventing duplicate publication.
"""
import argparse
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys

from scheduled_post import KST, save, slot_at, timestamp, validate_state

REPOSITORY = 'hhj4861/wp-auto-blog'
WORKFLOW = 'auto-post.yml'
MAX_ATTEMPTS = 3
COOLDOWN = timedelta(minutes=15)


class TimerError(Exception):
    pass


def target_at(now):
    now = now.astimezone(KST)
    slot = slot_at(now)
    return f'{now.date()}:{slot}' if slot else None


def read_local(path):
    if not path.exists():
        return {'version': 1, 'slots': {}}
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('slots'), dict):
        raise TimerError('invalid_local_state')
    for key, row in data['slots'].items():
        day, slot = key.split(':')
        datetime.strptime(day, '%Y-%m-%d')
        if slot not in ('morning', 'evening') or not isinstance(row, dict):
            raise TimerError('invalid_local_state')
        if (type(row.get('attempts')) is not int or not 0 <= row['attempts'] <= MAX_ATTEMPTS
                or row.get('status') not in ('pending', 'accepted', 'unknown', 'claimed')):
            raise TimerError('invalid_local_state')
        timestamp(row['last_attempt'])
    return data


class GitHub:
    def __init__(self, executable):
        self.executable = executable

    def api(self, endpoint, payload=None):
        command = [self.executable, 'api', '--hostname', 'github.com',
                   f'repos/{REPOSITORY}/{endpoint}']
        if payload is None:
            command += ['-H', 'Accept: application/vnd.github.raw+json']
        else:
            command += ['--method', 'POST', '--input', '-']
        try:
            result = subprocess.run(command, input=json.dumps(payload) if payload else None,
                                    text=True, capture_output=True, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise TimerError('github_unavailable') from None
        if result.returncode:
            # CLI errors can contain credentials. Never emit stdout/stderr.
            raise TimerError('github_request_failed')
        return result.stdout

    def ledger(self):
        return validate_state(json.loads(self.api('contents/data/scheduled_post_runs.json?ref=main')))

    def dispatch(self, target):
        self.api(f'actions/workflows/{WORKFLOW}/dispatches', {
            'ref': 'main', 'inputs': {'mode': 'queue', 'writer_provider': 'codex',
                                     'publish': True, 'scheduled_recovery': True,
                                     'scheduled_target': target}})


def tick(github, path, now, apply=False):
    target = target_at(now)
    if target is None:
        return {'status': 'before_first_slot'}
    local = read_local(path)
    row = local['slots'].get(target)
    if row and row['status'] == 'claimed':
        return {'status': 'already_claimed', 'target': target}
    # After the first 30 minutes, read every five minutes to permit wake-up catchup.
    local_now = now.astimezone(KST)
    target_hour = 9 if target.endswith(':morning') else 18
    if (local_now.hour != target_hour or local_now.minute >= 30) and local_now.minute % 5:
        return {'status': 'waiting_for_check', 'target': target}
    ledger = github.ledger()  # Missing, corrupt, unauthorized or offline => no dispatch.
    if target in ledger['runs']:
        if apply:
            local['slots'][target] = {'attempts': row['attempts'] if row else 0,
                                     'last_attempt': now.isoformat(), 'status': 'claimed'}
            persist(path, local, now)
        return {'status': 'already_attempted', 'target': target,
                'outcome': ledger['runs'][target]['status']}
    if row:
        elapsed = now - timestamp(row['last_attempt'])
        if elapsed < COOLDOWN:
            return {'status': 'awaiting_claim', 'target': target}
        if row['attempts'] >= MAX_ATTEMPTS:
            return {'status': 'unconfirmed_dispatch_limit', 'target': target}
    if not apply:
        return {'status': 'would_dispatch', 'target': target}
    # Persist BEFORE POST. On timeout or process death a second process waits;
    # retries are bounded and share the same server-side date/slot claim.
    row = {'attempts': row['attempts'] + 1 if row else 1,
           'last_attempt': now.isoformat(), 'status': 'pending'}
    local['slots'][target] = row
    persist(path, local, now)
    try:
        github.dispatch(target)
    except TimerError:
        row['status'] = 'unknown'
        persist(path, local, now)
        return {'status': 'dispatch_unconfirmed', 'target': target}
    row['status'] = 'accepted'
    persist(path, local, now)
    return {'status': 'dispatch_accepted', 'target': target}


def persist(path, data, now):
    cutoff = (now.astimezone(KST).date() - timedelta(days=14)).isoformat()
    data['slots'] = {key: row for key, row in data['slots'].items() if key[:10] >= cutoff}
    save(path, data)


def launchd_plist(python, script, gh, state_dir, log_dir):
    # RunAtLoad/interval also catch a missed calendar tick after login or sleep.
    # Calendar uses the Mac timezone; interval + target_at always enforce KST.
    return plistlib.dumps({
        'Label': 'blog.trendpulse.posting-timer',
        'ProgramArguments': [str(python), '-B', str(script), '--apply',
                             '--gh', str(gh), '--state-dir', str(state_dir)],
        'StartInterval': 60, 'RunAtLoad': True,
        'StartCalendarInterval': [{'Hour': 9, 'Minute': 0}, {'Hour': 18, 'Minute': 0}],
        'ProcessType': 'Background',
        'StandardOutPath': str(log_dir / 'posting-timer.log'),
        'StandardErrorPath': str(log_dir / 'posting-timer-error.log'),
        'EnvironmentVariables': {'PYTHONDONTWRITEBYTECODE': '1'},
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Actually dispatch main; default only inspects')
    parser.add_argument('--state-dir', type=Path, required=True, help='Local runtime directory, outside Git/iCloud')
    parser.add_argument('--gh', default=shutil.which('gh'))
    parser.add_argument('--print-launchd-plist', action='store_true')
    parser.add_argument('--log-dir', type=Path)
    args = parser.parse_args()
    try:
        if not args.gh or not Path(args.gh).is_absolute():
            raise TimerError('absolute_gh_path_required')
        directory = args.state_dir.expanduser().resolve()
        if args.print_launchd_plist:
            if args.apply or not args.log_dir:
                raise TimerError('plist_requires_log_dir_and_no_apply')
            sys.stdout.buffer.write(launchd_plist(Path(sys.executable).resolve(), Path(__file__).resolve(),
                                                 args.gh, directory, args.log_dir.expanduser().resolve()))
            return 0
        github = GitHub(args.gh)
        path = directory / 'dispatches.json'
        if not args.apply:
            result = tick(github, path, datetime.now(timezone.utc))
        else:
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            with (directory / 'timer.lock').open('a') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    print('{"status":"another_timer_running"}')
                    return 0
                os.chmod(lock.name, 0o600)
                result = tick(github, path, datetime.now(timezone.utc), apply=True)
        result['checked_at'] = datetime.now(timezone.utc).isoformat()
        print(json.dumps(result))
        return int(result['status'] in ('dispatch_unconfirmed', 'unconfirmed_dispatch_limit'))
    except (TimerError, ValueError, KeyError, TypeError, OSError):
        print('{"status":"timer_failed","action":"check GitHub access and local/remote state"}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
