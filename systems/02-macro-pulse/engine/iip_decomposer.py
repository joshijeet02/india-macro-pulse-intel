from dataclasses import dataclass
from typing import Literal


@dataclass
class IIPSignal:
    headline: float
    investment_demand: Literal["strong", "moderate", "weak"]
    consumption_demand: Literal["strong", "moderate", "weak"]
    mpc_growth_read: str
    capital_goods: float
    consumer_durables: float
    consumer_nondurables: float
    infra_construction: float
    primary_goods: float
    intermediate_goods: float


def _grade(value: float, high: float, low: float) -> Literal["strong", "moderate", "weak"]:
    if value >= high:
        return "strong"
    if value <= low:
        return "weak"
    return "moderate"


def assess_iip_composition(
    headline: float,
    capital_goods: float,
    consumer_durables: float,
    consumer_nondurables: float,
    infra_construction: float,
    primary_goods: float,
    intermediate_goods: float,
) -> IIPSignal:
    """
    Grade IIP components into investment and consumption demand signals.

    Thresholds calibrated to India IIP historical distribution (2016-2024):
    capital goods >8% = strong investment; <2% = weak.
    Consumer durables >5% = strong; <0% = weak.
    """
    investment = _grade(capital_goods, high=8.0, low=2.0)
    consumption = _grade(consumer_durables, high=5.0, low=0.0)

    invest_word = {
        "strong": f"Capital goods accelerated ({capital_goods:+.1f}%), pointing to a strengthening investment cycle.",
        "moderate": f"Capital goods grew at {capital_goods:+.1f}% — investment demand is holding but not accelerating.",
        "weak": f"Capital goods contracted/slowed to {capital_goods:+.1f}%, flagging weak private capex.",
    }[investment]

    consume_word = {
        "strong": f"Consumer durables ({consumer_durables:+.1f}%) signal healthy urban discretionary spending.",
        "moderate": f"Consumer durables at {consumer_durables:+.1f}% — consumption demand is uneven.",
        "weak": f"Consumer durables contracted ({consumer_durables:+.1f}%), indicating stressed urban demand.",
    }[consumption]

    mpc_read = (
        f"{invest_word} {consume_word} "
        f"Infra/construction at {infra_construction:+.1f}% reflects government capex execution."
    )

    return IIPSignal(
        headline=headline,
        investment_demand=investment,
        consumption_demand=consumption,
        mpc_growth_read=mpc_read,
        capital_goods=capital_goods,
        consumer_durables=consumer_durables,
        consumer_nondurables=consumer_nondurables,
        infra_construction=infra_construction,
        primary_goods=primary_goods,
        intermediate_goods=intermediate_goods,
    )
