"""
Index mathematics for CPI-tracking price indices.

Mirrors MOSPI's CPI 2024 two-stage compilation (source: MOSPI First Press
Release of CPI on Base 2024=100, 12 Feb 2026, Annexure V Q20-Q21):

  Stage 1 (elementary):  Jevons  — geometric mean of price relatives
                                   across the quotes for a single item.
  Stage 2 (aggregation): Young / modified Laspeyres — weighted arithmetic
                                   mean of elementary indices.

This module is deliberately free of project imports so it can be tested in
isolation and reused by both the Amazon and DoCA index builders.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def jevons_elementary(
    current: Sequence[float],
    base: Sequence[float],
) -> float:
    """
    Geometric mean of price relatives — the Jevons elementary index.

    `current` and `base` are parallel sequences of price quotes for ONE
    item. Pairs where either price is non-positive are excluded: they carry
    no price-change information and log() is undefined on them.

    Returns a ratio (1.10 == a 10% rise), not an index level.

    Note: Jevons is only meaningful over a STABLE quote set. Averaging
    relatives of products that changed between periods measures
    substitution, not inflation.
    """
    if len(current) != len(base):
        raise ValueError(
            f"current and base must be the same length, "
            f"got {len(current)} and {len(base)}"
        )

    log_relatives = [
        math.log(c / b)
        for c, b in zip(current, base)
        if c > 0 and b > 0
    ]
    if not log_relatives:
        raise ValueError("no usable quote pairs (all non-positive)")

    return math.exp(sum(log_relatives) / len(log_relatives))


def young_aggregate(
    relatives: Mapping[str, float],
    weights: Mapping[str, float],
) -> float:
    """
    Young / modified Laspeyres aggregation — weighted arithmetic mean of
    elementary price relatives, expressed as an index level (base = 100).

    Only keys present in BOTH mappings contribute. A relative with no
    weight cannot be aggregated; a weight with no relative has nothing to
    contribute this period.

    Returns an index level (110.0 == 10% above base).
    """
    shared = relatives.keys() & weights.keys()

    total_weight = sum(weights[k] for k in shared)
    if total_weight <= 0:
        raise ValueError("zero total weight — nothing to aggregate")

    weighted = sum(weights[k] * relatives[k] for k in shared)
    return (weighted / total_weight) * 100.0


def chain_link(
    previous_level: float,
    current_prices: Mapping[str, float],
    previous_prices: Mapping[str, float],
    weights: Mapping[str, float],
) -> float:
    """
    Chain the index forward one period using a matched sample.

    Only items priced in BOTH periods contribute. This is what prevents
    coverage changes from masquerading as price changes: an item that
    drops out is excluded from both the numerator and the denominator of
    the movement, so it cannot shift the level.

    If nothing matched, we have learned nothing about price change this
    period and the previous level is returned unchanged.
    """
    matched = (
        current_prices.keys()
        & previous_prices.keys()
        & weights.keys()
    )
    matched = {
        k for k in matched
        if current_prices[k] > 0 and previous_prices[k] > 0 and weights[k] > 0
    }
    if not matched:
        return previous_level

    total_weight = sum(weights[k] for k in matched)
    movement = sum(
        weights[k] * (current_prices[k] / previous_prices[k])
        for k in matched
    ) / total_weight

    return previous_level * movement
