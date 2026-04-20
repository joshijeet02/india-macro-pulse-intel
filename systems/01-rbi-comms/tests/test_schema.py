import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.schema import init_db


class InitDbTests(unittest.TestCase):
    def test_init_db_creates_tables(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db = Path(tmpdir) / "test.db"
            with mock.patch("db.schema.DB_PATH", test_db):
                init_db()

            conn = sqlite3.connect(test_db)
            try:
                rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                tables = {row[0] for row in rows}
            finally:
                conn.close()

            self.assertIn("documents", tables)
            self.assertIn("document_chunks", tables)
            self.assertIn("document_chunks_fts", tables)
            self.assertIn("auto_briefs", tables)

    def test_init_db_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db = Path(tmpdir) / "test.db"
            with mock.patch("db.schema.DB_PATH", test_db):
                init_db()
                init_db()


if __name__ == "__main__":
    unittest.main()
