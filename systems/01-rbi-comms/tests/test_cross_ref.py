"""
Tests for the rbi-comms ↔ macro-pulse cross-reference helper.

Reads the actual sibling system's data files. Tests run against real
committed data — they fail fast if the macro-pulse seed module's shape
ever changes in a way that breaks the regex-based fallback.
"""
from engine.cross_ref import (
    latest_cpi_print, latest_iip_print, macro_print_summary,
)


def test_macro_summary_returns_available_true_when_data_present():
    """The committed macro-pulse seed always has CPI/IIP data."""
    summary = macro_print_summary()
    assert summary["available"] is True
    assert summary["cpi"] is not None
    assert summary["iip"] is not None


def test_latest_cpi_has_required_fields():
    cpi = latest_cpi_print()
    assert cpi is not None
    for k in ("reference_month", "headline_yoy"):
        assert k in cpi, f"missing {k}"
    # reference_month is YYYY-MM
    assert len(cpi["reference_month"]) == 7
    assert cpi["reference_month"][4] == "-"
    # headline_yoy is a sane CPI value
    assert -2 <= cpi["headline_yoy"] <= 15


def test_latest_iip_has_required_fields():
    iip = latest_iip_print()
    assert iip is not None
    assert "reference_month" in iip
    assert "headline_yoy" in iip
    # IIP has wider range than CPI
    assert -15 <= iip["headline_yoy"] <= 20


def test_macro_url_is_present():
    """UI uses this for the deep-link button — must always be set."""
    summary = macro_print_summary()
    assert summary["macro_url"].startswith("http")


def test_iip_includes_components_from_json_sidecar():
    """When the macro-pulse JSON sidecar has the latest IIP, components flow through."""
    iip = latest_iip_print()
    assert iip is not None
    # If we got it from the JSON sidecar (not the seed regex fallback),
    # we expect manufacturing_yoy / capital_goods_yoy etc.
    if iip.get("source", "").startswith("https://"):
        assert "manufacturing_yoy" in iip
