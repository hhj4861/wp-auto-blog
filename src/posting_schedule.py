"""TrendPulse daily categories, shared by research and durable posting claims."""
from datetime import date
from zoneinfo import ZoneInfo

KST = ZoneInfo('Asia/Seoul')
WEEKDAY_CATEGORIES = ('생활정보', '취업', '생활정보', '취업', '생활정보', '건강')
SUNDAY_CATEGORIES = ('생산성', '리뷰', '테크')
SUNDAY_ANCHOR = date(2026, 9, 20)
CATEGORIES = frozenset((*WEEKDAY_CATEGORIES, *SUNDAY_CATEGORIES))


def category_for_date(day: date) -> str:
    if day.weekday() < 6:
        return WEEKDAY_CATEGORIES[day.weekday()]
    # Calendar-based rotation stays stable across retries, missed weeks and years.
    week = (day - SUNDAY_ANCHOR).days // 7
    return SUNDAY_CATEGORIES[week % len(SUNDAY_CATEGORIES)]
