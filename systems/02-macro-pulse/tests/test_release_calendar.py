from datetime import date
import pytest
from engine.release_calendar import get_upcoming_releases, days_until, ScheduledRelease


def test_get_upcoming_returns_future_only():
    """Releases before as_of date are excluded."""
    as_of = date(2025, 5, 1)
    upcoming = get_upcoming_releases(as_of=as_of, days_ahead=60)
    for r in upcoming:
        assert r.expected_date >= as_of


def test_days_ahead_filter():
    """Only releases within days_ahead window are returned."""
    as_of = date(2025, 5, 1)
    upcoming = get_upcoming_releases(as_of=as_of, days_ahead=30)
    for r in upcoming:
        assert (r.expected_date - as_of).days <= 30


def test_days_until_positive():
    as_of = date(2025, 4, 28)
    release = ScheduledRelease(
        indicator="CPI",
        reference_period="Mar-2025",
        expected_date=date(2025, 5, 13),
    )
    assert days_until(release, as_of=as_of) == 15


def test_days_until_today():
    today = date.today()
    release = ScheduledRelease(
        indicator="IIP",
        reference_period="Mar-2025",
        expected_date=today,
    )
    assert days_until(release) == 0


def test_release_schedule_has_both_indicators():
    """Schedule includes both CPI and IIP releases."""
    upcoming = get_upcoming_releases(as_of=date(2025, 4, 1), days_ahead=365)
    indicators = {r.indicator for r in upcoming}
    assert "CPI" in indicators
    assert "IIP" in indicators
