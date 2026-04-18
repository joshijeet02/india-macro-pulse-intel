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
