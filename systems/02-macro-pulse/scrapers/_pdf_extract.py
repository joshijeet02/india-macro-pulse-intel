"""
Shared PDF extraction helpers for MOSPI press release parsers.

Strategy is tiered:
1. Table extraction via pdfplumber — try to find a row whose first cell matches
   the target indicator and read the last numeric in YoY range.
2. Anchored regex fallback — same line as the indicator label, magnitude-bounded.
3. Sanity bounds to reject garbage from either path.

Each public function returns Optional[float]; None means "I don't trust what I
extracted — caller should treat as unknown rather than zero."
"""
from __future__ import annotations

import io
import re
from typing import Iterable, Optional

import requests

# Reasonable bounds for an Indian macro YoY %. CPI headline historically
# ranges roughly -2 to +15; IIP -10 to +20. We use wider bounds to allow for
# extreme single-month prints, but anything outside [-30, 50] is almost
# certainly a misparse (e.g., we caught a weight or an index level).
YOY_BOUNDS = (-30.0, 50.0)


def fetch_pdf_bytes(url: str, headers: dict, timeout: int = 30) -> bytes:
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def open_pdf_text(pdf_bytes: bytes, max_pages: int = 6) -> str:
    """Concatenate text from up to max_pages of the PDF."""
    import pdfplumber
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages[:max_pages])


def open_pdf_tables(pdf_bytes: bytes, max_pages: int = 6) -> list[list[list[str]]]:
    """Return list of tables (each a list of rows; rows are list[str])."""
    import pdfplumber
    tables: list[list[list[str]]] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages[:max_pages]:
            for tbl in page.extract_tables() or []:
                cleaned = [[(cell or "").strip() for cell in row] for row in tbl]
                tables.append(cleaned)
    return tables


# ─── Table-based extraction ──────────────────────────────────────────────────

def _row_label_matches(cell: str, label: str) -> bool:
    """Loose match — case-insensitive, ignores whitespace and punctuation noise."""
    norm = lambda s: re.sub(r"[^a-z0-9]+", "", s.lower())
    return norm(label) in norm(cell)


def _last_yoy_in_row(row: Iterable[str]) -> Optional[float]:
    """
    Return the LAST numeric in the row that is within YOY_BOUNDS.

    MOSPI tables typically have: [Indicator | Weight | Index Apr | Index Mar | YoY Apr | YoY Mar]
    or similar. The last bounded numeric is therefore reliably a YoY %.

    Weight values are positive integers/decimals (10-1000); index levels are
    typically 100-300. Both are excluded by YOY_BOUNDS.
    """
    candidate: Optional[float] = None
    for cell in row:
        # Pull all numbers out of the cell (handles "(-3.5)", "5.2*" etc.)
        for m in re.finditer(r"-?\d+\.\d+", cell):
            try:
                v = float(m.group(0))
            except ValueError:
                continue
            if YOY_BOUNDS[0] <= v <= YOY_BOUNDS[1]:
                candidate = v  # keep overwriting → last bounded numeric wins
    return candidate


def find_yoy_in_tables(
    tables: list[list[list[str]]], label: str
) -> Optional[float]:
    """
    Scan all tables for a row whose first non-empty cell matches `label`,
    then extract the last YoY-bounded number from that row.

    Returns None if no matching row found or no plausible YoY value.
    """
    for tbl in tables:
        for row in tbl:
            if not row:
                continue
            # First non-empty cell is the label cell
            first = next((c for c in row if c), "")
            if not first:
                continue
            if _row_label_matches(first, label):
                yoy = _last_yoy_in_row(row)
                if yoy is not None:
                    return yoy
    return None


# ─── Regex fallback (more anchored than original) ────────────────────────────

def find_yoy_in_text(text: str, label: str) -> Optional[float]:
    """
    Anchored regex: the label and the numeric must be on the same logical line
    or close together (within ~120 chars). The number must be in YOY_BOUNDS
    and in a context that suggests percent (followed by %, "per cent", or end-of-line).

    Trade-off vs original regex (which was greedy across lines): we miss
    cases where layout splits label and value, but we don't accidentally
    capture an index level from three paragraphs away.
    """
    # Build a pattern that finds the label followed within ~120 chars by a
    # decimal that's optionally followed by % or end-of-line.
    label_pattern = re.escape(label).replace(r"\ ", r"\s+")
    pattern = (
        rf"{label_pattern}[^\n\r]{{0,120}}?"
        rf"(?P<val>-?\d+\.\d+)\s*(?:%|per\s*cent|$|\s)"
    )
    for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
        try:
            v = float(m.group("val"))
        except (TypeError, ValueError):
            continue
        if YOY_BOUNDS[0] <= v <= YOY_BOUNDS[1]:
            return v
    return None


# ─── Combined extractor ──────────────────────────────────────────────────────

def extract_yoy(
    tables: list[list[list[str]]],
    text: str,
    label: str,
    aliases: tuple[str, ...] = (),
) -> Optional[float]:
    """
    Try table extraction across all label aliases, then text-anchored regex.

    aliases: alternative labels MOSPI sometimes uses (e.g.,
    "Consumer non-durables" vs "Consumer Non-Durables").
    """
    candidates = (label, *aliases)
    for alias in candidates:
        v = find_yoy_in_tables(tables, alias)
        if v is not None:
            return v
    for alias in candidates:
        v = find_yoy_in_text(text, alias)
        if v is not None:
            return v
    return None


# ─── Reference-month extraction ──────────────────────────────────────────────

_MONTHS = {
    "January": "01", "February": "02", "March": "03", "April": "04",
    "May": "05", "June": "06", "July": "07", "August": "08",
    "September": "09", "October": "10", "November": "11", "December": "12",
}


def extract_reference_month(text: str) -> Optional[str]:
    """
    MOSPI press releases say things like 'Quick Estimates of Index of
    Industrial Production for March, 2026' or 'CPI for the month of
    March, 2026'. Find the FIRST Month-Year pair in the document.

    Returns 'YYYY-MM' or None.
    """
    pattern = (
        r"(?P<month>January|February|March|April|May|June|July|August|"
        r"September|October|November|December)[,\s]+(?P<year>\d{4})"
    )
    m = re.search(pattern, text)
    if not m:
        return None
    return f"{m.group('year')}-{_MONTHS[m.group('month')]}"


# ─── Sanity ──────────────────────────────────────────────────────────────────

def sanity_check_release(payload: dict, required: tuple[str, ...]) -> tuple[bool, str]:
    """
    Verify a parsed release dict looks plausible.

    Returns (ok, reason). ok=False means caller should NOT persist this record.
    """
    if not payload.get("reference_month"):
        return False, "missing reference_month"

    headline = payload.get("headline_yoy")
    if headline is None:
        return False, "missing headline_yoy"
    if not (YOY_BOUNDS[0] <= float(headline) <= YOY_BOUNDS[1]):
        return False, f"headline_yoy={headline} outside plausible bounds"

    # At least 50% of the required component fields must have parsed
    parsed = sum(1 for k in required if payload.get(k) is not None)
    if parsed < len(required) // 2:
        return False, (
            f"only {parsed}/{len(required)} required components parsed — "
            f"PDF layout likely changed"
        )

    return True, "ok"
