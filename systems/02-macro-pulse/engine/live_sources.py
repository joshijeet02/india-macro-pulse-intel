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
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger(__name__)

SNAPSHOT_PATH = Path(__file__).parent.parent / "data" / "live_snapshots.json"

# A fetcher returns {division_key: {item_id: price}} or {} on failure.
#
# Item-level rather than one number per division, so the relative can be
# computed over items present in BOTH periods. Collapsing to a single average
# at fetch time would let a changed item set move the relative for composition
# reasons — a scrape that loses half the basket to throttling would read as a
# price move. That is the same defect matched-sample chaining fixes in the
# grocery index, and it must not be reintroduced here.
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
    if "XAU" not in prices:
        return {}
    items = {"gold_per_gram": prices["XAU"]}
    if "XAG" in prices:
        items["silver_per_gram"] = prices["XAG"]
    return {"personal_care_and_misc": items}


def fetch_grocery_prices() -> dict:
    """
    The 20-item grocery basket -> food_and_beverages, priced per item.

    Per-item rather than pre-averaged so the relative can be taken over items
    present in both periods. Amazon throttles, so item sets genuinely differ
    between fetches; averaging first would turn that into a phantom price move.
    """
    from engine.ecomm_basket import BASKET_BY_ID
    from scrapers.amazon import scrape_amazon
    from engine.ecomm_basket import BASKET

    observations = scrape_amazon(BASKET)
    if not observations:
        return {}

    items: dict[str, float] = {}
    for row in observations:
        if row["item_id"] not in BASKET_BY_ID:
            continue
        price = row.get("price_per_kg") or row.get("price")
        if price and price > 0:
            items[row["item_id"]] = float(price)
    return {"food_and_beverages": items} if items else {}


def fetch_fuel_prices() -> dict:
    """
    Retail petrol and diesel -> transport.

    Pump prices are revised daily by the oil marketing companies and are the
    cleanest high-frequency series in the whole index. They are also the main
    channel through which a crude shock reaches CPI.

    Not yet wired to a live source: the OMC pages are JS-rendered and
    data.gov.in's fuel resource needs an API key. Returning {} keeps transport
    honestly marked as carried rather than silently assumed flat under a
    fabricated price.
    """
    return {}


FETCHERS: dict[str, Fetcher] = {
    "bullion": fetch_bullion_prices,
    "grocery": fetch_grocery_prices,
    "fuel": fetch_fuel_prices,
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
    Earliest recorded price per ITEM, grouped by division.

    Per item, not per division or per snapshot: an item first seen in the third
    fetch uses that fetch as its own reference, rather than being excluded for
    having missed the first one. Never overwritten — moving a reference would
    silently rewrite every reading that came before.
    """
    reference: dict[str, dict[str, float]] = {}
    for snapshot in load_snapshots():          # oldest first
        for division, items in snapshot["prices"].items():
            if not isinstance(items, dict):
                continue
            bucket = reference.setdefault(division, {})
            for item_id, price in items.items():
                if item_id not in bucket and isinstance(price, (int, float)) and price > 0:
                    bucket[item_id] = float(price)
    return reference


def compute_relatives(current: dict, reference: Optional[dict] = None) -> dict:
    """
    One price relative per division, over a MATCHED SAMPLE of items.

    Only items priced in both the reference and this fetch contribute, and
    they are combined as a geometric mean of their individual ratios — the
    Jevons elementary form MOSPI uses.

    The matched sample is the point. Amazon throttles, so item sets genuinely
    differ between fetches. Averaging prices first and dividing the averages
    would let a lost item move the relative, reporting a composition change as
    a price change.
    """
    reference = reference_prices() if reference is None else reference
    out: dict[str, float] = {}

    for division, items in current.items():
        if not isinstance(items, dict):
            continue
        base_items = reference.get(division) or {}
        matched = [
            items[item_id] / base_items[item_id]
            for item_id in items.keys() & base_items.keys()
            if items[item_id] > 0 and base_items[item_id] > 0
        ]
        if not matched:
            continue
        log_sum = sum(math.log(r) for r in matched)
        out[division] = math.exp(log_sum / len(matched))

    return out


def fetch_all() -> dict:
    """Run every fetcher. A failing source is skipped, never fatal."""
    prices: dict[str, dict] = {}
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
