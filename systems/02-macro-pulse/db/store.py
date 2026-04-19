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
        try:
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
        finally:
            conn.close()

    def get_latest(self) -> Optional[dict]:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM cpi_releases ORDER BY reference_month DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_history(self, months: int = 12) -> list[dict]:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM cpi_releases ORDER BY reference_month DESC LIMIT ?",
                (months,)
            ).fetchall()
            return list(reversed([dict(r) for r in rows]))
        finally:
            conn.close()

    def count(self) -> int:
        conn = _connect()
        try:
            return conn.execute("SELECT COUNT(*) FROM cpi_releases").fetchone()[0]
        finally:
            conn.close()


class IIPStore:
    def upsert(self, record: dict):
        conn = _connect()
        try:
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
        finally:
            conn.close()

    def get_latest(self) -> Optional[dict]:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM iip_releases ORDER BY reference_month DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_history(self, months: int = 12) -> list[dict]:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM iip_releases ORDER BY reference_month DESC LIMIT ?",
                (months,)
            ).fetchall()
            return list(reversed([dict(r) for r in rows]))
        finally:
            conn.close()


class EcommStore:
    def insert_price(self, record: dict):
        conn = _connect()
        try:
            conn.execute("""
                INSERT INTO ecomm_prices
                    (platform, item_id, cpi_group, item_name, price, unit, price_per_kg, scraped_at, pincode)
                VALUES
                    (:platform, :item_id, :cpi_group, :item_name, :price, :unit, :price_per_kg, :scraped_at, :pincode)
            """, record)
            conn.commit()
        finally:
            conn.close()

    def insert_prices_bulk(self, records: list[dict]):
        conn = _connect()
        try:
            conn.executemany("""
                INSERT INTO ecomm_prices
                    (platform, item_id, cpi_group, item_name, price, unit, price_per_kg, scraped_at, pincode)
                VALUES
                    (:platform, :item_id, :cpi_group, :item_name, :price, :unit, :price_per_kg, :scraped_at, :pincode)
            """, records)
            conn.commit()
        finally:
            conn.close()

    def get_latest_prices(self, platform: str) -> list[dict]:
        """Most recent price observation per item for a given platform."""
        conn = _connect()
        try:
            rows = conn.execute("""
                SELECT p.*
                FROM ecomm_prices p
                INNER JOIN (
                    SELECT item_id, MAX(scraped_at) AS max_at
                    FROM ecomm_prices WHERE platform = ?
                    GROUP BY item_id
                ) latest ON p.item_id = latest.item_id AND p.scraped_at = latest.max_at
                WHERE p.platform = ?
                ORDER BY p.cpi_group, p.item_id
            """, (platform, platform)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_base_prices(self, platform: str) -> dict[str, float]:
        """Earliest price per item (used as Laspeyres base)."""
        conn = _connect()
        try:
            rows = conn.execute("""
                SELECT p.item_id,
                       COALESCE(p.price_per_kg, p.price) AS base_price
                FROM ecomm_prices p
                INNER JOIN (
                    SELECT item_id, MIN(scraped_at) AS min_at
                    FROM ecomm_prices WHERE platform = ?
                    GROUP BY item_id
                ) earliest ON p.item_id = earliest.item_id AND p.scraped_at = earliest.min_at
                WHERE p.platform = ?
            """, (platform, platform)).fetchall()
            return {r["item_id"]: r["base_price"] for r in rows}
        finally:
            conn.close()

    def get_scrape_runs(self, platform: str, limit: int = 30) -> list[str]:
        """Return distinct scraped_at timestamps, most recent first."""
        conn = _connect()
        try:
            rows = conn.execute("""
                SELECT DISTINCT scraped_at FROM ecomm_prices
                WHERE platform = ?
                ORDER BY scraped_at DESC LIMIT ?
            """, (platform, limit)).fetchall()
            return [r["scraped_at"] for r in rows]
        finally:
            conn.close()

    def get_prices_at(self, platform: str, scraped_at: str) -> list[dict]:
        conn = _connect()
        try:
            rows = conn.execute("""
                SELECT * FROM ecomm_prices
                WHERE platform = ? AND scraped_at = ?
                ORDER BY cpi_group, item_id
            """, (platform, scraped_at)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def insert_index(self, record: dict):
        conn = _connect()
        try:
            conn.execute("""
                INSERT INTO ecomm_index (platform, computed_at, index_value, coverage_pct, items_count)
                VALUES (:platform, :computed_at, :index_value, :coverage_pct, :items_count)
            """, record)
            conn.commit()
        finally:
            conn.close()

    def get_index_history(self, platform: str, limit: int = 60) -> list[dict]:
        conn = _connect()
        try:
            rows = conn.execute("""
                SELECT * FROM ecomm_index WHERE platform = ?
                ORDER BY computed_at DESC LIMIT ?
            """, (platform, limit)).fetchall()
            return list(reversed([dict(r) for r in rows]))
        finally:
            conn.close()

    def last_scraped_at(self, platform: str) -> Optional[str]:
        conn = _connect()
        try:
            row = conn.execute("""
                SELECT MAX(scraped_at) FROM ecomm_prices WHERE platform = ?
            """, (platform,)).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def has_data(self) -> bool:
        conn = _connect()
        try:
            count = conn.execute("SELECT COUNT(*) FROM ecomm_prices").fetchone()[0]
            return count > 0
        finally:
            conn.close()


class BriefStore:
    def save(self, release_type: str, reference_month: str, brief_text: str):
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO flash_briefs (release_type, reference_month, brief_text) VALUES (?,?,?)",
                (release_type, reference_month, brief_text)
            )
            conn.commit()
        finally:
            conn.close()

    def get_latest(self, release_type: str) -> Optional[dict]:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM flash_briefs WHERE release_type=? ORDER BY generated_at DESC LIMIT 1",
                (release_type,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
