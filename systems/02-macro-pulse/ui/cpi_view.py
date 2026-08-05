import streamlit as st
import pandas as pd
from db.store import CPIStore
from engine.surprise_calc import compute_surprise
from engine.assessments import assess_cpi
from engine.basket_weights import (
    CPI_2012_FOOD_WEIGHT,
    CPI_2012_FUEL_WEIGHT,
    CPI_FOOD_WEIGHT,
    CPI_NONFOOD_WEIGHT,
    base_year_for_month,
)
from engine.cross_ref import cpi_context_for_print
from ui._mode import assessment_text, render_glossary_expander

_TONE_FN = {
    "success": st.success,
    "info":    st.info,
    "warning": st.warning,
    "error":   st.error,
}


def base_year_of(decomposition: dict) -> str:
    """
    Determine which weight base a decomposition row belongs to.

    `decompose_cpi` returns a `base_year` key, but `CPIStore` does not persist
    it — a row read back from the database carries only `reference_month`. So
    trusting `base_year` alone made every *stored* 2026 release fall back to
    "2012" and display 45.86% beside contributions computed on 36.753%.
    Deriving from the month when the key is absent makes this correct for both
    a live decomposition and a database round-trip.
    """
    base_year = decomposition.get("base_year")
    if base_year:
        return base_year
    reference_month = decomposition.get("reference_month")
    if reference_month:
        try:
            return base_year_for_month(reference_month)
        except (ValueError, TypeError):
            # TypeError covers a non-string month (re.match rejects it before
            # base_year_for_month can raise ValueError). A display helper must
            # never crash the page over a malformed field.
            pass
    return "2012"


def core_definition_of(decomposition: dict) -> str:
    """
    Determine what "core" excludes for a decomposition row.

    Like `base_year`, `core_definition` is not persisted, so it is re-derived
    from the base era and the presence of a fuel contribution.
    """
    core_definition = decomposition.get("core_definition")
    if core_definition:
        return core_definition
    if base_year_of(decomposition) == "2024" or decomposition.get("fuel_contrib") is None:
        return "ex-food"
    return "ex-food-and-fuel"


def contribution_rows(decomposition: dict) -> list[tuple[str, float]]:
    """
    Select the contribution components worth charting, in display order.

    Under the 2024=100 base there is no "Fuel & Light" division, so
    `fuel_contrib` is legitimately None and the split is food vs core. That
    is still worth charting — the previous all-or-nothing gate hid the chart
    entirely for every 2026 release. The core label reflects
    `core_definition` so a reader is never left guessing what "core" excludes.
    """
    core_label = (
        "Core (ex-food)"
        if core_definition_of(decomposition) == "ex-food"
        else "Core"
    )
    candidates = [
        ("Food", decomposition.get("food_contrib")),
        ("Fuel", decomposition.get("fuel_contrib")),
        (core_label, decomposition.get("core_contrib")),
    ]
    return [(name, value) for name, value in candidates if value is not None]


def weight_caption(decomposition: dict) -> str:
    """
    Describe the weight base a decomposition was computed on.

    These figures were previously hardcoded to the 2012 series, so the app
    displayed "Food 45.86%" for releases actually compiled on 2024=100
    weights of 36.753% — stating the wrong number to the reader while the
    engine used the right one. They are now derived from the decomposition.
    """
    if base_year_of(decomposition) == "2024":
        return (
            f"base 2024=100 · Food {CPI_FOOD_WEIGHT * 100:.2f}% · "
            f"Non-food {CPI_NONFOOD_WEIGHT * 100:.2f}%"
        )
    core_weight = 1.0 - CPI_2012_FOOD_WEIGHT - CPI_2012_FUEL_WEIGHT
    return (
        f"base 2012=100 · Food {CPI_2012_FOOD_WEIGHT * 100:.2f}% · "
        f"Fuel {CPI_2012_FUEL_WEIGHT * 100:.2f}% · Core {core_weight * 100:.2f}%"
    )


def render_cpi_section():
    store = CPIStore()
    history = store.get_history(months=12)

    if not history:
        st.warning("No CPI data in database. Run `python seed/historical_data.py` first.")
        return

    latest = history[-1]
    # Fall back to the most recent month that has components, in case a
    # release arrives with headline only and no food breakdown.
    latest_dec = next(
        (r for r in reversed(history) if r.get("core_yoy") is not None),
        latest,
    )

    is_2024_base = base_year_of(latest_dec) == "2024"
    food_weight = CPI_FOOD_WEIGHT if is_2024_base else CPI_2012_FOOD_WEIGHT
    core_excludes = (
        "ex-food" if core_definition_of(latest_dec) == "ex-food"
        else "ex-food & fuel"
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Headline CPI", f"{latest['headline_yoy']}%", help="YoY %")
    col2.metric("Core Inflation", f"{latest_dec['core_yoy']}%",
                help=f"Residual {core_excludes} — key MPC signal")
    col3.metric("Food Inflation", f"{latest_dec['food_yoy']}%",
                help=f"Food & Beverages (weight: {food_weight * 100:.1f}%)")
    # Under 2024=100 there is no Fuel & Light division, so fuel_yoy is
    # legitimately absent — show "n/a" rather than the string "None%".
    if latest_dec.get("fuel_yoy") is None:
        col4.metric("Fuel Inflation", "n/a",
                    help="No 'Fuel & Light' division under 2024=100 — folded "
                         "into Housing, water, electricity, gas and other fuels")
    else:
        col4.metric("Fuel Inflation", f"{latest_dec['fuel_yoy']}%",
                    help=f"Fuel & Light (weight: {CPI_2012_FUEL_WEIGHT * 100:.1f}%)")

    comp_note = (
        f"Reference: {latest['reference_month']}"
        if latest_dec is latest
        else f"Headline: {latest['reference_month']} · "
             f"Components: {latest_dec['reference_month']}"
    )
    st.caption(f"{comp_note} · {weight_caption(latest_dec)}")
    render_glossary_expander(
        ["Headline CPI", "Core CPI", "Food Inflation", "Fuel Inflation",
         "RBI Target", "Real Rates", "Disinflation", "Base Effect"],
    )

    # ── Cross-reference with RBI's latest projection ───────────────────────
    _render_rbi_projection_panel(latest)

    # ── Economic Assessments ────────────────────────────────────────────────
    assessments = assess_cpi(history)
    if assessments:
        st.subheader("What This Means")
        tabs = st.tabs(["Headline", "Core", "Food", "Trajectory", "Market Implication", "Proprietary Pulse"])

        fields = ["headline", "core", "food", "trajectory", "implication", "alpha"]
        for tab, field in zip(tabs, fields):
            with tab:
                a = assessments.get(field, {})
                if a:
                    _TONE_FN.get(a["tone"], st.info)(assessment_text(a))

    # ── Contribution bar chart ──────────────────────────────────────────────
    _contrib_rows = contribution_rows(latest_dec)
    if len(_contrib_rows) >= 2:
        st.subheader("Contributions to Headline CPI (pp)")
        contrib_data = pd.DataFrame({
            "Component": [name for name, _ in _contrib_rows],
            "Contribution (pp)": [value for _, value in _contrib_rows],
        })
        st.bar_chart(contrib_data.set_index("Component"))

    st.subheader("12-Month Trend")
    df = pd.DataFrame(history).set_index("reference_month")
    chart_cols = {c: c.replace("_yoy", "").replace("_", " ").title()
                  for c in ["headline_yoy", "core_yoy", "food_yoy"] if c in df.columns}
    if chart_cols:
        st.line_chart(df[list(chart_cols.keys())].rename(columns=chart_cols))

    # Download the full series as CSV — analyst ergonomics
    full_df = pd.DataFrame(history)
    st.download_button(
        "Download CPI history (CSV)",
        data=full_df.to_csv(index=False).encode("utf-8"),
        file_name="india_cpi_history.csv",
        mime="text/csv",
        help="Export the full 12-month series for use in your own models.",
    )

    if any(r.get("consensus_forecast") is not None for r in history):
        st.subheader("Surprise vs Consensus")
        rows = []
        for r in reversed(history[-6:]):
            if r.get("consensus_forecast"):
                s = compute_surprise(r["headline_yoy"], r["consensus_forecast"], "CPI")
                rows.append({
                    "Month": r["reference_month"],
                    "Actual": f"{r['headline_yoy']}%",
                    "Consensus": f"{r['consensus_forecast']}%",
                    "Surprise": f"{s.surprise:+.2f}pp",
                    "Z-Score": f"{s.z_score:.1f}",
                    "Signal": s.label,
                })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_rbi_projection_panel(latest_print: dict) -> None:
    """
    Surface RBI's most recent CPI projection alongside the latest print, with
    a print-vs-projection delta and a deep-link to the RBI source. Quietly
    hides the panel if rbi-comms data isn't available (e.g., sister app not
    yet checked out, JSON sidecar missing).
    """
    ctx = cpi_context_for_print(latest_print)
    if ctx is None:
        return

    st.markdown("##### RBI projection vs latest print")
    cols = st.columns([1.2, 1.2, 2])
    cols[0].metric(
        f"RBI projection ({ctx['projection_fy']})",
        f"{ctx['rbi_projection']:.2f}%",
        help=f"From MPC meeting {ctx['mpc_meeting_date']} (stance: {ctx['stance']})",
    )
    if ctx["surprise_pp"] is not None:
        delta_label = (
            "above projection" if ctx["surprise_pp"] > 0
            else "below projection" if ctx["surprise_pp"] < 0
            else "on projection"
        )
        cols[1].metric(
            "Print vs RBI",
            f"{ctx['surprise_pp']:+.2f}pp",
            delta_label,
            delta_color="off",
        )
    with cols[2]:
        st.markdown(ctx["comment"])
        if ctx.get("mpc_url"):
            st.caption(
                f"[Read RBI MPC ({ctx['mpc_meeting_date']}) ↗]({ctx['mpc_url']})"
            )
