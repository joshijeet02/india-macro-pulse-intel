"""Integration tests for chunk indexing + FTS5 search end-to-end."""
import pytest

from db.schema import init_db
from db.store import ChunkStore, DocumentStore


@pytest.fixture(autouse=True)
def _db_seeded(tmp_path, monkeypatch):
    """Each test gets a fresh DB seeded from real fixtures."""
    db_dir = tmp_path / "data"
    db_dir.mkdir()
    db_path = db_dir / "test_rbi.db"
    monkeypatch.setattr("db.schema.DB_PATH", db_path)
    monkeypatch.setattr("db.store.DB_PATH", db_path, raising=False)
    init_db()
    from seed.historical_data import seed
    seed()
    yield


def test_chunks_get_indexed():
    """Seed should populate the document_chunks table with at least 100 chunks."""
    assert ChunkStore().count() >= 100


def test_search_finds_inflation_passages():
    docs = DocumentStore()
    rows = docs.search("inflation projection", limit=5)
    assert len(rows) > 0
    assert all("text" in r and "chunk_id" in r for r in rows)
    # Chunks should mention "inflation"
    assert any("inflation" in r["text"].lower() for r in rows)


def test_search_with_intent_expansion():
    """Lay query should expand to domain terms and still hit."""
    docs = DocumentStore()
    rows = docs.search("Will my EMI go up?", limit=5)
    # 'emi' expands to repo/transmission/lending — should hit something
    assert len(rows) > 0


def test_search_returns_chunk_id_and_metadata():
    docs = DocumentStore()
    rows = docs.search("monsoon rural demand", limit=3)
    if rows:
        r = rows[0]
        for k in ("chunk_id", "title", "published_at", "text"):
            assert k in r


def test_search_empty_query_returns_empty():
    docs = DocumentStore()
    assert docs.search("the a is", limit=5) == []


def test_search_handles_malformed_input():
    """Bare punctuation / FTS5 syntax must not crash the call."""
    docs = DocumentStore()
    assert isinstance(docs.search('"', limit=5), list)
    assert isinstance(docs.search("()", limit=5), list)
