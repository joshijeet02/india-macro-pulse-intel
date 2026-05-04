"""
Cross-reference between macro-pulse and rbi-comms.

When the user sees a fresh CPI/IIP print, they should also see what the RBI
projected for that horizon — that's the analytic value-add. The Indian rates
analyst's classic move is "the print came in 30bp below RBI's projection",
and we surface that gap automatically.

We read the sibling rbi-comms system's JSON sidecar directly. No HTTP, no
shared DB — both apps live in the same git repo on Streamlit Cloud.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


def _rbi_comms_root() -> Optional[Path]:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "systems" / "01-rbi-comms"
        if candidate.is_dir():
            return candidate
    return None


def _rbi_updates_path() -> Optional[Path]:
    root = _rbi_comms_root()
    if root is None:
        return None
    p = root / "data" / "rbi_communications.json"
    return p if p.exists() else None


# ─── Public: latest RBI projection ───────────────────────────────────────────

def latest_mpc_decision() -> Optional[dict]:
    """
    Return the most recent MPC decision recovered from the rbi-comms JSON
    sidecar. Returns None if the file is absent (sibling app not deployed
    or no autonomous refresh has fired yet).

    Output keys:
      - meeting_date, repo_rate, repo_rate_change_bps
      - vote_for, vote_against
      - stance_label
      - cpi_projection_curr_value, cpi_projection_curr_fy
      - gdp_projection_curr_value, gdp_projection_curr_fy
      - title, url (so the UI can deep-link to RBI)
    """
    p = _rbi_updates_path()
    if p is None:
        return None
    try:
        data = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning(f"rbi-comms sidecar unreadable: {exc}")
        return None

    docs = data.get("documents") or []
    statements = [
        d for d in docs
        if d.get("kind") == "mpc_statement" and d.get("decision")
    ]
    if not statements:
        return None

    latest = max(statements, key=lambda d: d.get("published_at") or "")
    decision = latest.get("decision") or {}
    return {
        "meeting_date":              decision.get("meeting_date") or latest.get("published_at"),
        "repo_rate":                 decision.get("repo_rate"),
        "repo_rate_change_bps":      decision.get("repo_rate_change_bps", 0),
        "vote_for":                  decision.get("vote_for"),
        "vote_against":              decision.get("vote_against"),
        "stance_label":              decision.get("stance_label"),
        "cpi_projection_curr_value": decision.get("cpi_projection_curr_value"),
        "cpi_projection_curr_fy":    decision.get("cpi_projection_curr_fy"),
        "gdp_projection_curr_value": decision.get("gdp_projection_curr_value"),
        "gdp_projection_curr_fy":    decision.get("gdp_projection_curr_fy"),
        "title":                     latest.get("title", ""),
        "url":                       latest.get("url", ""),
    }


# ─── UI-shaped summaries ─────────────────────────────────────────────────────

def cpi_context_for_print(cpi_print: dict) -> Optional[dict]:
    """
    Given a current CPI print, return the comparison panel data:
    {rbi_projection, projection_fy, surprise_pp, comment, mpc_meeting_date,
     stance, mpc_url}. None if no RBI data available.

    `surprise_pp` is the print MINUS RBI's projection — positive means the
    print came in HOTTER than RBI expected.
    """
    decision = latest_mpc_decision()
    if decision is None or decision.get("cpi_projection_curr_value") is None:
        return None

    rbi_proj = decision["cpi_projection_curr_value"]
    print_yoy = cpi_print.get("headline_yoy")
    surprise = (
        round(print_yoy - rbi_proj, 2)
        if print_yoy is not None else None
    )

    if surprise is None:
        comment = "Latest CPI print not available for comparison."
    elif abs(surprise) < 0.20:
        comment = "Print is in line with RBI's projection."
    elif surprise > 0:
        comment = (
            f"Print is **{surprise:+.2f}pp above** RBI's projected path — "
            f"hotter than the central bank expected."
        )
    else:
        comment = (
            f"Print is **{surprise:+.2f}pp below** RBI's projected path — "
            f"softer than the central bank expected."
        )

    return {
        "rbi_projection":   rbi_proj,
        "projection_fy":    decision.get("cpi_projection_curr_fy"),
        "surprise_pp":      surprise,
        "comment":          comment,
        "mpc_meeting_date": decision.get("meeting_date"),
        "stance":           decision.get("stance_label"),
        "mpc_url":          decision.get("url"),
    }


def gdp_context() -> Optional[dict]:
    """For an IIP-tab panel: RBI's GDP projection alongside latest IIP."""
    decision = latest_mpc_decision()
    if decision is None or decision.get("gdp_projection_curr_value") is None:
        return None
    return {
        "rbi_gdp_projection":     decision["gdp_projection_curr_value"],
        "projection_fy":          decision.get("gdp_projection_curr_fy"),
        "mpc_meeting_date":       decision.get("meeting_date"),
        "stance":                 decision.get("stance_label"),
        "mpc_url":                decision.get("url"),
        "repo_rate":              decision.get("repo_rate"),
    }
