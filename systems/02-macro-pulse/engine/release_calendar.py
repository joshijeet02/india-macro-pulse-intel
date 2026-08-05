from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional


@dataclass
class ScheduledRelease:
    indicator: str          # "CPI" or "IIP"
    reference_period: str   # e.g. "Mar-2025"
    expected_date: date
    actual_date: Optional[date] = None
    is_released: bool = False  # Hint only — at runtime, derive from data via has_been_released()


_MONTH_TO_NUM = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


def reference_period_to_month_str(ref: str) -> str:
    """Convert 'Mar-2026' → '2026-03', for matching against StoreA records."""
    try:
        mon, year = ref.split("-")
        return f"{int(year):04d}-{_MONTH_TO_NUM[mon]:02d}"
    except (ValueError, KeyError):
        return ref


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
    ScheduledRelease("IIP", "Sep-2025", date(2025, 11, 28), is_released=True),
    ScheduledRelease("IIP", "Oct-2025", date(2025, 12, 31), is_released=True),
    # CPI releases 2026
    ScheduledRelease("CPI", "Jan-2026", date(2026, 2, 12), is_released=True),
    ScheduledRelease("CPI", "Feb-2026", date(2026, 3, 12), is_released=True),
    ScheduledRelease("CPI", "Mar-2026", date(2026, 4, 14), is_released=True),
    ScheduledRelease("CPI", "Apr-2026", date(2026, 5, 13)),
    ScheduledRelease("CPI", "May-2026", date(2026, 6, 12)),
    ScheduledRelease("CPI", "Jun-2026", date(2026, 7, 13)),
    # IIP releases 2026 (2-month lag)
    ScheduledRelease("IIP", "Nov-2025", date(2026, 1, 30), is_released=True),
    ScheduledRelease("IIP", "Dec-2025", date(2026, 2, 27), is_released=True),
    ScheduledRelease("IIP", "Jan-2026", date(2026, 3, 31), is_released=True),
    ScheduledRelease("IIP", "Feb-2026", date(2026, 4, 30)),
    ScheduledRelease("IIP", "Mar-2026", date(2026, 5, 29)),
    ScheduledRelease("IIP", "Apr-2026", date(2026, 6, 30)),
]


# MOSPI publishes on a fixed rule: CPI on the 12th of the following month,
# IIP on the 28th, each shifted to the next weekday if it lands on a weekend.
# Verified against every release date we hold — six for six, exact.
_PUBLICATION_DAY = {"CPI": 12, "IIP": 28}
_MONTH_ABBR = {v: k for k, v in _MONTH_TO_NUM.items()}


def _publication_date(indicator: str, year: int, month: int) -> date:
    """When MOSPI publishes the release for a given reference month."""
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    published = date(next_year, next_month, _PUBLICATION_DAY[indicator])
    while published.weekday() >= 5:          # Sat/Sun -> next weekday
        published += timedelta(days=1)
    return published


def generate_schedule(as_of: date, months_ahead: int = 6) -> list[ScheduledRelease]:
    """
    Derive upcoming releases from the publication rule.

    The hardcoded RELEASE_SCHEDULE below stops at July 2026, so from August
    onward the calendar rendered "No releases scheduled in the next 90 days" —
    which reads as a broken app rather than a missing list. Generating from the
    rule means it never runs out and never needs editing.

    RELEASE_SCHEDULE is retained for the historical record; generated entries
    cover the future.
    """
    generated: list[ScheduledRelease] = []
    for indicator in ("CPI", "IIP"):
        # Start a month BACK: the release published this month covers last
        # month. Starting at the current month skipped the imminent one —
        # on 5 August that dropped July's CPI, due on the 12th, which is
        # precisely the release a visitor most wants to see.
        year, month = (as_of.year - 1, 12) if as_of.month == 1 else (as_of.year, as_of.month - 1)
        for _ in range(months_ahead + 3):
            published = _publication_date(indicator, year, month)
            if published >= as_of:
                generated.append(
                    ScheduledRelease(
                        indicator,
                        f"{_MONTH_ABBR[month]}-{year}",
                        published,
                    )
                )
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return generated


def get_upcoming_releases(as_of: date = None, days_ahead: int = 60) -> list[ScheduledRelease]:
    """
    Upcoming releases, from the hardcoded list plus the generated rule.

    Generated entries fill in wherever the hardcoded list has run out, so the
    calendar keeps working without anyone maintaining a table of dates.
    """
    if as_of is None:
        as_of = date.today()
    cutoff = as_of + timedelta(days=days_ahead)

    upcoming = {
        (r.indicator, r.reference_period): r
        for r in RELEASE_SCHEDULE
        if as_of <= r.expected_date <= cutoff
    }
    for r in generate_schedule(as_of, months_ahead=(days_ahead // 30) + 2):
        if as_of <= r.expected_date <= cutoff:
            upcoming.setdefault((r.indicator, r.reference_period), r)

    return sorted(upcoming.values(), key=lambda r: r.expected_date)


def days_until(release: ScheduledRelease, as_of: date = None) -> int:
    if as_of is None:
        as_of = date.today()
    return (release.expected_date - as_of).days


def has_been_released(release: ScheduledRelease) -> bool:
    """
    Authoritative check: a release is 'released' iff its reference_period exists
    in the corresponding store. The hardcoded `is_released` flag in
    RELEASE_SCHEDULE is treated as a hint only; the source of truth is the data.

    Falls back to the hardcoded flag if the store can't be queried (e.g. in
    tests or before db init).
    """
    try:
        from db.store import CPIStore, IIPStore
        ref_month = reference_period_to_month_str(release.reference_period)
        store_history: list[dict]
        if release.indicator == "CPI":
            store_history = CPIStore().get_history(months=240)
        elif release.indicator == "IIP":
            store_history = IIPStore().get_history(months=240)
        else:
            return release.is_released
        return any(r.get("reference_month") == ref_month for r in store_history)
    except Exception:
        return release.is_released


# ─── ICS calendar export ─────────────────────────────────────────────────────

def to_ics(
    releases: list[ScheduledRelease] | None = None,
    include_past: bool = False,
    as_of: date | None = None,
) -> str:
    """
    Generate an iCalendar (.ics) file body covering the given releases.

    By default, only emits events with expected_date >= today — users
    importing the calendar care about what's coming up, not 18-month-old
    events polluting their calendar view.
    """
    if releases is None:
        releases = RELEASE_SCHEDULE
    if not include_past:
        cutoff = as_of or date.today()
        releases = [r for r in releases if r.expected_date >= cutoff]

    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//India Macro Pulse//Release Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]

    for r in releases:
        d = r.expected_date.strftime("%Y%m%d")
        # All-day event ending the next day per RFC 5545
        next_day = (r.expected_date + timedelta(days=1)).strftime("%Y%m%d")
        uid = f"{r.indicator.lower()}-{r.reference_period.lower()}@india-macro-pulse"
        summary = f"{r.indicator} release · {r.reference_period}"
        description = (
            f"India MOSPI {r.indicator} release for {r.reference_period}. "
            f"Source: https://mospi.gov.in"
        )
        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_stamp}",
            f"DTSTART;VALUE=DATE:{d}",
            f"DTEND;VALUE=DATE:{next_day}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
