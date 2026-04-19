import streamlit as st
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from db.schema import init_db
from db.store import CPIStore

st.set_page_config(
    page_title="India Macro Pulse",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    h1 { font-size: 1.6rem !important; }
</style>
""", unsafe_allow_html=True)

init_db()
if CPIStore().count() == 0:
    from seed.historical_data import seed
    seed()

from ui.calendar_view import render_release_calendar
from ui.cpi_view import render_cpi_section
from ui.iip_view import render_iip_section
from ui.surprise_view import render_surprise_history
from ui.brief_view import render_brief_section
from ui.ecomm_view import render_ecomm_section

st.title("India Macro Pulse")
st.caption("Real-time data release intelligence · CPI · IIP · Surprise Tracker · Flash Briefs · Price Tracker")

render_release_calendar()
st.divider()

tab_cpi, tab_iip, tab_surprise, tab_brief, tab_ecomm = st.tabs([
    "CPI Decomposition", "IIP Decomposition", "Surprise Tracker", "Flash Brief", "Price Tracker"
])

with tab_cpi:
    render_cpi_section()

with tab_iip:
    render_iip_section()

with tab_surprise:
    render_surprise_history()

with tab_brief:
    render_brief_section()

with tab_ecomm:
    render_ecomm_section()
