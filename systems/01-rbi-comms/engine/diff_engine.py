"""
Paragraph-aligned diff between two RBI Governor's Statements.

Strategy:
1. Identify each paragraph by its leading paragraph number ("4. " / "10. ").
2. Align by paragraph number — paragraph 4 of the current MPC compares to
   paragraph 4 of the prior MPC. RBI's Governor's Statements are remarkably
   consistent in numbering across cycles.
3. Per aligned pair, compute sentence-level diff with `difflib.ndiff`.
4. Tag any stance/forward-guidance phrases that ENTERED or EXITED the text.

Output is a list of `ParagraphDiff` records, render-ready for Streamlit.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Optional

from engine.stance_lexicon import (
    FORWARD_GUIDANCE, GROWTH_ASSESSMENT, INFLATION_ASSESSMENT,
    LIQUIDITY_STANCE, RISK_BALANCE, STANCE,
)

PARA_NUMBER_RX = re.compile(r"^(\d+)\.\s")


@dataclass
class ParagraphDiff:
    paragraph_number: int
    prev_text: Optional[str]
    curr_text: Optional[str]
    sentence_diff: list[str]  # output of difflib.ndiff
    phrases_added: list[str] = field(default_factory=list)
    phrases_removed: list[str] = field(default_factory=list)
    is_unchanged: bool = False


def _split_into_paragraphs(text: str) -> dict[int, str]:
    """
    Split a Governor's Statement (one paragraph per line, numbered) into a
    dict keyed by paragraph number. Unnumbered intro lines (e.g., the
    opening greeting) get key 0.
    """
    out: dict[int, str] = {}
    current_num = 0
    buffer: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        m = PARA_NUMBER_RX.match(line)
        if m:
            if buffer:
                out[current_num] = " ".join(buffer).strip()
                buffer = []
            current_num = int(m.group(1))
            buffer.append(line)
        else:
            buffer.append(line)
    if buffer:
        out[current_num] = " ".join(buffer).strip()
    return out


def _split_sentences(paragraph: str) -> list[str]:
    """Tokenize a paragraph into sentences. Intentionally simple — full NLP overkill."""
    # Split on sentence-ending punctuation followed by whitespace + capital
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", paragraph)
    return [p.strip() for p in parts if p.strip()]


def _all_lexicon_phrases() -> list[str]:
    """Flat list of all tracked phrases for entry/exit detection."""
    phrases: list[str] = []
    for lex in (STANCE, GROWTH_ASSESSMENT, INFLATION_ASSESSMENT, LIQUIDITY_STANCE, RISK_BALANCE):
        phrases.extend(p for p, _ in lex)
    phrases.extend(p for p, _ in FORWARD_GUIDANCE)
    # Dedupe + sort by length DESC so longer phrases match first
    return sorted(set(phrases), key=len, reverse=True)


_LEXICON = _all_lexicon_phrases()


def _phrases_in(text: str) -> set[str]:
    lc = text.lower()
    return {p for p in _LEXICON if p.lower() in lc}


def diff_documents(prev_text: str, curr_text: str) -> list[ParagraphDiff]:
    """
    Return a list of ParagraphDiff records, one per aligned paragraph that
    differs (or that exists in only one document). Unchanged paragraphs
    are NOT included by default — use diff_documents_full() to keep them.
    """
    prev_paras = _split_into_paragraphs(prev_text)
    curr_paras = _split_into_paragraphs(curr_text)

    all_keys = sorted(set(prev_paras) | set(curr_paras))
    out: list[ParagraphDiff] = []

    for key in all_keys:
        p = prev_paras.get(key, "")
        c = curr_paras.get(key, "")
        if p == c:
            continue  # skip unchanged

        prev_sents = _split_sentences(p)
        curr_sents = _split_sentences(c)
        sentence_diff = list(difflib.ndiff(prev_sents, curr_sents))

        prev_phrases = _phrases_in(p)
        curr_phrases = _phrases_in(c)
        phrases_added = sorted(curr_phrases - prev_phrases)
        phrases_removed = sorted(prev_phrases - curr_phrases)

        out.append(ParagraphDiff(
            paragraph_number=key,
            prev_text=p or None,
            curr_text=c or None,
            sentence_diff=sentence_diff,
            phrases_added=phrases_added,
            phrases_removed=phrases_removed,
            is_unchanged=False,
        ))

    return out


def summarize_diff(diffs: list[ParagraphDiff]) -> dict:
    """Aggregate stats for the 'What Changed' header."""
    paragraphs_changed = len(diffs)
    all_added = sorted({p for d in diffs for p in d.phrases_added})
    all_removed = sorted({p for d in diffs for p in d.phrases_removed})
    return {
        "paragraphs_changed": paragraphs_changed,
        "phrases_added":      all_added,
        "phrases_removed":    all_removed,
    }
