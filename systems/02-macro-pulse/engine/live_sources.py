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


def link_relative(earlier: dict, later: dict) -> Optional[float]:
    """
    One chain link: the matched-sample geometric mean between two snapshots.

    Returns None when the two share no priceable item, which is a real
    outcome — it means that step measured nothing, not that prices held.
    """
    matched = [
        later[item] / earlier[item]
        for item in later.keys() & earlier.keys()
        if later[item] > 0 and earlier[item] > 0
    ]
    if not matched:
        return None
    return math.exp(sum(math.log(r) for r in matched) / len(matched))


def chained_relatives(snapshots: Optional[list] = None) -> dict:
    """
    Chain consecutive snapshots rather than comparing first to last.

    Why chaining is the correct construction and not a refinement:

    Comparing the newest snapshot directly against the oldest restricts the
    measurement to items present in BOTH ends. An item introduced midway
    contributes nothing, and an item that drops out late erases its own entire
    history. Over months of throttled scrapes that silently shrinks the sample
    to whatever survived from day one.

    Chaining link by link, each step uses its own matched sample. An item
    contributes to every link it spans and is dropped only from the links where
    it is genuinely missing. That is the same reasoning behind matched-sample
    chaining in the grocery index, applied across time instead of across a
    single period.

    A link that measures nothing (no shared item) is skipped rather than
    treated as 1.0 — asserting "no change" across a gap we did not observe
    would be a claim about prices rather than about our coverage.
    """
    snapshots = load_snapshots() if snapshots is None else snapshots
    if len(snapshots) < 2:
        return {}

    by_division: dict[str, float] = {}
    for earlier, later in zip(snapshots, snapshots[1:]):
        earlier_prices = earlier.get("prices") or {}
        later_prices = later.get("prices") or {}
        for division, items in later_prices.items():
            previous = earlier_prices.get(division)
            if not isinstance(items, dict) or not isinstance(previous, dict):
                continue
            link = link_relative(previous, items)
            if link is None:
                continue
            by_division[division] = by_division.get(division, 1.0) * link

    return by_division


def unmeasured_gap(anchor_month: str, snapshots: Optional[list] = None) -> Optional[str]:
    """
    Days between the anchor month ending and our first price observation.

    The anchor index describes the average of prices across its reference
    month. Our snapshots start whenever we first fetched. Everything in
    between is movement we never saw, and the live reading silently treats it
    as zero. Returning it lets the UI say so instead of implying the index is
    current to the day.
    """
    snapshots = load_snapshots() if snapshots is None else snapshots
    if not snapshots:
        return None
    try:
        year, month = (int(x) for x in anchor_month.split("-"))
        month_end = datetime(year + (month == 12), (month % 12) + 1, 1, tzinfo=timezone.utc)
        first = datetime.strptime(
            snapshots[0]["fetched_at"], "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=timezone.utc)
    except (ValueError, KeyError, TypeError):
        return None
    days = (first - month_end).days
    return f"{days} days" if days > 0 else None


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
    # Chain across every stored snapshot, not just newest-vs-first.
    relatives = chained_relatives()
    return current, relatives, first
