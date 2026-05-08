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


@dataclass
class SimilarityMatch:
    """
    Result of historical pattern-matching. Always has a `confidence_label`;
    the `decision` field is None when no match clears the threshold floor —
    important because Sid's feedback specifically called out the previous
    behavior of "coercing a weak match into a confident-looking output".
    """
    decision:           Optional[dict]   # mpc_decisions row, None if no clear match
    score:              float            # 0.0 – 1.0
    confidence_label:   str              # 'strong' | 'moderate' | 'distant' | 'no_match'
    rationale:          str              # one-line "why this match"


# Confidence thresholds — keep in lockstep with the UI band copy.
# Tuned conservatively after observing real Apr 2026 → Aug 2020 false-positive
# in v1 (no scoring). The goal is to surface "no clear match" honestly when
# the corpus genuinely doesn't have a peer.
_THRESHOLD_STRONG    = 0.85
_THRESHOLD_MODERATE  = 0.70
_THRESHOLD_DISTANT   = 0.55  # PRD-mandated floor — below this, return None match


def _confidence_label_for(score: float) -> str:
    if score >= _THRESHOLD_STRONG:
        return "strong"
    if score >= _THRESHOLD_MODERATE:
        return "moderate"
    if score >= _THRESHOLD_DISTANT:
        return "distant"
    return "no_match"


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

# Stance label → numeric position on the dovish ↔ hawkish axis.
_STANCE_AXIS = {
    "accommodative":               -1.0,
    "calibrated_withdrawal":       +0.5,
    "calibrated_tightening":       +0.7,
    "withdrawal_of_accommodation": +1.0,
    "neutral":                      0.0,
}


def _direction(bps: int) -> int:
    """+1 hike, -1 cut, 0 hold."""
    if bps > 0:
        return 1
    if bps < 0:
        return -1
    return 0


def compute_similarity(curr: dict, hist: dict) -> float:
    """
    Feature-weighted similarity between two `mpc_decisions` rows.

    Returns a score in [0.0, 1.0] where 1.0 = identical signals across all
    features and 0.0 = maximally different. Weights tuned for what an India
    rates analyst actually cares about when matching a current MPC to history:

    - Stance label (35%)            — the headline policy posture
    - Repo rate level (25%)         — proxy for the rate-cycle regime
    - Direction of move (25%)       — cut / hold / hike (categorical)
    - CPI projection level (15%)    — the inflation regime

    Returns 0.5 (uncertain) when both decisions are too sparse to compare.
    """
    # ─── Stance distance ────────────────────────────────────────────────────
    curr_stance = _STANCE_AXIS.get(curr.get("stance_label") or "neutral", 0.0)
    hist_stance = _STANCE_AXIS.get(hist.get("stance_label") or "neutral", 0.0)
    stance_dist = abs(curr_stance - hist_stance) / 2.0  # max axis spread is 2.0

    # ─── Repo-rate-level distance ───────────────────────────────────────────
    curr_rate = curr.get("repo_rate")
    hist_rate = hist.get("repo_rate")
    if curr_rate is not None and hist_rate is not None:
        rate_dist = min(abs(curr_rate - hist_rate) / 4.0, 1.0)  # 4pp = "max different"
    else:
        rate_dist = 0.5  # uncertain

    # ─── Direction-of-move distance (categorical) ───────────────────────────
    curr_dir = _direction(curr.get("repo_rate_change_bps") or 0)
    hist_dir = _direction(hist.get("repo_rate_change_bps") or 0)
    direction_dist = 0.0 if curr_dir == hist_dir else 0.5 if abs(curr_dir - hist_dir) == 1 else 1.0

    # ─── CPI projection distance ────────────────────────────────────────────
    cc = curr.get("cpi_projection_curr_value")
    hc = hist.get("cpi_projection_curr_value")
    if cc is not None and hc is not None:
        cpi_dist = min(abs(cc - hc) / 3.0, 1.0)  # 3pp diff = max
    else:
        cpi_dist = 0.5

    # ─── Weighted aggregate ─────────────────────────────────────────────────
    weighted_dist = (
        0.35 * stance_dist
        + 0.25 * rate_dist
        + 0.25 * direction_dist
        + 0.15 * cpi_dist
    )
    return round(1.0 - weighted_dist, 3)


def _build_rationale(score: float, curr: dict, hist: dict) -> str:
    """Single-sentence explanation of why this is the closest match."""
    stance_curr = (curr.get("stance_label") or "neutral").replace("_", " ")
    stance_hist = (hist.get("stance_label") or "neutral").replace("_", " ")
    rate_curr = curr.get("repo_rate")
    rate_hist = hist.get("repo_rate")
    bits = []
    if stance_curr == stance_hist:
        bits.append(f"same stance ({stance_curr})")
    elif _STANCE_AXIS.get(curr.get("stance_label"), 0) * _STANCE_AXIS.get(hist.get("stance_label"), 0) > 0:
        bits.append("stance leans the same direction")
    else:
        bits.append(f"stance differs ({stance_hist} → {stance_curr})")

    if rate_curr is not None and rate_hist is not None:
        bits.append(f"rate {rate_hist:.2f}% vs {rate_curr:.2f}%")

    curr_dir = _direction(curr.get("repo_rate_change_bps") or 0)
    hist_dir = _direction(hist.get("repo_rate_change_bps") or 0)
    if curr_dir == hist_dir:
        word = {1: "hike", -1: "cut", 0: "hold"}[curr_dir]
        bits.append(f"both {word}")

    return " · ".join(bits)


def find_most_similar_meeting(
    current: ArchetypeResult | None,
    history: list[dict],
    *,
    current_decision: Optional[dict] = None,
    exclude_meeting_date: Optional[str] = None,
) -> SimilarityMatch:
    """
    Find the most similar prior MPC by feature-vector similarity, with
    confidence band. Returns a SimilarityMatch — when no candidate clears
    the 0.55 floor, decision=None and confidence_label='no_match'.

    `current` is the ArchetypeResult of the current meeting (kept for
    backwards compat — the matcher itself uses `current_decision`, which
    can be passed directly when the caller already has the row).
    """
    if not history or len(history) < 2:
        return SimilarityMatch(
            decision=None, score=0.0,
            confidence_label="no_match",
            rationale="Need at least 2 historical meetings to find a peer.",
        )

    # Identify the current decision row. Prefer explicit; fall back to the
    # most-recent history row that's NOT the excluded one.
    if current_decision is None:
        candidates_for_current = [
            d for d in history if d.get("meeting_date") == exclude_meeting_date
        ]
        if candidates_for_current:
            current_decision = candidates_for_current[0]
        else:
            current_decision = history[-1]  # default: latest

    # Score every historical decision (excluding the current one)
    scored: list[tuple[float, dict]] = []
    for d in history:
        if d.get("meeting_date") == exclude_meeting_date:
            continue
        if d.get("meeting_date") == current_decision.get("meeting_date"):
            continue
        score = compute_similarity(current_decision, d)
        scored.append((score, d))

    if not scored:
        return SimilarityMatch(
            decision=None, score=0.0,
            confidence_label="no_match",
            rationale="No comparable historical meetings.",
        )

    # Best match
    scored.sort(key=lambda t: t[0], reverse=True)
    best_score, best_decision = scored[0]
    label = _confidence_label_for(best_score)

    if label == "no_match":
        return SimilarityMatch(
            decision=None,
            score=best_score,
            confidence_label="no_match",
            rationale=(
                f"Top candidate scored only {best_score:.2f} (need ≥{_THRESHOLD_DISTANT}). "
                f"This MPC reads as a fresh combination of signals."
            ),
        )

    return SimilarityMatch(
        decision=best_decision,
        score=best_score,
        confidence_label=label,
        rationale=_build_rationale(best_score, current_decision, best_decision),
    )


# ─── F5: theme-level pattern matching ───────────────────────────────────────
#
# Sid asked specifically: "I like your innovation 'reads most like the xxx
# meeting'. You can apply that to the theme diffs." This is that.
# Per-theme similarity uses lexicon-tracked phrase overlap (the same
# _phrases_in() helper as the diff engine — no LLM, no embeddings, just
# the explicit signal vocabulary). Overlap-coefficient is preferred over
# Jaccard because Statements vary widely in length and we want to reward
# partial overlap rather than punish length asymmetry.

def _phrase_overlap_coefficient(a: set[str], b: set[str]) -> float:
    """|A ∩ B| / min(|A|, |B|). Returns 0.0 if either set empty."""
    if not a or not b:
        return 0.0
    return round(len(a & b) / min(len(a), len(b)), 3)


def find_similar_theme(
    curr_text: str,
    historical_theme_texts: dict[str, str],
    *,
    min_phrases: int = 3,
) -> SimilarityMatch:
    """
    Find the historical Statement whose same-theme text most resembles the
    current theme's text, by lexicon-phrase overlap coefficient.

    `historical_theme_texts`: {meeting_date: theme_text_for_that_meeting}

    Returns a SimilarityMatch where decision contains {"meeting_date": <key>}
    and `score` is the overlap coefficient. Below the 0.40 floor (looser than
    the document-level 0.55 because phrase counts per theme are small),
    returns a no_match. The same confidence-label vocabulary applies, but
    rebanded for theme scope.
    """
    # Lazy import to avoid module-init circulars
    from engine.diff_engine import _phrases_in

    curr_phrases = _phrases_in(curr_text)
    if len(curr_phrases) < min_phrases:
        return SimilarityMatch(
            decision=None, score=0.0,
            confidence_label="no_match",
            rationale=f"Theme has only {len(curr_phrases)} tracked phrases — too sparse to match.",
        )

    scored: list[tuple[float, str, set[str]]] = []
    for date, hist_text in historical_theme_texts.items():
        hist_phrases = _phrases_in(hist_text)
        if not hist_phrases:
            continue
        score = _phrase_overlap_coefficient(curr_phrases, hist_phrases)
        scored.append((score, date, curr_phrases & hist_phrases))

    if not scored:
        return SimilarityMatch(
            decision=None, score=0.0,
            confidence_label="no_match",
            rationale="No historical theme had any tracked phrases.",
        )

    scored.sort(key=lambda t: t[0], reverse=True)
    best_score, best_date, shared_phrases = scored[0]

    # Theme-level rebanding — Statements are short enough that 0.85 is rare.
    if best_score >= 0.75:
        label = "strong"
    elif best_score >= 0.55:
        label = "moderate"
    elif best_score >= 0.40:
        label = "distant"
    else:
        label = "no_match"

    if label == "no_match":
        return SimilarityMatch(
            decision=None, score=best_score,
            confidence_label="no_match",
            rationale=(
                f"Top theme candidate scored only {best_score:.2f} — "
                f"this section reads as a fresh combination of language."
            ),
        )

    shared_preview = ", ".join(f"'{p}'" for p in sorted(shared_phrases)[:3])
    return SimilarityMatch(
        decision={"meeting_date": best_date},
        score=best_score,
        confidence_label=label,
        rationale=(
            f"Shares {len(shared_phrases)} tracked phrases including {shared_preview}."
            if shared_phrases else
            f"Overlap coefficient {best_score:.2f}."
        ),
    )
