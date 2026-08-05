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


def test_pre_2026_month_uses_2012_food_weight():
    result = decompose_cpi(
        headline=5.0, food_yoy=6.0, fuel_yoy=3.0, reference_month="2025-12"
    )
    # 6.0 * 0.4586 = 2.7516 -> 2.75
    assert result["food_contrib"] == pytest.approx(2.75, abs=0.01)
    assert result["base_year"] == "2012"


def test_2026_month_uses_2024_food_weight():
    result = decompose_cpi(
        headline=5.0, food_yoy=6.0, fuel_yoy=3.0, reference_month="2026-01"
    )
    # 6.0 * 0.36753 = 2.20518 -> 2.21
    assert result["food_contrib"] == pytest.approx(2.21, abs=0.01)
    assert result["base_year"] == "2024"


def test_food_contribution_is_lower_under_new_base():
    old = decompose_cpi(5.0, 6.0, 3.0, reference_month="2025-12")
    new = decompose_cpi(5.0, 6.0, 3.0, reference_month="2026-01")
    assert new["food_contrib"] < old["food_contrib"]


def test_omitting_reference_month_defaults_to_2012_base():
    # Backwards compatibility: existing callers pass three positional args.
    result = decompose_cpi(5.0, 6.0, 3.0)
    assert result["base_year"] == "2012"
    assert result["food_contrib"] == pytest.approx(2.75, abs=0.01)


def test_fuel_none_does_not_crash_and_reports_ex_food_core():
    result = decompose_cpi(4.38, 5.32, None, reference_month="2026-05")
    assert result["fuel_contrib"] is None
    assert result["core_definition"] == "ex-food"
    assert result["food_contrib"] == pytest.approx(1.96, abs=0.01)
    assert result["core_contrib"] == pytest.approx(2.42, abs=0.01)


def test_2024_base_core_uses_official_nonfood_weight():
    # core_yoy = core_contrib / 0.63247, NOT / (1 - 0.36753 - 0.0684)
    result = decompose_cpi(4.38, 5.32, None, reference_month="2026-05")
    assert result["core_yoy"] == pytest.approx(3.83, abs=0.01)


def test_2024_base_drops_fuel_even_when_fuel_supplied():
    # No 'Fuel & Light' division exists under COICOP 2018.
    result = decompose_cpi(5.0, 6.0, 3.0, reference_month="2026-01")
    assert result["fuel_contrib"] is None
    assert result["core_definition"] == "ex-food"


def test_2012_base_with_fuel_keeps_three_way_split():
    result = decompose_cpi(5.0, 6.0, 3.0, reference_month="2025-12")
    assert result["fuel_contrib"] == pytest.approx(0.21, abs=0.01)
    assert result["core_definition"] == "ex-food-and-fuel"
    assert result["base_year"] == "2012"


def test_2012_base_with_fuel_none_falls_back_to_ex_food():
    result = decompose_cpi(5.0, 6.0, None, reference_month="2025-12")
    assert result["fuel_contrib"] is None
    assert result["core_definition"] == "ex-food"
    assert result["base_year"] == "2012"
