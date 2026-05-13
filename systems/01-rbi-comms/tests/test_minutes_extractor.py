"""Tests for the Minutes per-member analysis."""
import json
from pathlib import Path

import pytest

from engine.minutes_extractor import analyze_minutes, member_view_summary
from scrapers.rbi_resolution import extract_press_release

FIXTURES = Path(__file__).parent / "fixtures" / "html"
SEED_DOCS = Path(__file__).parent.parent / "data" / "rbi_communications.json"


def _load_seed_minutes(date_prefix: str) -> dict:
    """Load a Minutes document from the seed corpus by publication-date prefix."""
    docs = json.loads(SEED_DOCS.read_text())["documents"]
    for doc in docs:
        if (doc.get("published_at") or "").startswith(date_prefix) and \
           doc.get("document_type") == "MPC Minutes":
            return doc
    raise LookupError(f"No MPC Minutes found for prefix {date_prefix}")


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


# ─── Middle-initial name parsing (regression: Prof. Jayanth R. Varma) ─────────
#
# Prof. Varma is the most-studied MPC dissenter in India's monetary history.
# His name carries a middle initial ("R.") that the prior regex pattern
# `[A-Z][a-zA-Z]+` could not match — every Varma-era Minutes silently lost his
# vote (vote table) and his individual stance (Statement section).
#
# These tests pin the correct behavior across the rate-resolution table and the
# Statement section headers so the regression cannot return.

def test_vote_table_captures_varma_with_middle_initial():
    """Vote-table parser must recognise 'Prof. Jayanth R. Varma No'.

    Synthetic Minutes mirroring the Feb 2023 structure (4-2 on the rate, with
    Goyal and Varma dissenting). Each member needs a Statement section so the
    aggregate vote_summary can be computed (it iterates `members`).
    """
    text = (
        "Voting on the Resolution to increase the policy repo rate to 6.50 per "
        "cent Member Vote "
        "Dr. Shashanka Bhide Yes "
        "Dr. Ashima Goyal No "
        "Prof. Jayanth R. Varma No "
        "Dr. Rajiv Ranjan Yes "
        "Dr. Michael Debabrata Patra Yes "
        "Shri Shaktikanta Das Yes\n\n"
        "Statement by Dr. Shashanka Bhide\n\nBhide rationale.\n\n"
        "Statement by Dr. Ashima Goyal\n\nGoyal rationale.\n\n"
        "Statement by Prof. Jayanth R. Varma\n\nVarma rationale.\n\n"
        "Statement by Dr. Rajiv Ranjan\n\nRanjan rationale.\n\n"
        "Statement by Dr. Michael Debabrata Patra\n\nPatra rationale.\n\n"
        "Statement by Shri Shaktikanta Das\n\nGovernor rationale.\n"
    )
    analysis = analyze_minutes(text, "2023-02-22")
    assert len(analysis.members) == 6, \
        f"expected 6 members, got {[m.name for m in analysis.members]}"
    summary = analysis.vote_summary
    assert summary["yes"] == 4, f"expected 4 yes, got {summary}"
    assert summary["no"] == 2, f"expected 2 no (Goyal + Varma), got {summary}"
    assert "Jayanth R. Varma" in analysis.dissenting_members, \
        f"Varma missing from dissenters: {analysis.dissenting_members}"


def test_statement_section_captures_varma_with_middle_initial():
    """'Statement by Prof. Jayanth R. Varma' must be recognised as a section."""
    text = (
        "Statement by Dr. Shashanka Bhide\n\nSome view from Bhide.\n\n"
        "Statement by Prof. Jayanth R. Varma\n\n"
        "I vote against the part of the resolution on remaining focused on "
        "the withdrawal of accommodation. The real rate is now adequately "
        "positive and further withdrawal is unwarranted.\n\n"
        "Statement by Dr. Michael Debabrata Patra\n\nGovernor's view.\n"
    )
    analysis = analyze_minutes(text, "2022-12-21")
    names = {m.name for m in analysis.members}
    assert "Jayanth R. Varma" in names, f"Varma section dropped; parsed names: {names}"


def test_feb_2023_minutes_attributes_varma_dissent():
    """End-to-end on the real Feb 2023 RBI Minutes: 4-2, Goyal + Varma dissent."""
    doc = _load_seed_minutes("2023-02")
    analysis = analyze_minutes(doc["full_text"], doc["published_at"])
    summary = member_view_summary(analysis)
    assert summary["members_parsed"] == 6, \
        f"Feb 2023 has 6 MPC members, parser found {summary['members_parsed']}"
    assert summary["vote_for"] == 4, summary
    assert summary["vote_against"] == 2, summary
    dissenters = set(summary["dissenting_members"])
    assert "Ashima Goyal" in dissenters, f"Goyal missing: {dissenters}"
    assert "Jayanth R. Varma" in dissenters, f"Varma missing: {dissenters}"
