"""Index level reconstruction — the identity the MoM work rests on."""
import pytest

from engine.cpi_levels import (
    ANCHOR_LEVELS, PUBLISHED_LEVELS, base_month_mom, build_levels, mom_series,
    verify_against_published, yoy_from_levels,
)

YOY_2026 = {"2026-02": 3.21, "2026-03": 3.40, "2026-04": 3.48,
            "2026-05": 3.93, "2026-06": 4.38}


def test_reconstruction_matches_levels_mospi_actually_printed():
    """
    I_t = I_t-12 x (1 + YoY_t/100) is an identity, not an approximation. If this
    ever drifts, every MoM downstream is wrong.
    """
    checks = verify_against_published(build_levels(YOY_2026))
    assert checks, "no published levels available to verify against"
    for month, got, published, ok in checks:
        assert ok, f"{month}: reconstructed {got} vs published {published}"


def test_june_reconstructs_exactly():
    assert build_levels(YOY_2026)["2026-06"] == pytest.approx(107.00, abs=0.01)


def test_anchor_is_left_unmodified():
    levels = build_levels(YOY_2026)
    for month, value in ANCHOR_LEVELS.items():
        assert levels[month] == value


def test_month_without_a_known_base_is_skipped():
    """A level is never invented from nothing."""
    levels = build_levels({"2030-05": 4.0})
    assert "2030-05" not in levels


def test_mom_series_is_correct_and_gap_aware():
    levels = {"2026-01": 100.0, "2026-02": 101.0, "2026-04": 103.0}
    moms = mom_series(levels)
    assert moms["2026-02"] == pytest.approx(1.0)
    assert "2026-04" not in moms          # Mar missing -> MoM meaningless


def test_yoy_from_levels_round_trips_the_input():
    levels = build_levels(YOY_2026)
    for month, expected in YOY_2026.items():
        assert yoy_from_levels(levels, month) == pytest.approx(expected, abs=0.02)


def test_yoy_needs_both_ends():
    assert yoy_from_levels({"2026-06": 107.0}, "2026-06") is None


def test_base_month_mom_surfaces_the_july_base_effect():
    """
    July 2025 was the hottest MoM in the series. That is why a YoY-momentum
    model over-predicts July 2026 — it cannot see the bar it has to clear.
    """
    levels = build_levels(YOY_2026)
    assert base_month_mom(levels, "2026-07") == pytest.approx(0.82, abs=0.02)


def test_published_levels_are_never_an_input_to_reconstruction():
    """Verification data must stay out of the thing it verifies."""
    levels = build_levels(YOY_2026)
    for month in PUBLISHED_LEVELS:
        if month in YOY_2026:
            base = ANCHOR_LEVELS[f"{int(month[:4]) - 1}-{month[5:]}"]
            assert levels[month] == pytest.approx(
                round(base * (1 + YOY_2026[month] / 100), 2), abs=0.001
            )


# ── the central month-on-month assumption ───────────────────────────────────

def test_central_mom_blends_seasonal_and_momentum():
    from engine.cpi_levels import central_mom
    moms = {"2025-07": 0.82, "2026-05": 0.75, "2026-06": 1.04}
    value, basis = central_mom(moms, "2026-07")
    assert value == pytest.approx((0.82 + 1.04) / 2)
    assert "2025-07" in basis and "2026-06" in basis


def test_central_mom_falls_back_to_momentum_without_a_seasonal_match():
    from engine.cpi_levels import central_mom
    value, basis = central_mom({"2026-06": 1.04}, "2026-07")
    assert value == pytest.approx(1.04)
    assert "last month" in basis


def test_central_mom_is_never_zero_when_prices_are_moving():
    """
    Flat was the WORST of five estimators over 14 months (MAE 0.372 vs 0.228),
    and shipping it as the headline understated the next print by about a
    percentage point. It must not creep back as a default.
    """
    from engine.cpi_levels import central_mom
    value, _ = central_mom({"2025-07": 0.82, "2026-06": 1.04}, "2026-07")
    assert value > 0.5


def test_central_mom_handles_an_empty_series():
    from engine.cpi_levels import central_mom
    assert central_mom({}, "2026-07") is None


def test_the_estimate_lands_near_street_consensus():
    """
    Reached from our own MoM data with the estimator chosen by backtest — not
    anchored to the poll. If a change moves us far from the street, that should
    be a deliberate call, not a silent drift.
    """
    from engine.cpi_levels import ANCHOR_LEVELS, CONSENSUS, central_mom
    moms = {"2025-07": 0.82, "2026-05": 0.75, "2026-06": 1.04}
    value, _ = central_mom(moms, "2026-07")
    implied = (107.00 * (1 + value / 100) / ANCHOR_LEVELS["2025-07"] - 1) * 100
    street = CONSENSUS["2026-07"]
    assert street["low"] - 0.3 <= implied <= street["high"] + 0.3, implied


def test_consensus_entries_carry_a_source_and_a_date():
    """An undated consensus quoted as current is worse than none."""
    from engine.cpi_levels import CONSENSUS
    for month, entry in CONSENSUS.items():
        assert entry["source"] and entry["as_of"]
        assert entry["low"] <= entry["high"]
