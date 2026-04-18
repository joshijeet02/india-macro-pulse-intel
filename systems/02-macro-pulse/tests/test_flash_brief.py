from unittest.mock import patch, MagicMock
import pytest
from ai.flash_brief import generate_cpi_brief, generate_iip_brief


def _mock_client(text: str):
    """Return a mock Anthropic client whose messages.create returns text."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=text)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client


def test_generate_cpi_brief_calls_api():
    """generate_cpi_brief returns the text from the API response."""
    expected = "March CPI came in at 3.34%, a significant beat below consensus of 3.70%."
    with patch("ai.flash_brief._client", return_value=_mock_client(expected)):
        result = generate_cpi_brief(
            reference_month="March 2025",
            headline_yoy=3.34,
            food_yoy=2.69,
            fuel_yoy=-1.67,
            consensus=3.70,
        )
    assert result == expected


def test_generate_iip_brief_calls_api():
    """generate_iip_brief returns the text from the API response."""
    expected = "January IIP at 5.0% surprised above the 4.5% consensus."
    with patch("ai.flash_brief._client", return_value=_mock_client(expected)):
        result = generate_iip_brief(
            reference_month="January 2025",
            headline_yoy=5.0,
            capital_goods=8.2,
            consumer_durables=12.1,
            consumer_nondurables=2.3,
            infra_construction=7.8,
            primary_goods=4.1,
            intermediate_goods=3.9,
            consensus=4.5,
        )
    assert result == expected


def test_cpi_brief_missing_api_key_raises():
    """generate_cpi_brief raises EnvironmentError when ANTHROPIC_API_KEY is not set."""
    import os
    original = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        with pytest.raises(EnvironmentError, match="ANTHROPIC_API_KEY"):
            generate_cpi_brief(
                reference_month="March 2025",
                headline_yoy=3.34,
                food_yoy=2.69,
                fuel_yoy=-1.67,
                consensus=3.70,
            )
    finally:
        if original:
            os.environ["ANTHROPIC_API_KEY"] = original
