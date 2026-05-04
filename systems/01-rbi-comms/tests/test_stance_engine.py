"""Tests for the lexicon-based stance engine."""
from engine.stance_engine import analyze_communication


def test_signed_dimension_returns_score_and_label():
    text = "Inflation risks remain elevated and upside risks dominate the outlook."
    sig = analyze_communication(text)
    assert sig.inflation_assessment.score is not None
    assert sig.inflation_assessment.label in ("hawkish", "leaning_hawkish")


def test_categorical_dimension_returns_label_only():
    text = "Policy will remain data-dependent and we will be calibrated."
    sig = analyze_communication(text)
    assert sig.forward_guidance.score is None  # categorical
    assert sig.forward_guidance.label is not None
    assert "data_dependent" in sig.forward_guidance.label or "calibrated" in sig.forward_guidance.label


def test_evidence_includes_phrases_with_counts():
    text = "Inflation is easing. Disinflation is broad-based."
    sig = analyze_communication(text)
    phrases = [p for p, _, _ in sig.inflation_assessment.evidence]
    assert any("disinflation" in p.lower() for p in phrases)


def test_empty_text_returns_no_label():
    sig = analyze_communication("")
    assert sig.stance.score is None
    assert sig.stance.label is None
    assert sig.tone_label == "neutral"


def test_to_record_keys_match_db_schema():
    """The record dict must have all keys the documents schema expects."""
    sig = analyze_communication("Inflation risks remain elevated.")
    record = sig.to_record()
    expected = {
        "hawkish_score", "dovish_score", "net_score", "tone_label",
        "policy_bias", "inflation_mentions", "growth_mentions",
        "liquidity_mentions", "stance_score", "stance_label",
        "growth_assessment", "inflation_assessment", "risk_balance",
        "liquidity_stance", "forward_guidance", "new_focus_terms_json",
    }
    assert expected.issubset(record.keys())
