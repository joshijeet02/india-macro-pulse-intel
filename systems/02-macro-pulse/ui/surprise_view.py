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

    # ── What This Means ──────────────────────────────────────────────────────
    st.subheader("What This Means")
    _TONE_FN = {"success": st.success, "info": st.info, "warning": st.warning, "error": st.error}

    tabs = st.tabs(["CPI Surprise Pattern", "IIP Surprise Pattern", "Combined Signal"])

    with tabs[0]:
        cpi_surprises = [
            compute_surprise(r["headline_yoy"], r["consensus_forecast"], "CPI").surprise
            for r in cpi_history if r.get("consensus_forecast") and r.get("headline_yoy")
        ]
        if not cpi_surprises:
            st.info("Add consensus forecast data to see the CPI surprise pattern.")
        else:
            avg = sum(cpi_surprises) / len(cpi_surprises)
            positives = sum(1 for s in cpi_surprises if s > 0)
            if avg > 0.1 and positives >= len(cpi_surprises) * 0.6:
                st.error(
                    f"🔴 **Systematic Upside Surprises** — CPI has beaten consensus {positives}/{len(cpi_surprises)} times "
                    f"(avg +{avg:.2f}pp). The market is consistently under-pricing inflation — hawkish bias for RBI rate path."
                )
            elif avg < -0.1 and positives <= len(cpi_surprises) * 0.4:
                st.success(
                    f"🟢 **Systematic Downside Surprises** — CPI has undershot consensus {len(cpi_surprises)-positives}/{len(cpi_surprises)} times "
                    f"(avg {avg:.2f}pp). Market is over-estimating inflation — supportive for rate cuts and bond rally."
                )
            else:
                st.info(f"✅ **No Systematic Bias** — CPI surprises are balanced (avg {avg:+.2f}pp). Consensus is broadly accurate.")

    with tabs[1]:
        iip_surprises = [
            compute_surprise(r["headline_yoy"], r["consensus_forecast"], "IIP").surprise
            for r in iip_history if r.get("consensus_forecast") and r.get("headline_yoy")
        ]
        if not iip_surprises:
            st.info("Add consensus forecast data to see the IIP surprise pattern.")
        else:
            avg = sum(iip_surprises) / len(iip_surprises)
            if avg > 1.0:
                st.success(f"🟢 **IIP Persistently Beats Consensus** (avg +{avg:.1f}pp). Industrial output stronger than expected — positive growth signal.")
            elif avg < -1.0:
                st.error(f"🔴 **IIP Persistently Misses** (avg {avg:.1f}pp). Industrial weakness underestimated — risk of a growth downgrade cycle.")
            else:
                st.info(f"✅ **IIP Surprises Balanced** (avg {avg:+.1f}pp). No systematic analyst bias detected.")

    with tabs[2]:
        st.info(
            "**Combined Macro Regime Read:** Cross the CPI and IIP patterns above. "
            "**Low CPI + High IIP** → Goldilocks (disinflation + growth) = RBI cut-friendly. "
            "**High CPI + Low IIP** → Stagflation risk = RBI on hold. "
            "**High CPI + High IIP** → Strong recovery, RBI stays cautious."
        )
