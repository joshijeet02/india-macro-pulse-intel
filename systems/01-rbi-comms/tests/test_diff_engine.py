"""Tests for the paragraph-aligned diff engine."""
from engine.diff_engine import diff_documents, summarize_diff


def test_unchanged_documents_produce_no_diffs():
    text = "1. The MPC met today.\n\n2. Decision: rate unchanged.\n\n3. Vote: 6-0."
    diffs = diff_documents(text, text)
    assert diffs == []


def test_changed_paragraph_is_detected():
    prev = "1. The MPC voted to keep the rate at 6.50 per cent.\n\n2. Stance: neutral."
    curr = "1. The MPC voted to reduce the rate to 6.25 per cent.\n\n2. Stance: neutral."
    diffs = diff_documents(prev, curr)
    assert len(diffs) == 1
    assert diffs[0].paragraph_number == 1
    assert "6.25" in diffs[0].curr_text


def test_added_paragraph_appears():
    prev = "1. Para one.\n\n2. Para two."
    curr = "1. Para one.\n\n2. Para two.\n\n3. New paragraph appended."
    diffs = diff_documents(prev, curr)
    assert any(d.paragraph_number == 3 and d.prev_text is None for d in diffs)


def test_removed_paragraph_appears():
    prev = "1. Para one.\n\n2. Para two.\n\n3. Para three."
    curr = "1. Para one.\n\n2. Para two."
    diffs = diff_documents(prev, curr)
    assert any(d.paragraph_number == 3 and d.curr_text is None for d in diffs)


def test_phrase_transition_added():
    prev = "1. The MPC will remain accommodative."
    curr = "1. The MPC stance is now neutral."
    diffs = diff_documents(prev, curr)
    assert len(diffs) == 1
    # The lexicon catches "remain accommodative" exiting and "neutral" entering
    assert any("accommodative" in p.lower() for p in diffs[0].phrases_removed)


def test_summarize_aggregates():
    prev = "1. Withdrawal of accommodation continues.\n\n2. Inflation easing."
    curr = "1. Stance is now neutral.\n\n2. Inflation easing further."
    diffs = diff_documents(prev, curr)
    summary = summarize_diff(diffs)
    assert summary["paragraphs_changed"] >= 1
    # "withdrawal of accommodation" should appear in phrases_removed
    assert any("withdrawal" in p.lower() for p in summary["phrases_removed"])
