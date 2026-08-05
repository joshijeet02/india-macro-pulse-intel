import pytest

from engine.cpi_decomposer import decompose_cpi
from ui.cpi_view import contribution_rows


def test_2012_base_charts_all_three_components():
    rows = contribution_rows(decompose_cpi(5.0, 6.0, 3.0, reference_month="2025-12"))
    assert [name for name, _ in rows] == ["Food", "Fuel", "Core"]


def test_2024_base_charts_food_and_core_only():
    """
    Regression guard: the old all-or-nothing gate hid this chart entirely for
    every 2026 release, because fuel_contrib is legitimately None there.
    """
    rows = contribution_rows(decompose_cpi(4.38, 5.32, None, reference_month="2026-05"))
    assert [name for name, _ in rows] == ["Food", "Core (ex-food)"]
    assert len(rows) >= 2          # so the chart actually renders
    assert rows[0][1] == pytest.approx(1.96, abs=0.01)
    assert rows[1][1] == pytest.approx(2.42, abs=0.01)


def test_core_label_states_what_core_excludes():
    ex_food = contribution_rows(decompose_cpi(4.38, 5.32, None, reference_month="2026-05"))
    ex_both = contribution_rows(decompose_cpi(5.0, 6.0, 3.0, reference_month="2025-12"))
    assert ex_food[-1][0] == "Core (ex-food)"
    assert ex_both[-1][0] == "Core"


def test_all_components_missing_yields_no_rows():
    assert contribution_rows(
        {"food_contrib": None, "fuel_contrib": None, "core_contrib": None}
    ) == []


def test_empty_decomposition_is_handled():
    assert contribution_rows({}) == []


def test_weight_caption_states_2024_weights_for_2026_release():
    """
    Regression guard: the caption previously hardcoded "Food 45.86%" for every
    release, telling the reader the wrong number for 2026 data while the
    engine correctly used 36.753%.
    """
    from ui.cpi_view import weight_caption
    caption = weight_caption(decompose_cpi(4.38, 5.32, None, reference_month="2026-05"))
    assert "36.75%" in caption
    assert "45.86%" not in caption
    assert "base 2024=100" in caption


def test_weight_caption_states_2012_weights_for_pre_2026_release():
    from ui.cpi_view import weight_caption
    caption = weight_caption(decompose_cpi(5.0, 6.0, 3.0, reference_month="2025-12"))
    assert "45.86%" in caption
    assert "6.84%" in caption
    assert "base 2012=100" in caption


def test_weight_caption_defaults_to_2012_when_base_absent():
    from ui.cpi_view import weight_caption
    assert "base 2012=100" in weight_caption({})


def test_base_year_survives_database_round_trip(tmp_path, monkeypatch):
    """
    Regression guard: decompose_cpi returns base_year, but CPIStore does not
    persist it. Reading a stored 2026 release back therefore fell through to
    the 2012 branch and displayed "Food 45.86%" beside contributions computed
    on 36.753%. The base era must be recoverable from reference_month alone.
    """
    import db.schema, db.store
    from ui.cpi_view import base_year_of, weight_caption

    db_path = tmp_path / "roundtrip.db"
    monkeypatch.setattr(db.schema, "DB_PATH", db_path)
    monkeypatch.setattr(db.store, "DB_PATH", db_path)
    db.schema.init_db()

    dec = decompose_cpi(4.38, 5.32, None, reference_month="2026-05")
    store = db.store.CPIStore()
    store.upsert({
        "release_date": "2026-07-13",
        "reference_month": "2026-05",
        "headline_yoy": 4.38,
        "food_yoy": 5.32,
        "fuel_yoy": None,
        "core_yoy": dec["core_yoy"],
        "food_contrib": dec["food_contrib"],
        "fuel_contrib": dec["fuel_contrib"],
        "core_contrib": dec["core_contrib"],
        "consensus_forecast": None,
    })
    row = store.get_history(months=12)[-1]

    assert "base_year" not in row          # confirms the field really is not persisted
    assert base_year_of(row) == "2024"     # ...yet the base era is still recovered
    assert "36.75%" in weight_caption(row)
    assert "45.86%" not in weight_caption(row)


def test_core_definition_recovered_for_stored_row():
    from ui.cpi_view import core_definition_of
    stored = {"reference_month": "2026-05", "fuel_contrib": None}
    assert core_definition_of(stored) == "ex-food"
    stored_2012 = {"reference_month": "2025-12", "fuel_contrib": 0.21}
    assert core_definition_of(stored_2012) == "ex-food-and-fuel"


def test_base_year_of_degrades_on_any_malformed_month():
    """A display helper must never crash the page over a malformed field."""
    from ui.cpi_view import base_year_of
    for bad in ({}, {"reference_month": None}, {"reference_month": ""},
                {"reference_month": "garbage"}, {"reference_month": "2026"},
                {"reference_month": "2026-13"}, {"reference_month": 202605}):
        assert base_year_of(bad) == "2012"


def test_provenance_labels_are_unambiguous():
    """
    The CPI figures are ingested from MOSPI, not estimated. If a viewer reads
    them as our forecast they conclude we predict inflation exactly — a claim
    nobody can defend. These labels must say so in plain words.
    """
    from ui._provenance import OFFICIAL_INGESTED, INDEPENDENT_ESTIMATE
    assert "ingested, not estimated" in OFFICIAL_INGESTED
    assert "not a forecast" in OFFICIAL_INGESTED
    assert "not an official figure" in INDEPENDENT_ESTIMATE
    assert "has not been measured" in INDEPENDENT_ESTIMATE
    # The two must not be interchangeable.
    assert OFFICIAL_INGESTED != INDEPENDENT_ESTIMATE


def test_alpha_signal_does_not_reference_the_deleted_scrape_job(tmp_path, monkeypatch):
    """The weekly Amazon workflow was deleted in 5c4139d (April 2026)."""
    import db.schema, db.store
    from engine.assessments import _cpi_alpha_signal

    monkeypatch.setattr("db.schema.DB_PATH", tmp_path / "alpha.db")
    monkeypatch.setattr("db.store.DB_PATH", tmp_path / "alpha.db")
    db.schema.init_db()

    text, _plain, _tone = _cpi_alpha_signal()   # empty DB -> the no-history branch
    assert "wait for the weekly Amazon scrape job" not in text
    assert "removed in April 2026" in text
