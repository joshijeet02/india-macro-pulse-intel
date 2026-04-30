"""
E-commerce price tracker tab.
Shows Amazon basket prices, Laspeyres index, and CPI food overlay.

Data lifecycle:
- Real prices accumulate via the weekly GH Action (scripts/scrape_amazon.py),
  persisted to data/amazon_prices.json, and hydrated into SQLite on app boot.
- The 'Run Price Scrape' button still works for ad-hoc local testing.
- The legacy 'Simulate 180-Day History' button is gated behind the
  MACRO_PULSE_DEV env var since the cron now produces real history.
"""
import os
import streamlit as st
import pandas as pd
from db.store import EcommStore, CPIStore
from engine.ecomm_basket import BASKET
from engine.ecomm_index import compute_index, group_summary

DEV_MODE = os.environ.get("MACRO_PULSE_DEV", "").lower() in ("1", "true", "yes")


def render_ecomm_section(pw_ready: bool = True, pw_err: str = ""):
    store = EcommStore()

    st.markdown(
        "**Engine Details** · Amazon Pulse basket tracker · "
        "Delhi (110001) · Laspeyres index (base = fixed)"
    )

    st.success(
        "**Methodology & Logic:** Traditional CPI data is released with a 15-to-45 day lag. "
        "To generate a leading indicator (alpha), we autonomously scrape real-time prices for 20 high-weight grocery items directly from Amazon India. "
        "By applying a Laspeyres index formula (comparing current aggregated costs against a fixed base-period cost), we can anticipate the food inflation vector weeks before MOSPI publishes official data."
    )


    # ── Playwright status warning ────────────────────────────────────────────
    if not pw_ready:
        st.warning(
            f"Browser setup issue — scraping may fail. Error: `{pw_err or 'unknown'}`\n\n"
            "If this persists on Streamlit Cloud, check `packages.txt` and redeploy."
        )

    # ── Scrape controls ──────────────────────────────────────────────────────
    col_btn, col_btn2, col_status = st.columns([1, 1.5, 2.5])
    with col_btn:
        run_scrape = st.button("Run Price Scrape", type="primary")
    with col_btn2:
        # Demo-history button is hidden in production — the weekly cron now
        # generates real history. Set MACRO_PULSE_DEV=1 locally to see it.
        run_history = st.button(
            "Simulate Demo History (dev only)",
            help="Generates synthetic history for local UI testing.",
        ) if DEV_MODE else False
    with col_status:
        am_last = store.last_scraped_at("amazon")
        if am_last:
            st.caption(f"Last scraped · Amazon: {am_last}")
        else:
            st.caption(
                "No scrape data yet. Real history accumulates via the weekly "
                "GitHub Action — or click **Run Price Scrape** for an instant local test."
            )

    # ── Show results/errors from previous scrape (persisted across rerun) ────
    if "scrape_msg" in st.session_state:
        for level, msg in st.session_state.pop("scrape_msg"):
            getattr(st, level)(msg)

    # ── Run scrape — save to session_state, THEN rerun ───────────────────────
    if run_scrape:
        msgs = []
        with st.spinner("Scraping Amazon India (2–3 min)…"):
            from engine.ecomm_index import run_scrape_and_store
            try:
                results = run_scrape_and_store(platforms=["amazon"])
                for platform, idx in results.items():
                    if "error" in idx:
                        msgs.append(("error", f"**{platform.title()}:** {idx['error']}"))
                    elif idx.get("index_value"):
                        msgs.append(("success",
                            f"**{platform.title()}:** {idx['items_count']} items scraped · "
                            f"Index = {idx['index_value']:.1f} · Coverage {idx['coverage_pct']:.0f}%"
                        ))
                    else:
                        msgs.append(("warning", f"**{platform.title()}:** scrape ran but index could not be computed"))
            except Exception as exc:
                msgs.append(("error", f"Scrape failed: {exc}"))
        st.session_state["scrape_msg"] = msgs
        st.rerun()

    if run_history:
        with st.spinner("Generating 180 days of simulated trend data..."):
            try:
                from seed.amazon_history import seed_historic_amazon
                seed_historic_amazon()
                st.session_state["scrape_msg"] = [("success", "Successfully back-propagated 180 days of historical index data!")]
            except Exception as exc:
                st.session_state["scrape_msg"] = [("error", f"History generation failed: Ensure you run a live scrape first. ({exc})")]
        st.rerun()

    # ── Guard: no data yet ────────────────────────────────────────────────────
    if not store.has_data():
        st.info(
            "No price data yet. Click **Run Price Scrape** above — it takes ~2–3 minutes. "
            "The scraper uses a headless Chromium browser to check Amazon grocery prices."
        )
        with st.expander("Basket composition (20 items)"):
            _render_basket_reference()
        return

    # ── Alpha Signal ──────────────────────────────────────────────────────
    _render_alpha_signal()

    # ── 180-Day Index History Chart ───────────────────────────────────────────
    _render_cpi_overlay(store)

    # ── Index Metrics ─────────────────────────────────────────────────────────
    st.subheader("Composite Price Level Index (Laspeyres, base = 100)")
    _render_index_cards(store)

    # ── Sub-Group Bar Chart ───────────────────────────────────────────────────
    st.subheader("Price Change by CPI Food Sub-Group (%)")
    _render_group_chart(store)

    # ── Price Table ───────────────────────────────────────────────────────────
    st.subheader("Current Basket Prices")
    _render_price_table(store)

    with st.expander("Basket composition (20 items)"):
        _render_basket_reference()


# ────────────────────────────────────────────────────────────────────────────

def _render_alpha_signal():
    """Calls assessments engine and renders the alpha signal prominently at tab top."""
    from engine.assessments import _cpi_alpha_signal
    from ui._mode import is_plain
    _TONE_FN = {"success": st.success, "info": st.info, "warning": st.warning, "error": st.error}
    try:
        text, plain, tone = _cpi_alpha_signal()
        st.subheader("📡 Proprietary Alpha Signal")
        _TONE_FN.get(tone, st.info)(plain if is_plain() else text)
    except Exception as e:
        st.info(f"📡 Proprietary Alpha Signal unavailable: {e}")

def _render_price_table(store: EcommStore):
    am_prices = {r["item_id"]: r for r in store.get_latest_prices("amazon")}

    rows = []
    for item in BASKET:
        iid = item["item_id"]
        am = am_prices.get(iid)
        
        row = {
            "Item":        item["name"],
            "Amazon Matched Product": am["item_name"] if am else "—",
            "CPI Group":   item["cpi_group"],
            "Unit Query":  item["unit"],
            "Amazon (₹)":   f"₹{am['price']:.0f}" if am else "—",
        }
        rows.append(row)

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_index_cards(store: EcommStore):
    cols = st.columns(2)
    for col, platform in zip(cols[:1], ["amazon"]):
        history = store.get_index_history(platform, limit=2)
        if not history:
            col.metric(platform.title(), "—", help="No data yet")
            continue
        latest_idx = history[-1]["index_value"]
        prev_idx   = history[-2]["index_value"] if len(history) >= 2 else None
        delta_str  = f"{latest_idx - prev_idx:+.1f} pts" if prev_idx else None
        col.metric(
            label=f"{platform.title()} Index",
            value=f"{latest_idx:.1f}",
            delta=delta_str,
            help=f"Coverage: {history[-1]['coverage_pct']:.0f}% · {history[-1]['items_count']} items",
        )


def _render_group_chart(store: EcommStore):
    all_components = []
    for platform in ["amazon"]:
        latest = store.get_latest_prices(platform)
        base   = store.get_base_prices(platform)
        if not latest or not base:
            continue
        idx = compute_index(latest, base)
        for c in idx["components"]:
            c["platform"] = platform
        all_components.extend(idx["components"])

    if not all_components:
        st.info("No index data available yet.")
        return

    summary_rows = []
    for platform in ["amazon"]:
        comps = [c for c in all_components if c["platform"] == platform]
        for g in group_summary(comps):
            summary_rows.append({
                "Platform":   platform.title(),
                "CPI Group":  g["cpi_group"],
                "Change (%)": g["avg_pct_change"],
            })

    if summary_rows:
        df    = pd.DataFrame(summary_rows)
        pivot = df.pivot(index="CPI Group", columns="Platform", values="Change (%)")
        st.bar_chart(pivot)


def _render_cpi_overlay(store: EcommStore):
    am_history = store.get_index_history("amazon", limit=180)
    if not am_history:
        return

    st.subheader("Basket Index Over Time vs CPI Food")

    index_rows: dict = {}
    for row in am_history:
        dt = row["computed_at"][:10]
        index_rows.setdefault(dt, {})["Amazon Index"] = row["index_value"]

    idx_df = pd.DataFrame.from_dict(index_rows, orient="index").sort_index()
    idx_df.index.name = "Date"

    cpi_hist = CPIStore().get_history(months=24)
    if cpi_hist:
        cpi_food = {r["reference_month"]: r.get("food_yoy")
                    for r in cpi_hist if r.get("food_yoy") is not None}
        if cpi_food:
            cpi_df = pd.DataFrame.from_dict(cpi_food, orient="index", columns=["CPI Food YoY (%)"])
            cpi_df.index.name = "Date"
            st.caption("Basket index = price level (100 = base) · CPI food = YoY % — different scales")
            c1, c2 = st.columns(2)
            c1.line_chart(idx_df)
            c2.line_chart(cpi_df)
            return

    st.line_chart(idx_df)


def _render_basket_reference():
    rows = [
        {"Item": i["name"], "CPI Group": i["cpi_group"],
         "Unit": i["unit"], "Basket Wt": f"{i['weight']:.1f}%"}
        for i in BASKET
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
