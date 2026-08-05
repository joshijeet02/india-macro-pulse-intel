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


def test_a_single_division_move_shifts_the_index_by_its_effective_weight():
    """
    A 10% move in a 36.753%-weight division, of which the grocery basket
    tracks 70%, lifts the index by roughly 0.70 x its full effect.
    """
    from engine.live_index import TRACKED_SHARE
    share = TRACKED_SHARE["food_and_beverages"]
    live = compute_live_index({"food_and_beverages": 1.10})
    expected = ANCHOR_HEADLINE_INDEX * (
        1 + share * 0.10 * ANCHOR_DIVISION_INDICES["food_and_beverages"]
        * CPI_2024_DIVISIONS["food_and_beverages"] / 100 / ANCHOR_HEADLINE_INDEX
    )
    assert live.index == pytest.approx(expected, abs=0.05)
    assert live.observed_weight == pytest.approx(36.753 * share, abs=0.01)


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
    """Coverage is discounted by tracked share — we report what we price."""
    from engine.live_index import TRACKED_SHARE
    live = compute_live_index({
        "food_and_beverages": 1.01,
        "personal_care_and_misc": 1.05,
    })
    expected = (
        CPI_2024_DIVISIONS["food_and_beverages"] * TRACKED_SHARE["food_and_beverages"]
        + CPI_2024_DIVISIONS["personal_care_and_misc"] * TRACKED_SHARE["personal_care_and_misc"]
    )
    assert live.observed_weight == pytest.approx(expected, abs=0.01)


def test_a_relative_of_exactly_one_still_counts_as_observed():
    """Measured 'no change' is a finding; a missing key is not."""
    from engine.live_index import TRACKED_SHARE
    live = compute_live_index({"food_and_beverages": 1.0})
    assert live.observed_weight == pytest.approx(
        36.753 * TRACKED_SHARE["food_and_beverages"], abs=0.01
    )
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
    # 0.168, not 0.583: only the ~28.8% jewellery share of the division moves
    assert hot.pct_change_since_anchor == pytest.approx(0.168, abs=0.01)


# ── tracked share ───────────────────────────────────────────────────────────

def test_tracked_share_stops_bullion_overstating_its_division():
    """
    Gold is one sub-class inside personal_care_and_misc. Applying its move to
    the whole 5.04% overstated the effect ~3.5x. The share is derived from
    MOSPI's own Jan-2026 figures, not guessed.
    """
    from engine.live_index import TRACKED_SHARE
    share = TRACKED_SHARE["personal_care_and_misc"]
    assert 0.27 <= share <= 0.30, "derived jewellery share drifted"

    live = compute_live_index({"personal_care_and_misc": 1.10})
    naive = ANCHOR_HEADLINE_INDEX * (
        1 + 0.10 * ANCHOR_DIVISION_INDICES["personal_care_and_misc"]
        * CPI_2024_DIVISIONS["personal_care_and_misc"] / 100 / ANCHOR_HEADLINE_INDEX
    )
    assert live.index < naive, "tracked share not applied"
    assert live.pct_change_since_anchor == pytest.approx(0.168, abs=0.01)


def test_observed_weight_is_discounted_by_tracked_share():
    """Coverage must reflect what we actually price, not the whole division."""
    from engine.live_index import TRACKED_SHARE
    live = compute_live_index({"personal_care_and_misc": 1.05})
    expected = CPI_2024_DIVISIONS["personal_care_and_misc"] * TRACKED_SHARE["personal_care_and_misc"]
    assert live.observed_weight == pytest.approx(expected, abs=0.01)


def test_untracked_division_defaults_to_full_share():
    """A division with no entry is assumed fully represented by its signal."""
    from engine.live_index import DEFAULT_TRACKED_SHARE, TRACKED_SHARE
    assert "health" not in TRACKED_SHARE
    live = compute_live_index({"health": 1.10})
    reading = next(r for r in live.readings if r.key == "health")
    assert reading.tracked_share == DEFAULT_TRACKED_SHARE
    assert live.observed_weight == pytest.approx(CPI_2024_DIVISIONS["health"], abs=0.01)


def test_tracked_shares_are_all_valid_fractions():
    from engine.live_index import TRACKED_SHARE
    for key, share in TRACKED_SHARE.items():
        assert key in CPI_2024_DIVISIONS, f"{key} is not a division"
        assert 0 < share <= 1, f"{key} share {share} is not a fraction"


def test_no_movement_still_reproduces_the_anchor_with_shares_applied():
    """Tracked share must not perturb the zero-movement identity."""
    assert compute_live_index({}).index == pytest.approx(ANCHOR_HEADLINE_INDEX, abs=0.02)
    assert compute_live_index(
        {"food_and_beverages": 1.0, "personal_care_and_misc": 1.0}
    ).index == pytest.approx(ANCHOR_HEADLINE_INDEX, abs=0.02)
