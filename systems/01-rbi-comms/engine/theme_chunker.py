"""
Group RBI Statement paragraphs into the analyst's mental themes.

Why this exists: Sid (real hedge fund operator) flagged that paragraph-by-
paragraph diffs are mechanical and don't match how an analyst reads. He
thinks in themes — Growth, Inflation, Liquidity, External, Stability — and
wants "what shifted in the *growth* read" rather than "what shifted in
paragraph 6".

The original HTML extractor stripped section headers (only kept numbered
paragraphs), so we can't regex out RBI's own section markers from full_text.
Instead we classify each paragraph by content using a per-theme keyword
lexicon. Paragraphs are tokenized, scored against each theme's keywords,
and assigned to the highest-scoring theme. Ties are broken by THEME_ORDER
so the result is deterministic.

This is a free, fast, transparent classifier. The LLM only enters at the
*contextual summary* layer (engine/theme_diff.py) where it shines.
"""
from __future__ import annotations

import re
from typing import Iterable

# Canonical theme order — also the tiebreaker when two themes score equally.
THEME_ORDER: tuple[str, ...] = (
    "Decisions",            # Rate decision, vote, stance — almost always ¶4
    "Stance",               # Forward guidance language
    "Growth",               # GDP, output, demand, investment
    "Inflation",            # CPI, prices, food/fuel
    "External Sector",      # Rupee, FX, FDI, BoP, oil
    "Liquidity",            # LAF, money market, transmission, banks
    "Financial Stability",  # Capital adequacy, NPAs, NBFCs
    "Additional Measures",  # Regulatory, ease-of-doing-business, payments
    "Other",                # Intro / closing remarks
)

# Visual icons for the UI cards (matches the Glossary tab vocabulary).
THEME_ICONS: dict[str, str] = {
    "Decisions":            "🎯",
    "Stance":               "🧭",
    "Growth":               "📊",
    "Inflation":            "📈",
    "External Sector":      "🌐",
    "Liquidity":            "💧",
    "Financial Stability":  "🏦",
    "Additional Measures":  "📜",
    "Other":                "📝",
}

# Per-theme keyword lexicon. Lowercased substring matching.
# Each match adds 1 to the theme's score. Order within a theme doesn't matter.
# When tuning, prefer SPECIFIC phrases over single words to reduce cross-theme
# confusion (e.g., "GDP growth" beats just "growth", which appears everywhere).
THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Decisions": (
        "monetary policy committee (mpc) met",
        "policy repo rate",
        "voted unanimously",
        "voted in favour",
        "voted against",
        "basis points",
        "kept unchanged at",
        "reduced by",
        "increased by",
        "standing deposit facility",
        "marginal standing facility",
        "bank rate",
    ),
    "Stance": (
        "decided to continue with",
        "withdrawal of accommodation",
        "neutral stance",
        "remain accommodative",
        "stance to neutral",
        "calibrated tightening",
        "calibrated withdrawal",
        "remain vigilant",
        "data-dependent",
        "data dependent",
        "ahead of the curve",
        "durable alignment",
    ),
    "Growth": (
        "real gdp growth",
        "gdp growth",
        "gross value added",
        " gva ",
        "manufacturing sector",
        "services sector",
        "private consumption",
        "discretionary spending",
        "rural demand",
        "urban consumption",
        "investment",
        "capex",
        "capacity utilisation",
        "high frequency indicators",
        "pmi manufacturing",
        "industrial production",
        "iip",
        "agricultural",
        "agriculture",
    ),
    "Inflation": (
        "headline inflation",
        "headline cpi",
        " cpi inflation",
        "core inflation",
        "food inflation",
        "fuel inflation",
        "inflation outlook",
        "price pressures",
        "vegetable",
        "vegetables",
        "deflation",
        "disinflation",
        "msp",
        "minimum support price",
        "rabi",
        "kharif",
        "el niño",
        "el nino",
    ),
    "External Sector": (
        "exchange rate",
        "indian rupee",
        "us dollar",
        "foreign exchange reserves",
        "fdi",
        "foreign direct investment",
        "foreign portfolio",
        " fpi ",
        "current account deficit",
        "balance of payments",
        "merchandise export",
        "merchandise import",
        "remittance",
        "external commercial borrowings",
        "global trade",
        "global growth",
        "geopolitical",
        "crude oil",
        "energy prices",
        "commodity prices",
    ),
    "Liquidity": (
        "system liquidity",
        "liquidity adjustment facility",
        " laf ",
        "liquidity management",
        "weighted average call rate",
        "weighted average lending rate",
        "wacr",
        "wallr",
        " sdf ",
        "standing deposit facility",
        "transmission of policy",
        "policy rate cuts to the money",
        "money market",
        "g-sec",
        "g sec",
        "government securities",
        "credit market",
        "bond yields",
        "open market operations",
        "omos",
    ),
    "Financial Stability": (
        "scheduled commercial banks",
        "capital adequacy",
        "asset quality",
        "gnpa",
        "non-performing",
        "nbfc",
        "non-banking financial",
        "credit growth",
        "credit from all sources",
        "system-level financial parameters",
        "profitability of",
        "regulatory capital",
        "crar",
    ),
    "Additional Measures": (
        "we propose to",
        "we have decided to permit",
        "decided to permit",
        "ease of doing business",
        "regulatory instructions",
        "msmes",
        "unified payments interface",
        " upi ",
        "payment system",
        "kyc",
        "term money market",
        "primary dealers",
        "non-bank entities",
        "harmonis",
        "rationalisat",
        "consolidate",
    ),
}

assert set(THEME_KEYWORDS.keys()) == (set(THEME_ORDER) - {"Other"}), \
    "THEME_KEYWORDS keys must match THEME_ORDER (minus 'Other')"


# Match a paragraph's leading number — used to skip the "1.", "2." prefix when
# building the comparison text but not when classifying.
_PARA_NUMBER_RX = re.compile(r"^\s*\d+\.\s")


def _normalize(text: str) -> str:
    """Lowercase + collapse whitespace, with a leading/trailing space so that
    keyword tokens like ' gva ' match word-boundary-style without regex."""
    return " " + " ".join(text.lower().split()) + " "


def classify_paragraph(text: str, min_score: int = 1) -> str:
    """
    Return the theme that best matches this paragraph's content.

    Scoring: each keyword in a theme's lexicon that appears in the paragraph
    adds 1 to that theme's score. Highest-scoring theme wins. Ties broken by
    THEME_ORDER. If no theme scores >= `min_score`, returns "Other".
    """
    norm = _normalize(text)
    scores: dict[str, int] = {}
    for theme in THEME_ORDER:
        if theme == "Other":
            continue
        keywords = THEME_KEYWORDS.get(theme, ())
        scores[theme] = sum(1 for kw in keywords if kw in norm)

    best_score = max(scores.values()) if scores else 0
    if best_score < min_score:
        return "Other"

    # First theme in canonical order with the highest score
    for theme in THEME_ORDER:
        if theme == "Other":
            continue
        if scores.get(theme) == best_score:
            return theme
    return "Other"


def chunk_by_theme(text: str) -> dict[str, list[str]]:
    """
    Split a Statement's full_text into themed groups.

    Returns a dict mapping each theme (in THEME_ORDER) to a list of the
    paragraphs assigned to it. Themes with zero paragraphs ARE included
    (with empty list) so the caller can decide whether to render an empty
    card or hide it.
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    out: dict[str, list[str]] = {theme: [] for theme in THEME_ORDER}
    for p in paragraphs:
        theme = classify_paragraph(p)
        out[theme].append(p)
    return out


def joined_theme_text(theme_paragraphs: list[str]) -> str:
    """Join themed paragraphs back into a comparable text block."""
    return "\n\n".join(theme_paragraphs)


def themes_with_content(by_theme: dict[str, list[str]]) -> list[str]:
    """Return themes that actually have at least one paragraph, in canonical order."""
    return [t for t in THEME_ORDER if by_theme.get(t)]
