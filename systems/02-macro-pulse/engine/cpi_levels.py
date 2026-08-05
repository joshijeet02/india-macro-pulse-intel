"""
Headline CPI index levels, and the month-on-month series derived from them.

Why levels rather than YoY:

    YoY_t = (I_t / I_{t-12} - 1) x 100

The denominator is already published. So a large part of next month's YoY is
knowable today with no forecasting at all — it is arithmetic on a number MOSPI
released a year ago. Extrapolating YoY directly throws that away and implicitly
assumes last year's month-on-month pattern repeats.

Concretely: July 2025 recorded +0.82% MoM, the largest in the series. For July
2026's YoY to hold at 4.38%, this July must repeat that unusually hot month. On
a normal MoM it prints near 3.84%. A YoY-momentum model cannot see any of this.

So we work in levels: predict MoM, chain onto the last level, divide by the
known base.

Where the levels come from:

MOSPI's first 2024=100 release (12 Feb 2026) published a 13-month level table,
Jan-2025 to Jan-2026. Every subsequent monthly release publishes that month's
YoY, and I_t = I_{t-12} x (1 + YoY_t/100) reconstructs the level exactly.

That identity is not an approximation and it is verified against published
levels: reconstructed Jun-2026 = 107.00 against 107.00 printed, Apr-2026 =
105.11 against 105.12. `verify_against_published` keeps that check honest.
"""
from __future__ import annotations

from typing import Iterable, Mapping, Optional, Sequence

# All-India CPI (General), Combined, base 2024=100.
# Source: MOSPI, First Press Release of CPI on Base 2024=100, 12 Feb 2026,
# 13-month table. Retrieved 2026-08-05.
ANCHOR_LEVELS: dict[str, float] = {
    "2025-01": 101.67, "2025-02": 101.32, "2025-03": 101.39, "2025-04": 101.58,
    "2025-05": 101.90, "2025-06": 102.51, "2025-07": 103.35, "2025-08": 103.74,
    "2025-09": 103.74, "2025-10": 103.74, "2025-11": 104.01, "2025-12": 104.10,
    "2026-01": 104.46,
}

# Headline index as printed in later releases' Annexure I (Combined column).
# Used only to verify the reconstruction — never as an input to it.
PUBLISHED_LEVELS: dict[str, float] = {
    "2026-04": 105.12,
    "2026-06": 107.00,
}

ANCHOR_SOURCE = (
    "MOSPI, First Press Release of Consumer Price Index on Base 2024=100, "
    "12 February 2026 (13-month level table)"
)


def _shift_year(reference_month: str, years: int) -> str:
    year, month = reference_month.split("-")
    return f"{int(year) + years:04d}-{month}"


def build_levels(
    yoy_by_month: Mapping[str, float],
    anchor: Optional[Mapping[str, float]] = None,
) -> dict[str, float]:
    """
    Extend the anchor forward using published YoY.

    `yoy_by_month` maps 'YYYY-MM' to headline YoY %. A month is reconstructed
    only when its base month (12 earlier) is already known, so the series grows
    forward month by month and never invents a level from nothing.

    Only months on the 2024=100 series are usable: the anchor is on that basis,
    and a YoY drawn from the retired 2012=100 series describes a different
    basket. Mixing them would produce a level that looks plausible and is wrong.
    """
    levels = dict(anchor if anchor is not None else ANCHOR_LEVELS)

    for month in sorted(yoy_by_month):
        if month in levels:
            continue
        base_month = _shift_year(month, -1)
        base = levels.get(base_month)
        if base is None:
            continue
        levels[month] = round(base * (1 + yoy_by_month[month] / 100.0), 2)

    return levels


def verify_against_published(
    levels: Mapping[str, float],
    tolerance: float = 0.02,
) -> list[tuple[str, float, float, bool]]:
    """
    Check reconstructed levels against the ones MOSPI actually printed.

    Returns (month, reconstructed, published, ok). A failure here means the
    identity or the anchor is wrong, and every downstream MoM is suspect — so
    this is worth asserting in tests rather than trusting once.
    """
    out = []
    for month, published in sorted(PUBLISHED_LEVELS.items()):
        if month not in levels:
            continue
        got = levels[month]
        out.append((month, got, published, abs(got - published) <= tolerance))
    return out


def mom_series(levels: Mapping[str, float]) -> dict[str, float]:
    """Month-on-month % change, keyed by the later month."""
    months = sorted(levels)
    out: dict[str, float] = {}
    for previous, current in zip(months, months[1:]):
        if _shift_month(previous) != current:
            continue          # a gap: MoM across it would be meaningless
        prior = levels[previous]
        if prior > 0:
            out[current] = (levels[current] / prior - 1) * 100.0
    return out


def _shift_month(reference_month: str) -> str:
    year, month = (int(x) for x in reference_month.split("-"))
    return f"{year + 1:04d}-01" if month == 12 else f"{year:04d}-{month + 1:02d}"


def yoy_from_levels(levels: Mapping[str, float], month: str) -> Optional[float]:
    """YoY for a month, if both it and its base twelve months earlier exist."""
    base = levels.get(_shift_year(month, -1))
    current = levels.get(month)
    if base is None or current is None or base <= 0:
        return None
    return round((current / base - 1) * 100.0, 2)


def base_month_mom(levels: Mapping[str, float], month: str) -> Optional[float]:
    """
    The MoM recorded in the base month a year before `month`.

    This is the base effect in one number. A large value means last year's
    corresponding month was hot, so this year's YoY faces a high bar and will
    fall unless the current month matches it.
    """
    return mom_series(levels).get(_shift_year(month, -1))
