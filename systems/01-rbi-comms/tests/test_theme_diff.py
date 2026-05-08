"""Tests for theme-aware diff orchestration."""
from unittest.mock import patch

import pytest

from engine.theme_diff import ThemeDelta, theme_diff_for_pair


@pytest.fixture
def sample_pair():
    prev = {
        "doc_id": "test-prev-001",
        "published_at": "2026-02-06",
        "full_text": (
            "1. Good morning.\n\n"
            "4. MPC voted unanimously to keep the policy repo rate at 5.25 per cent.\n\n"
            "10. Real GDP growth steady. Manufacturing sector resilient.\n\n"
            "14. Headline inflation moderated to 2.7 per cent. Core inflation benign.\n\n"
            "19. System liquidity under the LAF stood at modest surplus."
        ),
    }
    curr = {
        "doc_id": "test-curr-002",
        "published_at": "2026-04-08",
        "full_text": (
            "1. Good morning.\n\n"
            "4. MPC voted unanimously to keep the policy repo rate at 5.25 per cent.\n\n"
            "10. Real GDP growth firming. Manufacturing sector buoyant. Investment cycle expanding.\n\n"
            "14. Headline inflation rose slightly to 3.2 per cent. Core inflation slightly elevated.\n\n"
            "19. System liquidity under the LAF stood at large surplus."
        ),
    }
    return prev, curr


def test_returns_themedeltas(sample_pair):
    prev, curr = sample_pair
    with patch("engine.theme_diff._call_llm_once", return_value={}):
        deltas = theme_diff_for_pair(prev, curr, use_cache=False)
    assert isinstance(deltas, list)
    assert all(isinstance(d, ThemeDelta) for d in deltas)


def test_skips_other_bucket(sample_pair):
    prev, curr = sample_pair
    with patch("engine.theme_diff._call_llm_once", return_value={}):
        deltas = theme_diff_for_pair(prev, curr, use_cache=False)
    themes = [d.theme for d in deltas]
    assert "Other" not in themes


def test_includes_themes_present_in_either_doc(sample_pair):
    prev, curr = sample_pair
    with patch("engine.theme_diff._call_llm_once", return_value={}):
        deltas = theme_diff_for_pair(prev, curr, use_cache=False)
    themes = {d.theme for d in deltas}
    assert "Growth" in themes
    assert "Inflation" in themes
    assert "Liquidity" in themes
    assert "Decisions" in themes


def test_summary_populated_when_llm_returns(sample_pair):
    prev, curr = sample_pair
    fake_summaries = {
        "Growth":    "Growth picture firmed slightly (¶10).",
        "Inflation": "Inflation lifted from 2.7% to 3.2% (¶14).",
        "Liquidity": "Liquidity surplus widened (¶19).",
        "Decisions": "Repo rate held at 5.25% unanimously (¶4).",
    }
    with patch("engine.theme_diff._call_llm_once", return_value=fake_summaries):
        deltas = theme_diff_for_pair(prev, curr, use_cache=False)
    by_theme = {d.theme: d for d in deltas}
    assert by_theme["Growth"].summary == fake_summaries["Growth"]
    assert by_theme["Inflation"].summary == fake_summaries["Inflation"]


def test_summary_none_when_llm_unavailable(sample_pair):
    """If the LLM call returns empty dict (no API key, network failure),
    deltas still produce — summary just stays None."""
    prev, curr = sample_pair
    with patch("engine.theme_diff._call_llm_once", return_value={}):
        deltas = theme_diff_for_pair(prev, curr, use_cache=False)
    assert all(d.summary is None for d in deltas)
    # Phrase deltas are still computed (deterministic)
    assert any(d.phrases_added or d.phrases_removed for d in deltas)


def test_phrase_deltas_disjoint_per_theme(sample_pair):
    """Inherits the document-level disjointness guarantee at theme scope too."""
    prev, curr = sample_pair
    with patch("engine.theme_diff._call_llm_once", return_value={}):
        deltas = theme_diff_for_pair(prev, curr, use_cache=False)
    for d in deltas:
        overlap = set(d.phrases_added) & set(d.phrases_removed)
        assert overlap == set(), f"theme {d.theme} has overlap: {overlap}"


def test_paragraph_counts_recorded(sample_pair):
    prev, curr = sample_pair
    with patch("engine.theme_diff._call_llm_once", return_value={}):
        deltas = theme_diff_for_pair(prev, curr, use_cache=False)
    growth = next(d for d in deltas if d.theme == "Growth")
    assert growth.prev_paragraphs == 1
    assert growth.curr_paragraphs == 1


def test_cache_round_trip(sample_pair, tmp_path, monkeypatch):
    """Computed result is written to cache and read on second call."""
    prev, curr = sample_pair
    monkeypatch.setattr(
        "engine.theme_diff.CACHE_PATH",
        tmp_path / "theme_diff_cache.json",
    )
    fake_summaries = {"Growth": "Growth firmed.", "Decisions": "Held."}

    # First call: LLM hit, cache write
    with patch("engine.theme_diff._call_llm_once", return_value=fake_summaries) as mock_llm:
        deltas_first = theme_diff_for_pair(prev, curr, use_cache=True)
        assert mock_llm.call_count == 1

    # Second call: cache hit, no LLM call
    with patch("engine.theme_diff._call_llm_once", return_value={}) as mock_llm:
        deltas_second = theme_diff_for_pair(prev, curr, use_cache=True)
        assert mock_llm.call_count == 0

    # Same result both times
    assert len(deltas_first) == len(deltas_second)
    by_theme_1 = {d.theme: d.summary for d in deltas_first}
    by_theme_2 = {d.theme: d.summary for d in deltas_second}
    assert by_theme_1 == by_theme_2


def test_use_cache_false_bypasses_cache(sample_pair, tmp_path, monkeypatch):
    prev, curr = sample_pair
    monkeypatch.setattr(
        "engine.theme_diff.CACHE_PATH",
        tmp_path / "theme_diff_cache.json",
    )
    with patch("engine.theme_diff._call_llm_once", return_value={}) as mock_llm:
        theme_diff_for_pair(prev, curr, use_cache=False)
        theme_diff_for_pair(prev, curr, use_cache=False)
        assert mock_llm.call_count == 2  # called both times
