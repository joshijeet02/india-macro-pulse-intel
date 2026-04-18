import pytest
from engine.cpi_decomposer import decompose_cpi, CPIWeights


def test_contributions_sum_to_headline():
    """food_contrib + fuel_contrib + core_contrib must equal headline_yoy."""
    result = decompose_cpi(headline=3.61, food_yoy=3.75, fuel_yoy=-1.59)
    total = result["food_contrib"] + result["fuel_contrib"] + result["core_contrib"]
    assert total == pytest.approx(result["headline_yoy"], abs=0.01)


def test_core_yoy_derived_correctly():
    """Core YoY = core_contrib / core_weight."""
    result = decompose_cpi(headline=3.61, food_yoy=3.75, fuel_yoy=-1.59)
    expected_core_yoy = result["core_contrib"] / CPIWeights.CORE
    assert result["core_yoy"] == pytest.approx(expected_core_yoy, abs=0.01)


def test_food_contribution_arithmetic():
    """Food contribution = food_yoy * food_weight."""
    result = decompose_cpi(headline=5.49, food_yoy=9.24, fuel_yoy=5.26)
    assert result["food_contrib"] == pytest.approx(9.24 * CPIWeights.FOOD, abs=0.01)


def test_high_food_inflation_scenario():
    """Oct 2024: CPI=6.21, food=10.87, fuel=-1.56 → core is positive, food dominates."""
    result = decompose_cpi(headline=6.21, food_yoy=10.87, fuel_yoy=-1.56)
    # food_contrib = 10.87 * 0.4586 = 4.98, fuel_contrib = -1.56 * 0.0684 = -0.11
    # core_contrib = 6.21 - 4.98 - (-0.11) = 1.34, core_yoy = 1.34 / 0.4730 = 2.83
    assert result["core_yoy"] > 0
    assert result["food_contrib"] > abs(result["fuel_contrib"])


def test_negative_fuel_contribution():
    """Fuel deflation reduces headline — fuel_contrib should be negative."""
    result = decompose_cpi(headline=4.26, food_yoy=6.00, fuel_yoy=-1.50)
    assert result["fuel_contrib"] < 0


def test_rbi_signal_property():
    """Returns dominant_driver: which of food/fuel/core contributed most (by absolute value)."""
    result = decompose_cpi(headline=5.49, food_yoy=9.24, fuel_yoy=5.26)
    assert result["dominant_driver"] == "food"
