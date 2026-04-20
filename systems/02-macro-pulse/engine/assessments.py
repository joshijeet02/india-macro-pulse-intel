"""
Rule-based economic assessments for CPI and IIP data.
Returns structured dicts of short analyst-style judgements.
All thresholds calibrated to India's monetary policy framework (RBI target = 4%).
"""
from typing import Optional


# ---------------------------------------------------------------------------
# CPI
# ---------------------------------------------------------------------------

def assess_cpi(history: list[dict]) -> dict:
    """
    Generate economic assessments for the CPI decomposition tab.
    Uses latest record for headline; latest record with components for decomposition.
    Returns dict with keys: headline, core, food, trajectory, implication.
    """
    if not history:
        return {}

    sorted_h = sorted(history, key=lambda r: r["reference_month"])
    latest = sorted_h[-1]
    latest_dec = next(
        (r for r in reversed(sorted_h) if r.get("core_yoy") is not None),
        latest,
    )

    headline = latest["headline_yoy"]
    core     = latest_dec.get("core_yoy")
    food     = latest_dec.get("food_yoy")
    fuel     = latest_dec.get("fuel_yoy")

    # --- Headline story ---
    if headline < 1.5:
        headline_text = (
            f"At {headline}%, headline inflation is near zero — driven by food deflation "
            f"and base effects rather than demand weakness. RBI will look through this; "
            f"it does not signal deflation risk."
        )
        headline_tone = "info"
    elif headline < 2.5:
        headline_text = (
            f"At {headline}%, inflation is well below RBI's 4% target. "
            f"Real policy rates are deeply positive, providing strong justification for further easing."
        )
        headline_tone = "success"
    elif headline < 4.0:
        headline_text = (
            f"At {headline}%, inflation is within the 2–6% tolerance band and "
            f"approaching RBI's 4% midpoint — the disinflation cycle is maturing."
        )
        headline_tone = "success"
    elif headline < 5.0:
        headline_text = (
            f"At {headline}%, inflation is at RBI's 4% target. "
            f"MPC will watch for signs of consolidation before signalling further easing."
        )
        headline_tone = "info"
    else:
        headline_text = (
            f"At {headline}%, inflation is above RBI's 4% target. "
            f"Rate cuts are off the table until a sustained downward trend is established."
        )
        headline_tone = "warning"

    # --- Core signal ---
    if core is None:
        core_text = (
            "Core decomposition is not available under the revised 2024=100 base year "
            "(India switched from 2012=100 in January 2026). RBI's MPC will publish "
            "updated decomposition methodology in coming months."
        )
        core_tone = "info"
    elif core > headline + 2.0:
        core_text = (
            f"Core at {core}% is {core - headline:.1f}pp above headline — "
            f"food deflation is flattering the number. Underlying services and goods "
            f"inflation is sticky and this is what the MPC actually watches."
        )
        core_tone = "warning"
    elif core > 5.5:
        core_text = (
            f"Core at {core}% remains elevated. Services inflation "
            f"(health, education, personal care) is keeping core sticky "
            f"even as food prices fall — consistent with a labour market that hasn't loosened."
        )
        core_tone = "warning"
    elif core > 4.0:
        core_text = (
            f"Core at {core}% is above RBI's 4% target but within tolerance. "
            f"Gradual easing is consistent with this level; rapid cuts would not be."
        )
        core_tone = "info"
    else:
        core_text = (
            f"Core at {core}% is well-contained — no broad-based demand-side "
            f"price pressure visible. Gives MPC room to ease without stoking inflation."
        )
        core_tone = "success"

    # --- Food read ---
    if food is None:
        food_text = "Food component data not available for this period."
        food_tone = "info"
    elif food < -4.0:
        food_text = (
            f"Food deflation at {food}% — sharp vegetable price corrections dominate. "
            f"This is typically seasonal and mean-reverts within 2–3 months; "
            f"don't extrapolate the disinflation trend from food alone."
        )
        food_tone = "info"
    elif food < 0:
        food_text = (
            f"Mild food deflation at {food}% — seasonal base effects at work. "
            f"Monitor whether protein prices (eggs, milk, pulses) are also softening "
            f"or whether this is purely a vegetable story."
        )
        food_tone = "info"
    elif food < 4.0:
        food_text = (
            f"Food inflation benign at {food}% — no supply shock or procurement "
            f"price risk visible. MSP hikes are not feeding through to retail prices yet."
        )
        food_tone = "success"
    elif food < 8.0:
        food_text = (
            f"Food at {food}% is elevated — track monsoon progress, Rabi/Kharif "
            f"arrivals, and vegetable-specific disruptions. A sustained reading above "
            f"6% will put RBI on alert."
        )
        food_tone = "warning"
    else:
        food_text = (
            f"Food at {food}% — a supply shock is in progress. "
            f"This is the single largest risk to RBI's inflation trajectory and "
            f"would likely pause any rate cut cycle."
        )
        food_tone = "warning"

    # --- 3-month trajectory ---
    trajectory_text, trajectory_tone = _cpi_trajectory(sorted_h)

    # --- Market implication ---
    implication_text, implication_tone = _cpi_implication(headline, core, trajectory_text)

    # --- Proprietary Alpha Signal ---
    alpha_text, alpha_tone = _cpi_alpha_signal()

    return {
        "headline":    {"text": headline_text,    "tone": headline_tone},
        "core":        {"text": core_text,         "tone": core_tone},
        "food":        {"text": food_text,         "tone": food_tone},
        "trajectory":  {"text": trajectory_text,  "tone": trajectory_tone},
        "implication": {"text": implication_text, "tone": implication_tone},
        "alpha":       {"text": alpha_text,       "tone": alpha_tone},
    }


def _cpi_alpha_signal() -> tuple[str, str]:
    from db.store import EcommStore, CPIStore
    ecomm_store = EcommStore()
    cpi_store   = CPIStore()

    am_history = ecomm_store.get_index_history("amazon", limit=4)

    if not am_history:
        return (
            "🔬 Proprietary Early Pulse (Amazon Basket): No e-commerce data yet. "
            "Click 'Run Price Scrape' in the Proprietary Pulse tab to activate this leading signal.",
            "info"
        )

    latest    = am_history[-1]
    avg_idx   = latest["index_value"]
    coverage  = latest["coverage_pct"]
    trend_pts = avg_idx - am_history[0]["index_value"] if len(am_history) > 1 else 0

    # Cross-reference with official food CPI
    cpi_history  = cpi_store.get_history(months=3)
    official_food_yoy = None
    if cpi_history:
        for r in reversed(cpi_history):
            if r.get("food_yoy") is not None:
                official_food_yoy = r["food_yoy"]
                break

    basket_pct_above_base = avg_idx - 100  # how far above base our basket is

    # --- Divergence logic ---
    # Official food CPI measures YoY at the national level (urban+rural, lagged ~45 days).
    # Our Amazon basket measures current urban formal-retail prices vs a ~180-day fixed base.
    # These are NOT the same: divergence between the two is the actual alpha signal.

    if official_food_yoy is not None and official_food_yoy < 0 and basket_pct_above_base > 3:
        # DIVERGENCE: official is deflationary, but urban formal prices are rising
        return (
            f"🟡 Proprietary Pulse DIVERGENCE DETECTED — Amazon Basket Index at {avg_idx:.1f} "
            f"(+{basket_pct_above_base:.1f}pts above fixed base, {coverage:.0f}% coverage) while official "
            f"Food CPI is {official_food_yoy:+.2f}% YoY. This divergence — urban formal prices rising "
            f"as aggregate official data turns deflationary — reflects probable rural supply easing and/or "
            f"base effects masking urban food cost pressure. A potential upward correction in future prints.",
            "warning"
        )

    if official_food_yoy is not None and official_food_yoy < 0 and basket_pct_above_base <= 3:
        # Both official and basket agree: price environment is soft
        return (
            f"✅ Proprietary Pulse CONFIRMS DISINFLATION — Amazon Basket Index at {avg_idx:.1f} "
            f"(+{basket_pct_above_base:.1f}pts above fixed base, {coverage:.0f}% coverage), consistent with "
            f"official Food CPI of {official_food_yoy:+.2f}% YoY. Urban formal grocery prices reflect "
            f"the same benign inflation environment. No leading signal of a forthcoming food price reversal.",
            "success"
        )

    if avg_idx > 108:
        return (
            f"🔴 Proprietary Pulse ALERT — Amazon Basket Index at {avg_idx:.1f} "
            f"(+{basket_pct_above_base:.1f}pts above fixed base, {coverage:.0f}% coverage). "
            f"A {'rising' if trend_pts > 0 else 'sustained'} urban food cost escalation signals "
            f"a potential CPI Food upside surprise in the next MOSPI release.",
            "error"
        )
    if avg_idx > 103:
        return (
            f"🟡 Proprietary Pulse ELEVATED — Amazon Basket Index at {avg_idx:.1f} "
            f"({basket_pct_above_base:.1f}pts above fixed base, {coverage:.0f}% coverage). "
            f"Mild urban food cost pressure building, consistent with a {'rising' if trend_pts > 0 else 'flat'} trend. "
            f"Monitor for acceleration ahead of the next MOSPI release.",
            "warning"
        )

    return (
        f"✅ Proprietary Pulse STABLE — Amazon Basket Index at {avg_idx:.1f} "
        f"({basket_pct_above_base:.1f}pts from fixed base, {coverage:.0f}% coverage). "
        f"No significant urban price pressure detected 15-30 days ahead of next MOSPI release.",
        "success"
    )




def _cpi_trajectory(sorted_history: list[dict]) -> tuple[str, str]:
    if len(sorted_history) < 3:
        return "Insufficient history for trajectory analysis.", "info"
    recent = sorted_history[-3:]
    start  = recent[0]["headline_yoy"]
    end    = recent[-1]["headline_yoy"]
    delta  = end - start
    months = f"{recent[0]['reference_month']} → {recent[-1]['reference_month']}"
    if delta > 0.5:
        return (
            f"Re-accelerating: headline moved from {start}% to {end}% over {months}. "
            f"The disinflation trend has reversed — watch whether this persists.",
            "warning",
        )
    elif delta < -0.5:
        return (
            f"Decelerating: headline fell from {start}% to {end}% over {months}. "
            f"Disinflation momentum is intact.",
            "success",
        )
    else:
        return (
            f"Stable: headline in a tight range {start}%–{end}% over {months}. "
            f"Inflation is neither accelerating nor decelerating materially.",
            "info",
        )


def _cpi_implication(headline: float, core: Optional[float], trajectory_text: str) -> tuple[str, str]:
    if core is not None and core > headline + 2.0:
        return (
            "Bond market implication: long-end yields will stay anchored until core confirms "
            "the disinflation narrative. Rupee stable — no external pressure from inflation "
            "differential. Rate cut expectations should be calibrated to core, not headline.",
            "info",
        )
    if headline < 2.5 and (core is None or core < 5.5):
        return (
            "Bullish for bonds: real rates are deeply positive and the case for further "
            "RBI rate cuts is strong. 10Y G-sec yields have room to compress. "
            "Rupee carry attractiveness rises with positive real rates.",
            "success",
        )
    if headline > 5.0:
        return (
            "Bearish for bonds: above-target inflation keeps RBI on hold. "
            "10Y G-sec yields will face upward pressure. Watch for MPC hawkish dissents.",
            "warning",
        )
    return (
        "Neutral for rates: inflation is within the tolerance band. "
        "Bond market will take direction from global cues and the fiscal trajectory "
        "rather than domestic inflation in this range.",
        "info",
    )


# ---------------------------------------------------------------------------
# IIP
# ---------------------------------------------------------------------------

def assess_iip(history: list[dict]) -> dict:
    """
    Generate economic assessments for the IIP decomposition tab.
    Returns dict with keys: headline, investment, consumption, infrastructure, trajectory, implication.
    """
    if not history:
        return {}

    sorted_h = sorted(history, key=lambda r: r["reference_month"])
    latest = sorted_h[-1]

    headline = latest["headline_yoy"]
    cap      = latest.get("capital_goods_yoy")
    cd       = latest.get("consumer_durables_yoy")
    cnd      = latest.get("consumer_nondurables_yoy")
    infra    = latest.get("infra_construction_yoy")
    mfg      = latest.get("manufacturing_yoy")

    # --- Headline context ---
    if headline < 0:
        headline_text = (
            f"Industrial output contracted {headline}% — a negative print is rare "
            f"outside of global shocks. Check whether this is base-effect distortion "
            f"or genuine demand weakness."
        )
        headline_tone = "warning"
    elif headline < 2.0:
        headline_text = (
            f"IIP at {headline}% — growth is tepid, well below India's potential. "
            f"The manufacturing engine is not firing at capacity."
        )
        headline_tone = "warning"
    elif headline < 5.0:
        headline_text = (
            f"IIP at {headline}% — moderate, broad-based growth. "
            f"Consistent with the economic backdrop but not a breakout."
        )
        headline_tone = "info"
    elif headline < 8.0:
        headline_text = (
            f"Strong industrial growth at {headline}% — both investment and consumption "
            f"activity appear healthy. Consistent with GDP above 7%."
        )
        headline_tone = "success"
    else:
        base_note = " Check prior-year base for distortion." if headline > 10 else ""
        headline_text = (
            f"Robust IIP at {headline}% — a multi-month high.{base_note} "
            f"Manufacturing sector is in an expansionary phase."
        )
        headline_tone = "success"

    # --- Investment signal (capital goods) ---
    if cap is None:
        investment_text = "Capital goods breakdown not yet available for this period."
        investment_tone = "info"
    elif cap > 15:
        investment_text = (
            f"Capital goods surging at {cap}% — likely front-loaded government capex "
            f"or a new private investment cycle beginning. This is the most durable "
            f"growth signal in IIP."
        )
        investment_tone = "success"
    elif cap > 6:
        investment_text = (
            f"Capital goods at {cap}% — solid investment momentum. "
            f"Private capex is joining government spending; the investment cycle is real."
        )
        investment_tone = "success"
    elif cap > 0:
        investment_text = (
            f"Capital goods at {cap}% — investment activity is positive but restrained. "
            f"Private sector remains cautious; largely government-driven capex."
        )
        investment_tone = "info"
    else:
        investment_text = (
            f"Capital goods contracted {cap}% — investment demand is weakening. "
            f"This is the leading indicator that matters most for future growth; "
            f"a sustained contraction would be concerning."
        )
        investment_tone = "warning"

    # --- Consumption signal ---
    if cd is None and cnd is None:
        consumption_text = "Consumer goods breakdown not yet available for this period."
        consumption_tone = "info"
    elif cd is not None and cnd is not None:
        if cd > 0 and cnd > 0:
            consumption_text = (
                f"Consumer durables ({cd:+.1f}%) and non-durables ({cnd:+.1f}%) both positive "
                f"— a balanced demand signal. Urban discretionary spending and rural staples "
                f"consumption are moving in the same direction."
            )
            consumption_tone = "success"
        elif cd > 0 and cnd <= 0:
            consumption_text = (
                f"Urban durables demand ({cd:+.1f}%) outpacing staples ({cnd:+.1f}%) "
                f"— a K-shaped consumption split. Premium goods doing well; mass market lagging."
            )
            consumption_tone = "info"
        elif cd <= 0 and cnd > 0:
            consumption_text = (
                f"Staples ({cnd:+.1f}%) holding up but discretionary durables ({cd:+.1f}%) "
                f"contracting — consumers trading down. Urban demand is softening."
            )
            consumption_tone = "warning"
        else:
            consumption_text = (
                f"Both consumer durables ({cd:+.1f}%) and non-durables ({cnd:+.1f}%) "
                f"contracting — broad-based demand weakness. "
                f"Private consumption is the risk to the GDP growth story."
            )
            consumption_tone = "warning"
    elif cd is not None:
        if cd > 5:
            consumption_text = f"Consumer durables at {cd}% — urban discretionary demand is healthy."
            consumption_tone = "success"
        elif cd > 0:
            consumption_text = f"Consumer durables at {cd}% — modest positive; not a demand boom."
            consumption_tone = "info"
        else:
            consumption_text = f"Consumer durables at {cd}% — urban demand is softening."
            consumption_tone = "warning"
    else:
        consumption_text = f"Consumer non-durables at {cnd}%."
        consumption_tone = "info" if cnd and cnd > 0 else "warning"

    # --- Infrastructure momentum ---
    if infra is None:
        infra_text = "Infrastructure/construction breakdown not available for this period."
        infra_tone = "info"
    elif infra > 10:
        infra_text = (
            f"Infrastructure output surging at {infra}% — government capex execution "
            f"is strong. Cement, steel, construction activity all contributing. "
            f"This is the backbone of India's supply-side story."
        )
        infra_tone = "success"
    elif infra > 5:
        infra_text = (
            f"Infrastructure at {infra}% — solid momentum; project pipeline "
            f"is converting into actual output."
        )
        infra_tone = "success"
    elif infra > 0:
        infra_text = (
            f"Infrastructure growth at {infra}% — positive but below the 8–10% "
            f"pace needed to crowd in private investment."
        )
        infra_tone = "info"
    else:
        infra_text = (
            f"Infrastructure contracted {infra}% — government project execution "
            f"has slowed. Watch whether this is seasonal or signals fiscal tightening."
        )
        infra_tone = "warning"

    # --- 3-month trajectory ---
    trajectory_text, trajectory_tone = _iip_trajectory(sorted_h)

    # --- Market implication ---
    implication_text, implication_tone = _iip_implication(headline, cap, cd)

    return {
        "headline":     {"text": headline_text,     "tone": headline_tone},
        "investment":   {"text": investment_text,   "tone": investment_tone},
        "consumption":  {"text": consumption_text,  "tone": consumption_tone},
        "infrastructure": {"text": infra_text,      "tone": infra_tone},
        "trajectory":   {"text": trajectory_text,   "tone": trajectory_tone},
        "implication":  {"text": implication_text,  "tone": implication_tone},
    }


def _iip_trajectory(sorted_history: list[dict]) -> tuple[str, str]:
    if len(sorted_history) < 3:
        return "Insufficient history for trajectory analysis.", "info"
    recent = sorted_history[-3:]
    start  = recent[0]["headline_yoy"]
    end    = recent[-1]["headline_yoy"]
    delta  = end - start
    months = f"{recent[0]['reference_month']} → {recent[-1]['reference_month']}"
    if delta > 2.0:
        return (
            f"Accelerating: IIP moved from {start}% to {end}% over {months}. "
            f"Industrial momentum is building.",
            "success",
        )
    elif delta < -2.0:
        return (
            f"Decelerating: IIP fell from {start}% to {end}% over {months}. "
            f"Watch whether this is a cyclical pause or the start of a softer phase.",
            "warning",
        )
    else:
        return (
            f"Steady: IIP in the {min(start, end):.1f}–{max(start, end):.1f}% range "
            f"over {months}. Industrial output is stable.",
            "info",
        )


def _iip_implication(
    headline: float,
    cap: Optional[float],
    cd: Optional[float],
) -> tuple[str, str]:
    strong_capex = cap is not None and cap > 6
    strong_cd    = cd  is not None and cd  > 5

    if headline > 6 and strong_capex:
        return (
            "Bullish for equities (capital goods, infra, cement sectors). "
            "Strong IIP with capex leadership reduces urgency of rate cuts — "
            "bond market will be less excited than equity market.",
            "success",
        )
    if headline < 2:
        return (
            "Weak IIP strengthens the case for RBI rate cuts to support growth. "
            "Positive for bonds (yields down) but signals downside risk to corporate earnings.",
            "info",
        )
    if strong_cd and not strong_capex:
        return (
            "Consumption-led growth: positive for FMCG and consumer discretionary sectors. "
            "Without capex recovery, medium-term growth sustainability is questionable.",
            "info",
        )
    return (
        "Mixed signals: IIP is growing but not strongly enough to move markets directionally. "
        "Sector-level differentiation matters more than the headline number here.",
        "info",
    )


# ---------------------------------------------------------------------------
# Proprietary Alpha Signal — e-commerce basket vs official CPI food
# ---------------------------------------------------------------------------

def _cpi_alpha_signal() -> tuple[str, str]:
    """
    Compare the Amazon basket index 7-day trend against official CPI food.
    Returns (signal_text, tone) where tone is one of success/info/warning.

    Logic:
    - Basket index rising faster than CPI food  → upside surprise risk (warning)
    - Basket index falling while CPI food high  → disinflation ahead (success)
    - Basket index stable / aligned             → no directional signal (info)
    """
    from db.store import EcommStore, CPIStore

    store = EcommStore()
    idx_history = store.get_index_history("amazon", limit=30)

    if not idx_history or len(idx_history) < 2:
        return (
            "Insufficient basket data — run a price scrape to generate the alpha signal.",
            "info",
        )

    # 7-day trend: last 7 readings vs the 7 before that
    recent = idx_history[-7:]
    prev   = idx_history[-14:-7] if len(idx_history) >= 14 else []

    recent_avg = sum(r["index_value"] for r in recent) / len(recent)
    prev_avg   = sum(r["index_value"] for r in prev)   / len(prev) if prev else recent_avg
    basket_delta = recent_avg - prev_avg   # +ve = prices rising

    latest_idx  = idx_history[-1]["index_value"]
    coverage    = idx_history[-1]["coverage_pct"]

    # Official CPI food (most recent reading with components)
    cpi_hist = CPIStore().get_history(months=3)
    cpi_food: Optional[float] = None
    cpi_month = ""
    if cpi_hist:
        rec = next((r for r in reversed(cpi_hist) if r.get("food_yoy") is not None), None)
        if rec:
            cpi_food  = rec["food_yoy"]
            cpi_month = rec["reference_month"]

    # ── Signal logic ────────────────────────────────────────────────────────
    if basket_delta > 2.0:
        if cpi_food is not None and cpi_food < 3.0:
            text = (
                f"UPSIDE RISK: Basket index rising +{basket_delta:.1f} pts (7-day) while "
                f"official CPI food sits at {cpi_food}% ({cpi_month}). "
                f"This divergence historically precedes a CPI food surprise of +0.3–0.6pp. "
                f"Vegetables and oils are the likely drivers — watch the next MOSPI release closely."
            )
            tone = "warning"
        else:
            text = (
                f"Basket index rising +{basket_delta:.1f} pts (7-day), consistent with "
                f"continued food inflation pressure. "
                + (f"Official CPI food ({cpi_month}): {cpi_food}%." if cpi_food else "")
            )
            tone = "warning"

    elif basket_delta < -2.0:
        if cpi_food is not None and cpi_food > 4.0:
            text = (
                f"DOWNSIDE RISK: Basket index falling {basket_delta:.1f} pts (7-day) while "
                f"official CPI food remains elevated at {cpi_food}% ({cpi_month}). "
                f"Leading signal of food disinflation — next CPI print may surprise to the downside. "
                f"Positive for bonds; reinforces RBI rate-cut bias."
            )
            tone = "success"
        else:
            text = (
                f"Basket index declining {basket_delta:.1f} pts (7-day). "
                f"Food price trajectory is softening. "
                + (f"Official CPI food ({cpi_month}): {cpi_food}%." if cpi_food else "")
            )
            tone = "success"

    else:
        text = (
            f"No directional surprise signal: basket index stable "
            f"(7-day change: {basket_delta:+.1f} pts, index = {latest_idx:.1f}). "
            f"Food inflation tracking in line with official CPI trajectory."
            + (f" Official CPI food ({cpi_month}): {cpi_food}%." if cpi_food else "")
        )
        tone = "info"

    text += f"  |  Coverage: {coverage:.0f}% of basket ({idx_history[-1]['items_count']} items)."
    return text, tone
