"""
Fetch live prices, recompute, and say what the next CPI print will read.

Leads with an inflation RATE, not an index level. "107.0" means nothing to a
reader; "3.53%" is the number MOSPI actually prints and the one a rates analyst
is trying to anticipate.

The panel answers one question: what will the next release say? Two things
determine that, and both are shown:

  1. where prices are now, which we measure
  2. what the base month a year ago did, which is already published and fixed

The second is what catches people out. July 2025 recorded +0.82% MoM, the
hottest month in the series. July 2026 has to repeat that just to hold its
year-on-year steady — flat prices this month print LOWER, not the same. So the
sensitivity table is not decoration: without it the headline looks arbitrary.
"""
import pandas as pd
import streamlit as st

from engine.cpi_levels import (
    ANCHOR_LEVELS, CONSENSUS, build_levels, central_mom, mom_series,
)
from engine.live_index import compute_live_index
from engine.live_sources import (
    fetch_and_measure, load_snapshots, reference_prices, unmeasured_gap,
)

_MONTHS = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}

_PRETTY = {
    "food_and_beverages": "Food and beverages",
    "housing_water_electricity_gas_fuel": "Housing, water, electricity, gas, fuels",
    "transport": "Transport (incl. petrol/diesel)",
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


def pretty_month(reference_month: str) -> str:
    try:
        year, month = reference_month.split("-")
        return f"{_MONTHS[month]} {year}"
    except (ValueError, KeyError):
        return reference_month


def next_month_after(reference_month: str) -> str:
    year, month = (int(x) for x in reference_month.split("-"))
    return f"{year + 1:04d}-01" if month == 12 else f"{year:04d}-{month + 1:02d}"


def base_month_for(target_month: str) -> str:
    """The month twelve earlier — the denominator of a year-on-year rate."""
    year, month = target_month.split("-")
    return f"{int(year) - 1}-{month}"


def render_live_index():
    st.subheader("What will the next CPI print say?")

    snapshots = load_snapshots()
    col_go, col_opt = st.columns([1, 2])
    with col_go:
        go = st.button("Refresh prices", type="primary")
    with col_opt:
        include_grocery = st.checkbox(
            "Also scrape the grocery basket (adds 2–3 minutes)",
            value=False,
            help=(
                "Gold, silver, petrol and diesel are plain HTTP and return in about "
                "a second. The grocery basket drives a headless browser across 20 "
                "Amazon searches with backoff, so it is opt-in rather than default."
            ),
        )

    if go:
        label = "Fetching prices…" if not include_grocery else "Fetching — grocery scrape takes 2–3 min…"
        with st.spinner(label):
            current, relatives, first = fetch_and_measure(include_slow=include_grocery)
        st.session_state["live_result"] = {
            "current": current, "relatives": relatives, "first": first,
        }
        st.rerun()

    result = st.session_state.get("live_result")
    relatives = result["relatives"] if result else {}
    live = compute_live_index(relatives)

    target = next_month_after(live.anchor_month)
    base_level = ANCHOR_LEVELS.get(base_month_for(target))
    anchor_base = ANCHOR_LEVELS.get(base_month_for(live.anchor_month))
    last_print = live.implied_yoy(anchor_base) if anchor_base else None

    # The month-on-month to assume for a month we have not observed. NOT zero:
    # over 14 months, assuming flat was the worst of five estimators tested,
    # and in a series whose recent months ran +0.26/+0.75/+1.04 it understated
    # the next print by about a percentage point.
    from db.store import CPIStore
    history = CPIStore().get_history(months=240)
    moms = mom_series(build_levels({
        r["reference_month"]: r["headline_yoy"]
        for r in history if r.get("headline_yoy") is not None
    }))
    central = central_mom(moms, target)

    if base_level:
        flat = live.yoy_for_mom(0.0, base_level)
        mom_value, mom_basis = central if central else (0.0, "no basis available")
        estimate = live.yoy_for_mom(mom_value, base_level)

        a, b, c = st.columns(3)
        a.metric(
            f"{pretty_month(target)} CPI — estimate",
            f"{estimate}%",
            help=f"Year-on-year, the figure MOSPI prints. Assumes {mom_value:+.2f}% "
                 f"month-on-month: {mom_basis}.",
        )
        if last_print is not None:
            b.metric(
                f"{pretty_month(live.anchor_month)} — published",
                f"{last_print}%",
                help="The last official print, for comparison.",
            )
        c.metric(
            "Prices since that print",
            f"{live.pct_change_since_anchor:+.2f}%",
            help="Month-on-month movement in the parts of the basket we can price.",
        )

        street = CONSENSUS.get(target)
        if street:
            midpoint = (street["low"] + street["high"]) / 2
            gap_to_street = estimate - midpoint
            agreement = (
                "in line with" if abs(gap_to_street) <= 0.15
                else ("above" if gap_to_street > 0 else "below")
            )
            st.success(
                f"**Street consensus for {pretty_month(target)}: "
                f"{street['low']}–{street['high']}%.** Our estimate of {estimate}% is "
                f"{agreement} it"
                + (f", by {abs(gap_to_street):.2f}pp" if agreement != "in line with" else "")
                + f".\n\nWe get there from our own month-on-month data — "
                f"{mom_basis} — not by anchoring to the poll. "
                f"{street['note']} _Source: {street['source']}._"
            )

        if last_print is not None:
            needed = live.mom_needed_for(last_print, base_level)
            direction = "below" if estimate < last_print else "above"
            st.info(
                f"**{pretty_month(target)} is tracking {abs(estimate - last_print):.2f}pp "
                f"{direction} {pretty_month(live.anchor_month)}'s {last_print}%.**\n\n"
                f"A year-on-year rate divides today by a month twelve back. "
                f"{pretty_month(base_month_for(target))} indexed **{base_level}**, so "
                f"{pretty_month(target)} must move **{needed:+.2f}% month-on-month just "
                f"to hold {last_print}%**. Flat prices print lower. That base is already "
                f"published and cannot change — it is the most predictable part of the "
                f"next release.\n\n"
                f"On the other side, we assume **{mom_value:+.2f}% month-on-month** "
                f"({mom_basis}). Flat prices would print {flat}%, but flat is not a "
                f"neutral guess: over 14 months it was the worst of five estimators "
                f"tested, and recent months ran +0.26%, +0.75% and +1.04%."
            )

        st.markdown(f"**If {pretty_month(target)} prices move by…**")
        st.dataframe(
            pd.DataFrame([{
                "Month-on-month": f"{mom:+.2f}%",
                f"{pretty_month(target)} would print": f"{live.yoy_for_mom(mom, base_level)}%",
                "": ("← our estimate" if abs(mom - mom_value) < 0.05
                     else "← flat prices" if mom == 0.0 else ""),
            } for mom in sorted({-0.4, -0.2, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0,
                                 round(mom_value, 2)})]),
            use_container_width=True, hide_index=True,
        )
        release_month = _MONTHS[next_month_after(target).split("-")[1]]
        st.caption(
            f"{pretty_month(target)} data publishes around the 12th of {release_month}. "
            f"Find the row matching your own view of this month's price move, and read "
            f"off the print it implies."
        )

    if result is None:
        st.caption(
            f"Showing the last published position ({pretty_month(live.anchor_month)} = "
            f"index {live.anchor_index}). Press **Refresh prices** to fold in today's "
            f"gold, silver and fuel — about a second."
            + (f" {len(snapshots)} snapshot(s) on record." if snapshots else "")
        )
        return

    if not result["current"]:
        st.error("No price source returned data. Nothing recalculated.")
        return

    if result["first"] or not relatives:
        st.warning(
            "**First fetch — this sets the reference, it does not measure yet.** There "
            "is no earlier snapshot to compare against, so no price movement is claimed. "
            "Refresh again later and this becomes a real reading."
        )

    gap = unmeasured_gap(live.anchor_month)
    st.caption(
        f"Index {live.index} (base 2024=100), anchored on MOSPI's "
        f"{pretty_month(live.anchor_month)} release. "
        f"**{live.observed_weight:.1f}% of the basket repriced** from live sources; the "
        f"rest carried at its last published level."
        + (f" The {gap} between that month ending and our first observation are "
           f"unmeasured — treated as flat because we were not yet watching." if gap else "")
    )

    with st.expander("Division detail"):
        st.dataframe(
            pd.DataFrame([{
                "Division": _PRETTY.get(r.key, r.key),
                "Weight %": round(r.weight, 2),
                "We price": f"{r.tracked_share:.0%}",
                "Anchor": round(r.anchor_index, 2),
                "Live": round(r.live_index, 2),
                "Move": f"{r.pct_change:+.2f}%" if r.observed else "—",
                "Source": "measured" if r.observed else "carried",
            } for r in live.readings]),
            use_container_width=True, hide_index=True,
        )

    with st.expander("Prices fetched this run"):
        reference = reference_prices()
        rows = []
        for division, items in result["current"].items():
            base_items = reference.get(division, {})
            for item_id, price in sorted(items.items()):
                prior = base_items.get(item_id)
                rows.append({
                    "Division": _PRETTY.get(division, division),
                    "Item": item_id,
                    "Price now": round(price, 2),
                    "Reference": round(prior, 2) if prior else "—",
                    "Change": f"{(price / prior - 1) * 100:+.2f}%" if prior else "new",
                })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(
            "Each division's move is the geometric mean of the ratios above, over items "
            "priced in BOTH periods. Items marked 'new' set their own reference — a "
            "product that changes must never register as a price move."
        )
