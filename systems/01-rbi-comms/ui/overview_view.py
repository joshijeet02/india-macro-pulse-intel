import os

import pandas as pd
import streamlit as st

from ai.brief import generate_communication_brief
from db.store import BriefStore, CommunicationStore


def render_overview():
    communications = CommunicationStore()
    briefs = BriefStore()

    latest = communications.get_latest()
    if latest is None:
        st.info("No RBI communication records yet.")
        return

    tone_history = communications.tone_history(limit=12)
    history_df = pd.DataFrame(tone_history)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Latest Tone", latest["tone_label"].title(), latest["document_type"])
    col2.metric("Policy Bias", latest["policy_bias"].title(), latest["published_at"])
    col3.metric("Net Score", latest["net_score"], f"H {latest['hawkish_score']} / D {latest['dovish_score']}")
    col4.metric(
        "Theme Counts",
        latest["inflation_mentions"],
        f"Growth {latest['growth_mentions']} · Liquidity {latest['liquidity_mentions']}",
    )

    tab_latest, tab_history, tab_feed = st.tabs(["Latest Read", "Tone History", "Document Feed"])

    with tab_latest:
        st.subheader(latest["title"])
        st.caption(
            f"{latest['document_type']} · {latest['published_at']} · {latest.get('speaker') or 'Unknown speaker'}"
        )
        st.write(latest.get("summary") or "No summary available.")
        st.text_area("Document Text", latest["full_text"], height=220)

        saved_brief = briefs.get_latest(latest["doc_id"])
        if saved_brief:
            st.markdown("**Saved AI Brief**")
            st.write(saved_brief["brief_text"])

        if st.button("Generate AI Brief for Latest Document", use_container_width=True):
            try:
                brief_text = generate_communication_brief(latest)
            except EnvironmentError as exc:
                st.error(str(exc))
            else:
                briefs.save(latest["doc_id"], brief_text, model="claude-opus-4-7")
                st.success("Brief generated and saved.")
                st.write(brief_text)

        if not os.environ.get("ANTHROPIC_API_KEY"):
            st.caption("Set `ANTHROPIC_API_KEY` to enable AI-generated communication briefs.")

    with tab_history:
        st.subheader("Tone Time Series")
        if history_df.empty:
            st.info("No history available.")
        else:
            chart_df = history_df.set_index("published_at")[["net_score"]]
            st.line_chart(chart_df)
            st.dataframe(
                history_df.rename(
                    columns={
                        "published_at": "Published",
                        "document_type": "Type",
                        "net_score": "Net Score",
                        "tone_label": "Tone",
                        "policy_bias": "Policy Bias",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

    with tab_feed:
        st.subheader("Recent RBI Communications")
        for row in communications.list_recent(limit=12):
            with st.container(border=True):
                left, right = st.columns([3, 1])
                with left:
                    st.markdown(f"**{row['title']}**")
                    st.caption(f"{row['document_type']} · {row['published_at']} · {row.get('speaker') or 'Unknown'}")
                    st.write(row.get("summary") or "No summary available.")
                with right:
                    st.metric("Tone", row["tone_label"].title(), row["policy_bias"].title())
