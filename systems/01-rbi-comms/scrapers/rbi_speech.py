"""
RBI Speech corpus scraper.

Discovery via the speeches RSS feed at https://rbi.org.in/speeches_rss.xml,
which carries the last ~10 speeches by the Governor and Deputy Governors.
Each item links to BS_SpeechesView.aspx?Id=N — the full transcript page.

Note: the RSS only exposes 10 latest items, so backfill requires walking
sequential SpeechIDs (similar to how MPC backfill walked PRIDs). For v1
we rely on the RSS for going-forward discovery + a small hardcoded
historical seed.

Each speech becomes a `documents` row with kind='speech'. Stance engine
runs on the full transcript so the inter-meeting "policy walk" is
quantified.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional

import requests

from scrapers._rbi_api import DEFAULT_HEADERS, fetch_speech
from scrapers.rbi_resolution import extract_press_release  # reuses HTML parser

log = logging.getLogger(__name__)

SPEECH_RSS = "https://rbi.org.in/speeches_rss.xml"

_SPEECH_ID_RX = re.compile(
    r"BS_SpeechesView\.aspx\?Id=(\d+)",
    re.IGNORECASE,
)


def fetch_speech_listing(timeout: int = 15) -> list[dict]:
    """
    Fetch the RBI Speeches RSS feed and return a list of items:
      [{speech_id, title, link, pub_date}, ...]
    """
    try:
        resp = requests.get(SPEECH_RSS, headers=DEFAULT_HEADERS, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.warning(f"speech RSS fetch failed: {exc}")
        return []

    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as exc:
        log.warning(f"speech RSS parse failed: {exc}")
        return []

    items: list[dict] = []
    for item in root.findall(".//item"):
        link = (item.findtext("link") or "").strip()
        title = (item.findtext("title") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        m = _SPEECH_ID_RX.search(link)
        if not m:
            continue
        items.append({
            "speech_id": int(m.group(1)),
            "title":     title,
            "link":      link,
            "pub_date":  pub,
        })
    return items


def fetch_and_parse_speech(speech_id: int) -> Optional[dict]:
    """
    Fetch a single speech by ID and parse it using the same HTML extractor
    as press releases (RBI uses the same template).

    Returns dict with: speech_id, publication_date, title, paragraphs,
    full_text, speaker (best-effort), source_url.
    """
    html = fetch_speech(speech_id)
    if not html:
        return None
    parsed = extract_press_release(html)
    if not parsed:
        return None

    # Best-effort speaker extraction from the title
    # Titles look like "Speech by Governor Sanjay Malhotra at FIBAC 2026"
    speaker = _guess_speaker(parsed.get("title", ""))

    return {
        "speech_id":        speech_id,
        "publication_date": parsed["publication_date"],
        "title":            parsed["title"],
        "paragraphs":       parsed["paragraphs"],
        "full_text":        parsed["full_text"],
        "speaker":          speaker,
        "source_url":       f"https://www.rbi.org.in/Scripts/BS_SpeechesView.aspx?Id={speech_id}",
    }


def _guess_speaker(title: str) -> Optional[str]:
    """Pull a name out of titles like 'Speech by Governor X at Y' or 'X: Y'."""
    if not title:
        return None
    # "Address by <Name>" / "Speech by <Name>" / "Remarks by <Name>"
    m = re.search(
        r"(?:Address|Speech|Remarks|Lecture|Talk)\s+by\s+"
        r"(?:Governor|Deputy\s+Governor|Shri|Smt\.|Dr\.)?\s*"
        r"([A-Z][a-zA-Z\.]+(?:\s+[A-Z][a-zA-Z\.]+){1,3})",
        title,
    )
    if m:
        return m.group(1).strip()
    # Fallback: first proper noun cluster
    m = re.search(r"([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){1,3})", title)
    return m.group(1).strip() if m else None
