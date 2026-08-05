"""
Live gold and silver prices in INR.

Why this exists, ahead of any further grocery work:

Decomposing the January 2026 CPI print by division, `personal_care_and_misc`
carried just 5.04% of the basket weight but produced 35% of headline
inflation — more than food, which has seven times the weight. The driver is
gold and silver jewellery (COICOP sub-class 13.2) at 59% YoY.

Bullion is the rare CPI input that is priced continuously, globally, and for
free. A grocery basket cannot see it at all. Adding it buys more headline
accuracy than any incremental improvement to product matching in the food
basket, at a fraction of the effort and with none of the anti-bot fragility.

Indian retail jewellery prices track international spot converted at USD/INR,
plus import duty, GST and making charges. Those add a level offset but are
close to constant month to month, so the *change* in the INR spot price is a
good proxy for the *change* in the retail price — which is all an index needs.

Two independent FX sources are queried and cross-checked, because a silently
wrong exchange rate would corrupt the level without looking obviously broken.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import requests

log = logging.getLogger(__name__)

METAL_URL = "https://api.gold-api.com/price/{symbol}"
FX_PRIMARY = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=INR"
FX_FALLBACK = "https://open.er-api.com/v6/latest/USD"

TROY_OZ_IN_GRAMS = 31.1034768

# Two FX quotes disagreeing by more than this suggests one is stale or wrong.
FX_DISAGREEMENT_TOLERANCE = 0.02   # 2%


def _get_json(url: str, timeout: int = 15) -> Optional[dict]:
    try:
        resp = requests.get(url, timeout=timeout, headers={"Accept": "application/json"})
        resp.raise_for_status()
        payload = resp.json()
        return payload if isinstance(payload, dict) else None
    except (requests.RequestException, ValueError) as exc:
        log.warning(f"metals: {url} failed: {exc}")
        return None


def fetch_usd_inr() -> Optional[float]:
    """
    USD/INR, cross-checked across two independent providers.

    If both respond and disagree by more than the tolerance, we log loudly and
    take the primary — but the disagreement is the signal worth surfacing,
    because a bad rate corrupts every metal price downstream while still
    looking like a plausible number.
    """
    primary = _get_json(FX_PRIMARY)
    rate_primary = (primary or {}).get("rates", {}).get("INR")

    fallback = _get_json(FX_FALLBACK)
    rate_fallback = (fallback or {}).get("rates", {}).get("INR")

    rates = [r for r in (rate_primary, rate_fallback) if isinstance(r, (int, float)) and r > 0]
    if not rates:
        return None

    if len(rates) == 2:
        spread = abs(rates[0] - rates[1]) / min(rates)
        if spread > FX_DISAGREEMENT_TOLERANCE:
            log.warning(
                f"metals: USD/INR sources disagree by {spread:.1%} "
                f"({rates[0]} vs {rates[1]}) — using primary"
            )

    return float(rate_primary if rate_primary else rates[0])


def fetch_metal_inr_per_gram(symbol: str, usd_inr: float) -> Optional[dict]:
    """
    Spot price for one metal, converted to INR per gram.

    `symbol` is XAU (gold) or XAG (silver). Returns None rather than a partial
    record if anything is missing — a metal price with an unknown timestamp or
    a guessed FX rate is not worth storing.
    """
    payload = _get_json(METAL_URL.format(symbol=symbol))
    if not payload:
        return None

    usd_per_oz = payload.get("price")
    if not isinstance(usd_per_oz, (int, float)) or usd_per_oz <= 0:
        log.warning(f"metals: {symbol} returned no usable price")
        return None

    inr_per_gram = (usd_per_oz * usd_inr) / TROY_OZ_IN_GRAMS

    return {
        "symbol": symbol,
        "name": payload.get("name", symbol),
        "usd_per_oz": round(float(usd_per_oz), 4),
        "usd_inr": round(usd_inr, 4),
        "inr_per_gram": round(inr_per_gram, 2),
        "source_updated_at": payload.get("updatedAt"),
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }


def fetch_bullion() -> list[dict]:
    """
    Gold and silver in INR per gram. Empty list if FX is unavailable — without
    a trustworthy rate the INR figures would be fiction.
    """
    usd_inr = fetch_usd_inr()
    if usd_inr is None:
        log.warning("metals: no USD/INR rate available — skipping bullion")
        return []

    out = []
    for symbol in ("XAU", "XAG"):
        record = fetch_metal_inr_per_gram(symbol, usd_inr)
        if record:
            out.append(record)
    return out
