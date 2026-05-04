"""
Lexicon-based RBI communication stance engine.

Replaces the original 6-keyword counter in `engine/signal_engine.py` with
phrase-based scoring across 6 dimensions (see engine/stance_lexicon.py).
For each dimension the engine produces:
  - score: weighted average (-1 to +1)
  - label: most-recently-emphasized category
  - evidence: list of (phrase, count, weight) so analysts can audit

The engine is deliberately deterministic (no API calls). The Anthropic-backed
brief generator in `ai/brief.py` consumes the structured output.

`signal_engine.py` retains a thin shim for backwards compatibility with the
existing `seed/sample_data.py` and `db/store.py` callers.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Optional

from engine.stance_lexicon import (
    FORWARD_GUIDANCE, GROWTH_ASSESSMENT, INFLATION_ASSESSMENT,
    LIQUIDITY_STANCE, RISK_BALANCE, STANCE,
)


@dataclass
class DimensionResult:
    score: Optional[float]      # weighted average; None if no matches
    label: Optional[str]        # categorical label (signed dimensions only)
    evidence: list[tuple[str, int, float]] = field(default_factory=list)
    # evidence: list of (phrase, count, weight)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CommunicationSignal:
    stance:                DimensionResult
    forward_guidance:      DimensionResult
    growth_assessment:     DimensionResult
    inflation_assessment:  DimensionResult
    liquidity_stance:      DimensionResult
    risk_balance:          DimensionResult
    # Aggregate roll-ups
    hawkish_score:         int       # back-compat: count of "hawkish" matches
    dovish_score:          int       # back-compat: count of "dovish" matches
    net_score:             int       # back-compat: hawkish - dovish
    tone_label:            str       # 'hawkish' | 'dovish' | 'neutral'
    policy_bias:           str       # 'tightening bias' | 'easing bias' | 'on hold'
    inflation_mentions:    int
    growth_mentions:       int
    liquidity_mentions:    int

    def to_record(self) -> dict:
        """Flat dict shape for SQLite upsert (matches existing db schema)."""
        return {
            "hawkish_score":      self.hawkish_score,
            "dovish_score":       self.dovish_score,
            "net_score":          self.net_score,
            "tone_label":         self.tone_label,
            "policy_bias":        self.policy_bias,
            "inflation_mentions": self.inflation_mentions,
            "growth_mentions":    self.growth_mentions,
            "liquidity_mentions": self.liquidity_mentions,
            "stance_score":       self.stance.score or 0.0,
            "stance_label":       self.stance.label or "neutral",
            "growth_assessment":  self.growth_assessment.label or "",
            "inflation_assessment": self.inflation_assessment.label or "",
            "risk_balance":       self.risk_balance.label or "",
            "liquidity_stance":   self.liquidity_stance.label or "",
            "forward_guidance":   ", ".join(
                p for p, _, _ in self.forward_guidance.evidence
            ) if self.forward_guidance.evidence else "",
            "new_focus_terms_json": "[]",  # populated by diff engine in P1
        }


# ─── Core scoring ───────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Lowercase + collapse whitespace for substring matching."""
    return " ".join(text.lower().split())


def _score_signed_dimension(text: str, lexicon: list[tuple[str, float]]) -> DimensionResult:
    """
    Weighted-average score for a signed (numeric-weight) dimension.
    Multiple matches of the same phrase count once each.
    """
    norm = _normalize(text)
    evidence: list[tuple[str, int, float]] = []
    weighted_sum = 0.0
    total_count = 0
    for phrase, weight in lexicon:
        c = norm.count(phrase.lower())
        if c == 0:
            continue
        evidence.append((phrase, c, weight))
        weighted_sum += weight * c
        total_count += c

    if total_count == 0:
        return DimensionResult(score=None, label=None, evidence=[])

    score = weighted_sum / total_count
    label = _label_from_score(score)
    return DimensionResult(score=round(score, 3), label=label, evidence=evidence)


def _score_categorical_dimension(
    text: str, lexicon: list[tuple[str, str]]
) -> DimensionResult:
    """
    Categorical (forward_guidance): records which markers are present.
    score = None (not meaningful for categorical), label = first marker found.
    """
    norm = _normalize(text)
    evidence: list[tuple[str, int, float]] = []
    seen_categories: list[str] = []
    for phrase, category in lexicon:
        c = norm.count(phrase.lower())
        if c == 0:
            continue
        evidence.append((phrase, c, 0.0))
        if category not in seen_categories:
            seen_categories.append(category)

    if not evidence:
        return DimensionResult(score=None, label=None, evidence=[])

    return DimensionResult(
        score=None,
        label=" / ".join(seen_categories),
        evidence=evidence,
    )


def _label_from_score(score: float) -> str:
    if score >= 0.5:
        return "hawkish"
    if score <= -0.5:
        return "dovish"
    if score >= 0.15:
        return "leaning_hawkish"
    if score <= -0.15:
        return "leaning_dovish"
    return "neutral"


# ─── Public API ──────────────────────────────────────────────────────────────

def analyze_communication(text: str) -> CommunicationSignal:
    stance               = _score_signed_dimension(text, STANCE)
    forward_guidance     = _score_categorical_dimension(text, FORWARD_GUIDANCE)
    growth_assessment    = _score_signed_dimension(text, GROWTH_ASSESSMENT)
    inflation_assessment = _score_signed_dimension(text, INFLATION_ASSESSMENT)
    liquidity_stance     = _score_signed_dimension(text, LIQUIDITY_STANCE)
    risk_balance         = _score_signed_dimension(text, RISK_BALANCE)

    # Back-compat aggregates
    hawkish = sum(c for _, c, w in stance.evidence if w > 0)
    dovish  = sum(c for _, c, w in stance.evidence if w < 0)
    hawkish += sum(c for _, c, w in inflation_assessment.evidence if w > 0)
    dovish  += sum(c for _, c, w in inflation_assessment.evidence if w < 0)
    net = hawkish - dovish

    if net >= 2:
        tone, bias = "hawkish", "tightening bias"
    elif net <= -2:
        tone, bias = "dovish", "easing bias"
    else:
        tone, bias = "neutral", "on hold"

    norm = _normalize(text)
    # Liquidity mention count includes related liquidity-policy phrases used
    # by the back-compat tests (matches original signal_engine semantics).
    liquidity_mentions = (
        norm.count("liquidity")
        + norm.count("withdrawal of accommodation")
        + norm.count("transmission")
        + norm.count("financial conditions")
    )
    return CommunicationSignal(
        stance=stance,
        forward_guidance=forward_guidance,
        growth_assessment=growth_assessment,
        inflation_assessment=inflation_assessment,
        liquidity_stance=liquidity_stance,
        risk_balance=risk_balance,
        hawkish_score=hawkish,
        dovish_score=dovish,
        net_score=net,
        tone_label=tone,
        policy_bias=bias,
        inflation_mentions=norm.count("inflation"),
        growth_mentions=norm.count("growth"),
        liquidity_mentions=liquidity_mentions,
    )
