"""Tests for the rule-based statement archetype classifier."""
from engine.archetype import classify_statement, find_most_similar_meeting


def test_rate_cut_unambiguous():
    decision = {"repo_rate": 5.50, "repo_rate_change_bps": -50, "stance_label": "neutral"}
    a = classify_statement(decision, prior_decision=None)
    assert a.label == "rate_cut"
    assert "50bp" in a.rationale or "50" in a.rationale


def test_rate_hike_unambiguous():
    decision = {"repo_rate": 6.50, "repo_rate_change_bps": +25, "stance_label": "withdrawal_of_accommodation"}
    a = classify_statement(decision, prior_decision=None)
    assert a.label == "rate_hike"


def test_hawkish_pivot_on_stance_change():
    decision = {"repo_rate": 6.50, "repo_rate_change_bps": 0, "stance_label": "withdrawal_of_accommodation"}
    prior = {"repo_rate": 6.50, "stance_label": "neutral"}
    a = classify_statement(decision, prior)
    assert a.label == "hawkish_pivot"


def test_pre_cut_signal_on_stance_softening():
    decision = {"repo_rate": 6.50, "repo_rate_change_bps": 0, "stance_label": "neutral"}
    prior = {"repo_rate": 6.50, "stance_label": "withdrawal_of_accommodation"}
    a = classify_statement(decision, prior)
    assert a.label == "pre_cut_signal"


def test_hawkish_pivot_on_dissent():
    decision = {"repo_rate": 6.50, "repo_rate_change_bps": 0, "stance_label": "neutral"}
    prior = {"repo_rate": 6.50, "stance_label": "neutral"}
    a = classify_statement(decision, prior, dissent_count=2)
    assert a.label == "hawkish_pivot"


def test_insurance_pause_when_projection_moves():
    decision = {
        "repo_rate": 6.50, "repo_rate_change_bps": 0, "stance_label": "neutral",
        "cpi_projection_curr_value": 4.6, "gdp_projection_curr_value": 6.9,
    }
    prior = {
        "repo_rate": 6.50, "stance_label": "neutral",
        "cpi_projection_curr_value": 4.2, "gdp_projection_curr_value": 6.9,
    }
    # CPI projection moved +0.40 — significant
    a = classify_statement(decision, prior)
    assert a.label == "insurance_pause"
    assert "CPI" in a.rationale


def test_operational_tweak_default():
    decision = {"repo_rate": 6.50, "repo_rate_change_bps": 0, "stance_label": "neutral"}
    prior = {"repo_rate": 6.50, "stance_label": "neutral"}
    a = classify_statement(decision, prior)
    assert a.label == "operational_tweak"


def test_find_most_similar_meeting():
    # 3 historical decisions, all operational_tweak. The matcher should
    # return one of them.
    history = [
        {"meeting_date": "2025-08-06", "repo_rate": 5.5, "repo_rate_change_bps": 0, "stance_label": "neutral"},
        {"meeting_date": "2025-10-01", "repo_rate": 5.5, "repo_rate_change_bps": 0, "stance_label": "neutral"},
        {"meeting_date": "2026-02-06", "repo_rate": 5.25, "repo_rate_change_bps": 0, "stance_label": "neutral"},
        {"meeting_date": "2026-04-08", "repo_rate": 5.25, "repo_rate_change_bps": 0, "stance_label": "neutral"},
    ]
    current_arch = classify_statement(history[-1], history[-2])
    similar = find_most_similar_meeting(
        current_arch, history, exclude_meeting_date="2026-04-08",
    )
    assert similar is not None
    assert similar["meeting_date"] != "2026-04-08"
