"""
CPI-aligned grocery basket for e-commerce price tracking.
20 items spanning major CPI food sub-groups. Weights mirror India's 2012=100 CPI
food sub-group shares (renormalised to 100 across this basket).
"""
from typing import TypedDict


class BasketItem(TypedDict):
    item_id: str
    name: str
    cpi_group: str
    unit: str
    weight: float           # basket weight (all items sum to ~100)
    blinkit_search: str
    zepto_search: str
    amazon_search: str


BASKET: list[BasketItem] = [
    # ── Cereals (26.3) ──────────────────────────────────────────────────────
    {"item_id": "rice",      "name": "Rice",              "cpi_group": "Cereals",
     "unit": "5kg",    "weight": 14.0,
     "match_include": ['rice'], "match_exclude": ['flour', 'poha', 'cooker', 'seed', 'krispies'],
     "price_range": (250, 1500),
     "blinkit_search": "india gate basmati rice 5kg",   "zepto_search": "rice 5kg",
     "amazon_search": "basmati rice 5kg"},
    {"item_id": "atta",      "name": "Wheat Flour (Atta)", "cpi_group": "Cereals",
     "unit": "5kg",    "weight": 12.3,
     "match_include": ['atta', 'flour'], "match_exclude": ['besan', 'maida', 'rice flour'],
     "price_range": (150, 700),
     "blinkit_search": "aashirvaad atta 5kg",           "zepto_search": "atta wheat flour 5kg",
     "amazon_search": "aashirvaad atta 5kg"},

    # ── Pulses (6.5) ────────────────────────────────────────────────────────
    {"item_id": "toor_dal",  "name": "Toor Dal",          "cpi_group": "Pulses",
     "unit": "1kg",    "weight": 2.5,
     "match_include": ['toor', 'tur', 'arhar'], "match_exclude": ['whole', 'sabut'],
     "price_range": (80, 400),
     "blinkit_search": "toor dal 1kg",                  "zepto_search": "toor dal 1kg",
     "amazon_search": "toor dal 1kg"},
    {"item_id": "moong_dal", "name": "Moong Dal",          "cpi_group": "Pulses",
     "unit": "500g",   "weight": 2.0,
     "match_include": ['moong'], "match_exclude": ['whole', 'sabut', 'sprout'],
     "price_range": (30, 250),
     "blinkit_search": "moong dal 500g",                "zepto_search": "moong dal 500g",
     "amazon_search": "moong dal 500g"},
    {"item_id": "chana_dal", "name": "Chana Dal",          "cpi_group": "Pulses",
     "unit": "1kg",    "weight": 2.0,
     "match_include": ['chana'], "match_exclude": ['besan', 'kabuli', 'whole', 'kala'],
     "price_range": (50, 300),
     "blinkit_search": "chana dal 1kg",                 "zepto_search": "chana dal 1kg",
     "amazon_search": "chana dal 1kg"},

    # ── Oils & Fats (9.7) ───────────────────────────────────────────────────
    {"item_id": "sunflower_oil", "name": "Sunflower Oil",  "cpi_group": "Oils & Fats",
     "unit": "1L",     "weight": 5.0,
     "match_include": ['sunflower'], "match_exclude": ['blend', 'xpert', 'immunity', 'rice bran'],
     "price_range": (80, 400),
     "blinkit_search": "sunflower oil 1 litre",         "zepto_search": "sunflower oil 1 litre",
     "amazon_search": "sunflower oil 1 litre"},
    {"item_id": "mustard_oil",   "name": "Mustard Oil",    "cpi_group": "Oils & Fats",
     "unit": "1L",     "weight": 4.7,
     "match_include": ['mustard'], "match_exclude": ['blend', 'hair', 'massage'],
     "price_range": (80, 400),
     "blinkit_search": "mustard oil 1 litre",           "zepto_search": "mustard oil 1 litre",
     "amazon_search": "mustard oil 1 litre"},

    # ── Milk & Products (18.0) ──────────────────────────────────────────────
    {"item_id": "milk",   "name": "Full Cream Milk",       "cpi_group": "Milk & Products",
     "unit": "500ml",  "weight": 9.0,
     "match_include": ['milk'], "match_exclude": ['powder', 'shake', 'chocolate', 'soya', 'almond', 'condensed'],
     "price_range": (15, 150),
     "blinkit_search": "full cream milk 500ml",         "zepto_search": "full cream milk 500ml",
     "amazon_search": "amul full cream milk 500ml"},
    {"item_id": "curd",   "name": "Curd / Dahi",           "cpi_group": "Milk & Products",
     "unit": "400g",   "weight": 4.5,
     "match_include": ['curd', 'dahi', 'yogurt', 'yoghurt'], "match_exclude": ['powder', 'starter'],
     "price_range": (15, 200),
     "blinkit_search": "curd dahi 400g",                "zepto_search": "curd dahi 400g",
     "amazon_search": "amul dahi curd 400g"},
    {"item_id": "paneer", "name": "Paneer",                "cpi_group": "Milk & Products",
     "unit": "200g",   "weight": 4.5,
     "match_include": ['paneer'], "match_exclude": ['masala', 'curry', 'tikka', 'frozen', 'bhurji'],
     "price_range": (30, 250),
     "blinkit_search": "fresh paneer 200g",             "zepto_search": "paneer 200g",
     "amazon_search": "fresh paneer 200g"},

    # ── Egg (1.2) ───────────────────────────────────────────────────────────
    {"item_id": "eggs",  "name": "Eggs (12 pack)",         "cpi_group": "Egg",
     "unit": "12 pcs", "weight": 1.2,
     "match_include": ['egg'], "match_exclude": ['carton', 'tray', 'holder', 'boiler', 'cooker', 'paper', 'separator', 'whisk'],
     "price_range": (40, 250),
     "blinkit_search": "eggs 12",                       "zepto_search": "eggs 12 pcs",
     "amazon_search": "farm fresh eggs 12 pack"},

    # ── Vegetables (16.4) ───────────────────────────────────────────────────
    {"item_id": "onion",  "name": "Onion",                 "cpi_group": "Vegetables",
     "unit": "1kg",    "weight": 5.5,
     "match_include": ['onion'], "match_exclude": ['powder', 'fried', 'seed', 'spring', 'flakes'],
     "price_range": (10, 200),
     "blinkit_search": "onion 1kg",                     "zepto_search": "onion 1kg",
     "amazon_search": "fresh onion 1kg"},
    {"item_id": "tomato", "name": "Tomato",                "cpi_group": "Vegetables",
     "unit": "500g",   "weight": 5.5,
     "match_include": ['tomato'], "match_exclude": ['ketchup', 'puree', 'sauce', 'powder', 'seed', 'dried'],
     "price_range": (8, 200),
     "blinkit_search": "tomato 500g",                   "zepto_search": "tomato 500g",
     "amazon_search": "fresh tomato 500g"},
    {"item_id": "potato", "name": "Potato",                "cpi_group": "Vegetables",
     "unit": "1kg",    "weight": 5.4,
     "match_include": ['potato'], "match_exclude": ['chips', 'seed', 'powder', 'sweet', 'wafer', 'fries'],
     "price_range": (10, 200),
     "blinkit_search": "potato 1kg",                    "zepto_search": "potato 1kg",
     "amazon_search": "fresh potato 1kg"},

    # ── Fruits (7.8) ────────────────────────────────────────────────────────
    {"item_id": "banana", "name": "Banana",                "cpi_group": "Fruits",
     "unit": "12 pcs", "weight": 4.0,
     "match_include": ['banana'], "match_exclude": ['chips', 'powder', 'dried', 'wafer'],
     "price_range": (20, 300),
     "blinkit_search": "banana dozen",                  "zepto_search": "banana",
     "amazon_search": "fresh banana 12 pcs"},
    {"item_id": "apple",  "name": "Apple",                 "cpi_group": "Fruits",
     "unit": "4 pcs",  "weight": 3.8,
     "match_include": ['apple'], "match_exclude": ['juice', 'cider', 'vinegar', 'dried', 'custard'],
     "price_range": (60, 800),
     "blinkit_search": "apple 4 pcs",                   "zepto_search": "apple 4 pcs",
     "amazon_search": "fresh apple 4 pcs"},

    # ── Sugar (3.7) ─────────────────────────────────────────────────────────
    {"item_id": "sugar",  "name": "Sugar",                 "cpi_group": "Sugar & Confectionery",
     "unit": "1kg",    "weight": 3.7,
     "match_include": ['sugar'], "match_exclude": ['brown', 'jaggery', 'free', 'stevia', 'cube', 'icing'],
     "price_range": (30, 300),
     "blinkit_search": "sugar 1kg",                     "zepto_search": "sugar 1kg",
     "amazon_search": "sugar 1kg"},

    # ── Spices (6.8) ────────────────────────────────────────────────────────
    {"item_id": "turmeric",         "name": "Turmeric Powder",  "cpi_group": "Spices",
     "unit": "200g",   "weight": 3.4,
     "match_include": ['turmeric', 'haldi'], "match_exclude": ['fresh', 'raw', 'root', 'latte', 'capsule'],
     "price_range": (15, 300),
     "blinkit_search": "turmeric powder 200g",          "zepto_search": "turmeric haldi powder 200g",
     "amazon_search": "turmeric powder haldi 200g"},
    {"item_id": "coriander_powder", "name": "Coriander Powder", "cpi_group": "Spices",
     "unit": "200g",   "weight": 3.4,
     "match_include": ['coriander', 'dhaniya'], "match_exclude": ['seed', 'whole', 'fresh', 'leaves', 'chutney'],
     "price_range": (15, 300),
     "blinkit_search": "coriander powder 200g",         "zepto_search": "coriander dhaniya powder 200g",
     "amazon_search": "coriander powder dhaniya 200g"},

    # ── Beverages (3.7) ─────────────────────────────────────────────────────
    {"item_id": "tea",    "name": "Tea Leaves",            "cpi_group": "Non-Alcoholic Beverages",
     "unit": "250g",   "weight": 3.7,
     "match_include": ['tea'], "match_exclude": ['green tea', 'herbal', 'bag', 'instant', 'iced'],
     "price_range": (40, 600),
     "blinkit_search": "tea leaves 250g",               "zepto_search": "tea leaves 250g",
     "amazon_search": "tea leaves 250g"},
]

assert abs(sum(i["weight"] for i in BASKET) - 100.1) < 0.5, \
    f"Basket weights sum to {sum(i['weight'] for i in BASKET)}, expected ~100"

BASKET_BY_ID: dict[str, BasketItem] = {i["item_id"]: i for i in BASKET}
CPI_GROUPS = sorted({i["cpi_group"] for i in BASKET})
