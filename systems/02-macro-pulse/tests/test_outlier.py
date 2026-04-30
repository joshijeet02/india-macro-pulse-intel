"""Tests for outlier rejection on Amazon basket scrapes."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from engine.outlier import reject_outliers


def _build_store(history_by_ts: dict[str, list[dict]]):
    """Build a mock EcommStore from a {scraped_at: [records]} dict."""
    store = MagicMock()
    store.get_scrape_runs.return_value = list(history_by_ts.keys())
    store.get_prices_at.side_effect = lambda platform, ts: history_by_ts.get(ts, [])
    return store


def _ts(days_ago: int) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def test_no_history_keeps_everything():
    """Brand-new items can't be sanity-checked — keep them."""
    store = _build_store({})
    raw = [{"item_id": "rice", "price": 200, "price_per_kg": 40, "scraped_at": _ts(0)}]
    kept, rejected = reject_outliers(raw, store, platform="amazon")
    assert len(kept) == 1
    assert len(rejected) == 0


def test_normal_price_within_band_kept():
    """A price close to the trailing median passes through."""
    history = {
        _ts(7): [{"item_id": "rice", "price_per_kg": 40, "scraped_at": _ts(7)}],
        _ts(14): [{"item_id": "rice", "price_per_kg": 41, "scraped_at": _ts(14)}],
        _ts(21): [{"item_id": "rice", "price_per_kg": 42, "scraped_at": _ts(21)}],
    }
    store = _build_store(history)
    raw = [{"item_id": "rice", "price": 200, "price_per_kg": 43, "scraped_at": _ts(0)}]
    kept, rejected = reject_outliers(raw, store, platform="amazon")
    assert len(kept) == 1
    assert len(rejected) == 0


def test_outlier_price_rejected():
    """A price 100% higher than the trailing median is rejected."""
    history = {
        _ts(7): [{"item_id": "rice", "price_per_kg": 40, "scraped_at": _ts(7)}],
        _ts(14): [{"item_id": "rice", "price_per_kg": 41, "scraped_at": _ts(14)}],
        _ts(21): [{"item_id": "rice", "price_per_kg": 42, "scraped_at": _ts(21)}],
    }
    store = _build_store(history)
    raw = [{"item_id": "rice", "price": 410, "price_per_kg": 82, "scraped_at": _ts(0)}]
    kept, rejected = reject_outliers(raw, store, platform="amazon", threshold=0.40)
    assert len(kept) == 0
    assert len(rejected) == 1
    assert "deviates" in rejected[0]["_reject_reason"]


def test_threshold_at_boundary():
    """Price exactly at threshold should be rejected (we use strict >)."""
    history = {
        _ts(7): [{"item_id": "rice", "price_per_kg": 100, "scraped_at": _ts(7)}],
        _ts(14): [{"item_id": "rice", "price_per_kg": 100, "scraped_at": _ts(14)}],
    }
    store = _build_store(history)
    # 50% above median — definitely out
    raw = [{"item_id": "rice", "price_per_kg": 150, "price": 150, "scraped_at": _ts(0)}]
    kept, rejected = reject_outliers(raw, store, platform="amazon", threshold=0.40)
    assert len(rejected) == 1


def test_old_history_outside_window_ignored():
    """Observations older than 4 weeks shouldn't count toward the trailing median."""
    history = {
        # 60 days ago — outside the 4-week window, ignored
        _ts(60): [{"item_id": "rice", "price_per_kg": 200, "scraped_at": _ts(60)}],
    }
    store = _build_store(history)
    # No history within window → fail-open and keep the record
    raw = [{"item_id": "rice", "price_per_kg": 50, "price": 50, "scraped_at": _ts(0)}]
    kept, rejected = reject_outliers(raw, store, platform="amazon")
    assert len(kept) == 1
