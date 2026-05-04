"""Tests for the RBI listing-page parser (offline fixture)."""
from pathlib import Path

from scrapers._rbi_api import discover_current_cycle_documents

FIXTURE = Path(__file__).parent / "fixtures" / "html" / "annualpolicy_landing.html"


def test_discovery_returns_at_least_3_docs():
    html = FIXTURE.read_text()
    docs = discover_current_cycle_documents(html)
    assert len(docs) >= 3


def test_discovery_classifies_kinds():
    html = FIXTURE.read_text()
    docs = discover_current_cycle_documents(html)
    kinds = {d["kind"] for d in docs}
    assert "mpc_minutes" in kinds
    assert "mpc_statement" in kinds
    assert "press_conference" in kinds


def test_discovery_extracts_prids():
    html = FIXTURE.read_text()
    docs = discover_current_cycle_documents(html)
    statement = next(d for d in docs if d["kind"] == "mpc_statement")
    assert statement["prid"] == 62515


def test_discovery_extracts_speech_id():
    html = FIXTURE.read_text()
    docs = discover_current_cycle_documents(html)
    pc = next(d for d in docs if d["kind"] == "press_conference")
    assert pc["speech_id"] == 1551


def test_discovery_dedupes():
    """Same doc listed multiple times should appear only once."""
    html = FIXTURE.read_text() + FIXTURE.read_text()  # double the page
    docs = discover_current_cycle_documents(html)
    # Should still match deduped by (kind, id)
    statement_count = sum(1 for d in docs if d["kind"] == "mpc_statement")
    assert statement_count == 1
