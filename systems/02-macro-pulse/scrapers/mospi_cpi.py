"""
MOSPI CPI press release scraper.

Same pattern as IIP: JSON-API discovery + prose extraction.

Note on the 2024=100 base year (effective Jan 2026): MOSPI replaced the
"Fuel & Light" group with "Housing, water, electricity, gas and other
fuels", so fuel_yoy is frequently None for releases after that switch.
That's expected — sanity_check_release tolerates fuel=None as long as the
headline parsed. We do NOT silently accept *any* failure though; the
bypass that did so previously has been removed.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Optional

from scrapers._mospi_api import (
    DEFAULT_HEADERS, absolute_pdf_url, fetch_latest_releases, find_latest_release,
)
from scrapers._pdf_extract import (
    extract_cpi_from_prose,
    extract_reference_month,
    fetch_pdf_bytes,
    open_pdf_text,
    sanity_check_release,
)

log = logging.getLogger(__name__)

FIXTURE_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "sample_cpi.json"

# Only food_yoy is strictly required — fuel may be absent under 2024=100.
REQUIRED_COMPONENTS = ("food_yoy",)


def fetch_latest_cpi(use_fixture: bool = False) -> Optional[dict]:
    """Fetch latest CPI release, or None on any failure."""
    if use_fixture:
        return json.loads(FIXTURE_PATH.read_text())
    try:
        return _scrape_mospi_cpi()
    except Exception as exc:
        log.warning(f"[mospi_cpi] scrape failed: {exc}")
        return None


def parse_cpi_pdf(pdf_bytes: bytes, source_url: str = "") -> Optional[dict]:
    """Public for testing — parse an already-downloaded PDF blob."""
    text = open_pdf_text(pdf_bytes, max_pages=4)

    reference_month = extract_reference_month(text)
    if not reference_month:
        log.warning("[mospi_cpi] cannot extract reference month")
        return None

    prose = extract_cpi_from_prose(text)

    payload = {
        "reference_month": reference_month,
        "release_date":    date.today().isoformat(),
        "headline_yoy":    prose.get("headline_yoy"),
        "food_yoy":        prose.get("food_yoy"),
        "fuel_yoy":        prose.get("fuel_yoy"),
        "source":          source_url,
    }

    ok, reason = sanity_check_release(payload, REQUIRED_COMPONENTS)
    if not ok:
        # Tightened: only allow headline-only records under the 2024=100
        # base year (Jan 2026 onward) where the food_yoy field is
        # genuinely unavailable. Older periods MUST have food_yoy.
        if (
            payload.get("headline_yoy") is not None
            and payload.get("food_yoy") is None
            and reference_month
            and reference_month >= "2026-01"
        ):
            log.info(f"[mospi_cpi] keeping headline-only record for {reference_month} (post-2024-base)")
            return payload
        log.warning(f"[mospi_cpi] sanity check failed: {reason}")
        return None

    return payload


def _scrape_mospi_cpi() -> Optional[dict]:
    releases = fetch_latest_releases()
    if not releases:
        raise RuntimeError("MOSPI home API returned no releases")

    latest = find_latest_release(releases, "CPI")
    if not latest:
        log.info("[mospi_cpi] no CPI release in latest 4 — nothing new")
        return None

    pdf_url = absolute_pdf_url(latest["file_one"])
    if not pdf_url:
        raise RuntimeError(f"CPI entry has no PDF URL: {latest.get('id')}")

    log.info(f"[mospi_cpi] fetching {pdf_url}")
    pdf_bytes = fetch_pdf_bytes(pdf_url, DEFAULT_HEADERS, timeout=60)
    payload = parse_cpi_pdf(pdf_bytes, source_url=pdf_url)
    if payload:
        published = latest.get("published_date") or latest.get("start_date")
        if published:
            payload["release_date"] = published[:10]
    return payload
