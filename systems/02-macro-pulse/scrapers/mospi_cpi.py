"""
MOSPI CPI press release scraper.

Same tiered strategy as IIP: latest PDF discovery, table-first extraction,
anchored regex fallback, sanity checks. Returns None on failure.

Note on the 2024=100 base year (effective Jan 2026): MOSPI replaced the
"Fuel & Light" group with "Housing, water, electricity, gas and other fuels".
The fuel_yoy field will frequently be None for releases after that switch —
that's expected, not a bug.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

import requests

from scrapers._pdf_extract import (
    extract_reference_month,
    extract_yoy,
    fetch_pdf_bytes,
    open_pdf_tables,
    open_pdf_text,
    sanity_check_release,
)

logger = logging.getLogger(__name__)

MOSPI_PRESS_RELEASE_BASE = "https://mospi.gov.in"
MOSPI_CPI_LIST_URL = (
    "https://mospi.gov.in/web/mospi/press-releases/-/asset_publisher/"
    "5XjCDPHnBClZ/content/consumer-price-indices-cpi"
)

FIXTURE_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "sample_cpi.json"

REQUIRED_COMPONENTS = ("food_yoy",)  # fuel may be None under 2024=100; food
                                     # is the only consistently-required field.

USER_AGENT = "Mozilla/5.0 (research bot; joshijeet02@gmail.com)"


def fetch_latest_cpi(use_fixture: bool = False) -> Optional[dict]:
    """
    Fetch latest CPI release from MOSPI.

    Returns dict with: reference_month, release_date, headline_yoy, food_yoy,
    fuel_yoy, source. Returns None on any failure.
    """
    if use_fixture:
        return json.loads(FIXTURE_PATH.read_text())
    try:
        return _scrape_mospi_cpi()
    except Exception as e:
        logger.warning(f"[mospi_cpi] scrape failed: {e}")
        return None


def parse_cpi_pdf(pdf_bytes: bytes, source_url: str = "") -> Optional[dict]:
    """Public for testing — parse an already-downloaded PDF blob."""
    text = open_pdf_text(pdf_bytes, max_pages=4)
    tables = open_pdf_tables(pdf_bytes, max_pages=4)

    reference_month = extract_reference_month(text)
    if not reference_month:
        logger.warning("[mospi_cpi] cannot extract reference month")
        return None

    payload = {
        "reference_month": reference_month,
        "release_date":    date.today().isoformat(),
        "headline_yoy":    extract_yoy(tables, text, "General Index",
                                       aliases=("CPI Combined", "All Groups")),
        "food_yoy":        extract_yoy(
            tables, text, "Food and Beverages",
            aliases=("Food & Beverages", "Food",),
        ),
        "fuel_yoy":        extract_yoy(
            tables, text, "Fuel and Light",
            aliases=("Fuel & Light",),
        ),
        "source":          source_url,
    }

    ok, reason = sanity_check_release(payload, REQUIRED_COMPONENTS)
    if not ok:
        logger.warning(f"[mospi_cpi] sanity check failed: {reason}")
        # Allow records with food_yoy=None for post-2024 base year switch:
        # if only food/fuel are missing but headline parsed, still return it.
        if payload.get("headline_yoy") is not None:
            logger.info("[mospi_cpi] keeping headline-only record (post-2024-base)")
            return payload
        return None

    return payload


def _scrape_mospi_cpi() -> Optional[dict]:
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(MOSPI_CPI_LIST_URL, headers=headers, timeout=15)
    resp.raise_for_status()

    pdf_url = _find_latest_cpi_pdf(resp.text)
    if not pdf_url:
        raise ValueError("No CPI PDF link found on MOSPI press release page")

    pdf_bytes = fetch_pdf_bytes(pdf_url, headers, timeout=30)
    return parse_cpi_pdf(pdf_bytes, source_url=pdf_url)


def _find_latest_cpi_pdf(html: str) -> Optional[str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.lower().endswith(".pdf"):
            continue
        haystack = (href + " " + (a.get_text() or "")).lower()
        if "cpi" not in haystack and "consumer price" not in haystack:
            continue
        if any(skip in haystack for skip in ("methodology", "annexure", "annex-")):
            continue
        candidates.append(href if href.startswith("http") else MOSPI_PRESS_RELEASE_BASE + href)

    return candidates[0] if candidates else None
