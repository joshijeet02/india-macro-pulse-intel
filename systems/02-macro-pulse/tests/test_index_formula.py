import math

import pytest

from engine.index_formula import jevons_elementary


def test_single_quote_returns_its_own_ratio():
    # With one quote, Jevons degenerates to that quote's ratio.
    assert jevons_elementary([110.0], [100.0]) == pytest.approx(1.10)


def test_two_quotes_geometric_mean_of_relatives():
    # relatives 1.10 and 1.20 -> sqrt(1.32) = 1.148912529...
    result = jevons_elementary([110.0, 120.0], [100.0, 100.0])
    assert result == pytest.approx(math.sqrt(1.32), abs=1e-9)


def test_three_quotes_hand_computed():
    # 110/100=1.10, 118/105=1.123809..., 99/95=1.042105...
    # GM = exp((ln1.10 + ln1.1238095 + ln1.0421053)/3)
    result = jevons_elementary([110.0, 118.0, 99.0], [100.0, 105.0, 95.0])
    assert result == pytest.approx(1.088092, abs=1e-6)


def test_geometric_mean_is_at_most_arithmetic_mean():
    current = [110.0, 150.0, 90.0]
    base = [100.0, 100.0, 100.0]
    gm = jevons_elementary(current, base)
    am = sum(c / b for c, b in zip(current, base)) / len(current)
    assert gm <= am


def test_non_positive_quotes_are_excluded():
    # zero and negative prices carry no information and break log()
    assert jevons_elementary([110.0, 0.0], [100.0, 100.0]) == pytest.approx(1.10)
    assert jevons_elementary([110.0, -5.0], [100.0, 100.0]) == pytest.approx(1.10)
    assert jevons_elementary([110.0, 120.0], [100.0, 0.0]) == pytest.approx(1.10)


def test_length_mismatch_raises():
    with pytest.raises(ValueError, match="same length"):
        jevons_elementary([110.0, 120.0], [100.0])


def test_no_usable_pairs_raises():
    with pytest.raises(ValueError, match="no usable"):
        jevons_elementary([0.0], [100.0])


from engine.index_formula import young_aggregate


def test_young_uniform_rise():
    relatives = {"rice": 1.10, "atta": 1.10}
    weights = {"rice": 14.0, "atta": 12.3}
    assert young_aggregate(relatives, weights) == pytest.approx(110.0)


def test_young_hand_computed_weighted_mean():
    # (14.0*1.10 + 12.3*1.05 + 5.5*1.40) / (14.0+12.3+5.5) * 100
    # = (15.40 + 12.915 + 7.70) / 31.8 * 100 = 113.2547169...
    relatives = {"rice": 1.10, "atta": 1.05, "onion": 1.40}
    weights = {"rice": 14.0, "atta": 12.3, "onion": 5.5}
    assert young_aggregate(relatives, weights) == pytest.approx(113.254717, abs=1e-6)


def test_young_ignores_relatives_without_weights():
    relatives = {"rice": 1.10, "unknown_item": 99.0}
    weights = {"rice": 14.0}
    assert young_aggregate(relatives, weights) == pytest.approx(110.0)


def test_young_ignores_weights_without_relatives():
    relatives = {"rice": 1.10}
    weights = {"rice": 14.0, "atta": 12.3}
    assert young_aggregate(relatives, weights) == pytest.approx(110.0)


def test_young_zero_total_weight_raises():
    with pytest.raises(ValueError, match="zero total weight"):
        young_aggregate({"rice": 1.10}, {"rice": 0.0})


def test_young_empty_raises():
    with pytest.raises(ValueError, match="zero total weight"):
        young_aggregate({}, {})


from engine.index_formula import chain_link


def test_chain_link_uniform_rise():
    prev_prices = {"rice": 100.0, "atta": 100.0}
    curr_prices = {"rice": 110.0, "atta": 110.0}
    weights = {"rice": 14.0, "atta": 12.3}
    assert chain_link(100.0, curr_prices, prev_prices, weights) == pytest.approx(110.0)


def test_chain_link_compounds_onto_previous_level():
    prev_prices = {"rice": 110.0}
    curr_prices = {"rice": 121.0}
    weights = {"rice": 14.0}
    # previous level 110, this period +10% -> 121
    assert chain_link(110.0, curr_prices, prev_prices, weights) == pytest.approx(121.0)


def test_chain_link_ignores_item_missing_this_period():
    """
    THE FIX for the composition defect: rice absent this period must not
    move the level, because the matched sample excludes it entirely.
    """
    prev_prices = {"rice": 100.0, "atta": 100.0}
    curr_prices = {"atta": 100.0}          # atta flat, rice absent
    weights = {"rice": 14.0, "atta": 12.3}
    assert chain_link(100.0, curr_prices, prev_prices, weights) == pytest.approx(100.0)


def test_chain_link_ignores_item_new_this_period():
    prev_prices = {"atta": 100.0}
    curr_prices = {"atta": 100.0, "rice": 500.0}   # rice brand new
    weights = {"rice": 14.0, "atta": 12.3}
    assert chain_link(100.0, curr_prices, prev_prices, weights) == pytest.approx(100.0)


def test_chain_link_no_overlap_returns_previous_level_unchanged():
    # Nothing matched: we know nothing about price change, so hold the level.
    assert chain_link(107.5, {"rice": 110.0}, {"atta": 100.0}, {"rice": 1.0}) == 107.5


def test_chain_link_weighted_partial_movement():
    # rice +10% (wt 14.0), atta flat (wt 12.3), both matched
    # movement = (14.0*1.10 + 12.3*1.00)/26.3 = 1.053231939...
    prev_prices = {"rice": 100.0, "atta": 100.0}
    curr_prices = {"rice": 110.0, "atta": 100.0}
    weights = {"rice": 14.0, "atta": 12.3}
    assert chain_link(100.0, curr_prices, prev_prices, weights) == pytest.approx(
        105.3231939, abs=1e-6
    )
