"""
Plain-English summary of an MPC decision.

Deterministic (no LLM). Reads the structured stance signals + decision
record and produces a 3-paragraph lay-reader summary covering:
1. What just happened (decision facts)
2. What the stance signals about RBI's next move
3. What it means for borrowers / savers / equity investors

Used as the Plain English mode rendering in ui/mpc_view.py — analysts
still see the full analyst-grade AI brief; non-economist readers see this.
"""
from __future__ import annotations

from typing import Optional


def render_plain_summary(decision: dict, prior_decision: Optional[dict] = None) -> str:
    """
    Build a plain-English narrative from a `mpc_decisions` row + the prior one.
    Returns a Markdown-formatted string.
    """
    if not decision:
        return "No decision available."

    rate = decision.get("repo_rate")
    bps = decision.get("repo_rate_change_bps", 0) or 0
    vote_for = decision.get("vote_for")
    vote_against = decision.get("vote_against")
    stance = (decision.get("stance_label") or "neutral").replace("_", " ")
    cpi_proj = decision.get("cpi_projection_curr_value")
    cpi_fy = decision.get("cpi_projection_curr_fy")
    gdp_proj = decision.get("gdp_projection_curr_value")
    gdp_fy = decision.get("gdp_projection_curr_fy")
    meeting_date = decision.get("meeting_date")

    prior_stance = (prior_decision or {}).get("stance_label", "")
    prior_rate = (prior_decision or {}).get("repo_rate")
    stance_changed = prior_stance and prior_stance != decision.get("stance_label")
    rate_changed = prior_rate is not None and rate is not None and abs(prior_rate - rate) > 0.01

    # Para 1: the facts
    rate_phrase = (
        f"kept the repo rate **unchanged at {rate:.2f}%**" if bps == 0
        else f"**raised the repo rate by {abs(bps)} basis points to {rate:.2f}%**" if bps > 0
        else f"**cut the repo rate by {abs(bps)} basis points to {rate:.2f}%**"
    )
    vote_phrase = (
        f"a unanimous {vote_for}-{vote_against} vote" if vote_for == 6 and vote_against == 0
        else f"a {vote_for}-{vote_against} vote (with {vote_against} member{'s' if vote_against != 1 else ''} dissenting)"
        if vote_for is not None and vote_against is not None and vote_against > 0
        else "a vote"
    )
    para1 = (
        f"At the {meeting_date or 'most recent'} meeting, the RBI's six-member "
        f"Monetary Policy Committee {rate_phrase} on {vote_phrase}. "
        f"They chose to maintain a **{stance}** stance — meaning they're "
        f"{_stance_meaning(decision.get('stance_label'))}."
    )
    if stance_changed:
        para1 += (
            f" This is a **change from the previous {prior_stance.replace('_',' ')} stance** — "
            f"a meaningful shift in the policy posture."
        )

    # Para 2: what it signals
    para2_parts: list[str] = []
    if cpi_proj is not None and cpi_fy:
        para2_parts.append(
            f"The committee expects **inflation at around {cpi_proj:.1f}% over {cpi_fy}**"
        )
    if gdp_proj is not None and gdp_fy:
        para2_parts.append(
            f"and sees **GDP growth at {gdp_proj:.1f}%** over the same period"
        )
    para2 = (
        ". ".join(para2_parts) + ". "
        if para2_parts
        else "The committee did not publish fresh projections this meeting. "
    )
    para2 += _stance_outlook(decision.get("stance_label"), bps)

    # Para 3: what it means in everyday terms
    para3 = _what_it_means(decision.get("stance_label"), bps, rate, rate_changed)

    return "\n\n".join([para1, para2, para3])


def _stance_meaning(stance_label: Optional[str]) -> str:
    return {
        "accommodative":               "leaning toward making borrowing cheaper",
        "neutral":                     "in wait-and-see mode, deciding meeting-by-meeting",
        "withdrawal_of_accommodation": "actively pulling back the cheap-money policies of the past",
        "calibrated_withdrawal":       "moving away from accommodation but slowly",
        "calibrated_tightening":       "tightening policy in measured steps",
    }.get(stance_label or "neutral", "in their current policy posture")


def _stance_outlook(stance_label: Optional[str], bps: int) -> str:
    if bps > 0:
        return (
            "Because they tightened today, expect interest rates to stay where "
            "they are — or possibly go higher — at the next meeting."
        )
    if bps < 0:
        return (
            "Because they cut today, the path of least resistance is for rates "
            "to drift lower — though the next move depends on incoming data."
        )
    sl = stance_label or "neutral"
    if sl == "accommodative":
        return (
            "Even though rates didn't change today, the accommodative stance "
            "signals the next move is more likely to be a CUT than a hike."
        )
    if sl == "withdrawal_of_accommodation":
        return (
            "Even with no change today, the tightening stance suggests another "
            "HIKE is more likely than a cut at the next meeting."
        )
    return (
        "With a neutral stance, the next move could go either way — it depends "
        "on whether inflation surprises higher or growth surprises lower over "
        "the next two months."
    )


def _what_it_means(stance_label: Optional[str], bps: int, rate: Optional[float], rate_changed: bool) -> str:
    if bps < 0:
        return (
            "**For households:** home loans, car loans, and credit card balances "
            "should get cheaper soon as banks pass through the rate cut. "
            "**For savers:** fixed-deposit returns will fall in line. "
            "**For markets:** rate-sensitive sectors (banks, real estate) "
            "typically rally on rate cuts."
        )
    if bps > 0:
        return (
            "**For households:** EMIs on floating-rate loans (home, auto, "
            "credit card) will go up. **For savers:** fixed-deposit rates "
            "should rise. **For markets:** equity tends to react negatively "
            "to rate hikes, especially in rate-sensitive sectors."
        )
    # No change
    sl = stance_label or "neutral"
    if sl == "accommodative":
        return (
            "**For households and businesses:** the holding pattern means no "
            "immediate change to loan rates, but the dovish tone suggests "
            "borrowing could get cheaper in coming months. "
            "**For markets:** bond prices typically rally on accommodative "
            "stances; equity gets a tailwind."
        )
    if sl == "withdrawal_of_accommodation":
        return (
            "**For households:** keep an eye on your floating-rate loans — the "
            "tightening bias means rates could rise at the next meeting. "
            "**For markets:** bond yields stay elevated; rate-sensitive "
            "sectors face a headwind."
        )
    return (
        "**For households and businesses:** loan rates and savings rates "
        "should stay roughly where they are until the RBI sees more data. "
        "**For markets:** the neutral stance means the bond market will take "
        "direction from incoming inflation and growth data rather than from "
        "RBI commentary."
    )
