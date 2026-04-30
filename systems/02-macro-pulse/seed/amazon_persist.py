"""
Persisted Amazon basket data.

Streamlit Cloud has an ephemeral filesystem — the SQLite ecomm_prices table
gets wiped on every container restart. Without a persisted source, the index
chart resets to empty after each redeploy.

This module bridges that gap by storing every successful scrape in a JSON
sidecar (`data/amazon_prices.json`) that IS committed to git via the weekly
GitHub Action. On app boot, if the SQLite table is empty, we hydrate it from
JSON. The result is a real long-running price index that grows organically.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

PRICES_PATH = Path(__file__).parent.parent / "data" / "amazon_prices.json"

log = logging.getLogger(__name__)


def load_persisted_prices() -> list[dict]:
    """Return all persisted Amazon price observations, oldest first."""
    if not PRICES_PATH.exists():
        return []
    try:
        data = json.loads(PRICES_PATH.read_text())
    except json.JSONDecodeError as exc:
        log.warning(f"Cannot parse {PRICES_PATH}: {exc}")
        return []
    records = data.get("observations", []) if isinstance(data, dict) else []
    # Defensive: each record must have the seven required fields
    keep = ("platform", "item_id", "cpi_group", "item_name", "price",
            "unit", "scraped_at")
    return [
        r for r in records
        if all(k in r for k in keep)
    ]


def append_observations(observations: Iterable[dict]) -> int:
    """Append new observations to the persisted file. Returns count added."""
    PRICES_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = load_persisted_prices()
    seen = {(r["item_id"], r["scraped_at"]) for r in existing}
    added: list[dict] = []
    for obs in observations:
        key = (obs.get("item_id"), obs.get("scraped_at"))
        if not all(key) or key in seen:
            continue
        added.append(obs)
        seen.add(key)

    if not added:
        return 0

    payload = {
        "_comment": (
            "Amazon basket scrape history. Appended by the weekly GH Action; "
            "hydrated into SQLite on app boot. Hand-edits are tolerated but "
            "not recommended — they may collide with the next automated run."
        ),
        "observations": existing + added,
    }
    PRICES_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    return len(added)


def hydrate_db_from_json() -> int:
    """If the SQLite ecomm_prices table is empty, load from JSON. Returns rows added."""
    from db.store import EcommStore
    store = EcommStore()
    if store.has_data():
        return 0
    persisted = load_persisted_prices()
    if not persisted:
        return 0
    store.insert_prices_bulk(persisted)
    log.info(f"Hydrated {len(persisted)} Amazon price observations from JSON")
    return len(persisted)
