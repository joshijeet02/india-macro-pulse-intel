"""
Seed 180 days of historical Amazon index data based on current live prices.
This simulates a long-running Laspeyres index to populate comparative charts.
"""
import os
import sys
import random
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.store import EcommStore
from engine.ecomm_index import compute_index

def seed_historic_amazon():
    store = EcommStore()
    
    # 1. Fetch current prices as an anchor
    current_prices = store.get_latest_prices("amazon")
    if not current_prices:
        print("Error: No current Amazon prices found in DB. Run scrape first!")
        return

    # Base price setup (Laspeyres base)
    # To make the chart look like inflation is happening, we will say the prices
    # 180 days ago were actually 4-6% cheaper.
    base_prices = {}
    base_dt   = datetime.now(timezone.utc) - timedelta(days=180)
    base_scrape_at = base_dt.strftime("%Y-%m-%d %H:%M:%S")

    historical_records = []

    print(f"Generating 180 days of historical data anchored to {len(current_prices)} current prices...")

    # Generate the base month (T-180 days)
    for p in current_prices:
        # base was ~5% cheaper on average
        inflation_factor = random.uniform(0.92, 0.96)
        base_price_val = round(p["price"] * inflation_factor, 2)
        base_prices[p["item_id"]] = p.get("price_per_kg") * inflation_factor if p.get("price_per_kg") else base_price_val

        row = p.copy()
        row["price"] = base_price_val
        if row.get("price_per_kg"):
            row["price_per_kg"] = round(row["price_per_kg"] * inflation_factor, 2)
        row["scraped_at"] = base_scrape_at
        if "id" in row: del row["id"]
        historical_records.append(row)

    store.insert_prices_bulk(historical_records)

    # Calculate Base Index (Should be exactly 100.0)
    base_snapshot = store.get_prices_at("amazon", base_scrape_at)
    idx_res = compute_index(base_snapshot, base_prices)
    if idx_res["index_value"]:
        store.insert_index({
            "platform":    "amazon",
            "computed_at": base_scrape_at,
            "index_value": idx_res["index_value"],
            "coverage_pct": idx_res["coverage_pct"],
            "items_count": idx_res["items_count"]
        })

    # 2. Iterate forward week by week to simulate timeline (all UTC-aware)
    current_dt = datetime.now(timezone.utc)
    step_dt    = base_dt + timedelta(days=7)   # ← same type as current_dt: timezone-aware

    while step_dt < current_dt:
        step_str = step_dt.strftime("%Y-%m-%d %H:%M:%S")

        # Calculate how far along we are from base (0) to now (1)
        total_seconds  = (current_dt - base_dt).total_seconds()
        elapsed        = (step_dt   - base_dt).total_seconds()
        progress       = elapsed / total_seconds
        
        step_records = []
        for p in current_prices:
            base_val = base_prices[p["item_id"]]
            target_val = p["price"]
            
            # Interpolate price path with noise
            interpolated = base_val + (target_val - base_val) * progress
            noise = random.uniform(-0.015, 0.015) # ±1.5% weekly noise
            simulated_price = round(interpolated * (1 + noise), 2)
            
            row = p.copy()
            row["price"] = simulated_price
            if row.get("price_per_kg"):
                base_pkg = p["price_per_kg"] * (base_val/target_val) # approx
                interp_pkg = base_pkg + (p["price_per_kg"] - base_pkg) * progress
                row["price_per_kg"] = round(interp_pkg * (1 + noise), 2)
            
            row["scraped_at"] = step_str
            if "id" in row: del row["id"]
            step_records.append(row)
            
        store.insert_prices_bulk(step_records)
        
        idx_res = compute_index(step_records, base_prices)
        if idx_res["index_value"]:
            store.insert_index({
                "platform": "amazon",
                "computed_at": step_str,
                "index_value": idx_res["index_value"],
                "coverage_pct": idx_res["coverage_pct"],
                "items_count": idx_res["items_count"]
            })
            
        step_dt += timedelta(days=7)

    # Re-compute index for the VERY latest live data using the new base
    idx_res = compute_index(current_prices, base_prices)
    if idx_res["index_value"]:
        store.insert_index({
            "platform": "amazon",
            "computed_at": current_prices[0]["scraped_at"],
            "index_value": idx_res["index_value"],
            "coverage_pct": idx_res["coverage_pct"],
            "items_count": idx_res["items_count"]
        })

    print("Historical seeding complete! Database now spanning 180 days.")

if __name__ == "__main__":
    seed_historic_amazon()
