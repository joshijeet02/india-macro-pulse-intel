"""Tests for the 13-term theme-drift watchlist."""
from engine.focus_terms import FOCUS_TERMS, detect_new_focus_terms


def test_all_terms_classified_when_first_meeting():
    """No prior context — every term in curr counts as 'new'."""
    text = "Food inflation is benign. Monsoon outlook is favorable. Credit growth steady."
    out = detect_new_focus_terms(text, prev_text=None)
    assert "food inflation" in out["new"]
    assert "monsoon" in out["new"]
    assert "credit growth" in out["new"]
    assert out["dropped"] == []


def test_added_term_detected():
    prev = "Food inflation has eased."
    curr = "Food inflation has eased. Monsoon risks dominate the outlook."
    out = detect_new_focus_terms(curr, prev)
    assert "monsoon" in out["new"]
    assert "food inflation" in out["shared"]


def test_dropped_term_detected():
    prev = "Transmission lags remain a concern. Rural demand is firming."
    curr = "Rural demand is firming."
    out = detect_new_focus_terms(curr, prev)
    assert "transmission lags" in out["dropped"]
    assert "rural demand" in out["shared"]


def test_no_change_means_all_shared():
    text = "Food inflation outlook benign. Monsoon adequate."
    out = detect_new_focus_terms(text, text)
    assert out["new"] == [] and out["dropped"] == []
    assert "food inflation" in out["shared"]
    assert "monsoon" in out["shared"]


def test_case_insensitive():
    out = detect_new_focus_terms("Food Inflation rose", prev_text="")
    assert "food inflation" in out["new"]


def test_terms_not_in_text_arent_reported():
    out = detect_new_focus_terms("Repo rate decision was unanimous.", "")
    assert all(t in FOCUS_TERMS for t in out["new"])
    # Specifically, none of the watchlist terms appear in this text
    assert out["new"] == []
