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
import random
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
        for item in basket_items:
            q = item.get("amazon_search") or item.get("blinkit_search") or item["name"]
            url = f"https://www.amazon.in/s?k={q.replace(' ', '+')}"

            # A FRESH page per item. Sharing one page meant a single failed
            # navigation poisoned every subsequent item: the errors cascaded as
            # "interrupted by another navigation" and a live run lost 13 of 20
            # items after one stumble. An isolated page confines a failure to
            # the item that caused it.
            pick = None
            for attempt in (1, 2):
                page = None
                try:
                    page = ctx.new_page()
                    page.add_init_script(
                        "Object.defineProperty(navigator, 'webdriver', "
                        "{get: () => undefined})"
                    )
                    page.goto(url, timeout=25_000, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)
                    candidates = _extract_candidates(page, MAX_RESULTS_PER_QUERY)
                    pick = _pick_best_match(candidates, item)
                    break
                except PWTimeout:
                    logger.info(f"Amazon: timeout for {item['name']} (attempt {attempt})")
                except Exception as e:
                    logger.warning(f"Amazon: error for {item['name']} (attempt {attempt}): {e}")
                finally:
                    if page is not None:
                        try: page.close()
                        except Exception: pass
                if attempt == 1:
                    time.sleep(5.0)   # back off before the single retry

            if pick is None:
                logger.info(f"Amazon: no usable match for {item['name']}")
                time.sleep(random.uniform(2.0, 4.0))
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

            # Jittered delay — a fixed 1.5s cadence is itself a bot signature.
            time.sleep(random.uniform(2.0, 4.5))

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
            // Amazon renders the tile heading inconsistently: on many tiles
            // `h2 a span` holds only the BRAND ("NATURELAND ORGANICS",
            // "Amul", "Fresh"), not the product. A live run matched on those
            // truncated strings and produced nonsense. Try several selectors
            // and keep the LONGEST string — product titles are long, brand
            // labels are short.
            const titleCandidates = [
                t.querySelector('[data-cy="title-recipe"] h2'),
                t.querySelector('h2 a span'),
                t.querySelector('h2 span'),
                t.querySelector('h2'),
                t.querySelector('a.a-link-normal[title]'),
                t.querySelector('.a-size-medium.a-color-base'),
                t.querySelector('.a-size-base-plus.a-color-base'),
            ];
            let title = '';
            for (const el of titleCandidates) {
                if (!el) continue;
                const txt = ((el.getAttribute && el.getAttribute('title')) || el.innerText || '').trim();
                if (txt.length > title.length) title = txt;
            }
            const priceEl = t.querySelector('.a-price .a-price-whole');
            return {
                title: title,
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


def passes_match_guards(title: str, price: float, basket_item: dict) -> bool:
    """
    Reject candidates that are the wrong product entirely.

    The first live scrape (2026-08-05) matched "Zhanmai Egg Cartons 12 Count"
    at Rs.7722 for a dozen eggs, and "Fresh Onion, 1kg" for potato. Neither
    was caught downstream: outlier rejection needs trailing history, and the
    very first observation of an item has none — precisely when the matcher is
    least protected. So the guards run at pick time, not after.

    Three checks, all optional per item:
      match_include — at least one term must appear in the title
      match_exclude — no term may appear (catches accessories and variants)
      price_range   — plausible band for the item's stated unit
    """
    lowered = title.lower()

    include = basket_item.get("match_include")
    if include and not any(term.lower() in lowered for term in include):
        return False

    exclude = basket_item.get("match_exclude")
    if exclude and any(term.lower() in lowered for term in exclude):
        return False

    price_range = basket_item.get("price_range")
    if price_range and not (price_range[0] <= price <= price_range[1]):
        return False

    return True


def _pick_best_match(candidates: list[dict], basket_item: dict) -> Optional[dict]:
    """
    Filter sponsored, drop wrong-product matches, prefer unit-consistent
    candidates, return median by price.
    """
    # Strip sponsored
    natural = [c for c in candidates if not c["sponsored"]]
    if not natural:
        natural = candidates  # if EVERYTHING was sponsored, accept it

    # Wrong-product guards. Applied before anything else, and never relaxed:
    # a plausible price on the wrong product is worse than no observation,
    # because it silently contaminates the index and every chart downstream.
    guarded = [c for c in natural if passes_match_guards(c["title"], c["price"], basket_item)]
    if not guarded:
        logger.info(
            f"Amazon: all {len(natural)} candidates failed match guards for "
            f"{basket_item.get('item_id')} — recording no observation"
        )
        return None
    natural = guarded

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
