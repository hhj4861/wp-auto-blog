"""TrendPulse categories and two daily slots, shared by research and posting."""
from datetime import date
from zoneinfo import ZoneInfo

KST = ZoneInfo('Asia/Seoul')
CATEGORY_ROTATION = ('생활정보', '취업', '건강', '생산성', '리뷰', '테크')
ROTATION_ANCHOR = date(2026, 9, 21)
CATEGORIES = frozenset(CATEGORY_ROTATION)
SLOTS = ('morning', 'evening')
SLOT_HOURS = {'morning': 9, 'evening': 18}


def category_for_date(day: date, slot: str = 'morning') -> str:
    if slot not in SLOTS:
        raise ValueError('invalid_schedule_slot')
    # Six calendar days give every category one morning and one evening post.
    # Missed attempts and year boundaries never move the rotation.
    offset = 0 if slot == 'morning' else 3
    return CATEGORY_ROTATION[((day - ROTATION_ANCHOR).days + offset) % len(CATEGORY_ROTATION)]


def slot_at(moment) -> str | None:
    hour = moment.astimezone(KST).hour
    if hour >= SLOT_HOURS['evening']:
        return 'evening'
    if hour >= SLOT_HOURS['morning']:
        return 'morning'
    return None
