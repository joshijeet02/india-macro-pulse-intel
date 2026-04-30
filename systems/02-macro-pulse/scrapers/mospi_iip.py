"""
MOSPI IIP (Index of Industrial Production) press release scraper.

The scraper is tiered:
1. Find the latest IIP press release PDF on the MOSPI asset publisher page.
2. Extract YoY % values via table parsing (preferred) with anchored-regex
   fallback. Both go through bounds-based sanity checking.
3. Reject the entire record if too many fields fail to parse — better to
   surface a clear failure than persist garbage.

Returns None on any failure so callers can fall back to the DB / seed.
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
MOSPI_IIP_LIST_URL = (
    "https://mospi.gov.in/web/mospi/press-releases/-/asset_publisher/"
    "5XjCDPHnBClZ/content/index-industrial-production"
)

FIXTURE_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "sample_iip.json"

REQUIRED_COMPONENTS = (
    "manufacturing_yoy", "mining_yoy", "electricity_yoy",
    "capital_goods_yoy", "consumer_durables_yoy",
    "consumer_nondurables_yoy", "infra_construction_yoy",
    "primary_goods_yoy", "intermediate_goods_yoy",
)

USER_AGENT = "Mozilla/5.0 (research bot; joshijeet02@gmail.com)"


def fetch_latest_iip(use_fixture: bool = False) -> Optional[dict]:
    """
    Fetch latest IIP release from MOSPI.

    Returns dict with sectoral + use-based YoY values, or None on any failure.
    Callers should fall back to the DB / seed when None is returned.
    """
    if use_fixture:
        return json.loads(FIXTURE_PATH.read_text())
    try:
        return _scrape_mospi_iip()
    except Exception as e:
        logger.warning(f"[mospi_iip] scrape failed: {e}")
        return None


def parse_iip_pdf(pdf_bytes: bytes, source_url: str = "") -> Optional[dict]:
    """
    Public for testing: parse an already-downloaded PDF blob.
    Returns the IIP record dict, or None if parsing fails sanity checks.
    """
    text = open_pdf_text(pdf_bytes, max_pages=6)
    tables = open_pdf_tables(pdf_bytes, max_pages=6)

    reference_month = extract_reference_month(text)
    if not reference_month:
        logger.warning("[mospi_iip] cannot extract reference month")
        return None

    payload = {
        "reference_month":          reference_month,
        "release_date":             date.today().isoformat(),
        "headline_yoy":             extract_yoy(tables, text, "General Index",
                                                aliases=("General",)),
        "manufacturing_yoy":        extract_yoy(tables, text, "Manufacturing"),
        "mining_yoy":               extract_yoy(tables, text, "Mining"),
        "electricity_yoy":          extract_yoy(tables, text, "Electricity"),
        "capital_goods_yoy":        extract_yoy(tables, text, "Capital Goods"),
        "consumer_durables_yoy":    extract_yoy(tables, text, "Consumer Durables"),
        "consumer_nondurables_yoy": extract_yoy(
            tables, text, "Consumer Non-Durables",
            aliases=("Consumer Non Durables", "Consumer Nondurables"),
        ),
        "infra_construction_yoy":   extract_yoy(
            tables, text, "Infrastructure",
            aliases=("Infrastructure/ Construction", "Infra/Construction"),
        ),
        "primary_goods_yoy":        extract_yoy(tables, text, "Primary Goods"),
        "intermediate_goods_yoy":   extract_yoy(tables, text, "Intermediate Goods"),
        "source":                   source_url,
    }

    ok, reason = sanity_check_release(payload, REQUIRED_COMPONENTS)
    if not ok:
        logger.warning(f"[mospi_iip] sanity check failed: {reason}")
        return None

    return payload


def _scrape_mospi_iip() -> Optional[dict]:
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(MOSPI_IIP_LIST_URL, headers=headers, timeout=15)
    resp.raise_for_status()

    pdf_url = _find_latest_iip_pdf(resp.text)
    if not pdf_url:
        raise ValueError("No IIP PDF link found on MOSPI press release page")

    pdf_bytes = fetch_pdf_bytes(pdf_url, headers, timeout=30)
    return parse_iip_pdf(pdf_bytes, source_url=pdf_url)


def _find_latest_iip_pdf(html: str) -> Optional[str]:
    """
    MOSPI lists releases newest-first. We accept the first `.pdf` whose href
    or surrounding context mentions IIP. We also reject obvious non-press-
    release links (annexures, methodological notes).
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.lower().endswith(".pdf"):
            continue
        # Accept if "iip" appears in href OR surrounding link text.
        haystack = (href + " " + (a.get_text() or "")).lower()
        if "iip" not in haystack and "industrial production" not in haystack:
            continue
        if any(skip in haystack for skip in ("methodology", "annexure", "annex-")):
            continue
        candidates.append(href if href.startswith("http") else MOSPI_PRESS_RELEASE_BASE + href)

    return candidates[0] if candidates else None
