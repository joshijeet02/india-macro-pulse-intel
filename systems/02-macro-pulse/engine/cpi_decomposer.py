from dataclasses import dataclass


@dataclass(frozen=True)
class _CPIWeights:
    """CPI 2012 base year weights (share of total index)."""
    FOOD: float = 0.4586
    FUEL: float = 0.0684
    CORE: float = 0.4730   # = 1 - FOOD - FUEL


CPIWeights = _CPIWeights()


def decompose_cpi(headline: float, food_yoy: float, fuel_yoy: float) -> dict:
    """
    Decompose headline CPI into food, fuel, and core contributions.

    Core is residual: core_contrib = headline - food_contrib - fuel_contrib.
    This matches how RBI MPC staff decompose inflation in policy documents.
    """
    food_contrib = round(food_yoy * CPIWeights.FOOD, 2)
    fuel_contrib = round(fuel_yoy * CPIWeights.FUEL, 2)
    core_contrib = round(headline - food_contrib - fuel_contrib, 2)
    core_yoy = round(core_contrib / CPIWeights.CORE, 2)

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
    }
