import pytest

from engine.basket_weights import (
    CPI_2024_DIVISIONS,
    CPI_2012_DIVISIONS,
    CPI_FOOD_WEIGHT,
    CPI_NONFOOD_WEIGHT,
    PROVENANCE,
    food_weight_for_month,
)


def test_2024_divisions_sum_to_100():
    assert sum(CPI_2024_DIVISIONS.values()) == pytest.approx(100.0, abs=0.01)


def test_2012_divisions_sum_to_100():
    assert sum(CPI_2012_DIVISIONS.values()) == pytest.approx(100.0, abs=0.01)


def test_food_and_nonfood_weights_are_complementary():
    assert CPI_FOOD_WEIGHT + CPI_NONFOOD_WEIGHT == pytest.approx(1.0, abs=1e-9)


def test_food_weight_matches_official_division_share():
    assert CPI_FOOD_WEIGHT == pytest.approx(
        CPI_2024_DIVISIONS["food_and_beverages"] / 100.0, abs=1e-9
    )
    assert CPI_FOOD_WEIGHT == pytest.approx(0.36753, abs=1e-9)


def test_all_twelve_coicop_divisions_present():
    assert len(CPI_2024_DIVISIONS) == 12


def test_provenance_is_recorded():
    assert PROVENANCE["base_year"] == "2024"
    assert PROVENANCE["effective_from"] == "2026-01"
    assert "mospi.gov.in" in PROVENANCE["source_url"]
    assert PROVENANCE["retrieved_on"] == "2026-08-05"


def test_food_weight_for_month_selects_by_base_era():
    # 2024=100 series is effective from Jan 2026
    assert food_weight_for_month("2026-01") == pytest.approx(0.36753, abs=1e-9)
    assert food_weight_for_month("2026-07") == pytest.approx(0.36753, abs=1e-9)
    # earlier months use the 2012 series weight
    assert food_weight_for_month("2025-12") == pytest.approx(0.4586, abs=1e-9)
    assert food_weight_for_month("2024-06") == pytest.approx(0.4586, abs=1e-9)


def test_food_weight_for_month_rejects_malformed_input():
    with pytest.raises(ValueError, match="YYYY-MM"):
        food_weight_for_month("June 2026")


def test_base_year_for_month_derives_from_date():
    from engine.basket_weights import base_year_for_month
    assert base_year_for_month("2026-01") == "2024"
    assert base_year_for_month("2026-07") == "2024"
    assert base_year_for_month("2025-12") == "2012"
    assert base_year_for_month("2009-01") == "2012"


def test_base_year_for_month_rejects_malformed_input():
    from engine.basket_weights import base_year_for_month
    with pytest.raises(ValueError, match="YYYY-MM"):
        base_year_for_month("2026")
