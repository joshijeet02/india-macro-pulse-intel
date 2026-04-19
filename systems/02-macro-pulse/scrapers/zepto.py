"""
Zepto price scraper (Delhi, pincode 110001).
Uses Playwright — mirrors the Blinkit scraper structure for easy comparison.
"""
import re
import time
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

PINCODE = "110001"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def scrape_zepto(basket_items: list[dict]) -> list[dict]:
    """
    Scrape prices for basket_items from Zepto.
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
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent=_UA,
            locale="en-IN",
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()

        _api_buf: list[dict] = []

        def _on_response(response):
            ct = response.headers.get("content-type", "")
            if "json" in ct and ("search" in response.url or "product" in response.url):
                try:
                    _api_buf.append(response.json())
                except Exception:
                    pass

        page.on("response", _on_response)

        # Navigate once to set pincode
        _set_pincode(page, PWTimeout)

        for item in basket_items:
            _api_buf.clear()
            record = _scrape_item(page, _api_buf, item, scraped_at, PWTimeout)
            if record:
                results.append(record)
            time.sleep(1.2)

        browser.close()

    logger.info(f"Zepto: scraped {len(results)}/{len(basket_items)} items")
    return results


def _set_pincode(page, PWTimeout):
    try:
        page.goto("https://www.zeptonow.com/", timeout=20_000, wait_until="domcontentloaded")
        page.wait_for_timeout(2_000)
        # Try to enter pincode if modal is present
        pincode_input = page.query_selector('input[placeholder*="pincode"], input[placeholder*="Pincode"]')
        if pincode_input:
            pincode_input.fill(PINCODE)
            page.wait_for_timeout(1_000)
            # Click first suggestion
            suggestion = page.query_selector('[class*="suggestion"], [class*="Suggestion"]')
            if suggestion:
                suggestion.click()
                page.wait_for_timeout(1_500)
    except Exception:
        pass  # location setting is best-effort


def _scrape_item(page, api_buf: list, item: dict, scraped_at: str, PWTimeout) -> Optional[dict]:
    q = item["zepto_search"]
    try:
        page.goto(
            f"https://www.zeptonow.com/search?query={q.replace(' ', '%20')}",
            timeout=20_000,
            wait_until="domcontentloaded",
        )
        page.wait_for_timeout(3_000)

        price, item_name, unit_str = _extract_from_api(api_buf, item)
        if price is None:
            price, item_name, unit_str = _extract_from_dom(page, item)

        if price is None or price <= 0:
            logger.warning(f"Zepto: no price found for {item['name']}")
            return None

        unit_str = unit_str or item["unit"]
        ppkg = _price_per_kg(price, unit_str)

        return {
            "platform":    "zepto",
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
        logger.warning(f"Zepto: timeout for {item['name']}")
        return None
    except Exception as exc:
        logger.error(f"Zepto: error for {item['name']}: {exc}")
        return None


def _extract_from_api(api_buf: list, item: dict) -> tuple[Optional[float], Optional[str], Optional[str]]:
    for payload in api_buf:
        # Zepto API shapes vary — try common keys
        products = (
            payload.get("data", {}).get("products", [])
            or payload.get("products", [])
            or payload.get("results", [])
            or []
        )
        for p in products[:3]:
            price = (
                p.get("discountedPrice")
                or p.get("price")
                or p.get("mrp")
                or (p.get("pricingInfo", {}) or {}).get("price")
            )
            if price:
                name = p.get("name") or p.get("productName") or item["name"]
                unit = p.get("unitOfMeasure") or p.get("packSize") or p.get("weight") or ""
                return float(price) / 100 if float(price) > 1000 else float(price), str(name), str(unit)
    return None, None, None


def _extract_from_dom(page, item: dict) -> tuple[Optional[float], Optional[str], Optional[str]]:
    selectors = [
        '[data-testid="product-card"]',
        '[class*="ProductCard"]',
        '[class*="product-card"]',
        '[class*="ProductItem"]',
    ]
    cards = []
    for sel in selectors:
        cards = page.query_selector_all(sel)
        if cards:
            break

    for card in cards[:5]:
        price_el = (
            card.query_selector('[class*="price"], [class*="Price"]')
            or card.query_selector('[data-testid*="price"]')
        )
        if not price_el:
            continue
        raw = price_el.inner_text().strip()
        price = _parse_price(raw)
        if price and price > 0:
            name_el = (
                card.query_selector('[class*="name"], [class*="Name"]')
                or card.query_selector('[class*="title"], [class*="Title"]')
            )
            unit_el = (
                card.query_selector('[class*="unit"], [class*="Unit"]')
                or card.query_selector('[class*="weight"], [class*="Weight"]')
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
