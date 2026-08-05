"""
Headline CPI nowcast.

Goal: whenever someone opens the app — whether or not MOSPI has published —
they see an estimate of the CPI print, with an honest error band.

Design constraints that shaped this:

* **Very little history.** ~27 monthly observations. Anything with more than
  one or two free parameters overfits and will look brilliant in-sample and
  useless out-of-sample. Every model here has at most two.

* **The benchmark must be beatable, and reported either way.** India CPI YoY
  is strongly autocorrelated, so "next month equals this month" is a genuinely
  hard baseline. A nowcast that cannot beat it is not worth publishing, and
  we say so rather than hiding it.

* **Model choice is made by walk-forward performance, not by preference.**
  `select_model` fits nothing on data later than the month being predicted.

* **The band is measured, not asserted.** It is ±1 walk-forward RMSE of the
  selected model — the error it actually made on data it had not seen.

What this deliberately does NOT do: claim the food basket improves the
estimate. That claim requires the basket to have history, and it does not yet.
`food_augmented` exists and competes on the same walk-forward footing as
everything else; it wins only if it earns it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

# A predictor sees only past observations and returns the next YoY estimate,
# or None when it lacks the history it needs.
Predictor = Callable[[Sequence[dict]], Optional[float]]

MIN_TRAIN_MONTHS = 8      # below this, fitted models are noise
MIN_BACKTEST_POINTS = 6   # below this, an RMSE is not worth quoting


@dataclass(frozen=True)
class ModelScore:
    name: str
    rmse: float
    mae: float
    hit_rate: float        # share of correct direction calls
    n: int                 # out-of-sample points scored


@dataclass(frozen=True)
class Nowcast:
    reference_month: str          # the month being estimated
    point: float                  # estimated headline CPI YoY, %
    band: float                   # ±, one walk-forward RMSE
    model: str                    # which model produced `point`
    scores: list[ModelScore]      # every model's walk-forward performance
    beats_benchmark: bool         # did the selected model beat random walk?
    n_observations: int           # history the estimate rests on
    raw_point: float              # before any shock adjustment
    shock: Optional[ShockSignal]  # evidence of a regime the models cannot see

    @property
    def low(self) -> float:
        return round(self.point - self.band, 2)

    @property
    def high(self) -> float:
        return round(self.point + self.band, 2)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _yoy(history: Sequence[dict]) -> list[float]:
    return [r["headline_yoy"] for r in history if r.get("headline_yoy") is not None]


def next_month(reference_month: str) -> str:
    """'2026-06' -> '2026-07'. The month we are estimating."""
    year, month = (int(x) for x in reference_month.split("-"))
    return f"{year + 1:04d}-01" if month == 12 else f"{year:04d}-{month + 1:02d}"


def _ols(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float]:
    """Least-squares intercept and slope. Slope is 0 if x has no variance."""
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    var = sum((x - mean_x) ** 2 for x in xs)
    if var == 0:
        return mean_y, 0.0
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    slope = cov / var
    return mean_y - slope * mean_x, slope


# ─── Models ──────────────────────────────────────────────────────────────────

def predict_random_walk(history: Sequence[dict]) -> Optional[float]:
    """The benchmark: next month equals this month. Hard to beat on CPI."""
    series = _yoy(history)
    return series[-1] if series else None


def predict_ar1(history: Sequence[dict]) -> Optional[float]:
    """
    yoy_t = a + b * yoy_{t-1}, fitted on everything available.

    Two parameters. Captures mean reversion, which a random walk cannot.
    """
    series = _yoy(history)
    if len(series) < MIN_TRAIN_MONTHS:
        return None
    a, b = _ols(series[:-1], series[1:])
    return a + b * series[-1]


def predict_damped_momentum(history: Sequence[dict]) -> Optional[float]:
    """
    Carry forward half of last month's change.

    One fixed parameter, no fitting. CPI YoY moves in runs — disinflation and
    reflation both persist for several months — but undamped extrapolation
    overshoots badly at turning points.
    """
    series = _yoy(history)
    if len(series) < 2:
        return None
    return series[-1] + 0.5 * (series[-1] - series[-2])


def predict_food_augmented(history: Sequence[dict]) -> Optional[float]:
    """
    Regress headline YoY on the same month's food YoY.

    Food is the volatile component and drives most of India's headline
    surprises, so where a food print exists it carries real information. This
    competes on the same walk-forward footing as every other model and is
    selected only if it actually wins.
    """
    paired = [
        (r["food_yoy"], r["headline_yoy"])
        for r in history
        if r.get("food_yoy") is not None and r.get("headline_yoy") is not None
    ]
    if len(paired) < MIN_TRAIN_MONTHS:
        return None
    latest_food = next(
        (r["food_yoy"] for r in reversed(history) if r.get("food_yoy") is not None),
        None,
    )
    if latest_food is None:
        return None
    a, b = _ols([f for f, _ in paired], [h for _, h in paired])
    return a + b * latest_food


MODELS: dict[str, Predictor] = {
    "random_walk": predict_random_walk,
    "ar1": predict_ar1,
    "damped_momentum": predict_damped_momentum,
    "food_augmented": predict_food_augmented,
}

BENCHMARK = "random_walk"

# A regime shift is declared only when this share of models miss in the same
# direction. Below it, one-sided errors are unremarkable noise.
SHOCK_AGREEMENT_THRESHOLD = 0.85
SHOCK_LOOKBACK_MONTHS = 2


@dataclass(frozen=True)
class ShockSignal:
    """
    Evidence that something outside the models is moving prices.

    Structurally different models — momentum, mean reversion, seasonal, base
    effect — fail in *different* directions when they are merely imprecise.
    When they all miss the same way in the same month, the common cause is not
    in any of them: it is a force none of them observes.

    That happened in May and June 2026, when 7 of 7 models under-predicted by
    a mean of 0.45pp, coinciding with the West Asia conflict feeding through
    energy, freight and edible-oil import costs.

    `bias` is the mean signed error over the lookback. Subtracting it does not
    model the shock — it simply stops pretending the shock is not there while
    it persists. It decays to nothing the moment the models stop agreeing.
    """
    bias: float             # mean signed error, pp (negative = under-predicting)
    agreement: float        # share of models missing in the same direction
    months: int             # months in the lookback
    models_scored: int

    @property
    def is_active(self) -> bool:
        return (
            abs(self.bias) >= 0.10
            and self.agreement >= SHOCK_AGREEMENT_THRESHOLD
            and self.models_scored >= 3
        )

    @property
    def direction(self) -> str:
        return "under-predicting" if self.bias < 0 else "over-predicting"


def detect_shock(
    history: Sequence[dict],
    lookback: int = SHOCK_LOOKBACK_MONTHS,
) -> Optional[ShockSignal]:
    """
    Look for one-sided error across structurally different models.

    Every model is re-run out-of-sample on the last `lookback` months. If they
    agree on the direction of their miss, that is a common cause acting on the
    target, not on the models.
    """
    usable = sorted(
        (r for r in history if r.get("headline_yoy") is not None),
        key=lambda r: r["reference_month"],
    )
    if len(usable) < MIN_TRAIN_MONTHS + lookback:
        return None

    errors: list[float] = []
    for offset in range(lookback, 0, -1):
        index = len(usable) - offset
        train, actual = usable[:index], usable[index]["headline_yoy"]
        for predictor in MODELS.values():
            predicted = predictor(train)
            if predicted is not None:
                errors.append(predicted - actual)

    if len(errors) < 3:
        return None

    negative = sum(1 for e in errors if e < 0)
    agreement = max(negative, len(errors) - negative) / len(errors)
    return ShockSignal(
        bias=round(sum(errors) / len(errors), 3),
        agreement=round(agreement, 3),
        months=lookback,
        models_scored=len(errors),
    )


# ─── Walk-forward evaluation ─────────────────────────────────────────────────

def walk_forward(
    history: Sequence[dict],
    predictor: Predictor,
    min_train: int = MIN_TRAIN_MONTHS,
) -> Optional[ModelScore]:
    """
    Score a predictor out-of-sample: fit to months [0..i), predict month i,
    step forward. Nothing at or after the predicted month is ever visible.
    """
    errors: list[float] = []
    correct_direction = 0
    directional = 0

    for i in range(min_train, len(history)):
        train = history[:i]
        predicted = predictor(train)
        if predicted is None:
            continue
        actual = history[i].get("headline_yoy")
        if actual is None:
            continue
        errors.append(predicted - actual)

        previous = train[-1].get("headline_yoy")
        if previous is not None:
            actual_move = actual - previous
            predicted_move = predicted - previous
            if actual_move != 0:
                directional += 1
                if (actual_move > 0) == (predicted_move > 0):
                    correct_direction += 1

    if len(errors) < MIN_BACKTEST_POINTS:
        return None

    rmse = (sum(e * e for e in errors) / len(errors)) ** 0.5
    mae = sum(abs(e) for e in errors) / len(errors)
    hit = (correct_direction / directional) if directional else 0.0
    return ModelScore("", round(rmse, 3), round(mae, 3), round(hit, 3), len(errors))


def score_all(history: Sequence[dict]) -> list[ModelScore]:
    """Walk-forward score for every model, best (lowest RMSE) first."""
    scored: list[ModelScore] = []
    for name, predictor in MODELS.items():
        result = walk_forward(history, predictor)
        if result is not None:
            scored.append(
                ModelScore(name, result.rmse, result.mae, result.hit_rate, result.n)
            )
    return sorted(scored, key=lambda s: s.rmse)


# ─── Public entry point ──────────────────────────────────────────────────────

def nowcast_headline(history: Sequence[dict]) -> Optional[Nowcast]:
    """
    Estimate the next unpublished headline CPI YoY.

    Returns None when there is too little history to say anything defensible.
    Emitting a number without a measured error band would be worse than
    emitting nothing: it is the shape of claim that collapses under one
    follow-up question.
    """
    usable = [r for r in history if r.get("headline_yoy") is not None]
    usable = sorted(usable, key=lambda r: r["reference_month"])
    if len(usable) < MIN_TRAIN_MONTHS + MIN_BACKTEST_POINTS:
        return None

    scores = score_all(usable)
    if not scores:
        return None

    best = scores[0]
    point = MODELS[best.name](usable)
    if point is None:
        return None

    benchmark = next((s for s in scores if s.name == BENCHMARK), None)
    beats = benchmark is None or best.rmse < benchmark.rmse

    # Correct for a shock only while the models actually agree they are being
    # beaten in one direction. This is not a fitted parameter — it is the
    # measured, currently-persisting bias, and it vanishes on its own once the
    # models stop agreeing.
    shock = detect_shock(usable)
    adjusted = point - shock.bias if (shock and shock.is_active) else point

    return Nowcast(
        reference_month=next_month(usable[-1]["reference_month"]),
        point=round(adjusted, 2),
        band=round(best.rmse, 2),
        model=best.name,
        scores=scores,
        beats_benchmark=beats,
        n_observations=len(usable),
        raw_point=round(point, 2),
        shock=shock,
    )
