from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional


@dataclass
class ScheduledRelease:
    indicator: str          # "CPI" or "IIP"
    reference_period: str   # e.g. "Mar-2025"
    expected_date: date
    actual_date: Optional[date] = None
    is_released: bool = False


# MOSPI CPI: released ~12th of the following month
# MOSPI IIP: released ~28th of the following month (2-month lag)
RELEASE_SCHEDULE: list[ScheduledRelease] = [
    # CPI releases 2025
    ScheduledRelease("CPI", "Feb-2025", date(2025, 3, 12), is_released=True),
    ScheduledRelease("CPI", "Mar-2025", date(2025, 4, 14), is_released=True),
    ScheduledRelease("CPI", "Apr-2025", date(2025, 5, 13)),
    ScheduledRelease("CPI", "May-2025", date(2025, 6, 12)),
    ScheduledRelease("CPI", "Jun-2025", date(2025, 7, 14)),
    ScheduledRelease("CPI", "Jul-2025", date(2025, 8, 12)),
    ScheduledRelease("CPI", "Aug-2025", date(2025, 9, 12)),
    ScheduledRelease("CPI", "Sep-2025", date(2025, 10, 14)),
    ScheduledRelease("CPI", "Oct-2025", date(2025, 11, 12)),
    ScheduledRelease("CPI", "Nov-2025", date(2025, 12, 12)),
    ScheduledRelease("CPI", "Dec-2025", date(2026, 1, 13)),
    # IIP releases 2025 (2-month lag)
    ScheduledRelease("IIP", "Jan-2025", date(2025, 3, 28), is_released=True),
    ScheduledRelease("IIP", "Feb-2025", date(2025, 4, 30), is_released=True),
    ScheduledRelease("IIP", "Mar-2025", date(2025, 5, 30)),
    ScheduledRelease("IIP", "Apr-2025", date(2025, 6, 30)),
    ScheduledRelease("IIP", "May-2025", date(2025, 7, 31)),
    ScheduledRelease("IIP", "Jun-2025", date(2025, 8, 29)),
    ScheduledRelease("IIP", "Jul-2025", date(2025, 9, 30)),
    ScheduledRelease("IIP", "Aug-2025", date(2025, 10, 31)),
    ScheduledRelease("IIP", "Sep-2025", date(2025, 11, 28)),
    ScheduledRelease("IIP", "Oct-2025", date(2025, 12, 31)),
]


def get_upcoming_releases(as_of: date = None, days_ahead: int = 60) -> list[ScheduledRelease]:
    if as_of is None:
        as_of = date.today()
    cutoff = as_of + timedelta(days=days_ahead)
    return [r for r in RELEASE_SCHEDULE if as_of <= r.expected_date <= cutoff]


def days_until(release: ScheduledRelease, as_of: date = None) -> int:
    if as_of is None:
        as_of = date.today()
    return (release.expected_date - as_of).days
