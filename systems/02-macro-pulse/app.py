import streamlit as st
# Trigger redeploy: 2026-04-19 19:44
import os
import sys
import subprocess

def _install_playwright():
    try:
        import playwright
    except ImportError:
        return
    
    # Check if chromium is already installed in the standard playwright path
    # On Streamlit Cloud/Linux it's usually in ~/.cache/ms-playwright/
    if not os.path.exists(os.path.expanduser("~/.cache/ms-playwright")):
        try:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        except Exception as e:
            print(f"Playwright install failed: {e}")

_install_playwright()

sys.path.insert(0, os.path.dirname(__file__))


@st.cache_resource(show_spinner=False)
def _install_playwright_browser():
    """Install Playwright's Chromium binary once per container lifecycle."""
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True,
    )


_install_playwright_browser()

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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
    
    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif;
    }
    
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    
    h1 { 
        font-weight: 800 !important; 
        color: #1C1E21 !important;
        letter-spacing: -0.5px !important;
        margin-bottom: 0.5rem !important;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
    }

    .stTabs [data-baseweb="tab"] {
        height: 44px;
        white-space: pre-wrap;
        background-color: #F0F2F6;
        border-radius: 8px 8px 0px 0px;
        padding: 10px 20px;
        color: #555;
        font-weight: 600;
        border: none;
    }

    .stTabs [aria-selected="true"] {
        background-color: #2E5BFF !important;
        color: white !important;
    }
    
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 700 !important;
        color: #2E5BFF !important;
    }
    
    .stDivider {
        margin-top: 2rem !important;
        margin-bottom: 2rem !important;
    }
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
st.caption("Strategic release intelligence for India's economic indicators · Real-time proprietary e-commerce signals")

render_release_calendar()
st.divider()

tab_cpi, tab_iip, tab_surprise, tab_brief, tab_ecomm = st.tabs([
    "CPI Decomposition", "IIP Decomposition", "Surprise Tracker", "Flash Brief", "Proprietary Pulse"
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
