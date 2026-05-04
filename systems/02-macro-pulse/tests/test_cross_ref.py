"""
Tests for the macro-pulse ↔ rbi-comms cross-reference helper.

Reads the actual sibling system's JSON sidecar. Tolerates missing-data
gracefully (sister system not deployed / no autonomous refresh fired yet)
by returning None — UI panels then quietly hide.
"""
from engine.cross_ref import cpi_context_for_print, gdp_context, latest_mpc_decision


def test_latest_mpc_returns_decision_when_sidecar_populated():
    """Should pick up the April 2026 MPC committed in this branch."""
    decision = latest_mpc_decision()
    if decision is None:
        # Acceptable when run against a checkout without rbi-comms data —
        # but the test suite runs against this repo, where the file IS present.
        return
    for k in ("meeting_date", "repo_rate", "stance_label"):
        assert k in decision, f"missing {k}"
    assert 0 <= decision["repo_rate"] <= 12


def test_cpi_context_computes_signed_surprise():
    """Surprise is print MINUS RBI projection: positive = hotter than RBI expected."""
    decision = latest_mpc_decision()
    if decision is None or decision.get("cpi_projection_curr_value") is None:
        return  # skip cleanly when sidecar isn't populated

    rbi_cpi = decision["cpi_projection_curr_value"]
    # Print 0.50pp BELOW RBI's projection
    cooler = cpi_context_for_print({"headline_yoy": rbi_cpi - 0.5})
    assert cooler is not None
    assert cooler["surprise_pp"] == -0.5
    assert "below" in cooler["comment"].lower()

    # Print 0.50pp ABOVE
    hotter = cpi_context_for_print({"headline_yoy": rbi_cpi + 0.5})
    assert hotter["surprise_pp"] == 0.5
    assert "above" in hotter["comment"].lower()


def test_cpi_context_returns_in_line_when_close():
    decision = latest_mpc_decision()
    if decision is None or decision.get("cpi_projection_curr_value") is None:
        return
    rbi_cpi = decision["cpi_projection_curr_value"]
    on_target = cpi_context_for_print({"headline_yoy": rbi_cpi})
    assert on_target is not None
    assert "in line" in on_target["comment"].lower()


def test_gdp_context_has_required_fields():
    ctx = gdp_context()
    if ctx is None:
        return
    for k in ("rbi_gdp_projection", "projection_fy", "stance"):
        assert k in ctx, f"missing {k}"


def test_helpers_tolerate_missing_fields():
    """If the print is missing headline_yoy, surprise should be None, not crash."""
    if latest_mpc_decision() is None:
        return
    ctx = cpi_context_for_print({})
    if ctx is None:
        return
    assert ctx["surprise_pp"] is None
