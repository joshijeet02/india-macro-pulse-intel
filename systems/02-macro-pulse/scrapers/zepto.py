"""
Zepto price scraper (Delhi, pincode 110001).
Mirrors the Blinkit scraper structure. Raises RuntimeError if browser can't launch.
"""
import os
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
    Raises RuntimeError with a message if browser can't launch.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        raise RuntimeError("playwright package not installed")

    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/tmp/pw-browsers")

    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    results = []

    try:
        pw = sync_playwright().start()
    except Exception as exc:
        raise RuntimeError(f"Playwright failed to start: {exc}") from exc

    try:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ],
        )
    except Exception as exc:
        pw.stop()
        raise RuntimeError(f"Chromium launch failed: {exc}") from exc

    try:
        ctx = browser.new_context(
            user_agent=_UA,
            locale="en-IN",
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()

        # Anti-bot bypass: hide webdriver flag
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        _api_buf: list[dict] = []

        def _on_response(response):
            ct = response.headers.get("content-type", "")
            if "json" in ct and ("search" in response.url or "product" in response.url):
                try:
                    _api_buf.append(response.json())
                except Exception:
                    pass

        page.on("response", _on_response)
        _set_pincode(page)

        for item in basket_items:
            _api_buf.clear()
            record = _scrape_item(page, _api_buf, item, scraped_at, PWTimeout)
            if record:
                results.append(record)
            time.sleep(1.2)

    finally:
        try:
            browser.close()
        except Exception:
            pass
        try:
            pw.stop()
        except Exception:
            pass

    logger.info(f"Zepto: scraped {len(results)}/{len(basket_items)} items")
    return results


def _set_pincode(page):
    try:
        page.goto("https://www.zeptonow.com/", timeout=20_000, wait_until="domcontentloaded")
        page.wait_for_timeout(2_000)
        pincode_input = page.query_selector('input[placeholder*="pincode"], input[placeholder*="Pincode"]')
        if pincode_input:
            pincode_input.fill(PINCODE)
            page.wait_for_timeout(1_000)
            suggestion = page.query_selector('[class*="suggestion"], [class*="Suggestion"]')
            if suggestion:
                suggestion.click()
                page.wait_for_timeout(1_500)
    except Exception:
        pass


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
        return {
            "platform":     "zepto",
            "item_id":      item["item_id"],
            "cpi_group":    item["cpi_group"],
            "item_name":    item_name or item["name"],
            "price":        price,
            "unit":         unit_str,
            "price_per_kg": _price_per_kg(price, unit_str),
            "scraped_at":   scraped_at,
            "pincode":      PINCODE,
        }
    except PWTimeout:
        logger.warning(f"Zepto: timeout for {item['name']}")
        return None
    except Exception as exc:
        logger.error(f"Zepto: error for {item['name']}: {exc}")
        return None


def _extract_from_api(api_buf: list, item: dict) -> tuple[Optional[float], Optional[str], Optional[str]]:
    for payload in api_buf:
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
                raw = float(price)
                # Zepto sometimes returns paise (>1000 for items under ₹100)
                if raw > 1000:
                    raw /= 100
                name = p.get("name") or p.get("productName") or item["name"]
                unit = p.get("unitOfMeasure") or p.get("packSize") or p.get("weight") or ""
                return raw, str(name), str(unit)
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
        price = _parse_price(price_el.inner_text().strip())
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
