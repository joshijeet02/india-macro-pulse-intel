from dataclasses import dataclass
from typing import Optional

from engine.basket_weights import (
    CPI_2012_FOOD_WEIGHT,
    CPI_2012_FUEL_WEIGHT,
    CPI_FOOD_WEIGHT,
    food_weight_for_month,
)


@dataclass(frozen=True)
class _CPIWeights:
    """CPI 2012 base year weights (share of total index)."""
    FOOD: float = CPI_2012_FOOD_WEIGHT
    FUEL: float = CPI_2012_FUEL_WEIGHT
    CORE: float = 1.0 - CPI_2012_FOOD_WEIGHT - CPI_2012_FUEL_WEIGHT


CPIWeights = _CPIWeights()


def decompose_cpi(
    headline: float,
    food_yoy: float,
    fuel_yoy: float,
    reference_month: Optional[str] = None,
) -> dict:
    """
    Decompose headline CPI into food, fuel, and core contributions.

    Core is residual: core_contrib = headline - food_contrib - fuel_contrib.
    This matches how RBI MPC staff decompose inflation in policy documents.

    `reference_month` ("YYYY-MM") selects the weight base. MOSPI moved to
    2024=100 from January 2026, cutting the food share from 45.86% to
    36.753%; decomposing a 2026 release on 2012 weights overstates the food
    contribution by roughly a quarter and dumps the error into core.

    Omitting `reference_month` assumes the 2012 base, preserving the
    behaviour of existing callers.

    Note: under 2024=100 MOSPI replaced "Fuel & Light" with "Housing, water,
    electricity, gas and other fuels", so `fuel_yoy` is frequently absent
    for post-2026 releases. The 2012 fuel weight is retained for the fuel
    term because no like-for-like 2024 equivalent exists; when fuel_yoy is
    unavailable the caller should not rely on the fuel/core split.
    """
    if reference_month is None:
        food_weight = CPI_2012_FOOD_WEIGHT
        base_year = "2012"
    else:
        food_weight = food_weight_for_month(reference_month)
        base_year = "2024" if food_weight == CPI_FOOD_WEIGHT else "2012"

    fuel_weight = CPI_2012_FUEL_WEIGHT
    core_weight = 1.0 - food_weight - fuel_weight

    food_contrib = round(food_yoy * food_weight, 2)
    fuel_contrib = round(fuel_yoy * fuel_weight, 2)
    core_contrib = round(headline - food_contrib - fuel_contrib, 2)
    core_yoy = round(core_contrib / core_weight, 2)

    contribs = {
        "food": abs(food_contrib),
        "fuel": abs(fuel_contrib),
        "core": abs(core_contrib),
    }
    dominant_driver = max(contribs, key=contribs.get)

    return {
        "headline_yoy": headline,
        "food_yoy": food_yoy,
        "fuel_yoy": fuel_yoy,
        "core_yoy": core_yoy,
        "food_contrib": food_contrib,
        "fuel_contrib": fuel_contrib,
        "core_contrib": core_contrib,
        "dominant_driver": dominant_driver,
        "base_year": base_year,
    }
