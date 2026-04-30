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


def get_upcoming_releases(as_of: date = None, days_ahead: int = 60) -> list[ScheduledRelease]:
    if as_of is None:
        as_of = date.today()
    cutoff = as_of + timedelta(days=days_ahead)
    return [r for r in RELEASE_SCHEDULE if as_of <= r.expected_date <= cutoff]


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

def to_ics(releases: list[ScheduledRelease] | None = None) -> str:
    """
    Generate an iCalendar (.ics) file body covering the given releases (or
    the full RELEASE_SCHEDULE). Suitable for `st.download_button` →
    "Add to Google Calendar / Apple Calendar".
    """
    if releases is None:
        releases = RELEASE_SCHEDULE

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
