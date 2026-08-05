from dataclasses import dataclass
from typing import Optional

from engine.basket_weights import (
    CPI_2012_FOOD_WEIGHT,
    CPI_2012_FUEL_WEIGHT,
    base_year_for_month,
    food_weight_for_month,
)


@dataclass(frozen=True)
class _CPIWeights:
    """
    CPI 2012 base-year weights.

    Retained for backwards compatibility with callers predating
    base-awareness. These are ALWAYS 2012 figures and are never
    base-selected — new code should use engine.basket_weights directly.
    """
    FOOD: float = CPI_2012_FOOD_WEIGHT
    FUEL: float = CPI_2012_FUEL_WEIGHT
    CORE: float = 1.0 - CPI_2012_FOOD_WEIGHT - CPI_2012_FUEL_WEIGHT


CPIWeights = _CPIWeights()


def decompose_cpi(
    headline: float,
    food_yoy: float,
    fuel_yoy: Optional[float],
    reference_month: Optional[str] = None,
) -> dict:
    """
    Decompose headline CPI into food, fuel, and core contributions.

    Core is a residual: core_contrib = headline - food_contrib - fuel_contrib.
    This matches how RBI MPC staff decompose inflation in policy documents.

    `reference_month` ("YYYY-MM") selects the weight base. MOSPI moved to
    2024=100 from January 2026, cutting the food share from 45.86% to
    36.753%; decomposing a 2026 release on 2012 weights overstates the food
    contribution by roughly a quarter and dumps the error into core.
    Omitting `reference_month` assumes the 2012 base, preserving the
    behaviour of callers that predate base-awareness.

    `fuel_yoy` may be None. Under COICOP 2018 there is no "Fuel & Light"
    division — it was folded into "Housing, water, electricity, gas and
    other fuels" (17.665%), which also contains rent and is not comparable.
    So under the 2024 base, and whenever fuel_yoy is absent, we decompose
    food vs non-food only: `fuel_contrib` is None and core is the ex-food
    residual divided by the official non-food share (0.63247). Subtracting
    the retired 6.84% fuel weight instead would produce a core figure that
    reconciles to no published MOSPI aggregate.

    The `core_definition` key states which of the two applies, so a consumer
    never has to infer it.
    """
    if reference_month is None:
        food_weight = CPI_2012_FOOD_WEIGHT
        base_year = "2012"
    else:
        food_weight = food_weight_for_month(reference_month)
        base_year = base_year_for_month(reference_month)

    if base_year == "2024" or fuel_yoy is None:
        fuel_contrib: Optional[float] = None
        core_weight = 1.0 - food_weight
        core_definition = "ex-food"
    else:
        fuel_contrib = round(fuel_yoy * CPI_2012_FUEL_WEIGHT, 2)
        core_weight = 1.0 - food_weight - CPI_2012_FUEL_WEIGHT
        core_definition = "ex-food-and-fuel"

    food_contrib = round(food_yoy * food_weight, 2)
    core_contrib = round(headline - food_contrib - (fuel_contrib or 0.0), 2)
    core_yoy = round(core_contrib / core_weight, 2)

    contribs = {"food": abs(food_contrib), "core": abs(core_contrib)}
    if fuel_contrib is not None:
        contribs["fuel"] = abs(fuel_contrib)
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
        "core_definition": core_definition,
    }
