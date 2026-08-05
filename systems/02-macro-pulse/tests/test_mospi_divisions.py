"""
Division-index parsing, and the rebuild check that makes an anchor trustworthy.

The whole live index hangs off this table. A mis-parsed anchor would move every
division reading downstream without ever looking broken, so the parser must
refuse a bad parse rather than return a partial one.
"""
import pytest

from engine.basket_weights import CPI_2024_DIVISIONS
from scrapers.mospi_divisions import (
    DIVISION_CODES, parse_division_indices, sanity_check,
)

# Verbatim rows from MOSPI's June 2026 release, Annexure I.
JUNE_TEXT = """
Division Index Inflation
code Division name Rural Urban Comb. Rural Urban Comb.
01 Food and beverages 106.70 107.46 106.98 5.21 4.79 5.05
02 Paan, tobacco and intoxicants 107.88 108.10 107.94 4.61 5.31 4.83
03 Clothing and footwear 108.93 106.41 107.97 3.78 2.32 3.23
04 104.24 103.13 103.54 2.42 1.75 1.99
05 equipment and routine 105.16 104.32 104.80 2.54 1.73 2.19
06 Health 104.28 104.88 104.51 1.41 1.44 1.42
07 Transport 105.54 105.34 105.45 4.37 4.24 4.31
08 104.31 103.66 104.02 0.55 0.28 0.43
09 Recreation, sport and culture 104.76 103.97 104.36 1.90 1.60 1.75
10 Education services 106.18 108.40 107.52 2.60 3.80 3.34
11 110.74 112.11 111.46 6.75 7.06 6.91
13 protection and miscellaneous 125.62 123.51 124.71 17.90 15.40 16.72
All India 107.24 106.69 107.00 4.74 3.92 4.38
"""


def test_all_twelve_divisions_are_mapped_to_known_keys():
    assert set(DIVISION_CODES.values()) == set(CPI_2024_DIVISIONS)


def test_coicop_division_12_is_absent_from_indian_cpi():
    assert "12" not in DIVISION_CODES


def test_parses_every_division_and_the_headline():
    parsed = parse_division_indices(JUNE_TEXT)
    assert len(parsed["divisions"]) == 12
    assert parsed["headline_index"] == pytest.approx(107.00)
    assert parsed["headline_yoy"] == pytest.approx(4.38)


def test_reads_the_combined_column_not_rural_or_urban():
    """Columns are rural, urban, combined — combined is the third."""
    parsed = parse_division_indices(JUNE_TEXT)
    assert parsed["divisions"]["food_and_beverages"] == pytest.approx(106.98)
    assert parsed["inflation"]["food_and_beverages"] == pytest.approx(5.05)


def test_handles_rows_whose_division_name_wrapped_away():
    """Codes 04, 08 and 11 have no name on their row in the real PDF."""
    parsed = parse_division_indices(JUNE_TEXT)
    assert parsed["divisions"]["housing_water_electricity_gas_fuel"] == pytest.approx(103.54)
    assert parsed["divisions"]["information_and_communication"] == pytest.approx(104.02)
    assert parsed["divisions"]["restaurants_and_accommodation"] == pytest.approx(111.46)


def test_rebuild_check_passes_on_a_good_parse():
    ok, reason = sanity_check(parse_division_indices(JUNE_TEXT))
    assert ok, reason
    assert "107.00" in reason


def test_rebuild_check_rejects_a_partial_parse():
    """A partial anchor is worse than none — it looks fine and is wrong."""
    partial = parse_division_indices(JUNE_TEXT)
    partial["divisions"].pop("food_and_beverages")
    ok, reason = sanity_check(partial)
    assert not ok
    assert "11 of 12" in reason


def test_rebuild_check_rejects_a_corrupted_value():
    corrupted = parse_division_indices(JUNE_TEXT)
    corrupted["divisions"]["food_and_beverages"] = 200.0
    ok, reason = sanity_check(corrupted)
    assert not ok
    assert "!=" in reason


def test_rebuild_check_needs_a_printed_headline_to_compare_against():
    parsed = parse_division_indices(JUNE_TEXT)
    parsed["headline_index"] = None
    assert sanity_check(parsed)[0] is False


def test_rows_without_six_numbers_are_ignored():
    assert parse_division_indices("01 Food and beverages 106.70 107.46")["divisions"] == {}
