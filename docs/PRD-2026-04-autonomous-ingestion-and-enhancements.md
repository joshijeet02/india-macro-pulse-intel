# India Macro Pulse — Autonomous Ingestion & Platform Enhancements
**PRD · 2026-04-30 · author: jeet (with claude)**

## 0. Why this exists

The deployed app at https://india-macro-pulse.streamlit.app shows IIP through **Feb 2026** even though MOSPI released the **March 2026** IIP on April 28. Root cause: data is loaded from a hardcoded Python list in `seed/historical_data.py` and only refreshes when someone manually edits and pushes that file. The scrapers in `scrapers/mospi_*.py` exist but are never called. The README claims "Automated Ingestion" but no automation has ever existed.

Same architectural problem affects the **Amazon Pulse** tab: prices scraped at runtime live in an ephemeral SQLite DB on Streamlit Cloud and disappear on every container restart. The "180-day history" the user sees today is a `random.uniform(0.92, 0.96)` simulation in `seed/amazon_history.py:38`, not real data.

This PRD ships:
1. **Truly autonomous data ingestion** for CPI/IIP from MOSPI.
2. **A real Amazon basket index** with persisted history.
3. Three high-leverage UX enhancements that bridge the macro-economist / non-economist audience.
4. Bug fixes uncovered during discovery.

## 1. Audience & success metrics

| Audience | What they want | Success looks like |
|---|---|---|
| Macro economist | Fresh data the day MOSPI releases, raw exports, surprise vs consensus | Within 24h of MOSPI release the new month is live in the app; CSV export available on every tab |
| Non-economist (curious investor / student / journalist) | "What does this number mean for me?" | Plain-English toggle reframes every analyst note in lay terms; glossary tooltips on jargon |
| You (the operator) | Zero-touch maintenance | GH Actions handles refresh; failures surface as GitHub issues, not silent staleness |

Negative success metric: **deployed-app data should never lag MOSPI by more than 36 hours** for CPI or IIP. Current lag at time of writing: ~50 days (Feb → April 30 with March release missing).

## 2. Constraints

- **Streamlit Community Cloud** is the deployment target. Filesystem is ephemeral; SQLite resets on every container restart. Anything we want to persist has to live in the git repo.
- **No paid infra**. Free tier of GitHub Actions only. No external DB.
- **MOSPI** publishes PDFs (no JSON API). Layouts occasionally change. Parser must fail loud, not produce garbage.
- **Amazon India** actively defends against scraping. Any solution must tolerate scrape failures and not break the index.
- The `data/` directory is gitignored at the repo root only for `*.db`; JSON files in `data/` ARE committable.

## 3. Architecture decision

The repo IS the database. GitHub Actions are the "ETL". Streamlit reads the committed data on startup.

```
┌─────────────────┐  cron        ┌──────────────────┐  PR/push    ┌──────────────────┐
│ MOSPI press     │ ─────────►   │ GH Actions       │ ──────────► │ data/*.json in   │
│ release pages   │  scraper     │ refresh-data.yml │             │ main branch      │
└─────────────────┘              └──────────────────┘             └────────┬─────────┘
                                                                            │ auto redeploy
                                                                            ▼
                                                                  ┌──────────────────┐
                                                                  │ Streamlit Cloud  │
                                                                  │ reads JSON →     │
                                                                  │ seeds SQLite     │
                                                                  └──────────────────┘
```

Why JSON, not Python list edits: a workflow rewriting Python source is fragile (formatting, ordering, comments are lost). JSON sidecars merged-into-base via `seed.py` is clean, diff-friendly, and reversible.

Why git as DB: free, version-controlled (we get release history "for free"), forces transparency, plays nicely with Streamlit Cloud's auto-redeploy.

## 4. Features

### F1 — Autonomous CPI/IIP ingestion
**Owner:** the daily cron job.

#### F1.1 Hardened parsers
Replace fragile regex (`Manufacturing.*?(-?\d+\.\d+)` will catch index levels and MoM values, not necessarily YoY) with a tiered approach:
1. Try `pdfplumber.extract_tables()` and look for the YoY column in the use-based / sectoral tables.
2. Fall back to **anchored regex** that requires the value to be on the same line as the indicator name AND look like a YoY % (i.e., bounded magnitude).
3. **Sanity check** the extracted dict: `headline_yoy ∈ [-15, 25]`, components ∈ [-50, 50]. If any check fails, return None.
4. Existing `use_fixture=True` path stays intact for tests.

#### F1.2 Refresh script
`scripts/refresh_releases.py`:
- Calls `fetch_latest_cpi()` and `fetch_latest_iip()`.
- Compares `reference_month` against the most recent entry in `data/release_updates.json` (and the hardcoded seed if JSON is absent).
- If newer **and** sanity check passes, appends to `data/release_updates.json`.
- Returns exit code 0 if a new entry was added, 1 if no new release, 2 on parser failure.

#### F1.3 Seed merger
`seed/historical_data.py` becomes:
1. Load hardcoded `CPI_HISTORY` and `IIP_HISTORY` (these freeze the past so we never re-derive).
2. If `data/release_updates.json` exists, merge entries by `reference_month` (JSON wins for newer months).
3. Run upserts as today.

#### F1.4 GitHub Actions workflow
`.github/workflows/refresh-data.yml`:
- Schedule: `cron: '0 13 10-31 * *'` (18:30 IST every day from the 10th to the 31st — covers both CPI ~12th and IIP ~28th windows).
- Manual: `workflow_dispatch`.
- Steps: checkout, install (cached), run refresh script, commit + push if exit code 0, open issue if exit code 2.
- Uses `peter-evans/create-pull-request@v6` for the commit (or direct push to main with `actions/checkout@v4`).
- Token: `GITHUB_TOKEN` (no secrets needed for self-push).

#### F1.5 Failure mode
If the parser returns None or fails sanity check, the workflow opens a GitHub issue titled "MOSPI parser broke for {indicator} {date}" with the URL it tried and a link to the run. The user (you) reads it on next breakfast.

---

### F2 — Robust Amazon Pulse with real history
**Owner:** a separate weekly cron job.

#### F2.1 Persisted price observations
`data/amazon_prices.json` becomes the source of truth — list of `{scraped_at, item_id, price, price_per_kg, item_name, ...}`. The seed at app boot loads this into the SQLite ecomm_prices table the same way `historical_data.py` seeds CPI/IIP.

This single change kills the "simulated history" problem. The Amazon index becomes real over time as the cron job collects more data points.

#### F2.2 Smarter product matching
Today: pick the first `.a-price-whole` element. Problem: sponsored slot, wrong size, or premium variant.

New logic in `scrapers/amazon.py`:
1. Collect up to 10 result tiles, parsing each as `(title, price, sponsored_flag)`.
2. Filter out sponsored.
3. **Unit-aware match**: parse the size (`5kg`, `1L`) from the title and only keep results matching the basket item's expected unit.
4. Pick the **median-priced** match among 3+ candidates (cheapest is often a baiting outlier; median is robust).
5. **Outlier rejection vs trailing**: if the picked price is >40% off the 4-week median for that item, log a warning, do NOT store, and let the workflow open a GitHub issue.

#### F2.3 GH Action for Amazon scrape
`.github/workflows/scrape-amazon.yml` runs **weekly** (cron `0 4 * * 1` = Monday 09:30 IST). Same commit-back-to-repo pattern. Weekly is enough for an inflation signal — daily would be noisy and risk Amazon blocking us.

#### F2.4 Remove the "Simulate 180-Day History" button
Once real history exists this button is misleading. Replace with a "Force scrape now" button gated to local dev only (skip in cloud — only the GH Action should scrape).

#### F2.5 Index integrity
- Base period must be the FIRST stored observation. Today the base regenerates each call — fine for single-platform but breaks if we re-scrape. Pin the base in `data/amazon_index_base.json`.
- Show base date prominently in the UI ("Base: 2026-W18 = 100").

---

### F3 — Plain English Mode (UX bridge: economist ⇄ everyone else)
**The single biggest unlock for non-economists.**

#### F3.1 Top-level mode toggle
A toggle in the sidebar: **"View: [Economist] [Plain English]"**. Persists across reruns via session state.

#### F3.2 Parallel copy
Every rule-based string in `engine/assessments.py` gets a sibling `*_plain` variant. Example:
- Economist: *"Bond market implication: long-end yields will stay anchored until core confirms the disinflation narrative. Real rates are deeply positive."*
- Plain English: *"Borrowing costs for the government are likely to stay where they are. Inflation is below where the central bank wants it, so they may cut rates to make borrowing cheaper for businesses and households."*

Implementation: extend each assessment dict to `{text, text_plain, tone}`. UI selects based on mode toggle. ~25 strings to translate.

#### F3.3 Glossary tooltips
A `glossary.py` mapping technical terms to one-line plain-English definitions. UI wraps key terms in `?` tooltips in plain mode.

```python
GLOSSARY = {
  "Core CPI": "Inflation excluding food and fuel — the steady underlying trend...",
  "MPC": "Monetary Policy Committee — the RBI panel that decides interest rates...",
  ...
}
```

---

### F4 — Data export & calendar polish (analyst ergonomics)

#### F4.1 CSV download per tab
Streamlit `st.download_button` on CPI history, IIP history, basket history, surprise table. One-line per chart. Macro economists copy-paste data into Excel/Stata; this respects that workflow.

#### F4.2 ICS calendar export
A "📅 Add to Google Calendar" button on the release calendar that downloads `india-mospi-releases.ics` with all `RELEASE_SCHEDULE` entries.

#### F4.3 Auto-derived `is_released`
Today `is_released` is hardcoded in `release_calendar.py` and falls out of date. Derive it from the data: a release is released iff its `reference_period` exists in the CPIStore/IIPStore. Removes a class of bug.

---

### F5 — Bug fixes (uncovered during discovery)

- **Duplicate `_cpi_alpha_signal` in `engine/assessments.py`** (lines 160 and 544). The second definition silently overrides the first — the more nuanced "DIVERGENCE DETECTED" branch is dead code. Keep the better one (the second), delete the first.
- **`release_calendar.py` stale flags**: Apr-2025 to Aug-2025 CPI marked `is_released=False` but they happened. Fixed by F4.3.
- **`seed/amazon_history.py:36-38`**: comment says "5% cheaper anchor" but `random.uniform(0.92, 0.96)` is 4-8% cheaper, with random noise. Misleading. To be removed entirely (F2.4).

## 5. Out of scope (deferred)

- LLM-powered "Ask the Data" chat (high value, but adds API cost + key surface — defer).
- Auto-generated AI flash brief on each new release (depends on Anthropic API key in GH Actions secrets — defer one cycle).
- Email/RSS subscriber notifications (no infra, would need SMTP or Resend).
- Multi-platform scraping (Blinkit, Zepto). Existing skeletons are there; defer until Amazon is fully solid.
- WPI / GDP / GST collections / electricity demand nowcast. Architecturally same pattern as CPI/IIP — easy to add later once F1 is shipped.

## 6. Execution order

| Step | What | Why first |
|------|------|-----------|
| 1 | F5 bug fixes | Clean baseline before adding code |
| 2 | F1.1 hardened parsers + tests | The whole pipeline trusts these |
| 3 | F1.2/F1.3 refresh script + JSON-merging seed | Verify locally before wiring cron |
| 4 | F1.4/F1.5 GH Actions workflow | The autonomous bit |
| 5 | F2.1 amazon_prices.json seed-merger | Mirrors F1.3 |
| 6 | F2.2 smarter scraping + outlier rejection | Quality gate |
| 7 | F2.3 amazon scrape workflow | Weekly cron |
| 8 | F2.4/F2.5 UI cleanup | Tied to F2 |
| 9 | F3 plain-english + glossary | Self-contained UI work |
| 10 | F4 CSV / ICS / auto-released | Cross-cutting polish |
| 11 | Pytest + manual streamlit smoke | Verification |
| 12 | Commit + push | Ship |

## 7. Risk register

| Risk | Mitigation |
|------|-----------|
| MOSPI changes PDF layout | Tiered parser (table → regex → fail-with-issue). Sanity bounds reject garbage. |
| Amazon blocks scraping | Weekly cadence, anti-bot init script, fail gracefully into "stale-warning" UI. |
| GH Action commit loop / push permission denied | Use `permissions: contents: write` on the job. |
| Plain-English text drifts from accuracy | Treat as analyst-curated copy, not LLM-rewritten. Each string is a deliberate translation. |
| Adding committed JSON makes repo grow | At ~200 bytes per release × 12/year × 2 indicators = trivial. Amazon prices ~5KB/week × 52 = 250KB/year. Fine for a decade. |

## 8. Definition of done

- `pytest` passes locally.
- `streamlit run app.py` boots cleanly with the new seed-merge logic.
- `python scripts/refresh_releases.py --use-fixture` produces a JSON entry with no errors.
- GH Actions workflow YAML is valid (`actionlint` if installed; otherwise visual review).
- Plain-English toggle round-trips on every assessment text.
- README updated with the actual data-flow diagram and removes the lie about "automated ingestion" (since it's now true).
- All work committed in coherent chunks on `claude/sad-knuth-221faa` and pushed.

---

*End of PRD. Implementation follows.*
