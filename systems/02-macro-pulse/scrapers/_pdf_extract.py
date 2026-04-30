"""
Shared PDF extraction helpers for MOSPI press release parsers.

After verifying against a real April 2026 IIP PDF, the original "table-first
+ generic regex" strategy was found to mis-extract on two predictable axes:

  1. Reference month: MOSPI puts the RELEASE date ("April 28th, 2026") on
     line 1 and the REFERENCE month ("MARCH 2026") on line 13. A naive
     "first month-year pair" regex grabs the wrong one.

  2. Use-based YoY values: MOSPI's prose uses VALUE-then-LABEL
     ("2.2 percent in Primary goods, 14.6 percent in Capital goods, ...").
     A generic LABEL-followed-by-number regex matches the NEXT label's value,
     producing a one-position shift across all components.

The new strategy is structured-prose extraction: target the templated
highlight sentences MOSPI uses every release. The IIP press release follows
a stable phrase pattern; same goes for CPI. We anchor on those phrases.

Generic helpers (table extraction, sanity check) remain available as
fallbacks but are no longer the primary path.
"""
from __future__ import annotations

import io
import logging
import re
from typing import Iterable, Optional

import requests

log = logging.getLogger(__name__)

# Reasonable bounds for an Indian macro YoY %. CPI historically -2 to +15;
# IIP -10 to +20. Wider band allows extreme single-month prints; anything
# outside [-30, 50] is almost certainly a misparse (caught a weight, an
# index level, or a sponsored-tile price rather than a YoY).
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


# ─── Reference month — anchored, not first-match ─────────────────────────────

_MONTHS = {
    "January": "01", "February": "02", "March": "03", "April": "04",
    "May": "05", "June": "06", "July": "07", "August": "08",
    "September": "09", "October": "10", "November": "11", "December": "12",
}

_MONTH_GROUP = (
    r"(?P<month>January|February|March|April|May|June|July|August|"
    r"September|October|November|December)"
)
_YEAR_GROUP = r"(?P<year>\d{4})"

# Anchor patterns for the REFERENCE month. Tried in priority order.
# Patterns have a single named (?P<month>...)/(?P<year>...) group each — the
# "X over Y" phrasing repeats the month/year names, which Python re rejects,
# so we keep that pattern simpler and rely on the surrounding patterns.
_REF_MONTH_PATTERNS = [
    rf"FOR\s+THE\s+MONTH\s+OF\s+{_MONTH_GROUP}\s+{_YEAR_GROUP}",
    rf"for\s+the\s+month\s+of\s+{_MONTH_GROUP}\s+{_YEAR_GROUP}",
    rf"month\s+of\s+{_MONTH_GROUP}\s+{_YEAR_GROUP}",
    rf"in\s+{_MONTH_GROUP}\s+{_YEAR_GROUP}",
]


def extract_reference_month(text: str) -> Optional[str]:
    """
    Return 'YYYY-MM' for the reference period, anchored to MOSPI's typical
    phrasing ("for the month of MARCH 2026"). Avoids picking up the release
    date line ("April 28th, 2026") that comes earlier in the document.
    """
    for pattern in _REF_MONTH_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            month = m.group("month")
            year = m.group("year")
            return f"{int(year):04d}-{_MONTHS[month.title()]}"
    # Last-resort fallback: first month-year pair anywhere.
    m = re.search(rf"{_MONTH_GROUP}[,\s]+{_YEAR_GROUP}", text, re.IGNORECASE)
    if m:
        return f"{int(m.group('year')):04d}-{_MONTHS[m.group('month').title()]}"
    return None


# ─── Structured-prose extractors for IIP highlight sentences ─────────────────

# IIP press release sentence: "growth rates of the three sectors, Mining,
# Manufacturing and Electricity for the month of March 2026 are 5.5 percent,
# 4.3 percent and 0.8 percent respectively."
_IIP_SECTOR_SENTENCE = re.compile(
    r"growth\s+rates?\s+of\s+the\s+three\s+sectors[^.]*?Mining,\s*Manufacturing\s+and\s+Electricity"
    r"[^.]*?are\s+"
    r"(-?\d+(?:\.\d+)?)\s*per\s*cent\s*,\s*"
    r"(-?\d+(?:\.\d+)?)\s*per\s*cent\s+and\s+"
    r"(-?\d+(?:\.\d+)?)\s*per\s*cent",
    re.IGNORECASE | re.DOTALL,
)

# IIP "Key Highlights" sometimes phrases sectoral as: "Mining, Manufacturing
# and Electricity for the month of March 2026 are 5.5 percent, 4.3 percent
# and 0.8 percent respectively." Same pattern, slightly different lead-in.

# IIP use-based sentence: "The corresponding growth rates of IIP as per
# Use-based classification in March 2026 over March 2025 are 2.2 percent
# in Primary goods, 14.6 percent in Capital goods, 3.3 percent in
# Intermediate goods, 6.7 percent in Infrastructure/ Construction Goods,
# 5.3 percent in Consumer durables and 1.1 percent in Consumer non-durables"
_IIP_USEBASED_SENTENCE = re.compile(
    r"Use[-\s]?based\s+classification[^.]*?are\s+"
    r"(-?\d+(?:\.\d+)?)\s*per\s*cent\s+in\s+Primary\s+goods\s*,?\s*"
    r"(-?\d+(?:\.\d+)?)\s*per\s*cent\s+in\s+Capital\s+goods\s*,?\s*"
    r"(-?\d+(?:\.\d+)?)\s*per\s*cent\s+in\s+Intermediate\s+goods\s*,?\s*"
    r"(-?\d+(?:\.\d+)?)\s*per\s*cent\s+in\s+Infrastructure[/\s]+Construction"
    r"[^.]*?(-?\d+(?:\.\d+)?)\s*per\s*cent\s+in\s+Consumer\s+durables"
    r"[^.]*?(-?\d+(?:\.\d+)?)\s*per\s*cent\s+in\s+Consumer\s+non[-\s]?durables",
    re.IGNORECASE | re.DOTALL,
)

# IIP headline: "Index of Industrial Production (IIP) recorded a 4.1 %
# year-on-year growth in March 2026"
_IIP_HEADLINE = re.compile(
    r"(?:Index\s+of\s+Industrial\s+Production|IIP)[^.]*?"
    r"(-?\d+(?:\.\d+)?)\s*%\s*year[-\s]?on[-\s]?year\s+growth",
    re.IGNORECASE | re.DOTALL,
)
# Alternative phrasing seen in some releases:
# "IIP growth rate for the month of March 2026 is 4.1 percent"
_IIP_HEADLINE_ALT = re.compile(
    r"IIP\s+growth\s+rate\s+for\s+the\s+month\s+of\s+\w+\s+\d{4}\s+is\s+"
    r"(-?\d+(?:\.\d+)?)\s*per\s*cent",
    re.IGNORECASE,
)


def extract_iip_from_prose(text: str) -> dict:
    """
    Extract IIP YoY values from the press release's templated highlight
    sentences. Returns a partial dict with whatever was found; missing keys
    are simply absent (not None). Caller merges with defaults.
    """
    result: dict = {}

    m = _IIP_HEADLINE.search(text) or _IIP_HEADLINE_ALT.search(text)
    if m:
        try:
            v = float(m.group(1))
            if YOY_BOUNDS[0] <= v <= YOY_BOUNDS[1]:
                result["headline_yoy"] = v
        except ValueError:
            pass

    m = _IIP_SECTOR_SENTENCE.search(text)
    if m:
        for key, val in zip(
            ("mining_yoy", "manufacturing_yoy", "electricity_yoy"),
            m.groups(),
        ):
            try:
                v = float(val)
                if YOY_BOUNDS[0] <= v <= YOY_BOUNDS[1]:
                    result[key] = v
            except ValueError:
                pass

    m = _IIP_USEBASED_SENTENCE.search(text)
    if m:
        for key, val in zip(
            ("primary_goods_yoy", "capital_goods_yoy", "intermediate_goods_yoy",
             "infra_construction_yoy", "consumer_durables_yoy", "consumer_nondurables_yoy"),
            m.groups(),
        ):
            try:
                v = float(val)
                if YOY_BOUNDS[0] <= v <= YOY_BOUNDS[1]:
                    result[key] = v
            except ValueError:
                pass

    return result


# ─── Structured-prose extractors for CPI ─────────────────────────────────────

# CPI headline phrase across base years (2012=100 and 2024=100) typically:
# "Year-on-year inflation rate ... March 2026 over March 2025 is 3.40%"
# "All India Consumer Price Index ... March 2026 ... 3.40%"
_CPI_HEADLINE_PATTERNS = [
    re.compile(
        r"(?:Year[-\s]?on[-\s]?year\s+inflation\s+rate|All\s+India\s+inflation\s+rate)"
        r"[^.]*?(-?\d+(?:\.\d+)?)\s*%",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"All\s+India\s+CPI\s+(?:General\s+)?(?:Index|Inflation)?[^.]*?(-?\d+(?:\.\d+)?)\s*%",
        re.IGNORECASE | re.DOTALL,
    ),
]

# CPI food: "Food inflation rate ... is 2.69%" or "(Provisional)"
_CPI_FOOD_PATTERN = re.compile(
    r"(?:Food\s+(?:and\s+Beverages\s+)?inflation\s+rate|Consumer\s+Food\s+Price\s+Index)"
    r"[^.]*?(-?\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE | re.DOTALL,
)

# CPI fuel & light (only applicable under 2012=100 base, retired Jan 2026):
_CPI_FUEL_PATTERN = re.compile(
    r"Fuel\s*(?:and|&)\s*Light[^.]*?(-?\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE | re.DOTALL,
)


def extract_cpi_from_prose(text: str) -> dict:
    result: dict = {}
    for pattern in _CPI_HEADLINE_PATTERNS:
        m = pattern.search(text)
        if m:
            try:
                v = float(m.group(1))
                if YOY_BOUNDS[0] <= v <= YOY_BOUNDS[1]:
                    result["headline_yoy"] = v
                    break
            except ValueError:
                pass

    m = _CPI_FOOD_PATTERN.search(text)
    if m:
        try:
            v = float(m.group(1))
            if YOY_BOUNDS[0] <= v <= YOY_BOUNDS[1]:
                result["food_yoy"] = v
        except ValueError:
            pass

    m = _CPI_FUEL_PATTERN.search(text)
    if m:
        try:
            v = float(m.group(1))
            if YOY_BOUNDS[0] <= v <= YOY_BOUNDS[1]:
                result["fuel_yoy"] = v
        except ValueError:
            pass

    return result


# ─── Sanity check ────────────────────────────────────────────────────────────

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
    try:
        h = float(headline)
    except (TypeError, ValueError):
        return False, f"headline_yoy not numeric: {headline!r}"
    if not (YOY_BOUNDS[0] <= h <= YOY_BOUNDS[1]):
        return False, f"headline_yoy={headline} outside plausible bounds"

    if required:
        parsed = sum(1 for k in required if payload.get(k) is not None)
        # Strict majority — at least ⌈len/2⌉. Avoids the off-by-one in
        # `len(required) // 2` which lets too-sparse parses through when
        # the required list is short (e.g. 1 → threshold 0).
        threshold = (len(required) + 1) // 2
        if parsed < threshold:
            return False, (
                f"only {parsed}/{len(required)} required components parsed — "
                f"PDF layout likely changed"
            )

    return True, "ok"


# ─── Legacy helpers retained for backwards compatibility with tests ──────────
# These are no longer the primary path but tests against synthetic tables
# still exercise them; keep until those tests are updated.

def _row_label_matches(cell: str, label: str) -> bool:
    norm = lambda s: re.sub(r"[^a-z0-9]+", "", s.lower())
    return norm(label) in norm(cell)


def _last_yoy_in_row(row: Iterable[str]) -> Optional[float]:
    candidate: Optional[float] = None
    for cell in row:
        for m in re.finditer(r"-?\d+\.\d+", cell):
            try:
                v = float(m.group(0))
            except ValueError:
                continue
            if YOY_BOUNDS[0] <= v <= YOY_BOUNDS[1]:
                candidate = v
    return candidate


def find_yoy_in_tables(tables: list[list[list[str]]], label: str) -> Optional[float]:
    for tbl in tables:
        for row in tbl:
            if not row:
                continue
            first = next((c for c in row if c), "")
            if first and _row_label_matches(first, label):
                yoy = _last_yoy_in_row(row)
                if yoy is not None:
                    return yoy
    return None


def find_yoy_in_text(text: str, label: str) -> Optional[float]:
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


def extract_yoy(
    tables: list[list[list[str]]],
    text: str,
    label: str,
    aliases: tuple[str, ...] = (),
) -> Optional[float]:
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
