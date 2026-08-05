"""
The always-on CPI estimate.

This renders above everything else because it answers the question a visitor
actually arrives with: what is inflation right now? Official CPI is published
once a month with a ~12-day lag, so for most of any given month the published
number is stale. This panel is what fills that gap.

Every number shown is accompanied by the error it actually made out-of-sample.
An estimate without a measured band invites the reader to assume it is exact,
which is the failure mode this whole panel exists to avoid.
"""
import pandas as pd
import streamlit as st

from db.store import CPIStore
from engine.nowcast import nowcast_headline

_MONTH_NAMES = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}


def pretty_month(reference_month: str) -> str:
    """'2026-07' -> 'July 2026'."""
    try:
        year, month = reference_month.split("-")
        return f"{_MONTH_NAMES[month]} {year}"
    except (ValueError, KeyError):
        return reference_month


def _render_reconciliation(nowcast, latest):
    """
    State the relationship between this number and the one at the top of the
    page, before showing this number at all.

    Two estimates of the same month, both large and blue, with nothing said
    about why they differ, reads as a system that cannot decide what it thinks.
    The panel above is a price calculation; this is an extrapolation of the
    published series. They are different instruments and they are allowed to
    disagree — but the disagreement has to be named and sized, and the page has
    to say which number it stands behind.
    """
    headline = st.session_state.get("headline_estimate") or {}
    same_month = headline.get("month") == nowcast.reference_month
    measured = headline.get("value")

    if not same_month or measured is None:
        st.info(
            f"**Model extrapolation of the published series: "
            f"{nowcast.point}% for {pretty_month(nowcast.reference_month)}.** This is "
            f"a cross-check on the price-based estimate at the top of the page, not "
            f"the headline. It reads no prices; it extends the official history."
        )
        return

    gap = nowcast.point - measured
    st.info(
        f"**Two numbers, two methods — {pretty_month(nowcast.reference_month)}.**\n\n"
        f"- **{measured}% — the page headline.** Arithmetic on prices: measured "
        f"month-on-month moves where we have them, official CPI weights, the "
        f"already-published base month. It reads no history beyond that base.\n"
        f"- **{nowcast.point}% — this panel.** An extrapolation of the published "
        f"series. It reads no prices at all.\n\n"
        f"They differ by **{abs(gap):.2f}pp**, with the model "
        f"{'higher' if gap > 0 else 'lower'}. That gap is information: the model is "
        f"picking up momentum in the official series that current prices have not "
        f"confirmed"
        + (", and it is currently carrying a regime-shift adjustment on top (below)"
           if nowcast.shock is not None and nowcast.shock.is_active else "")
        + f". **The page stands behind {measured}%**, because it is computed from "
        f"observed prices rather than fitted to past prints. Treat {nowcast.point}% "
        f"as the upside case, not as a second forecast."
    )


def render_nowcast_header():
    history = CPIStore().get_history(months=240)
    if not history:
        return

    nowcast = nowcast_headline(history)
    latest = history[-1]

    if nowcast is None:
        st.info(
            f"**Latest published CPI — {pretty_month(latest['reference_month'])}: "
            f"{latest['headline_yoy']}%.** Not enough history yet to publish an "
            "estimate for the next print with a measured error band."
        )
        return

    _render_reconciliation(nowcast, latest)

    verdict = (
        "beats the naive benchmark"
        if nowcast.beats_benchmark
        else "does NOT beat the naive benchmark"
    )
    st.markdown(
        f"Method `{nowcast.model}`, chosen by walk-forward test on "
        f"{nowcast.n_observations} months — it {verdict} of assuming next month "
        f"repeats this month. Its band, {nowcast.low}%–{nowcast.high}%, is the error "
        f"it actually made on data it had not seen. Last published: "
        f"{pretty_month(latest['reference_month'])} at {latest['headline_yoy']}%."
    )

    if not nowcast.beats_benchmark:
        st.warning(
            "No model currently beats 'next month equals this month'. The estimate "
            "shown is the best available, but on this record it carries no edge over "
            "that assumption — treat it accordingly."
        )

    shock = nowcast.shock
    if shock is not None and shock.is_active:
        st.error(
            f"**Regime shift detected — estimate adjusted by "
            f"{-shock.bias:+.2f}pp** (raw model output was {nowcast.raw_point}%).\n\n"
            f"Over the last {shock.months} months, **{shock.agreement:.0%} of "
            f"{shock.models_scored} model-runs missed in the same direction** "
            f"({shock.direction} by {abs(shock.bias):.2f}pp on average). Models built "
            f"on momentum, mean reversion, seasonality and base effects fail in "
            f"*different* directions when they are merely imprecise. When they all "
            f"miss the same way, the cause is not in the models — it is a force none "
            f"of them observes, such as an energy or supply shock feeding through "
            f"fuel, freight and imported food costs.\n\n"
            f"The correction is the measured bias, not a fitted parameter. It "
            f"disappears on its own once the models stop agreeing."
        )

    with st.expander("How accurate is this? — full model scoreboard"):
        st.markdown(
            "Every model scored **out-of-sample**: fit on months up to *t*, predict "
            "*t+1*, step forward, never seeing the month being predicted. `RMSE` is "
            "the typical miss in percentage points; `hit rate` is how often the "
            "direction of change was called correctly. `random_walk` is the benchmark "
            "to beat."
        )
        st.dataframe(
            pd.DataFrame([
                {
                    "Model": s.name,
                    "RMSE (pp)": s.rmse,
                    "MAE (pp)": s.mae,
                    "Hit rate": f"{s.hit_rate:.0%}",
                    "Months scored": s.n,
                    "Selected": "✓" if s.name == nowcast.model else "",
                }
                for s in nowcast.scores
            ]),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            f"Scored on {nowcast.n_observations} months of published CPI. A short "
            "record is a real limitation: selecting the best of several models on a "
            "small sample can flatter the winner, and the band will widen or narrow "
            "as more prints accumulate."
        )
