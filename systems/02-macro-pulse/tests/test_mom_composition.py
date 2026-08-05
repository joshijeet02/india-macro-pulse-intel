"""
Measured versus assumed in the month-on-month.

The whole credibility of the panel rests on this split being real. A number
where every component is assumed is a forecast wearing a measurement's
clothes; what makes it defensible is being able to say which parts were
observed and which were inferred.
"""
import pytest

from engine.basket_weights import CPI_2024_DIVISIONS
from engine.live_index import TRACKED_SHARE, compose_mom


def test_no_measurements_falls_back_entirely_to_the_assumption():
    comp = compose_mom(assumed_mom=0.93)
    assert comp.headline_mom == pytest.approx(0.93, abs=1e-6)
    assert comp.measured_weight == 0.0
    assert comp.measured_share == 0.0


def test_a_measurement_actually_moves_the_headline():
    """
    If measured data cannot change the number, claiming the feeds contribute
    would be false — which is the exact failure this guards.
    """
    assumed = compose_mom(assumed_mom=0.93)
    measured = compose_mom(assumed_mom=0.93,
                           measured_moms={"personal_care_and_misc": -3.02})
    assert measured.headline_mom < assumed.headline_mom
    assert measured.measured_weight > 0


def test_only_the_tracked_slice_counts_as_measured():
    """
    We observe bullion, not the soap and shampoo also sitting in that division.
    Counting the whole division as measured would overstate coverage ~3.5x.
    """
    comp = compose_mom(assumed_mom=1.0,
                       measured_moms={"personal_care_and_misc": -3.0})
    expected = CPI_2024_DIVISIONS["personal_care_and_misc"] * TRACKED_SHARE["personal_care_and_misc"]
    assert comp.measured_weight == pytest.approx(expected, abs=0.01)
    assert comp.measured_weight < CPI_2024_DIVISIONS["personal_care_and_misc"]


def test_the_untracked_remainder_still_gets_the_assumption():
    """The rest of a partly-measured division must not be assumed to be flat."""
    comp = compose_mom(assumed_mom=2.0,
                       measured_moms={"personal_care_and_misc": 0.0})
    # everything except the tracked bullion slice still moves at +2.0%
    assert comp.headline_mom > 1.9
    assert comp.headline_mom < 2.0


def test_measuring_everything_removes_the_assumption_entirely():
    everything = {k: 1.5 for k in CPI_2024_DIVISIONS}
    comp = compose_mom(assumed_mom=99.0, measured_moms=everything)
    tracked = sum(CPI_2024_DIVISIONS[k] * TRACKED_SHARE.get(k, 1.0) for k in CPI_2024_DIVISIONS)
    assert comp.measured_weight == pytest.approx(tracked, abs=0.01)


def test_measured_and_assumed_weights_span_the_whole_basket():
    comp = compose_mom(assumed_mom=0.9,
                       measured_moms={"personal_care_and_misc": -3.0, "transport": 0.5})
    assert comp.measured_weight + comp.assumed_weight == pytest.approx(100.0, abs=0.05)


def test_detail_lists_what_was_measured():
    comp = compose_mom(assumed_mom=0.9,
                       measured_moms={"personal_care_and_misc": -3.02})
    assert comp.measured and comp.measured[0][0] == "personal_care_and_misc"
    assert comp.measured[0][2] == pytest.approx(-3.02)


def test_an_unknown_division_is_ignored_not_crashed_on():
    comp = compose_mom(assumed_mom=0.9, measured_moms={"not_a_division": 5.0})
    assert comp.headline_mom == pytest.approx(0.9, abs=1e-6)
    assert comp.measured_weight == 0.0
