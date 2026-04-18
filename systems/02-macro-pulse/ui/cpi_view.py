import streamlit as st
import pandas as pd
from db.store import CPIStore
from engine.surprise_calc import compute_surprise


def render_cpi_section():
    store = CPIStore()
    history = store.get_history(months=12)

    if not history:
        st.warning("No CPI data in database. Run `python seed/historical_data.py` first.")
        return

    latest = history[-1]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Headline CPI", f"{latest['headline_yoy']}%", help="YoY %")
    col2.metric("Core Inflation", f"{latest.get('core_yoy') or '—'}%",
                help="Residual ex-food & fuel — key MPC signal")
    col3.metric("Food Inflation", f"{latest.get('food_yoy') or '—'}%",
                help="Food & Beverages (weight: 45.9%)")
    col4.metric("Fuel Inflation", f"{latest.get('fuel_yoy') or '—'}%",
                help="Fuel & Light (weight: 6.8%)")

    st.caption(f"Reference: {latest['reference_month']} · Food 45.86% · Fuel 6.84% · Core 47.30%")

    if all(latest.get(k) is not None for k in ["food_contrib", "fuel_contrib", "core_contrib"]):
        st.subheader("Contributions to Headline CPI (pp)")
        contrib_data = pd.DataFrame({
            "Component": ["Food", "Fuel", "Core"],
            "Contribution (pp)": [
                latest["food_contrib"],
                latest["fuel_contrib"],
                latest["core_contrib"],
            ],
        })
        st.bar_chart(contrib_data.set_index("Component"))

    st.subheader("12-Month Trend")
    df = pd.DataFrame(history).set_index("reference_month")
    chart_cols = {c: c.replace("_yoy", "").replace("_", " ").title()
                  for c in ["headline_yoy", "core_yoy", "food_yoy"] if c in df.columns}
    if chart_cols:
        st.line_chart(df[list(chart_cols.keys())].rename(columns=chart_cols))

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
