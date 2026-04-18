"""Seed the DB with 12 months of historical CPI and IIP data."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.schema import init_db
from db.store import CPIStore, IIPStore
from engine.cpi_decomposer import decompose_cpi

# CPI data: Apr 2024 – Mar 2025 (from MOSPI actual releases)
# Format: (reference_month, release_date, headline_yoy, food_yoy, fuel_yoy, consensus)
CPI_HISTORY = [
    ("2024-04", "2024-05-13", 4.83,  8.70,   3.52,  4.80),
    ("2024-05", "2024-06-12", 4.75,  8.69,   3.83,  4.70),
    ("2024-06", "2024-07-12", 5.08,  9.36,   3.55,  4.90),
    ("2024-07", "2024-08-12", 3.54,  5.42,   5.45,  3.80),
    ("2024-08", "2024-09-12", 3.65,  5.66,   5.26,  3.80),
    ("2024-09", "2024-10-14", 5.49,  9.24,   5.26,  5.20),
    ("2024-10", "2024-11-12", 6.21, 10.87,  -1.56,  5.90),
    ("2024-11", "2024-12-12", 5.48,  9.04,  -1.31,  5.50),
    ("2024-12", "2025-01-13", 5.22,  8.39,  -1.04,  5.30),
    ("2025-01", "2025-02-12", 4.26,  6.00,  -1.51,  4.60),
    ("2025-02", "2025-03-12", 3.61,  3.75,  -1.59,  4.10),
    ("2025-03", "2025-04-14", 3.34,  2.69,  -1.67,  3.70),
]

# IIP data: Mar 2024 – Jan 2025 (from MOSPI actual releases)
# Format: (reference_month, release_date, headline, mfg, mining, elec,
#          cap_goods, cons_durable, cons_nondur, infra, primary, intermediate, consensus)
IIP_HISTORY = [
    ("2024-03", "2024-05-31", 4.9,  5.2,  1.2,  8.0, -0.7, 11.9, 3.7,  8.2,  5.1,  3.7,  4.5),
    ("2024-04", "2024-06-28", 5.0,  5.8,  6.7,  0.9,  2.3,  3.7,  4.4,  6.8,  6.3,  3.9,  4.8),
    ("2024-05", "2024-07-31", 5.9,  4.6,  6.0, 13.1, 12.6,  4.3,  1.3,  5.0,  6.4,  5.0,  6.0),
    ("2024-06", "2024-08-30", 4.2,  4.3,  7.4,  2.7,  1.0,  2.8,  4.4,  6.0,  5.9,  2.4,  4.5),
    ("2024-07", "2024-09-30", 4.8,  4.6,  3.7,  7.9,  1.4, 11.7,  3.2,  5.5,  5.1,  3.4,  5.0),
    ("2024-08", "2024-10-31", 0.1,  1.0, -4.3,  0.9, -0.6, 11.7, -0.2,  1.1,  0.5, -1.6,  1.0),
    ("2024-09", "2024-11-29",-3.5, -3.7, -4.8, -1.4, -3.7, -6.7, -2.1, -3.0, -3.6, -3.8,  0.5),
    ("2024-10", "2024-12-31", 3.5,  4.1, -0.9,  2.1, -1.9,  5.9,  5.0,  4.6,  4.2,  2.5,  3.5),
    ("2024-11", "2025-01-31", 5.2,  5.8,  2.9,  4.4, 12.8,  6.3,  1.3,  5.5,  5.9,  4.9,  4.8),
    ("2024-12", "2025-02-28", 3.2,  2.5,  4.1,  6.0,  8.2,  4.6, -0.4,  5.0,  4.0,  2.3,  3.8),
    ("2025-01", "2025-03-28", 5.0,  5.5,  4.4,  5.3,  8.2, 12.1,  2.3,  7.8,  4.1,  3.9,  4.5),
]


def seed():
    init_db()
    cpi_store = CPIStore()
    iip_store = IIPStore()

    print("Seeding CPI data...")
    for row in CPI_HISTORY:
        ref_month, rel_date, headline, food, fuel, consensus = row
        dec = decompose_cpi(headline=headline, food_yoy=food, fuel_yoy=fuel)
        cpi_store.upsert({
            "release_date":       rel_date,
            "reference_month":    ref_month,
            "headline_yoy":       headline,
            "food_yoy":           food,
            "fuel_yoy":           fuel,
            "core_yoy":           dec["core_yoy"],
            "food_contrib":       dec["food_contrib"],
            "fuel_contrib":       dec["fuel_contrib"],
            "core_contrib":       dec["core_contrib"],
            "consensus_forecast": consensus,
        })
        print(f"  CPI {ref_month}: {headline}% (core={dec['core_yoy']}%)")

    print("Seeding IIP data...")
    for row in IIP_HISTORY:
        ref, rel, hl, mfg, mine, elec, cap, cd, cnd, infra, prim, inter, cons = row
        iip_store.upsert({
            "release_date":             rel,
            "reference_month":          ref,
            "headline_yoy":             hl,
            "manufacturing_yoy":        mfg,
            "mining_yoy":               mine,
            "electricity_yoy":          elec,
            "capital_goods_yoy":        cap,
            "consumer_durables_yoy":    cd,
            "consumer_nondurables_yoy": cnd,
            "infra_construction_yoy":   infra,
            "primary_goods_yoy":        prim,
            "intermediate_goods_yoy":   inter,
            "consensus_forecast":       cons,
        })
        print(f"  IIP {ref}: {hl}%")

    print(f"\nSeed complete. CPI records: {cpi_store.count()}")


if __name__ == "__main__":
    seed()
