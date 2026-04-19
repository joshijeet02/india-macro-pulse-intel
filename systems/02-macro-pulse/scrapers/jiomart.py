"""
JioMart price scraper.
"""
import os
import re
import time
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

PINCODE = "110001"

def scrape_jiomart(basket_items: list[dict]) -> list[dict]:
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
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="en-IN",
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        for item in basket_items:
            q = item.get("jiomart_search") or item.get("blinkit_search") or item["name"]
            try:
                page.goto(f"https://www.jiomart.com/search/{q.replace(' ', '%20')}", timeout=20_000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                # Look for price in product cards
                price = None
                cards = page.query_selector_all('[class*="plp-card-details"]')
                if not cards:
                    cards = page.query_selector_all('[class*="product-card"]')

                for card in cards[:5]:
                    price_el = card.query_selector('[id="price"]') or card.query_selector('[class*="jm-heading"]')
                    if price_el:
                        text = price_el.inner_text().replace('₹', '').replace(',', '').strip()
                        m = re.search(r"(\d+(?:\.\d+)?)", text)
                        if m:
                            price = float(m.group(1))
                            break

                if price and price > 0:
                    results.append({
                        "platform":     "jiomart",
                        "item_id":      item["item_id"],
                        "cpi_group":    item["cpi_group"],
                        "item_name":    item["name"],
                        "price":        price,
                        "unit":         item["unit"],
                        "price_per_kg": _price_per_kg(price, item["unit"]),
                        "scraped_at":   scraped_at,
                        "pincode":      PINCODE,
                    })
                
                time.sleep(1.5)
            except PWTimeout:
                continue
            except Exception as e:
                logger.error(f"JioMart: error for {item['name']}: {e}")

    finally:
        try: browser.close()
        except: pass
        try: pw.stop()
        except: pass

    return results

def _price_per_kg(price: float, unit: str) -> Optional[float]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(g|gm|grams?|kg|l|litre?s?|ltr|ml)", unit.lower())
    if not m: return None
    qty, utype = float(m.group(1)), m.group(2)
    if utype in ("kg", "l", "litre", "litres", "liter", "liters", "ltr"):
        return round(price / qty, 2)
    if utype in ("g", "gm", "gram", "grams", "ml"):
        return round(price / qty * 1000, 2)
    return None
