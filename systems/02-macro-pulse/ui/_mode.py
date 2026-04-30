"""
View-mode toggle and shared UI helpers used across tabs.

Two viewing modes:
- "economist"     → analyst-style copy (default)
- "plain_english" → reframed for non-economist readers

State persists in st.session_state under MODE_KEY. Tabs read it via
current_mode() and pick the right field on each assessment dict (text /
text_plain). The Streamlit-native Mode toggle is rendered once from the
top of app.py via render_mode_toggle().
"""
from __future__ import annotations

import streamlit as st

from engine.glossary import lookup as _glossary_lookup

MODE_KEY = "view_mode"
ECONOMIST = "economist"
PLAIN = "plain_english"

_LABELS = {
    ECONOMIST: "Economist",
    PLAIN: "Plain English",
}


def render_mode_toggle() -> None:
    """Render the radio toggle (sidebar). Initializes session state if needed."""
    if MODE_KEY not in st.session_state:
        st.session_state[MODE_KEY] = ECONOMIST

    with st.sidebar:
        st.markdown("### Analysis tone")
        st.radio(
            "Tone",
            options=[ECONOMIST, PLAIN],
            format_func=lambda v: _LABELS[v],
            key=MODE_KEY,
            label_visibility="collapsed",
            help=(
                "Economist: analyst-style language for macro readers.  "
                "Plain English: reframes the 'What This Means' commentary "
                "for non-economist readers. Charts, metrics, and tables "
                "stay the same regardless of mode."
            ),
        )
        if st.session_state[MODE_KEY] == PLAIN:
            st.caption(
                "💡 Plain English is applied to the analyst commentary tabs. "
                "Use the **glossary expanders** on each tab for term definitions."
            )


def current_mode() -> str:
    return st.session_state.get(MODE_KEY, ECONOMIST)


def is_plain() -> bool:
    return current_mode() == PLAIN


def assessment_text(assessment: dict) -> str:
    """Pick the right field based on the active mode, with a safe fallback."""
    if is_plain():
        return assessment.get("text_plain") or assessment.get("text", "")
    return assessment.get("text", "")


def glossary_tooltip(term: str, label: str | None = None) -> str:
    """
    Inline glossary tooltip — returns an HTML <abbr> with the definition as
    the title attribute. Use with `st.markdown(..., unsafe_allow_html=True)`.
    """
    label = label or term
    definition = _glossary_lookup(term)
    if not definition:
        return label
    safe = definition.replace('"', "&quot;")
    return f'<abbr title="{safe}" style="text-decoration: underline dotted; cursor: help;">{label}</abbr>'


def render_glossary_expander(terms: list[str], context_label: str = "this section") -> None:
    """
    Render an expander populated with definitions for the given terms.
    Always visible regardless of mode — economists may also want a quick
    reminder of what we mean by 'core' vs 'headline'.
    """
    from engine.glossary import GLOSSARY
    rows = [(t, GLOSSARY[t]) for t in terms if t in GLOSSARY]
    if not rows:
        return
    with st.expander(f"📖 What do these terms mean? ({len(rows)})"):
        for term, definition in rows:
            st.markdown(f"**{term}** — {definition}")
