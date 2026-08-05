"""
Price fetchers, and the snapshots they are measured against.

Each fetcher returns current prices for one CPI division. To turn prices into
an index move we need a reference: the prices that prevailed when MOSPI last
published. So every fetch is stored, and the relative is
current / earliest-stored.

That means the FIRST fetch measures nothing — it establishes the reference and
the live index equals the official anchor. Every fetch after it reports real,
observed movement. This is stated plainly rather than papered over, because a
reading of "no change" on day one is a property of the method, not a finding
about prices.

Snapshots live in data/live_snapshots.json, the same repo-as-database pattern
the rest of the system uses, so the reference survives Streamlit restarts.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger(__name__)

SNAPSHOT_PATH = Path(__file__).parent.parent / "data" / "live_snapshots.json"

# A fetcher returns {division_key: representative_price} or {} on failure.
Fetcher = Callable[[], dict]


def fetch_bullion_prices() -> dict:
    """
    Gold and silver -> personal_care_and_misc.

    That division carried 5% of the basket but 35% of January's headline
    inflation, because jewellery sits inside it. Bullion is priced live and
    free, so this is the cheapest accurate signal in the whole index.

    Gold and silver are combined by their rough share of Indian jewellery
    demand rather than equally — silver is the smaller share by value.
    """
    from scrapers.metals import fetch_bullion

    prices = {m["symbol"]: m["inr_per_gram"] for m in fetch_bullion()}
    gold, silver = prices.get("XAU"), prices.get("XAG")
    if gold is None:
        return {}
    blended = 0.85 * gold + 0.15 * silver if silver is not None else gold
    return {"personal_care_and_misc": round(blended, 4)}


FETCHERS: dict[str, Fetcher] = {
    "bullion": fetch_bullion_prices,
}


# ─── Snapshot store ──────────────────────────────────────────────────────────

def load_snapshots() -> list[dict]:
    if not SNAPSHOT_PATH.exists():
        return []
    try:
        payload = json.loads(SNAPSHOT_PATH.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning(f"live_sources: cannot read snapshots: {exc}")
        return []
    snapshots = payload.get("snapshots", []) if isinstance(payload, dict) else []
    return [s for s in snapshots if isinstance(s, dict) and s.get("prices")]


def save_snapshot(prices: dict) -> dict:
    """Append one snapshot. Atomic write so a crash cannot corrupt the reference."""
    snapshot = {
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "prices": prices,
    }
    existing = load_snapshots()
    payload = {
        "_comment": (
            "Live price snapshots. The earliest snapshot per division is the "
            "reference the live index is measured against; it is never "
            "overwritten, because moving the reference would silently rewrite "
            "history."
        ),
        "snapshots": existing + [snapshot],
    }
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SNAPSHOT_PATH.with_suffix(SNAPSHOT_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    tmp.replace(SNAPSHOT_PATH)
    return snapshot


def reference_prices() -> dict:
    """
    Earliest recorded price per division — the denominator of every relative.

    Taken per division rather than per snapshot, so a division added later
    still gets its own first observation as its reference instead of being
    excluded for having no price in the very first snapshot.
    """
    reference: dict[str, float] = {}
    for snapshot in load_snapshots():          # oldest first
        for key, price in snapshot["prices"].items():
            if key not in reference and isinstance(price, (int, float)) and price > 0:
                reference[key] = float(price)
    return reference


def compute_relatives(current: dict, reference: Optional[dict] = None) -> dict:
    """current / reference per division, skipping anything unmeasurable."""
    reference = reference_prices() if reference is None else reference
    out = {}
    for key, price in current.items():
        base = reference.get(key)
        if base and isinstance(price, (int, float)) and price > 0:
            out[key] = price / base
    return out


def fetch_all() -> dict:
    """Run every fetcher. A failing source is skipped, never fatal."""
    prices: dict[str, float] = {}
    for name, fetcher in FETCHERS.items():
        try:
            prices.update(fetcher() or {})
        except Exception as exc:
            log.warning(f"live_sources: fetcher '{name}' failed: {exc}")
    return prices


def fetch_and_measure() -> tuple[dict, dict, bool]:
    """
    Fetch, store, and return (current_prices, relatives, is_first_fetch).

    `is_first_fetch` tells the caller the reading is a reference, not a
    measurement — the difference between "prices have not moved" and "we have
    nothing to compare against yet".
    """
    reference_before = reference_prices()
    current = fetch_all()
    if not current:
        return {}, {}, not reference_before

    save_snapshot(current)
    first = not reference_before
    relatives = compute_relatives(current, reference_before or current)
    return current, relatives, first
