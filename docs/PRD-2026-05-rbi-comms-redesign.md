# RBI Communication Intelligence — Redesign PRD
**Version:** 1.0 · **Date:** 2026-05-02 · **Author:** Jeet (with Claude as PM)
**Engineering owner:** Claude + subagents (executing in `systems/01-rbi-comms/`)
**Companion app:** [`systems/02-macro-pulse/`](systems/02-macro-pulse/) (deployed)

---

## 1. Problem statement

The existing app at `systems/01-rbi-comms/` is a stub: 3 hand-typed synthetic documents from early 2025, a 6-phrase keyword counter for sentiment, no scrapers, no deployment. The schema is rich (FTS5, document chunks, structured stance fields, auto-briefs) but unused.

Meanwhile, **real India rates analysts have a brutal workflow on MPC day**: the rate decision drops at 10:00 IST, the formal Resolution at ~10:15, the Governor's press conference at 12:00. Sell-side analysts have ~90 minutes to publish a client note that captures (a) what changed in the stance, (b) the vote split, (c) projection revisions, (d) forward-guidance language shifts. Their current toolkit:

- **Bloomberg / Reuters terminals** — fast facts, no analytical layer, $20K/seat/year
- **RBI's own website** — clunky PDFs, no comparison tools, server gets hammered on MPC day
- **CEIC / Haver** — paid, quantitative-only, no qualitative
- **Consumer LLMs** — general-purpose, no India context, hallucinate vote splits

**The gap is a structured, fast, free, AI-augmented MPC-day workbench specifically built for the Indian rates-watching workflow.** That's the product.

---

## 2. Target user

**Primary persona — Aanya, sell-side India rates analyst at a mid-tier broker.** Tracks RBI for clients. Needs to publish a 600-word note within 90 minutes of MPC. Doesn't have a Bloomberg terminal at her desk (her firm has 4 for 30 analysts). Currently does the diff manually in Word. Salary is good but firm won't pay $20K for her access. Audience for our app, ranked:

| Persona | Workflow | Priority |
|---|---|---|
| **Sell-side analyst (Aanya)** | Publish post-MPC client note in <2h | **Tier 1** — design for her |
| Buy-side macro PM | Form independent view, cross-check sell-side | Tier 2 — adjacent |
| Financial journalist (Reuters, Mint, BS) | Quick fact-check, quotable lines | Tier 2 |
| Policy researcher (think tank) | Long-form analysis, time series | Tier 3 |
| Student / curious | Educational read | Tier 3 |

If Tier 1 opens this app at 10:00 IST on MPC day instead of going to Bloomberg first, **we have won**. If Tier 1 doesn't, this is a portfolio piece, not a product.

---

## 3. Goals

| # | Goal | Measure | Target |
|---|---|---|---|
| G1 | Halve the time-to-first-draft for an MPC-day analyst note | Stopwatch test: from 10:15 IST to a structured "what changed" view | <60 seconds for ingestion + diff to render |
| G2 | Capture every MPC Resolution and Minutes autonomously, going forward | Lag between RBI publication and app reflecting it | <12 hours for Resolution, <48h for Minutes |
| G3 | Quantify policy stance with a defensible numeric score, not 6-keyword counts | Backtest stance score against ground-truth labels (manually labelled 12 historical MPCs) | ≥80% directional agreement |
| G4 | Cross-reference RBI's qualitative read with the live CPI/IIP from the sister app | One-click navigation between latest CPI print and most recent MPC's CPI projection | Working bidirectional links |
| G5 | Ship the AI Brief feature so an analyst can paste the output (with edits) into a client note | Time-to-Brief from "Generate" click | <15 seconds end-to-end |

---

## 4. Non-goals

| # | Non-goal | Why excluded |
|---|---|---|
| N1 | **Not** building a real-time bond price feed or G-Sec yield overlay | Belongs in a separate fixed-income system; would need a paid data source. Can mock with EOD data in Phase 2. |
| N2 | **Not** ingesting every RBI publication (FSR, Bulletin, Annual Report, Press Releases on regulatory matters) | Volume too high; signal-to-noise is poor for the analyst's MPC-day workflow. MPC + Speeches = 80% of value at 20% of effort. |
| N3 | **Not** doing member-level minutes analysis in v1 | Minutes ingestion + chunking by member + comparative tracking is a 1-week feature. Phase 2. |
| N4 | **Not** building a notification / email / RSS subscription system | Streamlit Cloud doesn't give us a worker for this. Phase 2 with a separate cron-driven sender, or a simple RSS file the user pulls. |
| N5 | **Not** generalizing to other central banks (Fed, ECB, BoE) | One-bank focus is the wedge. Multi-bank would dilute and make the UI generic. |
| N6 | **Not** building user accounts, paywalls, or tracking | This is open infrastructure. Adds zero value for v1; adds complexity. |

---

## 5. The wedge — what makes this different from Bloomberg

Three things, in order of importance:

### 5.1 Semantic stance tracking (not word counts)

Bloomberg shows the statement text. We show **what changed in which dimension**. Every Resolution gets parsed into:
- **Stance phrase** ("withdrawal of accommodation" / "neutral" / "accommodative")
- **Forward guidance markers** (presence/absence of "data-dependent", "calibrated", "appropriate")
- **Growth assessment language** ("resilient", "moderating", "uneven")
- **Inflation assessment language** ("aligning", "elevated", "easing")
- **Liquidity stance** ("surplus", "deficit", "appropriate")

Each dimension is tracked as a time series. **Diffs between meetings highlight transitions** — the moment "withdrawal of accommodation" first appears (or disappears) is the single most-watched language event on MPC day. We surface it as a labelled event on a timeline.

### 5.2 Cross-system integration with macro-pulse

RBI says: "Inflation is projected at 3.7% in FY27 with risks broadly balanced."
Macro-pulse (live data): "Latest CPI print is 3.40% (Mar 2026)."

The app shows these **side-by-side** with a one-click deep-link. When a CPI print surprises versus RBI's last projection, the macro-pulse app shows a "RBI projection: X% — actual: Y%, surprise +Zpp" badge.

Neither Bloomberg nor RBI's website connects projections to actuals. This is unique.

### 5.3 Free + AI-augmented + open

The Brief generator (already plumbed via `ai/brief.py`) lets an analyst convert structured signals into a 3-paragraph analyst note in seconds. Anyone — students, journalists, freelance researchers, sell-side analysts without terminal access — can use it. **No paywall, no auth, no terminal license**.

---

## 6. User stories

### Tier 1: MPC-day workflow (Aanya)

```
US-1   As an analyst on MPC day,
       I want to see the new Resolution diff vs the immediately-prior MPC
       within 60 seconds of clicking "Refresh",
       so that I can identify what's new without re-reading 3 pages of boilerplate.

US-2   As an analyst,
       I want a one-line "stance" headline at the top
       (e.g., "STANCE: NEUTRAL → still NEUTRAL · Repo: 6.25% (unchanged) · Vote: 6-0"),
       so that I can capture the key facts in my note's lede.

US-3   As an analyst,
       I want a tagged list of language transitions across 6 dimensions
       (stance / forward guidance / growth / inflation / liquidity / risks),
       so that I know which paragraph to quote and which transition to interpret.

US-4   As an analyst,
       I want to click "Generate Brief" and get a 3-paragraph analyst note,
       so that I have a draft to edit rather than a blank page.

US-5   As an analyst,
       I want the projections table (CPI / GDP) shown alongside the prior MPC's projections,
       so that I can quickly write "the central bank lowered its FY27 CPI projection by 20bp".
```

### Tier 1: cross-reference

```
US-6   As an analyst on a CPI release day,
       I want to see RBI's most recent inflation projection alongside the just-released print,
       so that I can write "this is X bp above/below RBI's projected path".

US-7   As an analyst on an IIP release day,
       I want to see whether RBI's growth language has softened/hardened since the last weak/strong print,
       so that I can interpret the data through RBI's reaction function.
```

### Tier 2: inter-meeting

```
US-8   As an analyst between MPCs,
       I want a feed of recent Governor + DG speeches with sentiment scores,
       so that I can detect a shift in the policy walk before the next MPC.

US-9   As an analyst,
       I want to search the historical RBI corpus for a specific phrase or theme,
       so that I can find precedents ("when has RBI used 'pause' before?")
```

### Tier 3: educational

```
US-10  As a student of monetary economics,
       I want a Plain English mode that re-explains MPC jargon,
       so that I can follow the analysis without three textbooks open.

US-11  As a journalist,
       I want a "quotable lines" panel that surfaces the 3-4 most newsworthy sentences,
       so that I can write my Reuters wire in 5 minutes.
```

---

## 7. Requirements

### P0 — must-have for v1 (one focused engineering session)

#### P0.1 — Real RBI Resolution ingestion
- **Source**: RBI press release page. Investigate first whether `rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx` is server-rendered (likely yes — it's old ASP.NET, unlike MOSPI's SPA) OR find an RSS feed. **First action of execution: spike a curl + grep to confirm.** If JS-rendered, use Playwright (already in deps).
- **Coverage**: Last 8 MPC Resolutions backfilled (covers Feb 2024 through Apr 2026). Going forward, autonomous via cron.
- **Schema**: Use existing `documents` table. Populate `document_type='MPC Resolution'`, fill all currently-zero fields (stance_score, stance_label, growth_assessment, inflation_assessment, risk_balance, liquidity_stance, forward_guidance) using the new stance engine (P0.3).
- **Acceptance**: `data/rbi_communications.json` has 8+ Resolution entries with full text, source URL, and a populated stance struct.

#### P0.2 — `mpc_decisions` structured table
New SQLite table for the time-series numeric layer:
```sql
CREATE TABLE mpc_decisions (
    meeting_date         TEXT PRIMARY KEY,
    doc_id               TEXT NOT NULL,
    repo_rate            REAL NOT NULL,
    repo_rate_change_bps INTEGER NOT NULL,
    vote_for             INTEGER NOT NULL,
    vote_against         INTEGER NOT NULL,
    stance_label         TEXT NOT NULL,
    stance_phrase        TEXT NOT NULL,
    cpi_projection_curr  REAL,
    cpi_projection_next  REAL,
    gdp_projection_curr  REAL,
    gdp_projection_next  REAL,
    dissenting_members   TEXT,  -- JSON array of names
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);
```
Extracted from each Resolution by a dedicated parser.
- **Acceptance**: 8 rows for the last 8 MPCs, all key fields parsed, repo rate matches RBI's actual calendar.

#### P0.3 — Structured stance engine (replace keyword counter)
Replace [`engine/signal_engine.py`](systems/01-rbi-comms/engine/signal_engine.py) with a **lexicon-based engine** that tags phrases by dimension.

```python
DIMENSIONS = {
    "stance": [
        ("withdrawal of accommodation", -1.0),
        ("calibrated withdrawal of accommodation", -0.7),
        ("neutral", 0.0),
        ("remain neutral", 0.0),
        ("remain accommodative", +1.0),
        ...
    ],
    "forward_guidance": [
        ("data-dependent", "data_dependent"),
        ("calibrated", "calibrated"),
        ("appropriate", "appropriate"),
        ("nimble", "nimble"),
        ...
    ],
    "growth_assessment": [
        ("resilient", +1.0),
        ("robust", +1.0),
        ("moderating", -0.5),
        ("uneven", -0.7),
        ...
    ],
    "inflation_assessment": [...],
    "liquidity_stance": [...],
    "risk_balance": [...],
}
```

Per dimension, output:
- A score (weighted average of matched phrases, -1 to +1)
- A label (most-recently-emphasized category)
- A list of matched phrases with locations (for transparency)

The 8 historical Resolutions become the **calibration corpus**. Manually label each one (which we know in hindsight) and tune the lexicon until directional agreement ≥80% (G3).
- **Acceptance**: `analyze_communication(text)` returns a structured dict with all 6 dimensions, scores, labels, and a list of evidence phrases. Backtest passes on 8 historical Resolutions.

#### P0.4 — Statement diff view
New module `engine/diff_engine.py`. Given two `documents.full_text` blobs:
- Tokenize at sentence level (use a simple punctuation-based splitter; full NLP is overkill here)
- Align paragraphs by topical key (look for paragraph-leading boilerplate: "On the growth front…", "The MPC noted…", "Headline inflation…")
- Per paragraph, compute word-level diff using `difflib.ndiff`
- Render with `+` (added), `-` (removed), `~` (changed) markers, color-coded

**UI**: side-by-side or unified diff toggle. Default to **unified diff** with paragraph headers for scannability.
- **Acceptance**: Given Apr-2026 and Feb-2026 MPC Resolutions, the diff highlights stance phrase changes correctly and is rendered in <500ms.

#### P0.5 — `ui/mpc_view.py` redesign
Replace [`ui/overview_view.py`](systems/01-rbi-comms/ui/overview_view.py) with a new tab structure:

1. **MPC Day Hero** (always-visible top of page):
   - Big repo rate number
   - Vote split badge
   - Stance label (with arrow showing transition: NEUTRAL → NEUTRAL or HAWKISH → NEUTRAL)
   - "Generate Brief" button
   - "Open in macro-pulse" cross-link

2. **Tab: "What Changed"**
   - Tagged language transitions across 6 dimensions
   - Diff view (P0.4)

3. **Tab: "Projections"**
   - CPI + GDP forecasts table, current MPC vs prior 3 MPCs
   - Highlight cells where projection moved >10bp

4. **Tab: "Stance Time Series"**
   - 12-meeting time series of stance score
   - Vote-split trend
   - Repo rate path

5. **Tab: "Document Feed"** (existing, polished)
   - Full archive, with FTS search

**Acceptance**: A first-time user can identify (a) latest decision, (b) what changed, (c) where the stance is heading, in under 30 seconds of landing on the page.

#### P0.6 — Autonomous refresh workflow
`.github/workflows/refresh-rbi.yml`:
- `cron: '0 4-12 * * *'` for the 5 days surrounding any MPC date (calculated from a YAML `mpc_dates` list), `0 4 * * *` daily otherwise. Polls every hour during MPC week.
- `workflow_dispatch` for manual trigger.
- `scripts/refresh_rbi.py` — same exit-code pattern as `refresh_releases.py` (0 new, 1 nochange, 2 fail, 3 partial). Atomic JSON write. GitHub issue on failure.
- **Acceptance**: Workflow runs successfully against fixtures; manual trigger picks up the latest Resolution and pushes to repo.

#### P0.7 — Hardening
- Tests (≥10 new): real-fixture parsing tests, stance engine backtest, diff engine output regression, `mpc_decisions` extractor.
- Streamlit smoke test (boot in <5s, render no errors).
- Atomic JSON writes everywhere (mirroring [`refresh_releases.py:_save_updates`](systems/02-macro-pulse/scripts/refresh_releases.py:65) pattern).

#### P0.8 — Deployment
- Streamlit Cloud config: a separate app at `india-rbi-comms.streamlit.app` (or whatever URL is approved by user).
- README updated.

### P1 — Phase 2 (next session, 1-2 weeks out)

| # | Feature | Why P1 |
|---|---|---|
| P1.1 | **MPC Minutes ingestion + member-level analysis** | Minutes are richer than Resolutions but only ship 14 days post-MPC. Lower MPC-day urgency. |
| P1.2 | **Speech corpus + sentiment** | Inter-meeting workflow (US-8). Speech URLs are different (`/Scripts/BS_SpeechesView.aspx?Id=...`); separate parser. |
| P1.3 | **Cross-reference with macro-pulse** | URL params + a small embed/widget on macro-pulse pulling latest stance. Adds value but not blocking for v1 launch. |
| P1.4 | **Statement archetype classifier** | "This statement reads most like Aug 2024." Trains on the historical corpus. Needs ≥12 meetings of clean data first. |
| P1.5 | **Plain English mode** | Mirror macro-pulse's pattern. Once stance commentary text is in place, this is mechanical. |
| P1.6 | **MPC-day live mode** | Toggleable auto-refresh during the 10:00–10:30 window. Polls scraper aggressively. Adds caching complexity. |
| P1.7 | **AI Brief upgrade** | Add citation requirements, "draft only" disclaimer, structured output (3 paragraphs, exactly). Already plumbed; need prompt eng. |

### P2 — Vision (later, design now to support)

| # | Feature |
|---|---|
| P2.1 | Press conference transcript parser + Q&A digest |
| P2.2 | Bond market reaction overlay (post-MPC G-Sec yield move) |
| P2.3 | Pre-MPC "policy walk" briefing aggregator (auto-runs 7 days before each MPC) |
| P2.4 | Member voting heatmap (after enough meetings ingested) |
| P2.5 | RSS feed export for journalists |
| P2.6 | Cross-CB compare (Fed/ECB/RBI on common axes) |
| P2.7 | Embargo-aware mode (statement is embargoed till 10:00 IST; show countdown) |

---

## 8. Engineering plan (execution-ready)

The eng team should mirror the architecture pattern just shipped in macro-pulse. Concretely:

### 8.1 Files to create

```
systems/01-rbi-comms/
├── scrapers/
│   ├── __init__.py
│   ├── _rbi_api.py          # listing discovery (HTML or RSS)
│   ├── _pdf_extract.py      # mirror macro-pulse pattern
│   ├── rbi_resolution.py    # MPC Resolution scraper + parser
│   └── rbi_speech.py        # P1, scaffold only in v1
├── engine/
│   ├── stance_engine.py     # NEW: replaces signal_engine.py
│   ├── diff_engine.py       # NEW: paragraph-level diff
│   ├── mpc_extractor.py     # NEW: extracts repo rate, vote, projections
│   └── signal_engine.py     # KEEP shim that delegates to stance_engine for backwards compat
├── scripts/
│   ├── __init__.py
│   └── refresh_rbi.py       # mirrors refresh_releases.py
├── seed/
│   ├── historical_data.py   # NEW: replaces sample_data.py
│   └── sample_data.py       # DEPRECATED: shim that calls historical_data
├── ui/
│   ├── mpc_view.py          # NEW: tabbed MPC view (P0.5)
│   └── overview_view.py     # KEEP but reduced — just a redirect / legacy
├── data/
│   ├── rbi_communications.json   # JSON sidecar (committed)
│   └── mpc_calendar.json         # known MPC dates for cron scheduling
├── tests/
│   ├── fixtures/pdf/             # real RBI Resolution PDFs (3-4)
│   ├── test_stance_engine.py
│   ├── test_diff_engine.py
│   ├── test_mpc_extractor.py
│   ├── test_real_rbi_pdfs.py     # integration tests against committed fixtures
│   └── test_seed_merger.py
└── README.md                # rewritten with data-flow diagram
.github/workflows/refresh-rbi.yml
```

### 8.2 Schema migration

Add `mpc_decisions` (P0.2) via `db/schema.py` migration. Existing `documents` schema retained — populate the structured fields that are currently always-zero.

### 8.3 Scraper pattern (P0.1)

Spike first: `curl rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=58128` (latest MPC Apr 2026). If server-rendered HTML with the PDF link discoverable in BS4, use the same pattern as the macro-pulse JSON-API + PDF-fetch flow. If the listing page is JS-rendered, use Playwright (already in deps via macro-pulse — share the binary install).

### 8.4 Stance engine calibration loop (P0.3)

1. Ingest 8 historical Resolutions.
2. Manually label each one with: stance, forward guidance label, growth direction, inflation direction.
3. Run lexicon-based engine.
4. Tune lexicon until ≥80% directional agreement.
5. Commit calibrated lexicon as `engine/stance_lexicon.py` with version comment.
6. Save labels as `tests/fixtures/historical_labels.json` for regression.

### 8.5 Diff engine (P0.4)

```python
# Sketch
def diff_resolutions(prev: str, curr: str) -> list[ParagraphDiff]:
    prev_paras = align_paragraphs(prev)
    curr_paras = align_paragraphs(curr)
    out = []
    for key in sorted(set(prev_paras) | set(curr_paras)):
        p, c = prev_paras.get(key, ""), curr_paras.get(key, "")
        if p == c:
            continue
        out.append(ParagraphDiff(
            section=key,
            sentence_diff=sentence_level_ndiff(p, c),
            stance_terms_added=lexicon_terms(c) - lexicon_terms(p),
            stance_terms_removed=lexicon_terms(p) - lexicon_terms(c),
        ))
    return out
```

Render with markdown + colored spans in Streamlit.

### 8.6 GH workflow (P0.6)

Mirror [`.github/workflows/refresh-data.yml`](.github/workflows/refresh-data.yml) but:
- Cron schedule: hourly during MPC week, daily otherwise. MPC week is calculated from a `data/mpc_calendar.json` list.
- Working directory: `systems/01-rbi-comms`
- Same exit-code semantics (0/1/2/3) and issue-on-failure.

### 8.7 Cross-app integration (P0.4 cross-reference)

URL params:
- macro-pulse → rbi-comms: `india-rbi-comms.streamlit.app/?focus=cpi_projection`
- rbi-comms → macro-pulse: `india-macro-pulse.streamlit.app/?tab=cpi`

In v1, just deep-link buttons. In P1.3, embed cross-data widgets.

---

## 9. Enhancements you wouldn't think to ask for

These are valuable for real economists but would not surface from a builder's perspective alone:

### E1 — Statement archetype classification (vibes engine)
Each MPC has a vibe. Classify the latest statement against historical archetypes:
- **"Pre-cut signal"**: stance softening, growth concern emphasis, inflation language relaxing
- **"Insurance pause"**: neutral stance held, residual inflation concern, growth seen resilient
- **"Hawkish pivot"**: forward guidance hardening, dissent appearing, "vigilance" emphasis
- **"Operational tweak"**: stance unchanged, focus on liquidity/transmission/regulatory

Implementation: cosine similarity between current statement embedding and labelled historical archetypes. Adds analytical leverage Bloomberg cannot match. P1, but design v1 to support.

### E2 — Pre-MPC "policy walk" aggregator
In the 7 days before each MPC, auto-aggregate Governor + DG speeches and produce a "policy walk so far" report: language softening / hardening since last MPC. Buy-side desks pay for this elsewhere (it's a Bloomberg "tracker"-style feature). Free + automated here.

### E3 — Embargo-aware MPC-day mode
RBI Resolutions are embargoed until 10:00 IST. The app should know this:
- Show a countdown
- Disable AI Brief generation until embargo lifts (preventing hallucinated drafts on stale data)
- Auto-refresh the moment embargo lifts

### E4 — "Quote-mining" view for journalists
A dedicated panel that surfaces the 3-4 most newsworthy sentences (highest stance-language density), formatted for direct copy-paste into a wire story with attribution. Reuters / Mint correspondents would actually use this.

### E5 — Member voting heatmap (post-Minutes)
Once Minutes are ingested (P1.1), a 6×N grid: rows = MPC members, columns = meetings, cell color = their stance. Reveals committee dynamics: who moves the consensus, who's a persistent dissenter.

### E6 — Statement-vs-Minutes divergence detector
The Resolution and Minutes (released 2 weeks later) sometimes tell different stories — Resolution language can be more hawkish than the actual member-level discussion. Flagging this divergence is alpha.

---

## 10. Risk register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | RBI changes site structure (e.g., migrates from ASP.NET to a SPA) | High | Daily smoke test in CI runs scraper against last-known-good URL and alerts on schema change. Versioned scraper code so a roll-back is one revert. |
| R2 | **App goes down at 10:00 IST on MPC day** | **Critical** | (a) Streamlit Cloud has 99% uptime — acceptable; (b) Implement aggressive caching of last-good-data so stale-but-functional UI shows during a scrape failure; (c) Pre-warm the deploy 1 hour before MPC by running a cron-triggered "warm-up" against the workflow. |
| R3 | Stance engine misclassifies a key transition | Medium | Backtest required ≥80%; any miss adds a labelled phrase to the lexicon. Engine outputs evidence (matched phrases) so analyst can audit. |
| R4 | AI Brief hallucinates vote split or quotes | High (reputational) | Strict prompting: provide structured signals only, require Brief to cite source paragraph. Add visible "DRAFT — VERIFY BEFORE PUBLISHING" banner. Brief is generated with `temperature=0`. |
| R5 | RBI website rate-limits the cron | Medium | Conservative cadence (hourly during MPC week, daily otherwise). Polite User-Agent with contact email. Backoff on 429. |
| R6 | PDF parsing brittleness | Medium | Real-PDF integration tests (mirroring macro-pulse [`test_real_pdf.py`](systems/02-macro-pulse/tests/test_real_pdf.py)). Sanity bounds on extracted values. Reject entire record on parse failure (don't persist garbage). |
| R7 | Lexicon overfitting to past 8 MPCs | Medium | Hold out 2 of 8 for validation. Document the lexicon's known blind spots. Plan a quarterly recalibration. |
| R8 | The 8 historical Resolutions are ingested wrong (e.g., we accidentally backfill with synthetic data) | Medium | First action of execution: delete `seed/sample_data.py` SAMPLE_COMMUNICATIONS list and replace with real-PDF-extracted data. Any data with `url` containing "example" must fail boot. |

---

## 11. Open questions

| # | Question | Owner | Blocking? |
|---|---|---|---|
| OQ1 | What's the deployed URL? `india-rbi-comms.streamlit.app`? Or merge into macro-pulse? | User | Non-blocking (default to standalone) |
| OQ2 | Should the AI Brief feature default to free-tier (basic prompt) or premium-tier (longer, structured)? | User | Non-blocking |
| OQ3 | Cross-reference UX: is it a deep-link or an embedded widget? | Eng (recommend deep-link in v1) | Non-blocking |
| OQ4 | Is rbi.org.in's press release page server-rendered or JS-rendered? | Eng — spike before any other work | **Blocking** (drives scraper choice) |
| OQ5 | Do we want a separate Streamlit secrets file for the Anthropic key, or share macro-pulse's? | User | Non-blocking (default: separate) |

---

## 12. Definition of done

The engineering team's work is complete when **all** of the following are true:

1. `pytest systems/01-rbi-comms/tests/` passes with **at least 25 tests**, including:
   - Stance engine backtest (≥80% on 8 historical Resolutions)
   - Diff engine regression (verified against a labelled diff snapshot)
   - At least 3 real-PDF integration tests against committed fixtures
   - Refresh script dry-run + fixture-mode tests
2. `streamlit run systems/01-rbi-comms/app.py` boots cleanly with no synthetic data — `seed/sample_data.py` is deprecated, `seed/historical_data.py` populates the 8 most recent real MPC Resolutions.
3. `python systems/01-rbi-comms/scripts/refresh_rbi.py --dry-run` exits 0 (or 1 / 3 with appropriate logs) against live RBI.
4. `.github/workflows/refresh-rbi.yml` is valid, scheduled, and the `workflow_dispatch` trigger has been tested manually.
5. The MPC Day Hero renders the latest Resolution's repo rate, vote split, and stance label correctly (verified against published RBI data).
6. The "What Changed" tab renders a paragraph-level diff against the prior MPC, with stance-phrase transitions highlighted.
7. AI Brief generation works end-to-end (clicked button → Brief in <15s → saved to `auto_briefs` table).
8. README is rewritten with the actual data flow diagram (no aspirational claims).
9. PRD addressed: every P0 requirement has a verifiable acceptance criterion that's been verified.
10. No commit contains the literal string `rbi.example` outside of a deprecated/marker file.

---

## 13. Suggested execution order

The eng team (Claude + subagents) should attack in this order:

1. **Spike RBI scraping** (1 hour). Verify rbi.org.in is server-rendered. Identify the listing endpoint. Download 1 real Resolution PDF as proof-of-concept.
2. **Schema migration** (15 min). Add `mpc_decisions` table; populate stance fields in `documents`.
3. **Stance engine + lexicon + calibration** (2 hours). Real cognitive work. Most of the v1 quality lives here.
4. **MPC extractor** (1 hour). Parses repo rate, vote split, projections from Resolution PDFs.
5. **Real seed data** (1 hour). Replace synthetic samples with the 8 real Resolutions. Hand-verify each.
6. **Diff engine + MPC view UI** (2 hours). The user-facing payoff.
7. **Refresh script + GH workflow** (1 hour). Mirror macro-pulse pattern.
8. **AI Brief polish** (30 min). Better prompt + draft banner.
9. **Tests + smoke + commit + push + deploy** (1 hour).

**Total: ~9-10 hours. Per the user's "one focused session" framing, this is two sessions, not one.** Recommend splitting after step 4: ship "real ingestion + structured stance" first, then ship "diff view + UI redesign" in a follow-up.

---

## 14. Success metrics (post-launch)

Defined for the user's own self-review at +1 month:

| Metric | Target |
|---|---|
| MPC-day diff render time (from button-click to visible diff) | < 5 seconds |
| AI Brief generation time | < 15 seconds |
| Time from RBI publishing a Resolution to the deployed app reflecting it | < 12 hours |
| Stance-engine accuracy on backtest | ≥ 80% directional |
| Number of real-PDF integration tests | ≥ 3 |
| Number of analyst-grade tests (calibrated lexicon + manually-verified diffs) | ≥ 8 |

---

*End of PRD. The engineering agents may execute this directly without re-clarification.*
