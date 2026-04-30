import streamlit as st
from datetime import datetime, timedelta
import zoneinfo
from engine.release_calendar import (
    RELEASE_SCHEDULE, days_until, get_upcoming_releases,
    has_been_released, to_ics,
)


def render_release_calendar():
    st.subheader("Data Release Calendar")

    ist_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    today = datetime.now(ist_tz).date()

    # Filter out releases that have already landed in the data (auto-derived).
    upcoming_all = get_upcoming_releases(as_of=today, days_ahead=120)
    upcoming = [r for r in upcoming_all if not has_been_released(r)]
    # Late releases: anything within the last 14 days that hasn't shown up
    # in the data yet. Sliding window so a release expected March 31 still
    # shows up as "5d late" on April 5 (the calendar-month-bound version
    # would have made it disappear).
    late_cutoff = today - timedelta(days=14)
    past_due = [
        r for r in RELEASE_SCHEDULE
        if late_cutoff <= r.expected_date < today
        and not has_been_released(r)
    ]
    visible = past_due + upcoming

    if not visible:
        st.info("No releases scheduled in the next 90 days.")
        return

    cols = st.columns(min(len(visible), 4))
    for i, release in enumerate(visible[:4]):
        d = days_until(release, as_of=today)
        with cols[i % 4]:
            if d < 0:
                color, bg_color = "#9E9E9E", "#F5F5F5"
                day_label = f"{abs(d)}d late"
            elif d <= 7:
                color, bg_color = "#D32F2F", "#FFEBEE"
                day_label = f"{d}d"
            elif d <= 21:
                color, bg_color = "#F9A825", "#FFF9C4"
                day_label = f"{d}d"
            else:
                color, bg_color = "#388E3C", "#E8F5E9"
                day_label = f"{d}d"
            st.markdown(f"""
<div style='background:{bg_color};border:1px solid {color}44;border-radius:12px;padding:16px;text-align:center;box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);'>
    <div style='font-size:10px;color:{color};font-weight:bold;letter-spacing:0.5px;text-transform:uppercase'>{release.indicator}</div>
    <div style='font-size:14px;font-weight:700;color:#333;margin:4px 0'>{release.reference_period}</div>
    <div style='font-size:28px;font-weight:800;color:{color};line-height:1'>{day_label}</div>
    <div style='font-size:11px;color:#666;margin-top:4px'>{release.expected_date.strftime("%b %d")}</div>
</div>
""", unsafe_allow_html=True)

    cap_col, dl_col = st.columns([3, 1])
    cap_col.caption(
        f"As of {today.strftime('%B %d, %Y')} · MOSPI scheduled dates · "
        f"'released' status auto-derived from data"
    )
    with dl_col:
        st.download_button(
            "📅 Add to Calendar",
            data=to_ics(),
            file_name="india-mospi-releases.ics",
            mime="text/calendar",
            help="Download all upcoming MOSPI release dates as an .ics calendar file.",
        )
