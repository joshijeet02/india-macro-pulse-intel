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
    body = to_ics(releases)
    assert body.count("BEGIN:VEVENT") == 2
    assert body.count("END:VEVENT") == 2
    assert "CPI release" in body
    assert "IIP release" in body
    assert "20260414" in body  # date format
    assert "20260430" in body


def test_to_ics_default_uses_full_schedule():
    body = to_ics()
    assert body.count("BEGIN:VEVENT") == len(RELEASE_SCHEDULE)


def test_reference_period_conversion():
    assert reference_period_to_month_str("Mar-2026") == "2026-03"
    assert reference_period_to_month_str("Dec-2025") == "2025-12"
    # Bad input → returned as-is
    assert reference_period_to_month_str("not a date") == "not a date"
