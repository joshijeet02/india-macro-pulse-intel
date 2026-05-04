import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from db.schema import init_db
from db.store import CommunicationStore
from seed.historical_data import seed
from ui.mpc_view import render_mpc_view


st.set_page_config(
    page_title="RBI Communication Intelligence",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1 { font-weight: 800 !important; color: #1C1E21 !important;
         letter-spacing: -0.5px !important; margin-bottom: 0.5rem !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: transparent; }
    .stTabs [data-baseweb="tab"] {
        height: 44px; background-color: #F0F2F6; border-radius: 8px 8px 0px 0px;
        padding: 10px 20px; color: #555; font-weight: 600; border: none;
    }
    .stTabs [aria-selected="true"] { background-color: #1F4B99 !important; color: white !important; }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem !important; font-weight: 700 !important; color: #1F4B99 !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

init_db()
if CommunicationStore().count() == 0:
    seed()

st.title("RBI Communication Intelligence")
st.caption(
    "MPC-day workbench for India rates analysts. Real Governor's Statements, "
    "structured stance scoring, statement diffs, and projection time series — "
    "with one-click AI brief generation."
)

render_mpc_view()
