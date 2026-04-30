"""
Outlier rejection for scraped Amazon prices.

Why this exists: the matcher will occasionally pick the wrong product variant
(e.g. matching '5kg basmati rice' but Amazon's first non-sponsored result is
the 25kg bulk pack at ₹3500). One bad observation slips into the index and
contaminates every downstream chart, signal, and YoY computation.

Rule: reject any new price that's more than `threshold` (default 40%) away
from the trailing 4-week median of its own item. The first few observations
of a brand-new item bypass this check (we have no history to compare against).

Trade-off: a real price shock of >40% in one week (rare but possible — onion
crisis, oil hike) would be filtered out. We accept that as the cost of
robustness, with the understanding that a sustained shock will resume getting
through once the trailing median catches up to the new level.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone
from typing import Optional


def _trailing_median(history: list[dict], item_id: str, weeks: int = 4) -> Optional[float]:
    cutoff_str = (datetime.now(timezone.utc) - timedelta(weeks=weeks)).strftime("%Y-%m-%d %H:%M:%S")
    values = [
        h.get("price_per_kg") or h.get("price")
        for h in history
        if h.get("item_id") == item_id and (h.get("scraped_at") or "") >= cutoff_str
    ]
    values = [v for v in values if v is not None and v > 0]
    if not values:
        return None
    return statistics.median(values)


def reject_outliers(
    raw: list[dict],
    store,  # db.store.EcommStore
    platform: str,
    threshold: float = 0.40,
    min_history_points: int = 2,
) -> tuple[list[dict], list[dict]]:
    """
    Split scraped records into (kept, rejected).

    Rejection criteria: the candidate's effective price (price_per_kg if
    present, else price) deviates from the trailing 4-week median of THAT
    item's history by more than `threshold` (40% by default).

    Items with fewer than `min_history_points` historical observations are
    always kept — we can't sanity-check what we've never seen.
    """
    # Pull the broader history once
    try:
        history = []
        for ts in store.get_scrape_runs(platform, limit=30):
            history.extend(store.get_prices_at(platform, ts))
    except Exception:
        # If the store can't give us history, fail-open — keep everything.
        return raw, []

    kept: list[dict] = []
    rejected: list[dict] = []
    for record in raw:
        item_id = record.get("item_id")
        price = record.get("price_per_kg") or record.get("price")
        if not item_id or price is None or price <= 0:
            kept.append(record)
            continue

        item_history = [h for h in history if h.get("item_id") == item_id]
        if len(item_history) < min_history_points:
            kept.append(record)
            continue

        median = _trailing_median(item_history, item_id, weeks=4)
        if median is None or median <= 0:
            kept.append(record)
            continue

        deviation = abs(price - median) / median
        if deviation > threshold:
            record["_reject_reason"] = (
                f"price ₹{price:.2f} deviates {deviation*100:.0f}% from "
                f"4-week median ₹{median:.2f}"
            )
            rejected.append(record)
        else:
            kept.append(record)

    return kept, rejected
