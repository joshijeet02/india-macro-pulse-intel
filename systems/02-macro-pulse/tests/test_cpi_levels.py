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
