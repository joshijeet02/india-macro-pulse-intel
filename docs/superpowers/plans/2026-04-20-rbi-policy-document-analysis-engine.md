# RBI Policy Document Analysis Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand `systems/01-rbi-comms/` into a corpus-scale RBI communications intelligence engine with queryable retrieval, citation-backed answers, and automatic meeting-to-meeting MPC briefing.

**Architecture:** Build on the existing `systems/01-rbi-comms/` foundation instead of creating a separate numbered system folder. Ingest public RBI PDFs and HTML pages into a normalized corpus store, split them into attributed chunks backed by SQLite FTS5 retrieval, layer an economist-specific five-dimension framework on top, and use that framework both for auto-briefing and query-time synthesis with citations.

**Tech Stack:** Python 3, Streamlit, SQLite + FTS5, requests, BeautifulSoup4, PyPDF2, pandas, unittest, Anthropic API

---

## File Structure

### Existing files to modify

- `systems/01-rbi-comms/app.py`
  Replace the simple one-tab shell with query, briefing, corpus, and ingestion modes.
- `systems/01-rbi-comms/db/schema.py`
  Expand from a single `communications` table into corpus documents, chunks, and saved briefings.
- `systems/01-rbi-comms/db/store.py`
  Add persistence helpers for documents, chunks, retrieval, previous-meeting lookup, and brief storage.
- `systems/01-rbi-comms/seed/sample_data.py`
  Seed realistic multi-document corpus data so the system still works without live RBI fetches.
- `systems/01-rbi-comms/ai/brief.py`
  Refactor to support both auto-brief generation and query answering with citations.
- `systems/01-rbi-comms/tests/test_schema.py`
  Cover the richer schema.
- `systems/01-rbi-comms/tests/test_store.py`
  Cover document/chunk persistence and lookup semantics.

### Files to create

- `systems/01-rbi-comms/scrapers/__init__.py`
  Package marker for RBI corpus ingestion.
- `systems/01-rbi-comms/scrapers/rbi_sources.py`
  Registry of RBI communication sources and series metadata.
- `systems/01-rbi-comms/scrapers/rbi_index.py`
  Parse RBI listing pages into candidate documents.
- `systems/01-rbi-comms/scrapers/rbi_document.py`
  Download and normalize HTML/PDF content from RBI links.
- `systems/01-rbi-comms/engine/chunker.py`
  Split long documents into attributed retrieval chunks.
- `systems/01-rbi-comms/engine/framework.py`
  Extract the five economic dimensions, stance score, and new variables in focus.
- `systems/01-rbi-comms/engine/retrieval.py`
  Run lexical retrieval over chunked corpus and format citations.
- `systems/01-rbi-comms/engine/briefing.py`
  Compare current and prior meeting documents and create the structured “what changed” brief.
- `systems/01-rbi-comms/seed/backfill_corpus.py`
  Orchestrate source discovery, parsing, chunking, framework extraction, and storage.
- `systems/01-rbi-comms/ui/query_view.py`
  Query mode UI with answer box and citations.
- `systems/01-rbi-comms/ui/briefing_view.py`
  Auto-briefing mode UI with five-dimension comparison and stance trend chart.
- `systems/01-rbi-comms/ui/corpus_view.py`
  Corpus explorer UI for documents, metadata, and raw text.
- `systems/01-rbi-comms/ui/ingestion_view.py`
  Manual refresh and ingestion status UI.
- `systems/01-rbi-comms/tests/test_scrapers.py`
  Tests RBI list-page and document parsing.
- `systems/01-rbi-comms/tests/test_framework.py`
  Tests the economist-specific five-dimension framework and stance scoring.
- `systems/01-rbi-comms/tests/test_retrieval.py`
  Tests chunking, search, and citation formatting.
- `systems/01-rbi-comms/tests/test_briefing.py`
  Tests “what changed” comparison logic.

---

### Task 1: Reshape System 1 Into A Corpus Database

**Files:**
- Modify: `systems/01-rbi-comms/db/schema.py`
- Modify: `systems/01-rbi-comms/db/store.py`
- Modify: `systems/01-rbi-comms/tests/test_schema.py`
- Modify: `systems/01-rbi-comms/tests/test_store.py`

- [ ] **Step 1: Write the failing schema tests**

```python
class InitDbTests(unittest.TestCase):
    def test_init_db_creates_corpus_tables(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db = Path(tmpdir) / "test.db"
            with mock.patch("db.schema.DB_PATH", test_db):
                init_db()

            conn = sqlite3.connect(test_db)
            try:
                tables = {
                    row[0]
                    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                }
            finally:
                conn.close()

        self.assertIn("documents", tables)
        self.assertIn("document_chunks", tables)
        self.assertIn("auto_briefs", tables)

    def test_init_db_creates_chunk_fts_table(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db = Path(tmpdir) / "test.db"
            with mock.patch("db.schema.DB_PATH", test_db):
                init_db()

            conn = sqlite3.connect(test_db)
            try:
                tables = {
                    row[0]
                    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                }
            finally:
                conn.close()

        self.assertIn("document_chunks_fts", tables)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_schema.py -v`

Expected: FAIL because the current schema only creates `communications` and `generated_briefs`.

- [ ] **Step 3: Write the minimal schema implementation**

```python
SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id                TEXT NOT NULL UNIQUE,
    series_key            TEXT NOT NULL,
    meeting_key           TEXT,
    published_at          TEXT NOT NULL,
    document_type         TEXT NOT NULL,
    title                 TEXT NOT NULL,
    speaker               TEXT,
    url                   TEXT NOT NULL,
    source                TEXT NOT NULL DEFAULT 'RBI',
    summary               TEXT,
    full_text             TEXT NOT NULL,
    content_hash          TEXT NOT NULL,
    stance_score          REAL NOT NULL DEFAULT 0,
    stance_label          TEXT NOT NULL DEFAULT 'neutral',
    growth_assessment     TEXT,
    inflation_assessment  TEXT,
    risk_balance          TEXT,
    liquidity_stance      TEXT,
    forward_guidance      TEXT,
    new_focus_terms_json  TEXT NOT NULL DEFAULT '[]',
    fetched_at            TEXT DEFAULT (datetime('now')),
    created_at            TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS document_chunks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id          TEXT NOT NULL UNIQUE,
    doc_id            TEXT NOT NULL,
    chunk_index       INTEGER NOT NULL,
    section_label     TEXT,
    page_label        TEXT,
    tokens_estimate   INTEGER NOT NULL,
    text              TEXT NOT NULL,
    citations_json    TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts USING fts5(
    chunk_id,
    doc_id,
    text,
    content='document_chunks',
    content_rowid='id'
);

CREATE TABLE IF NOT EXISTS auto_briefs (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_key            TEXT NOT NULL,
    current_doc_id         TEXT NOT NULL,
    previous_doc_id        TEXT,
    growth_change          TEXT NOT NULL,
    inflation_change       TEXT NOT NULL,
    risk_balance_change    TEXT NOT NULL,
    liquidity_change       TEXT NOT NULL,
    guidance_change        TEXT NOT NULL,
    new_focus_terms_json   TEXT NOT NULL DEFAULT '[]',
    stance_score           REAL NOT NULL,
    stance_label           TEXT NOT NULL,
    brief_text             TEXT,
    generated_at           TEXT DEFAULT (datetime('now'))
);
"""
```

- [ ] **Step 4: Write the failing store tests**

```python
class StoreTests(unittest.TestCase):
    def test_document_store_saves_and_reads_documents(self):
        store = DocumentStore()
        store.upsert_document(
            {
                "doc_id": "mpc-statement-2025-04",
                "series_key": "mpc-statement",
                "meeting_key": "2025-04",
                "published_at": "2025-04-09",
                "document_type": "Monetary Policy Statement",
                "title": "Resolution of the Monetary Policy Committee",
                "speaker": "MPC",
                "url": "https://rbi.example/statement-2025-04.pdf",
                "source": "RBI",
                "summary": "April policy statement.",
                "full_text": "Inflation risks remain elevated while growth holds up.",
                "content_hash": "hash-1",
                "stance_score": 1.5,
                "stance_label": "hawkish",
                "growth_assessment": "resilient",
                "inflation_assessment": "sticky",
                "risk_balance": "upside inflation risks",
                "liquidity_stance": "tight",
                "forward_guidance": "vigilant",
                "new_focus_terms_json": "[\"food inflation\"]",
            }
        )

        row = store.get_document("mpc-statement-2025-04")

        self.assertIsNotNone(row)
        self.assertEqual(row["meeting_key"], "2025-04")
        self.assertEqual(row["stance_label"], "hawkish")

    def test_document_store_returns_previous_meeting_document(self):
        store = DocumentStore()
        store.upsert_document({**base_doc, "doc_id": "mpc-statement-2025-02", "meeting_key": "2025-02", "published_at": "2025-02-07"})
        store.upsert_document({**base_doc, "doc_id": "mpc-statement-2025-04", "meeting_key": "2025-04", "published_at": "2025-04-09"})

        previous = store.get_previous_in_series("mpc-statement", "2025-04-09")

        self.assertIsNotNone(previous)
        self.assertEqual(previous["doc_id"], "mpc-statement-2025-02")
```

- [ ] **Step 5: Run test to verify it fails**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_store.py -v`

Expected: FAIL because `DocumentStore` and the new document schema do not exist.

- [ ] **Step 6: Write the minimal store implementation**

```python
class DocumentStore:
    def upsert_document(self, record: dict):
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO documents (
                    doc_id, series_key, meeting_key, published_at, document_type, title, speaker,
                    url, source, summary, full_text, content_hash, stance_score, stance_label,
                    growth_assessment, inflation_assessment, risk_balance, liquidity_stance,
                    forward_guidance, new_focus_terms_json
                ) VALUES (
                    :doc_id, :series_key, :meeting_key, :published_at, :document_type, :title, :speaker,
                    :url, :source, :summary, :full_text, :content_hash, :stance_score, :stance_label,
                    :growth_assessment, :inflation_assessment, :risk_balance, :liquidity_stance,
                    :forward_guidance, :new_focus_terms_json
                )
                ON CONFLICT(doc_id) DO UPDATE SET
                    published_at = excluded.published_at,
                    summary = excluded.summary,
                    full_text = excluded.full_text,
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
                record,
            )
            conn.commit()
        finally:
            conn.close()

    def get_document(self, doc_id: str) -> Optional[dict]:
        row = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
        return dict(row) if row else None

    def get_previous_in_series(self, series_key: str, published_at: str) -> Optional[dict]:
        row = conn.execute(
            """
            SELECT * FROM documents
            WHERE series_key = ? AND published_at < ?
            ORDER BY published_at DESC
            LIMIT 1
            """,
            (series_key, published_at),
        ).fetchone()
        return dict(row) if row else None
```

- [ ] **Step 7: Run the updated tests to verify they pass**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_schema.py systems/01-rbi-comms/tests/test_store.py -v`

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add systems/01-rbi-comms/db/schema.py systems/01-rbi-comms/db/store.py systems/01-rbi-comms/tests/test_schema.py systems/01-rbi-comms/tests/test_store.py
git commit -m "feat: add rbi corpus schema"
```

### Task 2: Ingest The RBI Corpus From Public Document Sources

**Files:**
- Create: `systems/01-rbi-comms/scrapers/__init__.py`
- Create: `systems/01-rbi-comms/scrapers/rbi_sources.py`
- Create: `systems/01-rbi-comms/scrapers/rbi_index.py`
- Create: `systems/01-rbi-comms/scrapers/rbi_document.py`
- Create: `systems/01-rbi-comms/seed/backfill_corpus.py`
- Create: `systems/01-rbi-comms/tests/test_scrapers.py`

- [ ] **Step 1: Write the failing scraper tests**

```python
class RbiScraperTests(unittest.TestCase):
    def test_extract_index_records_filters_supported_links(self):
        html = """
        <ul>
          <li><a href="/Scripts/BS_PressReleaseDisplay.aspx?prid=60001">Resolution of the Monetary Policy Committee April 9, 2025</a></li>
          <li><a href="/Scripts/BS_SpeechesView.aspx?Id=1501">Speech by Governor on monetary policy transmission</a></li>
          <li><a href="/scripts/unused.aspx">Banking ombudsman notice</a></li>
        </ul>
        """
        source = {
            "series_key": "mpc-statement",
            "document_type": "Monetary Policy Statement",
            "base_url": "https://www.rbi.org.in",
            "match_terms": ("resolution of the monetary policy committee", "monetary policy"),
        }

        records = extract_index_records(html, source)

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["url"], "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=60001")

    def test_extract_text_from_pdf_bytes(self):
        pdf_bytes = build_minimal_pdf_bytes("Inflation risks remain elevated.")
        text = extract_text_from_pdf_bytes(pdf_bytes)
        self.assertIn("Inflation risks remain elevated.", text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_scrapers.py -v`

Expected: FAIL because the scraper modules do not exist yet.

- [ ] **Step 3: Create the RBI source registry**

```python
RBI_SOURCES = [
    {
        "series_key": "mpc-minutes",
        "document_type": "MPC Minutes",
        "index_url": "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx",
        "base_url": "https://www.rbi.org.in",
        "match_terms": ("minutes of the monetary policy committee",),
    },
    {
        "series_key": "mpc-statement",
        "document_type": "Monetary Policy Statement",
        "index_url": "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=all",
        "base_url": "https://www.rbi.org.in",
        "match_terms": ("resolution of the monetary policy committee", "monetary policy statement"),
    },
    {
        "series_key": "governor-speech",
        "document_type": "Governor Speech",
        "index_url": "https://www.rbi.org.in/Scripts/BS_SpeechesView.aspx",
        "base_url": "https://www.rbi.org.in",
        "match_terms": ("speech",),
    },
    {
        "series_key": "mpr",
        "document_type": "Monetary Policy Report",
        "index_url": "https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=950",
        "base_url": "https://www.rbi.org.in",
        "match_terms": ("monetary policy report",),
    },
]
```

- [ ] **Step 4: Implement HTML index parsing and document extraction**

```python
def extract_index_records(html: str, source: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for link in soup.find_all("a", href=True):
        title = " ".join(link.get_text(" ", strip=True).split())
        lowered = title.lower()
        if not any(term in lowered for term in source["match_terms"]):
            continue
        records.append(
            {
                "series_key": source["series_key"],
                "document_type": source["document_type"],
                "title": title,
                "url": urljoin(source["base_url"], link["href"]),
            }
        )
    return records

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
```

- [ ] **Step 5: Add the corpus backfill orchestrator**

```python
def backfill_corpus(limit_per_source: int = 50) -> dict[str, int]:
    store = DocumentStore()
    inserted = 0
    for source in RBI_SOURCES:
        index_html = fetch_text(source["index_url"])
        for record in extract_index_records(index_html, source)[:limit_per_source]:
            content = fetch_bytes(record["url"])
            text = extract_document_text(record["url"], content)
            store.upsert_document({**record, "meeting_key": infer_meeting_key(record["title"], record["document_type"]), "published_at": infer_published_date(record["title"]), "summary": first_nonempty_paragraph(text), "full_text": text, "content_hash": sha256_text(text), "stance_score": 0.0, "stance_label": "neutral", "growth_assessment": "", "inflation_assessment": "", "risk_balance": "", "liquidity_stance": "", "forward_guidance": "", "new_focus_terms_json": "[]"})
            inserted += 1
    return {"inserted": inserted}
```

- [ ] **Step 6: Run the scraper tests to verify they pass**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_scrapers.py -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add systems/01-rbi-comms/scrapers/__init__.py systems/01-rbi-comms/scrapers/rbi_sources.py systems/01-rbi-comms/scrapers/rbi_index.py systems/01-rbi-comms/scrapers/rbi_document.py systems/01-rbi-comms/seed/backfill_corpus.py systems/01-rbi-comms/tests/test_scrapers.py
git commit -m "feat: ingest rbi document corpus"
```

### Task 3: Encode The Economist Five-Dimension Framework

**Files:**
- Create: `systems/01-rbi-comms/engine/framework.py`
- Create: `systems/01-rbi-comms/tests/test_framework.py`
- Modify: `systems/01-rbi-comms/seed/sample_data.py`
- Modify: `systems/01-rbi-comms/db/store.py`

- [ ] **Step 1: Write the failing framework tests**

```python
class FrameworkTests(unittest.TestCase):
    def test_assess_document_extracts_five_dimensions(self):
        text = (
            "Growth is gaining traction, but inflation remains above target. "
            "Liquidity conditions will remain calibrated while policy stays vigilant."
        )

        assessment = assess_document(text)

        self.assertEqual(assessment.growth_assessment, "growth-resilient")
        self.assertEqual(assessment.inflation_assessment, "inflation-sticky")
        self.assertEqual(assessment.liquidity_stance, "calibrated-tight")
        self.assertEqual(assessment.forward_guidance, "vigilant")

    def test_assess_document_finds_new_focus_terms(self):
        previous_text = "Inflation and growth were the main focus."
        current_text = "Food inflation, transmission lags, and global volatility need attention."

        assessment = assess_document(current_text, previous_text=previous_text)

        self.assertIn("food inflation", assessment.new_focus_terms)
        self.assertIn("transmission lags", assessment.new_focus_terms)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_framework.py -v`

Expected: FAIL because `assess_document` does not exist.

- [ ] **Step 3: Implement the framework dataclass and rule sets**

```python
@dataclass
class FrameworkAssessment:
    growth_assessment: str
    inflation_assessment: str
    risk_balance: str
    liquidity_stance: str
    forward_guidance: str
    stance_score: float
    stance_label: str
    new_focus_terms: list[str]

GROWTH_RULES = {
    "growth-resilient": ("growth is gaining traction", "resilient domestic activity", "investment demand remains strong"),
    "growth-softening": ("growth needs support", "slowdown", "weak demand"),
}

INFLATION_RULES = {
    "inflation-sticky": ("inflation remains above target", "inflation risks remain elevated", "price pressures persist"),
    "inflation-easing": ("disinflation is broad-based", "inflation is easing", "price pressures soften"),
}
```

- [ ] **Step 4: Write the minimal framework implementation**

```python
def assess_document(text: str, previous_text: str | None = None) -> FrameworkAssessment:
    normalized = " ".join(text.lower().split())
    growth_assessment = first_matching_label(normalized, GROWTH_RULES, fallback="growth-balanced")
    inflation_assessment = first_matching_label(normalized, INFLATION_RULES, fallback="inflation-balanced")
    risk_balance = infer_risk_balance(normalized)
    liquidity_stance = infer_liquidity_stance(normalized)
    forward_guidance = infer_forward_guidance(normalized)
    stance_score = compute_stance_score(growth_assessment, inflation_assessment, risk_balance, liquidity_stance, forward_guidance)
    stance_label = "hawkish" if stance_score >= 1.0 else "dovish" if stance_score <= -1.0 else "neutral"
    new_focus_terms = extract_new_focus_terms(normalized, previous_text or "")
    return FrameworkAssessment(
        growth_assessment=growth_assessment,
        inflation_assessment=inflation_assessment,
        risk_balance=risk_balance,
        liquidity_stance=liquidity_stance,
        forward_guidance=forward_guidance,
        stance_score=stance_score,
        stance_label=stance_label,
        new_focus_terms=new_focus_terms,
    )
```

- [ ] **Step 5: Persist the framework output when seeding**

```python
assessment = assess_document(document["full_text"], previous_text=previous_text)
store.upsert_document(
    {
        **document,
        "stance_score": assessment.stance_score,
        "stance_label": assessment.stance_label,
        "growth_assessment": assessment.growth_assessment,
        "inflation_assessment": assessment.inflation_assessment,
        "risk_balance": assessment.risk_balance,
        "liquidity_stance": assessment.liquidity_stance,
        "forward_guidance": assessment.forward_guidance,
        "new_focus_terms_json": json.dumps(assessment.new_focus_terms),
    }
)
```

- [ ] **Step 6: Run the framework tests to verify they pass**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_framework.py -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add systems/01-rbi-comms/engine/framework.py systems/01-rbi-comms/tests/test_framework.py systems/01-rbi-comms/seed/sample_data.py systems/01-rbi-comms/db/store.py
git commit -m "feat: encode rbi policy analysis framework"
```

### Task 4: Build Retrieval, Chunking, And Query Mode

**Files:**
- Create: `systems/01-rbi-comms/engine/chunker.py`
- Create: `systems/01-rbi-comms/engine/retrieval.py`
- Create: `systems/01-rbi-comms/ui/query_view.py`
- Modify: `systems/01-rbi-comms/ai/brief.py`
- Modify: `systems/01-rbi-comms/db/store.py`
- Create: `systems/01-rbi-comms/tests/test_retrieval.py`

- [ ] **Step 1: Write the failing retrieval tests**

```python
class RetrievalTests(unittest.TestCase):
    def test_chunk_document_preserves_source_metadata(self):
        chunks = chunk_document(
            doc_id="mpc-minutes-2025-04",
            text="Paragraph one.\n\nParagraph two mentions transmission lags.\n\nParagraph three mentions food inflation.",
            max_chars=60,
        )

        self.assertEqual(chunks[0]["doc_id"], "mpc-minutes-2025-04")
        self.assertEqual(chunks[0]["chunk_index"], 0)
        self.assertIn("Paragraph one.", chunks[0]["text"])

    def test_format_cited_answer_context_includes_chunk_ids(self):
        context = build_context_window(
            [
                {
                    "chunk_id": "mpc-minutes-2025-04::1",
                    "doc_id": "mpc-minutes-2025-04",
                    "title": "Minutes April 2025",
                    "published_at": "2025-04-23",
                    "text": "Transmission lags remain relevant.",
                }
            ]
        )

        self.assertIn("[mpc-minutes-2025-04::1]", context)
        self.assertIn("Transmission lags remain relevant.", context)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_retrieval.py -v`

Expected: FAIL because chunking and retrieval helpers do not exist.

- [ ] **Step 3: Implement the chunker**

```python
def chunk_document(doc_id: str, text: str, max_chars: int = 1400) -> list[dict]:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    chunks: list[dict] = []
    buffer = ""
    chunk_index = 0
    for paragraph in paragraphs:
        candidate = paragraph if not buffer else f"{buffer}\n\n{paragraph}"
        if len(candidate) <= max_chars:
            buffer = candidate
            continue
        chunks.append(
            {
                "chunk_id": f"{doc_id}::{chunk_index}",
                "doc_id": doc_id,
                "chunk_index": chunk_index,
                "section_label": None,
                "page_label": None,
                "tokens_estimate": max(1, len(buffer) // 4),
                "text": buffer,
                "citations_json": json.dumps([f"{doc_id}::{chunk_index}"]),
            }
        )
        chunk_index += 1
        buffer = paragraph
    if buffer:
        chunks.append(
            {
                "chunk_id": f"{doc_id}::{chunk_index}",
                "doc_id": doc_id,
                "chunk_index": chunk_index,
                "section_label": None,
                "page_label": None,
                "tokens_estimate": max(1, len(buffer) // 4),
                "text": buffer,
                "citations_json": json.dumps([f"{doc_id}::{chunk_index}"]),
            }
        )
    return chunks
```

- [ ] **Step 4: Implement retrieval and answer-context formatting**

```python
def build_context_window(rows: list[dict]) -> str:
    blocks = []
    for row in rows:
        blocks.append(
            f"[{row['chunk_id']}] {row['title']} ({row['published_at']})\n{row['text']}"
        )
    return "\n\n".join(blocks)

def search_chunks(conn: sqlite3.Connection, query: str, limit: int = 8) -> list[dict]:
    rows = conn.execute(
        """
        SELECT c.chunk_id, c.doc_id, c.text, d.title, d.published_at
        FROM document_chunks_fts f
        JOIN document_chunks c ON c.id = f.rowid
        JOIN documents d ON d.doc_id = c.doc_id
        WHERE document_chunks_fts MATCH ?
        ORDER BY bm25(document_chunks_fts)
        LIMIT ?
        """,
        (query, limit),
    ).fetchall()
    return [dict(row) for row in rows]
```

- [ ] **Step 5: Refactor the AI module for query answering**

```python
def build_query_prompt(question: str, context_window: str) -> str:
    return f"""You are answering a question about RBI communications.

Question:
{question}

Use only the cited context below.
Every factual claim must cite chunk IDs in square brackets.

Context:
{context_window}
"""

def answer_query(question: str, context_rows: list[dict]) -> str:
    prompt = build_query_prompt(question, build_context_window(context_rows))
    message = _client().messages.create(
        model="claude-opus-4-7",
        max_tokens=700,
        system="You are a senior India rates economist. Be concise, analytical, and citation-heavy.",
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text
```

- [ ] **Step 6: Add the query mode UI**

```python
def render_query_view():
    question = st.text_input("Ask about RBI communications")
    if not question:
        return
    rows = query_store.search(question, limit=8)
    if not rows:
        st.info("No supporting RBI passages found.")
        return
    st.write(answer_query(question, rows))
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
```

- [ ] **Step 7: Run the retrieval tests to verify they pass**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_retrieval.py -v`

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add systems/01-rbi-comms/engine/chunker.py systems/01-rbi-comms/engine/retrieval.py systems/01-rbi-comms/ui/query_view.py systems/01-rbi-comms/ai/brief.py systems/01-rbi-comms/db/store.py systems/01-rbi-comms/tests/test_retrieval.py
git commit -m "feat: add rbi query mode"
```

### Task 5: Add Automatic MPC Briefing And Decision-Grade UI

**Files:**
- Create: `systems/01-rbi-comms/engine/briefing.py`
- Create: `systems/01-rbi-comms/ui/briefing_view.py`
- Create: `systems/01-rbi-comms/ui/corpus_view.py`
- Create: `systems/01-rbi-comms/ui/ingestion_view.py`
- Modify: `systems/01-rbi-comms/app.py`
- Modify: `systems/01-rbi-comms/ai/brief.py`
- Create: `systems/01-rbi-comms/tests/test_briefing.py`

- [ ] **Step 1: Write the failing briefing tests**

```python
class BriefingTests(unittest.TestCase):
    def test_compare_meeting_documents_returns_five_dimension_changes(self):
        previous = {
            "growth_assessment": "growth-balanced",
            "inflation_assessment": "inflation-sticky",
            "risk_balance": "balanced-risks",
            "liquidity_stance": "calibrated-tight",
            "forward_guidance": "vigilant",
            "stance_score": 1.0,
            "stance_label": "hawkish",
            "new_focus_terms_json": "[\"food inflation\"]",
        }
        current = {
            "growth_assessment": "growth-softening",
            "inflation_assessment": "inflation-easing",
            "risk_balance": "two-sided-risks",
            "liquidity_stance": "neutral-liquidity",
            "forward_guidance": "data-dependent",
            "stance_score": -0.5,
            "stance_label": "neutral",
            "new_focus_terms_json": "[\"transmission lags\", \"global volatility\"]",
        }

        brief = compare_meeting_documents(previous, current)

        self.assertIn("growth-softening", brief["growth_change"])
        self.assertIn("inflation-easing", brief["inflation_change"])
        self.assertIn("transmission lags", brief["new_focus_terms"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_briefing.py -v`

Expected: FAIL because `compare_meeting_documents` does not exist.

- [ ] **Step 3: Implement the briefing engine**

```python
def compare_meeting_documents(previous: dict | None, current: dict) -> dict:
    if previous is None:
        return {
            "growth_change": f"First observation: {current['growth_assessment']}",
            "inflation_change": f"First observation: {current['inflation_assessment']}",
            "risk_balance_change": f"First observation: {current['risk_balance']}",
            "liquidity_change": f"First observation: {current['liquidity_stance']}",
            "guidance_change": f"First observation: {current['forward_guidance']}",
            "new_focus_terms": json.loads(current["new_focus_terms_json"]),
            "stance_score": current["stance_score"],
            "stance_label": current["stance_label"],
        }
    return {
        "growth_change": f"{previous['growth_assessment']} -> {current['growth_assessment']}",
        "inflation_change": f"{previous['inflation_assessment']} -> {current['inflation_assessment']}",
        "risk_balance_change": f"{previous['risk_balance']} -> {current['risk_balance']}",
        "liquidity_change": f"{previous['liquidity_stance']} -> {current['liquidity_stance']}",
        "guidance_change": f"{previous['forward_guidance']} -> {current['forward_guidance']}",
        "new_focus_terms": sorted(set(json.loads(current["new_focus_terms_json"])) - set(json.loads(previous["new_focus_terms_json"]))),
        "stance_score": current["stance_score"],
        "stance_label": current["stance_label"],
    }
```

- [ ] **Step 4: Add UI modes for briefing, corpus, and ingestion**

```python
tab_query, tab_briefing, tab_corpus, tab_ingestion = st.tabs(
    ["Query Mode", "Auto-Briefing Mode", "Corpus", "Ingestion"]
)

with tab_query:
    render_query_view()

with tab_briefing:
    render_briefing_view()

with tab_corpus:
    render_corpus_view()

with tab_ingestion:
    render_ingestion_view()
```

- [ ] **Step 5: Refactor the brief AI prompt for auto-briefing**

```python
def build_auto_brief_prompt(current_doc: dict, briefing: dict) -> str:
    return f"""Write an RBI MPC meeting brief.

Current document: {current_doc['title']} ({current_doc['published_at']})
Growth change: {briefing['growth_change']}
Inflation change: {briefing['inflation_change']}
Risk balance change: {briefing['risk_balance_change']}
Liquidity change: {briefing['liquidity_change']}
Guidance change: {briefing['guidance_change']}
New focus terms: {', '.join(briefing['new_focus_terms']) or 'none'}
Stance score: {briefing['stance_score']} ({briefing['stance_label']})
"""
```

- [ ] **Step 6: Run the briefing tests to verify they pass**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_briefing.py -v`

Expected: PASS

- [ ] **Step 7: Run the full System 2 test suite**

Run: `python3 -m unittest discover -s systems/01-rbi-comms/tests -v`

Expected: PASS

- [ ] **Step 8: Run syntax verification**

Run: `python3 -m py_compile systems/01-rbi-comms/app.py systems/01-rbi-comms/db/schema.py systems/01-rbi-comms/db/store.py systems/01-rbi-comms/engine/framework.py systems/01-rbi-comms/engine/chunker.py systems/01-rbi-comms/engine/retrieval.py systems/01-rbi-comms/engine/briefing.py systems/01-rbi-comms/scrapers/rbi_sources.py systems/01-rbi-comms/scrapers/rbi_index.py systems/01-rbi-comms/scrapers/rbi_document.py systems/01-rbi-comms/seed/backfill_corpus.py systems/01-rbi-comms/ui/query_view.py systems/01-rbi-comms/ui/briefing_view.py systems/01-rbi-comms/ui/corpus_view.py systems/01-rbi-comms/ui/ingestion_view.py systems/01-rbi-comms/ai/brief.py`

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add systems/01-rbi-comms/app.py systems/01-rbi-comms/engine/briefing.py systems/01-rbi-comms/ui/briefing_view.py systems/01-rbi-comms/ui/corpus_view.py systems/01-rbi-comms/ui/ingestion_view.py systems/01-rbi-comms/ai/brief.py systems/01-rbi-comms/tests/test_briefing.py
git commit -m "feat: add rbi auto briefing engine"
```

## Self-Review

### Spec coverage

- Corpus-wide RBI ingestion across statements, minutes, speeches, and reports: covered by Task 2.
- Query mode with cited synthesized answers: covered by Task 4.
- Auto-briefing mode on new MPC releases: covered by Task 5.
- Five-dimension economist framework and contextualization: covered by Task 3 and Task 5.
- Hawkish/dovish trend scoring and new variables in focus: covered by Task 3 and Task 5.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Every task includes explicit file paths, commands, and code snippets.
- Commands use `unittest` and `py_compile`, matching the current environment.

### Type consistency

- `documents`, `document_chunks`, and `auto_briefs` are defined in Task 1 before later tasks use them.
- `DocumentStore` methods are defined before the backfill, retrieval, and briefing tasks call them.
- `FrameworkAssessment` fields align with the persisted document columns and briefing comparisons.
