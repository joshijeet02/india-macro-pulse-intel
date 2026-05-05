"""
Natural-language → FTS5 query builder for the corpus search.

Translates a user's question ("Will my home loan EMI go up?") into an FTS5
OR-query. Two passes:

1. **Direct tokens** — keep the user's content words (drop stopwords + short tokens).
2. **Intent expansion** — when the user uses lay vocabulary like "EMI" or "jobs",
   expand to RBI domain terms ("repo", "transmission", "lending"; "growth",
   "demand", "output"). This is what lets a non-economist ask plain-English
   questions and still hit the FTS index.

The intent map is the most important part — it's the bridge between the
user's mental model and RBI's vocabulary. Tuned for India-rates-watcher
language. Ported from joshijeet02/rbi-comms-intel.
"""
from __future__ import annotations

import re

STOPWORDS = {
    "a", "about", "an", "and", "any", "are", "as", "at",
    "been", "can", "did", "does", "do", "for", "from",
    "has", "have", "how", "in", "is", "it", "its",
    "last", "me", "my", "of", "on", "or", "since",
    "tell", "the", "their", "think", "thinking", "this",
    "to", "us", "was", "what", "when", "which", "who", "will",
    "with", "years", "year",
}

# Map natural-language concepts to RBI domain keywords. Non-exhaustive but
# covers the questions a sell-side analyst or curious lay reader would ask.
INTENT_KEYWORDS: dict[str, list[str]] = {
    "evolve":     ["inflation", "growth", "stance", "guidance", "liquidity"],
    "evolution":  ["inflation", "growth", "stance", "guidance", "liquidity"],
    "change":     ["inflation", "growth", "stance", "guidance"],
    "changed":    ["inflation", "growth", "stance", "guidance"],
    "thinking":   ["inflation", "growth", "stance", "policy"],
    "view":       ["inflation", "growth", "stance"],
    "views":      ["inflation", "growth", "stance"],
    "stance":     ["stance", "hawkish", "dovish", "accommodation"],
    "emi":        ["repo", "transmission", "rate", "lending"],
    "loan":       ["repo", "transmission", "credit", "lending"],
    "homeloan":   ["repo", "transmission", "credit"],
    "savings":    ["repo", "liquidity", "deposit"],
    "prices":     ["inflation", "food", "core", "supply"],
    "food":       ["food", "inflation", "supply", "monsoon"],
    "economy":    ["growth", "gdp", "demand", "output"],
    "jobs":       ["growth", "demand", "output", "employment"],
    "rbi":        ["inflation", "growth", "stance", "guidance", "liquidity"],
    "vote":       ["voted", "members", "favour", "against", "unanimous"],
    "dissent":    ["voted", "members", "against", "dissent"],
    "transmission": ["transmission", "lags", "lending", "deposit"],
    "monsoon":    ["monsoon", "rural", "food", "agriculture"],
    "global":     ["global", "external", "spillover", "uncertainty"],
}


def prepare_search_query(query: str) -> str:
    """
    Convert user question into an FTS5 OR-query string.

    Returns empty string if no usable terms remain (caller should treat as
    "no FTS match" and fall back to recent docs).
    """
    raw_tokens = re.findall(r"[a-zA-Z0-9]+", query.lower())

    # Expand any intent triggers to domain terms
    expansions: list[str] = []
    for token in raw_tokens:
        if token in INTENT_KEYWORDS:
            expansions.extend(INTENT_KEYWORDS[token])

    # Direct content tokens (skip stopwords + tiny tokens)
    direct_tokens = [t for t in raw_tokens if len(t) > 2 and t not in STOPWORDS]

    # Merge, dedupe (preserving order), drop blanks
    combined = list(dict.fromkeys(direct_tokens + expansions))
    if not combined:
        return ""
    return " OR ".join(combined)


def build_context_window(rows: list[dict]) -> str:
    """Format retrieval results as a citation-ready LLM context block."""
    blocks = []
    for row in rows:
        blocks.append(
            f"[{row['chunk_id']}] {row['title']} ({row['published_at']})\n"
            f"{row['text']}"
        )
    return "\n\n".join(blocks)
