"""
E-commerce price tracker tab.
Shows Blinkit & Zepto basket prices, Laspeyres index, and CPI food overlay.
"""
import streamlit as st
import pandas as pd
from db.store import EcommStore, CPIStore
from engine.ecomm_basket import BASKET
from engine.ecomm_index import compute_index, group_summary


def render_ecomm_section(pw_ready: bool = True, pw_err: str = ""):
    store = EcommStore()

    st.info(
        "**Proprietary Intelligence:** This High-Frequency Pulse Index is a custom composite "
        "measure of urban food inflation. It tracks a fixed basket of 20 items across 9 CPI "
        "sub-groups in real-time, providing a leading signal 15-30 days before official MOSPI releases."
    )
    st.markdown(
        "**Engine Details** · Blinkit & Zepto basket tracker · "
        "Delhi (110001) · Laspeyres index (base = first scrape)"
    )

    # ── Playwright status warning ────────────────────────────────────────────
    if not pw_ready:
        st.warning(
            f"Browser setup issue — scraping may fail. Error: `{pw_err or 'unknown'}`\n\n"
            "If this persists on Streamlit Cloud, check `packages.txt` and redeploy."
        )

    # ── Scrape controls ──────────────────────────────────────────────────────
    col_btn, col_status = st.columns([1, 3])
    with col_btn:
        run_scrape = st.button("Run Price Scrape", type="primary")
    with col_status:
        bl_last = store.last_scraped_at("blinkit")
        zt_last = store.last_scraped_at("zepto")
        if bl_last or zt_last:
            st.caption(f"Last scraped · Blinkit: {bl_last or '—'} · Zepto: {zt_last or '—'}")
        else:
            st.caption("No scrape data yet. Click **Run Price Scrape** to collect prices.")

    # ── Show results/errors from previous scrape (persisted across rerun) ────
    if "scrape_msg" in st.session_state:
        for level, msg in st.session_state.pop("scrape_msg"):
            getattr(st, level)(msg)

    # ── Run scrape — save to session_state, THEN rerun ───────────────────────
    if run_scrape:
        msgs = []
        with st.spinner("Scraping Blinkit & Zepto (2–3 min)…"):
            from engine.ecomm_index import run_scrape_and_store
            try:
                results = run_scrape_and_store(platforms=["blinkit", "zepto"])
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

    # ── Data display ─────────────────────────────────────────────────────────
    if not store.has_data():
        st.info(
            "No price data yet. Click **Run Price Scrape** above — it takes ~2–3 minutes. "
            "The scraper uses a headless Chromium browser to check Blinkit and Zepto prices."
        )
        with st.expander("Basket composition (20 items)"):
            _render_basket_reference()
        return

    st.subheader("Current Basket Prices")
    _render_price_table(store)

    st.subheader("Composite Price Level Index (Laspeyres, base = 100)")
    _render_index_cards(store)

    st.subheader("Price Change by CPI Food Sub-Group (%)")
    _render_group_chart(store)

    _render_cpi_overlay(store)

    with st.expander("Basket composition (20 items)"):
        _render_basket_reference()


# ────────────────────────────────────────────────────────────────────────────

def _render_price_table(store: EcommStore):
    bl_prices = {r["item_id"]: r for r in store.get_latest_prices("blinkit")}
    zt_prices = {r["item_id"]: r for r in store.get_latest_prices("zepto")}

    rows = []
    for item in BASKET:
        iid = item["item_id"]
        bl = bl_prices.get(iid)
        zt = zt_prices.get(iid)
        row = {
            "Item":        item["name"],
            "CPI Group":   item["cpi_group"],
            "Unit":        item["unit"],
            "Blinkit (₹)": f"₹{bl['price']:.0f}" if bl else "—",
            "Zepto (₹)":   f"₹{zt['price']:.0f}" if zt else "—",
        }
        if bl and zt:
            diff = zt["price"] - bl["price"]
            row["Diff (₹)"] = f"{diff:+.0f}"
        else:
            row["Diff (₹)"] = "—"
        rows.append(row)

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_index_cards(store: EcommStore):
    cols = st.columns(2)
    for col, platform in zip(cols, ["blinkit", "zepto"]):
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
    for platform in ["blinkit", "zepto"]:
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
    for platform in ["blinkit", "zepto"]:
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
    bl_history = store.get_index_history("blinkit", limit=90)
    zt_history = store.get_index_history("zepto",   limit=90)
    if not bl_history and not zt_history:
        return

    st.subheader("Basket Index Over Time vs CPI Food")

    index_rows: dict = {}
    for row in bl_history:
        dt = row["computed_at"][:10]
        index_rows.setdefault(dt, {})["Blinkit Index"] = row["index_value"]
    for row in zt_history:
        dt = row["computed_at"][:10]
        index_rows.setdefault(dt, {})["Zepto Index"] = row["index_value"]

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
