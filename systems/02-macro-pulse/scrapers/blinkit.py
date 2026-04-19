"""
Blinkit price scraper (Delhi, pincode 110001).
Uses Playwright to search for each basket item and extract the first result price.
"""
import re
import time
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

PINCODE = "110001"
# Approx lat/lon for Connaught Place, Delhi
_LAT = "28.6339"
_LON = "77.2195"

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def scrape_blinkit(basket_items: list[dict]) -> list[dict]:
    """
    Scrape prices for basket_items from Blinkit.
    Returns list of price records ready for EcommStore.insert_prices_bulk.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        logger.error("playwright not installed. Run: pip install playwright && playwright install chromium")
        return []

    results = []
    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        ctx = browser.new_context(
            user_agent=_UA,
            locale="en-IN",
            viewport={"width": 1280, "height": 800},
        )
        ctx.add_cookies([
            {"name": "gr_1_latitude",  "value": _LAT,    "domain": ".blinkit.com", "path": "/"},
            {"name": "gr_1_longitude", "value": _LON,    "domain": ".blinkit.com", "path": "/"},
            {"name": "lat",            "value": _LAT,    "domain": ".blinkit.com", "path": "/"},
            {"name": "lon",            "value": _LON,    "domain": ".blinkit.com", "path": "/"},
        ])
        page = ctx.new_page()

        # Intercept JSON API responses (Blinkit fires REST calls on search)
        _api_buf: list[dict] = []

        def _on_response(response):
            ct = response.headers.get("content-type", "")
            if "json" in ct and ("search" in response.url or "product" in response.url):
                try:
                    _api_buf.append(response.json())
                except Exception:
                    pass

        page.on("response", _on_response)

        for item in basket_items:
            _api_buf.clear()
            record = _scrape_item(page, _api_buf, item, scraped_at, PWTimeout)
            if record:
                results.append(record)
            time.sleep(1.2)

        browser.close()

    logger.info(f"Blinkit: scraped {len(results)}/{len(basket_items)} items")
    return results


def _scrape_item(page, api_buf: list, item: dict, scraped_at: str, PWTimeout) -> Optional[dict]:
    q = item["blinkit_search"]
    try:
        page.goto(f"https://blinkit.com/s/?q={q}", timeout=20_000, wait_until="domcontentloaded")
        page.wait_for_timeout(3_000)

        # ── Try API buffer first ──────────────────────────────────────────
        price, item_name, unit_str = _extract_from_api(api_buf, item)

        # ── Fallback: DOM scraping ────────────────────────────────────────
        if price is None:
            price, item_name, unit_str = _extract_from_dom(page, item)

        if price is None or price <= 0:
            logger.warning(f"Blinkit: no price found for {item['name']}")
            return None

        unit_str = unit_str or item["unit"]
        ppkg = _price_per_kg(price, unit_str)

        return {
            "platform":    "blinkit",
            "item_id":     item["item_id"],
            "cpi_group":   item["cpi_group"],
            "item_name":   item_name or item["name"],
            "price":       price,
            "unit":        unit_str,
            "price_per_kg": ppkg,
            "scraped_at":  scraped_at,
            "pincode":     PINCODE,
        }

    except PWTimeout:
        logger.warning(f"Blinkit: timeout for {item['name']}")
        return None
    except Exception as exc:
        logger.error(f"Blinkit: error for {item['name']}: {exc}")
        return None


def _extract_from_api(api_buf: list, item: dict) -> tuple[Optional[float], Optional[str], Optional[str]]:
    for payload in api_buf:
        products = (
            payload.get("products")
            or payload.get("data", {}).get("products")
            or []
        )
        if isinstance(products, dict):
            products = products.get("objects", []) or []
        for p in products[:3]:
            price = (
                p.get("price")
                or p.get("mrp")
                or p.get("selling_price")
                or (p.get("pricing", {}) or {}).get("mrp")
            )
            if price:
                name = p.get("name") or p.get("product_name") or item["name"]
                unit = p.get("unit") or p.get("weight") or ""
                return float(price), str(name), str(unit)
    return None, None, None


def _extract_from_dom(page, item: dict) -> tuple[Optional[float], Optional[str], Optional[str]]:
    selectors = [
        '[class*="Product__UpdatedTitle"]',
        '[data-testid="product-name"]',
        '[class*="ProductCard"]',
        '[class*="product-card"]',
    ]
    cards = []
    for sel in selectors:
        cards = page.query_selector_all(sel)
        if cards:
            break

    for card in cards[:5]:
        # Try to find price within or near the card
        price_el = (
            card.query_selector('[class*="Price"]')
            or card.query_selector('[class*="price"]')
            or card.query_selector('[class*="mrp"]')
        )
        if not price_el:
            continue
        raw = price_el.inner_text().strip()
        price = _parse_price(raw)
        if price and price > 0:
            name_el = (
                card.query_selector('[class*="Name"]')
                or card.query_selector('[class*="name"]')
                or card.query_selector('[class*="title"]')
            )
            unit_el = (
                card.query_selector('[class*="Unit"]')
                or card.query_selector('[class*="unit"]')
                or card.query_selector('[class*="weight"]')
                or card.query_selector('[class*="quantity"]')
            )
            name = name_el.inner_text().strip() if name_el else item["name"]
            unit = unit_el.inner_text().strip() if unit_el else item["unit"]
            return price, name, unit

    return None, None, None


def _parse_price(text: str) -> Optional[float]:
    text = text.replace("₹", "").replace(",", "").strip()
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    return float(m.group(1)) if m else None


def _price_per_kg(price: float, unit: str) -> Optional[float]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(g|gm|grams?|kg|l|litre?s?|ltr|ml)", unit.lower())
    if not m:
        return None
    qty, utype = float(m.group(1)), m.group(2)
    if utype in ("kg", "l", "litre", "litres", "liter", "liters", "ltr"):
        return round(price / qty, 2)
    if utype in ("g", "gm", "gram", "grams"):
        return round(price / qty * 1000, 2)
    if utype == "ml":
        return round(price / qty * 1000, 2)
    return None
