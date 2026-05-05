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
from db.store import BriefStore, CommunicationStore, MemberViewStore, MPCDecisionStore
from engine.archetype import classify_statement, find_most_similar_meeting
from engine.cross_ref import macro_print_summary
from engine.diff_engine import diff_documents, summarize_diff
from engine.plain_summary import render_plain_summary
from engine.stance_engine import analyze_communication
from ui._mode import is_plain, render_glossary_expander


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

    # Statement archetype + nearest-historical-match
    _render_archetype_badge(latest_decision, prior_decision, decisions.get_history(limit=24))

    # Cross-reference: latest CPI/IIP prints from macro-pulse
    _render_macro_callout(latest_decision)

    # Always-available glossary so a non-economist reader can decode terms
    render_glossary_expander([
        "Repo Rate", "MPC", "MPC Vote", "Stance", "Withdrawal of accommodation",
        "Neutral stance", "Accommodative", "Forward guidance", "Hawkish", "Dovish",
        "Headline CPI", "RBI Target",
    ])

    st.divider()

    # ─── Tabs ──────────────────────────────────────────────────────────────
    tab_changed, tab_proj, tab_series, tab_members, tab_speeches, tab_feed, tab_brief = st.tabs([
        "What Changed", "Projections", "Stance Time Series",
        "Member Views", "Recent Speeches", "Document Feed", "AI Brief",
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

    with tab_members:
        _render_member_views(latest_decision)

    with tab_speeches:
        _render_speech_feed()

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


def _render_archetype_badge(
    latest_decision: dict | None,
    prior_decision: dict | None,
    history: list[dict],
) -> None:
    """Show the statement archetype + 'reads most like ...' pattern match."""
    if latest_decision is None:
        return

    archetype = classify_statement(latest_decision, prior_decision)
    similar = find_most_similar_meeting(
        archetype, history,
        exclude_meeting_date=latest_decision.get("meeting_date"),
    )

    badge_color = {
        "rate_cut":          "#388E3C",
        "rate_hike":         "#D32F2F",
        "pre_cut_signal":    "#1976D2",
        "hawkish_pivot":     "#E65100",
        "insurance_pause":   "#7B1FA2",
        "operational_tweak": "#616161",
    }.get(archetype.label, "#1976D2")

    similar_phrase = (
        f"Reads most like the **{similar['meeting_date']}** meeting "
        f"(repo {similar['repo_rate']:.2f}%)."
        if similar else
        "Not enough historical data for a similar-meeting match yet."
    )

    st.markdown(
        f"""
<div style='background: {badge_color}11; border-left: 4px solid {badge_color};
            padding: 12px 16px; border-radius: 4px; margin: 8px 0 16px 0;'>
  <div style='font-size: 11px; color: {badge_color}; font-weight: 700;
              letter-spacing: 0.6px; text-transform: uppercase;'>Archetype</div>
  <div style='font-size: 18px; font-weight: 700; color: #1C1E21; margin-top: 4px;'>
    {archetype.display}
  </div>
  <div style='font-size: 13px; color: #555; margin-top: 6px;'>
    {archetype.rationale}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.caption(similar_phrase)


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

def _render_member_views(latest_decision: dict | None) -> None:
    """
    Per-member analysis from MPC Minutes — current meeting roster + a cross-
    meeting heatmap so analysts can spot persistent dissenters and shifting
    votes. Only the Minutes contain member-level data; the Statement is
    Governor-only prose.
    """
    store = MemberViewStore()
    if store.count() == 0:
        st.info(
            "Per-member views become available after MPC Minutes are ingested. "
            "The Minutes are released ~2 weeks after each MPC meeting."
        )
        return

    # Latest meeting member roster
    if latest_decision and latest_decision.get("meeting_date"):
        members = store.get_for_meeting(latest_decision["meeting_date"])
    else:
        members = []

    if members:
        st.subheader(f"Member views — {members[0].get('meeting_date', '')}")
        rows = []
        for m in members:
            rows.append({
                "Member": f"{m.get('honorific') or ''} {m['member_name']}".strip(),
                "Vote":   m.get("vote") or "—",
                "Stance": (m.get("stance_label") or "—").replace("_", " ").title(),
                "Stance score": (
                    f"{m['stance_score']:+.2f}" if m.get("stance_score") is not None else "—"
                ),
                "Inflation read": (m.get("inflation_label") or "—").replace("_", " ").title(),
                "Growth read":    (m.get("growth_label") or "—").replace("_", " ").title(),
            })
        st.dataframe(
            pd.DataFrame(rows), use_container_width=True, hide_index=True,
        )

        # Reveal individual statements (long-form audit)
        with st.expander("Read individual member statements"):
            for m in members:
                st.markdown(f"**{m.get('honorific') or ''} {m['member_name']}**")
                st.write(m.get("statement_excerpt") or "—")
                st.divider()

    # Cross-meeting heatmap — table form (Streamlit native chart heatmap is
    # finicky; a styled dataframe is more readable for an analyst)
    st.subheader("Member stance heatmap (across meetings)")
    heatmap_rows = store.heatmap_data()
    if heatmap_rows:
        df = pd.DataFrame(heatmap_rows)
        df["stance_pretty"] = df["stance_label"].fillna("—").str.replace("_", " ").str.title()
        pivot = df.pivot_table(
            index="member_name",
            columns="meeting_date",
            values="stance_pretty",
            aggfunc="first",
        ).fillna("—")
        st.dataframe(pivot, use_container_width=True)
        st.caption(
            "One row per MPC member, one column per meeting. Blanks indicate "
            "either the member wasn't on the committee or their statement "
            "didn't trigger any stance phrase."
        )


@st.cache_data(ttl=3600, show_spinner=False)
def _cached_speech_listing() -> list[dict]:
    """1-hour cache so we don't hammer RBI's RSS endpoint on every rerun."""
    from scrapers.rbi_speech import fetch_speech_listing
    return fetch_speech_listing()


def _render_speech_feed() -> None:
    """
    Recent Governor + Deputy Governor speeches from RBI's RSS feed.
    Inter-meeting tracking — surfaces language drift between MPCs.

    Live RSS query (cached 1 hour). Full transcripts are linked, not
    ingested in v1; ingestion is Phase 2.
    """
    st.subheader("Recent RBI speeches")
    st.caption(
        "Live from RBI's speeches feed (cached 1 hour). "
        "Use these between MPC meetings to track whether the Governor or "
        "Deputy Governors are leaning more hawkish or dovish than the "
        "last formal Statement."
    )

    items = _cached_speech_listing()
    if not items:
        st.info(
            "Could not fetch the RBI speeches RSS feed — try again later, "
            "or visit [rbi.org.in/speeches](https://rbi.org.in/Scripts/BS_SpeechesView.aspx) directly."
        )
        return

    for item in items[:10]:
        with st.container(border=True):
            left, right = st.columns([3, 1])
            with left:
                st.markdown(f"**{item['title'][:140]}**")
                st.caption(item.get("pub_date") or "")
            with right:
                if item.get("link"):
                    st.markdown(
                        f"<a href='{item['link']}' target='_blank' "
                        f"style='font-size:13px;'>Open ↗</a>",
                        unsafe_allow_html=True,
                    )


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

    # In Plain English mode, render the deterministic lay-reader summary
    # alongside the analyst-style brief. No LLM call, no API cost.
    if is_plain():
        decision = MPCDecisionStore().get_latest()
        prior = (
            MPCDecisionStore().get_previous(decision["meeting_date"])
            if decision else None
        )
        if decision:
            st.markdown("##### What this means, plainly")
            st.info(render_plain_summary(decision, prior))

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
