# CPI Nowcast — Phase 1: Index Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Proprietary Pulse index a tested two-stage compilation structure (Jevons elementary → Young aggregation) and correct, provenance-carrying CPI 2024 weights, so later phases can measure tracking error against a sound base.

**Architecture:** Extract the index mathematics out of `engine/ecomm_index.py` into a pure, dependency-free `engine/index_formula.py`. Add `engine/basket_weights.py` holding official MOSPI CPI 2024 division and basket weights with source provenance. Make `engine/cpi_decomposer.py` select weights by reference month so pre- and post-Jan-2026 releases are decomposed on their own base. Every change is behaviour-preserving where it must be, and proven so by characterisation tests written *first*.

**Tech Stack:** Python 3.11, pytest, SQLite. No new dependencies. No network calls in this phase.

**Source of truth for all weights:** MOSPI, *First Press Release of Consumer Price Index on Base 2024=100*, dated 12 February 2026, Annexure V Q39 (division-wise weights) and Q40 (weight-shift decomposition).

**Run tests with `python3.11`** — the machine default `python3.14` has no dependencies installed.

---

## File Structure

| File | Responsibility |
|---|---|
| `systems/02-macro-pulse/engine/index_formula.py` | **Create.** Pure index mathematics: Jevons elementary, Young aggregation, matched-sample chaining. No imports from `db`, `scrapers`, or `engine.ecomm_basket`. |
| `systems/02-macro-pulse/engine/basket_weights.py` | **Create.** Official CPI 2024 weights + provenance metadata. Data only, no logic beyond renormalisation. |
| `systems/02-macro-pulse/engine/cpi_decomposer.py` | **Modify.** Base-aware weight selection by reference month. |
| `systems/02-macro-pulse/engine/ecomm_index.py` | **Modify.** `compute_index()` delegates arithmetic to `index_formula`. |
| `systems/02-macro-pulse/tests/test_ecomm_index.py` | **Create.** Characterisation tests pinning current behaviour before refactor. |
| `systems/02-macro-pulse/tests/test_index_formula.py` | **Create.** Hand-computed Jevons/Young/chaining values. |
| `systems/02-macro-pulse/tests/test_basket_weights.py` | **Create.** Weight sums, provenance presence, base-year lookup. |
| `systems/02-macro-pulse/tests/test_cpi_decomposer.py` | **Modify.** Add both-sides-of-the-break cases. |

`index_formula.py` deliberately imports nothing from the project. That is what makes it trivially testable and reusable by both the Amazon and DoCA indices in Phase 2.

---

### Task 1: Characterisation tests for existing `compute_index`

Pin current behaviour *before* touching it, so the refactor in Task 7 is provably behaviour-preserving. These tests encode what the code does today — including the composition-effect defect, which is documented here as a known-wrong behaviour and fixed in a later phase, not now.

> **Revised during execution (commit `378cae9`).** Code review found the original 8 tests inadequate as a refactor safety net, and four were added — final count **12**:
> - `test_group_summary_weights_items_within_a_group` — the original group test used two items with the *same* pct_change, so a weighted mean was indistinguishable from an unweighted one. The new test uses rice (wt 14.0) +10% and atta (wt 12.3) +20% → **14.68**, where a plain mean gives 15.0. Task 7 extracts exactly this arithmetic, so the gap mattered.
> - `test_component_dict_has_expected_shape_and_values` — pins the full component dict, whose fields `ui/ecomm_view.py` consumes.
> - `test_components_sorted_by_cpi_group_and_groups_by_change_desc` and `test_group_summary_of_empty_components_is_empty` — pin sort order and empty-input behaviour.
>
> The module docstring below says "Two of these encode known defects"; only one does. Corrected in the committed file to say "One".

**Files:**
- Test: `systems/02-macro-pulse/tests/test_ecomm_index.py`

- [ ] **Step 1: Write the characterisation tests**

```python
"""
Characterisation tests for engine/ecomm_index.compute_index.

These pin CURRENT behaviour so the Task 7 refactor can be proven
behaviour-preserving. Two of these encode known defects (documented in
docs/PRD-2026-08-cpi-nowcast-index-rebuild.md) and are expected to be
UPDATED — deliberately, with a commit that says so — when those defects
are fixed in a later phase. They are not aspirational tests.
"""
import pytest

from engine.ecomm_index import compute_index, group_summary


def _rows(prices: dict) -> list[dict]:
    """Build price rows shaped like EcommStore.get_latest_prices() output."""
    return [
        {"item_id": iid, "price": p, "price_per_kg": None}
        for iid, p in prices.items()
    ]


def test_all_items_flat_gives_index_100():
    base = {"rice": 100.0, "atta": 100.0}
    result = compute_index(_rows({"rice": 100.0, "atta": 100.0}), base)
    assert result["index_value"] == 100.0
    assert result["coverage_pct"] == pytest.approx(26.3 / 100.1 * 100, abs=0.1)
    assert result["items_count"] == 2


def test_uniform_ten_percent_rise_gives_index_110():
    base = {"rice": 100.0, "atta": 100.0}
    result = compute_index(_rows({"rice": 110.0, "atta": 110.0}), base)
    assert result["index_value"] == 110.0


def test_price_per_kg_preferred_over_raw_price():
    base = {"rice": 20.0}
    rows = [{"item_id": "rice", "price": 500.0, "price_per_kg": 22.0}]
    result = compute_index(rows, base)
    # 22.0 / 20.0 = 1.10 -> 110.0, NOT 500/20
    assert result["index_value"] == 110.0


def test_item_missing_from_base_is_skipped():
    base = {"rice": 100.0}
    result = compute_index(_rows({"rice": 110.0, "atta": 105.0}), base)
    assert result["items_count"] == 1
    assert result["index_value"] == 110.0


def test_zero_base_price_is_skipped():
    base = {"rice": 100.0, "atta": 0.0}
    result = compute_index(_rows({"rice": 110.0, "atta": 105.0}), base)
    assert result["items_count"] == 1


def test_no_overlap_returns_none_index():
    result = compute_index(_rows({"rice": 110.0}), {})
    assert result["index_value"] is None
    assert result["coverage_pct"] == 0.0
    assert result["items_count"] == 0
    assert result["components"] == []


def test_KNOWN_DEFECT_coverage_change_shifts_index_with_no_price_change():
    """
    DEFECT (PRD 0): the index renormalises over matched weight, so an item
    dropping out moves the level even when no price moved. Fixed by
    matched-sample chaining in a later phase; pinned here so the Task 7
    refactor does not silently alter it.
    """
    base = {"rice": 100.0, "atta": 100.0, "onion": 100.0}
    # rice flat, others +10%
    all_present = compute_index(
        _rows({"rice": 100.0, "atta": 110.0, "onion": 110.0}), base
    )
    rice_missing = compute_index(
        _rows({"atta": 110.0, "onion": 110.0}), base
    )
    assert all_present["index_value"] < rice_missing["index_value"]
    assert rice_missing["index_value"] == 110.0


def test_group_summary_rolls_up_by_cpi_group():
    base = {"rice": 100.0, "atta": 100.0, "onion": 100.0}
    result = compute_index(
        _rows({"rice": 110.0, "atta": 110.0, "onion": 120.0}), base
    )
    groups = {g["cpi_group"]: g for g in group_summary(result["components"])}
    assert groups["Cereals"]["avg_pct_change"] == pytest.approx(10.0, abs=0.01)
    assert groups["Vegetables"]["avg_pct_change"] == pytest.approx(20.0, abs=0.01)
    assert groups["Cereals"]["item_count"] == 2
```

- [ ] **Step 2: Run the tests to verify they pass against current code**

```bash
cd systems/02-macro-pulse && PYTHONPATH=. python3.11 -m pytest tests/test_ecomm_index.py -v
```

Expected: **12 passed** (8 as originally written, plus the 4 added during review — see the revision note above). These describe existing behaviour, so they must pass immediately. If any fails, the assumption about current behaviour is wrong — stop and investigate before continuing.

- [ ] **Step 3: Commit**

```bash
git add systems/02-macro-pulse/tests/test_ecomm_index.py
git commit -m "test(macro-pulse): characterise compute_index before refactor"
```

---

### Task 2: Jevons elementary index

**Files:**
- Create: `systems/02-macro-pulse/engine/index_formula.py`
- Test: `systems/02-macro-pulse/tests/test_index_formula.py`

- [ ] **Step 1: Write the failing test**

```python
import math

import pytest

from engine.index_formula import jevons_elementary


def test_single_quote_returns_its_own_ratio():
    # With one quote, Jevons degenerates to that quote's ratio.
    assert jevons_elementary([110.0], [100.0]) == pytest.approx(1.10)


def test_two_quotes_geometric_mean_of_relatives():
    # relatives 1.10 and 1.20 -> sqrt(1.32) = 1.148912529...
    result = jevons_elementary([110.0, 120.0], [100.0, 100.0])
    assert result == pytest.approx(math.sqrt(1.32), abs=1e-9)


def test_three_quotes_hand_computed():
    # 110/100=1.10, 118/105=1.123809..., 99/95=1.042105...
    # GM = exp((ln1.10 + ln1.1238095 + ln1.0421053)/3)
    result = jevons_elementary([110.0, 118.0, 99.0], [100.0, 105.0, 95.0])
    assert result == pytest.approx(1.088092, abs=1e-6)


def test_geometric_mean_is_at_most_arithmetic_mean():
    current = [110.0, 150.0, 90.0]
    base = [100.0, 100.0, 100.0]
    gm = jevons_elementary(current, base)
    am = sum(c / b for c, b in zip(current, base)) / len(current)
    assert gm <= am


def test_non_positive_quotes_are_excluded():
    # zero and negative prices carry no information and break log()
    assert jevons_elementary([110.0, 0.0], [100.0, 100.0]) == pytest.approx(1.10)
    assert jevons_elementary([110.0, -5.0], [100.0, 100.0]) == pytest.approx(1.10)
    assert jevons_elementary([110.0, 120.0], [100.0, 0.0]) == pytest.approx(1.10)


def test_length_mismatch_raises():
    with pytest.raises(ValueError, match="same length"):
        jevons_elementary([110.0, 120.0], [100.0])


def test_no_usable_pairs_raises():
    with pytest.raises(ValueError, match="no usable"):
        jevons_elementary([0.0], [100.0])
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd systems/02-macro-pulse && PYTHONPATH=. python3.11 -m pytest tests/test_index_formula.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'engine.index_formula'`

- [ ] **Step 3: Write the implementation**

```python
"""
Index mathematics for CPI-tracking price indices.

Mirrors MOSPI's CPI 2024 two-stage compilation (source: MOSPI First Press
Release of CPI on Base 2024=100, 12 Feb 2026, Annexure V Q20-Q21):

  Stage 1 (elementary):  Jevons  — geometric mean of price relatives
                                   across the quotes for a single item.
  Stage 2 (aggregation): Young / modified Laspeyres — weighted arithmetic
                                   mean of elementary indices.

This module is deliberately free of project imports so it can be tested in
isolation and reused by both the Amazon and DoCA index builders.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence


def jevons_elementary(
    current: Sequence[float],
    base: Sequence[float],
) -> float:
    """
    Geometric mean of price relatives — the Jevons elementary index.

    `current` and `base` are parallel sequences of price quotes for ONE
    item. Pairs where either price is non-positive are excluded: they carry
    no price-change information and log() is undefined on them.

    Returns a ratio (1.10 == a 10% rise), not an index level.

    Note: Jevons is only meaningful over a STABLE quote set. Averaging
    relatives of products that changed between periods measures
    substitution, not inflation.
    """
    if len(current) != len(base):
        raise ValueError(
            f"current and base must be the same length, "
            f"got {len(current)} and {len(base)}"
        )

    log_relatives = [
        math.log(c / b)
        for c, b in zip(current, base)
        if c > 0 and b > 0
    ]
    if not log_relatives:
        raise ValueError("no usable quote pairs (all non-positive)")

    return math.exp(sum(log_relatives) / len(log_relatives))
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd systems/02-macro-pulse && PYTHONPATH=. python3.11 -m pytest tests/test_index_formula.py -v
```

Expected: **7 passed**

- [ ] **Step 5: Commit**

```bash
git add systems/02-macro-pulse/engine/index_formula.py systems/02-macro-pulse/tests/test_index_formula.py
git commit -m "feat(macro-pulse): add Jevons elementary index"
```

---

### Task 3: Young aggregation

**Files:**
- Modify: `systems/02-macro-pulse/engine/index_formula.py`
- Test: `systems/02-macro-pulse/tests/test_index_formula.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_index_formula.py`:

```python
from engine.index_formula import young_aggregate


def test_young_uniform_rise():
    relatives = {"rice": 1.10, "atta": 1.10}
    weights = {"rice": 14.0, "atta": 12.3}
    assert young_aggregate(relatives, weights) == pytest.approx(110.0)


def test_young_hand_computed_weighted_mean():
    # (14.0*1.10 + 12.3*1.05 + 5.5*1.40) / (14.0+12.3+5.5) * 100
    # = (15.40 + 12.915 + 7.70) / 31.8 * 100 = 113.2547169...
    relatives = {"rice": 1.10, "atta": 1.05, "onion": 1.40}
    weights = {"rice": 14.0, "atta": 12.3, "onion": 5.5}
    assert young_aggregate(relatives, weights) == pytest.approx(113.254717, abs=1e-6)


def test_young_ignores_relatives_without_weights():
    relatives = {"rice": 1.10, "unknown_item": 99.0}
    weights = {"rice": 14.0}
    assert young_aggregate(relatives, weights) == pytest.approx(110.0)


def test_young_ignores_weights_without_relatives():
    relatives = {"rice": 1.10}
    weights = {"rice": 14.0, "atta": 12.3}
    assert young_aggregate(relatives, weights) == pytest.approx(110.0)


def test_young_zero_total_weight_raises():
    with pytest.raises(ValueError, match="zero total weight"):
        young_aggregate({"rice": 1.10}, {"rice": 0.0})


def test_young_empty_raises():
    with pytest.raises(ValueError, match="zero total weight"):
        young_aggregate({}, {})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd systems/02-macro-pulse && PYTHONPATH=. python3.11 -m pytest tests/test_index_formula.py -v -k young
```

Expected: FAIL — `ImportError: cannot import name 'young_aggregate'`

- [ ] **Step 3: Write the implementation**

Append to `engine/index_formula.py`:

```python
def young_aggregate(
    relatives: Mapping[str, float],
    weights: Mapping[str, float],
) -> float:
    """
    Young / modified Laspeyres aggregation — weighted arithmetic mean of
    elementary price relatives, expressed as an index level (base = 100).

    Only keys present in BOTH mappings contribute. A relative with no
    weight cannot be aggregated; a weight with no relative has nothing to
    contribute this period.

    Returns an index level (110.0 == 10% above base).
    """
    shared = relatives.keys() & weights.keys()

    total_weight = sum(weights[k] for k in shared)
    if total_weight <= 0:
        raise ValueError("zero total weight — nothing to aggregate")

    weighted = sum(weights[k] * relatives[k] for k in shared)
    return (weighted / total_weight) * 100.0
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd systems/02-macro-pulse && PYTHONPATH=. python3.11 -m pytest tests/test_index_formula.py -v
```

Expected: **13 passed**

- [ ] **Step 5: Commit**

```bash
git add systems/02-macro-pulse/engine/index_formula.py systems/02-macro-pulse/tests/test_index_formula.py
git commit -m "feat(macro-pulse): add Young aggregation to index_formula"
```

---

### Task 4: Matched-sample chain linking

Computes period-over-period movement using only items present in **both** periods, then chains onto the previous level. This is the mechanism that will eliminate the composition defect pinned in Task 1. It is built and tested now; wiring it into `compute_index` happens in a later phase alongside product identity.

> **Revised during execution (commit `07f0794`).** The signature below returns a bare `float`. Code review correctly identified that as a PRD violation — §2 requires that the app "never present an index reading whose coverage or provenance is undisclosed," and a bare float makes "prices were flat" indistinguishable from "the matched sample collapsed and nothing was measured." A scraper outage would have rendered as price stability.
>
> `chain_link` now returns a frozen `ChainResult(level, matched, eligible)` with `coverage_pct` and `has_matched_sample` properties, and delegates its weighted mean to `young_aggregate` rather than duplicating the formula. Six tests were added covering the positivity-filter branch, which had zero coverage. Final count for this file: **25 tests**.
>
> Two review findings were **rejected**, with the reasons recorded as comments in the source so they are not re-litigated: filtering non-positive weights in `young_aggregate` (would risk Task 7's byte-identical contract for no real-world gain), and switching to `log(c) - log(b)` (identical precision at realistic ratios; upstream bounds prices to (0, 100000] so the overflow it guards against is unreachable).

**Files:**
- Modify: `systems/02-macro-pulse/engine/index_formula.py`
- Test: `systems/02-macro-pulse/tests/test_index_formula.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_index_formula.py`:

```python
from engine.index_formula import chain_link


def test_chain_link_uniform_rise():
    prev_prices = {"rice": 100.0, "atta": 100.0}
    curr_prices = {"rice": 110.0, "atta": 110.0}
    weights = {"rice": 14.0, "atta": 12.3}
    assert chain_link(100.0, curr_prices, prev_prices, weights) == pytest.approx(110.0)


def test_chain_link_compounds_onto_previous_level():
    prev_prices = {"rice": 110.0}
    curr_prices = {"rice": 121.0}
    weights = {"rice": 14.0}
    # previous level 110, this period +10% -> 121
    assert chain_link(110.0, curr_prices, prev_prices, weights) == pytest.approx(121.0)


def test_chain_link_ignores_item_missing_this_period():
    """
    THE FIX for the Task 1 defect: rice absent this period must not move
    the level, because the matched sample excludes it entirely.
    """
    prev_prices = {"rice": 100.0, "atta": 100.0}
    curr_prices = {"atta": 100.0}          # atta flat, rice absent
    weights = {"rice": 14.0, "atta": 12.3}
    assert chain_link(100.0, curr_prices, prev_prices, weights) == pytest.approx(100.0)


def test_chain_link_ignores_item_new_this_period():
    prev_prices = {"atta": 100.0}
    curr_prices = {"atta": 100.0, "rice": 500.0}   # rice brand new
    weights = {"rice": 14.0, "atta": 12.3}
    assert chain_link(100.0, curr_prices, prev_prices, weights) == pytest.approx(100.0)


def test_chain_link_no_overlap_returns_previous_level_unchanged():
    # Nothing matched: we know nothing about price change, so hold the level.
    assert chain_link(107.5, {"rice": 110.0}, {"atta": 100.0}, {"rice": 1.0}) == 107.5


def test_chain_link_weighted_partial_movement():
    # rice +10% (wt 14.0), atta flat (wt 12.3), both matched
    # movement = (14.0*1.10 + 12.3*1.00)/26.3 = 1.053231939...
    prev_prices = {"rice": 100.0, "atta": 100.0}
    curr_prices = {"rice": 110.0, "atta": 100.0}
    weights = {"rice": 14.0, "atta": 12.3}
    assert chain_link(100.0, curr_prices, prev_prices, weights) == pytest.approx(
        105.3231939, abs=1e-6
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd systems/02-macro-pulse && PYTHONPATH=. python3.11 -m pytest tests/test_index_formula.py -v -k chain
```

Expected: FAIL — `ImportError: cannot import name 'chain_link'`

- [ ] **Step 3: Write the implementation**

Append to `engine/index_formula.py`:

```python
def chain_link(
    previous_level: float,
    current_prices: Mapping[str, float],
    previous_prices: Mapping[str, float],
    weights: Mapping[str, float],
) -> float:
    """
    Chain the index forward one period using a matched sample.

    Only items priced in BOTH periods contribute. This is what prevents
    coverage changes from masquerading as price changes: an item that
    drops out is excluded from both the numerator and the denominator of
    the movement, so it cannot shift the level.

    If nothing matched, we have learned nothing about price change this
    period and the previous level is returned unchanged.
    """
    matched = (
        current_prices.keys()
        & previous_prices.keys()
        & weights.keys()
    )
    matched = {
        k for k in matched
        if current_prices[k] > 0 and previous_prices[k] > 0 and weights[k] > 0
    }
    if not matched:
        return previous_level

    total_weight = sum(weights[k] for k in matched)
    movement = sum(
        weights[k] * (current_prices[k] / previous_prices[k])
        for k in matched
    ) / total_weight

    return previous_level * movement
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd systems/02-macro-pulse && PYTHONPATH=. python3.11 -m pytest tests/test_index_formula.py -v
```

Expected: **25 passed** (19 as originally written, plus 6 added during review — see the revision note above)

- [ ] **Step 5: Commit**

```bash
git add systems/02-macro-pulse/engine/index_formula.py systems/02-macro-pulse/tests/test_index_formula.py
git commit -m "feat(macro-pulse): add matched-sample chain linking"
```

---

### Task 5: Official CPI 2024 weights with provenance

**Files:**
- Create: `systems/02-macro-pulse/engine/basket_weights.py`
- Test: `systems/02-macro-pulse/tests/test_basket_weights.py`

- [ ] **Step 1: Write the failing test**

```python
import pytest

from engine.basket_weights import (
    CPI_2024_DIVISIONS,
    CPI_2012_DIVISIONS,
    CPI_FOOD_WEIGHT,
    CPI_NONFOOD_WEIGHT,
    PROVENANCE,
    food_weight_for_month,
)


def test_2024_divisions_sum_to_100():
    assert sum(CPI_2024_DIVISIONS.values()) == pytest.approx(100.0, abs=0.01)


def test_2012_divisions_sum_to_100():
    assert sum(CPI_2012_DIVISIONS.values()) == pytest.approx(100.0, abs=0.01)


def test_food_and_nonfood_weights_are_complementary():
    assert CPI_FOOD_WEIGHT + CPI_NONFOOD_WEIGHT == pytest.approx(1.0, abs=1e-9)


def test_food_weight_matches_official_division_share():
    assert CPI_FOOD_WEIGHT == pytest.approx(
        CPI_2024_DIVISIONS["food_and_beverages"] / 100.0, abs=1e-9
    )
    assert CPI_FOOD_WEIGHT == pytest.approx(0.36753, abs=1e-9)


def test_all_twelve_coicop_divisions_present():
    assert len(CPI_2024_DIVISIONS) == 12


def test_provenance_is_recorded():
    assert PROVENANCE["base_year"] == "2024"
    assert PROVENANCE["effective_from"] == "2026-01"
    assert "mospi.gov.in" in PROVENANCE["source_url"]
    assert PROVENANCE["retrieved_on"] == "2026-08-05"


def test_food_weight_for_month_selects_by_base_era():
    # 2024=100 series is effective from Jan 2026
    assert food_weight_for_month("2026-01") == pytest.approx(0.36753, abs=1e-9)
    assert food_weight_for_month("2026-07") == pytest.approx(0.36753, abs=1e-9)
    # earlier months use the 2012 series weight
    assert food_weight_for_month("2025-12") == pytest.approx(0.4586, abs=1e-9)
    assert food_weight_for_month("2024-06") == pytest.approx(0.4586, abs=1e-9)


def test_food_weight_for_month_rejects_malformed_input():
    with pytest.raises(ValueError, match="YYYY-MM"):
        food_weight_for_month("June 2026")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd systems/02-macro-pulse && PYTHONPATH=. python3.11 -m pytest tests/test_basket_weights.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'engine.basket_weights'`

- [ ] **Step 3: Write the implementation**

```python
"""
Official MOSPI CPI weights, with provenance.

Source: MOSPI, "First Press Release of Consumer Price Index on Base
2024=100", dated 12 February 2026, Annexure V Q39 (division-wise weights,
Combined sector).

Both weight sets below are expressed on the COICOP 2018 division structure
so they are directly comparable. Note that the widely-quoted "45.86% ->
36.75%" fall in the food share conflates two effects (Annexure V Q40):

  45.86% -> 40.10%   genuine expenditure shift, CPI 2012 classification
  42.62% -> 36.75%   genuine expenditure shift, COICOP 2018 classification
  40.10% vs 36.75%   reclassification only, chiefly restaurants and
                     accommodation splitting into their own division

CPI_2012_FOOD_WEIGHT below is the headline 45.86% figure, because that is
what the CPI 2012 series itself published and therefore what any pre-2026
release must be decomposed with.
"""
from __future__ import annotations

import re

PROVENANCE = {
    "base_year": "2024",
    "effective_from": "2026-01",
    "weight_reference": "HCES 2023-24",
    "price_reference": "calendar year 2024",
    "classification": "COICOP 2018",
    "sector": "Combined",
    "source_url": (
        "https://www.mospi.gov.in/uploads/latestReleases/"
        "latest_release_1770891893893_6b458c0a-c327-4fef-a554-41131ea67273_"
        "Press_Relase_of_CPI_for_Jan26.pdf"
    ),
    "source_note": "Annexure V Q39, division-wise weights, Combined",
    "retrieved_on": "2026-08-05",
}

# Division-wise weights, Combined sector, COICOP 2018 structure (% of index).
CPI_2024_DIVISIONS: dict[str, float] = {
    "food_and_beverages":                36.753,
    "paan_tobacco_and_intoxicants":       2.989,
    "clothing_and_footwear":              6.383,
    "housing_water_electricity_gas_fuel": 17.665,
    "furnishings_household_equipment":     4.469,
    "health":                              6.100,
    "transport":                           8.796,
    "information_and_communication":       3.609,
    "recreation_sport_and_culture":        1.516,
    "education_services":                  3.333,
    "restaurants_and_accommodation":       3.348,
    "personal_care_and_misc":              5.038,
}

# The same divisions valued on the CPI 2012 series, for like-for-like
# comparison. Source: same table, "CPI 2012" column.
CPI_2012_DIVISIONS: dict[str, float] = {
    "food_and_beverages":                42.617,
    "paan_tobacco_and_intoxicants":       2.380,
    "clothing_and_footwear":              6.527,
    "housing_water_electricity_gas_fuel": 16.888,
    "furnishings_household_equipment":     3.656,
    "health":                              5.900,
    "transport":                           6.394,
    "information_and_communication":       3.323,
    "recreation_sport_and_culture":        1.547,
    "education_services":                  3.513,
    "restaurants_and_accommodation":       3.246,
    "personal_care_and_misc":              4.006,
}

# Headline food share as published by each series, for decomposition.
CPI_FOOD_WEIGHT = CPI_2024_DIVISIONS["food_and_beverages"] / 100.0   # 0.36753
CPI_NONFOOD_WEIGHT = 1.0 - CPI_FOOD_WEIGHT                            # 0.63247

# CPI 2012 series as it was actually published (group structure, not COICOP).
CPI_2012_FOOD_WEIGHT = 0.4586
CPI_2012_FUEL_WEIGHT = 0.0684

# First reference month compiled on the 2024=100 series.
BASE_2024_FIRST_MONTH = "2026-01"

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def food_weight_for_month(reference_month: str) -> float:
    """
    Return the food weight appropriate to a release's reference month.

    MOSPI switched to 2024=100 from January 2026. Decomposing a pre-2026
    release with 2024 weights (or vice versa) misattributes the food
    contribution, so the base era must follow the data, not the clock.
    """
    if not _MONTH_RE.match(reference_month or ""):
        raise ValueError(
            f"reference_month must be YYYY-MM, got {reference_month!r}"
        )
    if reference_month >= BASE_2024_FIRST_MONTH:
        return CPI_FOOD_WEIGHT
    return CPI_2012_FOOD_WEIGHT
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd systems/02-macro-pulse && PYTHONPATH=. python3.11 -m pytest tests/test_basket_weights.py -v
```

Expected: **8 passed**

- [ ] **Step 5: Commit**

```bash
git add systems/02-macro-pulse/engine/basket_weights.py systems/02-macro-pulse/tests/test_basket_weights.py
git commit -m "feat(macro-pulse): add official CPI 2024 weights with provenance"
```

---

### Task 6: Base-aware CPI decomposer

Fixes the live defect: `cpi_decomposer.py` applies CPI 2012 weights to every release, including 2026 releases compiled on 2024=100.

**Files:**
- Modify: `systems/02-macro-pulse/engine/cpi_decomposer.py`
- Test: `systems/02-macro-pulse/tests/test_cpi_decomposer.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cpi_decomposer.py`:

```python
import pytest

from engine.cpi_decomposer import decompose_cpi


def test_pre_2026_month_uses_2012_food_weight():
    result = decompose_cpi(
        headline=5.0, food_yoy=6.0, fuel_yoy=3.0, reference_month="2025-12"
    )
    # 6.0 * 0.4586 = 2.7516 -> 2.75
    assert result["food_contrib"] == pytest.approx(2.75, abs=0.01)
    assert result["base_year"] == "2012"


def test_2026_month_uses_2024_food_weight():
    result = decompose_cpi(
        headline=5.0, food_yoy=6.0, fuel_yoy=3.0, reference_month="2026-01"
    )
    # 6.0 * 0.36753 = 2.20518 -> 2.21
    assert result["food_contrib"] == pytest.approx(2.21, abs=0.01)
    assert result["base_year"] == "2024"


def test_food_contribution_is_lower_under_new_base():
    old = decompose_cpi(5.0, 6.0, 3.0, reference_month="2025-12")
    new = decompose_cpi(5.0, 6.0, 3.0, reference_month="2026-01")
    assert new["food_contrib"] < old["food_contrib"]


def test_omitting_reference_month_defaults_to_2012_base():
    # Backwards compatibility: existing callers pass three positional args.
    result = decompose_cpi(5.0, 6.0, 3.0)
    assert result["base_year"] == "2012"
    assert result["food_contrib"] == pytest.approx(2.75, abs=0.01)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd systems/02-macro-pulse && PYTHONPATH=. python3.11 -m pytest tests/test_cpi_decomposer.py -v
```

Expected: FAIL — `TypeError: decompose_cpi() got an unexpected keyword argument 'reference_month'`

- [ ] **Step 3: Write the implementation**

Replace the body of `engine/cpi_decomposer.py` with:

```python
from dataclasses import dataclass
from typing import Optional

from engine.basket_weights import (
    CPI_2012_FOOD_WEIGHT,
    CPI_2012_FUEL_WEIGHT,
    CPI_FOOD_WEIGHT,
    food_weight_for_month,
)


@dataclass(frozen=True)
class _CPIWeights:
    """CPI 2012 base year weights (share of total index)."""
    FOOD: float = CPI_2012_FOOD_WEIGHT
    FUEL: float = CPI_2012_FUEL_WEIGHT
    CORE: float = 1.0 - CPI_2012_FOOD_WEIGHT - CPI_2012_FUEL_WEIGHT


CPIWeights = _CPIWeights()


def decompose_cpi(
    headline: float,
    food_yoy: float,
    fuel_yoy: float,
    reference_month: Optional[str] = None,
) -> dict:
    """
    Decompose headline CPI into food, fuel, and core contributions.

    Core is residual: core_contrib = headline - food_contrib - fuel_contrib.
    This matches how RBI MPC staff decompose inflation in policy documents.

    `reference_month` ("YYYY-MM") selects the weight base. MOSPI moved to
    2024=100 from January 2026, cutting the food share from 45.86% to
    36.753%; decomposing a 2026 release on 2012 weights overstates the food
    contribution by roughly a quarter and dumps the error into core.

    Omitting `reference_month` assumes the 2012 base, preserving the
    behaviour of existing callers.

    Note: under 2024=100 MOSPI replaced "Fuel & Light" with "Housing, water,
    electricity, gas and other fuels", so `fuel_yoy` is frequently absent
    for post-2026 releases. The 2012 fuel weight is retained for the fuel
    term because no like-for-like 2024 equivalent exists; when fuel_yoy is
    unavailable the caller should not rely on the fuel/core split.
    """
    if reference_month is None:
        food_weight = CPI_2012_FOOD_WEIGHT
        base_year = "2012"
    else:
        food_weight = food_weight_for_month(reference_month)
        base_year = "2024" if food_weight == CPI_FOOD_WEIGHT else "2012"

    fuel_weight = CPI_2012_FUEL_WEIGHT
    core_weight = 1.0 - food_weight - fuel_weight

    food_contrib = round(food_yoy * food_weight, 2)
    fuel_contrib = round(fuel_yoy * fuel_weight, 2)
    core_contrib = round(headline - food_contrib - fuel_contrib, 2)
    core_yoy = round(core_contrib / core_weight, 2)

    contribs = {
        "food": abs(food_contrib),
        "fuel": abs(fuel_contrib),
        "core": abs(core_contrib),
    }
    dominant_driver = max(contribs, key=contribs.get)

    return {
        "headline_yoy": headline,
        "food_yoy": food_yoy,
        "fuel_yoy": fuel_yoy,
        "core_yoy": core_yoy,
        "food_contrib": food_contrib,
        "fuel_contrib": fuel_contrib,
        "core_contrib": core_contrib,
        "dominant_driver": dominant_driver,
        "base_year": base_year,
    }
```

- [ ] **Step 4: Run the full suite to verify nothing regressed**

```bash
cd systems/02-macro-pulse && PYTHONPATH=. python3.11 -m pytest -v
```

Expected: all previously passing tests still pass, plus the 4 new ones. If an existing `test_cpi_decomposer.py` test asserted on the returned dict's exact keys, it will need the new `base_year` key added — update it and note that in the commit.

- [ ] **Step 5: Commit**

```bash
git add systems/02-macro-pulse/engine/cpi_decomposer.py systems/02-macro-pulse/tests/test_cpi_decomposer.py
git commit -m "fix(macro-pulse): decompose CPI on the release's own weight base"
```

---

### Task 7: Delegate `compute_index` aggregation to `index_formula`

Behaviour-preserving refactor. Task 1's characterisation tests are the proof.

**Files:**
- Modify: `systems/02-macro-pulse/engine/ecomm_index.py:19-77`
- Test: `systems/02-macro-pulse/tests/test_ecomm_index.py` (must pass unchanged)

**Critical detail:** `components[*]["price_ratio"]` is `round(ratio, 4)`, but the existing `numerator` accumulates the **unrounded** ratio. Building `relatives` from `price_ratio` would therefore change results at rounding boundaries. Collect the unrounded ratio separately.

- [ ] **Step 1: Add the import**

At the top of `engine/ecomm_index.py`, below the existing `from engine.ecomm_basket import BASKET`:

```python
from engine.index_formula import young_aggregate
```

- [ ] **Step 2: Collect unrounded relatives in the accumulation loop**

Inside `compute_index`, replace the accumulator initialisation:

```python
    numerator = 0.0
    denominator = 0.0
    components = []
```

with:

```python
    relatives: dict[str, float] = {}
    item_weights: dict[str, float] = {}
    denominator = 0.0
    components = []
```

Then in the per-item loop, replace:

```python
        numerator   += w * ratio
        denominator += w
```

with:

```python
        relatives[iid]    = ratio      # unrounded — rounding happens at the end
        item_weights[iid] = w
        denominator      += w
```

- [ ] **Step 3: Replace the aggregation block**

Replace the block from `if denominator == 0:` through the final `return` of `compute_index` with:

```python
    if denominator == 0:
        return {
            "index_value":   None,
            "coverage_pct":  0.0,
            "items_count":   0,
            "components":    [],
        }

    index = young_aggregate(relatives, item_weights)
    coverage = (denominator / total_weight) * 100.0

    return {
        "index_value":   round(index, 2),
        "coverage_pct":  round(coverage, 1),
        "items_count":   len(components),
        "components":    sorted(components, key=lambda x: x["cpi_group"]),
    }
```

The `if denominator == 0:` guard is kept verbatim rather than swapped for `if not components:`. They differ if any basket weight is ever zero, and this refactor must change nothing.

- [ ] **Step 4: Run the characterisation tests**

```bash
cd systems/02-macro-pulse && PYTHONPATH=. python3.11 -m pytest tests/test_ecomm_index.py -v
```

Expected: **12 passed** — identical to Task 1. Any failure means the refactor changed behaviour and must be reverted, not accommodated.

- [ ] **Step 5: Run the full suite**

```bash
cd systems/02-macro-pulse && PYTHONPATH=. python3.11 -m pytest -q
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add systems/02-macro-pulse/engine/ecomm_index.py
git commit -m "refactor(macro-pulse): compute_index delegates to index_formula"
```

---

### Task 8: Phase 1 verification

- [ ] **Step 1: Run the complete suite for both systems**

```bash
cd systems/02-macro-pulse && PYTHONPATH=. python3.11 -m pytest -q
```

Expected: **≥ 127 passed** (78 pre-existing + 12 characterisation + 25 formula + 8 weights + 4 decomposer, minus any consolidated).

```bash
cd systems/01-rbi-comms && PYTHONPATH=. python3.11 -m pytest -q
```

Expected: **141 passed** — unchanged; this phase does not touch rbi-comms.

- [ ] **Step 2: Confirm the decomposer fix is visible end to end**

```bash
cd systems/02-macro-pulse && PYTHONPATH=. python3.11 -c "
from engine.cpi_decomposer import decompose_cpi
old = decompose_cpi(4.38, 5.32, 0.0, reference_month='2025-12')
new = decompose_cpi(4.38, 5.32, 0.0, reference_month='2026-05')
print(f\"2025-12 (base {old['base_year']}): food_contrib={old['food_contrib']} core_contrib={old['core_contrib']}\")
print(f\"2026-05 (base {new['base_year']}): food_contrib={new['food_contrib']} core_contrib={new['core_contrib']}\")
"
```

Expected output:
```
2025-12 (base 2012): food_contrib=2.44 core_contrib=1.94
2026-05 (base 2024): food_contrib=1.96 core_contrib=2.42
```

This uses the real May-2026 CPI print (headline 4.38, food 5.32) from `data/release_updates.json` and shows the misattribution the fix corrects: roughly 0.5pp of contribution moving from food to core.

- [ ] **Step 3: Commit any remaining changes**

```bash
git add -A systems/02-macro-pulse
git commit -m "chore(macro-pulse): phase 1 index foundations complete"
```

---

## What Phase 1 deliberately does not do

- **No network calls.** DoCA ingestion is Phase 2.
- **No behaviour change to the live index level.** Task 7 is provably behaviour-preserving. `chain_link` and `jevons_elementary` are built and tested but not yet wired into `compute_index` — that lands with product identity in Phase 3, because Jevons over an unstable quote set would be worse than what we have now.
- **No accuracy claim.** Nothing here can be validated against CPI until Phase 2 supplies the backtest substrate. Phase 1 makes the foundation correct; Phase 3 makes it measurable.

## Follow-on plans

| Plan | Covers |
|---|---|
| Phase 2 | F4 DoCA ingestion, F5 MOSPI group-level extraction, schema changes |
| Phase 3 | F7 backtest harness, F8 product identity + chaining wire-up, F6 nowcast model |
| Phase 4 | F9 nowcast UI |
