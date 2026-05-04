"""
MPC-day workbench — primary tab for sell-side analysts.

Hero card: latest decision (repo rate, vote, stance arrow).
Tabs:
  1. What Changed — paragraph-aligned diff vs prior MPC
  2. Projections — CPI / GDP forecasts vs prior
  3. Stance Time Series — repo rate path + stance + projection trends
  4. Document Feed — full archive
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from ai.brief import generate_communication_brief
from db.store import BriefStore, CommunicationStore, MPCDecisionStore
from engine.cross_ref import macro_print_summary
from engine.diff_engine import diff_documents, summarize_diff
from engine.stance_engine import analyze_communication


_STANCE_COLORS = {
    "withdrawal_of_accommodation": "#D32F2F",
    "calibrated_tightening":       "#E64A19",
    "calibrated_withdrawal":       "#F57C00",
    "neutral":                     "#1976D2",
    "accommodative":               "#388E3C",
}


def render_mpc_view() -> None:
    docs = CommunicationStore()
    decisions = MPCDecisionStore()

    latest_doc = docs.get_latest()
    if latest_doc is None:
        st.warning("No RBI communications in the database. Run `python seed/historical_data.py`.")
        return

    latest_decision = decisions.get_latest()
    prior_decision = (
        decisions.get_previous(latest_decision["meeting_date"])
        if latest_decision else None
    )

    # ─── Hero ──────────────────────────────────────────────────────────────
    _render_hero(latest_doc, latest_decision, prior_decision)

    # Cross-reference: latest CPI/IIP prints from macro-pulse
    _render_macro_callout(latest_decision)

    st.divider()

    # ─── Tabs ──────────────────────────────────────────────────────────────
    tab_changed, tab_proj, tab_series, tab_feed, tab_brief = st.tabs([
        "What Changed", "Projections", "Stance Time Series",
        "Document Feed", "AI Brief",
    ])

    prior_doc = (
        docs.get_previous_in_series(latest_doc["series_key"], latest_doc["published_at"])
        if latest_doc.get("series_key") else None
    )

    with tab_changed:
        _render_what_changed(latest_doc, prior_doc)

    with tab_proj:
        _render_projections(decisions.get_history(limit=12))

    with tab_series:
        _render_time_series(decisions.get_history(limit=24))

    with tab_feed:
        _render_feed(docs)

    with tab_brief:
        _render_brief(latest_doc)


# ─── Hero card ────────────────────────────────────────────────────────────────

def _render_hero(latest_doc: dict, latest_decision: dict | None, prior_decision: dict | None) -> None:
    """Top-of-page summary line analysts can paste into their note's lede."""
    if latest_decision is None:
        # Fall back to document-level info only
        st.subheader(latest_doc.get("title") or "Latest RBI Communication")
        return

    cols = st.columns([1.5, 1.4, 1.4, 1.5, 1])
    cols[0].metric(
        "Repo Rate",
        f"{latest_decision['repo_rate']:.2f}%",
        _format_change(latest_decision["repo_rate_change_bps"]),
    )

    vote = (
        f"{latest_decision['vote_for']}-{latest_decision['vote_against']}"
        if latest_decision.get("vote_for") is not None else "—"
    )
    cols[1].metric("MPC Vote", vote)

    stance_label = latest_decision.get("stance_label") or "neutral"
    prior_stance = (prior_decision or {}).get("stance_label")
    transition = (
        f"{(prior_stance or stance_label).replace('_', ' ')} → "
        f"{stance_label.replace('_', ' ')}"
        if prior_stance and prior_stance != stance_label
        else stance_label.replace('_', ' ')
    )
    cols[2].metric("Stance", stance_label.replace("_", " ").title(), transition)

    cols[3].metric("Meeting", latest_decision["meeting_date"])

    if latest_doc.get("url"):
        cols[4].markdown(
            f'<div style="margin-top: 16px;"><a href="{latest_doc["url"]}" target="_blank">'
            f'📄 RBI source</a></div>',
            unsafe_allow_html=True,
        )

    # Headline lede line for analyst copy
    bps = latest_decision["repo_rate_change_bps"]
    bps_phrase = (
        "kept unchanged" if bps == 0
        else f"raised by {abs(bps)} basis points"
        if bps > 0 else f"reduced by {abs(bps)} basis points"
    )
    lede = (
        f"**RBI {bps_phrase}** the policy repo rate at "
        f"**{latest_decision['repo_rate']:.2f}%** with a **{vote}** vote, "
        f"maintaining a **{stance_label.replace('_', ' ')}** stance "
        f"({latest_decision['meeting_date']})."
    )
    st.info(lede)


def _format_change(bps: int) -> str | None:
    if bps == 0:
        return "unchanged"
    return f"+{bps}bp" if bps > 0 else f"{bps}bp"


def _render_macro_callout(latest_decision: dict | None) -> None:
    """
    Show the latest CPI/IIP prints + a print-vs-projection delta. The whole
    point of the wedge: an analyst reading RBI's latest projection should
    see real prints right next to it, with the surprise computed for free.
    """
    summary = macro_print_summary()
    if not summary["available"]:
        return

    cpi = summary.get("cpi") or {}
    iip = summary.get("iip") or {}

    cpi_yoy = cpi.get("headline_yoy")
    iip_yoy = iip.get("headline_yoy")
    cpi_proj = (latest_decision or {}).get("cpi_projection_curr_value")
    cpi_proj_fy = (latest_decision or {}).get("cpi_projection_curr_fy")

    cols = st.columns([1.4, 1.4, 1.4, 2])
    if cpi_yoy is not None:
        cols[0].metric(
            "Latest CPI",
            f"{cpi_yoy:.2f}%",
            cpi.get("reference_month"),
            delta_color="off",
        )
    if cpi_proj is not None and cpi_yoy is not None:
        delta = cpi_yoy - cpi_proj
        cols[1].metric(
            f"vs RBI projection ({cpi_proj_fy})",
            f"{cpi_proj:.2f}%",
            f"{delta:+.2f}pp",
            delta_color="off",
        )
    if iip_yoy is not None:
        cols[2].metric(
            "Latest IIP",
            f"{iip_yoy:.1f}%",
            iip.get("reference_month"),
            delta_color="off",
        )
    with cols[3]:
        st.caption(
            "Real-time CPI / IIP from the macro-pulse companion app. "
            "[Open macro-pulse ↗](https://india-macro-pulse.streamlit.app)"
        )


# ─── What Changed tab ────────────────────────────────────────────────────────

def _render_what_changed(latest_doc: dict, prior_doc: dict | None) -> None:
    st.subheader("Statement diff vs prior MPC")

    if prior_doc is None:
        st.info(
            "No prior document in this series yet — diff will populate "
            "after the second MPC is ingested."
        )
        st.write(latest_doc.get("summary") or latest_doc["full_text"][:1000])
        return

    diffs = diff_documents(prior_doc["full_text"], latest_doc["full_text"])
    summary = summarize_diff(diffs)

    cols = st.columns(3)
    cols[0].metric("Paragraphs changed", summary["paragraphs_changed"])
    cols[1].metric("Phrases added", len(summary["phrases_added"]))
    cols[2].metric("Phrases removed", len(summary["phrases_removed"]))

    # Surface lexicon-tracked language transitions prominently
    if summary["phrases_added"] or summary["phrases_removed"]:
        st.markdown("##### Tracked language transitions")
        if summary["phrases_added"]:
            st.success("**Newly appeared:** " + ", ".join(f"`{p}`" for p in summary["phrases_added"][:10]))
        if summary["phrases_removed"]:
            st.warning("**Dropped:** " + ", ".join(f"`{p}`" for p in summary["phrases_removed"][:10]))

    # Per-paragraph diff
    st.markdown(f"**Comparing** {prior_doc['published_at']} → {latest_doc['published_at']}")
    if not diffs:
        st.success("Statements are identical paragraph-for-paragraph.")
        return

    for d in diffs[:30]:  # cap render budget
        with st.expander(
            f"¶ {d.paragraph_number}  ·  "
            f"{'➕' if not d.prev_text else '➖' if not d.curr_text else '✏️'}  "
            f"{(d.curr_text or d.prev_text or '')[:80]}",
        ):
            if d.phrases_added:
                st.markdown("**Phrases added:** " + ", ".join(f"`{p}`" for p in d.phrases_added))
            if d.phrases_removed:
                st.markdown("**Phrases removed:** " + ", ".join(f"`{p}`" for p in d.phrases_removed))
            if d.prev_text and d.curr_text:
                lc, rc = st.columns(2)
                with lc:
                    st.caption(f"Prior ({prior_doc['published_at']})")
                    st.write(d.prev_text)
                with rc:
                    st.caption(f"Current ({latest_doc['published_at']})")
                    st.write(d.curr_text)
            elif d.curr_text:
                st.caption("Newly added paragraph")
                st.write(d.curr_text)
            else:
                st.caption("Removed paragraph")
                st.write(d.prev_text)


# ─── Projections tab ─────────────────────────────────────────────────────────

def _render_projections(history: list[dict]) -> None:
    st.subheader("RBI Projections Over Time")
    if not history:
        st.info("No projection data yet.")
        return

    rows = []
    for d in history:
        rows.append({
            "Meeting":     d["meeting_date"],
            "Repo Rate":   f"{d['repo_rate']:.2f}%",
            "Vote":        f"{d['vote_for']}-{d['vote_against']}" if d["vote_for"] is not None else "—",
            "Stance":      d["stance_label"].replace("_", " ").title(),
            "GDP FY":      d.get("gdp_projection_curr_fy") or "—",
            "GDP %":       d.get("gdp_projection_curr_value") or "—",
            "CPI FY":      d.get("cpi_projection_curr_fy") or "—",
            "CPI %":       d.get("cpi_projection_curr_value") or "—",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ─── Stance Time Series tab ──────────────────────────────────────────────────

def _render_time_series(history: list[dict]) -> None:
    st.subheader("Repo Rate Path")
    if not history:
        st.info("Need at least one decision in the store.")
        return

    df = pd.DataFrame(history)
    df["meeting_date"] = pd.to_datetime(df["meeting_date"])
    df = df.set_index("meeting_date")

    if "repo_rate" in df.columns:
        st.line_chart(df["repo_rate"])

    # Stance label time series
    st.subheader("Stance over time")
    stance_df = df[["stance_label"]].copy()
    stance_df["stance_label"] = stance_df["stance_label"].astype(str)
    st.dataframe(stance_df, use_container_width=True)


# ─── Document Feed tab ───────────────────────────────────────────────────────

def _render_feed(docs: CommunicationStore) -> None:
    st.subheader("Recent RBI Communications")
    for row in docs.list_recent(limit=12):
        with st.container(border=True):
            left, right = st.columns([3, 1])
            with left:
                st.markdown(f"**{row['title']}**")
                st.caption(
                    f"{row['document_type']} · {row['published_at']} · "
                    f"{row.get('speaker') or 'Unknown'}"
                )
                st.write((row.get("summary") or "")[:300])
                if row.get("url"):
                    st.markdown(f"[Open at RBI ↗]({row['url']})")
            with right:
                st.metric(
                    "Stance",
                    (row.get("stance_label") or "neutral").replace("_", " ").title(),
                    f"score {row.get('stance_score') or 0:+.2f}",
                )


# ─── AI Brief tab ────────────────────────────────────────────────────────────

def _render_brief(latest_doc: dict) -> None:
    st.subheader(f"AI Brief: {latest_doc['title']}")
    st.warning(
        "**DRAFT — verify before publishing.** This brief is generated by an LLM "
        "from the structured signals; vote splits, repo rate, and other quantitative "
        "claims must be cross-checked against the original RBI source before quotation.",
        icon="⚠️",
    )

    briefs = BriefStore()
    saved = briefs.get_latest(latest_doc["doc_id"])

    if saved:
        st.markdown("##### Most recent saved brief")
        st.write(saved["brief_text"])
        st.caption(f"Generated at {saved.get('generated_at') or 'unknown time'}")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.info(
            "Set `ANTHROPIC_API_KEY` in your environment or Streamlit secrets to "
            "enable on-demand generation."
        )
        return

    if st.button("Generate fresh brief", type="primary"):
        with st.spinner("Generating ..."):
            try:
                signal = analyze_communication(latest_doc["full_text"])
                # Decisions store has the structured numeric fields the prompt expects
                latest_decision = MPCDecisionStore().get_latest() or {}
                doc_for_brief = {
                    **latest_doc,
                    **signal.to_record(),
                    "repo_rate":            latest_decision.get("repo_rate"),
                    "repo_rate_change_bps": latest_decision.get("repo_rate_change_bps"),
                    "vote_for":             latest_decision.get("vote_for"),
                    "vote_against":         latest_decision.get("vote_against"),
                    "gdp_projection_curr_value": latest_decision.get("gdp_projection_curr_value"),
                    "gdp_projection_curr_fy":    latest_decision.get("gdp_projection_curr_fy"),
                    "cpi_projection_curr_value": latest_decision.get("cpi_projection_curr_value"),
                    "cpi_projection_curr_fy":    latest_decision.get("cpi_projection_curr_fy"),
                }
                brief_text = generate_communication_brief(doc_for_brief)
            except EnvironmentError as exc:
                st.error(str(exc))
                return
            except Exception as exc:
                st.error(f"Brief generation failed: {exc}")
                return
            briefs.save(latest_doc["doc_id"], brief_text, model="claude-opus-4-7")
            st.success("Brief generated and saved.")
            st.write(brief_text)
