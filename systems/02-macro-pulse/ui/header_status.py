"""
What the header chip says — currently the next scheduled release.

Why this is its own module rather than a function in calendar_view:

Streamlit Cloud picks up a push by pulling the repo and re-running the main
script, but modules already in `sys.modules` are not necessarily re-imported.
A new *file* is therefore always safe, while a new *symbol added to an existing
file* is not: `app.py` runs from the new source and asks the old module object
for a name it does not have, and the whole app dies on

    ImportError: cannot import name 'next_release_summary' from 'ui.calendar_view'

which is exactly what happened when this function first shipped inside
calendar_view. The traceback had no frames inside calendar_view at all — the
module imported fine, it simply predated the function.

So anything app.py imports at module scope gets its own file. This one depends
only on names that already existed in engine.release_calendar, so a stale copy
of that module still satisfies it.

It is also the better split on the merits: this answers "what is the one line
for the header", which is a different question from "draw the calendar".
"""
from __future__ import annotations

import zoneinfo
from datetime import datetime

from engine.release_calendar import days_until, get_upcoming_releases, has_been_released


def next_release_summary() -> str | None:
    """
    One line describing the next release, for the page header.

    Returns None when nothing is scheduled, so the header omits the chip
    rather than printing an empty box.
    """
    today = datetime.now(zoneinfo.ZoneInfo("Asia/Kolkata")).date()
    upcoming = [
        r for r in get_upcoming_releases(as_of=today, days_ahead=120)
        if not has_been_released(r)
    ]
    if not upcoming:
        return None

    release = upcoming[0]
    days = days_until(release, as_of=today)
    when = "today" if days == 0 else ("tomorrow" if days == 1 else f"in {days} days")
    return (
        f"{release.indicator} {release.reference_period}<br>"
        f"{release.expected_date:%b %d} · {when}"
    )
