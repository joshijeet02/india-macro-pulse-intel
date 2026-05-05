"""
View-mode toggle and shared UI helpers.

Mirrors the macro-pulse pattern. Two modes:
- "economist": analyst-style copy (default)
- "plain_english": reframed for non-economist readers

The toggle changes how analyst commentary renders. Charts, tables, and
metrics are mode-independent. Glossary expanders are always available.
"""
from __future__ import annotations

import streamlit as st

from engine.glossary import GLOSSARY
from engine.glossary import lookup as _glossary_lookup

MODE_KEY = "rbi_view_mode"
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
                "Plain English: reframes commentary for non-economist "
                "readers — the headline RBI numbers stay the same."
            ),
        )
        if st.session_state[MODE_KEY] == PLAIN:
            st.caption(
                "💡 Plain English is applied to AI briefs and stance "
                "interpretation. Use the **glossary expanders** on each "
                "tab for term definitions."
            )


def current_mode() -> str:
    return st.session_state.get(MODE_KEY, ECONOMIST)


def is_plain() -> bool:
    return current_mode() == PLAIN


def render_glossary_expander(terms: list[str], context_label: str = "this section") -> None:
    """Always-visible expander populated with definitions for the given terms."""
    rows = [(t, GLOSSARY[t]) for t in terms if t in GLOSSARY]
    if not rows:
        return
    with st.expander(f"📖 What do these terms mean? ({len(rows)})"):
        for term, definition in rows:
            st.markdown(f"**{term}** — {definition}")


def glossary_tooltip(term: str, label: str | None = None) -> str:
    """Inline tooltip for use with st.markdown(unsafe_allow_html=True)."""
    label = label or term
    definition = _glossary_lookup(term)
    if not definition:
        return label
    safe = definition.replace('"', "&quot;")
    return (
        f'<abbr title="{safe}" style="text-decoration: underline dotted; '
        f'cursor: help;">{label}</abbr>'
    )
