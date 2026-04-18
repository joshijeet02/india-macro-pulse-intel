import sqlite3

from db.schema import init_db, DB_PATH


def test_init_db_creates_tables(tmp_path, monkeypatch):
    """init_db creates all required tables in the SQLite file."""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr("db.schema.DB_PATH", test_db)

    init_db()

    conn = sqlite3.connect(test_db)
    try:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
    finally:
        conn.close()

    assert "cpi_releases" in tables
    assert "iip_releases" in tables
    assert "flash_briefs" in tables
    assert "spf_consensus" in tables


def test_init_db_idempotent(tmp_path, monkeypatch):
    """init_db can be called twice without error (IF NOT EXISTS)."""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr("db.schema.DB_PATH", test_db)

    init_db()
    init_db()  # must not raise
