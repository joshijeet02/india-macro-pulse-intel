"""
The JSON sidecar (`data/rbi_communications.json`) is the only source for
Minutes documents published between Oct 2016 and the most recent backfill.
Without per-member analysis on these sidecar entries, every meeting from
that period is missing its `mpc_member_views` rows — most consequentially,
Prof. Jayanth R. Varma's entire dissent record (Dec 2022 + Feb 2023) is
silently absent from the live app.

These tests pin that the sidecar seeder runs `analyze_minutes` on every
Minutes document and persists the member rows into the SQLite store.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))


class SidecarMemberSeedingTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.test_db = Path(self.tmpdir.name) / "test.db"
        self.schema_patch = mock.patch("db.schema.DB_PATH", self.test_db)
        self.store_patch = mock.patch("db.store.DB_PATH", self.test_db)
        self.schema_patch.start()
        self.store_patch.start()

        from db.schema import init_db
        init_db()

    def tearDown(self):
        self.store_patch.stop()
        self.schema_patch.stop()
        self.tmpdir.cleanup()

    def _run_sidecar(self):
        from seed.historical_data import _seed_from_json_sidecar
        return _seed_from_json_sidecar()

    # ─── Varma appears at all ─────────────────────────────────────────────────

    def test_sidecar_seeds_member_views_for_minutes_documents(self):
        """After the sidecar runs, mpc_member_views must be non-empty.

        Without the fix, the sidecar persists Communications + Decisions but
        skips per-member analysis entirely, so the table stays empty.
        """
        self._run_sidecar()
        from db.store import MemberViewStore
        assert MemberViewStore().count() > 0, \
            "mpc_member_views is empty — sidecar didn't run analyze_minutes"

    def test_sidecar_includes_varma_in_member_views(self):
        """Prof. Varma must appear in `mpc_member_views` after seeding.

        He was on the MPC from Oct 2020 to Oct 2023 and attended ~17 meetings.
        Anything less than 10 Varma rows means the per-member extractor isn't
        being called on the historical Minutes.
        """
        self._run_sidecar()
        import sqlite3
        rows = sqlite3.connect(self.test_db).execute(
            "SELECT COUNT(*) FROM mpc_member_views WHERE member_name LIKE '%Varma%'"
        ).fetchone()
        assert rows[0] >= 10, f"Varma appears in only {rows[0]} meetings (expected >=10)"

    # ─── Specific dissents are attributed ─────────────────────────────────────

    def test_sidecar_attributes_varma_dissent_in_dec_2022(self):
        """Dec 2022 rate-resolution vote: 5-1 with Varma as the lone dissenter."""
        self._run_sidecar()
        import sqlite3
        rows = sqlite3.connect(self.test_db).execute("""
            SELECT member_name, vote
            FROM mpc_member_views
            WHERE meeting_date LIKE '2022-12%' AND member_name LIKE '%Varma%'
        """).fetchall()
        assert rows, "Varma's Dec 2022 row is missing"
        assert rows[0][1] == "No", \
            f"Dec 2022 Varma should vote 'No' on rate, got {rows[0][1]!r}"

    def test_sidecar_attributes_varma_and_goyal_dissent_in_feb_2023(self):
        """Feb 2023 rate-resolution vote: 4-2 with Goyal AND Varma dissenting.

        This is the meeting whose misattribution Verma is most likely to test —
        a 4-2 dissent reported as 4-1 would be a credibility-killer.
        """
        self._run_sidecar()
        import sqlite3
        rows = dict(sqlite3.connect(self.test_db).execute("""
            SELECT member_name, vote
            FROM mpc_member_views
            WHERE meeting_date LIKE '2023-02%' AND vote = 'No'
        """).fetchall())
        names = " ".join(rows.keys())
        assert "Goyal" in names, f"Goyal missing from Feb 2023 dissenters: {rows}"
        assert "Varma" in names, f"Varma missing from Feb 2023 dissenters: {rows}"


if __name__ == "__main__":
    unittest.main()
