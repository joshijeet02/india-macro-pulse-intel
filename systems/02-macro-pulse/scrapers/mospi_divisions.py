"""
Division-wise index levels from a MOSPI CPI press release (Annexure I).

Every monthly release carries a table of all 12 COICOP divisions with their
index levels and inflation rates for Rural, Urban and Combined. That table is
the anchor the live index is measured from, so it must be parsed from whatever
release is newest rather than hardcoded to one month — a hardcoded anchor goes
stale the moment MOSPI publishes again, silently.

Parsing note: division names wrap across lines in the PDF, so matching on the
name is unreliable. Each row is identified instead by its two-digit division
code followed by exactly six numbers — rural/urban/combined index, then
rural/urban/combined inflation. That structure is stable across releases even
when the surrounding text reflows.

COICOP division 12 does not appear in India's CPI, so the codes run
01-11 and 13.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

log = logging.getLogger(__name__)

# Division code as printed by MOSPI -> the key used across this codebase.
DIVISION_CODES: dict[str, str] = {
    "01": "food_and_beverages",
    "02": "paan_tobacco_and_intoxicants",
    "03": "clothing_and_footwear",
    "04": "housing_water_electricity_gas_fuel",
    "05": "furnishings_household_equipment",
    "06": "health",
    "07": "transport",
    "08": "information_and_communication",
    "09": "recreation_sport_and_culture",
    "10": "education_services",
    "11": "restaurants_and_accommodation",
    "13": "personal_care_and_misc",
}

_NUMBER = r"-?\d{1,3}\.\d\d"
# code, then anything (a possibly-wrapped name), then six numbers.
_ROW = re.compile(rf"^(0[1-9]|1[0-3])\b.*?((?:{_NUMBER}\s+){{5}}{_NUMBER})\s*$")
_ALL_INDIA = re.compile(rf"^All India\s+((?:{_NUMBER}\s+){{5}}{_NUMBER})\s*$", re.I)


def parse_division_indices(text: str) -> dict:
    """
    Extract division index levels (Combined) from a release's text.

    Returns {"divisions": {key: index}, "inflation": {key: yoy},
             "headline_index": float | None, "headline_yoy": float | None}.

    Only rows carrying exactly six numbers are accepted. A row that has been
    mangled by the PDF text layer will not match and is skipped rather than
    guessed at — a wrong anchor is worse than a missing one, because it moves
    every division reading without looking broken.
    """
    divisions: dict[str, float] = {}
    inflation: dict[str, float] = {}
    headline_index: Optional[float] = None
    headline_yoy: Optional[float] = None

    for raw in text.split("\n"):
        line = raw.strip()

        match = _ALL_INDIA.match(line)
        if match:
            values = [float(v) for v in re.findall(_NUMBER, match.group(1))]
            headline_index, headline_yoy = values[2], values[5]
            continue

        match = _ROW.match(line)
        if not match:
            continue
        code = match.group(1)
        key = DIVISION_CODES.get(code)
        if key is None or key in divisions:
            continue          # first occurrence wins; later pages repeat codes
        values = [float(v) for v in re.findall(_NUMBER, match.group(2))]
        divisions[key] = values[2]        # Combined index
        inflation[key] = values[5]        # Combined YoY

    return {
        "divisions": divisions,
        "inflation": inflation,
        "headline_index": headline_index,
        "headline_yoy": headline_yoy,
    }


def sanity_check(parsed: dict, weights: Optional[dict] = None) -> tuple[bool, str]:
    """
    Confirm the parsed divisions actually rebuild the printed headline.

    This is the check that makes the anchor trustworthy. If a weighted
    aggregate of the parsed division indices does not return the headline MOSPI
    printed on the same page, something was mis-parsed and the anchor must be
    rejected.
    """
    from engine.basket_weights import CPI_2024_DIVISIONS

    weights = CPI_2024_DIVISIONS if weights is None else weights
    divisions = parsed.get("divisions") or {}
    headline = parsed.get("headline_index")

    if len(divisions) != len(DIVISION_CODES):
        return False, f"parsed {len(divisions)} of {len(DIVISION_CODES)} divisions"
    if headline is None:
        return False, "no All India headline index found"

    total_weight = sum(weights[k] for k in divisions if k in weights)
    if total_weight <= 0:
        return False, "no weights matched the parsed divisions"
    rebuilt = sum(weights[k] * v for k, v in divisions.items() if k in weights) / total_weight

    if abs(rebuilt - headline) > 0.05:
        return False, f"rebuilt {rebuilt:.2f} != printed {headline:.2f}"
    return True, f"rebuilt {rebuilt:.2f} matches printed {headline:.2f}"


ROW_MERGE_TOLERANCE_PX = 3


def parse_division_indices_by_position(pdf) -> dict:
    """
    Recover the table from word coordinates instead of the text layer.

    Needed because MOSPI's layout is not stable between releases: in some
    months the division names and their numbers land in separate text blocks,
    so reading the page line by line yields names with no numbers attached.

    Matching is by ORDER, not by y-proximity. Where a division name wraps onto
    three lines, its code sits at the top of the block while its numbers are
    vertically centred, so any y-tolerance loose enough to catch it also bleeds
    into the neighbouring row. But both sequences run down the page in the same
    order, so the nth code belongs to the nth six-number row.

    The annexure page is identified by how many division codes it carries —
    not by how many numeric rows, since the state-wise annexure has far more.
    """
    import re as _re
    from collections import defaultdict

    number = _re.compile(rf"^{_NUMBER}$")
    code_pattern = _re.compile(r"^(0[1-9]|1[0-3])$")

    def codes_and_rows(page):
        words = page.extract_words()
        codes = [
            w for w in words
            if code_pattern.match(w["text"]) and w["x0"] < 120
        ]
        numbers = [w for w in words if number.match(w["text"])]

        buckets = defaultdict(list)
        for w in numbers:
            buckets[round(w["top"])].append(w)
        merged = []
        for top in sorted(buckets):
            if merged and top - merged[-1][0] <= ROW_MERGE_TOLERANCE_PX:
                merged[-1][1].extend(buckets[top])
            else:
                merged.append([top, list(buckets[top])])
        rows = [
            sorted(ws, key=lambda w: w["x0"])
            for _, ws in merged if len(ws) == 6
        ]
        return sorted(codes, key=lambda w: w["top"]), rows

    best_codes, best_rows = [], []
    for page in pdf.pages:
        try:
            codes, rows = codes_and_rows(page)
        except Exception:
            continue
        if len(codes) > len(best_codes):
            best_codes, best_rows = codes, rows

    divisions: dict[str, float] = {}
    inflation: dict[str, float] = {}
    headline_index = None
    headline_yoy = None

    # The division rows come first, then the All India total row.
    if len(best_rows) == len(best_codes) + 1:
        total = best_rows[len(best_codes)]
        headline_index = float(total[2]["text"])
        headline_yoy = float(total[5]["text"])

    if len(best_rows) >= len(best_codes) and best_codes:
        for code_word, row in zip(best_codes, best_rows):
            key = DIVISION_CODES.get(code_word["text"])
            if key is None or key in divisions:
                continue
            divisions[key] = float(row[2]["text"])
            inflation[key] = float(row[5]["text"])

    return {
        "divisions": divisions,
        "inflation": inflation,
        "headline_index": headline_index,
        "headline_yoy": headline_yoy,
    }


def parse_release_pdf(pdf_bytes: bytes) -> Optional[dict]:
    """
    Parse a release PDF end to end. Returns None if it fails its sanity check.

    Tries the text layer first, then falls back to word positions. Both are
    validated the same way: the parsed divisions must rebuild the headline
    MOSPI printed on the same page. A partial or mis-parsed anchor is rejected
    rather than used, because it would move every division reading downstream
    without ever looking broken.
    """
    import io

    import pdfplumber

    from scrapers._pdf_extract import extract_reference_month, open_pdf_text

    text = open_pdf_text(pdf_bytes, max_pages=12)
    parsed = parse_division_indices(text)

    ok, _ = sanity_check(parsed)
    if not ok:
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                positional = parse_division_indices_by_position(pdf)
            if sanity_check(positional)[0]:
                log.info("mospi_divisions: text layer failed, positional parse succeeded")
                parsed = positional
        except Exception as exc:
            log.warning(f"mospi_divisions: positional parse errored: {exc}")

    parsed["reference_month"] = extract_reference_month(text)

    ok, reason = sanity_check(parsed)
    if not ok:
        log.warning(f"mospi_divisions: rejected parse — {reason}")
        return None
    if not parsed["reference_month"]:
        log.warning("mospi_divisions: no reference month; rejecting")
        return None

    log.info(f"mospi_divisions: {parsed['reference_month']} OK — {reason}")
    return parsed
