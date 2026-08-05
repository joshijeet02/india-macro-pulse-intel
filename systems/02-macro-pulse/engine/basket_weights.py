"""
Official MOSPI CPI weights, with provenance.

Source: MOSPI, "First Press Release of Consumer Price Index on Base
2024=100", dated 12 February 2026, Annexure V Q39 (division-wise weights,
Combined sector).

Both weight sets below are expressed on the COICOP 2018 division structure
so they are directly comparable. Note that the widely-quoted "45.86% ->
36.75%" fall in the food share conflates two effects (Annexure V Q40):

  45.86% -> 40.10%   genuine expenditure shift, CPI 2012 classification
  42.62% -> 36.75%   genuine expenditure shift, COICOP 2018 classification
  40.10% vs 36.75%   reclassification only, chiefly restaurants and
                     accommodation splitting into their own division

CPI_2012_FOOD_WEIGHT below is the headline 45.86% figure, because that is
what the CPI 2012 series itself published and therefore what any pre-2026
release must be decomposed with.
"""
from __future__ import annotations

import re

PROVENANCE = {
    "base_year": "2024",
    "effective_from": "2026-01",
    "weight_reference": "HCES 2023-24",
    "price_reference": "calendar year 2024",
    "classification": "COICOP 2018",
    "sector": "Combined",
    "source_url": (
        "https://www.mospi.gov.in/uploads/latestReleases/"
        "latest_release_1770891893893_6b458c0a-c327-4fef-a554-41131ea67273_"
        "Press_Relase_of_CPI_for_Jan26.pdf"
    ),
    "source_note": "Annexure V Q39, division-wise weights, Combined",
    "retrieved_on": "2026-08-05",
}

# Division-wise weights, Combined sector, COICOP 2018 structure (% of index).
CPI_2024_DIVISIONS: dict[str, float] = {
    "food_and_beverages":                36.753,
    "paan_tobacco_and_intoxicants":       2.989,
    "clothing_and_footwear":              6.383,
    "housing_water_electricity_gas_fuel": 17.665,
    "furnishings_household_equipment":     4.469,
    "health":                              6.100,
    "transport":                           8.796,
    "information_and_communication":       3.609,
    "recreation_sport_and_culture":        1.516,
    "education_services":                  3.333,
    "restaurants_and_accommodation":       3.348,
    "personal_care_and_misc":              5.038,
}

# The same divisions valued on the CPI 2012 series, for like-for-like
# comparison. Source: same table, "CPI 2012" column.
CPI_2012_DIVISIONS: dict[str, float] = {
    "food_and_beverages":                42.617,
    "paan_tobacco_and_intoxicants":       2.380,
    "clothing_and_footwear":              6.527,
    "housing_water_electricity_gas_fuel": 16.888,
    "furnishings_household_equipment":     3.656,
    "health":                              5.900,
    "transport":                           6.394,
    "information_and_communication":       3.323,
    "recreation_sport_and_culture":        1.547,
    "education_services":                  3.513,
    "restaurants_and_accommodation":       3.246,
    "personal_care_and_misc":              4.006,
}

# Headline food share as published by each series, for decomposition.
CPI_FOOD_WEIGHT = CPI_2024_DIVISIONS["food_and_beverages"] / 100.0   # 0.36753
CPI_NONFOOD_WEIGHT = 1.0 - CPI_FOOD_WEIGHT                            # 0.63247

# CPI 2012 series as it was actually published (group structure, not COICOP).
CPI_2012_FOOD_WEIGHT = 0.4586
CPI_2012_FUEL_WEIGHT = 0.0684

# First reference month compiled on the 2024=100 series.
BASE_2024_FIRST_MONTH = "2026-01"

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def food_weight_for_month(reference_month: str) -> float:
    """
    Return the food weight appropriate to a release's reference month.

    MOSPI switched to 2024=100 from January 2026. Decomposing a pre-2026
    release with 2024 weights (or vice versa) misattributes the food
    contribution, so the base era must follow the data, not the clock.
    """
    if not _MONTH_RE.match(reference_month or ""):
        raise ValueError(
            f"reference_month must be YYYY-MM, got {reference_month!r}"
        )
    if reference_month >= BASE_2024_FIRST_MONTH:
        return CPI_FOOD_WEIGHT
    return CPI_2012_FOOD_WEIGHT
