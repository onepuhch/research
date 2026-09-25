"""NYSE regular-session calendar shared by return evaluation and the screener.

Published holidays and early closes only; an unlisted year raises instead of
guessing. Renew EARLY and HOLIDAYS each year from the NYSE schedule.
"""
from datetime import date, datetime, timedelta, timezone

EARLY = {2026: {"2026-11-27", "2026-12-24"}, 2027: {"2027-11-26"}}
HOLIDAYS = set(('2026-01-01 2026-01-19 2026-02-16 2026-04-03 2026-05-25 '
                '2026-06-19 2026-07-03 2026-09-07 2026-11-26 2026-12-25 '
                '2027-01-01 2027-01-18 2027-02-15 2027-03-26 2027-05-31 '
                '2027-06-18 2027-07-05 2027-09-06 2027-11-25 2027-12-24').split())


def close_time(day):
    """UTC close of the regular session on day, or None when the market is closed."""
    if day.year not in EARLY:
        raise ValueError('trading calendar needs renewal')
    if day.weekday() >= 5 or day.isoformat() in HOLIDAYS:
        return None
    march = date(day.year, 3, 1)
    november = date(day.year, 11, 1)
    dst_start = march + timedelta(days=(6-march.weekday()) % 7 + 7)
    dst_end = november + timedelta(days=(6-november.weekday()) % 7)
    offset = 4 if dst_start <= day < dst_end else 5
    hour = 13 if day.isoformat() in EARLY[day.year] else 16
    return datetime(day.year, day.month, day.day, hour+offset, tzinfo=timezone.utc)
