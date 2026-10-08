"""Pre-verified topic stock for the posting slots.

Selection runs ahead of the slots and enqueues every category it can verify.
A slot consumes its own category's stock first and, when that is empty,
another category's fresh stock instead of publishing nothing. Freshness is
always the publication gate itself (fresh_market_item), never a cached flag.
"""
from datetime import datetime, timedelta

from src.market_topics import fresh_market_item
from src.posting_schedule import CATEGORY_ROTATION, KST, SLOT_HOURS, SLOTS, category_for_date


def fresh_counts(queue, now, *, fresh=fresh_market_item):
    counts = dict.fromkeys(CATEGORY_ROTATION, 0)
    for row in queue:
        category = row.get('category') if isinstance(row, dict) else None
        if category in counts and fresh(row, category, now):
            counts[category] += 1
    return counts


def upcoming_categories(now, slots=3):
    """Categories of the next slots that start after now, in posting order."""
    local, found = now.astimezone(KST), []
    day = local.date()
    while len(found) < slots:
        for slot in SLOTS:
            start = datetime(day.year, day.month, day.day, SLOT_HOURS[slot], tzinfo=KST)
            if start > local and len(found) < slots:
                found.append(category_for_date(day, slot))
        day += timedelta(days=1)
    return list(dict.fromkeys(found))


# Refill shares the posting concurrency group and may run up to 60 minutes.
REFILL_GUARD_BEFORE = timedelta(minutes=70)
REFILL_GUARD_AFTER = timedelta(minutes=45)


def near_posting_slot(now):
    """True where a starting refill could delay a 09:00/18:00 KST posting slot."""
    local = now.astimezone(KST)
    for hour in SLOT_HOURS.values():
        slot = local.replace(hour=hour, minute=0, second=0, microsecond=0)
        if slot - REFILL_GUARD_BEFORE <= local < slot + REFILL_GUARD_AFTER:
            return True
    return False


def refill_categories(queue, now, limit, *, fresh=fresh_market_item):
    """Empty categories, nearest upcoming slots first, then spare stock for fallback."""
    counts = fresh_counts(queue, now, fresh=fresh)
    order = list(dict.fromkeys([*upcoming_categories(now), *CATEGORY_ROTATION]))
    return [category for category in order if counts[category] == 0][:max(0, limit)]


def pick_category(queue, preferred, now, *, fresh=fresh_market_item):
    """The slot's category when stocked, otherwise the best-scored stocked category."""
    stocked = [row for row in queue if isinstance(row, dict)
               and row.get('category') in CATEGORY_ROTATION and fresh(row, row['category'], now)]
    if any(row['category'] == preferred for row in stocked):
        return preferred
    best = max(stocked, key=lambda row: row.get('score', 0), default=None)
    return best['category'] if best else None
