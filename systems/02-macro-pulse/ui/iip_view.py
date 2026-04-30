import streamlit as st
import pandas as pd
from db.store import IIPStore
from engine.iip_decomposer import assess_iip_composition
from engine.surprise_calc import compute_surprise
from engine.assessments import assess_iip
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
