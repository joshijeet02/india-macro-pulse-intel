"""
A live CPI measurement. Not a forecast.

CPI is a calculation: collect prices, apply fixed formulas with fixed weights,
get an index. MOSPI does that monthly. If we collect prices for the same
components and run the same formulas with the same official weights, we get an
independent *measurement* of the same quantity — no model, no fitting, no
prediction.

How it works:

1. Start from the last official division indices MOSPI published (the anchor).
2. Fetch current prices, and compare them to the prices that prevailed at the
   anchor date. That ratio is the division's measured price relative.
3. Move each observed division's index by its relative.
4. Divisions we cannot price are carried forward unchanged, and we report how
   much weight that covers so nobody mistakes silence for stability.
5. Aggregate with the official CPI 2024 weights — the Young/modified Laspeyres
   form MOSPI itself uses, already implemented in engine.index_formula.

The result is today's index level, and the YoY it implies against the base
month MOSPI published a year ago.

Why this is honest: every number is either an official figure or a measured
price ratio. Nothing is extrapolated. When a division is carried flat, that is
stated rather than hidden, because carrying flat IS an assumption — just an
explicit and conservative one.

The one thing this cannot do is measure a change that predates our first price
snapshot. The first fetch establishes the reference; from the second onward,
every reading reflects real observed movement.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

from engine.basket_weights import CPI_2024_DIVISIONS
from engine.index_formula import young_aggregate

# Official division indices, All-India Combined, base 2024=100.
# Source: MOSPI CPI press release for June 2026, Annexure I. Retrieved
# 2026-08-05. This is the anchor every live reading is measured from.
ANCHOR_MONTH = "2026-06"
ANCHOR_DIVISION_INDICES: dict[str, float] = {
    "food_and_beverages": 106.98,
    "paan_tobacco_and_intoxicants": 107.94,
    "clothing_and_footwear": 107.97,
    "housing_water_electricity_gas_fuel": 103.54,
    "furnishings_household_equipment": 104.80,
    "health": 104.51,
    "transport": 105.45,
    "information_and_communication": 104.02,
    "recreation_sport_and_culture": 104.36,
    "education_services": 107.52,
    "restaurants_and_accommodation": 111.46,
    "personal_care_and_misc": 124.71,
}
ANCHOR_HEADLINE_INDEX = 107.00          # All India, same release

# Headline index twelve months before the month we are measuring, needed to
# express the live level as a YoY rate. Source: MOSPI 13-month level table.
BASE_YEAR_LEVELS: dict[str, float] = {
    "2025-07": 103.35, "2025-08": 103.74, "2025-09": 103.74, "2025-10": 103.74,
    "2025-11": 104.01, "2025-12": 104.10, "2026-01": 104.46,
}


@dataclass(frozen=True)
class DivisionReading:
    key: str
    weight: float
    anchor_index: float
    relative: Optional[float]      # measured current/base price ratio, or None
    live_index: float

    @property
    def observed(self) -> bool:
        return self.relative is not None

    @property
    def pct_change(self) -> float:
        return round((self.live_index / self.anchor_index - 1) * 100, 3)


@dataclass(frozen=True)
class LiveIndex:
    index: float                       # measured headline index level
    anchor_index: float                # what MOSPI last published
    anchor_month: str
    observed_weight: float             # % of basket actually repriced
    readings: list[DivisionReading] = field(default_factory=list)

    @property
    def pct_change_since_anchor(self) -> float:
        return round((self.index / self.anchor_index - 1) * 100, 3)

    def implied_yoy(self, base_level: float) -> Optional[float]:
        """YoY implied by this level against the published base twelve months back."""
        if base_level <= 0:
            return None
        return round((self.index / base_level - 1) * 100, 2)


def compute_live_index(
    price_relatives: Mapping[str, float],
    anchor: Optional[Mapping[str, float]] = None,
    weights: Optional[Mapping[str, float]] = None,
) -> LiveIndex:
    """
    Move the official anchor by measured price ratios and re-aggregate.

    `price_relatives` maps a division key to current/base price ratio — 1.02
    means that division's observed prices are 2% above where they stood at the
    anchor date. Divisions absent from the mapping are carried unchanged.

    A relative of exactly 1.0 (genuinely measured, no change) is treated as
    observed; only a missing key counts as unobserved. The distinction matters
    for the coverage figure.
    """
    anchor_indices = dict(anchor if anchor is not None else ANCHOR_DIVISION_INDICES)
    division_weights = dict(weights if weights is not None else CPI_2024_DIVISIONS)

    readings: list[DivisionReading] = []
    observed_weight = 0.0

    for key, anchor_index in anchor_indices.items():
        weight = division_weights.get(key, 0.0)
        relative = price_relatives.get(key)
        if relative is not None and relative > 0:
            live = anchor_index * relative
            observed_weight += weight
        else:
            relative = None
            live = anchor_index
        readings.append(DivisionReading(key, weight, anchor_index, relative, round(live, 4)))

    # young_aggregate expects relatives and multiplies by 100, so feed it
    # levels/100 to get a weighted level back. Same tested code path MOSPI's
    # higher-level aggregation implies.
    levels_as_relatives = {r.key: r.live_index / 100.0 for r in readings}
    weights_present = {r.key: r.weight for r in readings}
    index = young_aggregate(levels_as_relatives, weights_present)

    readings.sort(key=lambda r: -r.weight)
    return LiveIndex(
        index=round(index, 2),
        anchor_index=ANCHOR_HEADLINE_INDEX if anchor is None else round(
            young_aggregate(
                {k: v / 100.0 for k, v in anchor_indices.items()}, weights_present
            ), 2
        ),
        anchor_month=ANCHOR_MONTH,
        observed_weight=round(observed_weight, 2),
        readings=readings,
    )
