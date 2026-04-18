from dataclasses import dataclass
from typing import Literal

# Historical SPF tracking error standard deviations (India, 2018-2024)
_STD_DEVS = {
    "CPI": 0.18,   # pp — 0.2pp miss ≈ 1.1 sigma
    "IIP": 2.80,   # pp — 0.2pp miss ≈ 0.07 sigma (noise)
    "GDP": 0.40,
}

Magnitude = Literal["SIGNIFICANT", "NOTABLE", "IN LINE"]
Direction = Literal["ABOVE", "BELOW", "IN LINE"]


@dataclass
class SurpriseResult:
    actual: float
    consensus: float
    surprise: float
    z_score: float
    magnitude: Magnitude
    direction: Direction
    label: str


def compute_surprise(actual: float, consensus: float, indicator: str) -> SurpriseResult:
    """
    Compute surprise vs consensus and assign magnitude using z-score.

    Magnitude thresholds:
        |z| > 1.5 → SIGNIFICANT (rare event given historical distribution)
        |z| > 0.7 → NOTABLE
        otherwise → IN LINE
    """
    std = _STD_DEVS.get(indicator.upper(), 1.0)
    surprise = round(actual - consensus, 3)
    z = round(surprise / std, 2)

    if abs(z) > 1.5:
        magnitude: Magnitude = "SIGNIFICANT"
    elif abs(z) > 0.7:
        magnitude = "NOTABLE"
    else:
        magnitude = "IN LINE"

    if surprise > 0:
        direction: Direction = "ABOVE"
    elif surprise < 0:
        direction = "BELOW"
    else:
        direction = "IN LINE"

    if magnitude == "IN LINE":
        label = "IN LINE WITH CONSENSUS"
    else:
        label = f"{magnitude} {direction} CONSENSUS ({surprise:+.2f}pp, z={z:.1f})"

    return SurpriseResult(
        actual=actual,
        consensus=consensus,
        surprise=surprise,
        z_score=z,
        magnitude=magnitude,
        direction=direction,
        label=label,
    )
