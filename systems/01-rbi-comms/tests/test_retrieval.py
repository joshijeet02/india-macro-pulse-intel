"""Tests for the NL → FTS5 query builder."""
from engine.retrieval import (
    INTENT_KEYWORDS, build_context_window, prepare_search_query,
)


def test_direct_tokens_kept():
    q = prepare_search_query("inflation forecast for 2026")
    assert "inflation" in q
    assert "forecast" in q
    # Stopwords are dropped
    assert "for" not in q.split(" OR ")


def test_stopwords_filtered():
    q = prepare_search_query("what is the stance")
    # "what" and "is" and "the" are stopwords
    parts = q.split(" OR ")
    assert "what" not in parts and "the" not in parts and "is" not in parts


def test_intent_expansion_emi():
    """'EMI' is lay vocabulary; should expand to RBI domain terms."""
    q = prepare_search_query("Will my home loan EMI go up?")
    parts = q.split(" OR ")
    assert "repo" in parts
    assert "transmission" in parts


def test_intent_expansion_food():
    q = prepare_search_query("Are food prices stabilizing?")
    parts = q.split(" OR ")
    # 'food' triggers expansion to inflation/supply/monsoon
    assert "monsoon" in parts or "supply" in parts


def test_empty_query_returns_empty_string():
    """No usable terms after filtering — caller treats as 'no FTS match'."""
    assert prepare_search_query("") == ""
    assert prepare_search_query("the in is to a") == ""


def test_combined_or_joined():
    q = prepare_search_query("growth and inflation")
    assert " OR " in q


def test_intent_keywords_have_unique_targets():
    """Sanity: each intent maps to a non-empty list of domain terms."""
    for token, expansions in INTENT_KEYWORDS.items():
        assert expansions, f"INTENT_KEYWORDS[{token!r}] is empty"
        assert all(isinstance(t, str) for t in expansions)


def test_build_context_window_formats_with_citations():
    rows = [
        {"chunk_id": "doc-1::0", "title": "Title A", "published_at": "2026-04-08", "text": "Body A."},
        {"chunk_id": "doc-2::1", "title": "Title B", "published_at": "2026-02-06", "text": "Body B."},
    ]
    out = build_context_window(rows)
    assert "[doc-1::0]" in out
    assert "[doc-2::1]" in out
    assert "Title A" in out and "Body A." in out
