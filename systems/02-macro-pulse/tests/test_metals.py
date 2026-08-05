"""Bullion price fetch — the highest-contribution observable in the index."""
from unittest.mock import patch

import pytest

from scrapers import metals


def test_troy_ounce_conversion_is_correct():
    """A wrong constant would scale every gold reading silently."""
    assert metals.TROY_OZ_IN_GRAMS == pytest.approx(31.1034768, abs=1e-7)


def test_metal_converts_usd_per_oz_to_inr_per_gram():
    payload = {"price": 4247.0, "name": "Gold", "updatedAt": "2026-08-05T16:54:44"}
    with patch.object(metals, "_get_json", return_value=payload):
        got = metals.fetch_metal_inr_per_gram("XAU", usd_inr=95.12)
    assert got["inr_per_gram"] == pytest.approx(4247.0 * 95.12 / 31.1034768, abs=0.01)
    assert got["usd_per_oz"] == 4247.0
    assert got["symbol"] == "XAU"


def test_metal_returns_none_on_missing_price():
    with patch.object(metals, "_get_json", return_value={"name": "Gold"}):
        assert metals.fetch_metal_inr_per_gram("XAU", usd_inr=95.12) is None


def test_metal_returns_none_on_nonpositive_price():
    with patch.object(metals, "_get_json", return_value={"price": 0}):
        assert metals.fetch_metal_inr_per_gram("XAU", usd_inr=95.12) is None


def test_fx_prefers_primary_when_both_agree():
    def fake(url, timeout=15):
        if "frankfurter" in url:
            return {"rates": {"INR": 95.12}}
        return {"rates": {"INR": 95.35}}
    with patch.object(metals, "_get_json", side_effect=fake):
        assert metals.fetch_usd_inr() == pytest.approx(95.12)


def test_fx_falls_back_when_primary_is_down():
    def fake(url, timeout=15):
        return None if "frankfurter" in url else {"rates": {"INR": 95.35}}
    with patch.object(metals, "_get_json", side_effect=fake):
        assert metals.fetch_usd_inr() == pytest.approx(95.35)


def test_fx_warns_when_sources_disagree_materially(caplog):
    """A silently wrong rate corrupts every INR price while looking plausible."""
    def fake(url, timeout=15):
        if "frankfurter" in url:
            return {"rates": {"INR": 95.0}}
        return {"rates": {"INR": 130.0}}      # ~37% apart
    with patch.object(metals, "_get_json", side_effect=fake):
        with caplog.at_level("WARNING"):
            rate = metals.fetch_usd_inr()
    assert rate == pytest.approx(95.0)
    assert any("disagree" in r.message for r in caplog.records)


def test_fx_returns_none_when_both_sources_fail():
    with patch.object(metals, "_get_json", return_value=None):
        assert metals.fetch_usd_inr() is None


def test_bullion_is_empty_without_a_trustworthy_fx_rate():
    """INR figures built on a guessed rate would be fiction."""
    with patch.object(metals, "fetch_usd_inr", return_value=None):
        assert metals.fetch_bullion() == []
