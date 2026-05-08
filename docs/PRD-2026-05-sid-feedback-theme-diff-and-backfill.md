# RBI Communication Intelligence — Theme-Aware Diff & Historical Corpus
**Version:** 1.0 · **Date:** 2026-05-07 · **Author:** Jeet (with Claude as PM)
**Engineering owner:** Claude + subagents (executing in `systems/01-rbi-comms/`)
**Triggered by:** Feedback from Sid, hedge fund operator (Indian macro markets, London desk)

---

## 1. Problem Statement

A hedge fund operator who trades Indian rates daily looked at our app and surfaced three concrete problems:

1. The "newly appeared" / "dropped" phrase summary on the **What Changed** tab has overlap — by set algebra it shouldn't.
2. The diff is run paragraph-by-paragraph, which is mechanically convenient but doesn't match how an analyst actually reads a Statement. An analyst thinks in **themes** (Growth, Inflation, Liquidity, External, Stability) and asks "what shifted in the *growth* read?" — not "what shifted in paragraph 6?".
3. The "this MPC reads most like Aug 2024" archetype feature he liked is starved by a 6-meeting corpus. He suggested 20 years of context.

The honest constraint: **the MPC framework only began October 2016**. Pre-2016 policy was decided by the Governor alone — structurally different, not directly comparable. The realistic ceiling is ~9.5 years (~50–57 historical MPCs), not 20. We will frame this honestly in the UI rather than over-promising.

**Cost of not solving it:** the app's primary value claim — "an MPC-day workbench for analysts who'd otherwise reach for Bloomberg" — degrades when the most-watched user finds an obvious set-algebra error and a structurally weaker diff than what he'd write by hand. Sid's continued use signals product-market fit; losing him signals we're at "demo" not "tool".

---

## 2. Target User

**Primary persona — Sid.** Trades Indian rates at a London hedge fund. Reads every MPC Statement, Resolution, Minutes, and Governor speech. Has Bloomberg. The bar this app has to clear is: *be more useful than 90 seconds of Bloomberg + a copy-paste into Word for a manual diff*. If Sid uses our diff to prep a trade view, we've won.

Secondary: sell-side India rates analysts (the prior PRD's Aanya persona). This phase doesn't change anything for them — but the theme-diff specifically helps them write better client notes faster.

---

## 3. Goals

| # | Goal | Measure | Target |
|---|---|---|---|
| G1 | Eliminate the overlap bug Sid spotted | Set-intersection of `phrases_added` and `phrases_removed` on every diff render | **0**, always |
| G2 | Replace paragraph-aligned diff with theme-aligned diff that an analyst can paste into a note | Manual evaluation: a hedge fund operator copies ≥1 theme-card body verbatim into a client note | Achievable on the Apr 2026 → Jun 2026 diff (next MPC) |
| G3 | Build enough historical corpus that the archetype classifier returns *meaningful* matches | Latest MPC's "reads most like" output, when shown to Sid, registers as a non-trivial historical pattern (not the only-other-meeting-in-corpus default) | ≥30 historical MPCs ingested before archetype is shown publicly |
| G4 | Hold cost & latency: theme-diff renders quickly enough that the analyst doesn't refresh and walk away | Theme-diff latency on cached / cold cases | <2s warm, <8s cold (one-time per MPC pair) |
| G5 | Ship Phase 1 the day Sid sees the response — credibility move | "Phase 1 only" merge & deploy | Same day |

---

## 4. Non-Goals

| # | Non-goal | Why excluded |
|---|---|---|
| N1 | **Pre-2016 (pre-MPC) RBI policy ingestion.** | Different decision-making framework; comparing apples to oranges. Would dilute the archetype classifier rather than strengthen it. |
| N2 | **Real-time live LLM streaming during diff render.** | Caching the LLM output once per MPC pair is sufficient — analysts re-read the same diff dozens of times, only the first render needs the LLM. |
| N3 | **Member-level theme diff** (e.g., "what changed in Dr. X's growth view across the last 3 Minutes"). | Real value but a separate, much larger feature. Park for after backfill stabilizes. |
| N4 | **Multi-language UI / Hindi support.** | Sid reads English; the corpus is published in English; not a customer ask. |
| N5 | **"Predict the next MPC" model.** | Out of scope — we're a comprehension tool, not a forecaster. Easy to overpromise; hard to deliver credibly. |
| N6 | **Sentiment dashboard / market-reaction overlay.** | Adjacent and useful but a different product surface. After Sid's three asks land, then re-evaluate. |

---

## 5. User Stories

### Tier 1: Sid's MPC-day workflow

```
US-1   As a hedge fund operator on MPC day,
       I want to see what changed in the GROWTH view vs the prior MPC
       (not what changed in paragraph 6),
       so that I can write a 2-line "growth picture has softened/firmed" note
       to my desk without re-reading two full Statements.

US-2   As an analyst,
       I want each theme-card to include a tagged list of phrases ENTERED
       (newly appeared) and EXITED (dropped) the document — with no overlap —
       so that the headline language transitions are scannable in one pass.

US-3   As an analyst,
       I want each theme-card to include 1–2 sentences of LLM-generated
       contextual diff summary,
       so that when I'm prepping a desk note in 90 seconds, I can copy that
       summary verbatim and trust the citation.

US-4   As an analyst,
       I want to know "this growth section reads most like the August 2018 MPC"
       rather than the only-other-meeting-in-the-corpus,
       so that the archetype actually says something I didn't already know.
```

### Tier 2: trust signals

```
US-5   As an analyst,
       I want to see a confidence indicator on archetype matches
       (e.g., "Strongly resembles" vs "Distantly resembles"),
       so that I don't reach for a weak match as if it were a strong one.

US-6   As an analyst,
       I want to copy the entire "What Changed" tab as Markdown to my clipboard,
       so that I can paste it as the skeleton of a Bloomberg note in one click.
```

---

## 6. Requirements

### P0 — Phase 1 (this session, ~30 min)

#### F1: Zero-overlap bug fix
- **Description**: Compute `phrases_added` and `phrases_removed` from document-level set membership, not from paragraph-level union. Set algebra guarantees they're disjoint.
- **Acceptance criteria**:
  - [ ] `summarize_diff()` reads from full prev-doc + curr-doc text, not from `[d.phrases_added for d in diffs]`.
  - [ ] On the Feb 2026 → Apr 2026 diff (currently shipped), no phrase appears in both lists.
  - [ ] One regression test in `tests/test_diff_engine.py` that constructs a curr/prev pair where a phrase appears in different paragraphs in each and asserts the set intersection is empty.
  - [ ] No regression in 102/102 existing tests.

### P0 — Phase 2 (next session, 2–3 hours)

#### F2: Theme-aware diff with LLM contextual summary

**Description**: Replace paragraph-aligned diff in the **What Changed** tab with a theme-grouped layout. Each theme renders as a card with: heading, the phrases that entered/exited, the underlying paragraph diffs, and a 2–3 sentence LLM summary of what changed.

**Themes** (deterministic, derived from RBI's own section headers — no LLM needed for classification):
- Growth
- Inflation
- External Sector
- Liquidity & Financial Markets
- Financial Stability
- Additional Measures (regulatory / operational)
- Stance & Forward Guidance (parsed from the rate-decision paragraph)

**Why deterministic theme classification, not LLM**: RBI's Statements have explicit section headers in the source HTML — `<b>Growth</b>`, `<b>Inflation</b>`, etc. Regex extraction is reliable, free, and fast. LLM only enters at step 4 below for the *contextual summary*.

**Pipeline**:
1. `engine/theme_chunker.py` — splits a Statement into `dict[theme: paragraphs]` using a regex-extracted section-header map.
2. `engine/theme_diff.py` — for each theme, produces `prev_text`, `curr_text`, lexicon-tracked phrase entries/exits, and a 2-line LLM summary (Sonnet 4.6, prompt-engineered for "explain what shifted in the growth read between [prev_date] and [curr_date], in <60 words, citing paragraph numbers").
3. UI: theme-card grid (2-up on desktop, 1-up on mobile). Each card has icon, heading, phrase deltas, LLM summary, and an "Open paragraph diff" expander.
4. Cache: results keyed on `(prev_doc_id, curr_doc_id, theme)` and persisted to a new `theme_diff_cache` SQLite table. First render LLM-cold; subsequent re-views are instant.

**Acceptance criteria**:
- [ ] Each of the 7 themes produces a populated card on the Feb 2026 → Apr 2026 diff.
- [ ] Phrase entries/exits within a card are disjoint (re-validates F1 at the theme level).
- [ ] LLM summary mentions paragraph numbers for any quoted material.
- [ ] Cache hit on second render completes in <500ms.
- [ ] Cold render (no cache) completes in <8s for the entire tab.
- [ ] Cost per cold render: ≤$0.10 at Sonnet 4.6 rates (target: ~$0.05).
- [ ] Tests: theme-chunker unit tests against committed HTML fixtures; theme-diff orchestration test with a mocked Anthropic client.
- [ ] If `ANTHROPIC_API_KEY` is missing, theme cards still render the deterministic phrase deltas — only the LLM summary is hidden, with a one-line "Set ANTHROPIC_API_KEY to enable LLM commentary" caption.

### P0 — Phase 3 (separate session, 3–4 hours active scraping + ~1 hour verification)

#### F3: Historical MPC corpus backfill (Oct 2016 → present)

**Description**: Sweep RBI's PRID space backward to ingest all MPC Governor's Statements + Minutes from October 2016 (first MPC) through the most-recent. Target ≥50 documents. Existing scraper architecture (`Annualpolicy.aspx` + `BS_PressReleaseDisplay.aspx?prid=N`) handles this — the backfill is mostly verification work.

**Scope**:
- All MPC Resolutions / Governor's Statements: ~57 meetings × 1 PRID each = 57 PRIDs.
- All Minutes: ~57 PRIDs (released ~2 weeks after each meeting).
- Total: ~114 documents to ingest.

**Quality bar**:
- Each ingested document goes through `mpc_extractor.py` (repo rate, vote split, stance) and gets a populated `mpc_decisions` row.
- Documents from before the 2016=100 base year transition (roughly Oct 2016 – Mar 2018) may have parser quirks; spot-check 5 manually.
- Documents that fail sanity check (missing repo rate, vote count off, stance unparseable) are NOT silently dropped — they go into a `data/ingestion_failures.json` for human review.

**Acceptance criteria**:
- [ ] ≥50 historical MPCs ingested into `data/rbi_communications.json`.
- [ ] Repo-rate path renders as a continuous time-series chart from Oct 2016 to the most-recent meeting (sanity check: should show all known cuts and hikes).
- [ ] Stance-time-series tab shows the regime transitions (accommodative → withdrawal → neutral) at the right meetings.
- [ ] Archetype classifier, when run on the latest MPC, returns matches that are NOT the only-other-meeting-in-corpus default.
- [ ] App boot time on Streamlit Cloud stays <12s with the expanded corpus (was <10s with 12 docs).
- [ ] FTS5 chunk count: ≤2,000 (current 286 will grow ~5x). Below SQLite's comfortable ceiling.
- [ ] Cost: zero recurring (one-time scrape); Anthropic API cost <$5 total during backfill (Sonnet, used only if we chunk-summarize during ingestion).
- [ ] Documentation: `docs/historical-corpus.md` with per-meeting verification log.

### P1 — Nice to have (next session if time, else after)

#### F4: Archetype confidence levels & "no match" handling

**Description**: When the archetype classifier returns a match, surface a confidence label:
- **Strongly resembles** (cosine similarity ≥0.85)
- **Resembles** (0.70–0.85)
- **Distantly resembles** (0.55–0.70)
- **No clear historical match** (<0.55) — the UI shows this honestly rather than coercing a weak match.

**Acceptance criteria**:
- [ ] `engine/archetype.py` returns a `confidence` field alongside `most_similar_meeting`.
- [ ] UI badge color-codes by confidence (green / blue / grey / orange).
- [ ] When all candidates score <0.55, the UI shows "No clear match in our 9-year corpus — this MPC reads as a fresh combination of signals" rather than the top-of-the-poor-pile.

#### F5: Theme-archetype (Sid's full ask)

**Description**: Apply archetype matching at the **theme level** — "the Growth section reads most like Aug 2018; the Inflation section reads most like Feb 2022". This is what Sid actually asked for in feedback #3.

**Dependencies**: Requires F2 (theme-chunked corpus) and F3 (≥30-document corpus to make per-theme matching meaningful).

**Acceptance criteria**:
- [ ] Each theme card on the **What Changed** tab shows its own "reads most like" line.
- [ ] Confidence levels apply per-theme (a strong match on Growth + a no-match on Inflation is a valid combined output).

### P2 — Future considerations (design now, build later)

| # | Idea |
|---|---|
| P2.1 | **Theme volatility chart** — a small heatmap on the Stance Time Series tab showing which themes have shifted most across recent MPCs. Helps Sid see "Inflation language is the most volatile axis right now". |
| P2.2 | **One-click Markdown export** of the entire What Changed tab → clipboard. Direct workflow win for Bloomberg-note prep. |
| P2.3 | **Member-level theme diff** — once Minutes are richer, who said what about Growth across the last 3 meetings. |
| P2.4 | **Pre-MPC speech aggregation** with theme classification — track the policy walk in the 7 days before each MPC. |

---

## 7. Cost & Time Analysis (PM-grade)

### Token cost (Sonnet 4.6 at ~$3/$15 per M tokens)

| Workload | Per-call tokens | Per-call cost | Frequency |
|---|---|---|---|
| Theme contextual summary (1 theme) | ~1.5k input, 100 output | ~$0.006 | 7 calls per cold render |
| Cold render of full theme-diff tab | ~10k input, 700 output | **~$0.05** | Once per MPC pair, then cached |
| AI Brief (existing) | ~5k input, 700 output | ~$0.025 | Once per MPC, cached |
| Q&A Mode (existing) | ~3k input, 500 output | ~$0.015 | Per user query, no cache |
| **Estimated monthly cost** at 100 active sessions, 1.5 cold theme-diffs each + 50 Q&A queries | | | **~$10–15/month** |

**Conclusion**: cost is well within "portfolio side project" budget. The cold-render cap of $0.10 keeps us defensible even if usage 5x.

### Streamlit Cloud boot-time impact

- Current: 286 chunks → boot ~6s.
- Phase 3 (50 historical MPCs): ~1,500 chunks → projected boot ~9s based on linear scan of FTS5 indexing.
- Mitigation if boot exceeds 12s: persist chunks in committed JSON (already do), skip re-chunking on hot boot, lazy-index FTS5 on first search rather than at startup. None of these are currently needed; design Phase 3 to monitor and degrade gracefully.

### Time-to-ship

| Feature | Active dev time | Critical path |
|---|---|---|
| F1 (overlap bug) | **~30 min** | Single function rewrite + 1 regression test. Ship same day. |
| F2 (theme-diff) | **2–3 hr** | Theme chunker, theme-diff orchestration, LLM call, cache table, UI grid, tests. |
| F3 (historical backfill) | **3–4 hr scraping + 1–2 hr verification** = **~5 hr total** | PRID sweep ~Oct 2016 onward, parser shake-out on older docs, manual spot-check of 5 anomalies, repo-rate/stance time-series sanity check. |
| F4 (archetype confidence) | **~1 hr** | Add confidence field + UI badge. |
| F5 (theme-archetype) | **~2 hr after F2 & F3 land** | Per-theme classifier instances + UI integration. |

**Recommended phasing**:
- **Today**: F1.
- **Next session**: F2 (works on current corpus).
- **Session after**: F3 (corpus expansion). After this lands, F4 + F5 ride together as a quick polish session.

---

## 8. Beautiful-Product Thinking

### Theme-card design

Each theme card should feel like an analyst's hand-written margin note:

- **Header**: theme icon + name (e.g., 📈 Inflation) + "vs Feb 2026" subhead
- **Lede**: the 2-line LLM summary in slightly larger text
- **Body**: phrase deltas as small chips — green chips for entered, grey strikethrough for exited
- **Expander**: paragraph-level diff for analysts who want to verify a quote
- **Footer**: archetype line ("This Inflation section reads most like Aug 2018") with confidence badge

Cards are 2-up on desktop, stacked on mobile. Visual rhythm consistent with the existing Glossary tab so the user feels they're in the same product.

### Empty-state and degradation

- **No prior MPC in corpus** (Phase 3 backfill not yet done): theme cards still render with phrase deltas but no archetype line; a one-line "Archetype line will populate once historical corpus is ingested" note.
- **LLM unavailable**: phrase-delta chips render; the LLM summary slot shows a one-line "Add ANTHROPIC_API_KEY in Streamlit secrets for context summary" caption — no broken-looking blank space.
- **Theme not present in this Statement** (rare — Additional Measures is sometimes empty): don't render the card. Don't render an empty card.
- **Archetype confidence <0.55**: card shows "No clear historical match" rather than a top-of-the-pile coerced match.

### What makes this paste-able into a Bloomberg note

The LLM summary prompt explicitly trains for analyst voice:

> "Explain what shifted in the [theme] read between [prev_date] and [curr_date], in <60 words. Cite paragraph numbers for any quoted phrasing. Avoid analyst clichés ('hawkish tilt', 'dovish pivot'). Voice: terse, decisive, professional. The reader is a hedge fund desk strategist."

This is the difference between "AI-generated commentary that smells like AI" and "two lines I'd actually quote".

---

## 9. Two Enhancements Sid Didn't Ask For

These would meaningfully move the product for hedge fund operators specifically:

### E1: Theme volatility heatmap on the Stance Time Series tab
A 7-row × 12-column heatmap (rows: themes, columns: last 12 MPCs). Each cell color-coded by *how much* that theme's language shifted from the prior MPC. Reveals at a glance "Inflation language has been the most volatile axis in 2026 — Growth and External Sector have been steady". This is a cross-meeting analytical surface that no Bloomberg dashboard provides.

### E2: "Trade-it" copy-export of theme summaries
Each theme card has a small clipboard icon. One click → copies a Markdown block with the theme name, the date pair, the LLM summary, the cited paragraphs, and a footer line "Source: RBI MPC Statement, [date], paragraphs [N], [N]." Pasting this into Slack / Bloomberg chat / Word produces a formatted block with attribution. The hedge-fund desk-prep workflow currently requires retyping; this collapses it to two clicks. The cost is trivial (a single button + `pyperclip` / Streamlit's clipboard widget) but the workflow win is significant.

These are deliberately **not** P0/P1 — they're documented here so we don't accidentally architect them out, but they ship after the three-feature core.

---

## 10. Risk Register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | LLM latency on theme classification spikes (cold start of 7 calls) | Medium | Parallelize theme calls (asyncio + httpx), cache per (prev_id, curr_id, theme), pre-warm on workflow when a new MPC ingests. Target: cold ≤8s, warm ≤500ms. |
| R2 | Archetype classifier coerces weak matches into a confident-looking output | High | F4 confidence levels + an explicit "no match" floor at cosine 0.55. UI uses copy that conveys uncertainty when present. |
| R3 | Older RBI URLs (2016–2018) have format drift the parser doesn't handle | High | Tiered fallback in `_pdf_extract.py`. On parse failure, log to `data/ingestion_failures.json` with PRID + reason. Manual spot-check 5 oldest docs before declaring backfill complete. |
| R4 | 9-year-old documents have OCR/PDF quality issues that confuse the chunker | Medium | Skip-on-parse-failure rather than persist garbage. Sanity-bound the time-series view to "ingestion_quality > 80%" of months covered. |
| R5 | Sonnet API rate limits during backfill (114 docs × ~1 LLM summary each) | Low | Sequential ingestion at <10 req/min. Anthropic free-tier limits are well above this. |
| R6 | Streamlit Cloud boot exceeds 12s with expanded corpus | Low | Lazy-load FTS5; persist seeded SQLite via a committed `.db` file (already in `.gitignore` rules for selective whitelist). Monitor first deploy after F3. |
| R7 | F2 ships without F3 — archetype-line on theme cards reads as gimmicky on a 6-doc corpus | Low | Hide the archetype line on theme cards until ≥30 historical docs are in the corpus. Use a feature flag. |
| R8 | Caching layer (theme_diff_cache) drifts from regenerated content (e.g., we update the prompt) | Low | Include the prompt hash in the cache key. Bumping the prompt invalidates stale cache entries. |

---

## 11. Definition of Done

### F1 (Phase 1 — today)
- [ ] `summarize_diff()` returns disjoint `phrases_added` / `phrases_removed`.
- [ ] Regression test added to `tests/test_diff_engine.py`.
- [ ] 103/103 tests pass (102 existing + 1 new).
- [ ] Streamlit smoke test boots clean.
- [ ] Pushed to `main`. Streamlit auto-redeploys. Sid can verify live within 2 minutes.

### F2 (Phase 2 — next session)
- [ ] `engine/theme_chunker.py` exists with deterministic header-based theme assignment.
- [ ] `engine/theme_diff.py` exists with theme-grouped LLM summary orchestration + cache.
- [ ] New `theme_diff_cache` SQLite table populated correctly.
- [ ] `ui/mpc_view.py` "What Changed" tab renders 7 theme cards (when applicable) with the design described in §8.
- [ ] Cold render <8s, warm render <500ms.
- [ ] No-LLM fallback works (phrase deltas still render).
- [ ] Tests: theme-chunker unit (against committed fixtures), theme-diff orchestration (mocked Anthropic).
- [ ] No regression in existing 102 tests.
- [ ] Pushed to `main`.

### F3 (Phase 3 — separate session)
- [ ] ≥50 historical MPCs (Statements + Minutes) ingested.
- [ ] Repo-rate time-series chart renders continuously from Oct 2016 to present, no gaps >3 months.
- [ ] Stance-label history shows correct regime transitions.
- [ ] `data/ingestion_failures.json` exists if any parser failures; failures spot-checked.
- [ ] `docs/historical-corpus.md` with verification log.
- [ ] Streamlit Cloud boot ≤12s.
- [ ] Pushed to `main`.

### F4 + F5 (combined polish session)
- [ ] Archetype returns confidence; UI badge renders correctly.
- [ ] Theme-cards include archetype line where confidence ≥0.55, "no clear match" otherwise.
- [ ] Sid sees per-theme archetypes when he opens a fresh diff post-F3.

---

## 12. Open Questions

| # | Question | Owner | Blocking? |
|---|---|---|---|
| OQ1 | Should the LLM summary prompt include macro-pulse cross-reference data (latest CPI/IIP print) to ground the contextual diff? | Eng — recommend NO for v1, add later if Sid asks | Non-blocking |
| OQ2 | For F3, should we also ingest **Monetary Policy Reports** (semi-annual, 60+ pages each) for richer Q&A coverage? | Stakeholder (Jeet) | Non-blocking; default skip in v1, decide post-backfill |
| OQ3 | Use `pyperclip` (Python-side) or `streamlit-extras` `to_clipboard` (browser-side) for E2's copy-export? | Eng — recommend browser-side for portability | Non-blocking |
| OQ4 | Should F3 backfill run as a one-off script (commit results to repo) or as an extension of the existing `refresh-rbi.yml` cron? | Eng — recommend one-off script with manual oversight; add cron later | Non-blocking |

---

## 13. Recommended Sequencing

| Stage | When | Effort | Ships |
|---|---|---|---|
| **Phase 1** | Today | 30 min | F1 (overlap bug fix) |
| **Phase 2** | Next session (~2-3 days out) | 2–3 hr | F2 (theme-aware diff) |
| **Phase 3** | Subsequent session | 5 hr | F3 (historical backfill) |
| **Phase 4** | Session after | ~3 hr | F4 + F5 (confidence + theme-archetype) |
| **Future** | When you decide | Variable | E1, E2 |

---

## 14. Sid Communication Strategy

After Phase 1 (today): "Bug fixed — push live within minutes. Two more upgrades coming based on your feedback."

After Phase 2: "Theme-based diff is live. Try the next MPC. Curious if it matches how you prep a desk note."

After Phase 3: "Now running on 9 years of MPC corpus (since RBI's MPC framework began Oct 2016). The archetype matches should now actually say something."

Don't promise "20 years" — Sid is sophisticated enough to know the framework history. Honest framing builds more trust than over-promising.

---

*End of PRD. The engineering agent may execute against this without re-clarification.*
