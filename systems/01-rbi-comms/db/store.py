import sqlite3
from typing import Optional

from db.schema import DB_PATH


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class DocumentStore:
    @staticmethod
    def _with_legacy_aliases(row: sqlite3.Row | dict) -> dict:
        data = dict(row)
        data["net_score"] = data.get("stance_score")
        data["tone_label"] = data.get("stance_label")
        data["policy_bias"] = data.get("forward_guidance")
        return data

    def _document_payload(self, record: dict) -> dict:
        doc_id = record["doc_id"]
        published_at = record["published_at"]
        series_key = (
            record.get("series_key")
            or record.get("meeting_key")
            or record.get("document_type")
            or doc_id
        )
        content_hash = record.get("content_hash") or f"{doc_id}:{published_at}"

        return {
            "doc_id": doc_id,
            "series_key": series_key,
            "meeting_key": record.get("meeting_key"),
            "published_at": published_at,
            "document_type": record["document_type"],
            "title": record["title"],
            "speaker": record.get("speaker"),
            "url": record["url"],
            "source": record.get("source") or "RBI",
            "summary": record.get("summary"),
            "full_text": record["full_text"],
            "hawkish_score": record.get("hawkish_score", 0) or 0,
            "dovish_score": record.get("dovish_score", 0) or 0,
            "inflation_mentions": record.get("inflation_mentions", 0) or 0,
            "growth_mentions": record.get("growth_mentions", 0) or 0,
            "liquidity_mentions": record.get("liquidity_mentions", 0) or 0,
            "content_hash": content_hash,
            "stance_score": record.get("stance_score")
            if record.get("stance_score") is not None
            else record.get("net_score", 0),
            "stance_label": record.get("stance_label")
            or record.get("tone_label")
            or "neutral",
            "growth_assessment": record.get("growth_assessment"),
            "inflation_assessment": record.get("inflation_assessment"),
            "risk_balance": record.get("risk_balance"),
            "liquidity_stance": record.get("liquidity_stance"),
            "forward_guidance": record.get("forward_guidance")
            or record.get("policy_bias"),
            "new_focus_terms_json": record.get("new_focus_terms_json") or "[]",
        }

    def upsert_document(self, record: dict):
        payload = self._document_payload(record)
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO documents (
                    doc_id,
                    series_key,
                    meeting_key,
                    published_at,
                    document_type,
                    title,
                    speaker,
                    url,
                    source,
                    summary,
                    full_text,
                    hawkish_score,
                    dovish_score,
                    inflation_mentions,
                    growth_mentions,
                    liquidity_mentions,
                    content_hash,
                    stance_score,
                    stance_label,
                    growth_assessment,
                    inflation_assessment,
                    risk_balance,
                    liquidity_stance,
                    forward_guidance,
                    new_focus_terms_json
                ) VALUES (
                    :doc_id,
                    :series_key,
                    :meeting_key,
                    :published_at,
                    :document_type,
                    :title,
                    :speaker,
                    :url,
                    :source,
                    :summary,
                    :full_text,
                    :hawkish_score,
                    :dovish_score,
                    :inflation_mentions,
                    :growth_mentions,
                    :liquidity_mentions,
                    :content_hash,
                    :stance_score,
                    :stance_label,
                    :growth_assessment,
                    :inflation_assessment,
                    :risk_balance,
                    :liquidity_stance,
                    :forward_guidance,
                    :new_focus_terms_json
                )
                ON CONFLICT(doc_id) DO UPDATE SET
                    series_key = excluded.series_key,
                    meeting_key = excluded.meeting_key,
                    published_at = excluded.published_at,
                    document_type = excluded.document_type,
                    title = excluded.title,
                    speaker = excluded.speaker,
                    url = excluded.url,
                    source = excluded.source,
                    summary = excluded.summary,
                    full_text = excluded.full_text,
                    hawkish_score = excluded.hawkish_score,
                    dovish_score = excluded.dovish_score,
                    inflation_mentions = excluded.inflation_mentions,
                    growth_mentions = excluded.growth_mentions,
                    liquidity_mentions = excluded.liquidity_mentions,
                    content_hash = excluded.content_hash,
                    stance_score = excluded.stance_score,
                    stance_label = excluded.stance_label,
                    growth_assessment = excluded.growth_assessment,
                    inflation_assessment = excluded.inflation_assessment,
                    risk_balance = excluded.risk_balance,
                    liquidity_stance = excluded.liquidity_stance,
                    forward_guidance = excluded.forward_guidance,
                    new_focus_terms_json = excluded.new_focus_terms_json
                """,
                payload,
            )
            conn.commit()
        finally:
            conn.close()

    def upsert(self, record: dict):
        self.upsert_document(record)

    def get_document(self, doc_id: str) -> Optional[dict]:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT *
                FROM documents
                WHERE doc_id = ?
                LIMIT 1
                """,
                (doc_id,),
            ).fetchone()
            return self._with_legacy_aliases(row) if row else None
        finally:
            conn.close()

    def get_previous_in_series(self, series_key: str, published_at: str) -> Optional[dict]:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT *
                FROM documents
                WHERE series_key = ?
                  AND published_at < ?
                ORDER BY published_at DESC, id DESC
                LIMIT 1
                """,
                (series_key, published_at),
            ).fetchone()
            return self._with_legacy_aliases(row) if row else None
        finally:
            conn.close()

    def get_latest(self) -> Optional[dict]:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT *
                FROM documents
                ORDER BY published_at DESC, created_at DESC
                LIMIT 1
                """
            ).fetchone()
            return self._with_legacy_aliases(row) if row else None
        finally:
            conn.close()

    def list_recent(self, limit: int = 10) -> list[dict]:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT *
                FROM documents
                ORDER BY published_at DESC, created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [self._with_legacy_aliases(row) for row in rows]
        finally:
            conn.close()

    def tone_history(self, limit: int = 12) -> list[dict]:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT *
                FROM documents
                ORDER BY published_at DESC, created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            history = [self._with_legacy_aliases(row) for row in rows]
            return list(reversed(history))
        finally:
            conn.close()

    def count(self) -> int:
        conn = _connect()
        try:
            return conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        finally:
            conn.close()


CommunicationStore = DocumentStore


class MPCDecisionStore:
    """Time-series store of structured MPC decisions (one row per meeting)."""

    def upsert(self, record: dict) -> None:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO mpc_decisions (
                    meeting_date, doc_id, repo_rate, repo_rate_change_bps,
                    vote_for, vote_against, stance_label, stance_phrase,
                    cpi_projection_curr_fy, cpi_projection_curr_value,
                    gdp_projection_curr_fy, gdp_projection_curr_value,
                    dissenting_members
                ) VALUES (
                    :meeting_date, :doc_id, :repo_rate, :repo_rate_change_bps,
                    :vote_for, :vote_against, :stance_label, :stance_phrase,
                    :cpi_projection_curr_fy, :cpi_projection_curr_value,
                    :gdp_projection_curr_fy, :gdp_projection_curr_value,
                    :dissenting_members
                )
                ON CONFLICT(meeting_date) DO UPDATE SET
                    doc_id = excluded.doc_id,
                    repo_rate = excluded.repo_rate,
                    repo_rate_change_bps = excluded.repo_rate_change_bps,
                    vote_for = excluded.vote_for,
                    vote_against = excluded.vote_against,
                    stance_label = excluded.stance_label,
                    stance_phrase = excluded.stance_phrase,
                    cpi_projection_curr_fy = excluded.cpi_projection_curr_fy,
                    cpi_projection_curr_value = excluded.cpi_projection_curr_value,
                    gdp_projection_curr_fy = excluded.gdp_projection_curr_fy,
                    gdp_projection_curr_value = excluded.gdp_projection_curr_value,
                    dissenting_members = excluded.dissenting_members
                """,
                {
                    "meeting_date":             record["meeting_date"],
                    "doc_id":                   record["doc_id"],
                    "repo_rate":                record["repo_rate"],
                    "repo_rate_change_bps":     record.get("repo_rate_change_bps", 0) or 0,
                    "vote_for":                 record.get("vote_for"),
                    "vote_against":             record.get("vote_against"),
                    "stance_label":             record.get("stance_label") or "neutral",
                    "stance_phrase":            record.get("stance_phrase"),
                    "cpi_projection_curr_fy":   record.get("cpi_projection_curr_fy"),
                    "cpi_projection_curr_value": record.get("cpi_projection_curr_value"),
                    "gdp_projection_curr_fy":   record.get("gdp_projection_curr_fy"),
                    "gdp_projection_curr_value": record.get("gdp_projection_curr_value"),
                    "dissenting_members":       record.get("dissenting_members"),
                },
            )
            conn.commit()
        finally:
            conn.close()

    def get_history(self, limit: int = 24) -> list[dict]:
        """Return decisions in chronological order (oldest first), most recent N."""
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM mpc_decisions ORDER BY meeting_date DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return list(reversed([dict(r) for r in rows]))
        finally:
            conn.close()

    def get_latest(self) -> Optional[dict]:
        history = self.get_history(limit=1)
        return history[-1] if history else None

    def get_previous(self, meeting_date: str) -> Optional[dict]:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT * FROM mpc_decisions
                WHERE meeting_date < ?
                ORDER BY meeting_date DESC LIMIT 1
                """,
                (meeting_date,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def count(self) -> int:
        conn = _connect()
        try:
            return conn.execute("SELECT COUNT(*) FROM mpc_decisions").fetchone()[0]
        finally:
            conn.close()


class BriefStore:
    def save(self, doc_id: str, brief_text: str, model: str | None = None):
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO auto_briefs (
                    meeting_key,
                    current_doc_id,
                    previous_doc_id,
                    growth_change,
                    inflation_change,
                    risk_balance_change,
                    liquidity_change,
                    guidance_change,
                    new_focus_terms_json,
                    stance_score,
                    stance_label,
                    brief_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    doc_id,
                    None,
                    "unchanged",
                    "unchanged",
                    "unchanged",
                    "unchanged",
                    "unchanged",
                    "[]",
                    0,
                    "neutral",
                    brief_text,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_latest(self, doc_id: str) -> Optional[dict]:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT *
                FROM auto_briefs
                WHERE current_doc_id = ?
                ORDER BY generated_at DESC
                LIMIT 1
                """,
                (doc_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
