from datetime import datetime, timedelta
import json
from pathlib import Path
import plistlib
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import posting_timer as timer
import scheduled_post as schedule


def at(time='09:00', day='2026-10-03'):
    return datetime.fromisoformat(f'{day}T{time}:00+09:00')


class GitHub:
    def __init__(self, ledger=None, fail=False):
        self.state = ledger or {'schema_version': 2, 'runs': {}}
        self.fail = fail
        self.calls = []
        self.reads = 0

    def ledger(self):
        self.reads += 1
        return self.state

    def dispatch(self, target):
        self.calls.append(target)
        if self.fail:
            raise timer.TimerError('unknown')


@pytest.mark.parametrize('time,target', [('08:59', None), ('09:00','morning'),
    ('17:59','morning'), ('18:00','evening'), ('23:59','evening')])
def test_kst_boundaries(time, target):
    result = timer.target_at(at(time))
    assert result == (f'2026-10-03:{target}' if target else None)
    assert timer.target_at(at(time).astimezone(schedule.timezone.utc)) == result


def test_default_is_readonly_and_before_nine_does_not_call_github(tmp_path):
    github = GitHub(); path = tmp_path/'state.json'
    assert timer.tick(github, path, at('08:59'))['status'] == 'before_first_slot'
    assert github.reads == 0
    assert timer.tick(github, path, at())['status'] == 'would_dispatch'
    assert not path.exists() and not github.calls


@pytest.mark.parametrize('status', ['started','success','failure','cancelled'])
def test_remote_attempt_prevents_any_dispatch(tmp_path, status):
    github = GitHub({'schema_version':2, 'runs': {'2026-10-03:morning':{'status':status}}})
    path = tmp_path/'state.json'
    result = timer.tick(github, path, at(), apply=True)
    assert result == {'status':'already_attempted','target':'2026-10-03:morning','outcome':status}
    assert not github.calls
    timer.tick(github, path, at('09:01'), apply=True)
    assert github.reads == 1


@pytest.mark.parametrize('fail', [False, True])
def test_delayed_or_ambiguous_dispatch_has_cooldown_and_cap(tmp_path, fail):
    github = GitHub(fail=fail); path=tmp_path/'state.json'
    status = timer.tick(github,path,at(),apply=True)['status']
    assert status == ('dispatch_unconfirmed' if fail else 'dispatch_accepted')
    assert timer.tick(github,path,at('09:01'),apply=True)['status'] == 'awaiting_claim'
    timer.tick(github,path,at('09:15'),apply=True)
    timer.tick(github,path,at('09:30'),apply=True)
    assert timer.tick(github,path,at('09:45'),apply=True)['status'] == 'unconfirmed_dispatch_limit'
    assert github.calls == ['2026-10-03:morning']*3
    assert timer.tick(github,path,at('18:00'),apply=True)['status'] == status
    assert github.calls[-1] == '2026-10-03:evening'


def test_state_is_written_before_request_and_process_death_waits(tmp_path):
    path=tmp_path/'state.json'; github=GitHub()
    def dispatch(target):
        assert timer.read_local(path)['slots'][target]['status'] == 'pending'
        raise KeyboardInterrupt()
    github.dispatch=dispatch
    with pytest.raises(KeyboardInterrupt):
        timer.tick(github,path,at(),apply=True)
    assert timer.tick(GitHub(),path,at('09:01'),apply=True)['status']=='awaiting_claim'


def test_unavailable_ledger_never_dispatches(tmp_path):
    github=GitHub()
    def offline():
        raise timer.TimerError('github_unavailable')
    github.ledger=offline
    with pytest.raises(timer.TimerError):
        timer.tick(github,tmp_path/'state.json',at(),apply=True)
    assert not github.calls and not (tmp_path/'state.json').exists()


@pytest.mark.parametrize('value', ['{', '{}', '{"version":1,"slots":[]}',
    '{"version":1,"slots":{"2026-10-03:morning":{"attempts":-1}}}'])
def test_invalid_local_state_fails_closed(tmp_path,value):
    path=tmp_path/'state.json';path.write_text(value);github=GitHub()
    with pytest.raises((ValueError, timer.TimerError, KeyError)):
        timer.tick(github,path,at(),apply=True)
    assert not github.calls


def test_sleep_recovery_checks_every_five_minutes(tmp_path):
    github=GitHub();path=tmp_path/'state.json'
    assert timer.tick(github,path,at('11:02'))['status']=='waiting_for_check'
    assert github.reads==0
    assert timer.tick(github,path,at('11:05'))['status']=='would_dispatch'


def test_timer_and_late_cron_use_single_durable_claim(tmp_path):
    path=tmp_path/'remote.json';github=GitHub()
    def dispatch(target):
        env={'GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF':'refs/heads/main',
             'GITHUB_REPOSITORY':timer.REPOSITORY,'GITHUB_RUN_ID':'123',
             'SCHEDULE_RUN_CREATED_AT':'2026-10-03T00:00:00Z','SCHEDULE_RECOVERY':'true',
             'SCHEDULE_TARGET':target,'BLOG_MODE':'queue','BLOG_PUBLISH':'true'}
        assert schedule.claim(env,path,at())['reason']=='claimed'
        late={**env,'GITHUB_EVENT_NAME':'schedule','GITHUB_RUN_ID':'456',
              'SCHEDULE_RECOVERY':'false','SCHEDULE_TARGET':'','SCHEDULE_CRON':'0 0 * * *',
              'SCHEDULE_RUN_CREATED_AT':'2026-10-03T04:07:36Z'}
        assert schedule.claim(late,path,at('13:08'))['reason']=='already_attempted'
    github.dispatch=dispatch
    timer.tick(github,tmp_path/'local.json',at(),apply=True)
    state=schedule.read_state(path)
    assert len(state['runs'])==1
    row=state['runs']['2026-10-03:morning']
    assert row['trigger']=='external_timer' and row['start_delay_seconds']==0


def test_cli_sends_fixed_main_payload_and_no_token_copy(monkeypatch):
    calls=[]
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command,0,'','')
    monkeypatch.setattr(timer.subprocess,'run',run)
    timer.GitHub('/usr/local/bin/gh').dispatch('2026-10-03:morning')
    command,kwargs=calls[0]
    assert command[:4]==['/usr/local/bin/gh','api','--hostname','github.com']
    assert command[-4:]==['--method','POST','--input','-']
    payload=json.loads(kwargs['input'])
    assert payload=={'ref':'main','inputs':{'mode':'queue','writer_provider':'codex',
        'publish':True,'scheduled_recovery':True,'scheduled_target':'2026-10-03:morning'}}


@pytest.mark.parametrize('timeout', [False,True])
def test_cli_does_not_expose_secret_errors(monkeypatch, timeout):
    def run(command,**kwargs):
        if timeout:
            raise subprocess.TimeoutExpired(command,30,stderr='super-secret')
        return subprocess.CompletedProcess(command,1,'super-secret','super-secret')
    monkeypatch.setattr(timer.subprocess,'run',run)
    with pytest.raises(timer.TimerError) as err:
        timer.GitHub('/usr/local/bin/gh').ledger()
    assert 'super-secret' not in str(err.value)


def test_plist_handles_spaces_and_has_no_credentials():
    data=plistlib.loads(timer.launchd_plist(Path('/a/python'),Path('/code with space/timer.py'),
        '/bin/gh',Path('/local state'),Path('/cloud logs')))
    assert data['StartInterval']==60 and data['RunAtLoad']
    assert data['ProgramArguments'][2]=='/code with space/timer.py'
    assert '--apply' in data['ProgramArguments']
    assert data['StandardOutPath']=='/cloud logs/posting-timer.log'
    assert 'TOKEN' not in str(data)


def test_separate_process_cannot_dispatch_while_timer_lock_is_held(tmp_path):
    import fcntl
    with (tmp_path/'timer.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result=subprocess.run([sys.executable,'-B','scripts/posting_timer.py','--apply',
                               '--gh','/usr/bin/false','--state-dir',str(tmp_path)],
                              capture_output=True,text=True,timeout=10)
    assert result.returncode==0
    assert json.loads(result.stdout)=={'status':'another_timer_running'}
    assert not (tmp_path/'dispatches.json').exists()
