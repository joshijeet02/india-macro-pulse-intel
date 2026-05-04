"""
Discovery and fetching helpers for RBI press releases.

Result of the spike documented in docs/PRD-2026-05-rbi-comms-redesign.md §13:

* `https://rbi.org.in/Scripts/Annualpolicy.aspx` is the canonical landing page
  for the CURRENT MPC cycle. Server-rendered HTML; lists the Resolution /
  Governor's Statement (PRID), Minutes (PRID), and Press Conference Transcript
  (Speech ID) for the most recent meeting.
* `https://rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=N` returns the
  full press release text inline as HTML — but ONLY when called with a
  `Referer` header (otherwise returns the generic listing page).
* `https://rbi.org.in/pressreleases_rss.xml` exposes the last 10 press releases
  (mostly daily money-market ops; rarely contains the MPC document fresh).

Strategy: poll Annualpolicy.aspx for the current cycle's PRIDs; fetch each
via BS_PressReleaseDisplay.aspx + Referer. RSS is too noisy to be the trigger.

Historical backfill is by hardcoded PRIDs in seed/historical_data.py — RBI
doesn't expose a clean archive endpoint without ASP.NET PostBack scraping,
which is brittle. PRIDs are sequential integers and stable across years.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import requests

log = logging.getLogger(__name__)

ANNUALPOLICY_URL = "https://rbi.org.in/Scripts/Annualpolicy.aspx"
PRESS_RELEASE_URL = "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx"
SPEECH_URL = "https://www.rbi.org.in/Scripts/BS_SpeechesView.aspx"

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (research bot; india-macro-pulse; "
        "joshijeet02+rbi-bot@gmail.com)"
    ),
    "Referer": "https://rbi.org.in/Scripts/Annualpolicy.aspx",
    "Accept": "text/html,application/xhtml+xml",
}


def fetch_annualpolicy_landing(timeout: int = 15) -> Optional[str]:
    """Return the HTML of /Scripts/Annualpolicy.aspx, or None on failure."""
    try:
        resp = requests.get(
            ANNUALPOLICY_URL,
            headers={**DEFAULT_HEADERS, "Referer": "https://rbi.org.in/"},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        log.warning(f"Annualpolicy.aspx fetch failed: {exc}")
        return None


def discover_current_cycle_documents(html: str) -> list[dict]:
    """
    Parse the Annualpolicy landing page and return the documents listed for
    the most recent MPC cycle. Each entry has:
      - kind: 'mpc_statement' | 'mpc_minutes' | 'press_conference' | 'other'
      - prid: int (for press releases) or None
      - speech_id: int (for speeches) or None
      - title: str
      - url: str (absolute)
    """
    out: list[dict] = []
    pattern = re.compile(
        r'<a\s+href="(?P<url>[^"]+)"[^>]*>(?P<title>[^<]{5,300})</a>',
        re.IGNORECASE,
    )
    for m in pattern.finditer(html):
        url = m.group("url")
        title = m.group("title").strip()
        kind = _classify(title)
        if kind == "other":
            continue

        prid = _extract_prid(url)
        speech_id = _extract_speech_id(url)
        if not (prid or speech_id):
            continue

        out.append({
            "kind": kind,
            "prid": prid,
            "speech_id": speech_id,
            "title": title,
            "url": url if url.startswith("http") else f"https://rbi.org.in{url}",
        })

    # Dedupe by (kind, prid|speech_id)
    seen: set[tuple] = set()
    deduped: list[dict] = []
    for d in out:
        key = (d["kind"], d["prid"] or d["speech_id"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(d)
    return deduped


def fetch_press_release(prid: int, timeout: int = 30) -> Optional[str]:
    """Fetch a single press release page by PRID. Returns raw HTML."""
    try:
        resp = requests.get(
            PRESS_RELEASE_URL,
            params={"prid": prid},
            headers=DEFAULT_HEADERS,
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        log.warning(f"PressRelease prid={prid} fetch failed: {exc}")
        return None


def fetch_speech(speech_id: int, timeout: int = 30) -> Optional[str]:
    try:
        resp = requests.get(
            SPEECH_URL,
            params={"Id": speech_id},
            headers={**DEFAULT_HEADERS, "Referer": "https://rbi.org.in/Scripts/BS_SpeechesView.aspx"},
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        log.warning(f"Speech id={speech_id} fetch failed: {exc}")
        return None


# ─── Internals ───────────────────────────────────────────────────────────────

def _classify(title: str) -> str:
    """Classify a document by its title — mpc_statement, mpc_minutes, etc."""
    t = title.lower()
    if "minutes" in t and ("monetary policy" in t or "mpc" in t):
        return "mpc_minutes"
    if "press conference" in t or "post-monetary policy" in t:
        return "press_conference"
    if (
        "governor" in t and "statement" in t
    ) or (
        "monetary policy statement" in t
    ) or (
        "resolution" in t and ("monetary policy" in t or "mpc" in t)
    ):
        return "mpc_statement"
    return "other"


_PRID_RX = re.compile(r"prid=(\d+)", re.IGNORECASE)
_SPEECH_RX = re.compile(r"BS_SpeechesView\.aspx\?Id=(\d+)", re.IGNORECASE)


def _extract_prid(url: str) -> Optional[int]:
    m = _PRID_RX.search(url)
    return int(m.group(1)) if m else None


def _extract_speech_id(url: str) -> Optional[int]:
    m = _SPEECH_RX.search(url)
    return int(m.group(1)) if m else None
