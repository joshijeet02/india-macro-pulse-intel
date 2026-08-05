"""The division coverage map and headline reconstruction."""
import pytest

from engine.basket_weights import CPI_2024_DIVISIONS
from engine.cpi_structure import (
    DIVISIONS, DIVISION_BY_KEY, MODELLED, OBSERVED, PARTIAL, contributions,
    covered_weight, directly_observable_weight, headline_from_divisions,
    weight_by_observability,
)

# Division-level inflation, Jan-2026 Combined, MOSPI Annexure I.
JAN_2026 = {
    "food_and_beverages": 2.11, "paan_tobacco_and_intoxicants": 2.86,
    "clothing_and_footwear": 2.98, "housing_water_electricity_gas_fuel": 1.53,
    "furnishings_household_equipment": 1.45, "health": 2.19, "transport": 0.09,
    "information_and_communication": 0.16, "recreation_sport_and_culture": 2.32,
    "education_services": 3.35, "restaurants_and_accommodation": 2.87,
    "personal_care_and_misc": 19.02,
}


def test_every_official_division_is_mapped():
    assert {d.key for d in DIVISIONS} == set(CPI_2024_DIVISIONS)


def test_weights_match_the_official_source_exactly():
    for d in DIVISIONS:
        assert d.weight == CPI_2024_DIVISIONS[d.key], d.key


def test_weights_sum_to_100():
    assert sum(d.weight for d in DIVISIONS) == pytest.approx(100.0, abs=0.01)


def test_observability_classes_partition_the_basket():
    totals = weight_by_observability()
    assert set(totals) == {OBSERVED, PARTIAL, MODELLED}
    assert sum(totals.values()) == pytest.approx(100.0, abs=0.01)


def test_directly_observable_weight_is_a_conservative_understatement():
    """PARTIAL counts at half, so the claim errs low — the safe direction."""
    observable = directly_observable_weight()
    totals = weight_by_observability()
    assert observable == pytest.approx(
        totals[OBSERVED] + totals[PARTIAL] * 0.5, abs=0.01
    )
    assert totals[OBSERVED] < observable < totals[OBSERVED] + totals[PARTIAL]


def test_reconstructing_headline_reproduces_the_official_print():
    """
    The whole architecture rests on this: weighting divisions by the official
    weights must rebuild the published headline. Jan-2026 printed 2.75%.
    """
    assert headline_from_divisions(JAN_2026) == pytest.approx(2.75, abs=0.03)


def test_full_division_set_covers_the_whole_basket():
    assert covered_weight(JAN_2026) == pytest.approx(100.0, abs=0.01)


def test_partial_division_set_reports_partial_coverage():
    subset = {"food_and_beverages": 2.11, "transport": 0.09}
    expected = CPI_2024_DIVISIONS["food_and_beverages"] + CPI_2024_DIVISIONS["transport"]
    assert covered_weight(subset) == pytest.approx(expected, abs=0.01)


def test_contributions_rank_by_impact_not_by_weight():
    """
    The organising insight: a 5%-weight division out-contributed food, which
    carries seven times the weight. If this ever sorts by weight, the whole
    prioritisation argument is silently inverted.
    """
    ranked = contributions(JAN_2026)
    assert ranked[0][0] == "personal_care_and_misc"
    assert ranked[1][0] == "food_and_beverages"
    # ...and it really is the lighter division
    assert ranked[0][1] < ranked[1][1]


def test_contributions_sum_to_the_headline():
    assert sum(c for _, _, _, c in contributions(JAN_2026)) == pytest.approx(2.75, abs=0.03)


def test_bullion_division_is_flagged_observed():
    """Gold/silver drove 35% of the Jan-2026 print; it must not be 'modelled'."""
    assert DIVISION_BY_KEY["personal_care_and_misc"].observability == OBSERVED
    assert "gold_spot" in DIVISION_BY_KEY["personal_care_and_misc"].sources


def test_unknown_divisions_are_ignored_not_crashed_on():
    assert headline_from_divisions({"not_a_division": 5.0}) is None
    assert covered_weight({"not_a_division": 5.0}) == 0.0


def test_empty_input_returns_none():
    assert headline_from_divisions({}) is None
