import streamlit as st
import pandas as pd
from db.store import IIPStore
from engine.iip_decomposer import assess_iip_composition
from engine.surprise_calc import compute_surprise
from engine.assessments import assess_iip
from engine.cross_ref import gdp_context
from ui._mode import assessment_text, render_glossary_expander

_TONE_FN = {
    "success": st.success,
    "info":    st.info,
    "warning": st.warning,
    "error":   st.error,
}


def render_iip_section():
    store = IIPStore()
    history = store.get_history(months=12)

    if not history:
        st.warning("No IIP data in database. Run `python seed/historical_data.py` first.")
        return

    latest = history[-1]

    col1, col2, col3 = st.columns(3)
    col1.metric("IIP Headline", f"{latest['headline_yoy']}%", help="YoY %")
    col2.metric("Capital Goods", f"{latest.get('capital_goods_yoy') or '—'}%",
                help="Investment demand proxy")
    col3.metric("Consumer Durables", f"{latest.get('consumer_durables_yoy') or '—'}%",
                help="Urban discretionary demand")

    render_glossary_expander(
        ["IIP", "Capital Goods", "Consumer Durables", "Consumer Non-Durables",
         "Use-Based Classification", "Capex"],
    )

    # ── Cross-reference with RBI's GDP projection ──────────────────────────
    _render_rbi_gdp_panel(latest)

    use_keys = [
        ("capital_goods_yoy",        "Capital Goods"),
        ("consumer_durables_yoy",    "Consumer Durables"),
        ("consumer_nondurables_yoy", "Consumer Non-Durables"),
        ("infra_construction_yoy",   "Infra/Construction"),
        ("primary_goods_yoy",        "Primary Goods"),
        ("intermediate_goods_yoy",   "Intermediate Goods"),
    ]
    available = {label: latest[key] for key, label in use_keys if latest.get(key) is not None}

    if available:
        st.subheader("Use-Based Classification (YoY %)")
        bar_df = pd.DataFrame(available.items(), columns=["Component", "YoY %"])
        st.bar_chart(bar_df.set_index("Component"))

        cap   = latest.get("capital_goods_yoy") or 0
        cd    = latest.get("consumer_durables_yoy") or 0
        cnd   = latest.get("consumer_nondurables_yoy") or 0
        infra = latest.get("infra_construction_yoy") or 0
        prim  = latest.get("primary_goods_yoy") or 0
        inter = latest.get("intermediate_goods_yoy") or 0

        signal = assess_iip_composition(
            headline=latest["headline_yoy"],
            capital_goods=cap, consumer_durables=cd,
            consumer_nondurables=cnd, infra_construction=infra,
            primary_goods=prim, intermediate_goods=inter,
        )
        invest_color = {"strong": "🟢", "moderate": "🟡", "weak": "🔴"}
        st.info(
            f"**Investment Demand:** {invest_color[signal.investment_demand]} {signal.investment_demand.upper()}  "
            f"**Consumption Demand:** {invest_color[signal.consumption_demand]} {signal.consumption_demand.upper()}\n\n"
            f"{signal.mpc_growth_read}"
        )

    # ── Economic Assessments ────────────────────────────────────────────────
    assessments = assess_iip(history)
    if assessments:
        st.subheader("What This Means")
        tab_labels = ["Headline", "Investment", "Consumption", "Infrastructure", "Trajectory", "Market Implication"]
        fields     = ["headline", "investment", "consumption", "infrastructure", "trajectory", "implication"]
        tabs = st.tabs(tab_labels)
        for tab, field in zip(tabs, fields):
            with tab:
                a = assessments.get(field, {})
                if a:
                    _TONE_FN.get(a["tone"], st.info)(assessment_text(a))

    st.subheader("12-Month IIP Trend")
    df = pd.DataFrame(history).set_index("reference_month")
    trend_cols = {c: c.replace("_yoy", "").replace("_", " ").title()
                  for c in ["headline_yoy", "capital_goods_yoy", "consumer_durables_yoy"]
                  if c in df.columns}
    if trend_cols:
        st.line_chart(df[list(trend_cols.keys())].rename(columns=trend_cols))

    full_df = pd.DataFrame(history)
    st.download_button(
        "Download IIP history (CSV)",
        data=full_df.to_csv(index=False).encode("utf-8"),
        file_name="india_iip_history.csv",
        mime="text/csv",
        help="Export the full 12-month series for use in your own models.",
    )


def _render_rbi_gdp_panel(latest_print: dict) -> None:
    """
    Show RBI's most recent GDP projection + monetary stance alongside the
    latest IIP print. IIP is monthly; GDP is quarterly; the comparison is
    qualitative ("RBI sees full-year growth at X% — monthly IIP is currently Y%")
    rather than a hard surprise calculation.
    """
    ctx = gdp_context()
    if ctx is None:
        return

    st.markdown("##### RBI growth view")
    cols = st.columns([1.2, 1.2, 2.6])
    cols[0].metric(
        f"RBI GDP projection ({ctx['projection_fy']})",
        f"{ctx['rbi_gdp_projection']:.1f}%",
    )
    cols[1].metric(
        "Repo rate",
        f"{ctx['repo_rate']:.2f}%",
        f"stance: {ctx['stance']}",
        delta_color="off",
    )
    with cols[2]:
        iip_yoy = latest_print.get("headline_yoy")
        if iip_yoy is not None:
            st.markdown(
                f"Latest IIP print is **{iip_yoy:.1f}% YoY** "
                f"({latest_print.get('reference_month', '')}). "
                f"RBI's full-year FY{ctx['projection_fy']} GDP path implies broad-based "
                f"strength of ~{ctx['rbi_gdp_projection']:.1f}% — track whether "
                f"successive IIP prints are running with or against that."
            )
        if ctx.get("mpc_url"):
            st.caption(
                f"[Read the MPC ({ctx['mpc_meeting_date']}) ↗]({ctx['mpc_url']})"
            )
