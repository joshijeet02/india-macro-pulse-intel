"""
Integration test against the real April 2026 IIP press release PDF.

This is the test that would have caught everything our synthetic-table
unit tests missed — the original "first month-year" reference-month regex
would pick April (release date) over March (reference period), and the
generic label-then-value extractor would shift every use-based component
by one position because MOSPI's prose is value-then-label.

The fixture PDF is committed at tests/fixtures/pdf/iip_2026_03_real.pdf
(~1.4 MB). Expected values are taken directly from the PDF prose:

    "Index of Industrial Production (IIP) recorded a 4.1 % year-on-year
     growth in March 2026"
    "growth rates of the three sectors, Mining, Manufacturing and
     Electricity for the month of March 2026 are 5.5 percent, 4.3 percent
     and 0.8 percent respectively."
    "growth rates of IIP as per Use-based classification ... are 2.2
     percent in Primary goods, 14.6 percent in Capital goods, 3.3 percent
     in Intermediate goods, 6.7 percent in Infrastructure/ Construction
     Goods, 5.3 percent in Consumer durables and 1.1 percent in Consumer
     non-durables"
"""
from pathlib import Path

import pytest

from scrapers.mospi_iip import parse_iip_pdf

FIXTURE = Path(__file__).parent / "fixtures" / "pdf" / "iip_2026_03_real.pdf"


@pytest.fixture(scope="module")
def real_iip_pdf():
    if not FIXTURE.exists():
        pytest.skip(f"Real PDF fixture missing at {FIXTURE}")
    return FIXTURE.read_bytes()


def test_real_iip_reference_month_is_march_not_april(real_iip_pdf):
    """The MOST important test — the original parser got this wrong.

    PDF says 'Dated: April 28th, 2026' (release date) on line 1 and
    'MONTH OF MARCH 2026' (reference period) on line 13. Naive regex
    grabs April. The anchored `for the month of` pattern grabs March.
    """
    result = parse_iip_pdf(real_iip_pdf, source_url="test")
    assert result is not None
    assert result["reference_month"] == "2026-03", (
        f"Reference month is March (the period the data describes), not "
        f"April (when MOSPI released it). Got {result['reference_month']!r}."
    )


def test_real_iip_headline(real_iip_pdf):
    result = parse_iip_pdf(real_iip_pdf, source_url="test")
    assert result["headline_yoy"] == pytest.approx(4.1)


def test_real_iip_sectoral_values(real_iip_pdf):
    """Mining, Manufacturing, Electricity — the order matters."""
    result = parse_iip_pdf(real_iip_pdf, source_url="test")
    assert result["mining_yoy"] == pytest.approx(5.5)
    assert result["manufacturing_yoy"] == pytest.approx(4.3)
    assert result["electricity_yoy"] == pytest.approx(0.8)


def test_real_iip_use_based_values_not_shifted(real_iip_pdf):
    """The original parser shifted these by one position. Anchor-and-test."""
    result = parse_iip_pdf(real_iip_pdf, source_url="test")
    assert result["primary_goods_yoy"] == pytest.approx(2.2)
    assert result["capital_goods_yoy"] == pytest.approx(14.6)
    assert result["intermediate_goods_yoy"] == pytest.approx(3.3)
    assert result["infra_construction_yoy"] == pytest.approx(6.7)
    assert result["consumer_durables_yoy"] == pytest.approx(5.3)
    assert result["consumer_nondurables_yoy"] == pytest.approx(1.1)


def test_real_iip_passes_sanity_check(real_iip_pdf):
    """All 9 required components should parse, comfortably above the threshold."""
    result = parse_iip_pdf(real_iip_pdf, source_url="test")
    components = (
        "manufacturing_yoy", "mining_yoy", "electricity_yoy",
        "capital_goods_yoy", "consumer_durables_yoy",
        "consumer_nondurables_yoy", "infra_construction_yoy",
        "primary_goods_yoy", "intermediate_goods_yoy",
    )
    parsed = sum(1 for k in components if result.get(k) is not None)
    assert parsed == len(components), (
        f"Only {parsed}/{len(components)} components parsed — "
        f"some component-extraction logic regressed."
    )
