"""
Price fetchers and the snapshot store.

The central property: a relative must be a MATCHED-SAMPLE geometric mean.
Amazon throttles, so item sets genuinely differ between fetches. Averaging
prices first and dividing the averages would report a lost item as a price
move — the same composition defect that matched-sample chaining fixes in the
grocery index.
"""
import math

import pytest

from engine import live_sources


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(live_sources, "SNAPSHOT_PATH", tmp_path / "snap.json")
    return tmp_path / "snap.json"


# ── snapshot store ──────────────────────────────────────────────────────────

def test_no_snapshots_yields_no_reference(store):
    assert live_sources.load_snapshots() == []
    assert live_sources.reference_prices() == {}


def test_reference_is_the_earliest_price_per_item(store):
    live_sources.save_snapshot({"food_and_beverages": {"rice": 100.0}})
    live_sources.save_snapshot({"food_and_beverages": {"rice": 120.0}})
    live_sources.save_snapshot({"food_and_beverages": {"rice": 90.0}})
    assert live_sources.reference_prices()["food_and_beverages"]["rice"] == 100.0


def test_an_item_first_seen_later_gets_its_own_reference(store):
    """Otherwise it would be excluded forever for missing the first fetch."""
    live_sources.save_snapshot({"food_and_beverages": {"rice": 100.0}})
    live_sources.save_snapshot({"food_and_beverages": {"rice": 110.0, "atta": 50.0}})
    reference = live_sources.reference_prices()["food_and_beverages"]
    assert reference["rice"] == 100.0
    assert reference["atta"] == 50.0


def test_nonpositive_prices_never_become_a_reference(store):
    live_sources.save_snapshot({"food_and_beverages": {"rice": 0.0}})
    live_sources.save_snapshot({"food_and_beverages": {"rice": 60.0}})
    assert live_sources.reference_prices()["food_and_beverages"]["rice"] == 60.0


def test_corrupt_snapshot_file_degrades_to_empty(store):
    store.write_text("{ not json")
    assert live_sources.load_snapshots() == []


# ── matched-sample relatives ────────────────────────────────────────────────

REFERENCE = {"food_and_beverages": {"rice": 100.0, "atta": 200.0, "tea": 500.0}}


def test_relative_is_the_geometric_mean_of_item_ratios():
    current = {"food_and_beverages": {"rice": 110.0, "atta": 240.0, "tea": 500.0}}
    got = live_sources.compute_relatives(current, REFERENCE)["food_and_beverages"]
    expected = math.exp((math.log(1.10) + math.log(1.20) + math.log(1.0)) / 3)
    assert got == pytest.approx(expected, abs=1e-9)


def test_a_lost_item_does_not_fake_a_price_move():
    """THE property. Same ratios, fewer items -> identical relative."""
    all_items = {"food_and_beverages": {"rice": 110.0, "atta": 220.0, "tea": 550.0}}
    tea_lost = {"food_and_beverages": {"rice": 110.0, "atta": 220.0}}
    a = live_sources.compute_relatives(all_items, REFERENCE)["food_and_beverages"]
    b = live_sources.compute_relatives(tea_lost, REFERENCE)["food_and_beverages"]
    assert a == pytest.approx(b, abs=1e-9)
    assert a == pytest.approx(1.10, abs=1e-9)


def test_flat_prices_with_a_lost_item_still_read_as_no_change():
    flat_minus_one = {"food_and_beverages": {"rice": 100.0, "atta": 200.0}}
    got = live_sources.compute_relatives(flat_minus_one, REFERENCE)["food_and_beverages"]
    assert got == pytest.approx(1.0, abs=1e-9)


def test_an_item_with_no_reference_is_excluded():
    current = {"food_and_beverages": {"rice": 110.0, "brand_new": 999.0}}
    got = live_sources.compute_relatives(current, REFERENCE)["food_and_beverages"]
    assert got == pytest.approx(1.10, abs=1e-9)


def test_division_with_no_matched_items_is_omitted():
    current = {"food_and_beverages": {"brand_new": 999.0}}
    assert live_sources.compute_relatives(current, REFERENCE) == {}


def test_nonpositive_current_prices_are_excluded():
    current = {"food_and_beverages": {"rice": 110.0, "atta": 0.0}}
    got = live_sources.compute_relatives(current, REFERENCE)["food_and_beverages"]
    assert got == pytest.approx(1.10, abs=1e-9)


# ── fetchers ────────────────────────────────────────────────────────────────

def test_first_fetch_is_flagged_as_a_reference_not_a_measurement(store, monkeypatch):
    """
    Day one measures nothing — it sets the denominator. Reporting that as
    "prices unchanged" would be a claim about the world, not about our method.
    """
    monkeypatch.setattr(
        live_sources, "FETCHERS",
        {"_t": lambda: {"food_and_beverages": {"rice": 100.0}}},
    )
    _, relatives, first = live_sources.fetch_and_measure()
    assert first is True
    # No link exists yet, so there is NO relative — not a synthetic 1.0.
    # Reporting 1.0 would assert prices held steady over a period we never
    # observed; reporting nothing says only that we have not measured yet.
    assert relatives == {}

    monkeypatch.setattr(
        live_sources, "FETCHERS",
        {"_t": lambda: {"food_and_beverages": {"rice": 125.0}}},
    )
    _, relatives2, first2 = live_sources.fetch_and_measure()
    assert first2 is False
    assert relatives2["food_and_beverages"] == pytest.approx(1.25)


def test_a_failing_fetcher_does_not_break_the_others(store, monkeypatch):
    def boom():
        raise RuntimeError("source down")
    monkeypatch.setattr(
        live_sources, "FETCHERS",
        {"_boom": boom, "_ok": lambda: {"transport": {"petrol": 42.0}}},
    )
    assert live_sources.fetch_all() == {"transport": {"petrol": 42.0}}


def test_grocery_returns_items_not_a_pre_averaged_number(monkeypatch):
    """Pre-averaging is what would reintroduce composition contamination."""
    fake = [
        {"item_id": "rice", "price": 369.0, "price_per_kg": 74.0},
        {"item_id": "atta", "price": 382.0, "price_per_kg": 76.0},
    ]
    monkeypatch.setattr("scrapers.amazon.scrape_amazon", lambda basket: fake)
    got = live_sources.fetch_grocery_prices()
    assert got == {"food_and_beverages": {"rice": 74.0, "atta": 76.0}}


def test_grocery_returns_nothing_when_the_scrape_fails(monkeypatch):
    monkeypatch.setattr("scrapers.amazon.scrape_amazon", lambda basket: [])
    assert live_sources.fetch_grocery_prices() == {}


def test_grocery_skips_unusable_rows(monkeypatch):
    fake = [
        {"item_id": "rice", "price": 100.0, "price_per_kg": 100.0},
        {"item_id": "atta", "price": 0.0, "price_per_kg": 0.0},
        {"item_id": "not_in_basket", "price": 999.0, "price_per_kg": 999.0},
    ]
    monkeypatch.setattr("scrapers.amazon.scrape_amazon", lambda basket: fake)
    assert live_sources.fetch_grocery_prices() == {"food_and_beverages": {"rice": 100.0}}


def test_bullion_returns_gold_and_silver_separately(monkeypatch):
    monkeypatch.setattr(
        "scrapers.metals.fetch_bullion",
        lambda: [{"symbol": "XAU", "inr_per_gram": 12973.10},
                 {"symbol": "XAG", "inr_per_gram": 190.25}],
    )
    got = live_sources.fetch_bullion_prices()
    assert got == {"personal_care_and_misc":
                   {"gold_per_gram": 12973.10, "silver_per_gram": 190.25}}


def test_bullion_needs_gold_at_minimum(monkeypatch):
    monkeypatch.setattr("scrapers.metals.fetch_bullion", lambda: [])
    assert live_sources.fetch_bullion_prices() == {}


def test_fuel_returns_nothing_rather_than_a_fabricated_price():
    """No live source wired yet — transport stays honestly marked 'carried'."""
    assert live_sources.fetch_fuel_prices() == {}


# ── chained links across time ───────────────────────────────────────────────

def _snap(day, prices):
    return {"fetched_at": f"2026-08-{day:02d} 00:00:00", "prices": prices}


def test_chaining_captures_movement_a_direct_comparison_would_discard():
    """
    THE reason chaining is correct rather than merely tidier.

    rice rises 20% then stops being scraped; atta then rises 10%. Comparing
    newest against oldest keeps only atta — the one item spanning both ends —
    and erases rice's move entirely. Chaining counts rice in the link it
    actually spans.
    """
    snapshots = [
        _snap(1, {"food_and_beverages": {"rice": 100.0, "atta": 100.0}}),
        _snap(2, {"food_and_beverages": {"rice": 120.0, "atta": 100.0}}),
        _snap(3, {"food_and_beverages": {"atta": 110.0}}),
    ]
    chained = live_sources.chained_relatives(snapshots)["food_and_beverages"]
    reference = {"food_and_beverages": snapshots[0]["prices"]["food_and_beverages"]}
    direct = live_sources.compute_relatives(
        snapshots[-1]["prices"], reference
    )["food_and_beverages"]

    assert chained == pytest.approx(1.2050, abs=1e-4)
    assert direct == pytest.approx(1.1000, abs=1e-4)
    assert chained > direct


def test_chained_links_compound():
    snapshots = [
        _snap(1, {"food_and_beverages": {"rice": 100.0}}),
        _snap(2, {"food_and_beverages": {"rice": 110.0}}),
        _snap(3, {"food_and_beverages": {"rice": 121.0}}),
    ]
    got = live_sources.chained_relatives(snapshots)["food_and_beverages"]
    assert got == pytest.approx(1.21, abs=1e-6)


def test_an_item_appearing_midway_contributes_to_later_links_only():
    snapshots = [
        _snap(1, {"food_and_beverages": {"rice": 100.0}}),
        _snap(2, {"food_and_beverages": {"rice": 100.0, "tea": 500.0}}),
        _snap(3, {"food_and_beverages": {"rice": 100.0, "tea": 600.0}}),
    ]
    got = live_sources.chained_relatives(snapshots)["food_and_beverages"]
    # link 1: rice flat -> 1.0 ; link 2: rice flat, tea +20% -> sqrt(1.0*1.2)
    assert got == pytest.approx(math.sqrt(1.2), abs=1e-6)


def test_a_link_with_no_shared_item_is_skipped_not_treated_as_flat():
    """
    Asserting 'no change' across a step we could not observe would be a claim
    about prices rather than about our coverage.
    """
    snapshots = [
        _snap(1, {"food_and_beverages": {"rice": 100.0}}),
        _snap(2, {"food_and_beverages": {"tea": 500.0}}),      # nothing shared
        _snap(3, {"food_and_beverages": {"tea": 550.0}}),
    ]
    got = live_sources.chained_relatives(snapshots)["food_and_beverages"]
    assert got == pytest.approx(1.10, abs=1e-6)   # only the tea link counted


def test_a_single_snapshot_yields_no_chain():
    assert live_sources.chained_relatives([_snap(1, {"x": {"a": 1.0}})]) == {}


def test_no_snapshots_yields_no_chain():
    assert live_sources.chained_relatives([]) == {}


def test_link_relative_needs_a_shared_item():
    assert live_sources.link_relative({"a": 1.0}, {"b": 2.0}) is None


def test_link_relative_ignores_nonpositive_prices():
    assert live_sources.link_relative({"a": 100.0, "b": 0.0},
                                      {"a": 110.0, "b": 50.0}) == pytest.approx(1.10)


# ── the unmeasured gap ──────────────────────────────────────────────────────

def test_gap_between_the_anchor_month_and_our_first_price_is_reported():
    """
    The anchor describes June's average prices; our first snapshot is in
    August. That movement was never observed and is silently treated as zero —
    so it has to be stated, not implied away.
    """
    snapshots = [_snap(5, {"food_and_beverages": {"rice": 100.0}})]
    gap = live_sources.unmeasured_gap("2026-06", snapshots)
    assert gap == "35 days"      # 1 July -> 5 August


def test_no_gap_reported_when_prices_predate_the_anchor_month_ending():
    snapshots = [{"fetched_at": "2026-06-15 00:00:00", "prices": {"x": {"a": 1.0}}}]
    assert live_sources.unmeasured_gap("2026-06", snapshots) is None


def test_gap_is_none_without_snapshots():
    assert live_sources.unmeasured_gap("2026-06", []) is None


def test_gap_degrades_on_a_malformed_timestamp():
    bad = [{"fetched_at": "not a date", "prices": {"x": {"a": 1.0}}}]
    assert live_sources.unmeasured_gap("2026-06", bad) is None
