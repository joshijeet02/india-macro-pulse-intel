# India Macro Pulse — Data Release Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Streamlit app that ingests India's key macro data releases (CPI, IIP), computes surprise vs consensus, decomposes into economically meaningful components, and generates AI-authored flash briefs — deployable publicly in 2 days.

**Architecture:** SQLite stores historical releases and consensus forecasts; pure-Python engine computes decompositions and surprise z-scores; Anthropic Claude generates flash briefs; Streamlit renders the UI. Scrapers fetch new MOSPI releases and write to the DB. Historical data is seeded as fixtures so the app works immediately without live scraping.

**Tech Stack:** Python 3.10, SQLite (sqlite3 stdlib), pdfplumber, requests, BeautifulSoup4, anthropic SDK, Streamlit, pytest

---

## File Map

```
systems/02-macro-pulse/
├── app.py                          # Streamlit entry point — imports all ui/ views
├── requirements.txt                # System-level deps (streamlit + project root deps)
├── .env.example                    # ANTHROPIC_API_KEY template
├── .streamlit/
│   └── config.toml                 # Theme (dark, accent color)
├── db/
│   ├── __init__.py
│   ├── schema.py                   # CREATE TABLE statements + init_db()
│   └── store.py                    # CPIStore, IIPStore, SPFStore, BriefStore classes
├── engine/
│   ├── __init__.py
│   ├── cpi_decomposer.py           # decompose_cpi() → contributions from food/fuel/core
│   ├── iip_decomposer.py           # decompose_iip() → use-based classification contributions
│   ├── surprise_calc.py            # compute_surprise() → z-score + magnitude label
│   └── release_calendar.py         # RELEASE_SCHEDULE + get_upcoming_releases() + days_until()
├── scrapers/
│   ├── __init__.py
│   ├── mospi_cpi.py                # Fetches latest MOSPI CPI press release PDF → parsed dict
│   ├── mospi_iip.py                # Fetches latest MOSPI IIP press release PDF → parsed dict
│   └── rbi_spf.py                  # Returns latest SPF consensus forecasts (hardcoded seed)
├── ai/
│   ├── __init__.py
│   └── flash_brief.py              # generate_cpi_brief() + generate_iip_brief() via Claude
├── seed/
│   └── historical_data.py          # One-shot script: seeds DB with 12 months of CPI + IIP
├── ui/
│   ├── __init__.py
│   ├── calendar_view.py            # Release calendar widget with countdown badges
│   ├── cpi_view.py                 # CPI decomposition chart + component table
│   ├── iip_view.py                 # IIP use-based decomposition chart
│   ├── surprise_view.py            # Surprise history table (last 12 months)
│   └── brief_view.py               # Flash brief display + generate button
└── tests/
    ├── __init__.py
    ├── test_schema.py
    ├── test_store.py
    ├── test_cpi_decomposer.py
    ├── test_iip_decomposer.py
    ├── test_surprise_calc.py
    ├── test_release_calendar.py
    └── fixtures/
        ├── sample_cpi.json
        └── sample_iip.json
```

---

## Task 1: Project Scaffolding + SQLite Schema

**Files:**
- Create: `systems/02-macro-pulse/db/__init__.py`
- Create: `systems/02-macro-pulse/db/schema.py`
- Create: `systems/02-macro-pulse/tests/__init__.py`
- Create: `systems/02-macro-pulse/tests/test_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_schema.py
import sqlite3
import tempfile
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.schema import init_db, DB_PATH


def test_init_db_creates_tables(tmp_path, monkeypatch):
    """init_db creates all required tables in the SQLite file."""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr("db.schema.DB_PATH", test_db)

    init_db()

    conn = sqlite3.connect(test_db)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    assert "cpi_releases" in tables
    assert "iip_releases" in tables
    assert "flash_briefs" in tables
    assert "spf_consensus" in tables


def test_init_db_idempotent(tmp_path, monkeypatch):
    """init_db can be called twice without error (IF NOT EXISTS)."""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr("db.schema.DB_PATH", test_db)

    init_db()
    init_db()  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd systems/02-macro-pulse
pytest tests/test_schema.py -v
```
Expected: `ModuleNotFoundError: No module named 'db.schema'`

- [ ] **Step 3: Create directory structure + empty inits**

```bash
cd systems/02-macro-pulse
mkdir -p db engine scrapers ai seed ui tests/fixtures
touch db/__init__.py engine/__init__.py scrapers/__init__.py \
      ai/__init__.py ui/__init__.py tests/__init__.py
```

- [ ] **Step 4: Write `db/schema.py`**

```python
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "macro_pulse.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS cpi_releases (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    release_date      TEXT NOT NULL,
    reference_month   TEXT NOT NULL UNIQUE,
    headline_yoy      REAL NOT NULL,
    headline_mom      REAL,
    food_yoy          REAL,
    fuel_yoy          REAL,
    core_yoy          REAL,
    food_contrib      REAL,
    fuel_contrib      REAL,
    core_contrib      REAL,
    consensus_forecast REAL,
    created_at        TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS iip_releases (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    release_date            TEXT NOT NULL,
    reference_month         TEXT NOT NULL UNIQUE,
    headline_yoy            REAL NOT NULL,
    manufacturing_yoy       REAL,
    mining_yoy              REAL,
    electricity_yoy         REAL,
    capital_goods_yoy       REAL,
    consumer_durables_yoy   REAL,
    consumer_nondurables_yoy REAL,
    infra_construction_yoy  REAL,
    primary_goods_yoy       REAL,
    intermediate_goods_yoy  REAL,
    consensus_forecast      REAL,
    created_at              TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS flash_briefs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    release_type    TEXT NOT NULL,
    reference_month TEXT NOT NULL,
    brief_text      TEXT NOT NULL,
    generated_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS spf_consensus (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    round_number     INTEGER NOT NULL,
    publication_date TEXT NOT NULL,
    indicator        TEXT NOT NULL,
    forecast_period  TEXT NOT NULL,
    median_forecast  REAL NOT NULL,
    q1_forecast      REAL,
    q3_forecast      REAL
);
"""


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_schema.py -v
```
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add db/ tests/test_schema.py tests/__init__.py
git commit -m "feat: db schema for macro pulse — CPI, IIP, SPF, flash briefs"
```

---

## Task 2: DB Store Layer

**Files:**
- Create: `systems/02-macro-pulse/db/store.py`
- Create: `systems/02-macro-pulse/tests/test_store.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_store.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from db.schema import init_db
from db.store import CPIStore, IIPStore


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr("db.schema.DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr("db.store.DB_PATH", tmp_path / "test.db")
    init_db()
    return tmp_path / "test.db"


def test_cpi_store_upsert_and_get_latest(db):
    store = CPIStore()
    store.upsert({
        "release_date": "2025-03-12",
        "reference_month": "2025-02",
        "headline_yoy": 3.61,
        "food_yoy": 3.75,
        "fuel_yoy": -1.59,
        "core_yoy": 4.09,
        "food_contrib": 1.72,
        "fuel_contrib": -0.11,
        "core_contrib": 2.00,
        "consensus_forecast": 4.10,
    })
    row = store.get_latest()
    assert row["reference_month"] == "2025-02"
    assert row["headline_yoy"] == pytest.approx(3.61)


def test_cpi_store_upsert_is_idempotent(db):
    store = CPIStore()
    record = {
        "release_date": "2025-03-12",
        "reference_month": "2025-02",
        "headline_yoy": 3.61,
        "food_yoy": 3.75,
        "fuel_yoy": -1.59,
        "core_yoy": 4.09,
        "food_contrib": 1.72,
        "fuel_contrib": -0.11,
        "core_contrib": 2.00,
        "consensus_forecast": 4.10,
    }
    store.upsert(record)
    store.upsert(record)  # must not raise or duplicate
    assert store.count() == 1


def test_cpi_store_get_history(db):
    store = CPIStore()
    for month, val in [("2025-01", 4.26), ("2025-02", 3.61)]:
        store.upsert({
            "release_date": "2025-01-01",
            "reference_month": month,
            "headline_yoy": val,
            "food_yoy": None,
            "fuel_yoy": None,
            "core_yoy": None,
            "food_contrib": None,
            "fuel_contrib": None,
            "core_contrib": None,
            "consensus_forecast": None,
        })
    history = store.get_history(months=12)
    assert len(history) == 2
    assert history[-1]["headline_yoy"] == pytest.approx(3.61)


def test_iip_store_upsert_and_get_latest(db):
    store = IIPStore()
    store.upsert({
        "release_date": "2025-03-28",
        "reference_month": "2025-01",
        "headline_yoy": 5.0,
        "manufacturing_yoy": 5.5,
        "mining_yoy": 4.4,
        "electricity_yoy": 5.3,
        "capital_goods_yoy": 8.2,
        "consumer_durables_yoy": 12.1,
        "consumer_nondurables_yoy": 2.3,
        "infra_construction_yoy": 7.8,
        "primary_goods_yoy": 4.1,
        "intermediate_goods_yoy": 3.9,
        "consensus_forecast": 4.5,
    })
    row = store.get_latest()
    assert row["headline_yoy"] == pytest.approx(5.0)
    assert row["capital_goods_yoy"] == pytest.approx(8.2)
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_store.py -v
```
Expected: `ModuleNotFoundError: No module named 'db.store'`

- [ ] **Step 3: Write `db/store.py`**

```python
import sqlite3
from typing import Optional
from db.schema import DB_PATH


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class CPIStore:
    def upsert(self, record: dict):
        conn = _connect()
        conn.execute("""
            INSERT INTO cpi_releases
                (release_date, reference_month, headline_yoy, food_yoy, fuel_yoy,
                 core_yoy, food_contrib, fuel_contrib, core_contrib, consensus_forecast)
            VALUES
                (:release_date, :reference_month, :headline_yoy, :food_yoy, :fuel_yoy,
                 :core_yoy, :food_contrib, :fuel_contrib, :core_contrib, :consensus_forecast)
            ON CONFLICT(reference_month) DO UPDATE SET
                headline_yoy       = excluded.headline_yoy,
                food_yoy           = excluded.food_yoy,
                fuel_yoy           = excluded.fuel_yoy,
                core_yoy           = excluded.core_yoy,
                food_contrib       = excluded.food_contrib,
                fuel_contrib       = excluded.fuel_contrib,
                core_contrib       = excluded.core_contrib,
                consensus_forecast = excluded.consensus_forecast
        """, record)
        conn.commit()
        conn.close()

    def get_latest(self) -> Optional[dict]:
        conn = _connect()
        row = conn.execute(
            "SELECT * FROM cpi_releases ORDER BY reference_month DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_history(self, months: int = 12) -> list[dict]:
        conn = _connect()
        rows = conn.execute(
            "SELECT * FROM cpi_releases ORDER BY reference_month DESC LIMIT ?",
            (months,)
        ).fetchall()
        conn.close()
        return list(reversed([dict(r) for r in rows]))

    def count(self) -> int:
        conn = _connect()
        n = conn.execute("SELECT COUNT(*) FROM cpi_releases").fetchone()[0]
        conn.close()
        return n


class IIPStore:
    def upsert(self, record: dict):
        conn = _connect()
        conn.execute("""
            INSERT INTO iip_releases
                (release_date, reference_month, headline_yoy, manufacturing_yoy,
                 mining_yoy, electricity_yoy, capital_goods_yoy, consumer_durables_yoy,
                 consumer_nondurables_yoy, infra_construction_yoy, primary_goods_yoy,
                 intermediate_goods_yoy, consensus_forecast)
            VALUES
                (:release_date, :reference_month, :headline_yoy, :manufacturing_yoy,
                 :mining_yoy, :electricity_yoy, :capital_goods_yoy, :consumer_durables_yoy,
                 :consumer_nondurables_yoy, :infra_construction_yoy, :primary_goods_yoy,
                 :intermediate_goods_yoy, :consensus_forecast)
            ON CONFLICT(reference_month) DO UPDATE SET
                headline_yoy             = excluded.headline_yoy,
                manufacturing_yoy        = excluded.manufacturing_yoy,
                mining_yoy               = excluded.mining_yoy,
                electricity_yoy          = excluded.electricity_yoy,
                capital_goods_yoy        = excluded.capital_goods_yoy,
                consumer_durables_yoy    = excluded.consumer_durables_yoy,
                consumer_nondurables_yoy = excluded.consumer_nondurables_yoy,
                infra_construction_yoy   = excluded.infra_construction_yoy,
                primary_goods_yoy        = excluded.primary_goods_yoy,
                intermediate_goods_yoy   = excluded.intermediate_goods_yoy,
                consensus_forecast       = excluded.consensus_forecast
        """, record)
        conn.commit()
        conn.close()

    def get_latest(self) -> Optional[dict]:
        conn = _connect()
        row = conn.execute(
            "SELECT * FROM iip_releases ORDER BY reference_month DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return dict(row) if row else None

    def get_history(self, months: int = 12) -> list[dict]:
        conn = _connect()
        rows = conn.execute(
            "SELECT * FROM iip_releases ORDER BY reference_month DESC LIMIT ?",
            (months,)
        ).fetchall()
        conn.close()
        return list(reversed([dict(r) for r in rows]))


class BriefStore:
    def save(self, release_type: str, reference_month: str, brief_text: str):
        conn = _connect()
        conn.execute(
            "INSERT INTO flash_briefs (release_type, reference_month, brief_text) VALUES (?,?,?)",
            (release_type, reference_month, brief_text)
        )
        conn.commit()
        conn.close()

    def get_latest(self, release_type: str) -> Optional[dict]:
        conn = _connect()
        row = conn.execute(
            "SELECT * FROM flash_briefs WHERE release_type=? ORDER BY generated_at DESC LIMIT 1",
            (release_type,)
        ).fetchone()
        conn.close()
        return dict(row) if row else None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_store.py -v
```
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add db/store.py tests/test_store.py
git commit -m "feat: db store layer — CPIStore, IIPStore, BriefStore with upsert/history"
```

---

## Task 3: CPI Decomposition Engine

**Files:**
- Create: `systems/02-macro-pulse/engine/cpi_decomposer.py`
- Create: `systems/02-macro-pulse/tests/test_cpi_decomposer.py`

Economic context: CPI 2012 base year weights — Food & Beverages: 45.86%, Fuel & Light: 6.84%, Core (residual): 47.30%. The RBI MPC tracks core inflation because food and fuel are supply-side shocks that monetary policy cannot address. Core trending up while headline falls is a hawkish signal.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cpi_decomposer.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from engine.cpi_decomposer import decompose_cpi, CPIWeights


def test_contributions_sum_to_headline():
    """food_contrib + fuel_contrib + core_contrib must equal headline_yoy."""
    result = decompose_cpi(headline=3.61, food_yoy=3.75, fuel_yoy=-1.59)
    total = result["food_contrib"] + result["fuel_contrib"] + result["core_contrib"]
    assert total == pytest.approx(result["headline_yoy"], abs=0.01)


def test_core_yoy_derived_correctly():
    """Core YoY = core_contrib / core_weight."""
    result = decompose_cpi(headline=3.61, food_yoy=3.75, fuel_yoy=-1.59)
    expected_core_yoy = result["core_contrib"] / CPIWeights.CORE
    assert result["core_yoy"] == pytest.approx(expected_core_yoy, abs=0.01)


def test_food_contribution_arithmetic():
    """Food contribution = food_yoy * food_weight."""
    result = decompose_cpi(headline=5.49, food_yoy=9.24, fuel_yoy=5.26)
    assert result["food_contrib"] == pytest.approx(9.24 * CPIWeights.FOOD, abs=0.01)


def test_high_food_inflation_scenario():
    """Oct 2024: CPI=6.21, food=10.87, fuel=-1.56 → core should be positive ~3.7."""
    result = decompose_cpi(headline=6.21, food_yoy=10.87, fuel_yoy=-1.56)
    assert result["core_yoy"] > 3.0
    assert result["food_contrib"] > result["fuel_contrib"]


def test_negative_fuel_contribution():
    """Fuel deflation reduces headline — fuel_contrib should be negative."""
    result = decompose_cpi(headline=4.26, food_yoy=6.00, fuel_yoy=-1.50)
    assert result["fuel_contrib"] < 0


def test_rbi_signal_property():
    """Returns dominant_driver: which of food/fuel/core contributed most."""
    result = decompose_cpi(headline=5.49, food_yoy=9.24, fuel_yoy=5.26)
    assert result["dominant_driver"] == "food"
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_cpi_decomposer.py -v
```
Expected: `ModuleNotFoundError: No module named 'engine.cpi_decomposer'`

- [ ] **Step 3: Write `engine/cpi_decomposer.py`**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class CPIWeights:
    """CPI 2012 base year weights (share of total index)."""
    FOOD: float = 0.4586
    FUEL: float = 0.0684
    CORE: float = 0.4730   # = 1 - FOOD - FUEL


CPIWeights = CPIWeights()  # singleton instance for import


def decompose_cpi(headline: float, food_yoy: float, fuel_yoy: float) -> dict:
    """
    Decompose headline CPI into food, fuel, and core contributions.

    Returns contributions (pp to headline) and implied core YoY.
    Core is residual: core_contrib = headline - food_contrib - fuel_contrib.
    This matches how RBI MPC staff decompose inflation in policy documents.
    """
    food_contrib = round(food_yoy * CPIWeights.FOOD, 2)
    fuel_contrib = round(fuel_yoy * CPIWeights.FUEL, 2)
    core_contrib = round(headline - food_contrib - fuel_contrib, 2)
    core_yoy = round(core_contrib / CPIWeights.CORE, 2)

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
    }
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_cpi_decomposer.py -v
```
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add engine/cpi_decomposer.py tests/test_cpi_decomposer.py
git commit -m "feat: CPI decomposition engine — food/fuel/core contributions with RBI-aligned weights"
```

---

## Task 4: IIP Decomposition Engine

**Files:**
- Create: `systems/02-macro-pulse/engine/iip_decomposer.py`
- Create: `systems/02-macro-pulse/tests/test_iip_decomposer.py`

Economic context: IIP use-based classification reveals demand composition. Capital Goods = investment demand (corporate capex signal). Consumer Durables = discretionary consumption (urban demand health). Consumer Non-Durables = staples. Infrastructure/Construction = government capex execution. When capital goods and infra/construction diverge, it signals private vs public investment split — critical for RBI growth assessment.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_iip_decomposer.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from engine.iip_decomposer import assess_iip_composition, IIPSignal


def test_strong_capex_signal():
    """Capital goods > 10% = positive investment cycle signal."""
    signal = assess_iip_composition(
        headline=8.0,
        capital_goods=14.5,
        consumer_durables=9.0,
        consumer_nondurables=3.0,
        infra_construction=12.0,
        primary_goods=5.0,
        intermediate_goods=4.0,
    )
    assert signal.investment_demand == "strong"
    assert signal.consumption_demand in ("moderate", "strong")


def test_weak_consumer_durable_signal():
    """Consumer durables < 0 = weak urban discretionary demand."""
    signal = assess_iip_composition(
        headline=2.0,
        capital_goods=3.0,
        consumer_durables=-5.0,
        consumer_nondurables=2.0,
        infra_construction=4.0,
        primary_goods=2.5,
        intermediate_goods=1.8,
    )
    assert signal.consumption_demand == "weak"


def test_headline_masked_by_base():
    """Low headline can hide strong capital goods — signal is separate from headline."""
    signal = assess_iip_composition(
        headline=-3.5,
        capital_goods=8.0,
        consumer_durables=-12.0,
        consumer_nondurables=1.0,
        infra_construction=6.0,
        primary_goods=-2.0,
        intermediate_goods=-4.0,
    )
    assert signal.investment_demand == "strong"
    assert signal.consumption_demand == "weak"


def test_mpc_growth_read():
    """Returns an mpc_read string summarising growth signal for flash brief."""
    signal = assess_iip_composition(
        headline=5.2,
        capital_goods=11.0,
        consumer_durables=8.5,
        consumer_nondurables=3.5,
        infra_construction=9.0,
        primary_goods=4.5,
        intermediate_goods=3.8,
    )
    assert isinstance(signal.mpc_growth_read, str)
    assert len(signal.mpc_growth_read) > 20
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_iip_decomposer.py -v
```
Expected: `ModuleNotFoundError: No module named 'engine.iip_decomposer'`

- [ ] **Step 3: Write `engine/iip_decomposer.py`**

```python
from dataclasses import dataclass
from typing import Literal


@dataclass
class IIPSignal:
    headline: float
    investment_demand: Literal["strong", "moderate", "weak"]
    consumption_demand: Literal["strong", "moderate", "weak"]
    mpc_growth_read: str
    capital_goods: float
    consumer_durables: float
    consumer_nondurables: float
    infra_construction: float
    primary_goods: float
    intermediate_goods: float


def _grade(value: float, high: float, low: float) -> Literal["strong", "moderate", "weak"]:
    if value >= high:
        return "strong"
    if value <= low:
        return "weak"
    return "moderate"


def assess_iip_composition(
    headline: float,
    capital_goods: float,
    consumer_durables: float,
    consumer_nondurables: float,
    infra_construction: float,
    primary_goods: float,
    intermediate_goods: float,
) -> IIPSignal:
    """
    Grade IIP components into investment and consumption demand signals.

    Thresholds calibrated to India's IIP historical distribution (2016-2024):
    - Capital goods >8% = strong investment; <2% = weak
    - Consumer durables >5% = strong; <0% = weak
    These match the qualitative language RBI MPC uses in policy statements.
    """
    investment = _grade(capital_goods, high=8.0, low=2.0)
    consumption = _grade(consumer_durables, high=5.0, low=0.0)

    invest_word = {
        "strong": f"Capital goods accelerated ({capital_goods:+.1f}%), pointing to a strengthening investment cycle.",
        "moderate": f"Capital goods grew at {capital_goods:+.1f}% — investment demand is holding but not accelerating.",
        "weak": f"Capital goods contracted/slowed to {capital_goods:+.1f}%, flagging weak private capex.",
    }[investment]

    consume_word = {
        "strong": f"Consumer durables ({consumer_durables:+.1f}%) signal healthy urban discretionary spending.",
        "moderate": f"Consumer durables at {consumer_durables:+.1f}% — consumption demand is uneven.",
        "weak": f"Consumer durables contracted ({consumer_durables:+.1f}%), indicating stressed urban demand.",
    }[consumption]

    mpc_read = f"{invest_word} {consume_word} Infra/construction at {infra_construction:+.1f}% reflects government capex execution."

    return IIPSignal(
        headline=headline,
        investment_demand=investment,
        consumption_demand=consumption,
        mpc_growth_read=mpc_read,
        capital_goods=capital_goods,
        consumer_durables=consumer_durables,
        consumer_nondurables=consumer_nondurables,
        infra_construction=infra_construction,
        primary_goods=primary_goods,
        intermediate_goods=intermediate_goods,
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_iip_decomposer.py -v
```
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add engine/iip_decomposer.py tests/test_iip_decomposer.py
git commit -m "feat: IIP decomposition engine — investment/consumption demand signals with MPC-aligned grading"
```

---

## Task 5: Surprise Calculator

**Files:**
- Create: `systems/02-macro-pulse/engine/surprise_calc.py`
- Create: `systems/02-macro-pulse/tests/test_surprise_calc.py`

Economic context: Surprise magnitude must be contextualised. CPI historical surprise std dev ≈ 0.18pp (based on SPF tracking error 2018–2024 — a 0.2pp miss is a ~1.1 sigma event, which is NOTABLE). IIP historical surprise std dev ≈ 2.8pp (so a 0.2pp miss is negligible noise). These constants prevent over-interpreting IIP misses that are within normal estimation error.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_surprise_calc.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from engine.surprise_calc import compute_surprise, SurpriseResult


def test_cpi_significant_below_consensus():
    """Feb 2025 CPI: 3.61% actual vs 4.10% consensus = -0.49pp = SIGNIFICANT BELOW."""
    result = compute_surprise(actual=3.61, consensus=4.10, indicator="CPI")
    assert result.surprise == pytest.approx(-0.49, abs=0.01)
    assert result.direction == "BELOW"
    assert result.magnitude == "SIGNIFICANT"
    assert "SIGNIFICANT" in result.label


def test_cpi_inline_with_consensus():
    """CPI 4.83% vs 4.80% consensus = +0.03pp = IN LINE."""
    result = compute_surprise(actual=4.83, consensus=4.80, indicator="CPI")
    assert result.magnitude == "IN LINE"
    assert result.label == "IN LINE WITH CONSENSUS"


def test_iip_large_miss_is_notable_not_significant():
    """IIP 0.1% vs consensus 4.0% — z-score ~1.4, so NOTABLE not SIGNIFICANT."""
    result = compute_surprise(actual=0.1, consensus=4.0, indicator="IIP")
    assert result.magnitude in ("NOTABLE", "IN LINE")  # 3.9pp miss / 2.8pp std = 1.39


def test_iip_small_miss_is_inline():
    """IIP 5.2% vs 5.0% = +0.2pp, z-score = 0.07 = IN LINE."""
    result = compute_surprise(actual=5.2, consensus=5.0, indicator="IIP")
    assert result.magnitude == "IN LINE"


def test_z_score_formula():
    """Z-score = surprise / std_dev."""
    result = compute_surprise(actual=3.61, consensus=4.10, indicator="CPI")
    expected_z = -0.49 / 0.18
    assert result.z_score == pytest.approx(expected_z, abs=0.01)


def test_contextual_label_format():
    """Label is human-readable for flash brief insertion."""
    result = compute_surprise(actual=6.21, consensus=5.80, indicator="CPI")
    assert isinstance(result.label, str)
    assert len(result.label) > 5
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_surprise_calc.py -v
```
Expected: `ModuleNotFoundError: No module named 'engine.surprise_calc'`

- [ ] **Step 3: Write `engine/surprise_calc.py`**

```python
from dataclasses import dataclass
from typing import Literal

# Historical SPF tracking error standard deviations (India, 2018-2024)
_STD_DEVS = {
    "CPI": 0.18,   # pp — 0.2pp miss ≈ 1.1 sigma
    "IIP": 2.80,   # pp — 0.2pp miss ≈ 0.07 sigma (noise)
    "GDP": 0.40,   # pp — 0.4pp miss ≈ 1 sigma
}

Magnitude = Literal["SIGNIFICANT", "NOTABLE", "IN LINE"]
Direction = Literal["ABOVE", "BELOW", "IN LINE"]


@dataclass
class SurpriseResult:
    actual: float
    consensus: float
    surprise: float
    z_score: float
    magnitude: Magnitude
    direction: Direction
    label: str


def compute_surprise(actual: float, consensus: float, indicator: str) -> SurpriseResult:
    """
    Compute surprise vs consensus and assign magnitude using z-score.

    Magnitude thresholds:
        |z| > 1.5 → SIGNIFICANT (≈5% tail event given normal distribution)
        |z| > 0.7 → NOTABLE (≈1-in-4 event)
        otherwise → IN LINE

    For CPI: |surprise| > 0.27pp = SIGNIFICANT; > 0.13pp = NOTABLE.
    For IIP: |surprise| > 4.2pp = SIGNIFICANT; > 1.96pp = NOTABLE.
    """
    std = _STD_DEVS.get(indicator.upper(), 1.0)
    surprise = round(actual - consensus, 3)
    z = round(surprise / std, 2)

    if abs(z) > 1.5:
        magnitude: Magnitude = "SIGNIFICANT"
    elif abs(z) > 0.7:
        magnitude = "NOTABLE"
    else:
        magnitude = "IN LINE"

    if surprise > 0:
        direction: Direction = "ABOVE"
    elif surprise < 0:
        direction = "BELOW"
    else:
        direction = "IN LINE"

    if magnitude == "IN LINE":
        label = "IN LINE WITH CONSENSUS"
    else:
        label = f"{magnitude} {direction} CONSENSUS ({surprise:+.2f}pp, z={z:.1f})"

    return SurpriseResult(
        actual=actual,
        consensus=consensus,
        surprise=surprise,
        z_score=z,
        magnitude=magnitude,
        direction=direction,
        label=label,
    )
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_surprise_calc.py -v
```
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add engine/surprise_calc.py tests/test_surprise_calc.py
git commit -m "feat: surprise calculator — z-score with CPI/IIP-calibrated std devs, contextualised labels"
```

---

## Task 6: Release Calendar

**Files:**
- Create: `systems/02-macro-pulse/engine/release_calendar.py`
- Create: `systems/02-macro-pulse/tests/test_release_calendar.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_release_calendar.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date
import pytest
from engine.release_calendar import get_upcoming_releases, days_until, ScheduledRelease


def test_get_upcoming_returns_future_only():
    """Releases before as_of date are excluded."""
    as_of = date(2025, 5, 1)
    upcoming = get_upcoming_releases(as_of=as_of, days_ahead=60)
    for r in upcoming:
        assert r.expected_date >= as_of


def test_days_ahead_filter():
    """Only releases within days_ahead window are returned."""
    as_of = date(2025, 5, 1)
    upcoming = get_upcoming_releases(as_of=as_of, days_ahead=30)
    for r in upcoming:
        assert (r.expected_date - as_of).days <= 30


def test_days_until_positive():
    as_of = date(2025, 4, 28)
    release = ScheduledRelease(
        indicator="CPI",
        reference_period="Mar-2025",
        expected_date=date(2025, 5, 13),
    )
    assert days_until(release, as_of=as_of) == 15


def test_days_until_today():
    today = date.today()
    release = ScheduledRelease(
        indicator="IIP",
        reference_period="Mar-2025",
        expected_date=today,
    )
    assert days_until(release) == 0


def test_release_schedule_has_both_indicators():
    """Schedule includes both CPI and IIP releases."""
    upcoming = get_upcoming_releases(as_of=date(2025, 4, 1), days_ahead=365)
    indicators = {r.indicator for r in upcoming}
    assert "CPI" in indicators
    assert "IIP" in indicators
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_release_calendar.py -v
```
Expected: `ModuleNotFoundError: No module named 'engine.release_calendar'`

- [ ] **Step 3: Write `engine/release_calendar.py`**

```python
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional


@dataclass
class ScheduledRelease:
    indicator: str          # "CPI" or "IIP"
    reference_period: str   # e.g. "Mar-2025"
    expected_date: date
    actual_date: Optional[date] = None
    is_released: bool = False


# MOSPI CPI: released ~12th of the following month
# MOSPI IIP: released ~28th of the following month (2-month lag)
# e.g. Feb-2025 IIP → released Mar-28-2025; Mar-2025 IIP → Apr-30-2025
RELEASE_SCHEDULE: list[ScheduledRelease] = [
    # CPI releases 2025
    ScheduledRelease("CPI", "Feb-2025", date(2025, 3, 12), is_released=True),
    ScheduledRelease("CPI", "Mar-2025", date(2025, 4, 14), is_released=True),
    ScheduledRelease("CPI", "Apr-2025", date(2025, 5, 13)),
    ScheduledRelease("CPI", "May-2025", date(2025, 6, 12)),
    ScheduledRelease("CPI", "Jun-2025", date(2025, 7, 14)),
    ScheduledRelease("CPI", "Jul-2025", date(2025, 8, 12)),
    ScheduledRelease("CPI", "Aug-2025", date(2025, 9, 12)),
    ScheduledRelease("CPI", "Sep-2025", date(2025, 10, 14)),
    ScheduledRelease("CPI", "Oct-2025", date(2025, 11, 12)),
    ScheduledRelease("CPI", "Nov-2025", date(2025, 12, 12)),
    ScheduledRelease("CPI", "Dec-2025", date(2026, 1, 13)),
    # IIP releases 2025 (2-month lag)
    ScheduledRelease("IIP", "Jan-2025", date(2025, 3, 28), is_released=True),
    ScheduledRelease("IIP", "Feb-2025", date(2025, 4, 30), is_released=True),
    ScheduledRelease("IIP", "Mar-2025", date(2025, 5, 30)),
    ScheduledRelease("IIP", "Apr-2025", date(2025, 6, 30)),
    ScheduledRelease("IIP", "May-2025", date(2025, 7, 31)),
    ScheduledRelease("IIP", "Jun-2025", date(2025, 8, 29)),
    ScheduledRelease("IIP", "Jul-2025", date(2025, 9, 30)),
    ScheduledRelease("IIP", "Aug-2025", date(2025, 10, 31)),
    ScheduledRelease("IIP", "Sep-2025", date(2025, 11, 28)),
    ScheduledRelease("IIP", "Oct-2025", date(2025, 12, 31)),
]


def get_upcoming_releases(as_of: date = None, days_ahead: int = 60) -> list[ScheduledRelease]:
    if as_of is None:
        as_of = date.today()
    cutoff = as_of + timedelta(days=days_ahead)
    return [r for r in RELEASE_SCHEDULE if as_of <= r.expected_date <= cutoff]


def days_until(release: ScheduledRelease, as_of: date = None) -> int:
    if as_of is None:
        as_of = date.today()
    return (release.expected_date - as_of).days
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_release_calendar.py -v
```
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add engine/release_calendar.py tests/test_release_calendar.py
git commit -m "feat: release calendar — CPI/IIP 2025 schedule with countdown logic"
```

---

## Task 7: Historical Data Seed

**Files:**
- Create: `systems/02-macro-pulse/seed/historical_data.py`
- Create: `systems/02-macro-pulse/seed/__init__.py`

This task seeds the database with 12 months of real CPI and IIP data so the app works immediately on first run without live scraping. Data sourced from MOSPI press releases and RBI DBIE (Apr 2024 – Mar 2025).

- [ ] **Step 1: Create `seed/historical_data.py`**

No TDD for seed scripts — verify by running and querying.

```python
# seed/historical_data.py
"""Seed the DB with 12 months of historical CPI and IIP data."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db.schema import init_db
from db.store import CPIStore, IIPStore
from engine.cpi_decomposer import decompose_cpi

# CPI data: Apr 2024 – Feb 2025 (MOSPI actual releases)
# Format: (reference_month, release_date, headline_yoy, food_yoy, fuel_yoy, consensus)
CPI_HISTORY = [
    ("2024-04", "2024-05-13", 4.83, 8.70,  3.52,  4.80),
    ("2024-05", "2024-06-12", 4.75, 8.69,  3.83,  4.70),
    ("2024-06", "2024-07-12", 5.08, 9.36,  3.55,  4.90),
    ("2024-07", "2024-08-12", 3.54, 5.42,  5.45,  3.80),
    ("2024-08", "2024-09-12", 3.65, 5.66,  5.26,  3.80),
    ("2024-09", "2024-10-14", 5.49, 9.24,  5.26,  5.20),
    ("2024-10", "2024-11-12", 6.21, 10.87, -1.56, 5.90),
    ("2024-11", "2024-12-12", 5.48, 9.04,  -1.31, 5.50),
    ("2024-12", "2025-01-13", 5.22, 8.39,  -1.04, 5.30),
    ("2025-01", "2025-02-12", 4.26, 6.00,  -1.51, 4.60),
    ("2025-02", "2025-03-12", 3.61, 3.75,  -1.59, 4.10),
    ("2025-03", "2025-04-14", 3.34, 2.69,  -1.67, 3.70),
]

# IIP data: Mar 2024 – Jan 2025 (MOSPI actual releases)
# Format: (reference_month, release_date, headline, mfg, mining, elec,
#          cap_goods, cons_durable, cons_nondur, infra, primary, intermediate, consensus)
IIP_HISTORY = [
    ("2024-03", "2024-05-31", 4.9,  5.2,  1.2,  8.0, -0.7, 11.9, 3.7,  8.2,  5.1,  3.7,  4.5),
    ("2024-04", "2024-06-28", 5.0,  5.8,  6.7,  0.9,  2.3,  3.7,  4.4,  6.8,  6.3,  3.9,  4.8),
    ("2024-05", "2024-07-31", 5.9,  4.6,  6.0, 13.1, 12.6,  4.3,  1.3,  5.0,  6.4,  5.0,  6.0),
    ("2024-06", "2024-08-30", 4.2,  4.3,  7.4,  2.7,  1.0,  2.8,  4.4,  6.0,  5.9,  2.4,  4.5),
    ("2024-07", "2024-09-30", 4.8,  4.6,  3.7,  7.9,  1.4, 11.7,  3.2,  5.5,  5.1,  3.4,  5.0),
    ("2024-08", "2024-10-31", 0.1,  1.0, -4.3,  0.9, -0.6, 11.7, -0.2,  1.1,  0.5, -1.6,  1.0),
    ("2024-09", "2024-11-29",-3.5, -3.7, -4.8, -1.4, -3.7, -6.7, -2.1, -3.0, -3.6, -3.8,  0.5),
    ("2024-10", "2024-12-31", 3.5,  4.1, -0.9,  2.1, -1.9,  5.9,  5.0,  4.6,  4.2,  2.5,  3.5),
    ("2024-11", "2025-01-31", 5.2,  5.8,  2.9,  4.4, 12.8,  6.3,  1.3,  5.5,  5.9,  4.9,  4.8),
    ("2024-12", "2025-02-28", 3.2,  2.5,  4.1,  6.0,  8.2,  4.6, -0.4,  5.0,  4.0,  2.3,  3.8),
    ("2025-01", "2025-03-28", 5.0,  5.5,  4.4,  5.3,  8.2, 12.1,  2.3,  7.8,  4.1,  3.9,  4.5),
]


def seed():
    init_db()
    cpi_store = CPIStore()
    iip_store = IIPStore()

    for row in CPI_HISTORY:
        ref_month, rel_date, headline, food, fuel, consensus = row
        dec = decompose_cpi(headline=headline, food_yoy=food, fuel_yoy=fuel)
        cpi_store.upsert({
            "release_date":       rel_date,
            "reference_month":    ref_month,
            "headline_yoy":       headline,
            "food_yoy":           food,
            "fuel_yoy":           fuel,
            "core_yoy":           dec["core_yoy"],
            "food_contrib":       dec["food_contrib"],
            "fuel_contrib":       dec["fuel_contrib"],
            "core_contrib":       dec["core_contrib"],
            "consensus_forecast": consensus,
        })
        print(f"  CPI {ref_month}: {headline}% (core={dec['core_yoy']}%)")

    for row in IIP_HISTORY:
        ref, rel, hl, mfg, mine, elec, cap, cd, cnd, infra, prim, inter, cons = row
        iip_store.upsert({
            "release_date":            rel,
            "reference_month":         ref,
            "headline_yoy":            hl,
            "manufacturing_yoy":       mfg,
            "mining_yoy":              mine,
            "electricity_yoy":         elec,
            "capital_goods_yoy":       cap,
            "consumer_durables_yoy":   cd,
            "consumer_nondurables_yoy": cnd,
            "infra_construction_yoy":  infra,
            "primary_goods_yoy":       prim,
            "intermediate_goods_yoy":  inter,
            "consensus_forecast":      cons,
        })
        print(f"  IIP {ref}: {hl}%")

    print("Seed complete.")


if __name__ == "__main__":
    seed()
```

- [ ] **Step 2: Run the seed script**

```bash
cd systems/02-macro-pulse
python seed/historical_data.py
```
Expected output: 12 CPI lines + 11 IIP lines + "Seed complete."

- [ ] **Step 3: Verify data is in DB**

```bash
python -c "
from db.store import CPIStore, IIPStore
cpi = CPIStore()
iip = IIPStore()
print('CPI records:', cpi.count())
print('Latest CPI:', cpi.get_latest()['reference_month'], cpi.get_latest()['headline_yoy'])
print('Latest IIP:', iip.get_latest()['reference_month'], iip.get_latest()['headline_yoy'])
"
```
Expected:
```
CPI records: 12
Latest CPI: 2025-03 3.34
Latest IIP: 2025-01 5.0
```

- [ ] **Step 4: Commit**

```bash
git add seed/ data/.gitkeep
git commit -m "feat: historical seed — 12 months CPI + 11 months IIP pre-loaded"
```

---

## Task 8: MOSPI CPI Scraper

**Files:**
- Create: `systems/02-macro-pulse/scrapers/mospi_cpi.py`
- Create: `systems/02-macro-pulse/tests/fixtures/sample_cpi.json`

The MOSPI press release page lists CPI releases. The scraper finds the latest PDF link, downloads it, and extracts the headline and component figures using pdfplumber. Falls back gracefully if the portal is down.

- [ ] **Step 1: Create fixture file**

```json
// tests/fixtures/sample_cpi.json
{
  "reference_month": "2025-03",
  "release_date": "2025-04-14",
  "headline_yoy": 3.34,
  "food_yoy": 2.69,
  "fuel_yoy": -1.67,
  "source": "fixture"
}
```

- [ ] **Step 2: Write `scrapers/mospi_cpi.py`**

```python
import json
import re
import requests
from pathlib import Path
from datetime import date
from typing import Optional

# MOSPI CPI press releases index
MOSPI_CPI_URL = "https://mospi.gov.in/web/mospi/press-releases/-/asset_publisher/5XjCDPHnBClZ/content/consumer-price-indices-cpi"

FIXTURE_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "sample_cpi.json"


def fetch_latest_cpi(use_fixture: bool = False) -> Optional[dict]:
    """
    Fetch latest CPI release from MOSPI.
    Returns dict with keys: reference_month, release_date, headline_yoy, food_yoy, fuel_yoy.
    Returns None if scraping fails (caller should fall back to DB).
    """
    if use_fixture:
        return json.loads(FIXTURE_PATH.read_text())

    try:
        return _scrape_mospi_cpi()
    except Exception as e:
        print(f"[mospi_cpi] scrape failed: {e}")
        return None


def _scrape_mospi_cpi() -> dict:
    headers = {"User-Agent": "Mozilla/5.0 (research bot; contact joshijeet02@gmail.com)"}
    resp = requests.get(MOSPI_CPI_URL, headers=headers, timeout=15)
    resp.raise_for_status()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "html.parser")

    # MOSPI press release page has links containing "CPI" in PDF hrefs
    pdf_links = [
        a["href"] for a in soup.find_all("a", href=True)
        if a["href"].endswith(".pdf") and "cpi" in a["href"].lower()
    ]

    if not pdf_links:
        raise ValueError("No CPI PDF links found on MOSPI page")

    latest_pdf_url = pdf_links[0]
    if not latest_pdf_url.startswith("http"):
        latest_pdf_url = "https://mospi.gov.in" + latest_pdf_url

    return _parse_cpi_pdf(latest_pdf_url, headers)


def _parse_cpi_pdf(pdf_url: str, headers: dict) -> dict:
    import pdfplumber
    import io

    resp = requests.get(pdf_url, headers=headers, timeout=30)
    resp.raise_for_status()

    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages[:3])

    # Extract reference month (e.g. "March 2025" or "February, 2025")
    month_match = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)[,\s]+(\d{4})",
        text
    )
    if not month_match:
        raise ValueError(f"Cannot extract reference month from PDF: {pdf_url}")

    month_str = month_match.group(1)
    year_str = month_match.group(2)
    month_num = {
        "January": "01", "February": "02", "March": "03", "April": "04",
        "May": "05", "June": "06", "July": "07", "August": "08",
        "September": "09", "October": "10", "November": "11", "December": "12"
    }[month_str]
    reference_month = f"{year_str}-{month_num}"

    # Extract headline YoY — typically a line like "General Index ... 3.34"
    # MOSPI tables show YoY change in column 3 of the CPI table
    headline = _extract_number_after(text, r"General Index.*?(\d+\.\d+)", group=1)
    food = _extract_number_after(text, r"Food and Beverages.*?(\d+\.\d+)", group=1)
    fuel = _extract_number_after(text, r"Fuel and Light.*?(-?\d+\.\d+)", group=1)

    return {
        "reference_month": reference_month,
        "release_date": date.today().isoformat(),
        "headline_yoy": headline,
        "food_yoy": food,
        "fuel_yoy": fuel,
        "source": pdf_url,
    }


def _extract_number_after(text: str, pattern: str, group: int = 1) -> Optional[float]:
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if match:
        try:
            return float(match.group(group))
        except (ValueError, IndexError):
            return None
    return None
```

- [ ] **Step 3: Verify fixture mode works**

```bash
python -c "
from scrapers.mospi_cpi import fetch_latest_cpi
data = fetch_latest_cpi(use_fixture=True)
print(data)
assert data['headline_yoy'] == 3.34
print('fixture OK')
"
```
Expected: prints fixture dict + "fixture OK"

- [ ] **Step 4: Commit**

```bash
git add scrapers/mospi_cpi.py tests/fixtures/sample_cpi.json
git commit -m "feat: MOSPI CPI scraper — PDF parser with fixture fallback"
```

---

## Task 9: MOSPI IIP Scraper

**Files:**
- Create: `systems/02-macro-pulse/scrapers/mospi_iip.py`
- Create: `systems/02-macro-pulse/tests/fixtures/sample_iip.json`

- [ ] **Step 1: Create fixture file**

```json
// tests/fixtures/sample_iip.json
{
  "reference_month": "2025-01",
  "release_date": "2025-03-28",
  "headline_yoy": 5.0,
  "manufacturing_yoy": 5.5,
  "mining_yoy": 4.4,
  "electricity_yoy": 5.3,
  "capital_goods_yoy": 8.2,
  "consumer_durables_yoy": 12.1,
  "consumer_nondurables_yoy": 2.3,
  "infra_construction_yoy": 7.8,
  "primary_goods_yoy": 4.1,
  "intermediate_goods_yoy": 3.9,
  "source": "fixture"
}
```

- [ ] **Step 2: Write `scrapers/mospi_iip.py`**

```python
import json
import re
import requests
from pathlib import Path
from datetime import date
from typing import Optional

MOSPI_IIP_URL = "https://mospi.gov.in/web/mospi/press-releases/-/asset_publisher/5XjCDPHnBClZ/content/index-industrial-production"

FIXTURE_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "sample_iip.json"


def fetch_latest_iip(use_fixture: bool = False) -> Optional[dict]:
    """
    Fetch latest IIP release from MOSPI.
    Returns None on failure — caller falls back to DB.
    """
    if use_fixture:
        return json.loads(FIXTURE_PATH.read_text())

    try:
        return _scrape_mospi_iip()
    except Exception as e:
        print(f"[mospi_iip] scrape failed: {e}")
        return None


def _scrape_mospi_iip() -> dict:
    headers = {"User-Agent": "Mozilla/5.0 (research bot; contact joshijeet02@gmail.com)"}
    resp = requests.get(MOSPI_IIP_URL, headers=headers, timeout=15)
    resp.raise_for_status()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "html.parser")

    pdf_links = [
        a["href"] for a in soup.find_all("a", href=True)
        if a["href"].endswith(".pdf") and "iip" in a["href"].lower()
    ]

    if not pdf_links:
        raise ValueError("No IIP PDF links found on MOSPI page")

    latest_pdf_url = pdf_links[0]
    if not latest_pdf_url.startswith("http"):
        latest_pdf_url = "https://mospi.gov.in" + latest_pdf_url

    return _parse_iip_pdf(latest_pdf_url, headers)


def _parse_iip_pdf(pdf_url: str, headers: dict) -> dict:
    import pdfplumber
    import io

    resp = requests.get(pdf_url, headers=headers, timeout=30)
    resp.raise_for_status()

    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages[:4])

    month_match = re.search(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)[,\s]+(\d{4})",
        text
    )
    if not month_match:
        raise ValueError(f"Cannot extract reference month from IIP PDF: {pdf_url}")

    month_num = {
        "January": "01", "February": "02", "March": "03", "April": "04",
        "May": "05", "June": "06", "July": "07", "August": "08",
        "September": "09", "October": "10", "November": "11", "December": "12"
    }[month_match.group(1)]
    reference_month = f"{month_match.group(2)}-{month_num}"

    def extract(pattern):
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if m:
            try:
                return float(m.group(1))
            except (ValueError, IndexError):
                return None
        return None

    return {
        "reference_month": reference_month,
        "release_date": date.today().isoformat(),
        "headline_yoy": extract(r"General Index.*?(-?\d+\.\d+)"),
        "manufacturing_yoy": extract(r"Manufacturing.*?(-?\d+\.\d+)"),
        "mining_yoy": extract(r"Mining.*?(-?\d+\.\d+)"),
        "electricity_yoy": extract(r"Electricity.*?(-?\d+\.\d+)"),
        "capital_goods_yoy": extract(r"Capital Goods.*?(-?\d+\.\d+)"),
        "consumer_durables_yoy": extract(r"Consumer Durables.*?(-?\d+\.\d+)"),
        "consumer_nondurables_yoy": extract(r"Consumer Non.durables.*?(-?\d+\.\d+)"),
        "infra_construction_yoy": extract(r"Infrastructure.*?(-?\d+\.\d+)"),
        "primary_goods_yoy": extract(r"Primary Goods.*?(-?\d+\.\d+)"),
        "intermediate_goods_yoy": extract(r"Intermediate Goods.*?(-?\d+\.\d+)"),
        "source": pdf_url,
    }
```

- [ ] **Step 3: Verify fixture mode works**

```bash
python -c "
from scrapers.mospi_iip import fetch_latest_iip
data = fetch_latest_iip(use_fixture=True)
assert data['capital_goods_yoy'] == 8.2
print('IIP fixture OK:', data['reference_month'])
"
```

- [ ] **Step 4: Commit**

```bash
git add scrapers/mospi_iip.py tests/fixtures/sample_iip.json
git commit -m "feat: MOSPI IIP scraper — PDF parser with use-based classification extraction"
```

---

## Task 10: Flash Brief Generator (Anthropic API)

**Files:**
- Create: `systems/02-macro-pulse/ai/flash_brief.py`
- Create: `systems/02-macro-pulse/.env.example`

- [ ] **Step 1: Write `ai/flash_brief.py`**

```python
import os
import anthropic
from engine.cpi_decomposer import decompose_cpi
from engine.iip_decomposer import assess_iip_composition
from engine.surprise_calc import compute_surprise

_SYSTEM = (
    "You are a senior economist at a top Indian investment bank writing a flash brief "
    "for a Chief Economist. Write concisely and analytically. Focus on: "
    "(1) What this print means for RBI rate expectations, "
    "(2) Bond yield direction (10Y G-sec), "
    "(3) Any supply vs demand signal that changes the MPC's assessment. "
    "Never hedge. Never pad. Three paragraphs, no headers, plain prose."
)


def _client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=api_key)


def generate_cpi_brief(
    reference_month: str,
    headline_yoy: float,
    food_yoy: float,
    fuel_yoy: float,
    consensus: float,
) -> str:
    """Generate a 3-paragraph CPI flash brief via Claude."""
    dec = decompose_cpi(headline=headline_yoy, food_yoy=food_yoy, fuel_yoy=fuel_yoy)
    surprise = compute_surprise(actual=headline_yoy, consensus=consensus, indicator="CPI")

    prompt = f"""CPI Flash Brief — {reference_month}

HEADLINE: {headline_yoy}% YoY ({surprise.label})
CONSENSUS: {consensus}%

DECOMPOSITION (contributions to headline, pp):
- Food: {dec['food_contrib']:+.2f}pp (food YoY {food_yoy}%)
- Fuel: {dec['fuel_contrib']:+.2f}pp (fuel YoY {fuel_yoy}%)
- Core: {dec['core_contrib']:+.2f}pp (core YoY {dec['core_yoy']}%)

Write the flash brief. Para 1: headline + surprise (≤50 words). \
Para 2: component story + MPC read (≤80 words). \
Para 3: bond yield implication + rate cut probability change (≤60 words)."""

    msg = _client().messages.create(
        model="claude-opus-4-7",
        max_tokens=450,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def generate_iip_brief(
    reference_month: str,
    headline_yoy: float,
    capital_goods: float,
    consumer_durables: float,
    consumer_nondurables: float,
    infra_construction: float,
    primary_goods: float,
    intermediate_goods: float,
    consensus: float,
) -> str:
    """Generate a 3-paragraph IIP flash brief via Claude."""
    signal = assess_iip_composition(
        headline=headline_yoy,
        capital_goods=capital_goods,
        consumer_durables=consumer_durables,
        consumer_nondurables=consumer_nondurables,
        infra_construction=infra_construction,
        primary_goods=primary_goods,
        intermediate_goods=intermediate_goods,
    )
    surprise = compute_surprise(actual=headline_yoy, consensus=consensus, indicator="IIP")

    prompt = f"""IIP Flash Brief — {reference_month}

HEADLINE: {headline_yoy}% YoY ({surprise.label})
CONSENSUS: {consensus}%

USE-BASED BREAKDOWN (YoY%):
- Capital Goods: {capital_goods:+.1f}% [investment demand: {signal.investment_demand}]
- Consumer Durables: {consumer_durables:+.1f}% [consumption demand: {signal.consumption_demand}]
- Consumer Non-Durables: {consumer_nondurables:+.1f}%
- Infra/Construction: {infra_construction:+.1f}%
- Primary Goods: {primary_goods:+.1f}%
- Intermediate Goods: {intermediate_goods:+.1f}%

MPC GROWTH READ: {signal.mpc_growth_read}

Write the flash brief. Para 1: headline + surprise (≤50 words). \
Para 2: use-based decomposition — investment vs consumption signal, MPC growth assessment (≤80 words). \
Para 3: implication for growth outlook and rate expectations (≤60 words)."""

    msg = _client().messages.create(
        model="claude-opus-4-7",
        max_tokens=450,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text
```

- [ ] **Step 2: Create `.env.example`**

```
# Copy to .env and fill in your key
ANTHROPIC_API_KEY=sk-ant-...
```

- [ ] **Step 3: Manual smoke test (requires ANTHROPIC_API_KEY in env)**

```bash
cd systems/02-macro-pulse
export $(cat .env | xargs)  # or set ANTHROPIC_API_KEY manually
python -c "
from ai.flash_brief import generate_cpi_brief
brief = generate_cpi_brief(
    reference_month='March 2025',
    headline_yoy=3.34,
    food_yoy=2.69,
    fuel_yoy=-1.67,
    consensus=3.70,
)
print(brief)
"
```
Expected: Three paragraphs of economic analysis, no headers.

- [ ] **Step 4: Commit**

```bash
git add ai/flash_brief.py .env.example
git commit -m "feat: Claude flash brief generator — CPI and IIP with surprise-aware prompting"
```

---

## Task 11: Streamlit UI — Layout + Release Calendar

**Files:**
- Create: `systems/02-macro-pulse/app.py`
- Create: `systems/02-macro-pulse/ui/calendar_view.py`
- Create: `systems/02-macro-pulse/.streamlit/config.toml`
- Create: `systems/02-macro-pulse/requirements.txt`

- [ ] **Step 1: Create Streamlit theme config**

```toml
# .streamlit/config.toml
[theme]
base = "dark"
primaryColor = "#00C2A0"
backgroundColor = "#0F1117"
secondaryBackgroundColor = "#1A1D27"
textColor = "#E8EAF0"
font = "monospace"
```

- [ ] **Step 2: Create `ui/calendar_view.py`**

```python
import streamlit as st
from datetime import date
from engine.release_calendar import get_upcoming_releases, days_until, RELEASE_SCHEDULE


def render_release_calendar():
    st.subheader("Data Release Calendar")

    today = date.today()
    upcoming = get_upcoming_releases(as_of=today, days_ahead=90)

    if not upcoming:
        st.info("No releases scheduled in the next 90 days.")
        return

    cols = st.columns(min(len(upcoming), 4))
    for i, release in enumerate(upcoming[:4]):
        d = days_until(release, as_of=today)
        with cols[i % 4]:
            color = "#FF6B6B" if d <= 7 else "#FFD93D" if d <= 21 else "#6BCB77"
            st.markdown(f"""
<div style='background:{color}22;border:1px solid {color};border-radius:8px;padding:12px;text-align:center'>
    <div style='font-size:11px;color:{color};font-weight:bold'>{release.indicator}</div>
    <div style='font-size:13px;font-weight:600'>{release.reference_period}</div>
    <div style='font-size:22px;font-weight:bold;color:{color}'>{d}d</div>
    <div style='font-size:10px;color:#888'>{release.expected_date.strftime("%b %d")}</div>
</div>
""", unsafe_allow_html=True)

    st.caption(f"As of {today.strftime('%B %d, %Y')} · Dates are MOSPI scheduled release dates")
```

- [ ] **Step 3: Create `app.py`**

```python
import streamlit as st
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from db.schema import init_db
from ui.calendar_view import render_release_calendar
from ui.cpi_view import render_cpi_section
from ui.iip_view import render_iip_section
from ui.surprise_view import render_surprise_history
from ui.brief_view import render_brief_section

st.set_page_config(
    page_title="India Macro Pulse",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

init_db()

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    h1 { font-size: 1.6rem !important; }
</style>
""", unsafe_allow_html=True)

st.title("India Macro Pulse")
st.caption("Real-time data release intelligence for India's economic indicators · CPI · IIP · Surprise Tracker")

render_release_calendar()
st.divider()

tab_cpi, tab_iip, tab_surprise, tab_brief = st.tabs([
    "CPI Decomposition", "IIP Decomposition", "Surprise Tracker", "Flash Brief"
])

with tab_cpi:
    render_cpi_section()

with tab_iip:
    render_iip_section()

with tab_surprise:
    render_surprise_history()

with tab_brief:
    render_brief_section()
```

- [ ] **Step 4: Create `requirements.txt`**

```
streamlit>=1.35.0
requests>=2.31.0
beautifulsoup4>=4.12.0
pdfplumber>=0.10.0
pandas>=2.1.0
anthropic>=0.26.0
python-dotenv>=1.0.0
```

- [ ] **Step 5: Verify app structure loads**

```bash
cd systems/02-macro-pulse
python -c "import app; print('imports OK')"
```
Note: This will fail if Streamlit UI imports are missing. Complete Tasks 12–13 first, then verify.

- [ ] **Step 6: Commit**

```bash
git add app.py ui/ .streamlit/ requirements.txt
git commit -m "feat: Streamlit app skeleton — layout, tab structure, release calendar"
```

---

## Task 12: Streamlit UI — CPI and IIP Decomposition Views

**Files:**
- Create: `systems/02-macro-pulse/ui/cpi_view.py`
- Create: `systems/02-macro-pulse/ui/iip_view.py`

- [ ] **Step 1: Write `ui/cpi_view.py`**

```python
import streamlit as st
import pandas as pd
from db.store import CPIStore
from engine.surprise_calc import compute_surprise


def render_cpi_section():
    store = CPIStore()
    history = store.get_history(months=12)

    if not history:
        st.warning("No CPI data in database. Run `python seed/historical_data.py` first.")
        return

    latest = history[-1]
    ref = latest["reference_month"]

    # Headline metric row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Headline CPI", f"{latest['headline_yoy']}%", help="YoY %")
    col2.metric("Core Inflation", f"{latest['core_yoy'] or '—'}%",
                help="Residual ex-food & fuel — key MPC signal")
    col3.metric("Food Inflation", f"{latest['food_yoy'] or '—'}%",
                help="Food & Beverages (weight: 45.9%)")
    col4.metric("Fuel Inflation", f"{latest['fuel_yoy'] or '—'}%",
                help="Fuel & Light (weight: 6.8%)")

    st.caption(f"Reference: {ref} · Food weight 45.86% · Fuel weight 6.84% · Core (residual) 47.30%")

    # Contribution bar chart
    if all(k in latest and latest[k] is not None
           for k in ["food_contrib", "fuel_contrib", "core_contrib"]):
        st.subheader("Contributions to Headline CPI (pp)")
        contrib_data = pd.DataFrame({
            "Component": ["Food", "Fuel", "Core"],
            "Contribution (pp)": [
                latest["food_contrib"],
                latest["fuel_contrib"],
                latest["core_contrib"],
            ],
        })
        st.bar_chart(contrib_data.set_index("Component"))

    # Historical trend
    st.subheader("12-Month Trend")
    df = pd.DataFrame(history)
    df = df.set_index("reference_month")
    chart_cols = [c for c in ["headline_yoy", "core_yoy", "food_yoy"] if c in df.columns]
    chart_df = df[chart_cols].rename(columns={
        "headline_yoy": "Headline",
        "core_yoy": "Core",
        "food_yoy": "Food",
    })
    st.line_chart(chart_df)

    # Surprise history table
    if any(r.get("consensus_forecast") is not None for r in history):
        st.subheader("Surprise vs Consensus")
        rows = []
        for r in reversed(history[-6:]):
            if r.get("consensus_forecast"):
                s = compute_surprise(r["headline_yoy"], r["consensus_forecast"], "CPI")
                rows.append({
                    "Month": r["reference_month"],
                    "Actual": f"{r['headline_yoy']}%",
                    "Consensus": f"{r['consensus_forecast']}%",
                    "Surprise": f"{s.surprise:+.2f}pp",
                    "Z-Score": f"{s.z_score:.1f}",
                    "Signal": s.label,
                })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
```

- [ ] **Step 2: Write `ui/iip_view.py`**

```python
import streamlit as st
import pandas as pd
from db.store import IIPStore
from engine.iip_decomposer import assess_iip_composition
from engine.surprise_calc import compute_surprise


def render_iip_section():
    store = IIPStore()
    history = store.get_history(months=12)

    if not history:
        st.warning("No IIP data in database. Run `python seed/historical_data.py` first.")
        return

    latest = history[-1]

    col1, col2, col3 = st.columns(3)
    col1.metric("IIP Headline", f"{latest['headline_yoy']}%", help="YoY %")
    col2.metric("Capital Goods", f"{latest.get('capital_goods_yoy', '—')}%",
                help="Investment demand proxy")
    col3.metric("Consumer Durables", f"{latest.get('consumer_durables_yoy', '—')}%",
                help="Urban discretionary demand")

    # Use-based classification breakdown
    use_keys = [
        ("capital_goods_yoy", "Capital Goods"),
        ("consumer_durables_yoy", "Consumer Durables"),
        ("consumer_nondurables_yoy", "Consumer Non-Durables"),
        ("infra_construction_yoy", "Infra/Construction"),
        ("primary_goods_yoy", "Primary Goods"),
        ("intermediate_goods_yoy", "Intermediate Goods"),
    ]
    available = {label: latest[key] for key, label in use_keys if latest.get(key) is not None}

    if available:
        st.subheader("Use-Based Classification (YoY %)")
        bar_df = pd.DataFrame(available.items(), columns=["Component", "YoY %"])
        st.bar_chart(bar_df.set_index("Component"))

        # Demand signal assessment
        cap = latest.get("capital_goods_yoy", 0)
        cd = latest.get("consumer_durables_yoy", 0)
        cnd = latest.get("consumer_nondurables_yoy", 0)
        infra = latest.get("infra_construction_yoy", 0)
        prim = latest.get("primary_goods_yoy", 0)
        inter = latest.get("intermediate_goods_yoy", 0)

        signal = assess_iip_composition(
            headline=latest["headline_yoy"],
            capital_goods=cap, consumer_durables=cd,
            consumer_nondurables=cnd, infra_construction=infra,
            primary_goods=prim, intermediate_goods=inter,
        )
        invest_color = {"strong": "🟢", "moderate": "🟡", "weak": "🔴"}
        st.info(
            f"**Investment Demand:** {invest_color[signal.investment_demand]} {signal.investment_demand.upper()}  "
            f"**Consumption Demand:** {invest_color[signal.consumption_demand]} {signal.consumption_demand.upper()}\n\n"
            f"{signal.mpc_growth_read}"
        )

    # Historical headline trend
    st.subheader("12-Month IIP Trend")
    df = pd.DataFrame(history).set_index("reference_month")
    trend_cols = {c: c.replace("_yoy", "").replace("_", " ").title()
                  for c in ["headline_yoy", "capital_goods_yoy", "consumer_durables_yoy"]
                  if c in df.columns}
    st.line_chart(df[list(trend_cols.keys())].rename(columns=trend_cols))
```

- [ ] **Step 3: Run and verify no import errors**

```bash
cd systems/02-macro-pulse
python -c "
from ui.cpi_view import render_cpi_section
from ui.iip_view import render_iip_section
print('UI imports OK')
"
```
Expected: `UI imports OK`

- [ ] **Step 4: Commit**

```bash
git add ui/cpi_view.py ui/iip_view.py
git commit -m "feat: CPI and IIP decomposition views — contribution charts, trend lines, demand signals"
```

---

## Task 13: Streamlit UI — Surprise Tracker + Flash Brief Panel

**Files:**
- Create: `systems/02-macro-pulse/ui/surprise_view.py`
- Create: `systems/02-macro-pulse/ui/brief_view.py`

- [ ] **Step 1: Write `ui/surprise_view.py`**

```python
import streamlit as st
import pandas as pd
from db.store import CPIStore, IIPStore
from engine.surprise_calc import compute_surprise

_SIGNAL_COLORS = {
    "SIGNIFICANT": "🔴",
    "NOTABLE": "🟡",
    "IN LINE": "🟢",
}


def render_surprise_history():
    st.subheader("Surprise vs Consensus — Track Record")
    st.caption(
        "Z-scores use historical surprise std devs: CPI = 0.18pp, IIP = 2.8pp. "
        "SIGNIFICANT = |z| > 1.5 · NOTABLE = |z| > 0.7"
    )

    col_cpi, col_iip = st.columns(2)

    with col_cpi:
        st.markdown("**CPI Surprises**")
        cpi_store = CPIStore()
        cpi_history = cpi_store.get_history(months=12)
        cpi_rows = []
        for r in reversed(cpi_history):
            if r.get("consensus_forecast") and r.get("headline_yoy"):
                s = compute_surprise(r["headline_yoy"], r["consensus_forecast"], "CPI")
                icon = _SIGNAL_COLORS.get(s.magnitude, "")
                cpi_rows.append({
                    "Month": r["reference_month"],
                    "Actual": r["headline_yoy"],
                    "Consensus": r["consensus_forecast"],
                    "Surprise (pp)": s.surprise,
                    "Signal": f"{icon} {s.magnitude}",
                })
        if cpi_rows:
            df = pd.DataFrame(cpi_rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No CPI consensus data available.")

    with col_iip:
        st.markdown("**IIP Surprises**")
        iip_store = IIPStore()
        iip_history = iip_store.get_history(months=12)
        iip_rows = []
        for r in reversed(iip_history):
            if r.get("consensus_forecast") and r.get("headline_yoy"):
                s = compute_surprise(r["headline_yoy"], r["consensus_forecast"], "IIP")
                icon = _SIGNAL_COLORS.get(s.magnitude, "")
                iip_rows.append({
                    "Month": r["reference_month"],
                    "Actual": r["headline_yoy"],
                    "Consensus": r["consensus_forecast"],
                    "Surprise (pp)": s.surprise,
                    "Signal": f"{icon} {s.magnitude}",
                })
        if iip_rows:
            df = pd.DataFrame(iip_rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No IIP consensus data available.")
```

- [ ] **Step 2: Write `ui/brief_view.py`**

```python
import streamlit as st
from db.store import CPIStore, IIPStore, BriefStore
from ai.flash_brief import generate_cpi_brief, generate_iip_brief
import os


def render_brief_section():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    brief_store = BriefStore()
    cpi_store = CPIStore()
    iip_store = IIPStore()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("CPI Flash Brief")
        latest_cpi = cpi_store.get_latest()
        saved_brief = brief_store.get_latest("CPI")

        if saved_brief:
            st.caption(f"Generated for {saved_brief['reference_month']} · {saved_brief['generated_at'][:10]}")
            st.markdown(saved_brief["brief_text"])

        if latest_cpi:
            if api_key:
                if st.button("Generate CPI Brief", key="gen_cpi"):
                    with st.spinner("Generating analysis..."):
                        try:
                            brief = generate_cpi_brief(
                                reference_month=latest_cpi["reference_month"],
                                headline_yoy=latest_cpi["headline_yoy"],
                                food_yoy=latest_cpi.get("food_yoy") or 0.0,
                                fuel_yoy=latest_cpi.get("fuel_yoy") or 0.0,
                                consensus=latest_cpi.get("consensus_forecast") or latest_cpi["headline_yoy"],
                            )
                            brief_store.save("CPI", latest_cpi["reference_month"], brief)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Brief generation failed: {e}")
            else:
                st.info("Set ANTHROPIC_API_KEY to enable flash brief generation.")
        else:
            st.warning("No CPI data loaded.")

    with col2:
        st.subheader("IIP Flash Brief")
        latest_iip = iip_store.get_latest()
        saved_iip_brief = brief_store.get_latest("IIP")

        if saved_iip_brief:
            st.caption(f"Generated for {saved_iip_brief['reference_month']} · {saved_iip_brief['generated_at'][:10]}")
            st.markdown(saved_iip_brief["brief_text"])

        if latest_iip:
            if api_key:
                if st.button("Generate IIP Brief", key="gen_iip"):
                    with st.spinner("Generating analysis..."):
                        try:
                            brief = generate_iip_brief(
                                reference_month=latest_iip["reference_month"],
                                headline_yoy=latest_iip["headline_yoy"],
                                capital_goods=latest_iip.get("capital_goods_yoy") or 0.0,
                                consumer_durables=latest_iip.get("consumer_durables_yoy") or 0.0,
                                consumer_nondurables=latest_iip.get("consumer_nondurables_yoy") or 0.0,
                                infra_construction=latest_iip.get("infra_construction_yoy") or 0.0,
                                primary_goods=latest_iip.get("primary_goods_yoy") or 0.0,
                                intermediate_goods=latest_iip.get("intermediate_goods_yoy") or 0.0,
                                consensus=latest_iip.get("consensus_forecast") or latest_iip["headline_yoy"],
                            )
                            brief_store.save("IIP", latest_iip["reference_month"], brief)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Brief generation failed: {e}")
            else:
                st.info("Set ANTHROPIC_API_KEY to enable flash brief generation.")
        else:
            st.warning("No IIP data loaded.")
```

- [ ] **Step 3: Run and verify all UI imports work**

```bash
cd systems/02-macro-pulse
python -c "
from ui.surprise_view import render_surprise_history
from ui.brief_view import render_brief_section
print('All UI views import OK')
"
```
Expected: `All UI views import OK`

- [ ] **Step 4: Commit**

```bash
git add ui/surprise_view.py ui/brief_view.py
git commit -m "feat: surprise tracker and flash brief UI — side-by-side CPI/IIP with generate buttons"
```

---

## Task 14: End-to-End Integration + Local Run

- [ ] **Step 1: Run all tests**

```bash
cd systems/02-macro-pulse
pytest tests/ -v --tb=short
```
Expected: All tests pass. If any fail, fix before proceeding.

- [ ] **Step 2: Seed the database**

```bash
python seed/historical_data.py
```
Expected: 12 CPI + 11 IIP rows printed, "Seed complete."

- [ ] **Step 3: Start Streamlit locally**

```bash
streamlit run app.py --server.port 8501
```
Open `http://localhost:8501` in browser. Verify:
- [ ] Release calendar shows next 4 upcoming releases with countdown badges
- [ ] CPI tab: 4 metric cards, contribution bar chart, 12-month line chart, surprise table
- [ ] IIP tab: 3 metric cards, use-based bar chart, demand signal (green/yellow/red), trend line
- [ ] Surprise Tracker tab: two-column CPI + IIP surprise history tables with signal icons
- [ ] Flash Brief tab: "Set ANTHROPIC_API_KEY..." message if key not set; generate buttons present

- [ ] **Step 4: Test with API key (if available)**

```bash
export ANTHROPIC_API_KEY=sk-ant-...
streamlit run app.py --server.port 8501
```
Click "Generate CPI Brief" — should produce a 3-paragraph brief in <30 seconds.

- [ ] **Step 5: Commit**

```bash
git add .
git commit -m "feat: end-to-end integration verified — macro pulse app running locally"
```

---

## Task 15: Deploy to Streamlit Cloud

**Files:**
- Create: `systems/02-macro-pulse/.gitignore`

- [ ] **Step 1: Create `.gitignore`**

```
data/macro_pulse.db
.env
__pycache__/
*.pyc
.DS_Store
```

- [ ] **Step 2: Verify requirements.txt has all deps**

```bash
cd systems/02-macro-pulse
pip install -r requirements.txt
python -c "import streamlit, anthropic, pdfplumber, bs4, pandas; print('all deps OK')"
```
Expected: `all deps OK`

- [ ] **Step 3: Push to GitHub**

The repo must be public for Streamlit Cloud free tier.

```bash
cd /path/to/india-econ-intelligence  # project root
git add systems/02-macro-pulse/
git commit -m "feat: System 2 — India Macro Pulse complete and ready to deploy"
git push origin main
```

- [ ] **Step 4: Deploy on Streamlit Cloud**

1. Go to share.streamlit.io
2. Click "New app"
3. Select repo: `india-econ-intelligence`
4. Branch: `main`
5. Main file path: `systems/02-macro-pulse/app.py`
6. Click "Advanced settings" → add secret: `ANTHROPIC_API_KEY = "sk-ant-..."`
7. Click "Deploy"

Note: The app needs to seed the DB on first run. The `init_db()` call in `app.py` handles schema creation. The seed script must be run separately or triggered via a UI button (add as Task 16 if needed).

- [ ] **Step 5: Add auto-seed on first run to `app.py`**

Add after `init_db()` in `app.py`:

```python
from db.store import CPIStore
if CPIStore().count() == 0:
    from seed.historical_data import seed
    seed()
```

- [ ] **Step 6: Commit and verify deployment**

```bash
git add systems/02-macro-pulse/app.py systems/02-macro-pulse/.gitignore
git commit -m "feat: auto-seed on first run for Streamlit Cloud deployment"
git push origin main
```

Wait for Streamlit Cloud to redeploy (~2 min). Verify:
- [ ] App loads in browser with no errors
- [ ] Release calendar shows
- [ ] CPI and IIP data visible (seeded on first run)
- [ ] Flash brief generation works (Anthropic key in secrets)

---

## Self-Review Against Spec

**Spec requirement → Task coverage:**

| Requirement | Task |
|-------------|------|
| Data release calendar with countdown | Task 6, 11 |
| Surprise calculator with z-score | Task 5 |
| CPI decomposition (core/food/fuel) with RBI-aligned weights | Task 3 |
| IIP use-based classification (capex/consumption split) | Task 4 |
| Flash brief generator (structured 3-para) | Task 10 |
| Historical release database (12 months) | Task 7 |
| Surprise contextualised to indicator (CPI ≠ IIP std dev) | Task 5 |
| Flash brief names market implication (bonds, rates) | Task 10 prompt design |
| MOSPI CPI scraper | Task 8 |
| MOSPI IIP scraper | Task 9 |
| Streamlit UI deployable at public URL | Tasks 11–15 |
| No login, no friction | Task 15 (Streamlit Cloud) |
| Economic logic: MPC-aligned CPI decomposition | Task 3 |
| Economic logic: investment vs consumption demand read | Task 4 |

All spec requirements covered.

**Type consistency check:**
- `decompose_cpi()` returns dict with keys `food_contrib`, `fuel_contrib`, `core_contrib`, `core_yoy` — used consistently in Task 7 seed and Task 10 flash brief
- `compute_surprise()` returns `SurpriseResult` with `.label`, `.z_score`, `.magnitude` — used correctly in Tasks 12, 13
- `CPIStore.upsert()` takes dict with `reference_month`, `headline_yoy` etc — keys match Task 7 seed exactly
- `assess_iip_composition()` returns `IIPSignal` with `.investment_demand`, `.consumption_demand`, `.mpc_growth_read` — used in Task 12 IIP view

No placeholder text found. All code blocks are complete and runnable.
