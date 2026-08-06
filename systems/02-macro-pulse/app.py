import streamlit as st
import os
import sys
import subprocess

# Must be set before any playwright import so the binary lands in /tmp (writable on Streamlit Cloud)
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "/tmp/pw-browsers"
sys.path.insert(0, os.path.dirname(__file__))


@st.cache_resource(show_spinner=False)
def ensure_playwright_chromium() -> tuple[bool, str]:
    """
    Install Playwright Chromium, once per container lifecycle.

    Called LAZILY — only when someone actually presses "Run Price Scrape" —
    never at import time.

    This used to run at module level, before a single pixel rendered. It
    downloads roughly 150 MB, so every cold container start left a visitor
    staring at Streamlit's "taking longer than normal" screen for minutes
    before seeing anything. Verified in a browser against the deployed app.

    Nothing on the page needs a browser: the live index, the CPI and IIP
    tabs, the release calendar and the nowcast are all plain HTTP or local
    computation. Only the Amazon scrape needs Chromium, and that is a
    deliberate button press where a wait is expected and explained.
    """
    result = subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
        text=True,
        env={**os.environ, "PLAYWRIGHT_BROWSERS_PATH": "/tmp/pw-browsers"},
    )
    return result.returncode == 0, result.stderr.strip()

from db.schema import init_db
from db.store import CPIStore

st.set_page_config(
    page_title="India Macro Pulse",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from ui._theme import inject_theme, render_page_header

inject_theme()

init_db()
if CPIStore().count() == 0:
    from seed.historical_data import seed
    seed()

# Hydrate Amazon basket from committed JSON if the ephemeral DB is empty.
# This makes the basket index survive Streamlit Cloud container restarts.
from seed.amazon_persist import hydrate_db_from_json
hydrate_db_from_json()

# Recompute the basket index history from hydrated price observations.
# Backfills any scrape runs that don't yet have a corresponding index row —
# a count comparison rather than a boolean check, so a single manually-triggered
# scrape can't permanently lock the chart at one point.
from db.store import EcommStore
from engine.ecomm_index import compute_index
_ecomm = EcommStore()
if _ecomm.has_data():
    _runs = set(_ecomm.get_scrape_runs("amazon", limit=10000))
    _base = _ecomm.get_base_prices("amazon")
    if _base:
        _existing_idx_ts = {
            r["computed_at"]
            for r in _ecomm.get_index_history("amazon", limit=10000)
        }
        _missing = sorted(_runs - _existing_idx_ts)  # oldest first
        for _ts in _missing:
            _snapshot = _ecomm.get_prices_at("amazon", _ts)
            _idx = compute_index(_snapshot, _base)
            if _idx["index_value"] is not None:
                _ecomm.insert_index({
                    "platform":     "amazon",
                    "computed_at":  _ts,
                    "index_value":  _idx["index_value"],
                    "coverage_pct": _idx["coverage_pct"],
                    "items_count":  _idx["items_count"],
                })

from ui._mode import render_mode_toggle
from ui.live_view import render_live_index
from ui.nowcast_view import render_nowcast_header
from ui.calendar_view import render_release_calendar
from ui.header_status import next_release_summary
from ui.cpi_view import render_cpi_section
from ui.iip_view import render_iip_section
from ui.surprise_view import render_surprise_history
from ui.brief_view import render_brief_section
from ui.ecomm_view import render_ecomm_section

render_mode_toggle()

render_page_header(
    "India Macro Pulse",
    "Live CPI estimate between official prints · Release intelligence for India's economic indicators",
    status=next_release_summary(),
)

# Everything below lives in a tab. It used to be a single column: the live
# estimate, then the model cross-check, then the release calendar, and only
# then the tabs — so the tab strip was several screens down and most of the
# app was reachable only by scrolling past content the visitor had already
# read. Each tab now answers one question, and the strip is the first thing
# under the title.
#
# Order is by what a visitor came for. The nowcast is the product and leads;
# the official decompositions come next; the calendar and the accuracy record
# sit behind them because they are checked occasionally, not on every visit.
tab_now, tab_cpi, tab_iip, tab_pulse, tab_releases, tab_brief = st.tabs([
    "Nowcast",
    "CPI",
    "IIP",
    "Proprietary Pulse",
    "Releases",
    "Flash Brief",
])

with tab_now:
    # A CALCULATION, not a forecast: fetch current prices, move the divisions
    # we can price, re-aggregate with official weights.
    render_live_index()
    st.divider()
    # Clearly labelled as a different kind of thing — a statistical estimate
    # from the published series, useful as a cross-check on the measured index
    # rather than as a second headline.
    with st.expander("Statistical cross-check (model estimate, not a measurement)"):
        render_nowcast_header()

with tab_cpi:
    render_cpi_section()

with tab_iip:
    render_iip_section()

with tab_pulse:
    render_ecomm_section(ensure_playwright_chromium)

with tab_releases:
    render_release_calendar()
    st.divider()
    render_surprise_history()

with tab_brief:
    render_brief_section()
