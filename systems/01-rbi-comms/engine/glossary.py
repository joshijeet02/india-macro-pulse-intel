"""
Plain-English glossary of RBI / monetary-policy terminology used in the app.

Each entry maps a term to (emoji_icon, plain_english_definition). Icons are
the visual hook on the Glossary tab; definitions are short enough to fit in a
tooltip and avoid defining technical concepts using more technical concepts.
"""

# Each entry: term -> (icon, definition)
GLOSSARY: dict[str, tuple[str, str]] = {
    # ─── Policy mechanics ───────────────────────────────────────────────────
    "Repo Rate": (
        "💰",
        "The interest rate at which the RBI lends short-term money to banks. "
        "When the repo rate rises, loans for businesses and households get "
        "more expensive; when it falls, they get cheaper. The headline rate "
        "everyone watches.",
    ),
    "MPC": (
        "🏛️",
        "Monetary Policy Committee — the six-member panel inside the RBI that "
        "votes on the repo rate every two months. Three members are RBI "
        "officials; three are external experts appointed by the government.",
    ),
    "MPC Vote": (
        "🗳️",
        "How the six members voted. A 6-0 unanimous vote signals committee "
        "agreement; a 4-2 split or a dissent points to internal disagreement "
        "and predicts more debate at the next meeting.",
    ),
    "Stance": (
        "🧭",
        "The RBI's official policy posture — typically one of 'accommodative' "
        "(easing bias, expect rate cuts), 'neutral' (data-dependent, no clear "
        "direction), or 'withdrawal of accommodation' (tightening bias, "
        "expect holds or hikes).",
    ),
    "Withdrawal of accommodation": (
        "🪜",
        "RBI-speak for 'tightening' — they're pulling back the cheap-money "
        "policies they had during the pandemic. Signals more concern about "
        "inflation than about growth.",
    ),
    "Accommodative": (
        "🕊️",
        "RBI is making it easier and cheaper to borrow. Used during downturns "
        "or when inflation is comfortably below target.",
    ),
    "Neutral stance": (
        "⚖️",
        "RBI is in 'wait and see' mode — neither pushing rates up nor pulling "
        "them down. Decisions go meeting-by-meeting based on incoming data.",
    ),
    # ─── Targets and frameworks ─────────────────────────────────────────────
    "RBI Target": (
        "🎯",
        "The Reserve Bank of India aims to keep CPI inflation at 4% on "
        "average, with a tolerance band of 2% to 6%. When inflation drifts "
        "outside the band for three quarters, the RBI must explain to the "
        "government in writing.",
    ),
    "Inflation targeting": (
        "📍",
        "The framework where the RBI's primary job is to keep inflation at "
        "4%. Adopted in 2016. All other goals (growth, employment) are "
        "subordinate to that target.",
    ),
    # ─── Forward guidance ───────────────────────────────────────────────────
    "Forward guidance": (
        "🔮",
        "The signals the RBI sends about its likely next move. Phrases like "
        "'data-dependent', 'calibrated', 'remain vigilant' all carry coded "
        "meaning to professional analysts about the policy path ahead.",
    ),
    "Data-dependent": (
        "📊",
        "Code for 'we'll decide based on incoming inflation and growth "
        "numbers, not based on a pre-committed plan.' Common during periods "
        "of uncertainty.",
    ),
    "Durable alignment": (
        "⚓",
        "RBI's promise to keep policy tight enough that inflation reaches "
        "the 4% target and STAYS there — not just dips through briefly. "
        "An anchor phrase signaling sustained vigilance.",
    ),
    # ─── Markets vocabulary ─────────────────────────────────────────────────
    "G-Sec": (
        "📜",
        "Government Security — Indian government bonds. The 10-year G-Sec "
        "yield is the benchmark long-term interest rate for the country.",
    ),
    "Bond yields": (
        "📈",
        "The interest rate the government pays to borrow money. Falls when "
        "investors expect lower future inflation or rate cuts; rises when "
        "they expect tightening.",
    ),
    "Liquidity": (
        "💧",
        "How much spare cash banks have parked with the RBI overnight. "
        "Surplus liquidity means easy credit; deficit means tighter "
        "interbank money market and higher short-term rates.",
    ),
    "LAF": (
        "🚪",
        "Liquidity Adjustment Facility — the RBI's main tool for managing "
        "overnight liquidity. Banks deposit excess cash here (earning the "
        "SDF rate) or borrow when short (paying the repo rate).",
    ),
    "SDF": (
        "🛏️",
        "Standing Deposit Facility — the rate the RBI pays banks for parking "
        "spare cash overnight. Forms the floor of the policy rate corridor.",
    ),
    "MSF": (
        "🚨",
        "Marginal Standing Facility — the rate at which banks can borrow "
        "emergency overnight funds from the RBI. Forms the ceiling of the "
        "rate corridor.",
    ),
    # ─── Process ────────────────────────────────────────────────────────────
    "MPC Resolution": (
        "📜",
        "The formal post-meeting statement summarizing the vote, the new "
        "rate, and the stance. Released right after each MPC meeting.",
    ),
    "MPC Minutes": (
        "📝",
        "Detailed record of the discussion at the MPC meeting, with each "
        "member's individual remarks. Released about two weeks after the "
        "meeting itself.",
    ),
    "Governor's Statement": (
        "🎤",
        "The RBI Governor's prepared remarks on MPC day, providing the "
        "rationale for the decision and assessment of growth and inflation. "
        "Read together with the formal Resolution.",
    ),
    "Press Conference": (
        "🗣️",
        "The Q&A session after the MPC, where journalists question the "
        "Governor and Deputy Governors. Often surfaces details not in the "
        "formal statement.",
    ),
    # ─── Macro context ──────────────────────────────────────────────────────
    "Headline CPI": (
        "🛒",
        "The overall rate at which consumer prices are rising compared to a "
        "year ago. The 'as-reported' inflation number that the RBI is "
        "officially targeting.",
    ),
    "Inflation": (
        "📈",
        "How fast prices are rising across the economy. The RBI tries to keep "
        "inflation near 4%. When inflation is too high, your household budget "
        "gets squeezed.",
    ),
    "Core inflation": (
        "🧱",
        "Inflation excluding food and fuel. Strips out the most volatile "
        "categories so you can see the underlying trend in prices. RBI "
        "watches core closely because it's stickier than headline.",
    ),
    "Disinflation": (
        "📉",
        "When inflation is positive but slowing down — prices are still "
        "rising, just at a calmer pace than before. Different from "
        "deflation (actual price falls).",
    ),
    "Real rates": (
        "🧮",
        "Interest rates minus inflation. When real rates are 'positive', "
        "savings earn more than inflation eats away — good for savers, "
        "tighter for borrowers.",
    ),
    "GDP Growth": (
        "📊",
        "How fast the entire Indian economy is expanding. Higher GDP growth "
        "generally means more jobs and better incomes across the country.",
    ),
    # ─── Reaction function / strategy ───────────────────────────────────────
    "Reaction function": (
        "⚙️",
        "The implicit rule explaining how a central bank responds to changes "
        "in inflation, growth, and other indicators. Analysts try to infer "
        "the RBI's reaction function from its language and decisions.",
    ),
    "Hawkish": (
        "🦅",
        "Lean toward higher rates. Concerned about inflation, willing to "
        "tolerate slower growth to keep prices in check.",
    ),
    "Dovish": (
        "🕊️",
        "Lean toward lower rates. More worried about supporting growth than "
        "about inflation creeping up.",
    ),
    "Insurance cut": (
        "🛡️",
        "A rate cut delivered before a clear economic slowdown — a "
        "preventive measure rather than a reactive one.",
    ),
    "Basis Points (bps)": (
        "📐",
        "A unit for measuring tiny changes in interest rates. 1 basis point "
        "= 0.01%. So '25 bps' means a rate moved by 0.25%.",
    ),
    "Transmission": (
        "⚡",
        "How quickly an RBI rate change actually reaches your bank's "
        "lending rates. If transmission is slow, a rate cut may take "
        "months before your EMI falls.",
    ),
}


def lookup(term: str) -> str:
    """Return the definition (no icon) for tooltip use. Empty string if missing."""
    entry = GLOSSARY.get(term)
    if entry is None:
        return ""
    return entry[1]


def lookup_with_icon(term: str) -> tuple[str, str]:
    """Return (icon, definition). ('', '') if missing."""
    return GLOSSARY.get(term, ("", ""))
