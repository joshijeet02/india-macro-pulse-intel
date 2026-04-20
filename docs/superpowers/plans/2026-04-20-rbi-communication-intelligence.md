# RBI Communication Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `systems/01-rbi-comms/` from a seeded demo into a live RBI communication intelligence system that ingests real RBI policy documents, scores tone shifts, stores comparable history, and produces analyst-ready reads.

**Architecture:** Keep the existing single-system Python + Streamlit + SQLite pattern used by `systems/02-macro-pulse`, but add a deterministic ingestion pipeline. RBI list pages and linked documents will be fetched into normalized records, scored by a richer signal engine, compared against prior documents in the same series, and surfaced in a decision-grade dashboard with optional Claude synthesis.

**Tech Stack:** Python 3, Streamlit, SQLite, requests, BeautifulSoup4, pypdf2/pdfplumber, unittest, Anthropic API

---

## File Structure

### Existing files to modify

- `systems/01-rbi-comms/app.py`
  Bootstraps the app and wires the new ingestion + document detail views.
- `systems/01-rbi-comms/db/schema.py`
  Expands the schema to support fetch metadata, series keys, and document deltas.
- `systems/01-rbi-comms/db/store.py`
  Adds query paths for ingestion status, previous-document lookup, filters, and saved briefs.
- `systems/01-rbi-comms/engine/signal_engine.py`
  Upgrades the phrase counter into a richer scoring engine with stance-change output.
- `systems/01-rbi-comms/ai/brief.py`
  Teaches the LLM prompt to use tone-change and document metadata.
- `systems/01-rbi-comms/seed/sample_data.py`
  Seeds the richer schema and keeps the system usable without live data.

### Files to create

- `systems/01-rbi-comms/scrapers/__init__.py`
  Package marker for scrapers.
- `systems/01-rbi-comms/scrapers/rbi_sources.py`
  Source registry describing statements, minutes, and speeches.
- `systems/01-rbi-comms/scrapers/rbi_index.py`
  Fetches RBI list pages and extracts candidate document metadata.
- `systems/01-rbi-comms/scrapers/rbi_document.py`
  Fetches HTML/PDF documents and returns normalized text.
- `systems/01-rbi-comms/engine/change_tracker.py`
  Compares a document against the previous item in its series and classifies stance change.
- `systems/01-rbi-comms/seed/backfill.py`
  Orchestrates source discovery, parsing, scoring, change detection, and DB upserts.
- `systems/01-rbi-comms/ui/ingestion_view.py`
  Adds backfill controls, source health, and latest refresh state.
- `systems/01-rbi-comms/ui/document_view.py`
  Shows a selected document, metadata, stance shift, and AI brief.
- `systems/01-rbi-comms/tests/test_scrapers.py`
  Verifies list-page parsing and HTML/PDF extraction.
- `systems/01-rbi-comms/tests/test_change_tracker.py`
  Verifies stance-shift detection.

### Existing tests to modify

- `systems/01-rbi-comms/tests/test_schema.py`
  Covers new schema tables/columns.
- `systems/01-rbi-comms/tests/test_store.py`
  Covers enriched persistence behavior.
- `systems/01-rbi-comms/tests/test_signal_engine.py`
  Covers stronger scoring and theme extraction.

---

### Task 1: Expand The Data Model For Real RBI Documents

**Files:**
- Modify: `systems/01-rbi-comms/db/schema.py`
- Modify: `systems/01-rbi-comms/db/store.py`
- Modify: `systems/01-rbi-comms/tests/test_schema.py`
- Modify: `systems/01-rbi-comms/tests/test_store.py`

- [ ] **Step 1: Write the failing schema tests**

```python
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

        self.assertIn("communications", tables)
        self.assertIn("generated_briefs", tables)

    def test_communications_table_has_live_ingestion_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_db = Path(tmpdir) / "test.db"
            with mock.patch("db.schema.DB_PATH", test_db):
                init_db()

            conn = sqlite3.connect(test_db)
            try:
                rows = conn.execute("PRAGMA table_info(communications)").fetchall()
                columns = {row[1] for row in rows}
            finally:
                conn.close()

        self.assertIn("series_key", columns)
        self.assertIn("content_hash", columns)
        self.assertIn("previous_doc_id", columns)
        self.assertIn("change_label", columns)
        self.assertIn("fetched_at", columns)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_schema.py -v`

Expected: FAIL because the new columns do not exist yet.

- [ ] **Step 3: Write the minimal schema implementation**

```python
SCHEMA = """
CREATE TABLE IF NOT EXISTS communications (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id              TEXT NOT NULL UNIQUE,
    series_key          TEXT NOT NULL,
    published_at        TEXT NOT NULL,
    document_type       TEXT NOT NULL,
    title               TEXT NOT NULL,
    speaker             TEXT,
    url                 TEXT,
    source              TEXT NOT NULL DEFAULT 'RBI',
    summary             TEXT,
    full_text           TEXT NOT NULL,
    content_hash        TEXT NOT NULL,
    previous_doc_id     TEXT,
    hawkish_score       INTEGER NOT NULL DEFAULT 0,
    dovish_score        INTEGER NOT NULL DEFAULT 0,
    net_score           INTEGER NOT NULL DEFAULT 0,
    tone_label          TEXT NOT NULL DEFAULT 'neutral',
    policy_bias         TEXT NOT NULL DEFAULT 'on hold',
    change_label        TEXT NOT NULL DEFAULT 'first-observation',
    change_summary      TEXT,
    inflation_mentions  INTEGER NOT NULL DEFAULT 0,
    growth_mentions     INTEGER NOT NULL DEFAULT 0,
    liquidity_mentions  INTEGER NOT NULL DEFAULT 0,
    fetched_at          TEXT DEFAULT (datetime('now')),
    created_at          TEXT DEFAULT (datetime('now'))
);
"""
```

- [ ] **Step 4: Add failing store tests for previous-document lookup and filtered listing**

```python
def test_communication_store_returns_previous_in_series(self):
    store = CommunicationStore()
    base_record = {
        "document_type": "Monetary Policy Statement",
        "title": "Resolution of the Monetary Policy Committee",
        "speaker": "MPC",
        "url": "https://rbi.example/mpc",
        "source": "RBI",
        "summary": "Policy statement",
        "full_text": "Inflation risks remain elevated.",
        "content_hash": "hash-1",
        "previous_doc_id": None,
        "hawkish_score": 2,
        "dovish_score": 0,
        "net_score": 2,
        "tone_label": "hawkish",
        "policy_bias": "tightening bias",
        "change_label": "first-observation",
        "change_summary": "First stored document in this RBI series.",
        "inflation_mentions": 1,
        "growth_mentions": 0,
        "liquidity_mentions": 0,
    }
    store.upsert({**base_record, "doc_id": "mpc-1", "series_key": "mpc-statement", "published_at": "2025-02-07"})
    store.upsert({**base_record, "doc_id": "mpc-2", "content_hash": "hash-2", "series_key": "mpc-statement", "published_at": "2025-04-09"})

    previous = store.get_previous_in_series("mpc-statement", "2025-04-09")

    self.assertIsNotNone(previous)
    self.assertEqual(previous["doc_id"], "mpc-1")

def test_communication_store_filters_by_type(self):
    store = CommunicationStore()
    shared = {
        "speaker": "Governor",
        "url": "https://rbi.example/doc",
        "source": "RBI",
        "summary": "Document summary",
        "full_text": "Growth is steady and inflation is easing.",
        "content_hash": "hash",
        "previous_doc_id": None,
        "hawkish_score": 0,
        "dovish_score": 1,
        "net_score": -1,
        "tone_label": "neutral",
        "policy_bias": "on hold",
        "change_label": "first-observation",
        "change_summary": "First stored document in this RBI series.",
        "inflation_mentions": 1,
        "growth_mentions": 1,
        "liquidity_mentions": 0,
    }
    store.upsert({**shared, "doc_id": "speech-1", "series_key": "governor-speech", "published_at": "2025-03-18", "document_type": "Governor Speech", "title": "Speech on inflation"})
    store.upsert({**shared, "doc_id": "minutes-1", "series_key": "mpc-minutes", "published_at": "2025-02-21", "document_type": "MPC Minutes", "title": "Minutes February 2025", "content_hash": "hash-2"})
    rows = store.list_recent(limit=10, document_type="Governor Speech")
    self.assertEqual([row["document_type"] for row in rows], ["Governor Speech"])
```

- [ ] **Step 5: Run test to verify it fails**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_store.py -v`

Expected: FAIL because `series_key`, `get_previous_in_series`, and filtered listing do not exist.

- [ ] **Step 6: Write the minimal store implementation**

```python
class CommunicationStore:
    def list_recent(self, limit: int = 10, document_type: str | None = None) -> list[dict]:
        where_clause = ""
        params: list[object] = []
        if document_type:
            where_clause = "WHERE document_type = ?"
            params.append(document_type)
        query = f"""
            SELECT *
            FROM communications
            {where_clause}
            ORDER BY published_at DESC, created_at DESC
            LIMIT ?
        """
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_previous_in_series(self, series_key: str, published_at: str) -> Optional[dict]:
        row = conn.execute(
            """
            SELECT *
            FROM communications
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
git commit -m "feat: expand rbi comms data model"
```

### Task 2: Add RBI Source Discovery And Document Parsing

**Files:**
- Create: `systems/01-rbi-comms/scrapers/__init__.py`
- Create: `systems/01-rbi-comms/scrapers/rbi_sources.py`
- Create: `systems/01-rbi-comms/scrapers/rbi_index.py`
- Create: `systems/01-rbi-comms/scrapers/rbi_document.py`
- Create: `systems/01-rbi-comms/tests/test_scrapers.py`

- [ ] **Step 1: Write the failing scraper tests**

```python
class RbiScraperTests(unittest.TestCase):
    def test_extract_documents_from_index_html(self):
        html = """
        <ul>
          <li><a href="/Scripts/BS_PressReleaseDisplay.aspx?prid=60001">Monetary Policy Statement, April 9, 2025</a></li>
          <li><a href="/Scripts/BS_SpeechesView.aspx?Id=1500">Governor's speech on inflation dynamics</a></li>
        </ul>
        """
        source = {"series_key": "mpc-statement", "document_type": "Monetary Policy Statement", "base_url": "https://rbi.org.in"}

        records = extract_index_records(html, source)

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["url"], "https://rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=60001")

    def test_extract_text_from_html_document(self):
        html = "<html><body><h1>Speech</h1><p>Inflation risks remain elevated.</p></body></html>"
        parsed = extract_text_from_html(html)
        self.assertIn("Inflation risks remain elevated.", parsed)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_scrapers.py -v`

Expected: FAIL because the scraper modules do not exist.

- [ ] **Step 3: Create the source registry**

```python
RBI_SOURCES = [
    {
        "series_key": "mpc-statement",
        "document_type": "Monetary Policy Statement",
        "index_url": "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=all",
        "base_url": "https://www.rbi.org.in",
        "match_terms": ("monetary policy", "resolution of the monetary policy committee"),
    },
    {
        "series_key": "mpc-minutes",
        "document_type": "MPC Minutes",
        "index_url": "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx",
        "base_url": "https://www.rbi.org.in",
        "match_terms": ("minutes of the monetary policy committee",),
    },
    {
        "series_key": "governor-speech",
        "document_type": "Governor Speech",
        "index_url": "https://www.rbi.org.in/Scripts/BS_SpeechesView.aspx",
        "base_url": "https://www.rbi.org.in",
        "match_terms": ("speech",),
    },
]
```

- [ ] **Step 4: Implement index parsing and HTML/PDF extraction**

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

def extract_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return "\n".join(chunk for chunk in soup.stripped_strings if chunk)
```

- [ ] **Step 5: Add a thin live-fetch wrapper**

```python
def fetch_url(url: str, timeout: int = 30) -> str:
    response = requests.get(url, timeout=timeout, headers={"User-Agent": "india-econ-intelligence/1.0"})
    response.raise_for_status()
    return response.text

def parse_document_response(url: str, content: bytes, content_type: str) -> str:
    if "pdf" in content_type or url.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(content))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    return extract_text_from_html(content.decode("utf-8", errors="ignore"))
```

- [ ] **Step 6: Run the scraper tests to verify they pass**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_scrapers.py -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add systems/01-rbi-comms/scrapers/__init__.py systems/01-rbi-comms/scrapers/rbi_sources.py systems/01-rbi-comms/scrapers/rbi_index.py systems/01-rbi-comms/scrapers/rbi_document.py systems/01-rbi-comms/tests/test_scrapers.py
git commit -m "feat: add rbi source discovery and parsing"
```

### Task 3: Add Tone-Shift Detection And Richer Signal Output

**Files:**
- Modify: `systems/01-rbi-comms/engine/signal_engine.py`
- Create: `systems/01-rbi-comms/engine/change_tracker.py`
- Create: `systems/01-rbi-comms/tests/test_change_tracker.py`
- Modify: `systems/01-rbi-comms/tests/test_signal_engine.py`

- [ ] **Step 1: Write the failing signal and change-tracker tests**

```python
def test_analyze_communication_returns_top_themes(self):
    result = analyze_communication(
        "Inflation risks remain elevated while liquidity conditions tighten and growth slows."
    )
    self.assertIn("inflation", result.top_themes)
    self.assertIn("liquidity", result.top_themes)

def test_classify_change_detects_hawkish_shift(self):
    previous = {"net_score": 0, "tone_label": "neutral", "policy_bias": "on hold"}
    current = {"net_score": 3, "tone_label": "hawkish", "policy_bias": "tightening bias"}

    change = classify_change(previous, current)

    self.assertEqual(change.change_label, "hawkish-shift")
    self.assertIn("tightening bias", change.change_summary)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_signal_engine.py systems/01-rbi-comms/tests/test_change_tracker.py -v`

Expected: FAIL because `top_themes` and `classify_change` do not exist.

- [ ] **Step 3: Extend the signal model**

```python
@dataclass
class CommunicationSignal:
    hawkish_score: int
    dovish_score: int
    net_score: int
    tone_label: str
    policy_bias: str
    inflation_mentions: int
    growth_mentions: int
    liquidity_mentions: int
    top_themes: list[str]

def analyze_communication(text: str) -> CommunicationSignal:
    normalized = " ".join(text.lower().split())
    hawkish_score = _count_terms(normalized, HAWKISH_PHRASES)
    dovish_score = _count_terms(normalized, DOVISH_PHRASES)
    net_score = hawkish_score - dovish_score
    if net_score >= 2:
        tone_label = "hawkish"
        policy_bias = "tightening bias"
    elif net_score <= -2:
        tone_label = "dovish"
        policy_bias = "easing bias"
    else:
        tone_label = "neutral"
        policy_bias = "on hold"
    theme_counts = {
        "inflation": _count_terms(normalized, INFLATION_TERMS),
        "growth": _count_terms(normalized, GROWTH_TERMS),
        "liquidity": _count_terms(normalized, LIQUIDITY_TERMS),
    }
    top_themes = [name for name, count in sorted(theme_counts.items(), key=lambda item: item[1], reverse=True) if count > 0]
    return CommunicationSignal(
        hawkish_score=hawkish_score,
        dovish_score=dovish_score,
        net_score=net_score,
        tone_label=tone_label,
        policy_bias=policy_bias,
        inflation_mentions=theme_counts["inflation"],
        growth_mentions=theme_counts["growth"],
        liquidity_mentions=theme_counts["liquidity"],
        top_themes=top_themes[:3],
    )
```

- [ ] **Step 4: Implement stance-change classification**

```python
@dataclass
class ChangeSignal:
    change_label: str
    change_summary: str

def classify_change(previous: dict | None, current: dict) -> ChangeSignal:
    if previous is None:
        return ChangeSignal("first-observation", "First stored document in this RBI series.")
    delta = current["net_score"] - previous["net_score"]
    if delta >= 2:
        return ChangeSignal("hawkish-shift", f"Communication shifted more hawkish versus the prior document and now points to {current['policy_bias']}.")
    if delta <= -2:
        return ChangeSignal("dovish-shift", f"Communication shifted more dovish versus the prior document and now points to {current['policy_bias']}.")
    return ChangeSignal("steady-stance", f"Communication stayed broadly consistent with the prior {previous['tone_label']} read.")
```

- [ ] **Step 5: Run the updated engine tests to verify they pass**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_signal_engine.py systems/01-rbi-comms/tests/test_change_tracker.py -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add systems/01-rbi-comms/engine/signal_engine.py systems/01-rbi-comms/engine/change_tracker.py systems/01-rbi-comms/tests/test_signal_engine.py systems/01-rbi-comms/tests/test_change_tracker.py
git commit -m "feat: add rbi stance change detection"
```

### Task 4: Build The Backfill Pipeline And Wire The Dashboard

**Files:**
- Create: `systems/01-rbi-comms/seed/backfill.py`
- Create: `systems/01-rbi-comms/ui/ingestion_view.py`
- Create: `systems/01-rbi-comms/ui/document_view.py`
- Modify: `systems/01-rbi-comms/ui/overview_view.py`
- Modify: `systems/01-rbi-comms/app.py`
- Modify: `systems/01-rbi-comms/seed/sample_data.py`
- Modify: `systems/01-rbi-comms/db/store.py`

- [ ] **Step 1: Write the failing backfill and view integration tests**

```python
def test_backfill_source_returns_upserted_documents(self):
    with mock.patch("seed.backfill.fetch_source_records", return_value=[sample_record]):
        results = backfill_source(limit=5)
    self.assertEqual(results["inserted"], 1)

def test_document_store_exposes_document_feed_filters(self):
    rows = store.list_recent(limit=10, document_type="MPC Minutes")
    self.assertEqual(rows[0]["document_type"], "MPC Minutes")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_store.py -v`

Expected: FAIL because the backfill entrypoint and richer listing workflow do not exist.

- [ ] **Step 3: Implement the backfill pipeline**

```python
def backfill_source(limit: int = 20) -> dict[str, int]:
    store = CommunicationStore()
    inserted = 0
    for source in RBI_SOURCES:
        for record in fetch_source_records(source)[:limit]:
            text = fetch_document_text(record["url"])
            signal = analyze_communication(text).to_record()
            previous = store.get_previous_in_series(record["series_key"], record["published_at"])
            change = classify_change(previous, signal). __dict__
            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            store.upsert({**record, "full_text": text, "content_hash": content_hash, "previous_doc_id": previous["doc_id"] if previous else None, **signal, **change})
            inserted += 1
    return {"inserted": inserted}
```

- [ ] **Step 4: Add the ingestion and detail views**

```python
def render_ingestion_view():
    st.subheader("RBI Source Refresh")
    if st.button("Run Backfill", use_container_width=True):
        results = backfill_source(limit=20)
        st.success(f"Inserted or updated {results['inserted']} RBI documents.")

def render_document_detail():
    options = communications.list_recent(limit=50)
    selected = st.selectbox("Select document", options, format_func=lambda row: f"{row['published_at']} · {row['title']}")
    st.markdown(f"**Change:** {selected['change_label']}")
    st.write(selected.get("change_summary") or "No change summary available.")
```

- [ ] **Step 5: Wire the new tabs in the app shell**

```python
tab_overview, tab_document, tab_ingestion = st.tabs(["Overview", "Document Detail", "Ingestion"])

with tab_overview:
    render_overview()

with tab_document:
    render_document_detail()

with tab_ingestion:
    render_ingestion_view()
```

- [ ] **Step 6: Run the focused tests to verify they pass**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_store.py -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add systems/01-rbi-comms/seed/backfill.py systems/01-rbi-comms/ui/ingestion_view.py systems/01-rbi-comms/ui/document_view.py systems/01-rbi-comms/ui/overview_view.py systems/01-rbi-comms/app.py systems/01-rbi-comms/seed/sample_data.py systems/01-rbi-comms/db/store.py
git commit -m "feat: add rbi backfill flow and dashboard tabs"
```

### Task 5: Upgrade AI Briefs And Verify End-To-End Behavior

**Files:**
- Modify: `systems/01-rbi-comms/ai/brief.py`
- Modify: `systems/01-rbi-comms/tests/test_store.py`
- Modify: `systems/01-rbi-comms/tests/test_signal_engine.py`
- Modify: `systems/01-rbi-comms/tests/test_scrapers.py`

- [ ] **Step 1: Write the failing brief-prompt test**

```python
def test_generate_communication_brief_uses_change_context(self):
    document = {
        "title": "Resolution",
        "document_type": "Monetary Policy Statement",
        "published_at": "2025-04-09",
        "tone_label": "hawkish",
        "policy_bias": "tightening bias",
        "change_label": "hawkish-shift",
        "change_summary": "Communication shifted more hawkish than the prior statement.",
        "inflation_mentions": 3,
        "growth_mentions": 1,
        "liquidity_mentions": 2,
        "full_text": "Inflation risks remain elevated.",
    }
    prompt = build_brief_prompt(document)
    self.assertIn("hawkish-shift", prompt)
    self.assertIn("Communication shifted more hawkish", prompt)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest systems/01-rbi-comms/tests/test_signal_engine.py -v`

Expected: FAIL because `build_brief_prompt` does not exist.

- [ ] **Step 3: Refactor the brief module to expose a deterministic prompt builder**

```python
def build_brief_prompt(document: dict) -> str:
    return f"""RBI Communication Intelligence

TITLE: {document['title']}
TYPE: {document['document_type']}
DATE: {document['published_at']}
TONE: {document['tone_label']}
POLICY BIAS: {document['policy_bias']}
CHANGE LABEL: {document.get('change_label', 'unknown')}
CHANGE SUMMARY: {document.get('change_summary', 'No prior comparison')}
THEMES: inflation={document['inflation_mentions']}, growth={document['growth_mentions']}, liquidity={document['liquidity_mentions']}

TEXT:
{document['full_text'][:4000]}
"""

def generate_communication_brief(document: dict) -> str:
    prompt = build_brief_prompt(document)
    message = _client().messages.create(
        model="claude-opus-4-7",
        max_tokens=500,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text
```

- [ ] **Step 4: Run the full System 1 test suite**

Run: `python3 -m unittest discover -s systems/01-rbi-comms/tests -v`

Expected: PASS

- [ ] **Step 5: Run syntax verification for the app and new modules**

Run: `python3 -m py_compile systems/01-rbi-comms/app.py systems/01-rbi-comms/ai/brief.py systems/01-rbi-comms/db/schema.py systems/01-rbi-comms/db/store.py systems/01-rbi-comms/engine/signal_engine.py systems/01-rbi-comms/engine/change_tracker.py systems/01-rbi-comms/scrapers/rbi_sources.py systems/01-rbi-comms/scrapers/rbi_index.py systems/01-rbi-comms/scrapers/rbi_document.py systems/01-rbi-comms/seed/backfill.py systems/01-rbi-comms/ui/overview_view.py systems/01-rbi-comms/ui/document_view.py systems/01-rbi-comms/ui/ingestion_view.py`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add systems/01-rbi-comms/ai/brief.py systems/01-rbi-comms/tests/test_store.py systems/01-rbi-comms/tests/test_signal_engine.py systems/01-rbi-comms/tests/test_scrapers.py
git commit -m "feat: finalize rbi communication intelligence workflow"
```

## Self-Review

### Spec coverage

- Live RBI ingestion: covered by Task 2 and Task 4.
- Durable storage for comparable document history: covered by Task 1.
- Tone scoring plus stance-shift detection: covered by Task 3.
- Analyst dashboard and document drill-down: covered by Task 4.
- AI synthesis with policy-change context: covered by Task 5.

### Placeholder scan

- No `TODO`, `TBD`, or "implement later" placeholders remain.
- Every task includes concrete files, commands, and code.
- Commands use `unittest` and `py_compile`, matching the current environment.

### Type consistency

- `series_key`, `content_hash`, `previous_doc_id`, `change_label`, and `change_summary` are defined in Task 1 before later tasks use them.
- `top_themes` is added in Task 3 before the brief layer references richer signal metadata.
- `build_brief_prompt` is introduced before `generate_communication_brief` uses it.
