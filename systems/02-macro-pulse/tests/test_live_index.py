"""
The live index is a MEASUREMENT, not a forecast. These tests hold it to that:
nothing may be extrapolated, and the official anchor must be reproduced exactly
when no price has moved.
"""
import pytest

from engine.basket_weights import CPI_2024_DIVISIONS
from engine.live_index import (
    ANCHOR_DIVISION_INDICES, ANCHOR_HEADLINE_INDEX, BASE_YEAR_LEVELS,
    compute_live_index,
)


def test_no_movement_reproduces_the_official_headline():
    """
    The single most important property. If our aggregation of MOSPI's own
    division indices does not return MOSPI's own headline, every live reading
    is wrong by construction.
    """
    live = compute_live_index({})
    assert live.index == pytest.approx(ANCHOR_HEADLINE_INDEX, abs=0.02)
    assert live.observed_weight == 0.0


def test_anchor_divisions_match_the_official_weight_keys():
    assert set(ANCHOR_DIVISION_INDICES) == set(CPI_2024_DIVISIONS)


def test_a_single_division_move_shifts_the_index_by_its_weight():
    """A 10% move in a 36.753%-weight division lifts the index ~3.6%."""
    live = compute_live_index({"food_and_beverages": 1.10})
    expected = ANCHOR_HEADLINE_INDEX * (
        1 + 0.10 * ANCHOR_DIVISION_INDICES["food_and_beverages"]
        * CPI_2024_DIVISIONS["food_and_beverages"] / 100 / ANCHOR_HEADLINE_INDEX
    )
    assert live.index == pytest.approx(expected, abs=0.05)
    assert live.observed_weight == pytest.approx(36.753, abs=0.01)


def test_unobserved_divisions_are_carried_not_dropped():
    """
    Dropping them would renormalise over observed weight and let coverage
    changes masquerade as price changes — the same defect fixed in the
    grocery index.
    """
    live = compute_live_index({"food_and_beverages": 1.02})
    carried = [r for r in live.readings if not r.observed]
    assert len(carried) == len(ANCHOR_DIVISION_INDICES) - 1
    for r in carried:
        assert r.live_index == r.anchor_index


def test_observed_weight_counts_only_measured_divisions():
    live = compute_live_index({
        "food_and_beverages": 1.01,
        "personal_care_and_misc": 1.05,
    })
    expected = (CPI_2024_DIVISIONS["food_and_beverages"]
                + CPI_2024_DIVISIONS["personal_care_and_misc"])
    assert live.observed_weight == pytest.approx(expected, abs=0.01)


def test_a_relative_of_exactly_one_still_counts_as_observed():
    """Measured 'no change' is a finding; a missing key is not."""
    live = compute_live_index({"food_and_beverages": 1.0})
    assert live.observed_weight == pytest.approx(36.753, abs=0.01)
    assert live.index == pytest.approx(ANCHOR_HEADLINE_INDEX, abs=0.02)


def test_nonpositive_relatives_are_treated_as_unobserved():
    for bad in (0.0, -1.0):
        live = compute_live_index({"food_and_beverages": bad})
        assert live.observed_weight == 0.0
        assert live.index == pytest.approx(ANCHOR_HEADLINE_INDEX, abs=0.02)


def test_implied_yoy_uses_the_published_base():
    live = compute_live_index({})
    base = BASE_YEAR_LEVELS["2025-07"]
    assert live.implied_yoy(base) == pytest.approx(
        (ANCHOR_HEADLINE_INDEX / base - 1) * 100, abs=0.02
    )


def test_implied_yoy_rejects_a_nonsense_base():
    assert compute_live_index({}).implied_yoy(0) is None


def test_bullion_move_lifts_the_index_measurably():
    """
    personal_care_and_misc is only 5% of weight but drove 35% of January's
    headline. A 10% bullion move must show up.
    """
    flat = compute_live_index({})
    hot = compute_live_index({"personal_care_and_misc": 1.10})
    assert hot.index > flat.index
    assert hot.pct_change_since_anchor == pytest.approx(0.583, abs=0.05)
