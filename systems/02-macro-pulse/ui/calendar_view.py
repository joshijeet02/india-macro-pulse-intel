import streamlit as st
from datetime import date, datetime
import zoneinfo
from engine.release_calendar import get_upcoming_releases, days_until


def render_release_calendar():
    st.subheader("Data Release Calendar")

    ist_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    today = datetime.now(ist_tz).date()
    upcoming = get_upcoming_releases(as_of=today, days_ahead=90)

    if not upcoming:
        st.info("No releases scheduled in the next 90 days.")
        return

    cols = st.columns(min(len(upcoming), 4))
    for i, release in enumerate(upcoming[:4]):
        d = days_until(release, as_of=today)
        with cols[i % 4]:
            color = "#D32F2F" if d <= 7 else "#F9A825" if d <= 21 else "#388E3C"
            bg_color = "#FFEBEE" if d <= 7 else "#FFF9C4" if d <= 21 else "#E8F5E9"
            st.markdown(f"""
<div style='background:{bg_color};border:1px solid {color}44;border-radius:12px;padding:16px;text-align:center;box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);'>
    <div style='font-size:10px;color:{color};font-weight:bold;letter-spacing:0.5px;text-transform:uppercase'>{release.indicator}</div>
    <div style='font-size:14px;font-weight:700;color:#333;margin:4px 0'>{release.reference_period}</div>
    <div style='font-size:28px;font-weight:800;color:{color};line-height:1'>{d}d</div>
    <div style='font-size:11px;color:#666;margin-top:4px'>{release.expected_date.strftime("%b %d")}</div>
</div>
""", unsafe_allow_html=True)

    st.caption(f"As of {today.strftime('%B %d, %Y')} · Dates are MOSPI scheduled release dates")
