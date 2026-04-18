import streamlit as st
import pandas as pd
from db.store import CPIStore, IIPStore
from engine.surprise_calc import compute_surprise

_SIGNAL_COLORS = {
    "SIGNIFICANT": "🔴",
    "NOTABLE": "🟡",
    "IN LINE": "🟢",
}


def render_surprise_history():
    st.subheader("Surprise vs Consensus — Track Record")
    st.caption(
        "Z-scores use historical surprise std devs: CPI = 0.18pp, IIP = 2.8pp. "
        "SIGNIFICANT = |z| > 1.5 · NOTABLE = |z| > 0.7"
    )

    col_cpi, col_iip = st.columns(2)

    with col_cpi:
        st.markdown("**CPI Surprises**")
        cpi_store = CPIStore()
        cpi_history = cpi_store.get_history(months=12)
        cpi_rows = []
        for r in reversed(cpi_history):
            if r.get("consensus_forecast") and r.get("headline_yoy"):
                s = compute_surprise(r["headline_yoy"], r["consensus_forecast"], "CPI")
                icon = _SIGNAL_COLORS.get(s.magnitude, "")
                cpi_rows.append({
                    "Month": r["reference_month"],
                    "Actual": r["headline_yoy"],
                    "Consensus": r["consensus_forecast"],
                    "Surprise (pp)": s.surprise,
                    "Signal": f"{icon} {s.magnitude}",
                })
        if cpi_rows:
            st.dataframe(pd.DataFrame(cpi_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No CPI consensus data available.")

    with col_iip:
        st.markdown("**IIP Surprises**")
        iip_store = IIPStore()
        iip_history = iip_store.get_history(months=12)
        iip_rows = []
        for r in reversed(iip_history):
            if r.get("consensus_forecast") and r.get("headline_yoy"):
                s = compute_surprise(r["headline_yoy"], r["consensus_forecast"], "IIP")
                icon = _SIGNAL_COLORS.get(s.magnitude, "")
                iip_rows.append({
                    "Month": r["reference_month"],
                    "Actual": r["headline_yoy"],
                    "Consensus": r["consensus_forecast"],
                    "Surprise (pp)": s.surprise,
                    "Signal": f"{icon} {s.magnitude}",
                })
        if iip_rows:
            st.dataframe(pd.DataFrame(iip_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No IIP consensus data available.")
