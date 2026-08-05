"""
Fetch live prices, recompute the index, show the number.

This panel is a calculation, not a forecast. It starts from the division
indices MOSPI last published, moves the ones we can price by their measured
price change, carries the rest unchanged, and re-aggregates with the official
CPI 2024 weights. Every input is either an official figure or an observed
price ratio.
"""
import pandas as pd
import streamlit as st

from engine.live_index import BASE_YEAR_LEVELS, compute_live_index
from engine.live_sources import (
    fetch_and_measure, load_snapshots, reference_prices, unmeasured_gap,
)

_PRETTY = {
    "food_and_beverages": "Food and beverages",
    "housing_water_electricity_gas_fuel": "Housing, water, electricity, gas, fuels",
    "transport": "Transport",
    "clothing_and_footwear": "Clothing and footwear",
    "health": "Health",
    "personal_care_and_misc": "Personal care and misc (incl. gold/silver)",
    "furnishings_household_equipment": "Furnishings and household equipment",
    "information_and_communication": "Information and communication",
    "restaurants_and_accommodation": "Restaurants and accommodation",
    "education_services": "Education services",
    "paan_tobacco_and_intoxicants": "Paan, tobacco and intoxicants",
    "recreation_sport_and_culture": "Recreation, sport and culture",
}


def _base_level_for(month: str) -> float | None:
    """Headline index twelve months before `month`, if published."""
    year, mm = month.split("-")
    return BASE_YEAR_LEVELS.get(f"{int(year) - 1}-{mm}")


def render_live_index():
    st.subheader("Live CPI index — computed from current prices")
    st.caption(
        "Not a forecast. Starts from MOSPI's last published division indices, "
        "moves the ones we can price by their measured change, carries the rest "
        "unchanged, and re-aggregates with the official CPI 2024 weights."
    )

    if st.button("Fetch latest prices and recalculate", type="primary"):
        with st.spinner("Fetching live prices…"):
            current, relatives, first = fetch_and_measure()
        st.session_state["live_result"] = {
            "current": current, "relatives": relatives, "first": first,
        }
        st.rerun()

    result = st.session_state.get("live_result")
    snapshots = load_snapshots()

    if result is None:
        if snapshots:
            st.info(
                f"{len(snapshots)} price snapshot(s) on record. "
                "Press the button to fetch current prices and recompute."
            )
        else:
            st.info(
                "No prices fetched yet. The first fetch establishes the reference "
                "the index is measured against — it will show no movement by "
                "construction, and every fetch after it reports real change."
            )
        return

    if not result["current"]:
        st.error("No price source returned data. Nothing recalculated.")
        return

    live = compute_live_index(result["relatives"])

    if result["first"] or not result["relatives"]:
        st.warning(
            "**First fetch — this is the reference, not a measurement.** Today's "
            "prices become the baseline. There is no link to measure along yet, so "
            "the index equals MOSPI's published figure. Fetch again later and this "
            "becomes a real reading.\n\n"
            "Note it reports *no* relative rather than a relative of 1.0: claiming "
            "no change would assert something about prices over a period we never "
            "observed."
        )
    else:
        st.caption(
            f"Measured along {len(snapshots) - 1} chained link(s) between "
            f"{len(snapshots)} snapshots. Each link uses its own matched sample, so "
            f"an item that stops scraping keeps the movement it contributed while it "
            f"was visible instead of being erased from the record."
        )

    left, right = st.columns([2, 3])
    with left:
        st.metric(
            "Computed CPI index",
            f"{live.index}",
            delta=f"{live.pct_change_since_anchor:+.3f}% vs {live.anchor_month}",
            help="Index level, base 2024=100.",
        )
        base = _base_level_for("2026-07")
        if base:
            implied = live.implied_yoy(base)
            st.metric(
                "Implied inflation (YoY)",
                f"{implied}%",
                help=f"This index level against the published base of {base}.",
            )

    with right:
        st.markdown(
            f"**{live.observed_weight:.1f}% of the basket was repriced** from live "
            f"sources. The remaining {100 - live.observed_weight:.1f}% is carried at "
            f"MOSPI's last published level.\n\n"
            f"Carrying unpriced divisions forward is an assumption — an explicit "
            f"and conservative one. It says only that we did not observe a change, "
            f"not that none occurred. As more sources come online, the carried "
            f"share shrinks and the reading tightens."
        )
        gap = unmeasured_gap(live.anchor_month)
        if gap:
            st.caption(
                f"Anchor: MOSPI CPI release for {live.anchor_month}, Annexure I. "
                f"**{gap} between that month ending and our first price observation "
                f"are unmeasured** — the index treats that stretch as flat because we "
                f"were not yet watching. It shrinks each time a new release lets us "
                f"re-anchor closer to the present."
            )
        else:
            st.caption(f"Anchor: MOSPI CPI release for {live.anchor_month}, Annexure I.")

    rows = []
    for r in live.readings:
        rows.append({
            "Division": _PRETTY.get(r.key, r.key),
            "Weight %": round(r.weight, 2),
            "Anchor": round(r.anchor_index, 2),
            "Live": round(r.live_index, 2),
            "Change": f"{r.pct_change:+.2f}%" if r.observed else "—",
            "Source": "measured" if r.observed else "carried",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with st.expander("Prices fetched this run"):
        reference = reference_prices()
        rows = []
        for division, items in result["current"].items():
            base_items = reference.get(division, {})
            for item_id, price in sorted(items.items()):
                base = base_items.get(item_id)
                rows.append({
                    "Division": _PRETTY.get(division, division),
                    "Item": item_id,
                    "Price now": round(price, 2),
                    "Reference": round(base, 2) if base else "—",
                    "Change": f"{(price / base - 1) * 100:+.2f}%" if base else "new",
                })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(
            "Each division's relative is the geometric mean of the ratios above, "
            "over items priced in BOTH periods. Items marked 'new' set their own "
            "reference and do not affect this reading — a lost or added item must "
            "never register as a price move."
        )
