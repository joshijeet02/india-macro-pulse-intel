"""
The CPI basket, division by division — what we can observe, and what we must model.

First principles behind this file:

MOSPI builds headline CPI as a weighted aggregate of 12 COICOP divisions. To
estimate the headline before it publishes, the honest approach is to rebuild
that same aggregate: nowcast each division, then combine with the official
weights. That is the mechanism, not an approximation of it.

The organising insight is that **weight and importance are not the same thing.**
Decomposing the January 2026 print by division:

    personal_care_and_misc     5.04% weight -> 35.0% of headline inflation
    food_and_beverages        36.75% weight -> 28.4%
    housing/water/elec/fuels  17.66% weight ->  9.9%
    transport                  8.80% weight ->  0.3%

A 5%-weight division out-contributed food, which carries seven times the
weight, because it contains gold and silver jewellery running near 60% YoY.
Transport, at nearly twice that weight, contributed almost nothing because
fuel prices were flat.

So effort follows **variance**, not weight. A grocery-only basket — however
well built — misses the single largest contributor to the current print, and
would have no way of knowing it.

Each division is classified by how we get its price signal:

    OBSERVED  we can read current prices directly, at daily or weekly cadence
    PARTIAL   a volatile sub-component is observable; the rest must be modelled
    MODELLED  no usable high-frequency price; sticky, administered, or seasonal,
              and therefore well served by persistence and seasonal norms

MODELLED is not a euphemism for guessed. Rent, telecom tariffs, education fees
and health charges move in small, highly persistent, often administered steps.
Persistence genuinely is the right model for them, and its error is measurable
like anything else. What matters is that we can state which is which.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional

from engine.basket_weights import CPI_2024_DIVISIONS

OBSERVED = "observed"
PARTIAL = "partial"
MODELLED = "modelled"


@dataclass(frozen=True)
class DivisionSpec:
    code: str
    key: str
    name: str
    weight: float           # official CPI 2024 Combined weight, % of index
    observability: str
    sources: tuple[str, ...]
    note: str


# Ordered by weight. `key` matches engine.basket_weights.CPI_2024_DIVISIONS.
DIVISIONS: tuple[DivisionSpec, ...] = (
    DivisionSpec(
        "01", "food_and_beverages", "Food and beverages", 36.753, OBSERVED,
        ("amazon", "bigbasket", "blinkit", "zepto", "jiomart"),
        "Highest weight and genuinely volatile. E-commerce grocery gives daily "
        "prices for most of the basket. Perishables (vegetables, fruit) carry "
        "the volatility; staples are stickier.",
    ),
    DivisionSpec(
        "04", "housing_water_electricity_gas_fuel",
        "Housing, water, electricity, gas and other fuels", 17.665, PARTIAL,
        ("lpg_price", "png_cng_price"),
        "Splits sharply. LPG/PNG/CNG are published and can jump. Rent (04.1) is "
        "the largest piece and is close to deterministic month to month — it is "
        "modelled, and modelling it well is easy.",
    ),
    DivisionSpec(
        "07", "transport", "Transport", 8.796, PARTIAL,
        ("petrol_diesel_daily", "rail_fare", "airfare"),
        "Petrol and diesel are repriced daily and published by the OMCs — the "
        "cleanest high-frequency series in the whole index. Contributed almost "
        "nothing in Jan-2026 because pump prices were flat, which is exactly why "
        "it must be observed rather than assumed.",
    ),
    DivisionSpec(
        "03", "clothing_and_footwear", "Clothing and footwear", 6.383, PARTIAL,
        ("myntra", "amazon_fashion"),
        "E-commerce observable but heavily discount-driven, so scraped prices are "
        "noisier than the underlying CPI series. Low MoM volatility.",
    ),
    DivisionSpec(
        "06", "health", "Health", 6.100, PARTIAL,
        ("pharmacy_ecommerce",),
        "Medicine prices are capped by NPPA and change in administered steps. "
        "Hospital and diagnostic charges are sticky.",
    ),
    DivisionSpec(
        "13", "personal_care_and_misc",
        "Personal care, social protection and miscellaneous", 5.038, OBSERVED,
        ("gold_spot", "silver_spot", "usd_inr", "ecommerce_personal_care"),
        "THE HIGH-LEVERAGE ONE. Contains gold and silver jewellery (sub-class "
        "13.2), which ran 59% YoY in Jan-2026 and made this 5%-weight division "
        "the largest single contributor to headline. Bullion is priced live and "
        "free. Missing it is a far bigger error than imperfect grocery matching.",
    ),
    DivisionSpec(
        "05", "furnishings_household_equipment",
        "Furnishings, household equipment and routine maintenance", 4.469, PARTIAL,
        ("amazon", "flipkart"),
        "Durables, observable via e-commerce, low volatility.",
    ),
    DivisionSpec(
        "08", "information_and_communication", "Information and communication",
        3.609, MODELLED,
        ("telecom_tariff", "ott_subscription"),
        "Telecom tariffs move in rare, large administered steps and are flat in "
        "between. Persistence is close to exactly right, with step risk on "
        "announced tariff hikes.",
    ),
    DivisionSpec(
        "11", "restaurants_and_accommodation",
        "Restaurants and accommodation services", 3.348, PARTIAL,
        ("swiggy", "zomato", "hotel_rates"),
        "Menu prices are scrapeable; hotel tariffs are strongly seasonal.",
    ),
    DivisionSpec(
        "10", "education_services", "Education services", 3.333, MODELLED,
        (),
        "Fees reset annually, concentrated around the April academic year. Almost "
        "deterministic within the year — a seasonal dummy captures nearly all of it.",
    ),
    DivisionSpec(
        "02", "paan_tobacco_and_intoxicants", "Paan, tobacco and intoxicants",
        2.989, MODELLED,
        (),
        "Moves on excise and state tax changes — step-like and announced in "
        "advance, so predictable in the months between.",
    ),
    DivisionSpec(
        "09", "recreation_sport_and_culture", "Recreation, sport and culture",
        1.516, MODELLED,
        (),
        "Smallest division. Not worth an observation pipeline.",
    ),
)

DIVISION_BY_KEY: dict[str, DivisionSpec] = {d.key: d for d in DIVISIONS}


def weight_by_observability() -> dict[str, float]:
    """Total basket weight in each observability class."""
    totals: dict[str, float] = {OBSERVED: 0.0, PARTIAL: 0.0, MODELLED: 0.0}
    for d in DIVISIONS:
        totals[d.observability] += d.weight
    return {k: round(v, 3) for k, v in totals.items()}


def directly_observable_weight() -> float:
    """
    Weight we can price directly today, counting PARTIAL divisions at half.

    The half-weight convention is a deliberate understatement. In a PARTIAL
    division we observe the volatile sub-component and model the sticky
    remainder, so our effective information share is usually well above half —
    but claiming that precisely would require sub-class weights we do not have.
    Understating a coverage claim is the safe direction to be wrong in.
    """
    total = sum(
        d.weight if d.observability == OBSERVED
        else d.weight * 0.5 if d.observability == PARTIAL
        else 0.0
        for d in DIVISIONS
    )
    return round(total, 2)


def contributions(inflation_by_division: Mapping[str, float]) -> list[tuple[str, float, float, float]]:
    """
    Decompose a headline print into per-division contributions.

    Returns (key, weight, inflation, contribution_pp), largest contribution
    first. Contribution is weight x inflation / 100 — the same arithmetic
    MOSPI's aggregate implies.
    """
    rows = [
        (key, CPI_2024_DIVISIONS[key], value, CPI_2024_DIVISIONS[key] * value / 100.0)
        for key, value in inflation_by_division.items()
        if key in CPI_2024_DIVISIONS
    ]
    rows.sort(key=lambda r: -abs(r[3]))
    return [(k, w, i, round(c, 4)) for k, w, i, c in rows]


def headline_from_divisions(
    inflation_by_division: Mapping[str, float],
) -> Optional[float]:
    """
    Rebuild headline inflation from division-level inflation and official
    weights — the mechanism MOSPI itself uses.

    Divisions may be missing; the result is then renormalised over what is
    present, and the caller should check `covered_weight` before trusting it.
    """
    present = {k: v for k, v in inflation_by_division.items() if k in CPI_2024_DIVISIONS}
    if not present:
        return None
    total_weight = sum(CPI_2024_DIVISIONS[k] for k in present)
    if total_weight <= 0:
        return None
    weighted = sum(CPI_2024_DIVISIONS[k] * v for k, v in present.items())
    return round(weighted / total_weight, 2)


def covered_weight(inflation_by_division: Mapping[str, float]) -> float:
    """Share of the basket, in %, that a set of division readings spans."""
    return round(
        sum(CPI_2024_DIVISIONS[k] for k in inflation_by_division if k in CPI_2024_DIVISIONS),
        2,
    )
