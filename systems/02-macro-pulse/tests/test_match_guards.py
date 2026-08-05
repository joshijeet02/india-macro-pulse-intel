"""
Wrong-product guards for the Amazon matcher.

Every case below is a REAL bad match from the first live scrape on
2026-08-05. Before these guards the scraper recorded egg cartons at Rs.7722
as the price of a dozen eggs, and an onion as the price of potato. Outlier
rejection could not catch either: it needs trailing history, and a first
observation has none.
"""
import pytest

from engine.ecomm_basket import BASKET, BASKET_BY_ID
from scrapers.amazon import passes_match_guards


@pytest.mark.parametrize("item_id,title,price", [
    ("eggs",          "Zhanmai Egg Cartons 12 Count, 25 Pack Bulk Paper Pulp", 7722.0),
    ("potato",        "Fresh Onion, 1kg", 35.0),
    ("sunflower_oil", "Fortune Xpert Pro Immunity Oil 850g pouch | Blend of oils", 171.0),
    ("tomato",        "Fresh", 50.0),
    ("milk",          "Amul", 83.0),
])
def test_real_bad_matches_are_rejected(item_id, title, price):
    assert passes_match_guards(title, price, BASKET_BY_ID[item_id]) is False


@pytest.mark.parametrize("item_id,title,price", [
    ("rice",             "India Gate Basmati Rice Everyday 5 kg", 369.0),
    ("atta",             "Nature's Superfoods Aashirvaad Organic Atta, 5kg", 382.0),
    ("mustard_oil",      "Fortune Premium Kachi Ghani Pure Mustard Oil, 1 ltr", 205.0),
    ("paneer",           "Amul Fresh Malai Paneer Block Pouch, 200 g", 92.0),
    ("coriander_powder", "Catch Coriander Powder | Dhaniya Powder, 200g", 50.0),
    ("tea",              "Society Leaf Tea 100% Pure Assam CTC", 155.0),
])
def test_real_good_matches_are_kept(item_id, title, price):
    assert passes_match_guards(title, price, BASKET_BY_ID[item_id]) is True


def test_absurd_price_rejected_even_with_right_keyword():
    """A correct keyword must not rescue an implausible price."""
    assert passes_match_guards("Farm Fresh Eggs 12 pack", 7722.0, BASKET_BY_ID["eggs"]) is False


def test_every_basket_item_carries_guards():
    """A guardless item silently reverts to the old, unprotected behaviour."""
    for item in BASKET:
        assert item.get("match_include"), f"{item['item_id']} has no match_include"
        assert item.get("price_range"), f"{item['item_id']} has no price_range"
        lo, hi = item["price_range"]
        assert 0 < lo < hi, f"{item['item_id']} has a nonsensical price_range"


def test_item_with_no_guards_configured_passes():
    """Guards are opt-in per item — absent config must not reject everything."""
    assert passes_match_guards("anything at all", 42.0, {"item_id": "x"}) is True
