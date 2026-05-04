"""
Extract structured numeric facts from an MPC Governor's Statement / Resolution.

Targets the templated phrasings RBI uses every meeting:
  - Repo rate decision: "policy repo rate ... unchanged at 6.50 per cent" /
    "reduced by 25 basis points to 6.25 per cent"
  - Vote split: "5 members voted in favour ... 1 member voted against"
  - Stance: "remain neutral" / "withdrawal of accommodation" / "remain accommodative"
  - GDP projection: "real GDP growth for 2026-27 is projected at 6.9 per cent"
  - CPI projection: "CPI inflation for 2026-27 is projected at 4.6 per cent"

Returns None on parse failure for any required field; returns a partial dict
when only optional fields fail (e.g. a Minutes document has vote splits but
no projections).

All extracted numbers go through bounds checks. Repo rate ∈ [0, 12].
GDP/CPI projections ∈ [-5, 15]. Vote split sums to 6.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

log = logging.getLogger(__name__)

# Bounds — anything outside is almost certainly a misparse
REPO_RATE_BOUNDS = (0.0, 12.0)
PROJECTION_BOUNDS = (-5.0, 15.0)
MPC_MEMBERS = 6  # statutory composition


# ─── Repo rate ───────────────────────────────────────────────────────────────

_REPO_PATTERNS = [
    # "reduced/increased by N basis points to X.XX per cent" — change decisions
    re.compile(
        r"policy\s+repo\s+rate\s+(?:was\s+)?(?P<dir>reduced|increased|cut|raised)"
        r"\s+by\s+(?P<bps>\d+)\s+basis\s+points?\s+to\s+(?P<rate>\d+(?:\.\d+)?)\s*per\s*cent",
        re.IGNORECASE,
    ),
    # Flexible "policy repo rate ... unchanged at X.XX per cent" — handles "(LAF)"
    # and other parentheticals between the phrase and the rate.
    re.compile(
        r"policy\s+repo\s+rate\b[^.]{0,150}?unchanged\s+at\s+"
        r"(\d+(?:\.\d+)?)\s*per\s*cent",
        re.IGNORECASE | re.DOTALL,
    ),
    # "keep the policy repo rate ... at X.XX per cent" — handles "decided to" prefix
    re.compile(
        r"keep\s+the\s+policy\s+repo\s+rate\b[^.]{0,150}?at\s+"
        r"(\d+(?:\.\d+)?)\s*per\s*cent",
        re.IGNORECASE | re.DOTALL,
    ),
    # Catch-all: "policy repo rate at X.XX per cent"
    re.compile(
        r"policy\s+repo\s+rate\s+at\s+(\d+(?:\.\d+)?)\s*per\s*cent",
        re.IGNORECASE,
    ),
]

# Lookup for changes in basis points (negative for cut)
def _change_sign(direction: str) -> int:
    d = direction.lower()
    if d in ("reduced", "cut"):
        return -1
    if d in ("increased", "raised"):
        return +1
    return 0


def extract_repo_rate(text: str) -> tuple[Optional[float], Optional[int]]:
    """
    Return (repo_rate, change_bps). change_bps is 0 for unchanged decisions.
    """
    for pat in _REPO_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        # Pattern with named change group?
        if "dir" in pat.groupindex:
            try:
                rate = float(m.group("rate"))
                bps = int(m.group("bps")) * _change_sign(m.group("dir"))
            except (ValueError, TypeError):
                continue
            if REPO_RATE_BOUNDS[0] <= rate <= REPO_RATE_BOUNDS[1]:
                return rate, bps
        else:
            try:
                rate = float(m.group(1))
            except (ValueError, TypeError):
                continue
            if REPO_RATE_BOUNDS[0] <= rate <= REPO_RATE_BOUNDS[1]:
                return rate, 0
    return None, None


# ─── Vote split ──────────────────────────────────────────────────────────────

# "5 members voted in favour ... 1 member voted against"
# "Dr. ... voted against the proposed reduction"
_VOTE_PATTERNS = [
    # "5 members voted in favour ... 1 member voted against"
    # Also: "5 members voted in favour, 1 against" (members optional after comma)
    re.compile(
        r"(?P<for>\d+)\s+members?\s+(?:voted\s+)?in\s+favou?r"
        r"[^.]*?(?P<against>\d+)\s+(?:members?\s+)?(?:voted\s+)?against",
        re.IGNORECASE | re.DOTALL,
    ),
    # "vote by 5 to 1"
    re.compile(
        r"vote(?:d|s)?\s+by\s+(?P<for>\d+)\s+to\s+(?P<against>\d+)",
        re.IGNORECASE,
    ),
    # Various unanimity phrasings — RBI uses different ones in different cycles:
    # "voted unanimously to keep / reduce ..."
    # "MPC voted unanimously"
    # "all six members ... voted unanimously"
    # "All members of the MPC voted to ..."
    re.compile(
        r"(?:MPC|members?|committee)\s+(?:[a-z\s]{0,40})?voted\s+unanimous(?:ly)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"unanimous(?:ly)?\s+(?:decision|vote|voted)",
        re.IGNORECASE,
    ),
]


def extract_vote_split(text: str) -> tuple[Optional[int], Optional[int]]:
    """Return (for, against). Both 6,0 if unanimous; both None if not found."""
    # Try the exact-numbers patterns first
    for pat in _VOTE_PATTERNS[:2]:
        m = pat.search(text)
        if not m:
            continue
        try:
            f = int(m.group("for"))
            a = int(m.group("against"))
        except (ValueError, TypeError):
            continue
        # Sanity: should sum to 6 (statutory MPC size)
        if 0 <= f <= MPC_MEMBERS and 0 <= a <= MPC_MEMBERS and (f + a) == MPC_MEMBERS:
            return f, a

    # Unanimity patterns
    for pat in _VOTE_PATTERNS[2:]:
        if pat.search(text):
            return MPC_MEMBERS, 0

    return None, None


# ─── Stance phrase ───────────────────────────────────────────────────────────

# Order matters — most specific first, since "neutral" appears in some
# accommodative-stance statements as a transitional phrase.
_STANCE_PHRASES = [
    ("withdrawal_of_accommodation", "withdrawal of accommodation"),
    ("calibrated_tightening",        "calibrated tightening"),
    ("calibrated_withdrawal",        "calibrated withdrawal of accommodation"),
    ("accommodative",                "remain accommodative"),
    ("accommodative",                "stance is accommodative"),
    ("accommodative",                "accommodative stance"),
    ("neutral",                      "remain neutral"),
    ("neutral",                      "neutral stance"),
    ("neutral",                      "stance to neutral"),
]


def extract_stance(text: str) -> tuple[Optional[str], Optional[str]]:
    """
    Return (stance_label, raw_phrase).

    Stance labels: 'accommodative' | 'neutral' | 'withdrawal_of_accommodation' |
    'calibrated_tightening' | 'calibrated_withdrawal'.
    """
    lc = text.lower()
    # Look for the most specific match (longest phrase wins on ties via order)
    matches: list[tuple[str, str, int]] = []
    for label, phrase in _STANCE_PHRASES:
        idx = lc.find(phrase.lower())
        if idx >= 0:
            matches.append((label, phrase, idx))

    if not matches:
        return None, None

    # Prefer the EARLIEST mention — RBI states the stance early in the document.
    matches.sort(key=lambda m: m[2])
    label, phrase, _ = matches[0]
    return label, phrase


# ─── Projections ─────────────────────────────────────────────────────────────

# "real GDP growth for 2026-27 is projected at 6.9 per cent, with Q1 at 6.8..."
_GDP_PROJ_RX = re.compile(
    r"real\s+GDP\s+growth\s+for\s+(?P<fy>\d{4}[-–]\d{2,4})"
    r"\s+is\s+projected\s+at\s+(?P<rate>-?\d+(?:\.\d+)?)\s*per\s*cent",
    re.IGNORECASE | re.DOTALL,
)

# "CPI inflation for 2026-27 is projected at 4.6 per cent ..."
_CPI_PROJ_RX = re.compile(
    r"CPI\s+inflation\s+for\s+(?P<fy>\d{4}[-–]\d{2,4})"
    r"\s+is\s+projected\s+at\s+(?P<rate>-?\d+(?:\.\d+)?)\s*per\s*cent",
    re.IGNORECASE | re.DOTALL,
)


def extract_projections(text: str) -> dict:
    """
    Return dict with optional keys:
      gdp_projection_curr_fy, gdp_projection_curr_value,
      cpi_projection_curr_fy, cpi_projection_curr_value
    """
    out: dict = {}

    m = _GDP_PROJ_RX.search(text)
    if m:
        try:
            v = float(m.group("rate"))
            if PROJECTION_BOUNDS[0] <= v <= PROJECTION_BOUNDS[1]:
                out["gdp_projection_curr_fy"] = m.group("fy")
                out["gdp_projection_curr_value"] = v
        except ValueError:
            pass

    m = _CPI_PROJ_RX.search(text)
    if m:
        try:
            v = float(m.group("rate"))
            if PROJECTION_BOUNDS[0] <= v <= PROJECTION_BOUNDS[1]:
                out["cpi_projection_curr_fy"] = m.group("fy")
                out["cpi_projection_curr_value"] = v
        except ValueError:
            pass

    return out


# ─── Combined extractor ──────────────────────────────────────────────────────

def extract_mpc_decision(text: str, publication_date: Optional[str] = None) -> dict:
    """
    Run all extractors and return a single decision record. Missing fields
    are simply absent from the dict (use .get() at the call site).
    """
    repo_rate, repo_change = extract_repo_rate(text)
    vote_for, vote_against = extract_vote_split(text)
    stance_label, stance_phrase = extract_stance(text)
    projections = extract_projections(text)

    record: dict = {
        "meeting_date":         publication_date,
        "repo_rate":            repo_rate,
        "repo_rate_change_bps": repo_change,
        "vote_for":             vote_for,
        "vote_against":         vote_against,
        "stance_label":         stance_label,
        "stance_phrase":        stance_phrase,
        **projections,
    }
    return record
