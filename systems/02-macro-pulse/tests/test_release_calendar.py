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


# ── the calendar must never run dry ─────────────────────────────────────────

def test_calendar_is_not_empty_after_the_hardcoded_list_runs_out():
    """
    RELEASE_SCHEDULE stops at July 2026, so from August the app rendered
    "No releases scheduled in the next 90 days" — which reads as broken
    software, not as a missing table. Caught in a browser on the live site.
    """
    from datetime import date
    from engine.release_calendar import get_upcoming_releases
    assert get_upcoming_releases(as_of=date(2026, 8, 5), days_ahead=90)


def test_calendar_still_works_years_out():
    from datetime import date
    from engine.release_calendar import get_upcoming_releases
    for probe in (date(2027, 3, 1), date(2030, 11, 20), date(2035, 1, 2)):
        assert get_upcoming_releases(as_of=probe, days_ahead=90), probe


def test_the_imminent_release_is_included():
    """
    The release published THIS month covers LAST month. Generating from the
    current month skipped it — on 5 August that dropped July's CPI, due on
    the 12th, which is exactly the release a visitor is looking for.
    """
    from datetime import date
    from engine.release_calendar import get_upcoming_releases
    upcoming = get_upcoming_releases(as_of=date(2026, 8, 5), days_ahead=30)
    assert any(
        r.indicator == "CPI" and r.reference_period == "Jul-2026"
        and r.expected_date == date(2026, 8, 12)
        for r in upcoming
    )


def test_generated_dates_reproduce_observed_release_dates():
    """The rule was validated against every release date we hold — 6 of 6."""
    from datetime import date
    from engine.release_calendar import _publication_date
    assert _publication_date("CPI", 2026, 4) == date(2026, 5, 12)
    assert _publication_date("CPI", 2026, 6) == date(2026, 7, 13)   # 12th was a Sunday
    assert _publication_date("IIP", 2026, 3) == date(2026, 4, 28)
    assert _publication_date("IIP", 2026, 6) == date(2026, 7, 28)


def test_publication_dates_never_land_on_a_weekend():
    from datetime import date
    from engine.release_calendar import _publication_date
    for month in range(1, 13):
        for indicator in ("CPI", "IIP"):
            assert _publication_date(indicator, 2027, month).weekday() < 5


def test_december_rolls_into_the_next_year():
    from datetime import date
    from engine.release_calendar import _publication_date, generate_schedule
    assert _publication_date("CPI", 2026, 12).year == 2027
    assert generate_schedule(date(2027, 1, 5))      # January must not underflow


def test_hardcoded_entries_are_not_duplicated_by_generated_ones():
    from datetime import date
    from engine.release_calendar import get_upcoming_releases
    upcoming = get_upcoming_releases(as_of=date(2026, 6, 1), days_ahead=90)
    keys = [(r.indicator, r.reference_period) for r in upcoming]
    assert len(keys) == len(set(keys))
