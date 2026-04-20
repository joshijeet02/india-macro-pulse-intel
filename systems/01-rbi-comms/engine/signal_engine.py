from dataclasses import asdict, dataclass


HAWKISH_PHRASES = (
    "inflation risks remain elevated",
    "withdrawal of accommodation",
    "remain vigilant",
    "durable alignment",
    "upside risks",
    "price stability",
)

DOVISH_PHRASES = (
    "growth needs support",
    "space is opening",
    "support activity",
    "disinflation",
    "accommodative",
    "soften",
)

INFLATION_TERMS = (
    "inflation",
    "price pressures",
    "target",
    "price stability",
    "disinflation",
)

GROWTH_TERMS = (
    "growth",
    "activity",
    "demand",
    "investment",
    "consumption",
)

LIQUIDITY_TERMS = (
    "liquidity",
    "withdrawal of accommodation",
    "transmission",
    "financial conditions",
)


@dataclass
class CommunicationSignal:
    hawkish_score: int
    dovish_score: int
    net_score: int
    tone_label: str
    policy_bias: str
    inflation_mentions: int
    growth_mentions: int
    liquidity_mentions: int

    def to_record(self) -> dict:
        return asdict(self)


def _count_terms(text: str, phrases: tuple[str, ...]) -> int:
    return sum(text.count(phrase) for phrase in phrases)


def analyze_communication(text: str) -> CommunicationSignal:
    normalized = " ".join(text.lower().split())

    hawkish_score = _count_terms(normalized, HAWKISH_PHRASES)
    dovish_score = _count_terms(normalized, DOVISH_PHRASES)
    net_score = hawkish_score - dovish_score

    if net_score >= 2:
        tone_label = "hawkish"
        policy_bias = "tightening bias"
    elif net_score <= -2:
        tone_label = "dovish"
        policy_bias = "easing bias"
    else:
        tone_label = "neutral"
        policy_bias = "on hold"

    return CommunicationSignal(
        hawkish_score=hawkish_score,
        dovish_score=dovish_score,
        net_score=net_score,
        tone_label=tone_label,
        policy_bias=policy_bias,
        inflation_mentions=_count_terms(normalized, INFLATION_TERMS),
        growth_mentions=_count_terms(normalized, GROWTH_TERMS),
        liquidity_mentions=_count_terms(normalized, LIQUIDITY_TERMS),
    )
