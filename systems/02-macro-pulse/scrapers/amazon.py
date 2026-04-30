"""
Amazon India price scraper.

Strategy:
1. Visit search page for the basket item's amazon_search query.
2. Collect up to N candidate result tiles, each with (title, price, sponsored).
3. Filter sponsored tiles out — they're paid placements, not natural prices.
4. Filter by unit consistency: the title should mention a quantity that matches
   the basket item's expected unit (e.g. "5kg" for a 5kg rice query). Loose
   match — we accept "5 kg", "5kg pack", etc.
5. Among 3+ remaining candidates, pick the MEDIAN price. Median is robust to
   bait-priced outliers and premium-variant tiles.
6. Compute price_per_kg using parsed unit when available.

Returns observations as list of dicts. Caller is responsible for outlier
rejection vs the historical trailing median (engine/outlier.py).
"""
from __future__ import annotations

import logging
import os
import re
import statistics
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

PINCODE = "110001"
MAX_RESULTS_PER_QUERY = 8


def scrape_amazon(basket_items: list[dict]) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        raise RuntimeError("playwright package not installed")

    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/tmp/pw-browsers")
    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    results: list[dict] = []

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
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-IN",
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        for item in basket_items:
            q = item.get("amazon_search") or item.get("blinkit_search") or item["name"]
            try:
                page.goto(
                    f"https://www.amazon.in/s?k={q.replace(' ', '+')}",
                    timeout=20_000,
                    wait_until="domcontentloaded",
                )
                page.wait_for_timeout(3000)

                candidates = _extract_candidates(page, MAX_RESULTS_PER_QUERY)
                pick = _pick_best_match(candidates, item)
                if pick is None:
                    logger.info(f"Amazon: no match for {item['name']}")
                    continue

                price = pick["price"]
                results.append({
                    "platform":     "amazon",
                    "item_id":      item["item_id"],
                    "cpi_group":    item["cpi_group"],
                    "item_name":    pick["title"][:200],  # cap title length
                    "price":        price,
                    "unit":         item["unit"],
                    "price_per_kg": _price_per_kg(price, item["unit"]),
                    "scraped_at":   scraped_at,
                    "pincode":      PINCODE,
                })

                time.sleep(1.5)
            except PWTimeout:
                logger.info(f"Amazon: timeout for {item['name']}")
                continue
            except Exception as e:
                logger.error(f"Amazon: error for {item['name']}: {e}")

    finally:
        try: browser.close()
        except Exception: pass
        try: pw.stop()
        except Exception: pass

    return results


# ─── Candidate extraction & matching ────────────────────────────────────────

def _extract_candidates(page, limit: int) -> list[dict]:
    """
    Pull up to `limit` non-sponsored search results. Each candidate dict has:
        title, price, sponsored, has_unit_match (filled later).
    """
    js = """
    () => {
        const tiles = Array.from(document.querySelectorAll('[data-component-type="s-search-result"]'));
        return tiles.map(t => {
            const sponsored = !!t.querySelector('.puis-label-popover-default')
                || !!t.querySelector('[data-component-type="sp-sponsored-result"]')
                || (t.innerText || '').includes('Sponsored');
            const titleEl = t.querySelector('h2 a span') || t.querySelector('h2 span');
            const priceEl = t.querySelector('.a-price .a-price-whole');
            return {
                title: titleEl ? titleEl.innerText.trim() : '',
                priceText: priceEl ? priceEl.innerText.replace(/[,\\s]/g, '') : '',
                sponsored: sponsored,
            };
        });
    }
    """
    try:
        raw = page.evaluate(js)
    except Exception as exc:
        # If page.evaluate breaks (Amazon DOM changed badly), the only
        # honest answer is "scraper blocked" — exit cleanly rather than
        # pretend a stale selector fallback worked.
        logger.warning(f"Amazon: page.evaluate failed: {exc}")
        return []

    candidates: list[dict] = []
    for r in raw:
        if not r.get("priceText") or not r.get("title"):
            continue
        m = re.match(r"(\d+(?:\.\d+)?)", r["priceText"])
        if not m:
            continue
        try:
            price = float(m.group(1))
        except ValueError:
            continue
        if price <= 0 or price > 100000:  # absurd prices are matcher errors
            continue
        candidates.append({
            "title":     r["title"],
            "price":     price,
            "sponsored": bool(r.get("sponsored")),
        })
        if len(candidates) >= limit:
            break
    return candidates


def _pick_best_match(candidates: list[dict], basket_item: dict) -> Optional[dict]:
    """
    Filter sponsored, prefer unit-consistent matches, return median by price.
    """
    # Strip sponsored
    natural = [c for c in candidates if not c["sponsored"]]
    if not natural:
        natural = candidates  # if EVERYTHING was sponsored, accept it

    # Unit-aware filter
    expected_unit = basket_item.get("unit", "")
    expected_qty, expected_kind = _parse_unit(expected_unit)
    if expected_qty is not None and expected_kind:
        unit_matches = [c for c in natural if _title_matches_unit(c["title"], expected_qty, expected_kind)]
        if len(unit_matches) >= 2:
            natural = unit_matches

    if not natural:
        return None

    # Median by price (robust to bait-priced outliers)
    natural.sort(key=lambda c: c["price"])
    if len(natural) >= 3:
        return natural[len(natural) // 2]
    return natural[0]  # 1-2 candidates: take the cheapest


_UNIT_RX = re.compile(
    r"(\d+(?:\.\d+)?)\s*(g|gm|grams?|kg|l|litres?|liters?|ltr|ml|pcs?|pieces?)",
    re.IGNORECASE,
)


def _parse_unit(unit_str: str) -> tuple[Optional[float], str]:
    m = _UNIT_RX.search(unit_str)
    if not m:
        return None, ""
    qty = float(m.group(1))
    kind = m.group(2).lower()
    if kind in ("kg",):
        return qty, "kg"
    if kind in ("g", "gm", "gram", "grams"):
        return qty / 1000.0, "kg"
    if kind in ("l", "ltr", "litre", "litres", "liter", "liters"):
        return qty, "l"
    if kind in ("ml",):
        return qty / 1000.0, "l"
    if kind in ("pc", "pcs", "piece", "pieces"):
        return qty, "pc"
    return None, ""


def _title_matches_unit(title: str, expected_qty: float, expected_kind: str) -> bool:
    """Check if the title mentions a quantity within ±20% of expected."""
    for m in _UNIT_RX.finditer(title):
        qty = float(m.group(1))
        kind = m.group(2).lower()
        # Normalise to base units
        kind_qty: Optional[tuple[float, str]] = None
        if kind in ("kg",):
            kind_qty = (qty, "kg")
        elif kind in ("g", "gm", "gram", "grams"):
            kind_qty = (qty / 1000.0, "kg")
        elif kind in ("l", "ltr", "litre", "litres", "liter", "liters"):
            kind_qty = (qty, "l")
        elif kind in ("ml",):
            kind_qty = (qty / 1000.0, "l")
        elif kind in ("pc", "pcs", "piece", "pieces"):
            kind_qty = (qty, "pc")
        if not kind_qty:
            continue
        title_qty, title_kind = kind_qty
        if title_kind != expected_kind:
            continue
        if abs(title_qty - expected_qty) / max(expected_qty, 0.001) <= 0.20:
            return True
    return False


def _price_per_kg(price: float, unit: str) -> Optional[float]:
    m = _UNIT_RX.search(unit)
    if not m:
        return None
    qty = float(m.group(1))
    kind = m.group(2).lower()
    if kind in ("kg", "l", "litre", "litres", "liter", "liters", "ltr"):
        return round(price / qty, 2) if qty else None
    if kind in ("g", "gm", "gram", "grams", "ml"):
        return round(price / qty * 1000, 2) if qty else None
    return None
