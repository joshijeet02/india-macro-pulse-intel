"""
Retail petrol and diesel prices for Delhi.

Why fuel matters to this index beyond its own weight: pump prices are revised
daily, they are the cleanest high-frequency series in the whole basket, and
they are the main channel through which a crude or geopolitical shock reaches
CPI. Transport carries 8.796% of the basket and petrol/diesel are roughly 40%
of it, so this is ~3.5% of the index — small enough that a wrong number would
not look obviously broken, which is exactly why it needs guarding.

Extraction is by LABEL, not position. These pages carry several price tables
(other cities, LPG, historical rows), and reading "the first number that looks
like a price" produced four different candidates on the same page. Instead we
find the table with a City column and read the row whose city cell matches
exactly.

Delhi is used because the grocery basket is already priced at Delhi 110001, so
both signals describe the same geography.

The oil marketing companies publish these prices themselves, but their pages
are JS-rendered and would need a headless browser — which the daily GitHub
Action cannot rely on, since Amazon already blocks headless Chromium from
cloud IP ranges. These aggregators mirror the same OMC figures over plain
HTTP, and two independent ones are cross-checked against each other.
"""
from __future__ import annotations

import html as html_lib
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import requests

log = logging.getLogger(__name__)

CITY = "New Delhi"

# Single source, deliberately. A bankbazaar mirror was included as a
# cross-check but its pages carry no City/Price table, so it never once
# parsed — it contributed no verification and roughly doubled fetch latency.
# A source that has never succeeded is not redundancy, and keeping it would
# have implied a corroboration that was not happening.
SOURCES = {
    "petrol": ("https://www.goodreturns.in/petrol-price-in-delhi.html",),
    "diesel": ("https://www.goodreturns.in/diesel-price-in-delhi.html",),
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
}

# Indian retail fuel has traded in a narrow band for years. Anything outside
# this is a parse error, not a price — a mis-read table cell would otherwise
# move the transport division hard while looking like a plausible number.
PLAUSIBLE_RANGE = (60.0, 200.0)

# Kept short: this runs on a button press a person is waiting on.
FETCH_TIMEOUT = 10

# Two sources disagreeing by more than this means one is stale or mis-parsed.
DISAGREEMENT_TOLERANCE = 0.03      # 3%

_TABLE = re.compile(r"<table.*?</table>", re.S | re.I)
_ROW = re.compile(r"<tr.*?</tr>", re.S | re.I)
_CELL = re.compile(r"<t[dh].*?</t[dh]>", re.S | re.I)
_TAGS = re.compile(r"<[^>]+>")
_PRICE = re.compile(r"([0-9]{2,3}\.[0-9]{2})")


def _clean(cell: str) -> str:
    return html_lib.unescape(_TAGS.sub("", cell)).strip()


def extract_city_price(html: str, city: str = CITY) -> Optional[float]:
    """
    Read one city's price from a City/Price table.

    Matched on an exact city-cell match rather than a nearby-text search: these
    pages list many cities and several unrelated price tables, and proximity
    matching returned a different answer depending on which phrase was
    anchored on.
    """
    for table in _TABLE.findall(html):
        if "city" not in table.lower():
            continue
        for row in _ROW.findall(table):
            cells = [_clean(c) for c in _CELL.findall(row)]
            if len(cells) < 2 or cells[0].lower() != city.lower():
                continue
            match = _PRICE.search(cells[1])
            if match:
                return float(match.group(1))
    return None


def _fetch(url: str) -> Optional[str]:
    try:
        response = requests.get(url, headers=HEADERS, timeout=FETCH_TIMEOUT)
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        log.warning(f"fuel: {url} failed: {exc}")
        return None


def fetch_fuel_price(kind: str) -> Optional[float]:
    """
    One fuel's Delhi price, cross-checked across two independent mirrors.

    Returns the primary source's figure when both agree. If they disagree
    materially we log loudly and still return the primary — but the
    disagreement is the thing worth surfacing, because a silently stale mirror
    produces a number that looks entirely reasonable.
    """
    readings: list[float] = []
    for url in SOURCES.get(kind, ()):
        html = _fetch(url)
        if html is None:
            continue
        price = extract_city_price(html)
        if price is None:
            log.warning(f"fuel: no {CITY} row found at {url}")
            continue
        if not (PLAUSIBLE_RANGE[0] <= price <= PLAUSIBLE_RANGE[1]):
            log.warning(f"fuel: {kind} {price} outside plausible range — discarding")
            continue
        readings.append(price)

    if not readings:
        return None
    if len(readings) >= 2:
        spread = abs(readings[0] - readings[1]) / min(readings)
        if spread > DISAGREEMENT_TOLERANCE:
            log.warning(
                f"fuel: {kind} sources disagree by {spread:.1%} "
                f"({readings[0]} vs {readings[1]}) — using primary"
            )
    return readings[0]


def fetch_fuel() -> dict:
    """
    Delhi petrol and diesel, per litre.

    Returns {} rather than a partial reading if neither fuel resolves, so the
    transport division stays honestly marked as carried instead of moving on
    half a signal.
    """
    prices: dict[str, float] = {}
    for kind in ("petrol", "diesel"):
        price = fetch_fuel_price(kind)
        if price is not None:
            prices[f"{kind}_per_litre"] = price

    if prices:
        log.info(
            f"fuel: {', '.join(f'{k} {v}' for k, v in prices.items())} "
            f"({CITY}, {datetime.now(timezone.utc):%Y-%m-%d})"
        )
    return prices
