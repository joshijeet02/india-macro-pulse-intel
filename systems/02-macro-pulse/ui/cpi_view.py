import streamlit as st
import pandas as pd
from db.store import CPIStore
from engine.surprise_calc import compute_surprise
from engine.assessments import assess_cpi
from engine.cross_ref import cpi_context_for_print
from ui._mode import assessment_text, render_glossary_expander

_TONE_FN = {
    "success": st.success,
    "info":    st.info,
    "warning": st.warning,
    "error":   st.error,
}


def render_cpi_section():
    store = CPIStore()
    history = store.get_history(months=12)

    if not history:
        st.warning("No CPI data in database. Run `python seed/historical_data.py` first.")
        return

    latest = history[-1]
    # Component decomposition requires 2012=100 base weights.
    # India switched to 2024=100 from Jan 2026 — use latest month that still has components.
    latest_dec = next(
        (r for r in reversed(history) if r.get("core_yoy") is not None),
        latest,
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Headline CPI", f"{latest['headline_yoy']}%", help="YoY %")
    col2.metric("Core Inflation", f"{latest_dec['core_yoy']}%",
                help="Residual ex-food & fuel — key MPC signal")
    col3.metric("Food Inflation", f"{latest_dec['food_yoy']}%",
                help="Food & Beverages (weight: 45.9%)")
    col4.metric("Fuel Inflation", f"{latest_dec['fuel_yoy']}%",
                help="Fuel & Light (weight: 6.8%)")

    comp_note = (
        f"Reference: {latest['reference_month']}"
        if latest_dec is latest
        else f"Headline: {latest['reference_month']} · Components: {latest_dec['reference_month']} "
             f"(base 2024=100 from Jan 2026 — old weights no longer apply)"
    )
    st.caption(comp_note + " · Food 45.86% · Fuel 6.84% · Core 47.30%")
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
    if all(latest_dec.get(k) is not None for k in ["food_contrib", "fuel_contrib", "core_contrib"]):
        st.subheader("Contributions to Headline CPI (pp)")
        contrib_data = pd.DataFrame({
            "Component": ["Food", "Fuel", "Core"],
            "Contribution (pp)": [
                latest_dec["food_contrib"],
                latest_dec["fuel_contrib"],
                latest_dec["core_contrib"],
            ],
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
