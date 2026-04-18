import json
from pathlib import Path
import pytest
from scrapers.mospi_cpi import fetch_latest_cpi
from scrapers.mospi_iip import fetch_latest_iip


def test_cpi_fixture_mode():
    """fetch_latest_cpi(use_fixture=True) returns correct fixture data."""
    data = fetch_latest_cpi(use_fixture=True)
    assert data is not None
    assert data["reference_month"] == "2025-03"
    assert data["headline_yoy"] == pytest.approx(3.34)
    assert data["source"] == "fixture"


def test_cpi_fixture_has_required_keys():
    data = fetch_latest_cpi(use_fixture=True)
    for key in ("reference_month", "release_date", "headline_yoy", "food_yoy", "fuel_yoy"):
        assert key in data, f"Missing key: {key}"


def test_iip_fixture_mode():
    """fetch_latest_iip(use_fixture=True) returns correct fixture data."""
    data = fetch_latest_iip(use_fixture=True)
    assert data is not None
    assert data["reference_month"] == "2025-01"
    assert data["headline_yoy"] == pytest.approx(5.0)
    assert data["capital_goods_yoy"] == pytest.approx(8.2)
    assert data["source"] == "fixture"


def test_iip_fixture_has_required_keys():
    data = fetch_latest_iip(use_fixture=True)
    required = (
        "reference_month", "release_date", "headline_yoy",
        "capital_goods_yoy", "consumer_durables_yoy",
        "infra_construction_yoy",
    )
    for key in required:
        assert key in data, f"Missing key: {key}"
