"""
Delhi petrol and diesel.

Transport is 8.8% of the basket and fuel roughly 40% of it, so a mis-read
price moves ~3.5% of the index — small enough not to look obviously broken,
which is why extraction is label-driven and range-guarded rather than
"first number that looks like a price".
"""
from unittest.mock import patch

import pytest

from scrapers import fuel

# Shape of the real goodreturns table: several cities, Delhi not first.
TABLE = """
<table>
  <tr><th>City</th><th>Price</th><th>Price Change</th></tr>
  <tr><td>Mumbai</td><td>&#x20b9;111.21</td><td>0.00</td></tr>
  <tr><td>Kolkata</td><td>&#x20b9;113.51</td><td>0.00</td></tr>
  <tr><td>New Delhi</td><td>&#x20b9;102.12</td><td>0.00</td></tr>
</table>
"""


def test_reads_the_named_city_not_the_first_row():
    """Positional reading returned a different answer on the real page."""
    assert fuel.extract_city_price(TABLE) == pytest.approx(102.12)


def test_unknown_city_returns_nothing():
    assert fuel.extract_city_price(TABLE, "Atlantis") is None


def test_table_without_a_city_column_is_ignored():
    """These pages carry unrelated price tables — LPG, historical rows."""
    other = "<table><tr><td>LPG</td><td>941.50</td></tr></table>"
    assert fuel.extract_city_price(other) is None


def test_html_entities_are_decoded():
    assert fuel.extract_city_price(
        '<table><tr><th>City</th><th>Price</th></tr>'
        '<tr><td>New Delhi</td><td>&#x20b9;99.99</td></tr></table>'
    ) == pytest.approx(99.99)


def test_implausible_price_is_discarded():
    """A mis-parsed cell must not become a fuel price."""
    absurd = ('<table><tr><th>City</th><th>Price</th></tr>'
              '<tr><td>New Delhi</td><td>941.50</td></tr></table>')
    with patch.object(fuel, "_fetch", return_value=absurd):
        assert fuel.fetch_fuel_price("petrol") is None


def test_plausible_range_brackets_real_indian_prices():
    low, high = fuel.PLAUSIBLE_RANGE
    assert low < 95.20 < high      # diesel
    assert low < 102.12 < high     # petrol
    assert not (low <= 941.50 <= high)   # an LPG cylinder must not qualify


def test_sources_agreeing_returns_the_primary():
    with patch.object(fuel, "_fetch", return_value=TABLE):
        assert fuel.fetch_fuel_price("petrol") == pytest.approx(102.12)


def test_material_disagreement_is_logged(caplog):
    """A silently stale mirror yields a number that looks entirely reasonable."""
    other = ('<table><tr><th>City</th><th>Price</th></tr>'
             '<tr><td>New Delhi</td><td>&#x20b9;150.00</td></tr></table>')
    pages = iter([TABLE, other])
    with patch.object(fuel, "_fetch", side_effect=lambda url: next(pages)):
        with caplog.at_level("WARNING"):
            got = fuel.fetch_fuel_price("petrol")
    assert got == pytest.approx(102.12)          # primary still wins
    assert any("disagree" in r.message for r in caplog.records)


def test_all_sources_down_returns_none():
    with patch.object(fuel, "_fetch", return_value=None):
        assert fuel.fetch_fuel_price("petrol") is None


def test_fetch_fuel_returns_both_fuels():
    with patch.object(fuel, "_fetch", return_value=TABLE):
        got = fuel.fetch_fuel()
    assert set(got) == {"petrol_per_litre", "diesel_per_litre"}


def test_fetch_fuel_returns_empty_when_nothing_resolves():
    """Transport stays honestly 'carried' rather than moving on half a signal."""
    with patch.object(fuel, "_fetch", return_value=None):
        assert fuel.fetch_fuel() == {}


def test_no_test_here_touches_the_network():
    """Every case above patches _fetch; this asserts the seam exists."""
    assert hasattr(fuel, "_fetch")
