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
    summary = summarize_diff(diffs, prev_text=prev, curr_text=curr)
    assert summary["paragraphs_changed"] >= 1
    # "withdrawal of accommodation" should appear in phrases_removed
    assert any("withdrawal" in p.lower() for p in summary["phrases_removed"])


def test_summarize_added_and_removed_are_disjoint_when_phrase_moves_paragraphs():
    """
    Regression test for Sid's bug:

    A phrase that appears in DIFFERENT paragraphs of the prev and curr
    documents must not appear in both `phrases_added` and `phrases_removed`.
    By document-level set algebra, the intersection should always be empty.
    """
    # "remain accommodative" exists in BOTH documents — just in different
    # paragraphs. The old paragraph-level summary would mark it as both added
    # (to ¶6) and removed (from ¶4). Document-level set diff sees it's in
    # both and excludes it from both lists.
    prev = (
        "1. Opening remarks.\n\n"
        "2. Growth view.\n\n"
        "3. Inflation view.\n\n"
        "4. The MPC decided to remain accommodative.\n\n"
        "5. Liquidity stance.\n\n"
        "6. Closing remarks."
    )
    curr = (
        "1. Opening remarks.\n\n"
        "2. Growth view (revised).\n\n"
        "3. Inflation view (revised).\n\n"
        "4. The committee adjusted its outlook.\n\n"
        "5. Liquidity stance.\n\n"
        "6. The MPC decided to remain accommodative."
    )
    diffs = diff_documents(prev, curr)
    summary = summarize_diff(diffs, prev_text=prev, curr_text=curr)

    added_set = set(summary["phrases_added"])
    removed_set = set(summary["phrases_removed"])
    overlap = added_set & removed_set
    assert overlap == set(), (
        f"phrases_added and phrases_removed must be disjoint at document level "
        f"(set algebra guarantee). Overlap: {overlap}"
    )
    # "remain accommodative" appears in BOTH documents, so neither side
    assert not any("accommodative" in p.lower() for p in summary["phrases_added"])
    assert not any("accommodative" in p.lower() for p in summary["phrases_removed"])


def test_summarize_legacy_fallback_when_texts_not_supplied():
    """The legacy path (paragraph-level union) is preserved for API stability,
    even though it can produce overlap. Tests that a caller without texts
    still gets a valid dict shape."""
    prev = "1. Withdrawal of accommodation."
    curr = "1. Stance is neutral."
    diffs = diff_documents(prev, curr)
    summary = summarize_diff(diffs)  # no texts — legacy path
    assert "phrases_added" in summary
    assert "phrases_removed" in summary
    assert "paragraphs_changed" in summary
