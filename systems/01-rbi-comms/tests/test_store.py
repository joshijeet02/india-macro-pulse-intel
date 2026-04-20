import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sqlite3

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.schema import init_db
from db.store import DocumentStore


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.test_db = Path(self.tmpdir.name) / "test.db"
        self.schema_patch = mock.patch("db.schema.DB_PATH", self.test_db)
        self.store_patch = mock.patch("db.store.DB_PATH", self.test_db)
        self.schema_patch.start()
        self.store_patch.start()
        init_db()

    def tearDown(self):
        self.store_patch.stop()
        self.schema_patch.stop()
        self.tmpdir.cleanup()

    def test_document_store_upsert_and_get_document(self):
        store = DocumentStore()
        store.upsert_document(
            {
                "doc_id": "mpc-2025-04",
                "series_key": "mpc",
                "meeting_key": "2025-04",
                "published_at": "2025-04-09",
                "document_type": "Monetary Policy Statement",
                "title": "Resolution of the Monetary Policy Committee",
                "speaker": "MPC",
                "url": "https://rbi.example/mpc-2025-04",
                "summary": "Policy rate unchanged with hawkish guidance.",
                "full_text": "Inflation risks remain elevated and the stance stays focused on withdrawal of accommodation.",
                "content_hash": "hash-mpc-2025-04",
            }
        )

        row = store.get_document("mpc-2025-04")

        self.assertIsNotNone(row)
        self.assertEqual(row["doc_id"], "mpc-2025-04")
        self.assertEqual(row["title"], "Resolution of the Monetary Policy Committee")
        self.assertEqual(row["source"], "RBI")
        self.assertEqual(row["stance_label"], "neutral")

    def test_document_store_returns_legacy_read_aliases(self):
        store = DocumentStore()
        store.upsert_document(
            {
                "doc_id": "speech-2025-04-15",
                "series_key": "speech",
                "published_at": "2025-04-15",
                "document_type": "Governor Speech",
                "title": "Speech on inflation and growth",
                "speaker": "Governor",
                "url": "https://rbi.example/speech-2025-04-15",
                "summary": "Balanced speech.",
                "full_text": "Disinflation is progressing but vigilance remains necessary.",
                "content_hash": "hash-speech-2025-04-15",
                "net_score": 3,
                "tone_label": "hawkish",
                "policy_bias": "tightening bias",
                "hawkish_score": 4,
                "dovish_score": 1,
                "inflation_mentions": 3,
                "growth_mentions": 2,
                "liquidity_mentions": 1,
            }
        )

        row = store.get_latest()
        history_row = store.tone_history(limit=1)[0]

        self.assertIsNotNone(row)
        self.assertEqual(row["stance_score"], 3)
        self.assertEqual(row["stance_label"], "hawkish")
        self.assertEqual(row["forward_guidance"], "tightening bias")
        self.assertEqual(row["net_score"], 3)
        self.assertEqual(row["tone_label"], "hawkish")
        self.assertEqual(row["policy_bias"], "tightening bias")
        self.assertEqual(row["hawkish_score"], 4)
        self.assertEqual(row["dovish_score"], 1)
        self.assertEqual(row["inflation_mentions"], 3)
        self.assertEqual(row["growth_mentions"], 2)
        self.assertEqual(row["liquidity_mentions"], 1)
        self.assertEqual(history_row["hawkish_score"], 4)
        self.assertEqual(history_row["dovish_score"], 1)
        self.assertEqual(history_row["inflation_mentions"], 3)
        self.assertEqual(history_row["growth_mentions"], 2)
        self.assertEqual(history_row["liquidity_mentions"], 1)

    def test_document_store_returns_previous_document_in_series(self):
        store = DocumentStore()
        store.upsert_document(
            {
                "doc_id": "mpc-2025-02",
                "series_key": "mpc",
                "meeting_key": "2025-02",
                "published_at": "2025-02-07",
                "document_type": "Monetary Policy Statement",
                "title": "Resolution of the Monetary Policy Committee - February",
                "speaker": "MPC",
                "url": "https://rbi.example/mpc-2025-02",
                "summary": "Earlier statement.",
                "full_text": "Inflation risks remain elevated.",
                "content_hash": "hash-mpc-2025-02",
            }
        )
        store.upsert_document(
            {
                "doc_id": "mpc-2025-04",
                "series_key": "mpc",
                "meeting_key": "2025-04",
                "published_at": "2025-04-09",
                "document_type": "Monetary Policy Statement",
                "title": "Resolution of the Monetary Policy Committee - April",
                "speaker": "MPC",
                "url": "https://rbi.example/mpc-2025-04",
                "summary": "Current statement.",
                "full_text": "Inflation is easing but vigilance remains necessary.",
                "content_hash": "hash-mpc-2025-04",
            }
        )

        previous = store.get_previous_in_series("mpc", "2025-04-09")

        self.assertIsNotNone(previous)
        self.assertEqual(previous["doc_id"], "mpc-2025-02")
        self.assertEqual(previous["published_at"], "2025-02-07")

    def test_document_chunks_fts_stays_in_sync_on_insert(self):
        conn = sqlite3.connect(self.test_db)
        try:
            conn.execute(
                """
                INSERT INTO document_chunks (
                    chunk_id,
                    doc_id,
                    chunk_index,
                    section_label,
                    page_label,
                    tokens_estimate,
                    text,
                    citations_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "chunk-1",
                    "mpc-2025-04",
                    0,
                    "Policy stance",
                    "p. 1",
                    12,
                    "Inflation risks remain elevated and vigilance is required.",
                    "[]",
                ),
            )
            conn.commit()

            rows = conn.execute(
                """
                SELECT chunk_id
                FROM document_chunks_fts
                WHERE document_chunks_fts MATCH ?
                """,
                ("vigilance",),
            ).fetchall()
        finally:
            conn.close()

        self.assertEqual([row[0] for row in rows], ["chunk-1"])


if __name__ == "__main__":
    unittest.main()
