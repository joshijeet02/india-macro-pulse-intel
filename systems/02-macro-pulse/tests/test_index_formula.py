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
