"""Tests for the plain-English MPC summary."""
from engine.plain_summary import render_plain_summary


def test_unanimous_unchanged_neutral():
    decision = {
        "meeting_date": "2026-04-08",
        "repo_rate": 5.25, "repo_rate_change_bps": 0,
        "vote_for": 6, "vote_against": 0,
        "stance_label": "neutral",
        "cpi_projection_curr_value": 4.6, "cpi_projection_curr_fy": "2026-27",
        "gdp_projection_curr_value": 6.9, "gdp_projection_curr_fy": "2026-27",
    }
    text = render_plain_summary(decision, prior_decision=None)
    assert "5.25%" in text
    assert "unanimous" in text.lower()
    assert "neutral" in text.lower()
    assert "wait-and-see" in text.lower() or "wait and see" in text.lower()


def test_rate_cut_explanation():
    decision = {
        "meeting_date": "2025-12-05",
        "repo_rate": 5.25, "repo_rate_change_bps": -25,
        "vote_for": 6, "vote_against": 0,
        "stance_label": "neutral",
    }
    text = render_plain_summary(decision)
    assert "cut" in text.lower()
    assert "cheaper" in text.lower() or "fall" in text.lower()


def test_rate_hike_explanation():
    decision = {
        "meeting_date": "2025-04-01",
        "repo_rate": 6.50, "repo_rate_change_bps": +25,
        "vote_for": 5, "vote_against": 1,
        "stance_label": "withdrawal_of_accommodation",
    }
    text = render_plain_summary(decision)
    assert "raised" in text.lower() or "hike" in text.lower() or "go up" in text.lower()


def test_dissent_surfaced():
    decision = {
        "meeting_date": "2025-04-01",
        "repo_rate": 6.50, "repo_rate_change_bps": 0,
        "vote_for": 4, "vote_against": 2,
        "stance_label": "neutral",
    }
    text = render_plain_summary(decision)
    assert "dissent" in text.lower() or "4-2" in text or "2 member" in text


def test_stance_change_called_out():
    decision = {
        "meeting_date": "2026-04-08",
        "repo_rate": 5.25, "repo_rate_change_bps": 0,
        "vote_for": 6, "vote_against": 0,
        "stance_label": "neutral",
    }
    prior = {
        "meeting_date": "2026-02-06",
        "repo_rate": 5.25,
        "stance_label": "accommodative",
    }
    text = render_plain_summary(decision, prior)
    assert "change" in text.lower() or "shift" in text.lower()
