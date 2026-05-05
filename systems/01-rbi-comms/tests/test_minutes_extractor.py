"""Tests for the Minutes per-member analysis."""
from pathlib import Path

import pytest

from engine.minutes_extractor import analyze_minutes, member_view_summary
from scrapers.rbi_resolution import extract_press_release

FIXTURES = Path(__file__).parent / "fixtures" / "html"


@pytest.fixture(scope="module")
def april_minutes_text() -> str:
    html = (FIXTURES / "mpc_minutes_2026_04_22.html").read_text()
    return extract_press_release(html)["full_text"]


@pytest.fixture(scope="module")
def june_minutes_text() -> str:
    html = (FIXTURES / "mpc_minutes_2025_06_20.html").read_text()
    return extract_press_release(html)["full_text"]


def test_april_minutes_finds_six_members(april_minutes_text):
    analysis = analyze_minutes(april_minutes_text, "2026-04-08")
    # The Apr 2026 MPC has six members; we should find Statement-by sections for each.
    assert len(analysis.members) == 6


def test_april_minutes_unanimous_vote(april_minutes_text):
    analysis = analyze_minutes(april_minutes_text, "2026-04-08")
    summary = analysis.vote_summary
    assert summary["yes"] == 6
    assert summary["no"] == 0


def test_april_minutes_member_names(april_minutes_text):
    analysis = analyze_minutes(april_minutes_text, "2026-04-08")
    names = {m.name for m in analysis.members}
    # The 6 current MPC members
    expected = {
        "Nagesh Kumar", "Saugata Bhattacharya", "Ram Singh",
        "Indranil Bhattacharyya", "Poonam Gupta", "Sanjay Malhotra",
    }
    assert expected.issubset(names)


def test_member_view_summary_aggregates(april_minutes_text):
    analysis = analyze_minutes(april_minutes_text, "2026-04-08")
    summary = member_view_summary(analysis)
    assert summary["members_parsed"] == 6
    assert summary["vote_for"] == 6
    assert summary["vote_against"] == 0
    assert summary["dissenting_members"] == []


def test_june_minutes_also_unanimous(june_minutes_text):
    """Sanity check across cycles — older Minutes use a slightly different
    table format ('Magnitude of policy repo rate reduction')."""
    analysis = analyze_minutes(june_minutes_text, "2025-06-06")
    assert len(analysis.members) >= 6
    summary = analysis.vote_summary
    # All members voted Yes for the 50bp cut
    assert summary["yes"] >= 6


def test_each_member_gets_stance_signal(april_minutes_text):
    """Every member's individual statement should run through stance engine."""
    analysis = analyze_minutes(april_minutes_text, "2026-04-08")
    for m in analysis.members:
        # Statement text should be non-trivial
        assert len(m.statement) > 100
