"""Tests for the JSON-sidecar merging in seed/historical_data.py."""
import json
from pathlib import Path
from unittest.mock import patch

from seed import historical_data as seed_mod


def _write_updates_file(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "release_updates.json"
    p.write_text(json.dumps(payload))
    return p


def test_merger_returns_baseline_when_no_json(tmp_path, monkeypatch):
    monkeypatch.setattr(seed_mod, "RELEASE_UPDATES_PATH", tmp_path / "missing.json")
    cpi = seed_mod._merged_cpi_history()
    iip = seed_mod._merged_iip_history()
    assert len(cpi) == len(seed_mod.CPI_HISTORY)
    assert len(iip) == len(seed_mod.IIP_HISTORY)


def test_merger_appends_newer_cpi_entry(tmp_path, monkeypatch):
    updates_path = _write_updates_file(tmp_path, {
        "cpi": [{
            "reference_month": "2099-12",
            "release_date": "2100-01-13",
            "headline_yoy": 4.2,
            "food_yoy": 3.0,
            "fuel_yoy": 2.5,
            "consensus_forecast": 4.0,
        }],
        "iip": [],
    })
    monkeypatch.setattr(seed_mod, "RELEASE_UPDATES_PATH", updates_path)

    cpi = seed_mod._merged_cpi_history()
    months = [row[0] for row in cpi]
    assert "2099-12" in months
    # Sorted: future entry should be at end
    assert cpi[-1][0] == "2099-12"


def test_merger_overrides_existing_month(tmp_path, monkeypatch):
    """If JSON contains a month already in baseline, JSON wins."""
    # Pick the FIRST baseline CPI month and override its headline
    first_baseline = seed_mod.CPI_HISTORY[0]
    override_month = first_baseline[0]
    updates_path = _write_updates_file(tmp_path, {
        "cpi": [{
            "reference_month": override_month,
            "release_date": first_baseline[1],
            "headline_yoy": 99.9,
            "food_yoy": 0.0,
            "fuel_yoy": 0.0,
            "consensus_forecast": 0.0,
        }],
        "iip": [],
    })
    monkeypatch.setattr(seed_mod, "RELEASE_UPDATES_PATH", updates_path)
    cpi = dict((row[0], row) for row in seed_mod._merged_cpi_history())
    assert cpi[override_month][2] == 99.9


def test_merger_iip_partial_keeps_baseline_fields(tmp_path, monkeypatch):
    """A partial scrape (only headline) must not erase richer baseline data."""
    first_baseline = seed_mod.IIP_HISTORY[0]
    override_month = first_baseline["reference_month"]
    # Partial: only headline_yoy + reference_month, no components
    updates_path = _write_updates_file(tmp_path, {
        "cpi": [],
        "iip": [{
            "reference_month": override_month,
            "headline_yoy": 88.8,
        }],
    })
    monkeypatch.setattr(seed_mod, "RELEASE_UPDATES_PATH", updates_path)
    iip = {row["reference_month"]: row for row in seed_mod._merged_iip_history()}
    record = iip[override_month]
    assert record["headline_yoy"] == 88.8  # JSON override applied
    # Baseline component preserved (not erased by partial JSON entry)
    assert record.get("manufacturing_yoy") == first_baseline.get("manufacturing_yoy")


def test_merger_tolerates_invalid_json(tmp_path, monkeypatch, capsys):
    bad = tmp_path / "release_updates.json"
    bad.write_text("{ this is not json")
    monkeypatch.setattr(seed_mod, "RELEASE_UPDATES_PATH", bad)
    # Should not raise — just print a warning and return baseline
    cpi = seed_mod._merged_cpi_history()
    assert len(cpi) == len(seed_mod.CPI_HISTORY)
