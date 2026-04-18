import pytest
from engine.iip_decomposer import assess_iip_composition, IIPSignal


def test_strong_capex_signal():
    """Capital goods > 8% = strong investment demand."""
    signal = assess_iip_composition(
        headline=8.0,
        capital_goods=14.5,
        consumer_durables=9.0,
        consumer_nondurables=3.0,
        infra_construction=12.0,
        primary_goods=5.0,
        intermediate_goods=4.0,
    )
    assert signal.investment_demand == "strong"
    assert signal.consumption_demand in ("moderate", "strong")


def test_weak_consumer_durable_signal():
    """Consumer durables < 0 = weak urban discretionary demand."""
    signal = assess_iip_composition(
        headline=2.0,
        capital_goods=3.0,
        consumer_durables=-5.0,
        consumer_nondurables=2.0,
        infra_construction=4.0,
        primary_goods=2.5,
        intermediate_goods=1.8,
    )
    assert signal.consumption_demand == "weak"


def test_headline_masked_by_base():
    """Low headline can hide strong capital goods — signal is separate from headline."""
    signal = assess_iip_composition(
        headline=-3.5,
        capital_goods=8.0,
        consumer_durables=-12.0,
        consumer_nondurables=1.0,
        infra_construction=6.0,
        primary_goods=-2.0,
        intermediate_goods=-4.0,
    )
    assert signal.investment_demand == "strong"
    assert signal.consumption_demand == "weak"


def test_mpc_growth_read_is_string():
    """Returns an mpc_growth_read string of meaningful length."""
    signal = assess_iip_composition(
        headline=5.2,
        capital_goods=11.0,
        consumer_durables=8.5,
        consumer_nondurables=3.5,
        infra_construction=9.0,
        primary_goods=4.5,
        intermediate_goods=3.8,
    )
    assert isinstance(signal.mpc_growth_read, str)
    assert len(signal.mpc_growth_read) > 20
