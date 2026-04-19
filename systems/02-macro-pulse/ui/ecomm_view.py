"""
E-commerce price tracker tab.
Shows Blinkit & Zepto basket prices, Laspeyres index, and CPI food overlay.
"""
import streamlit as st
import pandas as pd
from db.store import EcommStore, CPIStore
from engine.ecomm_basket import BASKET, CPI_GROUPS
from engine.ecomm_index import compute_index, group_summary


def render_ecomm_section():
    store = EcommStore()
    has_data = store.has_data()

    st.markdown(
        "**Blinkit & Zepto basket tracker** · 20 items across 9 CPI food sub-groups · "
        "Delhi (110001) · Laspeyres index (base = first scrape)"
    )

    # ── Scrape controls ─────────────────────────────────────────────────────
    col_btn, col_status = st.columns([1, 3])
    with col_btn:
        run_scrape = st.button("Run Price Scrape", type="primary")
    with col_status:
        bl_last = store.last_scraped_at("blinkit")
        zt_last = store.last_scraped_at("zepto")
        if bl_last or zt_last:
            st.caption(
                f"Last scraped · Blinkit: {bl_last or '—'} · Zepto: {zt_last or '—'}"
            )
        else:
            st.caption("No scrape data yet. Click **Run Price Scrape** to collect prices.")

    if run_scrape:
        _run_scrape_with_progress(store)
        st.rerun()

    if not has_data:
        st.info(
            "No price data yet. Click **Run Price Scrape** above — it takes ~3 minutes to scrape "
            "20 items from Blinkit and Zepto. Requires `playwright install chromium`."
        )
        _render_basket_reference()
        return

    # ── Latest prices table ─────────────────────────────────────────────────
    st.subheader("Current Basket Prices")
    _render_price_table(store)

    # ── Index cards ─────────────────────────────────────────────────────────
    st.subheader("Laspeyres Food Price Index (base = 100 at first scrape)")
    _render_index_cards(store)

    # ── Category heatmap ────────────────────────────────────────────────────
    st.subheader("Price Change by CPI Food Sub-Group (%)")
    _render_group_chart(store)

    # ── Index vs CPI food overlay ────────────────────────────────────────────
    _render_cpi_overlay(store)

    # ── Basket reference ────────────────────────────────────────────────────
    with st.expander("Basket composition"):
        _render_basket_reference()


# ────────────────────────────────────────────────────────────────────────────
# Private helpers
# ────────────────────────────────────────────────────────────────────────────

def _run_scrape_with_progress(store: EcommStore):
    from engine.ecomm_index import run_scrape_and_store
    bar = st.progress(0, text="Starting scrape...")
    try:
        bar.progress(10, text="Scraping Blinkit...")
        results = run_scrape_and_store(platforms=["blinkit"])
        bar.progress(55, text="Scraping Zepto...")
        results.update(run_scrape_and_store(platforms=["zepto"]))
        bar.progress(100, text="Done.")
        _show_scrape_results(results)
    except Exception as e:
        bar.empty()
        st.error(f"Scrape failed: {e}")


def _show_scrape_results(results: dict):
    for platform, idx in results.items():
        if "error" in idx:
            st.warning(f"{platform.title()}: {idx['error']}")
        elif idx.get("index_value"):
            st.success(
                f"{platform.title()}: {idx['items_count']} items scraped · "
                f"Index = {idx['index_value']:.1f} · Coverage {idx['coverage_pct']:.0f}%"
            )
        else:
            st.warning(f"{platform.title()}: scrape completed but index could not be computed.")


def _render_price_table(store: EcommStore):
    bl_prices = {r["item_id"]: r for r in store.get_latest_prices("blinkit")}
    zt_prices = {r["item_id"]: r for r in store.get_latest_prices("zepto")}

    rows = []
    for item in BASKET:
        iid = item["item_id"]
        bl = bl_prices.get(iid)
        zt = zt_prices.get(iid)
        row = {
            "Item":         item["name"],
            "CPI Group":    item["cpi_group"],
            "Unit":         item["unit"],
            "Blinkit (₹)":  f"₹{bl['price']:.0f}" if bl else "—",
            "Zepto (₹)":    f"₹{zt['price']:.0f}" if zt else "—",
        }
        # price diff
        if bl and zt:
            diff = zt["price"] - bl["price"]
            row["Diff (₹)"] = f"{diff:+.0f}"
        else:
            row["Diff (₹)"] = "—"
        rows.append(row)

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_index_cards(store: EcommStore):
    platforms = ["blinkit", "zepto"]
    cols = st.columns(len(platforms))
    for col, platform in zip(cols, platforms):
        with col:
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
        base = store.get_base_prices(platform)
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
        df = pd.DataFrame(summary_rows)
        pivot = df.pivot(index="CPI Group", columns="Platform", values="Change (%)")
        st.bar_chart(pivot)


def _render_cpi_overlay(store: EcommStore):
    bl_history = store.get_index_history("blinkit", limit=90)
    zt_history = store.get_index_history("zepto", limit=90)

    if not bl_history and not zt_history:
        return

    st.subheader("Basket Index Over Time vs CPI Food")

    index_rows = {}
    for row in bl_history:
        dt = row["computed_at"][:10]
        index_rows.setdefault(dt, {})["Blinkit Index"] = row["index_value"]
    for row in zt_history:
        dt = row["computed_at"][:10]
        index_rows.setdefault(dt, {})["Zepto Index"] = row["index_value"]

    idx_df = pd.DataFrame.from_dict(index_rows, orient="index").sort_index()
    idx_df.index.name = "Date"

    # Add CPI food if available
    cpi_hist = CPIStore().get_history(months=24)
    if cpi_hist:
        cpi_food = {
            r["reference_month"]: r.get("food_yoy")
            for r in cpi_hist if r.get("food_yoy") is not None
        }
        if cpi_food:
            cpi_df = pd.DataFrame.from_dict(cpi_food, orient="index", columns=["CPI Food YoY (%)"])
            cpi_df.index.name = "Date"
            st.caption("Note: basket index = level (100 = base), CPI food = YoY %. Different scales.")
            col_idx, col_cpi = st.columns(2)
            with col_idx:
                st.line_chart(idx_df)
            with col_cpi:
                st.line_chart(cpi_df)
            return

    st.line_chart(idx_df)


def _render_basket_reference():
    rows = [
        {
            "Item":      item["name"],
            "CPI Group": item["cpi_group"],
            "Unit":      item["unit"],
            "Basket Wt": f"{item['weight']:.1f}%",
        }
        for item in BASKET
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
