"""
MOSPI's React frontend hits a JSON API at https://www.mospi.gov.in/api/.
Most endpoints are 403-walled but `/main-site/get-home-main-site-data` is
public and returns the four most-recent press releases inside the
`latestReleasesData` field, including the relative path to each PDF.

This is the path we use for autonomous discovery of new IIP/CPI releases.
The original `requests.get` against the asset_publisher page returned a
React shell (2KB, zero PDF links) — the hardcoded HTML scrape never worked
in production. The JSON API does.
"""
from __future__ import annotations

import logging
from typing import Optional

import requests

log = logging.getLogger(__name__)

HOME_API_URL = "https://www.mospi.gov.in/api/main-site/get-home-main-site-data?lang=en"
SITE_BASE = "https://www.mospi.gov.in/"

# Browser-mimicking headers the API accepts. Without Origin/Referer it 403s.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Origin": "https://mospi.gov.in",
    "Referer": "https://mospi.gov.in/",
    "Accept": "application/json",
}


def fetch_latest_releases(timeout: int = 15) -> list[dict]:
    """
    Returns the 4 most-recent press release entries. Each entry has at
    minimum: id, title, published_date (or start_date as fallback), and
    file_one (with path, filename, filemime).

    Returns [] on any error — caller decides how to surface that.
    """
    try:
        resp = requests.get(HOME_API_URL, headers=DEFAULT_HEADERS, timeout=timeout)
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError) as exc:
        log.warning(f"MOSPI home API failed: {exc}")
        return []

    if not isinstance(payload, dict) or not payload.get("success"):
        log.warning(f"MOSPI home API returned unexpected shape: {type(payload).__name__}")
        return []

    releases = payload.get("latestReleasesData") or []
    return [r for r in releases if isinstance(r, dict)]


def find_latest_release(releases: list[dict], indicator: str) -> Optional[dict]:
    """
    Filter the release list for a specific indicator (CPI or IIP).

    Match is title-based and tolerant: title containing 'IIP' or 'Industrial
    Production' = IIP; title containing 'CPI' or 'Consumer Price Index' = CPI.
    Returns the most recent matching entry by published_date, or None.
    """
    needles = {
        "IIP": ("iip", "industrial production"),
        "CPI": ("cpi", "consumer price"),
    }.get(indicator.upper(), ())
    if not needles:
        return None

    matches = []
    for r in releases:
        title = (r.get("title") or "").lower()
        if not any(n in title for n in needles):
            continue
        # Skip approach papers, methodology notes, etc.
        if any(skip in title for skip in (
            "approach paper", "methodology", "consultation", "circular",
            "interaction", "draft revised",
        )):
            continue
        if not (r.get("file_one") or {}).get("path"):
            continue
        matches.append(r)

    if not matches:
        return None

    # Sort by published_date descending (or start_date as fallback)
    matches.sort(
        key=lambda r: r.get("published_date") or r.get("start_date") or "",
        reverse=True,
    )
    return matches[0]


def absolute_pdf_url(file_one: dict) -> Optional[str]:
    """Convert the API's relative path to an absolute URL."""
    path = file_one.get("path")
    if not path:
        return None
    if path.startswith("http"):
        return path
    return SITE_BASE + path.lstrip("/")
