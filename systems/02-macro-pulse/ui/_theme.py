"""
Typography and chrome for the app.

Why this file exists:

Streamlit's defaults are tuned for dashboards read at a glance — 14px body
copy, 14px metric labels, 14px tab labels, and full-bleed width. This page is
not that. Almost every block on it is an argument someone has to actually read:
why the base month matters, what was measured versus assumed, why two methods
disagree. At 14px across a 1600px column that reading does not happen; the
reader zooms in or gives up.

Two changes carry most of the improvement:

  1. Body copy to 17px with 1.7 line-height. Long-form explanation, not
     dashboard chrome.
  2. A reading column. `layout="wide"` is right for tables and charts, but
     prose set across the full width of a monitor loses the line-return — the
     eye cannot find the start of the next line. 1240px is the usual ceiling.

Everything else is consistency: one type scale, one accent, one tab treatment.

Colours are deliberately sparse. The accent is used for figures the page is
asserting and nothing else, so a blue number always means "this is a reading".
Text colour is inherited rather than pinned, because Streamlit Cloud lets a
visitor override the theme and hard-coded near-black text disappears on a dark
background.
"""
from __future__ import annotations

import streamlit as st

ACCENT = "#2E5BFF"

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"], button, input, select, textarea {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── Reading column ─────────────────────────────────────────────────────── */
/* Top padding must clear Streamlit's floating 60px header bar, which overlays
   the container rather than pushing it down. Too little and the h1 is sliced
   in half. */
.stMainBlockContainer {
    max-width: 1240px;
    padding-top: 4rem;
    padding-bottom: 5rem;
}

/* ── Type scale ─────────────────────────────────────────────────────────── */
h1 { font-size: 2.4rem !important; font-weight: 800 !important;
     letter-spacing: -1.1px !important; line-height: 1.15 !important;
     margin-bottom: 0.15rem !important; padding-top: 0 !important; }
h2 { font-size: 1.7rem !important; font-weight: 700 !important;
     letter-spacing: -0.5px !important; padding-top: 0.4rem !important; }
h3 { font-size: 1.3rem !important; font-weight: 700 !important;
     letter-spacing: -0.3px !important; padding-top: 0.3rem !important; }

/* Body copy — the main fix. Also applied inside alerts, which carry the
   longest passages on the page. */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li {
    font-size: 1.0625rem;
    line-height: 1.7;
}
[data-testid="stMarkdownContainer"] li { margin-bottom: 0.3rem; }

[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {
    font-size: 0.9375rem !important;
    line-height: 1.6 !important;
    opacity: 0.78;
}

/* ── Alerts ─────────────────────────────────────────────────────────────── */
.stAlert { border-radius: 12px; padding: 1.1rem 1.25rem; }
.stAlert [data-testid="stMarkdownContainer"] p,
.stAlert [data-testid="stMarkdownContainer"] li {
    font-size: 1.0625rem;
    line-height: 1.7;
}

/* ── Metrics ────────────────────────────────────────────────────────────── */
/* Streamlit renders a metric's text through a stMarkdownContainer <p>, so the
   body-copy rule above lands on it too and silently shrinks every headline
   figure to 17px. These have to restate the size at matching specificity —
   sizing stMetricValue alone does nothing, because the <p> inside it wins. */
[data-testid="stMetricLabel"],
[data-testid="stMetricLabel"] p,
[data-testid="stMetricLabel"] [data-testid="stMarkdownContainer"] p {
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    line-height: 1.4 !important;
    opacity: 0.75;
}
[data-testid="stMetricValue"],
[data-testid="stMetricValue"] [data-testid="stMarkdownContainer"] p {
    font-size: 2.3rem !important;
    font-weight: 700 !important;
    letter-spacing: -1.2px !important;
    color: ACCENT_COLOR !important;
    line-height: 1.3 !important;
}
[data-testid="stMetricDelta"],
[data-testid="stMetricDelta"] [data-testid="stMarkdownContainer"] p {
    font-size: 0.95rem !important;
    font-weight: 600 !important;
}

/* ── Tabs ───────────────────────────────────────────────────────────────── */
/* Targeted three ways on purpose. Streamlit's tab internals are BaseWeb's and
   they move between versions: on the deployed build the fill landed but the
   sizing did not, because `aria-selected` and `data-baseweb="tab"` sat on
   different elements than they do locally. `[role="tab"]` and "the button
   inside the tab list" are ARIA and structural contracts rather than
   implementation details, so they survive the version drift. */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background: transparent;
    border-bottom: 1px solid rgba(128, 138, 160, 0.28);
    margin-bottom: 1.6rem;
}
.stTabs [data-baseweb="tab"],
.stTabs [role="tab"],
.stTabs [data-baseweb="tab-list"] button {
    height: 48px !important;
    min-height: 48px;
    display: inline-flex;
    align-items: center;
    font-size: 1rem !important;
    font-weight: 600;
    padding: 0 20px !important;
    border: none;
    border-radius: 10px 10px 0 0;
    background: transparent;
    opacity: 0.72;
}
.stTabs [data-baseweb="tab"]:hover,
.stTabs [role="tab"]:hover,
.stTabs [data-baseweb="tab-list"] button:hover {
    background: rgba(128, 138, 160, 0.12);
    opacity: 1;
}
.stTabs [data-baseweb="tab"] p,
.stTabs [role="tab"] p { font-size: 1rem !important; font-weight: 600 !important; }
.stTabs [aria-selected="true"],
.stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
    background: ACCENT_COLOR !important;
    opacity: 1;
}
.stTabs [aria-selected="true"] p,
.stTabs [aria-selected="true"] { color: #FFFFFF !important; }
/* BaseWeb draws its own underline under the active tab; with a filled tab it
   reads as a stray rule. */
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] { display: none; }

/* ── Expanders ──────────────────────────────────────────────────────────── */
[data-testid="stExpander"] summary p {
    font-size: 1rem !important;
    font-weight: 600 !important;
}
[data-testid="stExpander"] details {
    border-radius: 12px;
    border-color: rgba(128, 138, 160, 0.28);
}

/* ── Controls ───────────────────────────────────────────────────────────── */
.stButton button {
    font-size: 1rem;
    font-weight: 600;
    padding: 0.55rem 1.3rem;
    border-radius: 9px;
}
.stDownloadButton button { font-size: 0.95rem; font-weight: 600; border-radius: 9px; }
[data-testid="stCheckbox"] label p, [data-testid="stRadio"] label p { font-size: 1rem !important; }

/* ── Rules ──────────────────────────────────────────────────────────────── */
hr { margin: 2.25rem 0 !important; opacity: 0.35; }
</style>
"""


def inject_theme() -> None:
    """Apply the stylesheet. Call once, before anything renders."""
    st.markdown(_CSS.replace("ACCENT_COLOR", ACCENT), unsafe_allow_html=True)


def render_page_header(title: str, subtitle: str, status: str | None = None) -> None:
    """
    Page title, one-line positioning statement, and an optional status chip.

    The chip carries whatever a returning visitor checks first — currently the
    next release date. It sits in the header rather than in a panel because it
    is orientation, not analysis, and it should not cost a scroll.
    """
    left, right = st.columns([3, 1.15], vertical_alignment="center")
    with left:
        st.title(title)
        st.caption(subtitle)
    if status:
        with right:
            st.markdown(
                f"""
<div style="border:1px solid rgba(128,138,160,0.32);border-radius:12px;
            padding:0.7rem 0.95rem;text-align:right;">
  <div style="font-size:0.7rem;font-weight:700;letter-spacing:0.09em;
              text-transform:uppercase;opacity:0.6;">Next release</div>
  <div style="font-size:1.02rem;font-weight:700;margin-top:0.15rem;
              line-height:1.35;">{status}</div>
</div>
""",
                unsafe_allow_html=True,
            )
