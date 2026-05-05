"""
Theme-drift detection — which macro topics are *new* in this MPC vs the prior?

Tracks 13 watchlist phrases that India rates analysts care about (food
inflation, transmission lags, monsoon, supply shocks, durable alignment, etc.).
For each pair of consecutive MPCs, flags any term that appears in the current
text but didn't appear in the prior text. The reverse direction (terms that
DROPPED) is also tracked — sometimes the most informative signal is what RBI
stopped talking about.

Ported from joshijeet02/rbi-comms-intel and integrated with the diff view.
"""
from __future__ import annotations

FOCUS_TERMS: tuple[str, ...] = (
    "food inflation",
    "transmission lags",
    "global volatility",
    "financial conditions",
    "liquidity conditions",
    "core inflation",
    "rural demand",
    "credit growth",
    "monsoon",
    "supply shocks",
    "exchange rate",
    "durable alignment",
    "uncertainty",
)


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def detect_new_focus_terms(curr_text: str, prev_text: str | None) -> dict:
    """
    Compare the current and prior MPC documents for theme drift.

    Returns:
      {
        "new":     [terms that appeared in curr but not in prev],
        "dropped": [terms that appeared in prev but not in curr],
        "shared":  [terms that appear in both],
      }

    If `prev_text` is None or empty, all curr-only terms are reported as "new"
    (first-meeting baseline).
    """
    curr = _normalize(curr_text or "")
    prev = _normalize(prev_text or "") if prev_text else ""

    new: list[str] = []
    dropped: list[str] = []
    shared: list[str] = []

    for term in FOCUS_TERMS:
        in_curr = term in curr
        in_prev = term in prev if prev else False
        if in_curr and not in_prev:
            new.append(term)
        elif in_prev and not in_curr:
            dropped.append(term)
        elif in_curr and in_prev:
            shared.append(term)

    return {"new": new, "dropped": dropped, "shared": shared}
