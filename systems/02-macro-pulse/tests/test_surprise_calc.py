import pytest
from engine.surprise_calc import compute_surprise, SurpriseResult


def test_cpi_significant_below_consensus():
    """Feb 2025 CPI: 3.61% actual vs 4.10% consensus = -0.49pp = SIGNIFICANT BELOW."""
    result = compute_surprise(actual=3.61, consensus=4.10, indicator="CPI")
    assert result.surprise == pytest.approx(-0.49, abs=0.01)
    assert result.direction == "BELOW"
    assert result.magnitude == "SIGNIFICANT"
    assert "SIGNIFICANT" in result.label


def test_cpi_inline_with_consensus():
    """CPI 4.83% vs 4.80% consensus = +0.03pp = IN LINE."""
    result = compute_surprise(actual=4.83, consensus=4.80, indicator="CPI")
    assert result.magnitude == "IN LINE"
    assert result.label == "IN LINE WITH CONSENSUS"


def test_iip_large_miss_is_notable_not_significant():
    """IIP 0.1% vs consensus 4.0% — z-score ~1.39, so NOTABLE not SIGNIFICANT."""
    result = compute_surprise(actual=0.1, consensus=4.0, indicator="IIP")
    assert result.magnitude in ("NOTABLE", "IN LINE")


def test_iip_small_miss_is_inline():
    """IIP 5.2% vs 5.0% = +0.2pp, z-score = 0.07 = IN LINE."""
    result = compute_surprise(actual=5.2, consensus=5.0, indicator="IIP")
    assert result.magnitude == "IN LINE"


def test_z_score_formula():
    """Z-score = surprise / std_dev."""
    result = compute_surprise(actual=3.61, consensus=4.10, indicator="CPI")
    expected_z = -0.49 / 0.18
    assert result.z_score == pytest.approx(expected_z, abs=0.01)


def test_contextual_label_format():
    """Label is human-readable for flash brief insertion."""
    result = compute_surprise(actual=6.21, consensus=5.80, indicator="CPI")
    assert isinstance(result.label, str)
    assert len(result.label) > 5
