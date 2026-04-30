"""
MOSPI IIP (Index of Industrial Production) press release scraper.

Discovery path: hits the MOSPI public JSON home-data API and finds the most
recent IIP entry. Falls back to None on any failure so callers can keep
showing seed/JSON-merged data.

Parsing path: structured-prose extraction targeting MOSPI's templated
highlight sentences ("growth rates of the three sectors, ...", "Use-based
classification ... are X percent in Primary goods, ...").

This is deliberately stricter than the original generic regex hunt — but
verified against the real April 2026 IIP PDF (see tests/fixtures/pdf/).
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
    extract_iip_from_prose,
    extract_reference_month,
    fetch_pdf_bytes,
    open_pdf_text,
    sanity_check_release,
)

log = logging.getLogger(__name__)

FIXTURE_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "sample_iip.json"

# Components we expect to extract; sanity check requires majority parsed.
REQUIRED_COMPONENTS = (
    "manufacturing_yoy", "mining_yoy", "electricity_yoy",
    "capital_goods_yoy", "consumer_durables_yoy",
    "consumer_nondurables_yoy", "infra_construction_yoy",
    "primary_goods_yoy", "intermediate_goods_yoy",
)


def fetch_latest_iip(use_fixture: bool = False) -> Optional[dict]:
    """
    Fetch the latest MOSPI IIP press release and return a parsed dict.

    Returns None on any failure — callers should fall back to existing
    DB / JSON / seed data rather than persist a partial parse.
    """
    if use_fixture:
        return json.loads(FIXTURE_PATH.read_text())
    try:
        return _scrape_mospi_iip()
    except Exception as exc:
        log.warning(f"[mospi_iip] scrape failed: {exc}")
        return None


def parse_iip_pdf(pdf_bytes: bytes, source_url: str = "") -> Optional[dict]:
    """Public for testing — parse an already-downloaded PDF blob."""
    text = open_pdf_text(pdf_bytes, max_pages=4)

    reference_month = extract_reference_month(text)
    if not reference_month:
        log.warning("[mospi_iip] cannot extract reference month")
        return None

    # Prose-based extraction (anchored on MOSPI's templated sentences).
    prose = extract_iip_from_prose(text)

    payload: dict = {
        "reference_month": reference_month,
        "release_date":    date.today().isoformat(),
        "headline_yoy":    prose.get("headline_yoy"),
        "manufacturing_yoy":        prose.get("manufacturing_yoy"),
        "mining_yoy":               prose.get("mining_yoy"),
        "electricity_yoy":          prose.get("electricity_yoy"),
        "capital_goods_yoy":        prose.get("capital_goods_yoy"),
        "consumer_durables_yoy":    prose.get("consumer_durables_yoy"),
        "consumer_nondurables_yoy": prose.get("consumer_nondurables_yoy"),
        "infra_construction_yoy":   prose.get("infra_construction_yoy"),
        "primary_goods_yoy":        prose.get("primary_goods_yoy"),
        "intermediate_goods_yoy":   prose.get("intermediate_goods_yoy"),
        "source":                   source_url,
    }

    ok, reason = sanity_check_release(payload, REQUIRED_COMPONENTS)
    if not ok:
        log.warning(f"[mospi_iip] sanity check failed: {reason}")
        return None

    return payload


def _scrape_mospi_iip() -> Optional[dict]:
    releases = fetch_latest_releases()
    if not releases:
        raise RuntimeError("MOSPI home API returned no releases")

    latest = find_latest_release(releases, "IIP")
    if not latest:
        log.info("[mospi_iip] no IIP release in latest 4 — nothing new")
        return None

    pdf_url = absolute_pdf_url(latest["file_one"])
    if not pdf_url:
        raise RuntimeError(f"IIP entry has no PDF URL: {latest.get('id')}")

    log.info(f"[mospi_iip] fetching {pdf_url}")
    pdf_bytes = fetch_pdf_bytes(pdf_url, DEFAULT_HEADERS, timeout=60)
    payload = parse_iip_pdf(pdf_bytes, source_url=pdf_url)
    if payload:
        # Override release_date with MOSPI's actual published_date
        published = latest.get("published_date") or latest.get("start_date")
        if published:
            payload["release_date"] = published[:10]
    return payload
