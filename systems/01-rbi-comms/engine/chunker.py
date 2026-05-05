"""
Document chunker for FTS5 retrieval + LLM citation.

Splits a long RBI press release / Minutes into paragraph-sized chunks small
enough to fit comfortably in an LLM context window with multiple peers, and
large enough to preserve sentence-level context for citation.

Each chunk has a stable `chunk_id` of the form `<doc_id>::<chunk_index>` —
analyst-facing UI surfaces this so quotes can be traced back to the exact
RBI passage.

Ported from joshijeet02/rbi-comms-intel and adapted to our seed pipeline.
"""
from __future__ import annotations

import json


def _split_long_paragraph(paragraph: str, max_chars: int) -> list[str]:
    """Word-split a paragraph that exceeds the chunk size."""
    if len(paragraph) <= max_chars:
        return [paragraph]
    parts: list[str] = []
    buffer = ""
    for word in paragraph.split():
        candidate = word if not buffer else f"{buffer} {word}"
        if len(candidate) <= max_chars:
            buffer = candidate
            continue
        if buffer:
            parts.append(buffer)
        buffer = word
    if buffer:
        parts.append(buffer)
    return parts


def chunk_document(doc_id: str, text: str, max_chars: int = 1400) -> list[dict]:
    """
    Split a document into ~1400-char chunks.

    Greedily packs paragraphs together until the next paragraph would push
    the buffer over max_chars; then flushes. Long paragraphs are word-split.

    Returns list of dicts ready for ChunkStore.insert_chunks().
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[dict] = []
    buffer = ""
    chunk_index = 0

    def flush(current: str) -> None:
        nonlocal chunk_index
        cleaned = current.strip()
        if not cleaned:
            return
        chunk_id = f"{doc_id}::{chunk_index}"
        chunks.append({
            "chunk_id":        chunk_id,
            "doc_id":          doc_id,
            "chunk_index":     chunk_index,
            "section_label":   None,
            "page_label":      None,
            "tokens_estimate": max(1, len(cleaned) // 4),  # rough: 4 chars/token
            "text":            cleaned,
            "citations_json":  json.dumps([chunk_id]),
        })
        chunk_index += 1

    for paragraph in paragraphs:
        for piece in _split_long_paragraph(paragraph, max_chars):
            candidate = piece if not buffer else f"{buffer}\n\n{piece}"
            if len(candidate) <= max_chars:
                buffer = candidate
                continue
            flush(buffer)
            buffer = piece

    flush(buffer)
    return chunks
