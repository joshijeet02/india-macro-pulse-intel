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
