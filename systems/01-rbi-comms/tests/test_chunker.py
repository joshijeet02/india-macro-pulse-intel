"""Tests for the document chunker."""
from engine.chunker import chunk_document


def test_short_text_produces_single_chunk():
    text = "Para 1 short.\n\nPara 2 short."
    chunks = chunk_document("doc-1", text, max_chars=1400)
    assert len(chunks) == 1
    assert chunks[0]["chunk_id"] == "doc-1::0"
    assert chunks[0]["doc_id"] == "doc-1"


def test_chunks_pack_paragraphs_until_max():
    """Two 600-char paragraphs should pack into one chunk; a third spills over."""
    para = "x" * 600
    text = "\n\n".join([para] * 3)  # 600 + 2 + 600 = 1202 fits, +600 = 1804 doesn't
    chunks = chunk_document("doc-1", text, max_chars=1400)
    assert len(chunks) == 2
    assert all(len(c["text"]) <= 1500 for c in chunks)  # +newlines slack


def test_long_paragraph_is_word_split():
    long_para = "word " * 500  # ~2500 chars
    chunks = chunk_document("doc-1", long_para.strip(), max_chars=600)
    assert len(chunks) >= 4
    for c in chunks:
        assert len(c["text"]) <= 700  # within slack


def test_chunk_ids_are_unique_and_sequential():
    text = "\n\n".join([f"Para {i}." for i in range(20)])
    chunks = chunk_document("doc-1", text, max_chars=200)
    ids = [c["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids))
    indices = [c["chunk_index"] for c in chunks]
    assert indices == list(range(len(indices)))


def test_chunk_payload_has_required_fields():
    chunks = chunk_document("rbi-pr-62515", "Some content here.", max_chars=1400)
    keys = chunks[0].keys()
    for required in ("chunk_id", "doc_id", "chunk_index", "tokens_estimate", "text", "citations_json"):
        assert required in keys


def test_empty_text_returns_no_chunks():
    assert chunk_document("doc-1", "") == []
    assert chunk_document("doc-1", "   \n\n   \n   ") == []
