"""
Autonomously check MOSPI for newer CPI / IIP releases and append them to
data/release_updates.json.

Designed to be invoked by .github/workflows/refresh-data.yml on a daily cron.

Exit codes:
    0 → at least one new release was added (workflow should commit + push)
    1 → no new releases (workflow should do nothing)
    2 → parser failure or unexpected error (workflow should open an issue)

Usage:
    python scripts/refresh_releases.py                # live scrape
    python scripts/refresh_releases.py --use-fixture  # use bundled test fixtures
    python scripts/refresh_releases.py --cpi-only
    python scripts/refresh_releases.py --iip-only
    python scripts/refresh_releases.py --dry-run      # don't write JSON
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Allow running from anywhere — make systems/02-macro-pulse importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scrapers.mospi_cpi import fetch_latest_cpi  # noqa: E402
from scrapers.mospi_iip import fetch_latest_iip  # noqa: E402
from seed.historical_data import CPI_HISTORY, IIP_HISTORY  # noqa: E402

UPDATES_PATH = ROOT / "data" / "release_updates.json"

# CLI exit codes
EXIT_NEW = 0
EXIT_NOCHANGE = 1
EXIT_FAIL = 2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("refresh_releases")


def _load_updates() -> dict:
    if UPDATES_PATH.exists():
        try:
            data = json.loads(UPDATES_PATH.read_text())
        except json.JSONDecodeError as exc:
            log.error(f"Cannot parse {UPDATES_PATH}: {exc}")
            return {"_comment": "", "cpi": [], "iip": []}
        data.setdefault("cpi", [])
        data.setdefault("iip", [])
        return data
    return {
        "_comment": (
            "Autonomous additions. See seed/historical_data.py for details. "
            "Newer reference_months override hardcoded baseline."
        ),
        "cpi": [],
        "iip": [],
    }


def _save_updates(data: dict) -> None:
    UPDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPDATES_PATH.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")


def _existing_latest(indicator: str, updates: dict) -> Optional[str]:
    """Return the highest reference_month across baseline + JSON updates."""
    baseline = (
        [row[0] for row in CPI_HISTORY] if indicator == "cpi"
        else [row["reference_month"] for row in IIP_HISTORY]
    )
    json_months = [e["reference_month"] for e in updates.get(indicator, []) if e.get("reference_month")]
    all_months = baseline + json_months
    return max(all_months) if all_months else None


def _is_newer(candidate: str, existing_latest: Optional[str]) -> bool:
    if existing_latest is None:
        return True
    return candidate > existing_latest


def _normalize_cpi(payload: dict) -> dict:
    """Pick only the fields we persist for CPI."""
    return {
        "reference_month":    payload["reference_month"],
        "release_date":       payload.get("release_date") or datetime.now().date().isoformat(),
        "headline_yoy":       payload.get("headline_yoy"),
        "food_yoy":           payload.get("food_yoy"),
        "fuel_yoy":           payload.get("fuel_yoy"),
        "consensus_forecast": payload.get("consensus_forecast"),  # rare for live scrapes
        "source":             payload.get("source", ""),
    }


def _normalize_iip(payload: dict) -> dict:
    keep = (
        "reference_month", "release_date", "headline_yoy",
        "manufacturing_yoy", "mining_yoy", "electricity_yoy",
        "capital_goods_yoy", "consumer_durables_yoy", "consumer_nondurables_yoy",
        "infra_construction_yoy", "primary_goods_yoy", "intermediate_goods_yoy",
        "consensus_forecast", "source",
    )
    out = {k: payload.get(k) for k in keep}
    out["release_date"] = out["release_date"] or datetime.now().date().isoformat()
    return out


def refresh_cpi(updates: dict, use_fixture: bool) -> tuple[bool, Optional[str]]:
    """Returns (added, error). added=True iff a new entry was appended."""
    payload = fetch_latest_cpi(use_fixture=use_fixture)
    if payload is None:
        return False, "fetch_latest_cpi returned None (parser failure)"

    candidate_month = payload.get("reference_month")
    if not candidate_month:
        return False, "no reference_month in payload"

    existing_latest = _existing_latest("cpi", updates)
    if not _is_newer(candidate_month, existing_latest):
        log.info(f"CPI: latest={existing_latest}, scraped={candidate_month} → no change")
        return False, None

    record = _normalize_cpi(payload)
    updates["cpi"].append(record)
    log.info(f"CPI: ADDED {candidate_month} (headline={record['headline_yoy']}%)")
    return True, None


def refresh_iip(updates: dict, use_fixture: bool) -> tuple[bool, Optional[str]]:
    payload = fetch_latest_iip(use_fixture=use_fixture)
    if payload is None:
        return False, "fetch_latest_iip returned None (parser failure)"

    candidate_month = payload.get("reference_month")
    if not candidate_month:
        return False, "no reference_month in payload"

    existing_latest = _existing_latest("iip", updates)
    if not _is_newer(candidate_month, existing_latest):
        log.info(f"IIP: latest={existing_latest}, scraped={candidate_month} → no change")
        return False, None

    record = _normalize_iip(payload)
    updates["iip"].append(record)
    log.info(f"IIP: ADDED {candidate_month} (headline={record['headline_yoy']}%)")
    return True, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--use-fixture", action="store_true",
                        help="Use bundled test fixtures instead of live scraping")
    parser.add_argument("--cpi-only", action="store_true")
    parser.add_argument("--iip-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true",
                        help="Detect newer releases but don't write JSON")
    args = parser.parse_args()

    if args.cpi_only and args.iip_only:
        parser.error("--cpi-only and --iip-only are mutually exclusive")

    updates = _load_updates()
    any_added = False
    any_failed = False

    if not args.iip_only:
        added, err = refresh_cpi(updates, args.use_fixture)
        any_added |= added
        if err:
            log.error(f"CPI failure: {err}")
            any_failed = True

    if not args.cpi_only:
        added, err = refresh_iip(updates, args.use_fixture)
        any_added |= added
        if err:
            log.error(f"IIP failure: {err}")
            any_failed = True

    if any_added and not args.dry_run:
        _save_updates(updates)
        log.info(f"Wrote {UPDATES_PATH}")

    if any_failed:
        # Treat as failure only if NOTHING new came through. A successful
        # CPI add is still a win even if IIP failed in the same run.
        if not any_added:
            return EXIT_FAIL
    return EXIT_NEW if any_added else EXIT_NOCHANGE


if __name__ == "__main__":
    sys.exit(main())
