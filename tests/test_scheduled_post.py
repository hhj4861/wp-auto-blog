from datetime import datetime, date, timedelta
import json
from pathlib import Path
import sys

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import scheduled_post as schedule
from src.posting_schedule import category_for_date


def environment(day='2026-09-14', cron='0 0 * * *', run='100', time='00:00'):
    return {'GITHUB_EVENT_NAME': 'schedule', 'GITHUB_REF': 'refs/heads/main',
            'GITHUB_REPOSITORY': 'hhj4861/wp-auto-blog', 'GITHUB_RUN_ID': run,
            'SCHEDULE_RUN_CREATED_AT': f'{day}T{time}:00Z', 'SCHEDULE_CRON': cron,
            'BLOG_MODE': 'queue', 'BLOG_PUBLISH': 'true', 'BLOG_CATEGORY': ''}


def at(day='2026-09-14', time='12:15'):
    return datetime.fromisoformat(f'{day}T{time}:00+09:00')


@pytest.mark.parametrize('day,category', [('2026-09-21', '생활정보'), ('2026-09-22', '취업'),
    ('2026-09-23', '건강'), ('2026-09-24', '생산성'), ('2026-09-25', '리뷰'), ('2026-09-26', '테크')])
def test_recovery_uses_scheduled_kst_category(tmp_path, day, category):
    result = schedule.claim(environment(day, '17,47 0-13 * * *'), tmp_path/'runs.json', at(day))
    assert result['run'] == 'true'
    assert result['category'] == category


@pytest.mark.parametrize('status', ['started', 'success', 'failure', 'cancelled'])
def test_delayed_primary_catchup_and_rerun_never_duplicate(tmp_path, status):
    path = tmp_path/'runs.json'
    env = environment(cron='17,47 0-13 * * *')
    assert schedule.claim(env, path, at())['run'] == 'true'
    if status != 'started':
        schedule.finish({**env, 'SCHEDULE_JOB_STATUS': status}, path)
    before = path.read_bytes()
    for run in ('100', '101', '102'):
        assert schedule.claim(environment(run=run), path, at(time='15:00'))['run'] == 'false'
    assert path.read_bytes() == before


@pytest.mark.parametrize('day,time,cron', [
    ('2026-09-14', '08:59', '0 0 * * *'),
    ('2026-09-15', '12:00', '0 9 * * *'),
    ('2026-09-20', '12:00', '0 2 * * 6'),
    ('2026-09-14', '12:00', 'unknown')])
def test_invalid_schedule_time_or_day_does_not_claim(tmp_path, day, time, cron):
    path = tmp_path/'runs.json'
    assert schedule.claim(environment(day, cron), path, at(day,time))['run'] == 'false'
    assert not path.exists()


def test_job_waiting_until_next_kst_day_does_not_steal_today(tmp_path):
    path = tmp_path/'runs.json'
    assert schedule.claim(environment(), path, at('2026-09-15'))['run'] == 'false'
    assert not path.exists()


def test_manual_recovery_and_late_cron_share_claim(tmp_path):
    path = tmp_path/'runs.json'
    env = {**environment(), 'GITHUB_EVENT_NAME': 'workflow_dispatch', 'SCHEDULE_RECOVERY': 'true'}
    assert schedule.claim(env, path, at())['reason'] == 'claimed'
    assert schedule.claim(environment(run='200'), path, at())['reason'] == 'already_attempted'


@pytest.mark.parametrize('change', [{'GITHUB_REF':'refs/heads/feature'},
    {'GITHUB_REPOSITORY':'other/repo'}, {'BLOG_PUBLISH':'false'}, {'BLOG_MODE':'general'},
    {'BLOG_TOPIC':'forced topic'}, {'BLOG_RESUME_DRAFT_ID':'1754'}, {'BLOG_CATEGORY':'건강'}])
def test_recovery_cannot_override_scheduled_scope(tmp_path, change):
    env = {**environment(), 'GITHUB_EVENT_NAME': 'workflow_dispatch', 'SCHEDULE_RECOVERY': 'true', **change}
    with pytest.raises(ValueError):
        schedule.claim(env, tmp_path/'runs.json', at())


def test_regular_manual_work_does_not_consume_scheduled_day(tmp_path):
    path = tmp_path/'runs.json'
    assert schedule.claim({'GITHUB_EVENT_NAME':'workflow_dispatch'}, path, at())['run'] == 'true'
    assert not path.exists()


@pytest.mark.parametrize('value', ['bad json', '{}', '{"schema_version":1,"runs":[]}',
    '{"schema_version":1,"runs":{"2026-09-14":{}}}'])
def test_corrupt_state_fails_closed(tmp_path, value):
    path=tmp_path/'runs.json'; path.write_text(value)
    with pytest.raises((ValueError, KeyError)):
        schedule.claim(environment(),path,at())


def test_finish_cannot_change_another_run(tmp_path):
    path=tmp_path/'runs.json'
    schedule.claim(environment(),path,at())
    before=path.read_bytes()
    schedule.finish({'GITHUB_RUN_ID':'999','SCHEDULE_JOB_STATUS':'success'},path)
    assert path.read_bytes()==before


def test_error_notification_contains_stage_and_link_without_exception_text(tmp_path):
    path=tmp_path/'stage'; path.write_text('selection')
    env={**environment(), 'SCHEDULE_STAGE_PATH':str(path), 'SCHEDULE_CATEGORY':'생활정보',
         'TELEGRAM_BOT_TOKEN':'never-print-this', 'ERROR':'secret details'}
    message=schedule.failure_message(env)
    assert '키워드 선정' in message and '생활정보' in message and '/runs/100' in message
    assert 'secret' not in message and 'never-print-this' not in message


def test_workflow_claim_is_serialized_durable_and_blocks_generation():
    wf=yaml.safe_load(Path('.github/workflows/auto-post.yml').read_text())
    trigger=wf.get('on',wf.get(True))
    assert trigger['schedule'][-1]['cron']=='17,47 0-13 * * *'
    job=wf['jobs']['post-queue']; steps=job['steps']
    assert job['concurrency']['group']=='trendpulse-general-posting'
    assert steps[0]['with']['ref']=='${{ github.ref }}'
    claim=next(i for i,s in enumerate(steps) if s.get('id')=='daily')
    assert 'scheduled_post.py claim' in steps[claim]['run']
    assert 'SCHEDULE_STAGE_PATH=$RUNNER_TEMP/' in steps[claim]['run']
    assert not any('runner.' in str(value) for value in job['env'].values())
    assert 'commit_coupang_state.sh' in steps[claim+1]['run']
    for step in steps[claim+2:]:
        if step.get('if')=='always()' or 'scheduled_post.py' in step.get('run',''):
            continue
        assert "steps.daily.outputs.run == 'true'" in step['if'],step
    assert 'data/scheduled_post_runs.json' in Path('scripts/commit_coupang_state.sh').read_text()
    finish=next(s for s in steps if 'scheduled_post.py finish' in s.get('run',''))
    assert "steps.daily.outputs.reason == 'claimed'" in finish['if']
    failure=next(s for s in steps if 'notify-failure' in s.get('run',''))
    assert 'failure()' in failure['if']


@pytest.mark.parametrize('day,morning,evening', [
    ('2026-09-21', '생활정보', '생산성'), ('2026-09-22', '취업', '리뷰'),
    ('2026-09-23', '건강', '테크'), ('2026-09-24', '생산성', '생활정보'),
    ('2026-09-25', '리뷰', '취업'), ('2026-09-26', '테크', '건강'),
    ('2026-09-27', '생활정보', '생산성')])
def test_two_slots_claim_finish_and_recovery_are_independent(tmp_path, day, morning, evening):
    path = tmp_path/'runs.json'
    for slot, category, utc, local, run, cron in (
        ('morning', morning, '00:00', '09:00', '100', '0 0 * * *'),
        ('evening', evening, '09:00', '18:00', '200', '0 9 * * *')):
        env = environment(day, cron, run, utc)
        result = schedule.claim(env, path, at(day, local))
        assert result['category'] == category and result['slot'] == slot
        schedule.finish({**env, 'SCHEDULE_JOB_STATUS': 'success'}, path)
        assert schedule.read_state(path)['runs'][f'{day}:{slot}']['status'] == 'success'
        for duplicate in (env, {**env, 'GITHUB_RUN_ID': run+'1', 'SCHEDULE_CRON': '17,47 0-13 * * *'},
                          {**env, 'GITHUB_EVENT_NAME': 'workflow_dispatch', 'SCHEDULE_RECOVERY': 'true'}):
            assert schedule.claim(duplicate, path, at(day, local))['reason'] == 'already_attempted'
        manual = {**env, 'GITHUB_EVENT_NAME': 'workflow_dispatch', 'SCHEDULE_RECOVERY': 'true',
                  'BLOG_CATEGORY': category}
        assert schedule.claim(manual, tmp_path/f'{slot}.json', at(day, local))['category'] == category
    assert len(schedule.read_state(path)['runs']) == 2


def test_rotation_is_balanced_in_both_slots_across_years():
    from collections import Counter
    start = date(2026, 9, 20)
    for cycle in range(70):
        days = [start + timedelta(days=cycle*6 + i) for i in range(6)]
        for slot in ('morning', 'evening'):
            assert Counter(category_for_date(day, slot) for day in days) == Counter(schedule.CATEGORIES)
        assert all(category_for_date(day, 'morning') != category_for_date(day, 'evening') for day in days)


@pytest.mark.parametrize('cron', ['0 0 * * *', '17,47 0-13 * * *'])
def test_morning_run_waiting_until_evening_cannot_claim_evening(tmp_path, cron):
    path = tmp_path/'runs.json'
    assert schedule.claim(environment(cron=cron), path, at(time='18:00'))['reason'] == 'outside_scheduled_slot'
    assert not path.exists()


def test_delayed_morning_primary_created_in_evening_is_rejected(tmp_path):
    assert schedule.claim(environment(time='10:00'), tmp_path/'runs.json', at(time='19:00'))['run'] == 'false'


@pytest.mark.parametrize('status', ['started', 'success', 'failure', 'cancelled'])
def test_legacy_daily_record_blocks_morning_only_and_preserves_history(tmp_path, status):
    path = tmp_path/'runs.json'
    old = {'run_id': '10', 'category': '생활정보', 'claimed_at': '2026-09-14T15:00:00+09:00',
           'status': status, 'completed_at': '2026-09-14T07:00:00+00:00'}
    path.write_text(json.dumps({'schema_version': 1, 'runs': {'2026-09-14': old}}))
    before = path.read_bytes()
    assert schedule.claim(environment(), path, at())['reason'] == 'already_attempted'
    assert path.read_bytes() == before
    evening = environment(cron='0 9 * * *', run='200', time='09:00')
    assert schedule.claim(evening, path, at(time='18:00'))['slot'] == 'evening'
    state = schedule.read_state(path)
    assert state['schema_version'] == 2
    assert state['runs']['2026-09-14:morning'] == {**old, 'slot': 'morning'}
    assert len(state['runs']) == 2


@pytest.mark.parametrize('status', ['started', 'success', 'failure', 'cancelled'])
def test_failed_or_finished_morning_does_not_block_evening(tmp_path, status):
    path = tmp_path/'runs.json'
    schedule.claim(environment(), path, at())
    if status != 'started':
        schedule.finish({**environment(), 'SCHEDULE_JOB_STATUS': status}, path)
    env = environment(cron='17,47 0-13 * * *', run='200', time='09:17')
    assert schedule.claim(env, path, at(time='18:17'))['slot'] == 'evening'
    schedule.finish({**env, 'SCHEDULE_JOB_STATUS': 'success'}, path)
    assert schedule.read_state(path)['runs']['2026-09-14:morning']['status'] == status


def test_sunday_run_cannot_post_on_monday(tmp_path):
    assert schedule.claim(environment('2026-09-20'), tmp_path/'runs.json',
                          at('2026-09-21'))['reason'] == 'outside_scheduled_day'


def test_workflows_research_and_post_all_scheduled_categories():
    wf = yaml.safe_load(Path('.github/workflows/auto-post.yml').read_text())
    for cron in schedule.CRONS:
        assert cron in [s['cron'] for s in wf.get('on', wf.get(True))['schedule']]
        assert f"github.event.schedule == '{cron}'" in wf['jobs']['post-queue']['if']
    research = yaml.safe_load(Path('.github/workflows/blog-keyword-select.yml').read_text())
    choices = research.get('on', research.get(True))['workflow_dispatch']['inputs']['category']['options']
    assert schedule.CATEGORIES <= set(choices)
    step = next(s for s in research['jobs']['select']['steps'] if 'SELECT_CATEGORY' in s.get('env', {}))
    assert step['env']['SELECT_CATEGORY'] == "${{ inputs.category || 'scheduled' }}"
    assert research.get('on', research.get(True))['schedule'] == [
        {'cron': '30 22 * * *'}, {'cron': '30 7 * * *'}]
    assert "github.event.schedule == '30 7 * * *' && 'evening' || 'morning'" in step['env']['SELECT_SLOT']
    assert '--slot "$SELECT_SLOT"' in step['run']


@pytest.mark.parametrize('time,slot', [('08:59', None), ('09:00', 'morning'),
    ('17:59', 'morning'), ('18:00', 'evening'), ('23:59', 'evening')])
def test_slot_boundaries_use_korean_time(time, slot):
    from datetime import timezone
    assert schedule.slot_at(at(time=time).astimezone(timezone.utc)) == slot


@pytest.mark.parametrize('key,slot', [('2026-09-14:morning', 'evening'),
    ('2026-09-14', 'morning'), ('2026-09-14:night', 'night'), ('2026-02-30:morning', 'morning')])
def test_invalid_slot_records_fail_closed(tmp_path, key, slot):
    path = tmp_path/'runs.json'
    row = {'run_id': '100', 'category': '건강', 'slot': slot, 'status': 'success',
           'claimed_at': '2026-09-14T09:00:00+09:00'}
    path.write_text(json.dumps({'schema_version': 2, 'runs': {key: row}}))
    with pytest.raises(ValueError):
        schedule.claim(environment(), path, at())


def test_one_run_cannot_own_two_slots(tmp_path):
    path = tmp_path/'runs.json'
    schedule.claim(environment(), path, at())
    env = environment(cron='0 9 * * *', time='09:00')
    assert schedule.claim(env, path, at(time='18:00'))['reason'] == 'run_already_claimed'
    assert len(schedule.read_state(path)['runs']) == 1
