import os
import anthropic
from engine.cpi_decomposer import decompose_cpi
from engine.iip_decomposer import assess_iip_composition
from engine.surprise_calc import compute_surprise

_SYSTEM = (
    "You are a senior economist at a top Indian investment bank writing a flash brief "
    "for a Chief Economist. Write concisely and analytically. Focus on: "
    "(1) What this print means for RBI rate expectations, "
    "(2) Bond yield direction (10Y G-sec), "
    "(3) Any supply vs demand signal that changes the MPC's assessment. "
    "Never hedge. Never pad. Three paragraphs, no headers, plain prose."
)


def _client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=api_key)


def generate_cpi_brief(
    reference_month: str,
    headline_yoy: float,
    food_yoy: float,
    fuel_yoy: float,
    consensus: float,
) -> str:
    """Generate a 3-paragraph CPI flash brief via Claude."""
    dec = decompose_cpi(headline=headline_yoy, food_yoy=food_yoy, fuel_yoy=fuel_yoy)
    surprise = compute_surprise(actual=headline_yoy, consensus=consensus, indicator="CPI")

    prompt = f"""CPI Flash Brief — {reference_month}

HEADLINE: {headline_yoy}% YoY ({surprise.label})
CONSENSUS: {consensus}%

DECOMPOSITION (contributions to headline, pp):
- Food: {dec['food_contrib']:+.2f}pp (food YoY {food_yoy}%)
- Fuel: {dec['fuel_contrib']:+.2f}pp (fuel YoY {fuel_yoy}%)
- Core: {dec['core_contrib']:+.2f}pp (core YoY {dec['core_yoy']}%)

Write the flash brief. Para 1: headline + surprise (≤50 words). \
Para 2: component story + MPC read (≤80 words). \
Para 3: bond yield implication + rate cut probability change (≤60 words)."""

    msg = _client().messages.create(
        model="claude-opus-4-7",
        max_tokens=450,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def generate_iip_brief(
    reference_month: str,
    headline_yoy: float,
    capital_goods: float,
    consumer_durables: float,
    consumer_nondurables: float,
    infra_construction: float,
    primary_goods: float,
    intermediate_goods: float,
    consensus: float,
) -> str:
    """Generate a 3-paragraph IIP flash brief via Claude."""
    signal = assess_iip_composition(
        headline=headline_yoy,
        capital_goods=capital_goods,
        consumer_durables=consumer_durables,
        consumer_nondurables=consumer_nondurables,
        infra_construction=infra_construction,
        primary_goods=primary_goods,
        intermediate_goods=intermediate_goods,
    )
    surprise = compute_surprise(actual=headline_yoy, consensus=consensus, indicator="IIP")

    prompt = f"""IIP Flash Brief — {reference_month}

HEADLINE: {headline_yoy}% YoY ({surprise.label})
CONSENSUS: {consensus}%

USE-BASED BREAKDOWN (YoY%):
- Capital Goods: {capital_goods:+.1f}% [investment demand: {signal.investment_demand}]
- Consumer Durables: {consumer_durables:+.1f}% [consumption demand: {signal.consumption_demand}]
- Consumer Non-Durables: {consumer_nondurables:+.1f}%
- Infra/Construction: {infra_construction:+.1f}%
- Primary Goods: {primary_goods:+.1f}%
- Intermediate Goods: {intermediate_goods:+.1f}%

MPC GROWTH READ: {signal.mpc_growth_read}

Write the flash brief. Para 1: headline + surprise (≤50 words). \
Para 2: use-based decomposition — investment vs consumption signal, MPC growth assessment (≤80 words). \
Para 3: implication for growth outlook and rate expectations (≤60 words)."""

    msg = _client().messages.create(
        model="claude-opus-4-7",
        max_tokens=450,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text
