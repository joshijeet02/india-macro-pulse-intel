"""The 'Data as of' line, the staleness warning, and the anchor sync behind them."""
import json
from datetime import date

from ui.freshness import STALE_AFTER_DAYS, freshness

CPI_SEP = {"reference_month": "2026-09", "release_date": "2026-10-12"}
IIP_AUG = {"reference_month": "2026-08", "release_date": "2026-09-28"}


def test_line_names_the_newest_release_date_and_both_series():
    info = freshness(CPI_SEP, IIP_AUG, date(2026, 10, 23))
    assert info["line"] == (
        "Data as of 12 October 2026: latest official CPI for September 2026 "
        "and IIP for August 2026."
    )
    assert not info["stale"]
    assert info["age_days"] == 11


def test_warns_once_cpi_is_more_than_45_days_old():
    # The state the deployed app was actually in: June CPI, published 13 July.
    cpi_jun = {"reference_month": "2026-06", "release_date": "2026-07-13"}
    assert freshness(cpi_jun, IIP_AUG, date(2026, 10, 23))["stale"]
    # Boundary: exactly 45 days is fine, 46 is not.
    published = date(2026, 10, 12)
    assert not freshness(CPI_SEP, None, date.fromordinal(published.toordinal() + STALE_AFTER_DAYS))["stale"]
    assert freshness(CPI_SEP, None, date.fromordinal(published.toordinal() + STALE_AFTER_DAYS + 1))["stale"]


def test_no_data_is_stale_not_silent():
    info = freshness(None, None, date(2026, 10, 23))
    assert info["stale"]


def test_no_em_dashes_in_visitor_text():
    info = freshness(CPI_SEP, IIP_AUG, date(2026, 10, 23))
    assert "—" not in info["line"]


def test_refresh_anchor_follows_the_division_file(tmp_path, monkeypatch):
    """A running process must pick up a new anchor without a module reload."""
    import engine.live_index as live_index
    from engine.data_sync import refresh_anchor

    payload = json.loads(live_index.DIVISION_HISTORY_PATH.read_text())
    newest = max(payload["months"])
    entry = dict(payload["months"][newest])
    payload["months"]["2099-01"] = entry
    path = tmp_path / "division_indices.json"
    path.write_text(json.dumps(payload))

    original = (live_index.ANCHOR_MONTH, live_index.ANCHOR_DIVISION_INDICES,
                live_index.ANCHOR_HEADLINE_INDEX)
    monkeypatch.setattr(live_index, "DIVISION_HISTORY_PATH", path)
    try:
        assert refresh_anchor() == "2099-01"
        assert live_index.compute_live_index({}).anchor_month == "2099-01"
    finally:
        (live_index.ANCHOR_MONTH, live_index.ANCHOR_DIVISION_INDICES,
         live_index.ANCHOR_HEADLINE_INDEX) = original


def test_division_backfill_skips_months_older_than_the_newest(tmp_path, monkeypatch):
    """May 2026 is deliberately absent; retrying it daily would open an issue a day."""
    import scripts.refresh_releases as rr

    path = tmp_path / "division_indices.json"
    path.write_text(json.dumps({"months": {"2026-06": {}}}))
    monkeypatch.setattr(rr, "DIVISIONS_PATH", path)
    updates = {"cpi": [{"reference_month": "2026-05", "source": "http://x/may.pdf"}]}
    assert rr.refresh_divisions(updates) == (False, None)
