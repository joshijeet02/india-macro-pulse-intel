"""Unit tests for the tiered PDF extraction helpers."""
from scrapers._pdf_extract import (
    YOY_BOUNDS, extract_reference_month, extract_yoy,
    find_yoy_in_tables, find_yoy_in_text, sanity_check_release,
)


def test_extract_reference_month_basic():
    text = "Quick Estimates of Index of Industrial Production for March, 2026"
    assert extract_reference_month(text) == "2026-03"


def test_extract_reference_month_alternative_phrasing():
    text = "CPI for the month of October 2025 is released today."
    assert extract_reference_month(text) == "2025-10"


def test_extract_reference_month_missing():
    assert extract_reference_month("no date in this text") is None


def test_find_yoy_in_tables_picks_yoy_column():
    """Last bounded numeric in the row should be YoY (per MOSPI table layout)."""
    tables = [[
        ["Use-Based Group", "Weight", "Index Apr", "Index Mar", "YoY Apr"],
        ["Capital Goods", "10.5", "138.2", "135.1", "5.8"],
        ["Consumer Durables", "12.3", "141.0", "139.8", "-0.4"],
    ]]
    assert find_yoy_in_tables(tables, "Capital Goods") == 5.8
    assert find_yoy_in_tables(tables, "Consumer Durables") == -0.4


def test_find_yoy_in_tables_skips_weight_and_index():
    """Weight (10.5) and index level (138.2) must NOT be returned as YoY."""
    tables = [[
        ["Capital Goods", "10.5", "138.2", "135.1", "5.8"],
    ]]
    # 10.5 is in YOY_BOUNDS but the LAST bounded value is 5.8 — that's what we want.
    assert find_yoy_in_tables(tables, "Capital Goods") == 5.8


def test_find_yoy_in_tables_loose_label_match():
    """Label match is case-insensitive and ignores spaces/punctuation."""
    tables = [[["consumer non-durables", "5.0", "120.0", "118.5", "-3.2"]]]
    assert find_yoy_in_tables(tables, "Consumer Non-Durables") == -3.2
    assert find_yoy_in_tables(tables, "Consumer Nondurables") == -3.2


def test_find_yoy_in_text_anchored():
    """Anchored regex: same line as the label."""
    text = "Manufacturing growth was 4.6% in March 2026."
    assert find_yoy_in_text(text, "Manufacturing") == 4.6


def test_find_yoy_in_text_rejects_far_away_match():
    """If the label and number are separated by lots of text, don't match."""
    text = "Manufacturing — see annexure for details.\n" * 10 + "5.5"
    # The 5.5 is way outside the 120-char window
    result = find_yoy_in_text(text, "Manufacturing")
    assert result is None or result != 5.5


def test_find_yoy_in_text_respects_bounds():
    """An out-of-bounds number near the label should be skipped."""
    text = "Manufacturing index level: 138.2 percent of base year"
    # 138.2 is > YOY_BOUNDS upper, so it's filtered
    assert find_yoy_in_text(text, "Manufacturing") is None


def test_extract_yoy_falls_back_to_text():
    """If table extraction misses, regex fallback should still find the value."""
    tables = []
    text = "Capital Goods grew 12.3% YoY in April."
    assert extract_yoy(tables, text, "Capital Goods") == 12.3


def test_extract_yoy_aliases():
    """Alias matching for label variants."""
    tables = [[["Infrastructure/ Construction", "13.0", "150.0", "148.0", "7.5"]]]
    assert extract_yoy(tables, "", "Infrastructure", aliases=("Infrastructure/ Construction",)) == 7.5


def test_sanity_check_passes_on_good_record():
    payload = {
        "reference_month": "2026-03",
        "headline_yoy": 5.2,
        "manufacturing_yoy": 5.8,
        "mining_yoy": 3.1,
        "electricity_yoy": 4.5,
    }
    ok, _ = sanity_check_release(payload, ("manufacturing_yoy", "mining_yoy", "electricity_yoy"))
    assert ok


def test_sanity_check_rejects_missing_reference_month():
    payload = {"headline_yoy": 5.2}
    ok, reason = sanity_check_release(payload, ())
    assert not ok and "reference_month" in reason


def test_sanity_check_rejects_out_of_bounds_headline():
    payload = {"reference_month": "2026-03", "headline_yoy": 999.0}
    ok, reason = sanity_check_release(payload, ())
    assert not ok and "outside plausible bounds" in reason


def test_sanity_check_rejects_too_few_components():
    """If <50% of required components parsed, layout probably changed."""
    payload = {
        "reference_month": "2026-03",
        "headline_yoy": 5.2,
        "manufacturing_yoy": None,
        "mining_yoy": None,
        "electricity_yoy": None,
        "capital_goods_yoy": 8.0,
    }
    required = ("manufacturing_yoy", "mining_yoy", "electricity_yoy", "capital_goods_yoy")
    ok, reason = sanity_check_release(payload, required)
    assert not ok and "components parsed" in reason
