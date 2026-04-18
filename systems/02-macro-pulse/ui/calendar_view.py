import streamlit as st
from datetime import date
from engine.release_calendar import get_upcoming_releases, days_until


def render_release_calendar():
    st.subheader("Data Release Calendar")

    today = date.today()
    upcoming = get_upcoming_releases(as_of=today, days_ahead=90)

    if not upcoming:
        st.info("No releases scheduled in the next 90 days.")
        return

    cols = st.columns(min(len(upcoming), 4))
    for i, release in enumerate(upcoming[:4]):
        d = days_until(release, as_of=today)
        with cols[i % 4]:
            color = "#FF6B6B" if d <= 7 else "#FFD93D" if d <= 21 else "#6BCB77"
            st.markdown(f"""
<div style='background:{color}22;border:1px solid {color};border-radius:8px;padding:12px;text-align:center'>
    <div style='font-size:11px;color:{color};font-weight:bold'>{release.indicator}</div>
    <div style='font-size:13px;font-weight:600'>{release.reference_period}</div>
    <div style='font-size:22px;font-weight:bold;color:{color}'>{d}d</div>
    <div style='font-size:10px;color:#888'>{release.expected_date.strftime("%b %d")}</div>
</div>
""", unsafe_allow_html=True)

    st.caption(f"As of {today.strftime('%B %d, %Y')} · Dates are MOSPI scheduled release dates")
