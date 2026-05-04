"""
Stance lexicon — phrase library tagged across 6 dimensions of MPC communication.

Each entry: (phrase, weight). Phrases match case-insensitively as substrings.
Weights are calibrated on a -1 (dovish/easing) to +1 (hawkish/tightening) axis
where applicable, or used as binary presence indicators where directional
weighting doesn't apply (e.g., forward_guidance markers).

The lexicon is intentionally over-included: more phrases catch more nuance.
False matches are cheaper than false misses because the engine outputs
EVIDENCE alongside the score, so an analyst can see what triggered the read.
"""
from __future__ import annotations

# ─── STANCE: the headline policy posture ────────────────────────────────────
# Hawkish (+) = withdrawal of accommodation / tightening
# Dovish (-)  = accommodative
# Neutral (0) = pause / data-dependent
STANCE = [
    ("withdrawal of accommodation",          +1.0),
    ("calibrated withdrawal of accommodation", +0.7),
    ("calibrated tightening",                +0.9),
    ("policy tightening",                    +0.7),
    ("focus remains on withdrawal",          +0.7),
    ("remain focused on withdrawal",         +0.7),
    ("remain neutral",                        0.0),
    ("neutral stance",                        0.0),
    ("stance to neutral",                     0.0),
    ("change of stance to neutral",          -0.2),
    ("remain accommodative",                 -1.0),
    ("accommodative stance",                 -1.0),
    ("stance is accommodative",              -1.0),
    ("continue with the accommodative",      -1.0),
]

# ─── FORWARD_GUIDANCE: language about the next move ─────────────────────────
# Tagged as binary categorical markers; the analyst cares about WHICH terms
# are present, not the score.
FORWARD_GUIDANCE = [
    ("data-dependent",                "data_dependent"),
    ("data dependent",                "data_dependent"),
    ("calibrated",                    "calibrated"),
    ("appropriate",                   "appropriate"),
    ("nimble",                        "nimble"),
    ("watchful",                      "watchful"),
    ("vigilant",                      "vigilant"),
    ("remain vigilant",               "vigilant"),
    ("remain on guard",               "on_guard"),
    ("flexibility",                   "flexibility"),
    ("decisive action",               "decisive_action"),
    ("durable alignment",             "durable_alignment"),
    ("sustained alignment",           "sustained_alignment"),
    ("ahead of the curve",            "ahead_of_curve"),
    ("forward-looking",               "forward_looking"),
    ("anchoring inflation expectations","anchor_expectations"),
]

# ─── GROWTH_ASSESSMENT ──────────────────────────────────────────────────────
# +1 (strongly positive on growth) to -1 (concerned)
GROWTH_ASSESSMENT = [
    ("robust growth",                +1.0),
    ("buoyant growth",               +1.0),
    ("strong momentum in economic",  +1.0),
    ("resilient",                    +0.7),
    ("steady growth",                +0.5),
    ("supportive of growth",         +0.5),
    ("growth remains",               +0.3),  # neutral filler — context dependent
    ("growth is expected to remain", +0.3),
    ("growth concerns",              -0.7),
    ("moderation in growth",         -0.7),
    ("moderating",                   -0.5),
    ("uneven recovery",              -0.7),
    ("downside risks to growth",     -0.7),
    ("loss of momentum",             -0.9),
    ("growth has weakened",          -0.9),
    ("growth needs support",         -0.9),
]

# ─── INFLATION_ASSESSMENT ───────────────────────────────────────────────────
# +1 (concerned, hawkish read) to -1 (comfortable, dovish read)
INFLATION_ASSESSMENT = [
    ("inflation risks remain elevated",        +1.0),
    ("inflation pressures",                    +0.7),
    ("upside risks to inflation",              +0.9),
    ("upward pressure on inflation",           +0.9),
    ("price pressures",                        +0.5),
    ("sticky inflation",                       +0.7),
    ("inflation has remained elevated",        +0.7),
    ("disinflation",                           -0.7),
    ("inflation is easing",                    -0.7),
    ("inflation has moderated",                -0.7),
    ("price stability",                         0.0),  # mantra; tracks separately
    ("aligning to the target",                 -0.3),
    # "durable alignment" is RBI's anchor-language for sustained tight policy
    # to bring inflation to target. Tracked as a forward-guidance marker
    # (see FORWARD_GUIDANCE) — NOT here, where the dovish weighting would be
    # misleading.
    ("comfortable buffer",                     -0.5),
    ("inflation outlook",                       0.0),  # filler
    ("benign inflation",                       -0.7),
    ("disinflation is broad-based",            -0.9),
    ("space is opening",                       -0.9),
]

# ─── LIQUIDITY_STANCE ────────────────────────────────────────────────────────
# +1 (tight) to -1 (loose). RBI's stance language separately tracked here
# because it sometimes diverges from the rate stance.
LIQUIDITY_STANCE = [
    ("liquidity surplus",                      -0.7),
    ("durable liquidity",                       0.0),
    ("ensure sufficient liquidity",            -0.5),
    ("withdrawal of liquidity",                +0.7),
    ("liquidity tightening",                   +0.7),
    ("absorb liquidity",                       +0.5),
    ("absorbed durably",                       +0.5),
    ("liquidity deficit",                      +0.7),
    ("active liquidity management",             0.0),
    ("nimble liquidity management",             0.0),
    ("transmission of policy rates",            0.0),  # neutral signal
    ("transmission has been satisfactory",     -0.3),
    ("system-level liquidity",                  0.0),
]

# ─── RISK_BALANCE ────────────────────────────────────────────────────────────
# +1 (downside-skewed = dovish) to -1 (upside-skewed = hawkish)
# Note: this dimension's sign convention is INVERTED — "balanced" = 0, "tilted to upside" = -1 (hawkish for inflation), "tilted to downside" = +1 (dovish read on growth)
RISK_BALANCE = [
    ("risks are broadly balanced",            0.0),
    ("risks are evenly balanced",             0.0),
    ("balance of risks",                      0.0),
    ("risks tilted to the upside",           -0.7),  # hawkish for inflation
    ("upside risks dominate",                -0.9),
    ("downside risks",                       +0.5),
    ("risks tilted to the downside",         +0.7),
    ("downside risks dominate",              +0.9),
    ("two-way risks",                         0.0),
    ("heightened uncertainty",                0.0),  # contextual
]


def all_dimensions() -> dict:
    """Convenience accessor."""
    return {
        "stance":               STANCE,
        "forward_guidance":     FORWARD_GUIDANCE,
        "growth_assessment":    GROWTH_ASSESSMENT,
        "inflation_assessment": INFLATION_ASSESSMENT,
        "liquidity_stance":     LIQUIDITY_STANCE,
        "risk_balance":         RISK_BALANCE,
    }
