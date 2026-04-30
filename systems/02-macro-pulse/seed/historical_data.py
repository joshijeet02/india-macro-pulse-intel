"""Seed the DB with historical CPI and IIP data through current releases.

Two layers compose the seed:
1. Hardcoded baseline below (CPI_HISTORY, IIP_HISTORY) — frozen historical record.
2. JSON sidecar at data/release_updates.json — written by the autonomous
   refresh job (scripts/refresh_releases.py) when MOSPI publishes a new release.
   Entries here OVERRIDE the hardcoded baseline by reference_month, allowing
   forward-only growth without ever editing this file by hand.
"""
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.schema import init_db
from db.store import CPIStore, IIPStore
from engine.cpi_decomposer import decompose_cpi

RELEASE_UPDATES_PATH = Path(__file__).parent.parent / "data" / "release_updates.json"

# ---------------------------------------------------------------------------
# CPI data (MOSPI press releases, base 2012=100 unless noted)
# Format: (reference_month, release_date, headline_yoy, food_yoy, fuel_yoy, consensus)
# food_yoy / fuel_yoy = None where not available or base year changed
# ---------------------------------------------------------------------------
CPI_HISTORY = [
    # FY2024-25 (Apr 2024 – Mar 2025) ----------------------------------------
    ("2024-04", "2024-05-13",  4.83,  8.70,   3.52,  4.80),
    ("2024-05", "2024-06-12",  4.75,  8.69,   3.83,  4.70),
    ("2024-06", "2024-07-12",  5.08,  9.36,   3.55,  4.90),
    ("2024-07", "2024-08-12",  3.54,  5.42,   5.45,  3.80),
    ("2024-08", "2024-09-12",  3.65,  5.66,   5.26,  3.80),
    ("2024-09", "2024-10-14",  5.49,  9.24,   5.26,  5.20),
    ("2024-10", "2024-11-12",  6.21, 10.87,  -1.56,  5.90),
    ("2024-11", "2024-12-12",  5.48,  9.04,  -1.31,  5.50),
    ("2024-12", "2025-01-13",  5.22,  8.39,  -1.04,  5.30),
    ("2025-01", "2025-02-12",  4.26,  5.97,  -1.51,  4.60),
    ("2025-02", "2025-03-12",  3.61,  3.75,  -1.59,  4.10),
    ("2025-03", "2025-04-14",  3.34,  2.69,  -1.67,  3.70),
    # FY2025-26 (Apr 2025 – Mar 2026) ----------------------------------------
    # Apr–Dec 2025: base 2012=100, full food + fuel components confirmed
    ("2025-04", "2025-05-13",  3.16,  1.78,   2.92,  3.30),
    ("2025-05", "2025-06-12",  2.82,  0.99,   2.78,  3.10),
    ("2025-06", "2025-07-14",  2.10, -1.01,   2.55,  2.80),  # food/fuel final from Jul release
    ("2025-07", "2025-08-12",  1.61, -1.76,   2.67,  2.20),  # revised up from provisional 1.55%
    ("2025-08", "2025-09-12",  2.07, -0.64,   2.32,  2.10),  # final from Sep release
    ("2025-09", "2025-10-14",  1.44, -2.33,   1.98,  2.00),  # final from Oct release (prov 1.54%)
    ("2025-10", "2025-11-12",  0.25, -5.02,   1.98,  1.20),  # GST-cut base effect
    ("2025-11", "2025-12-12",  0.71, -3.91,   2.32,  0.80),
    ("2025-12", "2026-01-13",  1.33, -2.71,   1.97,  1.10),
    # Jan–Mar 2026: NEW BASE YEAR 2024=100 (HCES 2023-24 weights)
    # Fuel & light replaced by "Housing, water, electricity, gas and other fuels" division
    # Old 2012=100 component weights no longer apply — store food only, fuel=None
    ("2026-01", "2026-02-12",  2.75,  2.13,   None,  2.50),
    ("2026-02", "2026-03-12",  3.21,  None,   None,  3.00),
    ("2026-03", "2026-04-14",  3.40,  None,   None,  3.20),
]

# ---------------------------------------------------------------------------
# IIP data (MOSPI press releases, base 2011-12=100)
# Using final revised figures where available (Canara Bank Jan-2026 analysis
# + MOSPI Sep-2025 IIP PDF for Apr–Sep 2025 revisions)
# ---------------------------------------------------------------------------
IIP_HISTORY = [
    # FY2024-25 (Mar 2024 – Mar 2025) ----------------------------------------
    {
        "reference_month": "2024-03", "release_date": "2024-05-31",
        "headline_yoy": 4.9, "manufacturing_yoy": 5.2, "mining_yoy": 1.2, "electricity_yoy": 8.0,
        "capital_goods_yoy": -0.7, "consumer_durables_yoy": 11.9, "consumer_nondurables_yoy": 3.7,
        "infra_construction_yoy": 8.2, "primary_goods_yoy": 5.1, "intermediate_goods_yoy": 3.7,
        "consensus_forecast": 4.5,
    },
    {
        "reference_month": "2024-04", "release_date": "2024-06-28",
        "headline_yoy": 5.0, "manufacturing_yoy": 5.8, "mining_yoy": 6.7, "electricity_yoy": 0.9,
        "capital_goods_yoy": 2.3, "consumer_durables_yoy": 3.7, "consumer_nondurables_yoy": 4.4,
        "infra_construction_yoy": 6.8, "primary_goods_yoy": 6.3, "intermediate_goods_yoy": 3.9,
        "consensus_forecast": 4.8,
    },
    {
        "reference_month": "2024-05", "release_date": "2024-07-31",
        "headline_yoy": 5.9, "manufacturing_yoy": 4.6, "mining_yoy": 6.0, "electricity_yoy": 13.1,
        "capital_goods_yoy": 12.6, "consumer_durables_yoy": 4.3, "consumer_nondurables_yoy": 1.3,
        "infra_construction_yoy": 5.0, "primary_goods_yoy": 6.4, "intermediate_goods_yoy": 5.0,
        "consensus_forecast": 6.0,
    },
    {
        "reference_month": "2024-06", "release_date": "2024-08-30",
        "headline_yoy": 4.2, "manufacturing_yoy": 4.3, "mining_yoy": 7.4, "electricity_yoy": 2.7,
        "capital_goods_yoy": 1.0, "consumer_durables_yoy": 2.8, "consumer_nondurables_yoy": 4.4,
        "infra_construction_yoy": 6.0, "primary_goods_yoy": 5.9, "intermediate_goods_yoy": 2.4,
        "consensus_forecast": 4.5,
    },
    {
        "reference_month": "2024-07", "release_date": "2024-09-30",
        "headline_yoy": 4.8, "manufacturing_yoy": 4.6, "mining_yoy": 3.7, "electricity_yoy": 7.9,
        "capital_goods_yoy": 1.4, "consumer_durables_yoy": 11.7, "consumer_nondurables_yoy": 3.2,
        "infra_construction_yoy": 5.5, "primary_goods_yoy": 5.1, "intermediate_goods_yoy": 3.4,
        "consensus_forecast": 5.0,
    },
    {
        "reference_month": "2024-08", "release_date": "2024-10-31",
        "headline_yoy": 0.1, "manufacturing_yoy": 1.0, "mining_yoy": -4.3, "electricity_yoy": 0.9,
        "capital_goods_yoy": -0.6, "consumer_durables_yoy": 11.7, "consumer_nondurables_yoy": -0.2,
        "infra_construction_yoy": 1.1, "primary_goods_yoy": 0.5, "intermediate_goods_yoy": -1.6,
        "consensus_forecast": 1.0,
    },
    {
        "reference_month": "2024-09", "release_date": "2024-11-29",
        "headline_yoy": -3.5, "manufacturing_yoy": -3.7, "mining_yoy": -4.8, "electricity_yoy": -1.4,
        "capital_goods_yoy": -3.7, "consumer_durables_yoy": -6.7, "consumer_nondurables_yoy": -2.1,
        "infra_construction_yoy": -3.0, "primary_goods_yoy": -3.6, "intermediate_goods_yoy": -3.8,
        "consensus_forecast": 0.5,
    },
    {
        "reference_month": "2024-10", "release_date": "2024-12-31",
        "headline_yoy": 3.5, "manufacturing_yoy": 4.1, "mining_yoy": -0.9, "electricity_yoy": 2.1,
        "capital_goods_yoy": -1.9, "consumer_durables_yoy": 5.9, "consumer_nondurables_yoy": 5.0,
        "infra_construction_yoy": 4.6, "primary_goods_yoy": 4.2, "intermediate_goods_yoy": 2.5,
        "consensus_forecast": 3.5,
    },
    {
        "reference_month": "2024-11", "release_date": "2025-01-31",
        "headline_yoy": 5.2, "manufacturing_yoy": 5.8, "mining_yoy": 2.9, "electricity_yoy": 4.4,
        "capital_goods_yoy": 12.8, "consumer_durables_yoy": 6.3, "consumer_nondurables_yoy": 1.3,
        "infra_construction_yoy": 5.5, "primary_goods_yoy": 5.9, "intermediate_goods_yoy": 4.9,
        "consensus_forecast": 4.8,
    },
    {
        "reference_month": "2024-12", "release_date": "2025-02-28",
        "headline_yoy": 3.2, "manufacturing_yoy": 2.5, "mining_yoy": 4.1, "electricity_yoy": 6.0,
        "capital_goods_yoy": 8.2, "consumer_durables_yoy": 4.6, "consumer_nondurables_yoy": -0.4,
        "infra_construction_yoy": 5.0, "primary_goods_yoy": 4.0, "intermediate_goods_yoy": 2.3,
        "consensus_forecast": 3.8,
    },
    # Jan 2025: revised headline 5.2% (from 5.0% provisional)
    {
        "reference_month": "2025-01", "release_date": "2025-03-28",
        "headline_yoy": 5.2, "manufacturing_yoy": 5.8, "mining_yoy": 4.4, "electricity_yoy": 2.4,
        "capital_goods_yoy": 8.2, "consumer_durables_yoy": 12.1, "consumer_nondurables_yoy": 2.3,
        "infra_construction_yoy": 7.8, "primary_goods_yoy": 4.1, "intermediate_goods_yoy": 3.9,
        "consensus_forecast": 4.5,
    },
    {
        "reference_month": "2025-02", "release_date": "2025-04-30",
        "headline_yoy": 2.7, "manufacturing_yoy": 2.8, "mining_yoy": 1.6, "electricity_yoy": 3.6,
        "capital_goods_yoy": None, "consumer_durables_yoy": None, "consumer_nondurables_yoy": None,
        "infra_construction_yoy": None, "primary_goods_yoy": None, "intermediate_goods_yoy": None,
        "consensus_forecast": 3.5,
    },
    {
        "reference_month": "2025-03", "release_date": "2025-05-30",
        "headline_yoy": 3.0, "manufacturing_yoy": 3.0, "mining_yoy": 0.4, "electricity_yoy": 6.3,
        "capital_goods_yoy": None, "consumer_durables_yoy": None, "consumer_nondurables_yoy": None,
        "infra_construction_yoy": None, "primary_goods_yoy": None, "intermediate_goods_yoy": None,
        "consensus_forecast": 3.5,
    },
    # FY2025-26 (Apr 2025 – Feb 2026) ----------------------------------------
    # Sector and use-based figures: revised from MOSPI Sep-2025 IIP PDF
    {
        "reference_month": "2025-04", "release_date": "2025-05-28",
        "headline_yoy": 2.6, "manufacturing_yoy": 3.1, "mining_yoy": -0.2, "electricity_yoy": 1.7,
        "capital_goods_yoy": 20.3, "consumer_durables_yoy": 6.4, "consumer_nondurables_yoy": -1.7,
        "infra_construction_yoy": 4.0, "primary_goods_yoy": -0.4, "intermediate_goods_yoy": 4.1,
        "consensus_forecast": 2.0,
    },
    {
        "reference_month": "2025-05", "release_date": "2025-06-30",
        "headline_yoy": 1.9, "manufacturing_yoy": 3.2, "mining_yoy": -0.1, "electricity_yoy": -4.7,
        "capital_goods_yoy": 14.1, "consumer_durables_yoy": -0.7, "consumer_nondurables_yoy": -2.4,
        "infra_construction_yoy": 6.3, "primary_goods_yoy": -1.9, "intermediate_goods_yoy": 3.5,
        "consensus_forecast": 2.0,
    },
    {
        "reference_month": "2025-06", "release_date": "2025-07-28",
        "headline_yoy": 1.5, "manufacturing_yoy": 3.7, "mining_yoy": -8.7, "electricity_yoy": -1.2,
        "capital_goods_yoy": 3.0, "consumer_durables_yoy": 2.8, "consumer_nondurables_yoy": None,
        "infra_construction_yoy": None, "primary_goods_yoy": None, "intermediate_goods_yoy": None,
        "consensus_forecast": 2.0,
    },
    {
        "reference_month": "2025-07", "release_date": "2025-08-28",
        "headline_yoy": 4.3, "manufacturing_yoy": 6.0, "mining_yoy": -7.2, "electricity_yoy": 3.7,
        "capital_goods_yoy": 5.0, "consumer_durables_yoy": 7.7, "consumer_nondurables_yoy": None,
        "infra_construction_yoy": 11.9, "primary_goods_yoy": None, "intermediate_goods_yoy": 5.8,
        "consensus_forecast": 4.0,
    },
    {
        "reference_month": "2025-08", "release_date": "2025-09-29",
        "headline_yoy": 4.1, "manufacturing_yoy": 3.8, "mining_yoy": 6.6, "electricity_yoy": 4.1,
        "capital_goods_yoy": 4.4, "consumer_durables_yoy": 3.5, "consumer_nondurables_yoy": -6.3,
        "infra_construction_yoy": 10.6, "primary_goods_yoy": 5.2, "intermediate_goods_yoy": 5.0,
        "consensus_forecast": 3.5,
    },
    {
        "reference_month": "2025-09", "release_date": "2025-10-28",
        "headline_yoy": 4.0, "manufacturing_yoy": 4.8, "mining_yoy": -0.4, "electricity_yoy": 3.1,
        "capital_goods_yoy": 4.7, "consumer_durables_yoy": 10.2, "consumer_nondurables_yoy": -2.9,
        "infra_construction_yoy": 10.5, "primary_goods_yoy": 1.4, "intermediate_goods_yoy": 5.3,
        "consensus_forecast": 4.0,
    },
    {
        "reference_month": "2025-10", "release_date": "2025-11-28",
        "headline_yoy": 0.4, "manufacturing_yoy": 1.8, "mining_yoy": -1.8, "electricity_yoy": -6.9,
        "capital_goods_yoy": 2.4, "consumer_durables_yoy": -0.5, "consumer_nondurables_yoy": -4.4,
        "infra_construction_yoy": 7.1, "primary_goods_yoy": -0.6, "intermediate_goods_yoy": 0.9,
        "consensus_forecast": 2.0,
    },
    {
        "reference_month": "2025-11", "release_date": "2025-12-29",
        "headline_yoy": 7.2, "manufacturing_yoy": 8.5, "mining_yoy": 5.8, "electricity_yoy": -1.5,
        "capital_goods_yoy": None, "consumer_durables_yoy": None, "consumer_nondurables_yoy": None,
        "infra_construction_yoy": None, "primary_goods_yoy": None, "intermediate_goods_yoy": None,
        "consensus_forecast": 5.5,
    },
    {
        "reference_month": "2025-12", "release_date": "2026-01-28",
        "headline_yoy": 7.8, "manufacturing_yoy": 8.1, "mining_yoy": 6.8, "electricity_yoy": 6.3,
        "capital_goods_yoy": 8.1, "consumer_durables_yoy": 12.3, "consumer_nondurables_yoy": 8.3,
        "infra_construction_yoy": 12.1, "primary_goods_yoy": 4.4, "intermediate_goods_yoy": 7.5,
        "consensus_forecast": 7.0,
    },
    {
        "reference_month": "2026-01", "release_date": "2026-02-28",
        "headline_yoy": 5.1, "manufacturing_yoy": None, "mining_yoy": None, "electricity_yoy": None,
        "capital_goods_yoy": None, "consumer_durables_yoy": None, "consumer_nondurables_yoy": None,
        "infra_construction_yoy": None, "primary_goods_yoy": None, "intermediate_goods_yoy": None,
        "consensus_forecast": 5.0,
    },
    {
        "reference_month": "2026-02", "release_date": "2026-03-30",
        "headline_yoy": 5.2, "manufacturing_yoy": None, "mining_yoy": None, "electricity_yoy": None,
        "capital_goods_yoy": 12.5, "consumer_durables_yoy": 7.3, "consumer_nondurables_yoy": -0.6,
        "infra_construction_yoy": 11.2, "primary_goods_yoy": None, "intermediate_goods_yoy": None,
        "consensus_forecast": 5.0,
    },
]


def _load_release_updates() -> dict:
    """Load the autonomously-updated release JSON if present; tolerate missing/invalid."""
    if not RELEASE_UPDATES_PATH.exists():
        return {"cpi": [], "iip": []}
    try:
        data = json.loads(RELEASE_UPDATES_PATH.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[seed] WARN: could not read {RELEASE_UPDATES_PATH}: {exc} — using baseline only")
        return {"cpi": [], "iip": []}
    return {"cpi": data.get("cpi", []) or [], "iip": data.get("iip", []) or []}


def _merged_cpi_history() -> list[tuple]:
    """Baseline tuples + JSON updates, deduped by reference_month (JSON wins)."""
    baseline = {row[0]: row for row in CPI_HISTORY}
    for entry in _load_release_updates()["cpi"]:
        rm = entry.get("reference_month")
        if not rm:
            continue
        baseline[rm] = (
            rm,
            entry.get("release_date"),
            entry.get("headline_yoy"),
            entry.get("food_yoy"),
            entry.get("fuel_yoy"),
            entry.get("consensus_forecast"),
        )
    return sorted(baseline.values(), key=lambda r: r[0])


def _merged_iip_history() -> list[dict]:
    baseline = {row["reference_month"]: row for row in IIP_HISTORY}
    for entry in _load_release_updates()["iip"]:
        rm = entry.get("reference_month")
        if not rm:
            continue
        # Carry over any baseline values for keys missing in the update,
        # so partial scrapes never erase richer hardcoded data.
        merged = {**baseline.get(rm, {}), **entry}
        merged["reference_month"] = rm
        baseline[rm] = merged
    return sorted(baseline.values(), key=lambda r: r["reference_month"])


def seed():
    init_db()
    cpi_store = CPIStore()
    iip_store = IIPStore()

    cpi_records = _merged_cpi_history()
    iip_records = _merged_iip_history()

    print(f"Seeding CPI data ({len(cpi_records)} records)...")
    for row in cpi_records:
        ref_month, rel_date, headline, food, fuel, consensus = row
        if headline is None:
            print(f"  SKIP CPI {ref_month}: missing headline_yoy")
            continue
        if food is not None and fuel is not None:
            dec = decompose_cpi(headline=headline, food_yoy=food, fuel_yoy=fuel)
            core_yoy     = dec["core_yoy"]
            food_contrib = dec["food_contrib"]
            fuel_contrib = dec["fuel_contrib"]
            core_contrib = dec["core_contrib"]
        else:
            core_yoy = food_contrib = fuel_contrib = core_contrib = None

        cpi_store.upsert({
            "release_date":       rel_date,
            "reference_month":    ref_month,
            "headline_yoy":       headline,
            "food_yoy":           food,
            "fuel_yoy":           fuel,
            "core_yoy":           core_yoy,
            "food_contrib":       food_contrib,
            "fuel_contrib":       fuel_contrib,
            "core_contrib":       core_contrib,
            "consensus_forecast": consensus,
        })
        core_str = f"core={core_yoy}%" if core_yoy is not None else "no components"
        print(f"  CPI {ref_month}: {headline}% ({core_str})")

    print(f"\nSeeding IIP data ({len(iip_records)} records)...")
    for record in iip_records:
        if record.get("headline_yoy") is None:
            print(f"  SKIP IIP {record.get('reference_month')}: missing headline_yoy")
            continue
        iip_store.upsert({
            "release_date":             record["release_date"],
            "reference_month":          record["reference_month"],
            "headline_yoy":             record["headline_yoy"],
            "manufacturing_yoy":        record.get("manufacturing_yoy"),
            "mining_yoy":               record.get("mining_yoy"),
            "electricity_yoy":          record.get("electricity_yoy"),
            "capital_goods_yoy":        record.get("capital_goods_yoy"),
            "consumer_durables_yoy":    record.get("consumer_durables_yoy"),
            "consumer_nondurables_yoy": record.get("consumer_nondurables_yoy"),
            "infra_construction_yoy":   record.get("infra_construction_yoy"),
            "primary_goods_yoy":        record.get("primary_goods_yoy"),
            "intermediate_goods_yoy":   record.get("intermediate_goods_yoy"),
            "consensus_forecast":       record.get("consensus_forecast"),
        })
        print(f"  IIP {record['reference_month']}: {record['headline_yoy']}%")

    print(f"\nSeed complete. CPI records: {cpi_store.count()}")


if __name__ == "__main__":
    seed()
