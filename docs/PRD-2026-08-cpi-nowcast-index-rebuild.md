# Proprietary Pulse → CPI Nowcast Engine

**PRD · 2026-08-05 · author: jeet (with claude)**

## 0. Why this exists

The "Proprietary Pulse" tab promises a real-time proprietary grocery price index that anticipates official CPI. Today it delivers neither the data nor the accuracy claim.

**It has no data, and no mechanism that can produce any.**

- `data/amazon_prices.json` has **never existed** in the repo's git history (verified across all refs).
- `5c4139d` (Apr 30) deleted both `.github/workflows/scrape-amazon.yml` and `scripts/scrape_amazon.py`, moving to manual-only scraping.
- `hydrate_db_from_json()` therefore returns 0 on every boot, and the deployed tab renders "No price data yet."
- The only remaining trigger is the **Run Price Scrape** button. On Streamlit Cloud, `append_observations()` writes to the container's ephemeral filesystem, which is never committed to git. There is no path from container disk back into the repo, so the persistence layer is sound code wired to a dead end. It works locally and only locally.

**And where it does compute, it computes the wrong number.**

- **Formula mismatch.** `compute_index()` uses a weighted *arithmetic* mean of price relatives. MOSPI CPI 2024 uses **Jevons** (geometric mean) at the elementary level and **Young/modified Laspeyres** at higher levels. By Jensen's inequality the arithmetic mean is always ≥ the geometric mean, so our index carries a systematic upward bias against the exact series it claims to anticipate, widening as price dispersion widens.
- **Stale weights.** `engine/ecomm_basket.py` weights "mirror India's 2012=100 CPI food sub-group shares." CPI rebased to **2024=100 effective January 2026**, and Food & Beverages fell from **45.86% → 36.75%** under HCES 2023-24 and COICOP 2018. The basket is weighted to a retired consumption pattern.
- **Composition leakage.** `compute_index()` renormalises over whatever weight matched this run. With **every price literally unchanged**, dropping one item (rice, weight 14.0) moves the index **+1.40 points** — pure composition artifact, several times larger than the ~0.5pp CPI food moves the index exists to detect.
- **No product identity.** Each run re-searches Amazon and picks a fresh median candidate, so week 2 can measure a different SKU than week 1. Product substitution is indistinguishable from price change.

**Collateral damage outside this tab:** `engine/cpi_decomposer.py:7` hardcodes `FOOD = 0.4586` and derives core as the residual. Every 2026 CPI reading in the app is decomposed on retired weights, overstating the food contribution by roughly a quarter and dumping the error into core.

This PRD rebuilds Proprietary Pulse as a **CPI nowcast engine with a measured, published tracking record** — the standard a sell-side desk applies before adopting an indicator.

## 1. Objective

One quantity is being optimized: **out-of-sample absolute error between our published nowcast and MOSPI's headline CPI YoY print.**

Headline is the target because that is what the MPC targets, what consensus trades, and what a desk publishes. But our basket only observes food, so we predict headline by decomposition:

```
headline_nowcast = 0.36753 × food_nowcast  +  0.63247 × non_food_nowcast
                   └── observed basket ──┘      └── AR / persistence ──┘
```

Weights are the official CPI 2024 Combined division shares (source: MOSPI first 2024-base release, 12 Feb 2026, Annexure V Q39).

This split is not a compromise; it is the point. The two legs have opposite statistical characters:

- **Food** is volatile and drives nearly all of India's headline surprises. High-frequency observation earns its keep here.
- **Non-food core** is smooth, persistent, and mean-reverting. A cheap AR model on published group indices captures most of it, with no proprietary data required.

Expensive signal is spent where variance lives; cheap statistics cover where it does not. Errors become **attributable** to a leg, which is the difference between a number we can improve and one we can only apologise for.

**Consequence of the rebasing — and an important correction.** The headline "45.86% → 36.75%" is *not* all Engel's-law expenditure shift. MOSPI decomposes it (Annexure V, Q40):

| Comparison | Shift | Cause |
|---|---|---|
| 45.86% → 40.10% | −5.76pp | Genuine expenditure shift, holding CPI 2012 classification fixed |
| 42.62% → 36.75% | −5.87pp | Genuine shift, holding COICOP 2018 classification fixed |
| 40.10% vs 36.75% | −3.35pp | **Reclassification only**, not behaviour |

The reclassification gap is mostly "Restaurants and accommodation services" (3.348%) splitting out into its own division. Under CPI 2012, Food & Beverages included eating out; under COICOP 2018 it does not.

**This materially improves our construct validity.** Our basket is 20 raw grocery items. It never had any business proxying a 45.86% aggregate that bundled restaurant meals. The new 36.753% F&B division is *closer* to what we actually measure. The effective leverage loss is therefore smaller than the headline numbers suggest, and the mapping is cleaner.

## 2. Audience & success metrics

| Audience | What they want | Success looks like |
|---|---|---|
| Sell-side / buy-side macro desk | A number they can defend in a morning note | Published out-of-sample RMSE vs headline CPI, benchmarked against random-walk and AR(1); methodology reproducible from the repo |
| RBI-watcher / rates analyst | A read before the print lands | Nowcast published on day 1 of month M+1, ~11 days ahead of MOSPI's ~12th-of-month release |
| You (the operator) | Zero-touch maintenance | Daily cron ingests DoCA; failures surface as GitHub issues, not silent staleness |

**Primary success metric:** headline nowcast RMSE beats the random-walk benchmark out-of-sample. If it does not, we report that and diagnose which leg failed — a negative result published honestly is still a result.

**Negative success metric:** the app must never present an index reading whose coverage or provenance is undisclosed.

## 3. Constraints

- **Streamlit Community Cloud.** Ephemeral filesystem; SQLite resets on restart. Anything persisted lives in the git repo. Unchanged from prior PRDs.
- **No paid infra.** Free-tier GitHub Actions only.
- **Network reachability is not uniform** (measured 2026-08-05):

  | Host | Status |
  |---|---|
  | `fcainfoweb.nic.in` (DoCA Price Monitoring System) | HTTP 200 — authoritative, reachable |
  | `data.gov.in` | HTTP 200 |
  | `dca.ceda.ashoka.edu.in` (CEDA mirror) | DNS does not resolve |
  | `cpi.mospi.gov.in` | Connection timeout |

  Ingestion must therefore be **primary + fallback**, never single-host, and must cache into the repo.
- **Series break at Jan 2026 — and MOSPI forbids linking below the general index.** Verbatim from the 2024-base release: *"the two series can be directly linked only for general index level."* Official linking factors exist (Rural 0.5222, Urban 0.5320, **Combined 0.5267**) and an official back series covers the General Index Jan-2013 → Dec-2024. But **no linkable food series spans the break.** This is a hard constraint, not a modelling preference: the food leg cannot be backtested continuously across Jan-2026, while the headline leg can.
- **Amazon actively defends against scraping.** The index must degrade gracefully, never silently.

## 4. Data sources

| Source | Role | Coverage |
|---|---|---|
| DoCA Price Monitoring System | Index backbone + backtest substrate | 22→38 commodities, 550 centres, 2009→present, **daily** |
| MOSPI CPI prints (existing pipeline) | Ground truth | Already flowing |
| MOSPI CPI 2024 weights | Official item/group weights | Static, versioned; published per FAQ Q12 |
| Amazon India (existing scraper) | Channel overlay + non-DoCA items | 20 items, irregular |

**Basket coverage by DoCA** — 13 of 20 items, **75.3% of basket weight**:

| Status | Items | Weight |
|---|---|---|
| Covered by DoCA | rice, atta, toor, moong, chana, sunflower oil, mustard oil, milk, onion, tomato, potato, sugar, tea | 75.3% |
| Amazon-only | curd, paneer, eggs, banana, apple, turmeric, coriander | 24.8% |

### Official CPI 2024 division weights (Combined)

Sourced from MOSPI's first 2024-base release, Annexure V Q39. Both columns are on the COICOP 2018 structure, so they are directly comparable. Sums to 100.0.

| Division | CPI 2012 | CPI 2024 |
|---|---|---|
| **Food and beverages** | 42.617 | **36.753** |
| Housing, water, electricity, gas and other fuels | 16.888 | 17.665 |
| Transport | 6.394 | 8.796 |
| Clothing and footwear | 6.527 | 6.383 |
| Health | 5.900 | 6.100 |
| Personal care, social protection and misc | 4.006 | 5.038 |
| Furnishings, household equipment, maintenance | 3.656 | 4.469 |
| Information and communication | 3.323 | 3.609 |
| Restaurants and accommodation services | 3.246 | 3.348 |
| Education services | 3.513 | 3.333 |
| Paan, tobacco and intoxicants | 2.380 | 2.989 |
| Recreation, sport and culture | 1.547 | 1.516 |

These are the weights for the non-food leg. **Item-level weights are also published** — the monthly release itself carries them in its high/low inflation tables (e.g. Onion 0.7006, Potato 0.7549, Tomato 0.4961, Arhar/Tur 0.5333), and the full item list is on `mospi.gov.in` per FAQ Q12.

### CFPI — the official food index

MOSPI publishes a **Consumer Food Price Index** alongside headline (Jan-2026: Rural 1.96, Urban 2.44, Combined 2.13), with a monthly index level series in the release. CFPI is the canonical food inflation number and is a cleaner target for the food leg than reconstructing the F&B division ourselves. The food leg targets CFPI; the F&B division weight is used for the headline roll-up.

**Why this matters strategically:** CPI 2024 itself now ingests e-commerce prices — 12 online markets across towns above 25 lakh population, collected weekly, plus explicit "alternative data sources… e-commerce/online price data" (FAQ Q14, Q26). This modestly erodes the novelty of an Amazon basket but materially *raises* the correlation we should expect, because the target now contains online prices.

## 5. Architecture

Unchanged principle: **the repo is the database.** DoCA ingestion joins the existing cron pattern.

```
DoCA daily prices ──┐
                    ├─► refresh-doca.yml (cron) ─► data/doca_prices.json ─┐
MOSPI CPI prints ───┤                                                      │
                    ├─► refresh-data.yml (cron) ─► data/release_updates.json
Amazon basket ──────┘                                                      │
                                                                           ▼
                                                        SQLite hydrated on boot
                                                                           │
                              index_formula → nowcast → backtest ──────────┤
                                                                           ▼
                                                                    UI reads results
```

New modules, each pure and independently testable:

| Module | Responsibility | Depends on |
|---|---|---|
| `engine/index_formula.py` | Jevons elementary, Young aggregation, matched-sample chaining. **No I/O.** | nothing |
| `engine/basket_weights.py` | Official CPI 2024 weights keyed to `item_id`, with provenance (source URL, retrieval date, base year) | nothing |
| `scrapers/doca.py` | DoCA ingestion, primary + fallback host, backfill + increment | requests/bs4 |
| `engine/nowcast.py` | Food leg, non-food leg, weighted combination | index_formula, basket_weights |
| `engine/backtest.py` | Walk-forward evaluation, metrics, benchmarks | nowcast |

Changed: `ecomm_index.py` (delegates math), `outlier.py` (repair not drop; protect base), `amazon.py` (product identity, consistent estimator), `cpi_decomposer.py` (base-aware weights), `scrapers/_pdf_extract.py` (group-level index extraction), `db/` (new tables), `ui/ecomm_view.py` (nowcast + accuracy panel).

## 6. Features

### F1 — Formula correctness (P0)

Replace the weighted arithmetic mean of relatives with **Jevons at elementary level** (geometric mean across an item's candidate quotes) and **Young/modified Laspeyres at aggregation**, matching MOSPI exactly.

Pure functions, no network, fully unit-testable against hand-computed examples. This is the cheapest accuracy gain available — it removes a known one-directional bias for zero new data.

**Done when:** `index_formula.py` reproduces hand-computed Jevons and Young values to 6dp; `compute_index()` delegates to it; existing tests still pass.

### F2 — Official CPI 2024 weights (P0)

Replace 2012-derived basket weights with official CPI 2024 weights. Carry provenance in code so the base year is never ambiguous again.

- All 12 division weights (table in §4) — needed for the non-food leg.
- `CPI_FOOD_WEIGHT = 0.36753`, `CPI_NONFOOD_WEIGHT = 0.63247`.
- Item-level weights where published; renormalised within the basket.

**Done when:** weights trace to a cited MOSPI source with retrieval date; `basket_weights.py` exposes base year; division weights sum to 100.0 ± 0.01 under test; basket weights sum asserted.

### F3 — Base-aware CPI decomposer (P0, adjacent bug)

`cpi_decomposer.py` selects weights by reference month: 2012 weights before 2026-01, 2024 weights from 2026-01. Fixes the food-contribution overstatement corrupting every 2026 reading in the CPI tab.

**Done when:** decomposing a 2025 month uses 0.4586, a 2026 month uses 0.3675, both covered by tests.

### F4 — DoCA ingestion (P0)

Historical backfill (2009→present) plus daily increment, committed to `data/doca_prices.json`, on the established cron + issue-on-failure pattern. Primary host `fcainfoweb.nic.in`, with fallback.

**Done when:** backfill produces a continuous daily series for the 13 covered items; cron refreshes incrementally; parser failure opens an issue rather than committing garbage.

### F5 — MOSPI group-level index extraction (P0, new dependency)

The non-food leg needs published **group-level indices**, not just headline and food. The current parser extracts headline / food / fuel only, and already has partial-extraction problems (every recent CPI row has `fuel_yoy: null`; every recent IIP row has null sector splits).

**Done when:** the parser extracts division-level YoY for the 12 COICOP divisions where present, and degrades to null per-division rather than failing the whole release.

### F6 — Nowcast model (P0)

- **Food leg:** basket index → **CFPI** YoY (the official food index, not a self-reconstructed F&B division). Monthly-average prices → YoY → fitted mapping with lags.
- **Non-food leg:** AR / persistence model on published non-food division indices.
- **Combination:** official weights, `0.36753 / 0.63247`.

Deliberately few parameters. With ~200 monthly observations since 2009, OLS with 2–3 regressors is appropriate; anything heavier overfits.

**Done when:** the model produces a headline nowcast with a stated error band, and every fitted coefficient is inspectable in the UI.

### F7 — Backtest harness (P0)

Walk-forward, out-of-sample: fit to month M, predict M+1, roll.

- **Metrics:** RMSE, MAE, directional hit rate, full error distribution — reported per leg (food, non-food, combined headline).
- **Benchmarks:** random walk, seasonal naive, AR(1). A nowcast that cannot beat "last month's rate persists" is not a product, and we report the comparison whichever way it falls.
- **Series break:** headline uses MOSPI's official linked back series (Combined LF 0.5267). The food leg is fitted and reported per regime, never pooled — MOSPI permits linking only at general-index level. 2024-base food performance carries an explicit caveat that it rests on ~7 months (Jan–Jul 2026). A short honest track record beats a long misleading one.

**Done when:** `backtest.py` emits a metrics table for current vs revised methodology, so F1–F2's effect is measured rather than asserted.

### F8 — Amazon structural fixes (P1)

- **Product identity:** pin each basket item to a stable product; re-discover only on delisting; log substitutions as discrete events.
- **Matched-sample chaining:** period-over-period movement computed only across items present in both periods, then chained. Kills the +1.40-point artifact.
- **Base discipline:** one common fixed base (calendar 2024, matching MOSPI's price reference period). Amazon's base is its first complete month, labelled as such rather than silently conflated.
- **Estimator consistency:** one estimator regardless of candidate count; unit consistency enforced rather than abandoned when few candidates survive (`amazon.py:189`, `:197`).
- **Outlier repair:** rejected observations no longer vanish (which drops coverage and triggers composition bias) — they are imputed from the item's own trailing behaviour and flagged.

### F9 — Nowcast UI (P1)

Replace the two-charts-different-scales panel with: the headline nowcast, its error band, the accuracy table vs benchmarks, per-leg attribution, and coverage/provenance disclosure.

### F10 — Test coverage for the untested core (P0, cross-cutting)

`compute_index`, `group_summary`, `amazon_persist`, and the entire matcher (`_pick_best_match`, `_parse_unit`, `_title_matches_unit`, `_price_per_kg`) currently have **zero tests**. New pure modules are written test-first; the legacy core gets characterisation tests before it is changed.

## 7. Validation protocol

The protocol *is* the product claim. It is specified before any model is fitted, so results cannot be selected after the fact.

1. **Split:** walk-forward only. No fitting on data later than the prediction month.
2. **Regimes, constrained by what MOSPI permits linking.** This is not a stylistic choice — MOSPI states the two series link only at general-index level:

   | Leg | Pre-2026 backtest | Basis |
   |---|---|---|
   | Headline | **Available** | Official linked back series, General Index Jan-2013 → Dec-2024, Combined linking factor 0.5267 |
   | Food (CFPI) | **Not available across the break** | No linkable food series exists; CPI 2012 food and CPI 2024 F&B are different constructs |

   So the food leg is validated on the 2012-base era and the 2024-base era *separately*, never pooled. The headline leg can use the official linked series. Any pooled food statistic would be an artifact of our own linking assumption, not a measurement — we do not produce one.
3. **Benchmarks:** random walk, seasonal naive, AR(1) — all on the same splits.
4. **Reporting:** per-leg and combined. Point estimates always accompanied by error distribution.
5. **Publication rule:** if the revised methodology does not beat the benchmark out-of-sample, that is stated in the UI, not hidden.

## 8. Risk register

| Risk | Mitigation |
|---|---|
| **DoCA and CPI measure different instruments.** DoCA tracks modal retail prices at physical centres; MOSPI collects its own quotes and now includes online markets. Some tracking error is structural and will not optimize away. | The backtest quantifies the floor. If it is high, that is a finding we act on — possibly reweighting toward Amazon — not one we paper over. |
| Only ~7 months of 2024-base data for out-of-sample validation | Report it separately with wide bands and say so plainly. Track record lengthens monthly. |
| `fcainfoweb.nic.in` changes structure or goes down | Primary + fallback host; committed JSON cache means an outage degrades freshness, not availability. Issue-on-failure. |
| CEDA mirror unreachable from build environment | Not a dependency. Government source is primary. |
| Overfitting the nowcast on ~200 observations | Hard cap on parameters; walk-forward only; benchmark comparison mandatory. |
| Amazon anti-bot continues to block | Amazon is the overlay, not the backbone. DoCA carries 75.3% of basket weight. Core index survives total Amazon failure. |
| Repo growth from daily DoCA history | 13 items × ~250 bytes × 365 days ≈ 1.2 MB/year. Comparable to the existing 3.5 MB RBI corpus. Acceptable for a decade. |
| Scope: this PRD is larger than one session | Phased so each phase ships independently valuable. F1–F3 alone move the number and need no network. |

## 9. Cost & time analysis

**Token cost:** near zero. This is a deterministic-statistics PRD — no LLM calls in the index, nowcast, or backtest paths. The existing `ai/flash_brief.py` is untouched.

**Compute:** backfilling 17 years of daily DoCA prices for 13 items is ~80k rows — trivial for SQLite. Backtest over ~200 months with OLS is sub-second.

**Time to ship:**

| Feature | Active dev time | Critical path |
|---|---|---|
| F1 (formula) | ~1.5 hr | Pure math + tests. No network. |
| F2 (weights) | ~1 hr | Sourcing official weights is the long pole, not coding. |
| F3 (decomposer) | ~30 min | Small change, high value, adjacent bug. |
| F10 (characterisation tests) | ~1.5 hr | Should precede F1 so the change is provably safe. |
| F4 (DoCA ingestion) | ~3 hr | Parser shake-out against a government ASP.NET report page. Highest uncertainty. |
| F5 (group extraction) | ~2 hr | Existing parser already fragile; budget for surprises. |
| F7 (backtest) | ~2 hr | Straightforward once data lands. |
| F6 (nowcast) | ~2 hr | Fitting is quick; specifying it honestly is the work. |
| F8 (Amazon structure) | ~3 hr | Product identity is the hard part. |
| F9 (UI) | ~2 hr | |

**Recommended sequencing — today:** F10 → F1 → F2 → F3 (no network dependency, immediately measurable, ~4.5 hr). **Next:** F4 → F5 → F7, which is where an accuracy number first becomes provable. **Then:** F6 → F8 → F9.

## 10. Definition of done

**Phase 1 (F10, F1, F2, F3)**
- [ ] Characterisation tests pin current `compute_index` behaviour before it changes
- [ ] `index_formula.py` matches hand-computed Jevons/Young to 6dp
- [ ] Basket weights trace to a cited MOSPI source with base year and retrieval date in code
- [ ] `cpi_decomposer` selects weights by reference month, tested on both sides of the break
- [ ] Full suite green

**Phase 2 (F4, F5, F7)**
- [ ] Continuous daily DoCA series backfilled for all 13 covered items
- [ ] Cron refreshes incrementally; failure opens an issue
- [ ] Group-level CPI indices extracted, degrading per-division rather than wholesale
- [ ] Backtest emits current-vs-revised metrics table

**Phase 3 (F6, F8, F9)**
- [ ] Headline nowcast with error band and per-leg attribution
- [ ] Benchmarked against random walk / seasonal naive / AR(1), result published either way
- [ ] Amazon index uses pinned product identity and matched-sample chaining
- [ ] UI discloses coverage and provenance on every reading

## 11. Open questions

1. ~~**Official item-level weights**~~ — **resolved 2026-08-05.** All 12 division weights recovered from MOSPI's first 2024-base release (Annexure V Q39) and recorded in §4. Selected item weights are published in each monthly release. The full item list on `cpi.mospi.gov.in` remains unreachable from this environment; if it stays unreachable, basket item weights are renormalised within-division from the published items and the approximation is documented in `basket_weights.py` rather than silently assumed.
2. **DoCA centre selection** — national average, or Delhi (110001) to match the existing Amazon pincode? Matching the Amazon geography makes the two indices comparable; the national average tracks national CPI better. Recommend national for the backbone, Delhi as a diagnostic series.
3. **38-commodity expansion** — DoCA expanded from 22 to 38 monitored commodities. Whether the added items improve basket coverage enough to justify re-deriving weights is a Phase 2 question, answered with data.
4. **Amazon's weight in the published nowcast** — should be *fitted* once it has history, not asserted. Until then it is a diagnostic overlay, not a model input.
