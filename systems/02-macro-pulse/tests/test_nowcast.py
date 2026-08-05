"""Tests for the headline CPI nowcast."""
import pytest

from engine.nowcast import (
    MIN_BACKTEST_POINTS, MIN_TRAIN_MONTHS, MODELS, _ols, next_month,
    nowcast_headline, predict_damped_momentum, predict_random_walk,
    score_all, walk_forward,
)


def _series(values, food=None):
    """Build history rows with sequential reference months from 2024-01."""
    rows = []
    for i, v in enumerate(values):
        y, m = 2024 + i // 12, i % 12 + 1
        row = {"reference_month": f"{y:04d}-{m:02d}", "headline_yoy": v}
        if food is not None:
            row["food_yoy"] = food[i]
        rows.append(row)
    return rows


# ── month arithmetic ────────────────────────────────────────────────────────

def test_next_month_increments():
    assert next_month("2026-06") == "2026-07"


def test_next_month_rolls_over_december():
    assert next_month("2026-12") == "2027-01"


# ── OLS ─────────────────────────────────────────────────────────────────────

def test_ols_recovers_a_known_line():
    a, b = _ols([1, 2, 3, 4], [3, 5, 7, 9])   # y = 1 + 2x
    assert a == pytest.approx(1.0, abs=1e-9)
    assert b == pytest.approx(2.0, abs=1e-9)


def test_ols_zero_variance_returns_mean_and_flat_slope():
    a, b = _ols([5, 5, 5], [2, 4, 6])
    assert a == pytest.approx(4.0)
    assert b == 0.0


# ── individual models ───────────────────────────────────────────────────────

def test_random_walk_returns_last_value():
    assert predict_random_walk(_series([1.0, 2.0, 3.5])) == 3.5


def test_damped_momentum_carries_half_the_last_move():
    # last move +1.0 -> 4.0 + 0.5
    assert predict_damped_momentum(_series([3.0, 4.0])) == pytest.approx(4.5)


def test_damped_momentum_needs_two_points():
    assert predict_damped_momentum(_series([3.0])) is None


def test_models_return_none_rather_than_guessing_on_thin_history():
    thin = _series([1.0, 2.0])
    for name, predictor in MODELS.items():
        if name in ("random_walk", "damped_momentum"):
            continue          # these legitimately work on 1-2 points
        assert predictor(thin) is None, f"{name} produced a number from 2 points"


# ── the critical property: no lookahead ─────────────────────────────────────

def test_walk_forward_never_sees_the_month_it_predicts():
    """
    A backtest that leaks future data reports a flattering RMSE and is worthless.
    This predictor asserts the value it is being scored on is absent from what
    it was handed.
    """
    values = [float(i) for i in range(20)]
    history = _series(values)
    seen: list[int] = []

    def spy(train):
        seen.append(len(train))
        # the row at index len(train) is the one about to be scored
        assert all(r["headline_yoy"] in values[:len(train)] for r in train)
        return train[-1]["headline_yoy"]

    walk_forward(history, spy, min_train=MIN_TRAIN_MONTHS)
    # training windows must grow strictly, starting at min_train
    assert seen == list(range(MIN_TRAIN_MONTHS, len(values)))


def test_walk_forward_is_none_below_the_minimum_scored_points():
    short = _series([float(i) for i in range(MIN_TRAIN_MONTHS + 2)])
    assert walk_forward(short, predict_random_walk) is None


def test_walk_forward_scores_a_perfect_predictor_at_zero_error():
    history = _series([float(i) for i in range(20)])
    # values increase by exactly 1, so damped momentum on a straight line
    # is not perfect, but a clairvoyant predictor is — build one explicitly
    def perfect(train):
        return float(len(train))
    score = walk_forward(history, perfect)
    assert score.rmse == 0.0
    assert score.mae == 0.0


# ── selection and the public entry point ────────────────────────────────────

def test_score_all_is_sorted_best_first():
    history = _series([2.0, 2.2, 2.1, 2.5, 2.9, 3.0, 3.2, 3.1, 3.4, 3.8,
                       4.0, 4.2, 4.1, 4.5, 4.9, 5.0, 5.2, 5.1, 5.4, 5.8])
    scores = score_all(history)
    assert len(scores) >= 2
    assert scores == sorted(scores, key=lambda s: s.rmse)


def test_nowcast_returns_none_on_insufficient_history():
    assert nowcast_headline(_series([1.0, 2.0, 3.0])) is None


def test_nowcast_targets_the_month_after_the_last_print():
    history = _series([float(i) * 0.1 + 2 for i in range(20)])
    nc = nowcast_headline(history)
    assert nc is not None
    assert nc.reference_month == next_month(history[-1]["reference_month"])


def test_nowcast_band_is_the_selected_models_walk_forward_rmse():
    history = _series([float(i) * 0.1 + 2 for i in range(20)])
    nc = nowcast_headline(history)
    selected = next(s for s in nc.scores if s.name == nc.model)
    assert nc.band == pytest.approx(round(selected.rmse, 2))
    assert nc.high - nc.low == pytest.approx(2 * nc.band, abs=0.01)


def test_nowcast_ignores_rows_with_no_headline():
    history = _series([float(i) * 0.1 + 2 for i in range(20)])
    history.append({"reference_month": "2025-09", "headline_yoy": None})
    nc = nowcast_headline(history)
    assert nc is not None
    assert nc.n_observations == 20


# ── UI-facing helpers ───────────────────────────────────────────────────────

def test_pretty_month_formats_for_a_reader():
    from ui.nowcast_view import pretty_month
    assert pretty_month("2026-07") == "July 2026"
    assert pretty_month("2026-01") == "January 2026"


def test_pretty_month_degrades_on_bad_input():
    """A header helper must never crash the whole page."""
    from ui.nowcast_view import pretty_month
    for bad in ("2026", "garbage", "2026-99", ""):
        assert isinstance(pretty_month(bad), str)
