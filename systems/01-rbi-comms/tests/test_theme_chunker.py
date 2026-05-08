"""Tests for the keyword-based theme classifier."""
from engine.theme_chunker import (
    THEME_ORDER, chunk_by_theme, classify_paragraph, themes_with_content,
)


def test_unambiguous_growth_paragraph():
    text = (
        "10. As per the new GDP series (base year 2022-23), real GDP growth "
        "for 2025-26 is estimated at 7.6 per cent. This corroborates the "
        "underlying strong momentum in economic activity."
    )
    assert classify_paragraph(text) == "Growth"


def test_unambiguous_inflation_paragraph():
    text = (
        "14. In January-February, headline inflation continued to remain "
        "below target (2.7 per cent and 3.2 per cent, respectively), with "
        "food group recording a deflation."
    )
    assert classify_paragraph(text) == "Inflation"


def test_unambiguous_external_sector_paragraph():
    text = (
        "16. Global trade is expected to witness a slowdown in growth "
        "during 2026 as compared to 2025, due to the lingering tariff "
        "related uncertainties. India's merchandise exports contracted by "
        "0.2 per cent during January-February 2026 on a year-on-year basis."
    )
    assert classify_paragraph(text) == "External Sector"


def test_unambiguous_liquidity_paragraph():
    text = (
        "19. System liquidity, as measured by the net position under the "
        "Liquidity Adjustment Facility (LAF), stood at an average daily "
        "surplus. The weighted average call rate (WACR) traded in the "
        "lower half of the corridor."
    )
    assert classify_paragraph(text) == "Liquidity"


def test_unambiguous_financial_stability_paragraph():
    text = (
        "21. The system-level financial parameters related to capital "
        "adequacy, liquidity, asset quality and profitability of "
        "Scheduled Commercial Banks remain robust. NBFC parameters too "
        "are sound with adequate capital position."
    )
    assert classify_paragraph(text) == "Financial Stability"


def test_unambiguous_additional_measures_paragraph():
    text = (
        "31. For further development of the term money market, we have "
        "decided to permit certain additional categories of non-bank "
        "entities in this market segment."
    )
    assert classify_paragraph(text) == "Additional Measures"


def test_decision_paragraph_classified_as_decisions():
    text = (
        "4. The Monetary Policy Committee (MPC) met on the 6th, 7th and "
        "8th of April. The MPC voted unanimously to keep the policy repo "
        "rate unchanged at 5.25 per cent. Standing deposit facility at 5.00."
    )
    assert classify_paragraph(text) == "Decisions"


def test_intro_paragraph_falls_to_other():
    """Generic intro chatter shouldn't trigger any theme."""
    text = "Good morning and Namaskar. Let me welcome you all to the first policy of 2026-27."
    assert classify_paragraph(text) == "Other"


def test_empty_text_classifies_as_other():
    assert classify_paragraph("") == "Other"


def test_chunk_by_theme_returns_all_themes_with_empty_lists():
    """Caller can rely on every THEME_ORDER key existing in the output."""
    by_theme = chunk_by_theme("Just a generic line.")
    for t in THEME_ORDER:
        assert t in by_theme
        assert isinstance(by_theme[t], list)


def test_chunk_by_theme_groups_paragraphs():
    text = (
        "1. Good morning. Welcome.\n\n"
        "4. The MPC voted unanimously to keep the policy repo rate at 5.25.\n\n"
        "10. Real GDP growth for 2026-27 is projected at 6.9 per cent.\n\n"
        "14. Headline inflation moderated to 2.7 per cent. Core inflation steady.\n\n"
        "19. System liquidity under the LAF stood at surplus."
    )
    by_theme = chunk_by_theme(text)
    # Expected: 1 → Other, 4 → Decisions, 10 → Growth, 14 → Inflation, 19 → Liquidity
    assert len(by_theme["Decisions"]) == 1
    assert len(by_theme["Growth"]) == 1
    assert len(by_theme["Inflation"]) == 1
    assert len(by_theme["Liquidity"]) == 1
    assert len(by_theme["Other"]) == 1


def test_themes_with_content_filters_empty_themes():
    text = "10. Real GDP growth strong. Investment cycle is expanding."
    by_theme = chunk_by_theme(text)
    populated = themes_with_content(by_theme)
    assert "Growth" in populated
    assert "Inflation" not in populated
    assert "Other" not in populated  # the input has no other-bucket content
