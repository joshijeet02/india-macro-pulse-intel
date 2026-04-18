import json
from pathlib import Path
import pytest
from scrapers.mospi_cpi import fetch_latest_cpi


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
