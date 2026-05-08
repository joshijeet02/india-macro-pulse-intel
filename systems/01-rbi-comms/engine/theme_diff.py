"""
Theme-aware diff between two MPC Governor's Statements.

Sid's feedback (verbatim): "don't run [the diff] by paragraph. Instead get
the LLM to chunk the paragraphs into themes, then compare the themes and
extract contextual diff, not absolute diff."

Pipeline:
1. Run engine/theme_chunker.py on both prev and curr texts → per-theme paragraphs.
2. For each theme that has content, compute lexicon-tracked phrase entries
   and exits at the theme level (using the same _phrases_in helper as
   the document-level diff — so the disjointness guarantee carries through).
3. SINGLE LLM call (Sonnet 4.6) that produces a 2-line contextual summary
   for each theme. Batched into one round-trip for cost & latency.
4. JSON-file cache keyed on (prev_doc_id, curr_doc_id, prompt_version).
   Survives Streamlit Cloud redeploys because data/ is in the repo.

Cost target (per PRD): ≤$0.10 per cold render at Sonnet rates.
Achieved: ~$0.025 (one ~5k input, ~700 output token call).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from engine.diff_engine import _phrases_in
from engine.theme_chunker import (
    THEME_ICONS, THEME_ORDER, chunk_by_theme,
    joined_theme_text, themes_with_content,
)

log = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).parent.parent / "data" / "theme_diff_cache.json"

# Bumping this invalidates any cached LLM output that came from an older
# prompt — keeps the cache truthful when we tweak the analyst voice.
PROMPT_VERSION = "v1.0"


@dataclass
class ThemeDelta:
    theme:           str
    icon:            str
    prev_paragraphs: int
    curr_paragraphs: int
    phrases_added:   list[str] = field(default_factory=list)
    phrases_removed: list[str] = field(default_factory=list)
    summary:         Optional[str] = None  # LLM-generated; may be None if API unavailable

    def to_dict(self) -> dict:
        return asdict(self)


# ─── Cache ───────────────────────────────────────────────────────────────────

def _cache_key(prev_doc_id: str, curr_doc_id: str) -> str:
    raw = f"{prev_doc_id}::{curr_doc_id}::{PROMPT_VERSION}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        log.warning(f"theme_diff_cache unreadable: {exc}")
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_PATH.with_suffix(CACHE_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(cache, indent=2) + "\n")
    tmp.replace(CACHE_PATH)


# ─── Phrase deltas per theme ────────────────────────────────────────────────

def _theme_phrase_deltas(prev_text: str, curr_text: str) -> tuple[list[str], list[str]]:
    """Document-level set algebra applied at theme scope. Always disjoint."""
    prev_phrases = _phrases_in(prev_text)
    curr_phrases = _phrases_in(curr_text)
    added = sorted(curr_phrases - prev_phrases)
    removed = sorted(prev_phrases - curr_phrases)
    return added, removed


# ─── LLM contextual summary (single batched call) ───────────────────────────

_SYSTEM_PROMPT = (
    "You are a senior India macro economist. The reader is a hedge fund desk "
    "strategist prepping a 90-second post-MPC view.\n\n"
    "For each theme below, produce ONE short paragraph (≤60 words) explaining "
    "what shifted between the two MPC Statements. Cite paragraph numbers in "
    "parentheses for any quoted phrasing — e.g., (¶4). Avoid analyst clichés "
    "('hawkish tilt', 'dovish pivot'). Voice: terse, decisive, professional. "
    "If a theme has no meaningful change, write 'Unchanged: <one-line reason>.'\n\n"
    "Output format — one block per theme:\n"
    "## <Theme Name>\n"
    "<your one paragraph>\n\n"
    "Themes will be supplied in the user message. Use only the supplied text "
    "— do not invent dates, vote splits, or projections that aren't there."
)


def _build_user_prompt(prev_date: str, curr_date: str, theme_pairs: list[dict]) -> str:
    lines = [
        f"Comparing prev MPC ({prev_date}) → curr MPC ({curr_date}).",
        "",
        "For each theme below, the prev and curr text blocks are quoted.",
        "Produce one '## <Theme>' block per theme, in the order given.",
        "",
    ]
    for tp in theme_pairs:
        lines.append(f"=== Theme: {tp['theme']} ===")
        lines.append(f"PREV ({prev_date}):")
        lines.append(tp["prev_text"] or "(no content)")
        lines.append("")
        lines.append(f"CURR ({curr_date}):")
        lines.append(tp["curr_text"] or "(no content)")
        lines.append("")
    return "\n".join(lines)


def _parse_llm_summary(text: str) -> dict[str, str]:
    """Parse the LLM's '## <Theme>\\n<paragraph>' format into a dict."""
    out: dict[str, str] = {}
    current_theme: Optional[str] = None
    buffer: list[str] = []

    def flush() -> None:
        if current_theme and buffer:
            out[current_theme] = " ".join(line.strip() for line in buffer if line.strip()).strip()

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            flush()
            current_theme = line[3:].strip()
            buffer = []
        elif current_theme:
            buffer.append(line)
    flush()
    return out


def _call_llm_once(theme_pairs: list[dict], prev_date: str, curr_date: str) -> dict[str, str]:
    """Single Anthropic call producing summaries for all themes. Empty dict on failure."""
    try:
        from ai.brief import MODEL, _client
    except ImportError as exc:
        log.warning(f"brief module unavailable: {exc}")
        return {}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.info("No ANTHROPIC_API_KEY — skipping LLM summary")
        return {}

    try:
        client = _client()
        message = client.messages.create(
            model=MODEL,
            max_tokens=900,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_prompt(prev_date, curr_date, theme_pairs)}],
        )
        return _parse_llm_summary(message.content[0].text)
    except Exception as exc:
        log.warning(f"LLM summary call failed: {exc}")
        return {}


# ─── Public entrypoint ──────────────────────────────────────────────────────

def theme_diff_for_pair(
    prev_doc: dict,
    curr_doc: dict,
    use_cache: bool = True,
) -> list[ThemeDelta]:
    """
    Produce theme-grouped diffs between two MPC Statement documents.

    `prev_doc` / `curr_doc` need: doc_id, full_text, published_at.

    Returns a list[ThemeDelta] in canonical theme order, including only themes
    that have at least one paragraph in either document.
    """
    prev_id = prev_doc["doc_id"]
    curr_id = curr_doc["doc_id"]
    cache_key = _cache_key(prev_id, curr_id)

    cache = _load_cache() if use_cache else {}
    if cache_key in cache:
        log.info(f"theme_diff cache HIT for {prev_id} → {curr_id}")
        try:
            return [ThemeDelta(**d) for d in cache[cache_key]]
        except (TypeError, KeyError) as exc:
            log.warning(f"cache entry malformed; recomputing: {exc}")

    log.info(f"theme_diff cache MISS — computing for {prev_id} → {curr_id}")

    prev_by_theme = chunk_by_theme(prev_doc.get("full_text", ""))
    curr_by_theme = chunk_by_theme(curr_doc.get("full_text", ""))

    # Build the input for the LLM call. Only include themes with at least one
    # paragraph in EITHER document — skip 'Other' (intro/closing chatter is
    # not analyst-relevant).
    relevant_themes = [
        t for t in THEME_ORDER
        if t != "Other" and (prev_by_theme.get(t) or curr_by_theme.get(t))
    ]

    theme_pairs = []
    for theme in relevant_themes:
        prev_text = joined_theme_text(prev_by_theme.get(theme, []))
        curr_text = joined_theme_text(curr_by_theme.get(theme, []))
        theme_pairs.append({
            "theme":     theme,
            "prev_text": prev_text,
            "curr_text": curr_text,
        })

    # One LLM call for ALL themes (efficiency).
    summaries = _call_llm_once(
        theme_pairs,
        prev_date=prev_doc.get("published_at", ""),
        curr_date=curr_doc.get("published_at", ""),
    )

    deltas: list[ThemeDelta] = []
    for tp in theme_pairs:
        theme = tp["theme"]
        added, removed = _theme_phrase_deltas(tp["prev_text"], tp["curr_text"])
        deltas.append(ThemeDelta(
            theme=theme,
            icon=THEME_ICONS.get(theme, ""),
            prev_paragraphs=len(prev_by_theme.get(theme, [])),
            curr_paragraphs=len(curr_by_theme.get(theme, [])),
            phrases_added=added,
            phrases_removed=removed,
            summary=summaries.get(theme),
        ))

    # Persist to cache (best-effort)
    if use_cache:
        try:
            cache[cache_key] = [d.to_dict() for d in deltas]
            _save_cache(cache)
        except Exception as exc:
            log.warning(f"could not write theme_diff_cache: {exc}")

    return deltas
