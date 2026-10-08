"""Slot inventory: refill ahead of slots and never leave a slot empty while stock exists."""
from datetime import datetime

import pytest

from src import topic_inventory as inventory
from src.posting_schedule import category_for_date


def item(category, score=50.0, fresh=True, status='pending'):
    return {'category': category, 'keyword': f'{category}{score}', 'topic': f'{category} 주제 {score}',
            'score': score, 'status': status, 'fresh': fresh}


def is_fresh(row, category, now=None):
    return row['fresh'] and row['status'] == 'pending' and row['category'] == category


def at(text):
    return datetime.fromisoformat(text + '+09:00')


def test_counts_only_fresh_pending_items_per_category():
    queue = [item('테크'), item('테크'), item('건강', fresh=False), item('리뷰', status='completed')]
    counts = inventory.fresh_counts(queue, at('2026-10-08T12:00'), fresh=is_fresh)
    assert counts['테크'] == 2
    assert counts['건강'] == 0 and counts['리뷰'] == 0
    assert set(counts) == set(inventory.CATEGORY_ROTATION)


def test_upcoming_categories_follow_the_slot_rotation_from_now():
    now = at('2026-10-08T12:00')  # after the morning slot, before the evening slot
    day = now.date()
    expected = [category_for_date(day, 'evening'),
                category_for_date(day.fromordinal(day.toordinal() + 1), 'morning'),
                category_for_date(day.fromordinal(day.toordinal() + 1), 'evening')]
    assert inventory.upcoming_categories(now, 3) == list(dict.fromkeys(expected))


def test_refill_prefers_empty_upcoming_slot_categories_then_other_empty_categories():
    now = at('2026-10-08T12:00')
    upcoming = inventory.upcoming_categories(now, 3)
    stocked = upcoming[0]
    queue = [item(stocked)]
    order = inventory.refill_categories(queue, now, limit=6, fresh=is_fresh)
    assert stocked not in order
    assert order[:len(upcoming) - 1] == upcoming[1:]
    assert set(order) == set(inventory.CATEGORY_ROTATION) - {stocked}
    assert inventory.refill_categories(queue, now, limit=2, fresh=is_fresh) == upcoming[1:3]


def test_refill_returns_nothing_when_every_category_is_stocked():
    queue = [item(category) for category in inventory.CATEGORY_ROTATION]
    assert inventory.refill_categories(queue, at('2026-10-08T12:00'), limit=2, fresh=is_fresh) == []


def test_pick_keeps_the_slot_category_when_it_has_stock():
    queue = [item('테크', 40), item('건강', 90)]
    assert inventory.pick_category(queue, '테크', at('2026-10-08T09:00'), fresh=is_fresh) == '테크'


def test_pick_falls_back_to_the_best_scored_other_category_when_slot_category_is_empty():
    queue = [item('테크', fresh=False), item('건강', 60), item('리뷰', 80), item('취업', 99, status='completed')]
    assert inventory.pick_category(queue, '테크', at('2026-10-08T09:00'), fresh=is_fresh) == '리뷰'


def test_pick_returns_none_without_any_fresh_stock():
    queue = [item('테크', fresh=False)]
    assert inventory.pick_category(queue, '테크', at('2026-10-08T09:00'), fresh=is_fresh) is None


def test_default_freshness_is_the_publication_gate():
    # Legacy pending rows (no market evidence) must never count as stock.
    legacy = {'category': '생활정보', 'topic': '휴면계좌 조회 방법', 'status': 'pending'}
    now = at('2026-10-08T12:00')
    assert inventory.fresh_counts([legacy], now)['생활정보'] == 0
    assert inventory.pick_category([legacy], '생활정보', now) is None


def test_slot_pick_cli_prints_the_publishing_category_or_fails_without_stock(tmp_path, monkeypatch, capsys):
    import json
    import scripts.pick_slot_category as cli
    queue = tmp_path / 'queue.json'
    queue.write_text(json.dumps([item('건강', 70)], ensure_ascii=False))
    monkeypatch.setattr(cli, 'QUEUE', queue)
    monkeypatch.setattr(cli, 'fresh_market_item', is_fresh)
    monkeypatch.setattr(cli, 'load_dotenv', lambda: None)
    monkeypatch.setattr(cli, 'existing_titles', lambda: [])
    assert cli.main(['--preferred', '테크']) == 0
    assert capsys.readouterr().out.strip() == '건강'
    queue.write_text('[]')
    assert cli.main(['--preferred', '테크']) == 1
    assert capsys.readouterr().out.strip() == ''


def test_slot_pick_cli_skips_stock_that_duplicates_an_existing_post(tmp_path, monkeypatch, capsys):
    # E2E 37753649624: the only 테크 stock duplicated a post published after its
    # selection, so the writer skipped it and the fallback slot failed.
    import json
    import scripts.pick_slot_category as cli
    duplicate_stock = {**item('테크', 90), 'keyword': '윈도우재설치', 'topic': '윈도우재설치 방법'}
    queue = tmp_path / 'queue.json'
    queue.write_text(json.dumps([duplicate_stock, item('건강', 60)], ensure_ascii=False))
    monkeypatch.setattr(cli, 'QUEUE', queue)
    monkeypatch.setattr(cli, 'fresh_market_item', is_fresh)
    monkeypatch.setattr(cli, 'load_dotenv', lambda: None)
    monkeypatch.setattr(cli, 'existing_titles', lambda: ['윈도우재설치 방법'])
    assert cli.main(['--preferred', '생활정보']) == 0
    assert capsys.readouterr().out.strip() == '건강'


@pytest.mark.parametrize('local,blocked', [
    ('2026-10-09T07:00', False), ('2026-10-09T07:49', False), ('2026-10-09T07:50', True),
    ('2026-10-09T09:00', True), ('2026-10-09T09:44', True), ('2026-10-09T09:45', False),
    ('2026-10-09T13:00', False), ('2026-10-09T16:50', True), ('2026-10-09T18:44', True),
    ('2026-10-09T18:45', False), ('2026-10-09T03:00', False)])
def test_refill_never_starts_where_it_could_delay_a_posting_slot(local, blocked):
    # Refill shares the posting concurrency group and can run 60 minutes; GitHub
    # schedules are often hours late (the 03:00 refill had not started by 07:01).
    assert inventory.near_posting_slot(at(local)) is blocked


def test_scheduled_refill_near_a_slot_exits_without_research(tmp_path, monkeypatch, capsys):
    import scripts.select_blog_keywords as cli
    data = tmp_path / 'data'
    data.mkdir()
    (data / 'topic_queue_general.json').write_text('[]')
    monkeypatch.setattr(cli, 'ROOT', tmp_path)
    monkeypatch.setattr(cli, 'REPORT', data / 'report.json')
    monkeypatch.setattr(cli, 'load_dotenv', lambda: None)
    monkeypatch.setattr(cli, 'near_posting_slot', lambda now: True)
    monkeypatch.setattr(cli, 'existing_titles', lambda: (_ for _ in ()).throw(AssertionError('no WordPress read')))
    monkeypatch.setattr(cli, 'select_category', lambda *a, **k: (_ for _ in ()).throw(AssertionError('no research')))
    monkeypatch.setenv('SELECT_SLOT_GUARD', '1')
    monkeypatch.setattr('sys.argv', ['select', '--category', 'inventory', '--enqueue'])
    assert cli.main() == 0
    assert 'near a posting slot' in capsys.readouterr().out
