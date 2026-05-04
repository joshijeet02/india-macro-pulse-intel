"""
Cross-reference between rbi-comms and macro-pulse.

The whole point: when the user is reading RBI's latest projection ("CPI for
2026-27 is projected at 4.6 per cent"), they should see the actual CPI prints
right next to it. And vice versa — when they're looking at the latest CPI
print on macro-pulse, they should see what RBI projected for that horizon.

Both apps live in the same git repo. macro-pulse persists CPI/IIP into
data/release_updates.json (autonomous additions on top of the hardcoded
CPI_HISTORY / IIP_HISTORY in seed/historical_data.py). rbi-comms reads those
files directly from disk — no HTTP, no shared DB.

If macro-pulse data is unreachable (file missing, malformed, sibling not
checked out), the helpers return None and the UI degrades gracefully to
"latest data unavailable".
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


def _macro_pulse_root() -> Optional[Path]:
    """Locate sibling macro-pulse system. Returns None if not present."""
    here = Path(__file__).resolve()
    # Walk up until we find a `systems/` parent
    for parent in here.parents:
        candidate = parent / "systems" / "02-macro-pulse"
        if candidate.is_dir():
            return candidate
    return None


def _macro_updates_path() -> Optional[Path]:
    root = _macro_pulse_root()
    if root is None:
        return None
    p = root / "data" / "release_updates.json"
    return p if p.exists() else None


def _macro_seed_path() -> Optional[Path]:
    root = _macro_pulse_root()
    if root is None:
        return None
    p = root / "seed" / "historical_data.py"
    return p if p.exists() else None


# ─── Public: latest macro print ──────────────────────────────────────────────

def latest_cpi_print() -> Optional[dict]:
    """
    Return {reference_month, headline_yoy, food_yoy, fuel_yoy, source} for
    the most recent CPI print, or None if unreachable.
    """
    return _latest_indicator("cpi")


def latest_iip_print() -> Optional[dict]:
    return _latest_indicator("iip")


def _latest_indicator(indicator: str) -> Optional[dict]:
    """Pull from JSON sidecar first, fall back to scanning the seed module."""
    p = _macro_updates_path()
    if p is not None:
        try:
            data = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            log.warning(f"macro-pulse {indicator} sidecar unreadable: {exc}")
            data = {}
        entries = data.get(indicator) or []
        latest = _pick_latest(entries, key="reference_month")
        if latest is not None:
            return latest

    # Fall back to parsing the seed module (rough but works without imports)
    seed_path = _macro_seed_path()
    if seed_path is None:
        return None
    return _scan_seed_for_latest(seed_path, indicator)


def _pick_latest(entries: list[dict], key: str) -> Optional[dict]:
    if not entries:
        return None
    valid = [e for e in entries if e.get(key)]
    if not valid:
        return None
    return max(valid, key=lambda e: e[key])


def _scan_seed_for_latest(seed_path: Path, indicator: str) -> Optional[dict]:
    """
    Lightweight parse of the macro-pulse seed module to recover the highest
    reference_month tuple/dict. Avoids importing macro-pulse modules (whose
    side effects — DB init etc. — we do NOT want here).
    """
    try:
        text = seed_path.read_text()
    except OSError:
        return None

    if indicator == "cpi":
        # CPI_HISTORY tuples: ("YYYY-MM", "release_date", headline, food, fuel, consensus)
        import re
        latest_month: Optional[str] = None
        latest_record: Optional[dict] = None
        for m in re.finditer(
            r'\("(\d{4}-\d{2})",\s*"([^"]+)",\s*([\-\d\.]+),\s*([\-\d\.]+|None),\s*([\-\d\.]+|None),\s*([\-\d\.]+|None)\)',
            text,
        ):
            ref = m.group(1)
            if latest_month is None or ref > latest_month:
                latest_month = ref
                latest_record = {
                    "reference_month": ref,
                    "release_date":    m.group(2),
                    "headline_yoy":    _maybe_float(m.group(3)),
                    "food_yoy":        _maybe_float(m.group(4)),
                    "fuel_yoy":        _maybe_float(m.group(5)),
                    "consensus_forecast": _maybe_float(m.group(6)),
                    "source": "macro-pulse seed (CPI_HISTORY)",
                }
        return latest_record

    if indicator == "iip":
        # IIP_HISTORY dicts — we need only reference_month + headline_yoy
        import re
        latest_month: Optional[str] = None
        latest_record: Optional[dict] = None
        for m in re.finditer(
            r'"reference_month":\s*"(\d{4}-\d{2})"[^}]*?"headline_yoy":\s*([\-\d\.]+)',
            text, re.DOTALL,
        ):
            ref = m.group(1)
            if latest_month is None or ref > latest_month:
                latest_month = ref
                latest_record = {
                    "reference_month": ref,
                    "headline_yoy": _maybe_float(m.group(2)),
                    "source": "macro-pulse seed (IIP_HISTORY)",
                }
        return latest_record

    return None


def _maybe_float(s: str) -> Optional[float]:
    if s == "None":
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ─── Convenience: build a UI-ready summary dict ──────────────────────────────

def macro_print_summary() -> dict:
    """
    One call; returns whatever data we have, with `available` flags so the
    UI can decide how much to render.
    """
    cpi = latest_cpi_print()
    iip = latest_iip_print()
    return {
        "available":   bool(cpi or iip),
        "cpi":         cpi,
        "iip":         iip,
        "macro_url":   "https://india-macro-pulse.streamlit.app",
    }
