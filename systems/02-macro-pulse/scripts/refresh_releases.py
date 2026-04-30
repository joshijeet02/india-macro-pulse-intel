"""
Autonomously check MOSPI for newer CPI / IIP releases and append them to
data/release_updates.json.

Designed to be invoked by .github/workflows/refresh-data.yml on a daily cron.

Exit codes:
    0 → at least one new release was added (workflow should commit + push)
    1 → no new releases (workflow should do nothing)
    2 → parser failure with NO successful additions (open issue, don't commit)
    3 → partial success: at least one new release added AND at least one
        parser failed. Workflow should commit AND open an issue.

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

from scrapers._mospi_api import fetch_latest_releases, find_latest_release  # noqa: E402
from scrapers.mospi_cpi import fetch_latest_cpi  # noqa: E402
from scrapers.mospi_iip import fetch_latest_iip  # noqa: E402
from seed.historical_data import CPI_HISTORY, IIP_HISTORY  # noqa: E402

UPDATES_PATH = ROOT / "data" / "release_updates.json"

# CLI exit codes
EXIT_NEW = 0
EXIT_NOCHANGE = 1
EXIT_FAIL = 2
EXIT_PARTIAL = 3   # at least one indicator added AND at least one failed

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
    """Atomic write: temp file + rename, so a crash mid-write can't corrupt the JSON."""
    UPDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = UPDATES_PATH.with_suffix(UPDATES_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n")
    tmp.replace(UPDATES_PATH)


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


def _refresh_indicator(
    updates: dict,
    indicator: str,            # "CPI" or "IIP"
    fetch_fn,                  # fetch_latest_cpi / fetch_latest_iip
    normalize_fn,              # _normalize_cpi / _normalize_iip
    use_fixture: bool,
    api_releases: Optional[list[dict]] = None,
) -> tuple[bool, Optional[str]]:
    """
    Shared driver that distinguishes "no candidate in API window" (not a
    failure — common case) from "parser broke on a found PDF" (real failure
    that should surface as a GitHub issue).

    Returns (added, error_reason). error_reason is None on success or
    no-candidate; non-None only on actual parser/network failure.
    """
    key = indicator.lower()

    if not use_fixture and api_releases is not None:
        # Cheap check: if no candidate matches in the API window, skip the
        # full scrape and don't treat it as a failure.
        if find_latest_release(api_releases, indicator) is None:
            log.info(f"{indicator}: no candidate in MOSPI API window — nothing to refresh")
            return False, None

    payload = fetch_fn(use_fixture=use_fixture)
    if payload is None:
        return False, f"fetch_latest_{key} returned None (parser failure)"

    candidate_month = payload.get("reference_month")
    if not candidate_month:
        return False, f"{indicator}: payload missing reference_month"

    existing_latest = _existing_latest(key, updates)
    if not _is_newer(candidate_month, existing_latest):
        log.info(f"{indicator}: latest={existing_latest}, scraped={candidate_month} → no change")
        return False, None

    record = normalize_fn(payload)
    updates[key].append(record)
    log.info(f"{indicator}: ADDED {candidate_month} (headline={record['headline_yoy']}%)")
    return True, None


def refresh_cpi(updates: dict, use_fixture: bool, api_releases=None) -> tuple[bool, Optional[str]]:
    return _refresh_indicator(updates, "CPI", fetch_latest_cpi, _normalize_cpi,
                              use_fixture, api_releases)


def refresh_iip(updates: dict, use_fixture: bool, api_releases=None) -> tuple[bool, Optional[str]]:
    return _refresh_indicator(updates, "IIP", fetch_latest_iip, _normalize_iip,
                              use_fixture, api_releases)


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

    # Single API hit shared by both indicators (reduces load on MOSPI server
    # and avoids two-shot inconsistency when releases roll out of the window
    # between calls).
    api_releases = None if args.use_fixture else fetch_latest_releases()

    any_added = False
    any_failed = False

    if not args.iip_only:
        added, err = refresh_cpi(updates, args.use_fixture, api_releases)
        any_added |= added
        if err:
            log.error(f"CPI failure: {err}")
            any_failed = True

    if not args.cpi_only:
        added, err = refresh_iip(updates, args.use_fixture, api_releases)
        any_added |= added
        if err:
            log.error(f"IIP failure: {err}")
            any_failed = True

    if any_added and not args.dry_run:
        _save_updates(updates)
        log.info(f"Wrote {UPDATES_PATH}")

    # Exit code precedence: partial > pure-fail > new > nochange
    if any_added and any_failed:
        return EXIT_PARTIAL
    if any_failed:
        return EXIT_FAIL
    return EXIT_NEW if any_added else EXIT_NOCHANGE


if __name__ == "__main__":
    sys.exit(main())
