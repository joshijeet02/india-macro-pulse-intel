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
    try:
        conn.executescript(SCHEMA)
    finally:
        conn.close()
