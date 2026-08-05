"""Snapshot handling for the live fetchers."""
import pytest

from engine import live_sources


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(live_sources, "SNAPSHOT_PATH", tmp_path / "snap.json")
    return tmp_path / "snap.json"


def test_no_snapshots_yields_no_reference(store):
    assert live_sources.load_snapshots() == []
    assert live_sources.reference_prices() == {}


def test_reference_is_the_earliest_price_per_division(store):
    live_sources.save_snapshot({"personal_care_and_misc": 100.0})
    live_sources.save_snapshot({"personal_care_and_misc": 120.0})
    live_sources.save_snapshot({"personal_care_and_misc": 90.0})
    assert live_sources.reference_prices()["personal_care_and_misc"] == 100.0


def test_reference_is_per_division_not_per_snapshot(store):
    """A source added later must use its own first reading as reference."""
    live_sources.save_snapshot({"personal_care_and_misc": 100.0})
    live_sources.save_snapshot({"personal_care_and_misc": 110.0, "transport": 50.0})
    reference = live_sources.reference_prices()
    assert reference["personal_care_and_misc"] == 100.0
    assert reference["transport"] == 50.0


def test_relatives_are_current_over_reference(store):
    live_sources.save_snapshot({"personal_care_and_misc": 100.0})
    rel = live_sources.compute_relatives({"personal_care_and_misc": 125.0})
    assert rel["personal_care_and_misc"] == pytest.approx(1.25)


def test_division_without_a_reference_is_skipped(store):
    assert live_sources.compute_relatives({"transport": 50.0}, reference={}) == {}


def test_nonpositive_prices_never_become_a_reference(store):
    live_sources.save_snapshot({"transport": 0.0})
    live_sources.save_snapshot({"transport": 60.0})
    assert live_sources.reference_prices()["transport"] == 60.0


def test_first_fetch_is_flagged_as_a_reference_not_a_measurement(store, monkeypatch):
    """
    Day one measures nothing — it establishes the denominator. Reporting that
    as "prices unchanged" would be a claim about the world rather than about
    our own method.
    """
    monkeypatch.setattr(
        live_sources, "FETCHERS",
        {"_t": lambda: {"personal_care_and_misc": 100.0}},
    )
    _, relatives, first = live_sources.fetch_and_measure()
    assert first is True
    assert relatives["personal_care_and_misc"] == pytest.approx(1.0)

    monkeypatch.setattr(
        live_sources, "FETCHERS",
        {"_t": lambda: {"personal_care_and_misc": 125.0}},
    )
    _, relatives2, first2 = live_sources.fetch_and_measure()
    assert first2 is False
    assert relatives2["personal_care_and_misc"] == pytest.approx(1.25)


def test_a_failing_fetcher_does_not_break_the_others(store, monkeypatch):
    def boom():
        raise RuntimeError("source down")
    monkeypatch.setattr(
        live_sources, "FETCHERS",
        {"_boom": boom, "_ok": lambda: {"transport": 42.0}},
    )
    assert live_sources.fetch_all() == {"transport": 42.0}


def test_no_test_touches_the_network(store, monkeypatch):
    """Every fetcher is stubbed above; nothing here may make a real request."""
    monkeypatch.setattr(live_sources, "FETCHERS", {})
    assert live_sources.fetch_all() == {}


def test_corrupt_snapshot_file_degrades_to_empty(store):
    store.write_text("{ not json")
    assert live_sources.load_snapshots() == []
