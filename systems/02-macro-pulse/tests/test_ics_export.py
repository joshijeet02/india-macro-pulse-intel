"""Smoke tests for the ICS calendar export."""
from datetime import date

from engine.release_calendar import (
    RELEASE_SCHEDULE, ScheduledRelease, reference_period_to_month_str, to_ics,
)


def test_to_ics_contains_required_envelope():
    body = to_ics([])
    assert body.startswith("BEGIN:VCALENDAR")
    assert "END:VCALENDAR" in body
    assert "VERSION:2.0" in body
    assert "PRODID:" in body


def test_to_ics_emits_one_vevent_per_release():
    releases = [
        ScheduledRelease("CPI", "Mar-2026", date(2026, 4, 14)),
        ScheduledRelease("IIP", "Feb-2026", date(2026, 4, 30)),
    ]
    body = to_ics(releases, include_past=True)
    assert body.count("BEGIN:VEVENT") == 2
    assert body.count("END:VEVENT") == 2
    assert "CPI release" in body
    assert "IIP release" in body
    assert "20260414" in body  # date format
    assert "20260430" in body


def test_to_ics_default_skips_past_releases():
    """By default, past releases are filtered out — users importing the
    calendar care about what's coming, not stale events."""
    past = ScheduledRelease("CPI", "Jan-2020", date(2020, 2, 12))
    future = ScheduledRelease("CPI", "Jan-2099", date(2099, 2, 12))
    body = to_ics([past, future])
    assert body.count("BEGIN:VEVENT") == 1
    assert "20990212" in body
    assert "20200212" not in body


def test_to_ics_include_past_overrides_filter():
    past = ScheduledRelease("CPI", "Jan-2020", date(2020, 2, 12))
    body = to_ics([past], include_past=True)
    assert "20200212" in body


def test_reference_period_conversion():
    assert reference_period_to_month_str("Mar-2026") == "2026-03"
    assert reference_period_to_month_str("Dec-2025") == "2025-12"
    # Bad input → returned as-is
    assert reference_period_to_month_str("not a date") == "not a date"
