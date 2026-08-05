
"""
Monthly average bullion prices in INR, back-dated.

Why this exists:

The live snapshot store only knows prices from the day we first fetched. For
the July print that is useless — July was over before we started watching, so
the measured contribution to the July estimate was exactly zero while the page
claimed to be "computed from current prices". That gap is the difference
between a tool and an overstatement.

Gold and silver are the one part of the basket where the gap is closable.
Unlike Amazon listings, bullion has a public daily price history, so June's and
July's average prices can be measured after the fact rather than assumed. The
June -> July move becomes an observation, not a guess.

Method mirrors how a monthly index is actually built: average the daily prices
across the calendar month, in INR, converting each day at that day's exchange
rate. Converting a monthly average price at a monthly average rate is not the
same number, and the difference is real when the rupee moves within the month —
which it did, 94.72 to 96.26 between mid-June and mid-July.

Grocery has no equivalent: Amazon does not publish price history, so the
basket cannot contribute to a month that ended before observation began. It
starts contributing to the first print whose month we observe throughout.
"""
from __future__ import annotations

import json
import logging
import statistics
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import requests

log = logging.getLogger(__name__)

# Front-month futures track spot closely enough for a month-over-month ratio,
# which is all the index needs — a constant level offset cancels in the ratio.
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range={rng}&interval=1d"
SYMBOLS = {"gold": "GC=F", "silver": "SI=F"}

FX_RANGE = "https://api.frankfurter.dev/v1/{start}..{end}?base=USD&symbols=INR"

TROY_OZ_IN_GRAMS = 31.1034768

# Indian jewellery demand is predominantly gold by value; silver is the smaller
# share. Same split used by the live fetcher so the two are comparable.
GOLD_SHARE = 0.85
SILVER_SHARE = 0.15

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
FETCH_TIMEOUT = 12


def _daily_closes(symbol: str, rng: str = "6mo") -> dict[str, float]:
    """Daily closes keyed 'YYYY-MM-DD'. Empty on any failure."""
    try:
        payload = requests.get(
            YAHOO_CHART.format(symbol=symbol, rng=rng),
            headers=HEADERS, timeout=FETCH_TIMEOUT,
        ).json()
        result = payload["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]
        out: dict[str, float] = {}
        for stamp, close in zip(result["timestamp"], closes):
            if close:
                out[date.fromtimestamp(stamp).isoformat()] = float(close)
        return out
    except Exception as exc:
        log.warning(f"metals_history: {symbol} failed: {exc}")
        return {}


def _daily_fx(start: str, end: str, attempts: int = 3) -> dict[str, float]:
    """
    Daily USD/INR keyed 'YYYY-MM-DD'.

    Retried: the range endpoint returns a few months of data and occasionally
    times out under load. Failing outright would drop bullion from the measured
    set and silently push it back into the assumption, which is exactly the
    substitution this module exists to prevent — so it is worth a retry before
    giving up.
    """
    for attempt in range(1, attempts + 1):
        try:
            payload = requests.get(
                FX_RANGE.format(start=start, end=end),
                headers=HEADERS,
                timeout=FETCH_TIMEOUT,
            ).json()
            rates = {d: v["INR"] for d, v in (payload.get("rates") or {}).items() if v.get("INR")}
            if rates:
                return rates
        except Exception as exc:
            log.warning(f"metals_history: FX range attempt {attempt} failed: {exc}")
    return {}


def monthly_average_inr_per_gram(
    closes: dict[str, float],
    fx: dict[str, float],
    year_month: str,
) -> Optional[float]:
    """
    Average INR-per-gram across a calendar month.

    Each day is converted at ITS OWN exchange rate before averaging. Averaging
    the dollar price and converting once at a monthly average rate gives a
    different figure whenever the rupee moves within the month, and the whole
    point of this module is to measure rather than approximate.
    """
    values = [
        close * fx[day] / TROY_OZ_IN_GRAMS
        for day, close in closes.items()
        if day.startswith(year_month) and day in fx
    ]
    return statistics.mean(values) if values else None


def measured_bullion_mom(from_month: str, to_month: str) -> Optional[dict]:
    """
    Measured month-over-month change in the INR bullion blend.

    Returns a dict with the ratio and both monthly averages, or None if either
    month lacks data. None means "we could not measure this" and must not be
    silently read as zero change — that is precisely the substitution this
    module exists to stop.
    """
    start = f"{min(from_month, to_month)}-01"
    end = datetime.now(timezone.utc).date().isoformat()
    fx = _daily_fx(start, end)
    if not fx:
        return None

    averages: dict[str, dict[str, float]] = {}
    for metal, symbol in SYMBOLS.items():
        closes = _daily_closes(symbol)
        if not closes:
            continue
        for month in (from_month, to_month):
            value = monthly_average_inr_per_gram(closes, fx, month)
            if value is not None:
                averages.setdefault(month, {})[metal] = value

    def blend(month: str) -> Optional[float]:
        entry = averages.get(month) or {}
        if "gold" not in entry:
            return None
        if "silver" not in entry:
            return entry["gold"]
        return GOLD_SHARE * entry["gold"] + SILVER_SHARE * entry["silver"]

    earlier, later = blend(from_month), blend(to_month)
    if not earlier or not later or earlier <= 0:
        return None

    return {
        "from_month": from_month,
        "to_month": to_month,
        "from_inr_per_gram": round(earlier, 2),
        "to_inr_per_gram": round(later, 2),
        "mom_pct": round((later / earlier - 1) * 100, 3),
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }


# ─── Cached result, written by the daily job ─────────────────────────────────

MEASURED_PATH = Path(__file__).parent.parent / "data" / "measured_moms.json"


def save_measured(record: dict) -> None:
    """Persist a measurement so the app never has to fetch it."""
    existing = load_measured()
    existing[f"{record['from_month']}->{record['to_month']}"] = record
    payload = {
        "_comment": (
            "Month-over-month moves measured from back-dated price history, "
            "written by scripts/fetch_live_prices.py. The app READS this and "
            "never fetches it: an earlier version computed it on page load and "
            "a single slow FX call blocked the whole render for up to a minute."
        ),
        "measured": existing,
    }
    MEASURED_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = MEASURED_PATH.with_suffix(MEASURED_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    tmp.replace(MEASURED_PATH)


def load_measured() -> dict:
    if not MEASURED_PATH.exists():
        return {}
    try:
        payload = json.loads(MEASURED_PATH.read_text())
        return payload.get("measured", {}) if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        log.warning(f"metals_history: cannot read cache: {exc}")
        return {}


def cached_bullion_mom(from_month: str, to_month: str) -> Optional[dict]:
    """Read a previously measured move. Never makes a network call."""
    return load_measured().get(f"{from_month}->{to_month}")
