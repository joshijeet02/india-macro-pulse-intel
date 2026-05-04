"""
Extract structured content from an RBI press release HTML page.

The press release content is inline HTML (no PDF). Strategy:
1. Strip nav/footer/script noise.
2. Find the date marker ("Date : Apr 08, 2026") to anchor the content start.
3. Extract numbered paragraphs (1., 2., 3., ...) which is RBI's stable format
   for both Governor's Statements and Minutes.
4. Footnote markers (single-digit numbers on their own lines, between
   paragraphs) are stripped — they're rendered as superscripts on the source
   page and break paragraph continuity in the text dump.

Returns a structured dict; None on parse failure.
"""
from __future__ import annotations

import logging
import re
from html.parser import HTMLParser
from typing import Optional

log = logging.getLogger(__name__)

_DATE_PATTERNS = [
    r"Date\s*:\s*(?P<date>[A-Za-z]+\s+\d{1,2}\s*,\s*\d{4})",
    r"Date:\s*(?P<date>[A-Za-z]+\s+\d{1,2}\s*,\s*\d{4})",
]

_PARAGRAPH_RX = re.compile(r"^\d+\.\s")
_FOOTNOTE_RX = re.compile(r"^\d{1,2}$")


class _TextExtractor(HTMLParser):
    """Strip script/style/nav and produce a list of stripped text lines."""

    SKIP = {"script", "style", "meta", "link", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            d = data.strip()
            if d:
                self.parts.append(d)


def extract_press_release(html: str) -> Optional[dict]:
    """
    Parse RBI press release HTML and return structured content.

    Returns dict with keys:
      - publication_date: 'YYYY-MM-DD' or None
      - title: the document's H1/heading text
      - paragraphs: list[str] — each numbered paragraph, footnote-stripped
      - full_text: '\\n\\n'.join(paragraphs)
      - press_release_id: '2026-2027/37' style internal RBI ID, if found
    """
    extractor = _TextExtractor()
    try:
        extractor.feed(html)
    except Exception as exc:
        log.warning(f"HTML parse failed: {exc}")
        return None
    lines = extractor.parts

    # Find the date anchor — start of actual content
    start_idx, raw_date = _find_date_anchor(lines)
    if start_idx is None:
        log.warning("No 'Date :' anchor found in press release")
        return None

    # Title is typically the line right after the date
    title = ""
    if start_idx + 1 < len(lines):
        candidate = lines[start_idx + 1]
        if not _PARAGRAPH_RX.match(candidate):
            title = candidate

    # Walk forward, accumulating paragraphs. Stop when we hit the boilerplate
    # footer ("(Brij Raj)" / "Press Release: 2026-2027/37" / "Concluding Remarks"
    # is part of body but the references/footnotes section is junk).
    paragraphs: list[str] = []
    current: list[str] = []
    end_markers = ("Press Release:", "Released on", "Click here", "Cookie ")
    rbi_internal_id: Optional[str] = None

    body_start = start_idx + 1 + (1 if title else 0)
    for line in lines[body_start:]:
        # Stop at known footer markers
        if any(line.startswith(m) for m in end_markers):
            m = re.search(r"Press Release:\s*([\d/-]+)", line)
            if m:
                rbi_internal_id = m.group(1)
            break

        # Skip pure footnote markers (single 1-2 digit lines)
        if _FOOTNOTE_RX.match(line):
            continue

        if _PARAGRAPH_RX.match(line):
            if current:
                paragraphs.append(" ".join(current).strip())
            current = [line]
        else:
            current.append(line)

    if current:
        paragraphs.append(" ".join(current).strip())

    if not paragraphs:
        log.warning("Extracted 0 paragraphs — page format may have changed")
        return None

    publication_date = _normalize_date(raw_date)

    return {
        "publication_date":  publication_date,
        "title":             title,
        "paragraphs":        paragraphs,
        "full_text":         "\n\n".join(paragraphs),
        "press_release_id":  rbi_internal_id,
    }


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _find_date_anchor(lines: list[str]) -> tuple[Optional[int], Optional[str]]:
    """Find the "Date : <date>" line and return its index + the raw date string."""
    for i, line in enumerate(lines):
        for pat in _DATE_PATTERNS:
            m = re.match(pat, line)
            if m:
                return i, m.group("date")
    return None, None


_MONTHS = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    "january": "01", "february": "02", "march": "03", "april": "04",
    "june": "06", "july": "07", "august": "08", "september": "09",
    "october": "10", "november": "11", "december": "12",
}


def _normalize_date(raw: str) -> Optional[str]:
    """'Apr 08, 2026' → '2026-04-08'."""
    m = re.match(
        r"([A-Za-z]+)\s+(\d{1,2})\s*,\s*(\d{4})",
        raw.strip(),
    )
    if not m:
        return None
    month_name = m.group(1).lower()
    day = int(m.group(2))
    year = int(m.group(3))
    month = _MONTHS.get(month_name)
    if not month:
        return None
    return f"{year:04d}-{month}-{day:02d}"
