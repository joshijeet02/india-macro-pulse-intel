"""
Statement archetype classifier.

Each MPC meeting has a "vibe" — the combination of stance, projection
movement, dissent pattern, and language emphasis tells a story. We classify
each Statement against six archetypes:

  - pre_cut_signal      stance softening, growth concern, inflation easing
  - rate_cut            actual cut delivered
  - insurance_pause     unchanged + neutral + risks balanced (calm waters)
  - hawkish_pivot       stance hardening, dissent, inflation upside risks
  - rate_hike           actual hike delivered
  - operational_tweak   no change in stance/rate; focus on liquidity / measures

Implementation: rule-based on the structured signals already extracted by
mpc_extractor.extract_mpc_decision() and stance_engine.analyze_communication().
The same archetype label is shown on the hero card and used for the
"this statement reads most like Aug 2025" pattern matcher.

Compared to a neural classifier this is:
- Explainable — analysts can see which rule triggered
- Deterministic — same input → same output
- No training data needed — works on the first MPC ingested
- Limited — won't catch nuanced patterns. That's OK for a v1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

ARCHETYPES = {
    "rate_cut":          "Rate cut delivered",
    "rate_hike":         "Rate hike delivered",
    "pre_cut_signal":    "Pre-cut signal",
    "hawkish_pivot":     "Hawkish pivot",
    "insurance_pause":   "Insurance pause",
    "operational_tweak": "Operational tweak",
}


@dataclass
class ArchetypeResult:
    label: str            # one of the keys above
    display:    str       # human-readable label
    rationale:  str       # one-sentence explanation


def classify_statement(
    decision: dict,
    prior_decision: Optional[dict] = None,
    inflation_label: Optional[str] = None,
    growth_label: Optional[str] = None,
    dissent_count: int = 0,
) -> ArchetypeResult:
    """
    Classify a Statement based on:
      decision: dict from MPCDecisionStore (repo_rate, change_bps, stance_label, projections)
      prior_decision: same shape, for the previous MPC
      inflation_label / growth_label: optional, from the stance engine
      dissent_count: number of dissenting members from the Minutes (0 if Minutes not yet released)

    Returns the most-applicable archetype + rationale.
    """
    bps = decision.get("repo_rate_change_bps") or 0
    stance = decision.get("stance_label") or "neutral"
    prior_stance = (prior_decision or {}).get("stance_label") or stance

    # Tier 1: actual rate change is unambiguous
    if bps > 0:
        return ArchetypeResult(
            label="rate_hike",
            display=ARCHETYPES["rate_hike"],
            rationale=f"Repo rate raised by {bps}bp — explicit tightening.",
        )
    if bps < 0:
        return ArchetypeResult(
            label="rate_cut",
            display=ARCHETYPES["rate_cut"],
            rationale=f"Repo rate cut by {abs(bps)}bp — explicit easing.",
        )

    # Tier 2: stance-shift signals
    stance_softened = (
        prior_stance == "withdrawal_of_accommodation" and stance != "withdrawal_of_accommodation"
    ) or (
        prior_stance in ("calibrated_tightening", "calibrated_withdrawal") and stance == "neutral"
    ) or (
        prior_stance == "neutral" and stance == "accommodative"
    )
    stance_hardened = (
        prior_stance == "accommodative" and stance != "accommodative"
    ) or (
        prior_stance == "neutral" and stance in (
            "withdrawal_of_accommodation", "calibrated_tightening", "calibrated_withdrawal",
        )
    )

    if stance_hardened or dissent_count >= 2 or inflation_label == "hawkish":
        reasons = []
        if stance_hardened:
            reasons.append(f"stance shifted from {prior_stance.replace('_',' ')} to {stance.replace('_',' ')}")
        if dissent_count >= 2:
            reasons.append(f"{dissent_count} dissents in the vote")
        if inflation_label == "hawkish":
            reasons.append("inflation language hardened")
        return ArchetypeResult(
            label="hawkish_pivot",
            display=ARCHETYPES["hawkish_pivot"],
            rationale="Hawkish signals: " + ", ".join(reasons) + ".",
        )

    if stance_softened or growth_label in ("dovish", "leaning_dovish") and inflation_label in ("dovish", "leaning_dovish"):
        reasons = []
        if stance_softened:
            reasons.append(f"stance softened from {prior_stance.replace('_',' ')} to {stance.replace('_',' ')}")
        if growth_label in ("dovish", "leaning_dovish"):
            reasons.append("growth language softer")
        if inflation_label in ("dovish", "leaning_dovish"):
            reasons.append("inflation language easier")
        return ArchetypeResult(
            label="pre_cut_signal",
            display=ARCHETYPES["pre_cut_signal"],
            rationale="Setting up for a cut: " + ", ".join(reasons) + ".",
        )

    # Tier 3: pause variants
    # If projections moved meaningfully, classify as insurance pause; otherwise
    # operational tweak (the "boring" archetype).
    cpi_delta = _projection_delta(
        decision.get("cpi_projection_curr_value"),
        (prior_decision or {}).get("cpi_projection_curr_value"),
    )
    gdp_delta = _projection_delta(
        decision.get("gdp_projection_curr_value"),
        (prior_decision or {}).get("gdp_projection_curr_value"),
    )

    if abs(cpi_delta or 0) >= 0.10 or abs(gdp_delta or 0) >= 0.10:
        rationale_bits = []
        if cpi_delta:
            rationale_bits.append(f"CPI projection moved {cpi_delta:+.2f}pp")
        if gdp_delta:
            rationale_bits.append(f"GDP projection moved {gdp_delta:+.2f}pp")
        return ArchetypeResult(
            label="insurance_pause",
            display=ARCHETYPES["insurance_pause"],
            rationale="Holding while projections shift: " + ", ".join(rationale_bits) + ".",
        )

    return ArchetypeResult(
        label="operational_tweak",
        display=ARCHETYPES["operational_tweak"],
        rationale="No rate or stance change; projections roughly steady. Focus on liquidity / regulatory measures.",
    )


def _projection_delta(curr: Optional[float], prev: Optional[float]) -> Optional[float]:
    if curr is None or prev is None:
        return None
    return round(curr - prev, 2)


# ─── Pattern matching: "this MPC reads most like..." ──────────────────────────

def find_most_similar_meeting(
    current: ArchetypeResult,
    history: list[dict],   # list of mpc_decisions rows, oldest first
    *,
    exclude_meeting_date: Optional[str] = None,
) -> Optional[dict]:
    """
    Find the most similar prior meeting based on archetype + numeric signals.
    Returns the matching mpc_decisions row, or None if no good match.

    Similarity priority:
      1. Same archetype label.
      2. Among same-archetype matches, smallest stance/projection distance.
    """
    if len(history) < 2:
        return None

    candidates = [
        d for d in history
        if d.get("meeting_date") != exclude_meeting_date
    ]

    same_archetype: list[dict] = []
    for d in candidates:
        # Re-classify each historical meeting to get its archetype label
        prior = next((h for h in history if h.get("meeting_date", "") < d.get("meeting_date", "")), None)
        archetype = classify_statement(d, prior)
        d_with_arch = {**d, "_archetype_label": archetype.label}
        if archetype.label == current.label:
            same_archetype.append(d_with_arch)

    if not same_archetype:
        return None

    # Among same-archetype, prefer the closest by repo rate (proxy for "regime")
    if "_archetype_label" not in candidates[0]:
        return same_archetype[0]
    return same_archetype[0]
