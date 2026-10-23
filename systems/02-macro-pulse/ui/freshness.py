"""
"Data as of" line under the title, and a warning when the data has gone stale.

The app once sat three months behind MOSPI with nothing on screen to say so:
the Nowcast kept estimating July long after September was published, and
read as current to anyone who did not already know the calendar. Staleness
must never be silent again, so the date the data runs to is always shown,
and the page says so plainly when it falls behind.

New module rather than an addition to _theme.py, for the reason given in
ui/header_status.py.
"""
from __future__ import annotations

import zoneinfo
from datetime import date, datetime

import streamlit as st

# CPI publishes monthly, so the newest print is normally under 35 days old.
# Past 45, at least one release has been missed.
STALE_AFTER_DAYS = 45

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _month_name(reference_month: str) -> str:
    year, month = reference_month.split("-")
    return f"{_MONTHS[int(month) - 1]} {year}"


def _long_date(d: date) -> str:
    return f"{d.day} {_MONTHS[d.month - 1]} {d.year}"


def freshness(latest_cpi: dict | None, latest_iip: dict | None, today: date) -> dict:
    """
    What the freshness line says, and whether to warn. Pure, so it can be tested.

    "As of" is the newest official release date in the store, CPI or IIP.
    Stale is judged on CPI alone: it is the series the Nowcast is built on.
    """
    releases = [r for r in (latest_cpi, latest_iip) if r and r.get("release_date")]
    if not releases:
        return {"line": "No official data loaded.", "stale": True, "age_days": None}

    as_of = max(date.fromisoformat(r["release_date"]) for r in releases)
    parts = []
    if latest_cpi:
        parts.append(f"CPI for {_month_name(latest_cpi['reference_month'])}")
    if latest_iip:
        parts.append(f"IIP for {_month_name(latest_iip['reference_month'])}")
    line = f"Data as of {_long_date(as_of)}: latest official {' and '.join(parts)}."

    age_days = None
    stale = True
    if latest_cpi and latest_cpi.get("release_date"):
        age_days = (today - date.fromisoformat(latest_cpi["release_date"])).days
        stale = age_days > STALE_AFTER_DAYS
    return {"line": line, "stale": stale, "age_days": age_days}


def render_freshness() -> None:
    from db.store import CPIStore, IIPStore

    today = datetime.now(zoneinfo.ZoneInfo("Asia/Kolkata")).date()
    cpi, iip = CPIStore().get_latest(), IIPStore().get_latest()
    info = freshness(cpi, iip, today)

    st.caption(info["line"])
    if info["stale"]:
        age = (f"{info['age_days']} days ago" if info["age_days"] is not None
               else "at an unknown date")
        st.warning(
            f"**This page may be out of date.** The newest CPI figure here was "
            f"published {age}, and MOSPI publishes a new one every month. The "
            f"estimates below are measured from that older release until the data "
            f"catches up."
        )
