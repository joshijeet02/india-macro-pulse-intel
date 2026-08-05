"""
Characterisation tests for engine/ecomm_index.compute_index.

These pin CURRENT behaviour so the Task 7 refactor can be proven
behaviour-preserving. Two of these encode known defects (documented in
docs/PRD-2026-08-cpi-nowcast-index-rebuild.md) and are expected to be
UPDATED — deliberately, with a commit that says so — when those defects
are fixed in a later phase. They are not aspirational tests.
"""
import pytest

from engine.ecomm_index import compute_index, group_summary


def _rows(prices: dict) -> list[dict]:
    """Build price rows shaped like EcommStore.get_latest_prices() output."""
    return [
        {"item_id": iid, "price": p, "price_per_kg": None}
        for iid, p in prices.items()
    ]


def test_all_items_flat_gives_index_100():
    base = {"rice": 100.0, "atta": 100.0}
    result = compute_index(_rows({"rice": 100.0, "atta": 100.0}), base)
    assert result["index_value"] == 100.0
    assert result["coverage_pct"] == pytest.approx(26.3 / 100.1 * 100, abs=0.1)
    assert result["items_count"] == 2


def test_uniform_ten_percent_rise_gives_index_110():
    base = {"rice": 100.0, "atta": 100.0}
    result = compute_index(_rows({"rice": 110.0, "atta": 110.0}), base)
    assert result["index_value"] == 110.0


def test_price_per_kg_preferred_over_raw_price():
    base = {"rice": 20.0}
    rows = [{"item_id": "rice", "price": 500.0, "price_per_kg": 22.0}]
    result = compute_index(rows, base)
    # 22.0 / 20.0 = 1.10 -> 110.0, NOT 500/20
    assert result["index_value"] == 110.0


def test_item_missing_from_base_is_skipped():
    base = {"rice": 100.0}
    result = compute_index(_rows({"rice": 110.0, "atta": 105.0}), base)
    assert result["items_count"] == 1
    assert result["index_value"] == 110.0


def test_zero_base_price_is_skipped():
    base = {"rice": 100.0, "atta": 0.0}
    result = compute_index(_rows({"rice": 110.0, "atta": 105.0}), base)
    assert result["items_count"] == 1


def test_no_overlap_returns_none_index():
    result = compute_index(_rows({"rice": 110.0}), {})
    assert result["index_value"] is None
    assert result["coverage_pct"] == 0.0
    assert result["items_count"] == 0
    assert result["components"] == []


def test_KNOWN_DEFECT_coverage_change_shifts_index_with_no_price_change():
    """
    DEFECT (PRD 0): the index renormalises over matched weight, so an item
    dropping out moves the level even when no price moved. Fixed by
    matched-sample chaining in a later phase; pinned here so the Task 7
    refactor does not silently alter it.
    """
    base = {"rice": 100.0, "atta": 100.0, "onion": 100.0}
    # rice flat, others +10%
    all_present = compute_index(
        _rows({"rice": 100.0, "atta": 110.0, "onion": 110.0}), base
    )
    rice_missing = compute_index(
        _rows({"atta": 110.0, "onion": 110.0}), base
    )
    assert all_present["index_value"] < rice_missing["index_value"]
    assert rice_missing["index_value"] == 110.0


def test_group_summary_rolls_up_by_cpi_group():
    base = {"rice": 100.0, "atta": 100.0, "onion": 100.0}
    result = compute_index(
        _rows({"rice": 110.0, "atta": 110.0, "onion": 120.0}), base
    )
    groups = {g["cpi_group"]: g for g in group_summary(result["components"])}
    assert groups["Cereals"]["avg_pct_change"] == pytest.approx(10.0, abs=0.01)
    assert groups["Vegetables"]["avg_pct_change"] == pytest.approx(20.0, abs=0.01)
    assert groups["Cereals"]["item_count"] == 2
