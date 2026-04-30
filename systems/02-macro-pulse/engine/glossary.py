"""
Plain-English glossary of macro terminology used in the app.

Each entry is short enough for a tooltip (one or two sentences) and avoids
defining technical concepts using more technical concepts.
"""

GLOSSARY: dict[str, str] = {
    # CPI side
    "Headline CPI": (
        "The overall rate at which consumer prices are rising compared to a "
        "year ago. It includes everything households buy — food, fuel, rent, "
        "transport — so it bounces around with seasonal stuff like vegetables."
    ),
    "Core CPI": (
        "Inflation excluding food and fuel. Strips out the most volatile "
        "categories so you can see the steady underlying trend in prices. "
        "RBI watches this more closely than headline CPI."
    ),
    "Food Inflation": (
        "How much more expensive the food group has gotten over the past year. "
        "In India this carries about 46% weight in the overall CPI basket, so "
        "moves here dominate the headline number."
    ),
    "Fuel Inflation": (
        "Year-on-year change in the 'Fuel & Light' group — household electricity, "
        "cooking gas, kerosene. Note: under the new 2024=100 base year (effective "
        "Jan 2026) this group was renamed and reweighted."
    ),
    "RBI Target": (
        "The Reserve Bank of India aims to keep CPI inflation at 4% on average, "
        "with a tolerance band of 2–6%. When inflation is below 4%, the RBI has "
        "room to cut interest rates; above 6%, they typically hold or hike."
    ),
    "MPC": (
        "Monetary Policy Committee — the six-member panel inside the RBI that "
        "votes on interest rate decisions. Meets every two months."
    ),
    "Real Rates": (
        "Interest rates minus inflation. When real rates are 'positive', savings "
        "earn more than inflation eats away — good for savers, but tighter for "
        "borrowers, which can slow the economy."
    ),
    "Bond Yields": (
        "The interest rate the government pays to borrow money. Falls when "
        "investors expect lower future inflation or rate cuts; rises when they "
        "expect tightening."
    ),
    "10Y G-Sec": (
        "10-year Government Security — the benchmark Indian government bond. "
        "Its yield is the standard reference for long-term interest rates."
    ),
    "Disinflation": (
        "When inflation is positive but slowing down — prices are still rising, "
        "just at a calmer pace than before. Different from deflation (actual "
        "price falls)."
    ),
    "Base Effect": (
        "When this year's inflation looks artificially high or low because last "
        "year's number was unusual. A spike in food prices last summer can "
        "make this summer's number look mild even if underlying pressure is real."
    ),

    # IIP side
    "IIP": (
        "Index of Industrial Production — measures the volume of factory output, "
        "mining, and electricity generation. India's main monthly indicator of "
        "supply-side economic activity."
    ),
    "Capital Goods": (
        "Machines, equipment, and tools that businesses buy to produce other "
        "goods. Strong capital-goods output usually means companies are "
        "investing for future growth."
    ),
    "Consumer Durables": (
        "Stuff people buy that lasts years — fridges, washing machines, cars. "
        "A barometer of urban discretionary spending."
    ),
    "Consumer Non-Durables": (
        "FMCG-style consumer goods: food, soaps, toiletries. Reflects "
        "broad-based household consumption including rural demand."
    ),
    "Use-Based Classification": (
        "MOSPI groups industrial output by what the products are used for: "
        "primary, capital, intermediate, infrastructure, durables, non-durables. "
        "Tells you whether growth is investment-led or consumption-led."
    ),
    "Capex": (
        "Capital expenditure — money companies (or the government) spend "
        "building new factories, roads, equipment. A leading indicator of "
        "future supply capacity."
    ),

    # Surprise / market terms
    "Consensus Forecast": (
        "The average of what professional economists expected the number to be. "
        "When the actual print is far from consensus, markets move."
    ),
    "Surprise Index": (
        "How far the actual data print landed from consensus, expressed in "
        "standard deviations. A z-score of +2 means a release that was twice "
        "the typical month-to-month volatility above expectations."
    ),
    "Laspeyres Index": (
        "A way of measuring price change by holding the basket of goods fixed. "
        "Tracks how much MORE you'd pay today for the EXACT same shopping list "
        "you bought at the start of the period."
    ),

    # Proprietary
    "Alpha Signal": (
        "A leading indicator we generate ourselves from real-time grocery "
        "scraping, designed to anticipate the official inflation print before "
        "MOSPI publishes it."
    ),
}


def lookup(term: str) -> str:
    """Return the definition or empty string if the term is not in the glossary."""
    return GLOSSARY.get(term, "")
