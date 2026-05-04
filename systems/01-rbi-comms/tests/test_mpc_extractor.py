"""Unit tests for the MPC field extractor (regex-based)."""
import pytest

from engine.mpc_extractor import (
    extract_mpc_decision, extract_projections, extract_repo_rate,
    extract_stance, extract_vote_split,
)


def test_extract_repo_rate_unchanged():
    text = (
        "the MPC voted unanimously to keep the policy repo rate under the "
        "liquidity adjustment facility (LAF) unchanged at 5.25 per cent"
    )
    rate, bps = extract_repo_rate(text)
    assert rate == pytest.approx(5.25)
    assert bps == 0


def test_extract_repo_rate_cut():
    text = (
        "the policy repo rate was reduced by 25 basis points to 6.00 per cent"
    )
    rate, bps = extract_repo_rate(text)
    assert rate == pytest.approx(6.00)
    assert bps == -25


def test_extract_repo_rate_hike():
    text = (
        "the policy repo rate was increased by 50 basis points to 5.40 per cent"
    )
    rate, bps = extract_repo_rate(text)
    assert rate == pytest.approx(5.40)
    assert bps == 50


def test_extract_repo_rate_rejects_out_of_bounds():
    """Catches a misparse where some other 'X per cent' string slips in."""
    text = "policy repo rate at 99.9 per cent"  # out of [0, 12]
    rate, bps = extract_repo_rate(text)
    assert rate is None


def test_extract_vote_split_explicit():
    text = "5 members voted in favour of the proposal while 1 member voted against"
    f, a = extract_vote_split(text)
    assert f == 5 and a == 1


def test_extract_vote_split_unanimous():
    text = "the MPC voted unanimously to keep the rate unchanged"
    f, a = extract_vote_split(text)
    assert f == 6 and a == 0


def test_extract_vote_split_must_sum_to_six():
    """Reject parses that don't add up — common misparse."""
    text = "3 members in favour and 4 against"  # 7 total — invalid
    f, a = extract_vote_split(text)
    assert f is None and a is None


def test_extract_stance_neutral():
    text = "The MPC also decided to continue with the neutral stance"
    label, phrase = extract_stance(text)
    assert label == "neutral"


def test_extract_stance_withdrawal():
    text = "The stance remains focused on withdrawal of accommodation"
    label, phrase = extract_stance(text)
    assert label == "withdrawal_of_accommodation"


def test_extract_stance_accommodative():
    text = "The MPC decided to remain accommodative as long as necessary"
    label, _ = extract_stance(text)
    assert label == "accommodative"


def test_extract_projections_gdp_and_cpi():
    text = (
        "Considering all these factors, real GDP growth for 2026-27 is "
        "projected at 7.5 per cent. CPI inflation for 2026-27 is projected "
        "at 4.0 per cent."
    )
    p = extract_projections(text)
    assert p["gdp_projection_curr_value"] == pytest.approx(7.5)
    assert p["gdp_projection_curr_fy"] == "2026-27"
    assert p["cpi_projection_curr_value"] == pytest.approx(4.0)
    assert p["cpi_projection_curr_fy"] == "2026-27"


def test_extract_projections_handles_missing():
    p = extract_projections("no projections in this text")
    assert "gdp_projection_curr_value" not in p


def test_combined_extractor_returns_full_record():
    text = (
        "After detailed assessment, the MPC voted to keep the policy repo rate "
        "unchanged at 6.50 per cent. "
        "5 members voted in favour, 1 against. Stance to remain neutral. "
        "real GDP growth for 2025-26 is projected at 6.5 per cent. "
        "CPI inflation for 2025-26 is projected at 4.5 per cent."
    )
    record = extract_mpc_decision(text, publication_date="2025-08-08")
    assert record["repo_rate"] == 6.50
    assert record["vote_for"] == 5 and record["vote_against"] == 1
    assert record["stance_label"] == "neutral"
    assert record["gdp_projection_curr_value"] == 6.5
    assert record["cpi_projection_curr_value"] == 4.5
