"""
Integration tests against real RBI Governor's Statement HTML fixtures.

These are the highest-value tests in the suite — they exercise the full
ingestion pipeline (HTML extraction → MPC field extraction → stance engine)
against actual RBI press release pages downloaded during the spike.

Without these, the synthetic-only tests would have shipped a parser that
silently mis-extracts values when the real page format differs.
"""
from pathlib import Path

import pytest

from engine.mpc_extractor import extract_mpc_decision
from engine.stance_engine import analyze_communication
from scrapers.rbi_resolution import extract_press_release

FIXTURES = Path(__file__).parent / "fixtures" / "html"


@pytest.fixture(scope="module")
def april_2026() -> dict:
    """Apr 8 2026 Governor's Statement (PRID 62515)."""
    html = (FIXTURES / "governor_statement_2026_04_08.html").read_text()
    return extract_press_release(html)


@pytest.fixture(scope="module")
def feb_2026() -> dict:
    """Feb 6 2026 Governor's Statement (PRID 62170)."""
    html = (FIXTURES / "governor_statement_2026_02_06.html").read_text()
    return extract_press_release(html)


# ─── Extraction (HTML → structured doc) ──────────────────────────────────────

def test_april_extraction_metadata(april_2026):
    assert april_2026 is not None
    assert april_2026["publication_date"] == "2026-04-08"
    assert "Governor" in april_2026["title"]
    assert "April 08, 2026" in april_2026["title"]
    assert april_2026["press_release_id"] == "2026-2027/37"
    assert len(april_2026["paragraphs"]) >= 25


def test_february_extraction_metadata(feb_2026):
    assert feb_2026["publication_date"] == "2026-02-06"
    assert "February 06, 2026" in feb_2026["title"]
    assert len(feb_2026["paragraphs"]) >= 25


def test_april_paragraph_4_contains_repo_decision(april_2026):
    """Paragraph 4 of Governor's Statements always carries the rate decision."""
    paras = april_2026["paragraphs"]
    p4 = paras[3]  # 0-indexed; "1. ..." is paras[0]
    assert p4.startswith("4.")
    assert "repo rate" in p4.lower()
    assert "5.25 per cent" in p4 or "5.25%" in p4


# ─── MPC Decision extraction (full pipeline) ─────────────────────────────────

def test_april_decision_repo_rate(april_2026):
    d = extract_mpc_decision(april_2026["full_text"], publication_date=april_2026["publication_date"])
    assert d["repo_rate"] == pytest.approx(5.25)
    assert d["repo_rate_change_bps"] == 0  # unchanged


def test_april_decision_vote_split(april_2026):
    d = extract_mpc_decision(april_2026["full_text"])
    # April 2026 was a unanimous decision per the prose
    assert d["vote_for"] == 6
    assert d["vote_against"] == 0


def test_april_decision_stance(april_2026):
    d = extract_mpc_decision(april_2026["full_text"])
    assert d["stance_label"] == "neutral"


def test_april_decision_projections(april_2026):
    d = extract_mpc_decision(april_2026["full_text"])
    # GDP and CPI projections cited in the text:
    # "real GDP growth for 2026-27 is projected at 6.9 per cent"
    # "CPI inflation for 2026-27 is projected at 4.6 per cent"
    assert d["gdp_projection_curr_value"] == pytest.approx(6.9)
    assert d["gdp_projection_curr_fy"] == "2026-27"
    assert d["cpi_projection_curr_value"] == pytest.approx(4.6)
    assert d["cpi_projection_curr_fy"] == "2026-27"


def test_february_decision_extracts_consistently(feb_2026):
    d = extract_mpc_decision(feb_2026["full_text"])
    assert d["repo_rate"] == pytest.approx(5.25)
    assert d["vote_for"] == 6 and d["vote_against"] == 0
    assert d["stance_label"] == "neutral"


# ─── Stance engine on real text ──────────────────────────────────────────────

def test_april_stance_engine_returns_evidence(april_2026):
    sig = analyze_communication(april_2026["full_text"])
    assert sig.stance.label is not None
    # April was a "neutral" stance — engine should reflect that
    assert sig.stance.label == "neutral"
    # Evidence list non-empty (at minimum the "neutral stance" phrase)
    assert any("neutral" in p.lower() for p, _, _ in sig.stance.evidence)


def test_real_text_back_compat_aggregates(april_2026):
    """Aggregate fields used by legacy UI / store consumers must populate."""
    sig = analyze_communication(april_2026["full_text"])
    record = sig.to_record()
    for k in ("hawkish_score", "dovish_score", "net_score", "tone_label",
              "policy_bias", "inflation_mentions", "growth_mentions",
              "liquidity_mentions", "stance_score", "stance_label",
              "growth_assessment", "inflation_assessment", "risk_balance",
              "liquidity_stance", "forward_guidance"):
        assert k in record, f"missing key {k}"
