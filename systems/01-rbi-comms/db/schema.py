import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "rbi_comms.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT UNIQUE NOT NULL,
    series_key TEXT NOT NULL,
    meeting_key TEXT,
    published_at TEXT NOT NULL,
    document_type TEXT NOT NULL,
    title TEXT NOT NULL,
    speaker TEXT,
    url TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'RBI',
    summary TEXT,
    full_text TEXT NOT NULL,
    hawkish_score INTEGER NOT NULL DEFAULT 0,
    dovish_score INTEGER NOT NULL DEFAULT 0,
    inflation_mentions INTEGER NOT NULL DEFAULT 0,
    growth_mentions INTEGER NOT NULL DEFAULT 0,
    liquidity_mentions INTEGER NOT NULL DEFAULT 0,
    content_hash TEXT NOT NULL,
    stance_score REAL NOT NULL DEFAULT 0,
    stance_label TEXT NOT NULL DEFAULT 'neutral',
    growth_assessment TEXT,
    inflation_assessment TEXT,
    risk_balance TEXT,
    liquidity_stance TEXT,
    forward_guidance TEXT,
    new_focus_terms_json TEXT NOT NULL DEFAULT '[]',
    fetched_at TEXT DEFAULT (datetime('now')),
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id TEXT UNIQUE NOT NULL,
    doc_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    section_label TEXT,
    page_label TEXT,
    tokens_estimate INTEGER NOT NULL,
    text TEXT NOT NULL,
    citations_json TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts USING fts5(
    chunk_id,
    doc_id,
    text,
    content='document_chunks',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS document_chunks_ai AFTER INSERT ON document_chunks BEGIN
    INSERT INTO document_chunks_fts(rowid, chunk_id, doc_id, text)
    VALUES (new.id, new.chunk_id, new.doc_id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS document_chunks_ad AFTER DELETE ON document_chunks BEGIN
    INSERT INTO document_chunks_fts(document_chunks_fts, rowid, chunk_id, doc_id, text)
    VALUES ('delete', old.id, old.chunk_id, old.doc_id, old.text);
END;

CREATE TRIGGER IF NOT EXISTS document_chunks_au AFTER UPDATE ON document_chunks BEGIN
    INSERT INTO document_chunks_fts(document_chunks_fts, rowid, chunk_id, doc_id, text)
    VALUES ('delete', old.id, old.chunk_id, old.doc_id, old.text);
    INSERT INTO document_chunks_fts(rowid, chunk_id, doc_id, text)
    VALUES (new.id, new.chunk_id, new.doc_id, new.text);
END;

CREATE TABLE IF NOT EXISTS auto_briefs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_key TEXT NOT NULL,
    current_doc_id TEXT NOT NULL,
    previous_doc_id TEXT,
    growth_change TEXT NOT NULL,
    inflation_change TEXT NOT NULL,
    risk_balance_change TEXT NOT NULL,
    liquidity_change TEXT NOT NULL,
    guidance_change TEXT NOT NULL,
    new_focus_terms_json TEXT NOT NULL DEFAULT '[]',
    stance_score REAL NOT NULL,
    stance_label TEXT NOT NULL,
    brief_text TEXT,
    generated_at TEXT DEFAULT (datetime('now'))
);

-- Time-series of structured MPC decisions for the analyst-facing chart layer.
-- One row per MPC meeting; populated from documents.full_text via
-- engine.mpc_extractor.
CREATE TABLE IF NOT EXISTS mpc_decisions (
    meeting_date         TEXT PRIMARY KEY,
    doc_id               TEXT NOT NULL,
    repo_rate            REAL NOT NULL,
    repo_rate_change_bps INTEGER NOT NULL DEFAULT 0,
    vote_for             INTEGER,
    vote_against         INTEGER,
    stance_label         TEXT NOT NULL DEFAULT 'neutral',
    stance_phrase        TEXT,
    cpi_projection_curr_fy    TEXT,
    cpi_projection_curr_value REAL,
    gdp_projection_curr_fy    TEXT,
    gdp_projection_curr_value REAL,
    dissenting_members   TEXT,  -- JSON array, populated from Minutes (P1)
    created_at           TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);
"""


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()
