"""Back-dated bullion averages — the one part of the basket we can measure retroactively."""
from unittest.mock import patch

import pytest

from scrapers import metals_history as mh


CLOSES = {
    "2026-06-01": 4300.0, "2026-06-15": 4320.0, "2026-06-30": 4340.0,
    "2026-07-01": 4200.0, "2026-07-15": 4180.0, "2026-07-31": 4160.0,
}
FX = {
    "2026-06-01": 94.0, "2026-06-15": 95.0, "2026-06-30": 96.0,
    "2026-07-01": 96.0, "2026-07-15": 96.0, "2026-07-31": 96.0,
}


def test_troy_ounce_constant_is_right():
    assert mh.TROY_OZ_IN_GRAMS == pytest.approx(31.1034768, abs=1e-7)


def test_each_day_converts_at_its_own_exchange_rate():
    """
    Converting a monthly average price at a monthly average rate is a different
    number whenever the rupee moves within the month — and it did, 94.72 to
    96.26 between mid-June and mid-July.
    """
    got = mh.monthly_average_inr_per_gram(CLOSES, FX, "2026-06")
    expected = sum(
        CLOSES[d] * FX[d] / mh.TROY_OZ_IN_GRAMS for d in CLOSES if d.startswith("2026-06")
    ) / 3
    assert got == pytest.approx(expected, abs=1e-6)

    naive = (sum(CLOSES[d] for d in CLOSES if d.startswith("2026-06")) / 3) \
        * (sum(FX[d] for d in FX if d.startswith("2026-06")) / 3) / mh.TROY_OZ_IN_GRAMS
    assert got != pytest.approx(naive, abs=1e-9)


def test_month_with_no_data_returns_none_not_zero():
    """None means 'not measured'. Zero would mean 'measured as unchanged'."""
    assert mh.monthly_average_inr_per_gram(CLOSES, FX, "2026-03") is None


def test_days_without_an_fx_rate_are_skipped():
    partial_fx = {"2026-06-15": 95.0}
    got = mh.monthly_average_inr_per_gram(CLOSES, partial_fx, "2026-06")
    assert got == pytest.approx(4320.0 * 95.0 / mh.TROY_OZ_IN_GRAMS, abs=1e-6)


def test_measured_mom_computes_the_ratio():
    with patch.object(mh, "_daily_fx", return_value=FX), \
         patch.object(mh, "_daily_closes", return_value=CLOSES):
        got = mh.measured_bullion_mom("2026-06", "2026-07")
    assert got is not None
    assert got["mom_pct"] < 0            # gold fell between the two months
    assert got["from_month"] == "2026-06" and got["to_month"] == "2026-07"


def test_missing_fx_yields_no_measurement_rather_than_a_guess():
    with patch.object(mh, "_daily_fx", return_value={}):
        assert mh.measured_bullion_mom("2026-06", "2026-07") is None


def test_missing_price_history_yields_no_measurement():
    with patch.object(mh, "_daily_fx", return_value=FX), \
         patch.object(mh, "_daily_closes", return_value={}):
        assert mh.measured_bullion_mom("2026-06", "2026-07") is None


def test_gold_alone_is_enough_if_silver_is_unavailable():
    def closes(symbol, rng="6mo"):
        return CLOSES if symbol == mh.SYMBOLS["gold"] else {}
    with patch.object(mh, "_daily_fx", return_value=FX), \
         patch.object(mh, "_daily_closes", side_effect=closes):
        assert mh.measured_bullion_mom("2026-06", "2026-07") is not None


def test_fx_is_retried_before_giving_up():
    """
    Dropping bullion on a transient timeout would silently push it back into
    the assumption — the substitution this module exists to prevent.
    """
    calls = {"n": 0}
    def flaky(*a, **k):
        calls["n"] += 1
        raise RuntimeError("timeout")
    with patch.object(mh.requests, "get", side_effect=flaky):
        assert mh._daily_fx("2026-06-01", "2026-08-06") == {}
    assert calls["n"] >= 2, "should retry rather than fail on first timeout"
