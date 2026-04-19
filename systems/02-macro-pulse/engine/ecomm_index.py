"""
Laspeyres price index engine for e-commerce basket.
Index = 100 at first scrape date. Each subsequent scrape produces an index reading
that directly parallels CPI food movement.
"""
from datetime import datetime, timezone
from typing import Optional

from engine.ecomm_basket import BASKET, BASKET_BY_ID


def compute_index(
    current_prices: list[dict],
    base_prices: dict[str, float],
) -> dict:
    """
    Compute Laspeyres food price index.

    current_prices: list of price records from EcommStore.get_latest_prices()
    base_prices:    dict {item_id: base_price} from EcommStore.get_base_prices()

    Returns dict with: index_value, coverage_pct, items_count, components
    """
    price_map = {p["item_id"]: p for p in current_prices}
    total_weight = sum(i["weight"] for i in BASKET)

    numerator = 0.0
    denominator = 0.0
    components = []

    for item in BASKET:
        iid = item["item_id"]
        if iid not in price_map or iid not in base_prices:
            continue

        row = price_map[iid]
        current = row.get("price_per_kg") or row["price"]
        base = base_prices[iid]

        if base == 0:
            continue

        w = item["weight"]
        ratio = current / base
        numerator   += w * ratio
        denominator += w

        components.append({
            "item_id":       iid,
            "name":          item["name"],
            "cpi_group":     item["cpi_group"],
            "weight":        w,
            "current_price": current,
            "base_price":    base,
            "price_ratio":   round(ratio, 4),
            "pct_change":    round((ratio - 1) * 100, 2),
        })

    if denominator == 0:
        return {
            "index_value":   None,
            "coverage_pct":  0.0,
            "items_count":   0,
            "components":    [],
        }

    index = (numerator / denominator) * 100
    coverage = (denominator / total_weight) * 100

    return {
        "index_value":   round(index, 2),
        "coverage_pct":  round(coverage, 1),
        "items_count":   len(components),
        "components":    sorted(components, key=lambda x: x["cpi_group"]),
    }


def group_summary(components: list[dict]) -> list[dict]:
    """Roll up index components to CPI-group level."""
    groups: dict[str, dict] = {}
    for c in components:
        g = c["cpi_group"]
        if g not in groups:
            groups[g] = {"cpi_group": g, "total_weight": 0, "weighted_pct": 0.0, "item_count": 0}
        groups[g]["total_weight"]  += c["weight"]
        groups[g]["weighted_pct"]  += c["weight"] * c["pct_change"]
        groups[g]["item_count"]    += 1

    result = []
    for g, data in groups.items():
        if data["total_weight"] > 0:
            result.append({
                "cpi_group":    g,
                "avg_pct_change": round(data["weighted_pct"] / data["total_weight"], 2),
                "item_count":   data["item_count"],
            })
    return sorted(result, key=lambda x: x["avg_pct_change"], reverse=True)


def run_scrape_and_store(platforms: list[str] = ("blinkit", "zepto")) -> dict[str, dict]:
    """
    Convenience runner: scrape both platforms, store raw prices, compute+store index.
    Returns dict {platform: index_result}.
    """
    from db.store import EcommStore
    from engine.ecomm_basket import BASKET
    store = EcommStore()
    results = {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    for platform in platforms:
        if platform == "blinkit":
            from scrapers.blinkit import scrape_blinkit
            raw = scrape_blinkit(BASKET)
        elif platform == "zepto":
            from scrapers.zepto import scrape_zepto
            raw = scrape_zepto(BASKET)
        else:
            continue

        if not raw:
            results[platform] = {"error": "No data returned from scraper"}
            continue

        store.insert_prices_bulk(raw)

        base = store.get_base_prices(platform)
        latest = store.get_latest_prices(platform)
        idx = compute_index(latest, base)

        if idx["index_value"] is not None:
            store.insert_index({
                "platform":    platform,
                "computed_at": now,
                "index_value": idx["index_value"],
                "coverage_pct": idx["coverage_pct"],
                "items_count":  idx["items_count"],
            })

        results[platform] = idx

    return results
