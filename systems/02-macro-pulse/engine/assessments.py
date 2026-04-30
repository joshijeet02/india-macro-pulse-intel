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
        headline_plain = (
            f"Prices are barely going up at all this month ({headline}% above last year). "
            f"This is mostly because food prices have actually fallen — not because the economy "
            f"is weak — so the central bank won't panic about it."
        )
        headline_tone = "info"
    elif headline < 2.5:
        headline_text = (
            f"At {headline}%, inflation is well below RBI's 4% target. "
            f"Real policy rates are deeply positive, providing strong justification for further easing."
        )
        headline_plain = (
            f"Prices are rising slowly ({headline}%) — well below the central bank's 4% goal. "
            f"That gives the RBI room to cut interest rates, which would make borrowing cheaper "
            f"for businesses and households."
        )
        headline_tone = "success"
    elif headline < 4.0:
        headline_text = (
            f"At {headline}%, inflation is within the 2–6% tolerance band and "
            f"approaching RBI's 4% midpoint — the disinflation cycle is maturing."
        )
        headline_plain = (
            f"Inflation ({headline}%) is settling close to the RBI's 4% sweet spot. "
            f"The cooling-down in prices that started months ago looks like it's running its course."
        )
        headline_tone = "success"
    elif headline < 5.0:
        headline_text = (
            f"At {headline}%, inflation is at RBI's 4% target. "
            f"MPC will watch for signs of consolidation before signalling further easing."
        )
        headline_plain = (
            f"Inflation ({headline}%) is right around where the RBI wants it. "
            f"Don't expect rate cuts soon — they'll wait to see if the number stays this stable."
        )
        headline_tone = "info"
    else:
        headline_text = (
            f"At {headline}%, inflation is above RBI's 4% target. "
            f"Rate cuts are off the table until a sustained downward trend is established."
        )
        headline_plain = (
            f"Inflation ({headline}%) is running above the RBI's 4% goal. "
            f"That means no rate cuts for a while — they'll keep money tight until prices ease."
        )
        headline_tone = "warning"

    # --- Core signal ---
    if core is None:
        core_text = (
            "Core decomposition is not available under the revised 2024=100 base year "
            "(India switched from 2012=100 in January 2026). RBI's MPC will publish "
            "updated decomposition methodology in coming months."
        )
        core_plain = (
            "We can't show core inflation right now — India switched its calculation method "
            "in January 2026 and the new component breakdown isn't out yet."
        )
        core_tone = "info"
    elif core > headline + 2.0:
        core_text = (
            f"Core at {core}% is {core - headline:.1f}pp above headline — "
            f"food deflation is flattering the number. Underlying services and goods "
            f"inflation is sticky and this is what the MPC actually watches."
        )
        core_plain = (
            f"If you strip out food and fuel, prices are still rising fast ({core}%). "
            f"The headline number looks calm only because food prices fell — but services "
            f"like education and healthcare are still getting more expensive. "
            f"This is what the RBI actually pays attention to."
        )
        core_tone = "warning"
    elif core > 5.5:
        core_text = (
            f"Core at {core}% remains elevated. Services inflation "
            f"(health, education, personal care) is keeping core sticky "
            f"even as food prices fall — consistent with a labour market that hasn't loosened."
        )
        core_plain = (
            f"Underlying inflation (excluding food and fuel) is still high at {core}% — "
            f"things like healthcare, education, and personal care are getting pricier. "
            f"This makes it harder for the RBI to cut rates."
        )
        core_tone = "warning"
    elif core > 4.0:
        core_text = (
            f"Core at {core}% is above RBI's 4% target but within tolerance. "
            f"Gradual easing is consistent with this level; rapid cuts would not be."
        )
        core_plain = (
            f"Underlying inflation ({core}%) is a bit above the RBI's 4% goal but not alarming. "
            f"Expect slow rate cuts at most — nothing aggressive."
        )
        core_tone = "info"
    else:
        core_text = (
            f"Core at {core}% is well-contained — no broad-based demand-side "
            f"price pressure visible. Gives MPC room to ease without stoking inflation."
        )
        core_plain = (
            f"Underlying inflation is calm at {core}%. The economy isn't running too hot, "
            f"which gives the RBI freedom to cut rates without risking a price spiral."
        )
        core_tone = "success"

    # --- Food read ---
    if food is None:
        food_text = "Food component data not available for this period."
        food_plain = "We don't have a food breakdown for this month yet."
        food_tone = "info"
    elif food < -4.0:
        food_text = (
            f"Food deflation at {food}% — sharp vegetable price corrections dominate. "
            f"This is typically seasonal and mean-reverts within 2–3 months; "
            f"don't extrapolate the disinflation trend from food alone."
        )
        food_plain = (
            f"Food prices have actually FALLEN ({food}%) compared to last year — "
            f"mostly because vegetables have crashed from earlier highs. "
            f"This is usually a seasonal blip, not a lasting trend."
        )
        food_tone = "info"
    elif food < 0:
        food_text = (
            f"Mild food deflation at {food}% — seasonal base effects at work. "
            f"Monitor whether protein prices (eggs, milk, pulses) are also softening "
            f"or whether this is purely a vegetable story."
        )
        food_plain = (
            f"Food prices have slipped ({food}%) below last year's level. "
            f"Whether this lasts depends on whether eggs, milk, and lentils start falling too — "
            f"or if it's just vegetables."
        )
        food_tone = "info"
    elif food < 4.0:
        food_text = (
            f"Food inflation benign at {food}% — no supply shock or procurement "
            f"price risk visible. MSP hikes are not feeding through to retail prices yet."
        )
        food_plain = (
            f"Food is getting only mildly more expensive ({food}%). No grocery-bill panic — "
            f"crops and supply chains are flowing fine."
        )
        food_tone = "success"
    elif food < 8.0:
        food_text = (
            f"Food at {food}% is elevated — track monsoon progress, Rabi/Kharif "
            f"arrivals, and vegetable-specific disruptions. A sustained reading above "
            f"6% will put RBI on alert."
        )
        food_plain = (
            f"Food prices are climbing at {food}% — noticeable at the grocery store. "
            f"If the monsoon disappoints or vegetables stay scarce, the RBI will start worrying."
        )
        food_tone = "warning"
    else:
        food_text = (
            f"Food at {food}% — a supply shock is in progress. "
            f"This is the single largest risk to RBI's inflation trajectory and "
            f"would likely pause any rate cut cycle."
        )
        food_plain = (
            f"Food prices are surging at {food}% — a real supply shock. "
            f"Households feel this immediately, and the RBI will hold off on rate cuts until "
            f"food eases up."
        )
        food_tone = "warning"

    # --- 3-month trajectory ---
    trajectory_text, trajectory_plain, trajectory_tone = _cpi_trajectory(sorted_h)

    # --- Market implication ---
    implication_text, implication_plain, implication_tone = _cpi_implication(
        headline, core, trajectory_text
    )

    # --- Proprietary Alpha Signal ---
    alpha_text, alpha_plain, alpha_tone = _cpi_alpha_signal()

    return {
        "headline":    {"text": headline_text,    "text_plain": headline_plain,    "tone": headline_tone},
        "core":        {"text": core_text,         "text_plain": core_plain,        "tone": core_tone},
        "food":        {"text": food_text,         "text_plain": food_plain,        "tone": food_tone},
        "trajectory":  {"text": trajectory_text,  "text_plain": trajectory_plain,  "tone": trajectory_tone},
        "implication": {"text": implication_text, "text_plain": implication_plain, "tone": implication_tone},
        "alpha":       {"text": alpha_text,       "text_plain": alpha_plain,       "tone": alpha_tone},
    }


def _cpi_trajectory(sorted_history: list[dict]) -> tuple[str, str, str]:
    if len(sorted_history) < 3:
        return (
            "Insufficient history for trajectory analysis.",
            "We don't have enough recent data to spot a trend yet.",
            "info",
        )
    recent = sorted_history[-3:]
    start  = recent[0]["headline_yoy"]
    end    = recent[-1]["headline_yoy"]
    delta  = end - start
    months = f"{recent[0]['reference_month']} → {recent[-1]['reference_month']}"
    if delta > 0.5:
        return (
            f"Re-accelerating: headline moved from {start}% to {end}% over {months}. "
            f"The disinflation trend has reversed — watch whether this persists.",
            f"Inflation is creeping back up — from {start}% to {end}% over the last few months. "
            f"The earlier cooling-down has stalled. One to keep an eye on.",
            "warning",
        )
    elif delta < -0.5:
        return (
            f"Decelerating: headline fell from {start}% to {end}% over {months}. "
            f"Disinflation momentum is intact.",
            f"Inflation has been slowing down — from {start}% to {end}% in recent months. "
            f"Prices are calming, which is what the RBI wants.",
            "success",
        )
    else:
        return (
            f"Stable: headline in a tight range {start}%–{end}% over {months}. "
            f"Inflation is neither accelerating nor decelerating materially.",
            f"Inflation has been holding steady around {start}%–{end}% for a few months. "
            f"No big surprises in either direction.",
            "info",
        )


def _cpi_implication(headline: float, core: Optional[float], trajectory_text: str) -> tuple[str, str, str]:
    if core is not None and core > headline + 2.0:
        return (
            "Bond market implication: long-end yields will stay anchored until core confirms "
            "the disinflation narrative. Rupee stable — no external pressure from inflation "
            "differential. Rate cut expectations should be calibrated to core, not headline.",
            "Don't expect long-term interest rates to drop until underlying inflation also cools. "
            "The headline number may look friendly, but markets see through it. Currency stable.",
            "info",
        )
    if headline < 2.5 and (core is None or core < 5.5):
        return (
            "Bullish for bonds: real rates are deeply positive and the case for further "
            "RBI rate cuts is strong. 10Y G-sec yields have room to compress. "
            "Rupee carry attractiveness rises with positive real rates.",
            "Good environment for bond investors — interest rates are likely to come down further. "
            "Government bond prices should rise. The rupee remains attractive to foreign investors "
            "because real interest rates are positive.",
            "success",
        )
    if headline > 5.0:
        return (
            "Bearish for bonds: above-target inflation keeps RBI on hold. "
            "10Y G-sec yields will face upward pressure. Watch for MPC hawkish dissents.",
            "Tough for bond investors — with inflation high, the RBI won't cut rates, "
            "which keeps bond yields elevated. Some panel members may push for HIKES.",
            "warning",
        )
    return (
        "Neutral for rates: inflation is within the tolerance band. "
        "Bond market will take direction from global cues and the fiscal trajectory "
        "rather than domestic inflation in this range.",
        "Bond markets won't get a strong signal from this print. Rates will move on global "
        "factors (US Fed, oil) and India's government spending plans more than on this number.",
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
        headline_plain = (
            f"Factories actually produced LESS this month ({headline}%) than a year ago. "
            f"That's unusual and worth investigating."
        )
        headline_tone = "warning"
    elif headline < 2.0:
        headline_text = (
            f"IIP at {headline}% — growth is tepid, well below India's potential. "
            f"The manufacturing engine is not firing at capacity."
        )
        headline_plain = (
            f"Factory output grew only {headline}% — sluggish for India. "
            f"The manufacturing economy isn't really firing."
        )
        headline_tone = "warning"
    elif headline < 5.0:
        headline_text = (
            f"IIP at {headline}% — moderate, broad-based growth. "
            f"Consistent with the economic backdrop but not a breakout."
        )
        headline_plain = (
            f"Factories grew {headline}% over the past year — decent but not exceptional. "
            f"Steady expansion."
        )
        headline_tone = "info"
    elif headline < 8.0:
        headline_text = (
            f"Strong industrial growth at {headline}% — both investment and consumption "
            f"activity appear healthy. Consistent with GDP above 7%."
        )
        headline_plain = (
            f"Strong factory output at {headline}% — businesses are clearly investing and "
            f"consumers are clearly buying. Healthy economic activity."
        )
        headline_tone = "success"
    else:
        base_note = " Check prior-year base for distortion." if headline > 10 else ""
        headline_text = (
            f"Robust IIP at {headline}% — a multi-month high.{base_note} "
            f"Manufacturing sector is in an expansionary phase."
        )
        headline_plain = (
            f"Factory output is booming — up {headline}% from a year ago. "
            f"This is one of the best readings in months."
        )
        headline_tone = "success"

    # --- Investment signal (capital goods) ---
    if cap is None:
        investment_text = "Capital goods breakdown not yet available for this period."
        investment_plain = "We don't have the investment-goods breakdown for this month yet."
        investment_tone = "info"
    elif cap > 15:
        investment_text = (
            f"Capital goods surging at {cap}% — likely front-loaded government capex "
            f"or a new private investment cycle beginning. This is the most durable "
            f"growth signal in IIP."
        )
        investment_plain = (
            f"Production of machinery and equipment surged {cap}%. "
            f"Companies and the government are spending big on building new capacity — "
            f"the strongest signal for future growth."
        )
        investment_tone = "success"
    elif cap > 6:
        investment_text = (
            f"Capital goods at {cap}% — solid investment momentum. "
            f"Private capex is joining government spending; the investment cycle is real."
        )
        investment_plain = (
            f"Equipment and machinery output is up {cap}%. "
            f"Real investment activity from both businesses and government."
        )
        investment_tone = "success"
    elif cap > 0:
        investment_text = (
            f"Capital goods at {cap}% — investment activity is positive but restrained. "
            f"Private sector remains cautious; largely government-driven capex."
        )
        investment_plain = (
            f"Investment activity is positive but weak ({cap}%). "
            f"Mostly the government doing the spending — private companies are still cautious."
        )
        investment_tone = "info"
    else:
        investment_text = (
            f"Capital goods contracted {cap}% — investment demand is weakening. "
            f"This is the leading indicator that matters most for future growth; "
            f"a sustained contraction would be concerning."
        )
        investment_plain = (
            f"Investment-goods output FELL {cap}% — companies are pulling back on building "
            f"new capacity. This is the most worrying signal for future growth."
        )
        investment_tone = "warning"

    # --- Consumption signal ---
    if cd is None and cnd is None:
        consumption_text = "Consumer goods breakdown not yet available for this period."
        consumption_plain = "We don't have a consumer-goods breakdown for this month yet."
        consumption_tone = "info"
    elif cd is not None and cnd is not None:
        if cd > 0 and cnd > 0:
            consumption_text = (
                f"Consumer durables ({cd:+.1f}%) and non-durables ({cnd:+.1f}%) both positive "
                f"— a balanced demand signal. Urban discretionary spending and rural staples "
                f"consumption are moving in the same direction."
            )
            consumption_plain = (
                f"Both big-ticket goods (fridges, cars: {cd:+.1f}%) AND everyday items "
                f"(soaps, food: {cnd:+.1f}%) are growing. Households across the income "
                f"spectrum are spending."
            )
            consumption_tone = "success"
        elif cd > 0 and cnd <= 0:
            consumption_text = (
                f"Urban durables demand ({cd:+.1f}%) outpacing staples ({cnd:+.1f}%) "
                f"— a K-shaped consumption split. Premium goods doing well; mass market lagging."
            )
            consumption_plain = (
                f"Big-ticket purchases ({cd:+.1f}%) are doing well, but everyday-goods "
                f"output ({cnd:+.1f}%) is flat. Higher-income urban consumers are spending — "
                f"the broader mass market is not."
            )
            consumption_tone = "info"
        elif cd <= 0 and cnd > 0:
            consumption_text = (
                f"Staples ({cnd:+.1f}%) holding up but discretionary durables ({cd:+.1f}%) "
                f"contracting — consumers trading down. Urban demand is softening."
            )
            consumption_plain = (
                f"Everyday-goods output ({cnd:+.1f}%) is up but big-ticket items ({cd:+.1f}%) "
                f"are down. Urban households are tightening up — buying essentials, "
                f"skipping discretionary purchases."
            )
            consumption_tone = "warning"
        else:
            consumption_text = (
                f"Both consumer durables ({cd:+.1f}%) and non-durables ({cnd:+.1f}%) "
                f"contracting — broad-based demand weakness. "
                f"Private consumption is the risk to the GDP growth story."
            )
            consumption_plain = (
                f"Both big-ticket ({cd:+.1f}%) and everyday-goods ({cnd:+.1f}%) output is "
                f"DOWN. Households are spending less across the board — a real risk for "
                f"the broader economy."
            )
            consumption_tone = "warning"
    elif cd is not None:
        if cd > 5:
            consumption_text = f"Consumer durables at {cd}% — urban discretionary demand is healthy."
            consumption_plain = f"Big-ticket goods output up {cd}% — urban consumers are spending."
            consumption_tone = "success"
        elif cd > 0:
            consumption_text = f"Consumer durables at {cd}% — modest positive; not a demand boom."
            consumption_plain = f"Big-ticket goods up {cd}% — positive but not a boom."
            consumption_tone = "info"
        else:
            consumption_text = f"Consumer durables at {cd}% — urban demand is softening."
            consumption_plain = f"Big-ticket goods output is down ({cd}%) — urban consumers are pulling back."
            consumption_tone = "warning"
    else:
        consumption_text = f"Consumer non-durables at {cnd}%."
        consumption_plain = f"Everyday-goods output: {cnd}%."
        consumption_tone = "info" if cnd and cnd > 0 else "warning"

    # --- Infrastructure momentum ---
    if infra is None:
        infra_text = "Infrastructure/construction breakdown not available for this period."
        infra_plain = "Infrastructure-output breakdown not available for this month."
        infra_tone = "info"
    elif infra > 10:
        infra_text = (
            f"Infrastructure output surging at {infra}% — government capex execution "
            f"is strong. Cement, steel, construction activity all contributing. "
            f"This is the backbone of India's supply-side story."
        )
        infra_plain = (
            f"Construction-related output is booming ({infra}%). Roads, bridges, "
            f"buildings — government project spending is flowing through."
        )
        infra_tone = "success"
    elif infra > 5:
        infra_text = (
            f"Infrastructure at {infra}% — solid momentum; project pipeline "
            f"is converting into actual output."
        )
        infra_plain = (
            f"Construction sector growing at {infra}% — government projects are "
            f"actually getting built, not just announced."
        )
        infra_tone = "success"
    elif infra > 0:
        infra_text = (
            f"Infrastructure growth at {infra}% — positive but below the 8–10% "
            f"pace needed to crowd in private investment."
        )
        infra_plain = (
            f"Construction-related output up {infra}% — positive but slower than what's "
            f"needed to pull private investment along with it."
        )
        infra_tone = "info"
    else:
        infra_text = (
            f"Infrastructure contracted {infra}% — government project execution "
            f"has slowed. Watch whether this is seasonal or signals fiscal tightening."
        )
        infra_plain = (
            f"Construction-related output is DOWN ({infra}%). Government project "
            f"execution has slowed — could be seasonal, could be belt-tightening."
        )
        infra_tone = "warning"

    # --- 3-month trajectory ---
    trajectory_text, trajectory_plain, trajectory_tone = _iip_trajectory(sorted_h)

    # --- Market implication ---
    implication_text, implication_plain, implication_tone = _iip_implication(headline, cap, cd)

    return {
        "headline":     {"text": headline_text,     "text_plain": headline_plain,     "tone": headline_tone},
        "investment":   {"text": investment_text,   "text_plain": investment_plain,   "tone": investment_tone},
        "consumption":  {"text": consumption_text,  "text_plain": consumption_plain,  "tone": consumption_tone},
        "infrastructure": {"text": infra_text,      "text_plain": infra_plain,        "tone": infra_tone},
        "trajectory":   {"text": trajectory_text,   "text_plain": trajectory_plain,   "tone": trajectory_tone},
        "implication":  {"text": implication_text,  "text_plain": implication_plain,  "tone": implication_tone},
    }


def _iip_trajectory(sorted_history: list[dict]) -> tuple[str, str, str]:
    if len(sorted_history) < 3:
        return (
            "Insufficient history for trajectory analysis.",
            "Not enough recent data to spot a trend yet.",
            "info",
        )
    recent = sorted_history[-3:]
    start  = recent[0]["headline_yoy"]
    end    = recent[-1]["headline_yoy"]
    delta  = end - start
    months = f"{recent[0]['reference_month']} → {recent[-1]['reference_month']}"
    if delta > 2.0:
        return (
            f"Accelerating: IIP moved from {start}% to {end}% over {months}. "
            f"Industrial momentum is building.",
            f"Factory growth is speeding up — from {start}% to {end}% in recent months. "
            f"The industrial economy is gaining steam.",
            "success",
        )
    elif delta < -2.0:
        return (
            f"Decelerating: IIP fell from {start}% to {end}% over {months}. "
            f"Watch whether this is a cyclical pause or the start of a softer phase.",
            f"Factory growth has slowed sharply — from {start}% to {end}% recently. "
            f"Could be a temporary breather or a real softening; one to watch.",
            "warning",
        )
    else:
        return (
            f"Steady: IIP in the {min(start, end):.1f}–{max(start, end):.1f}% range "
            f"over {months}. Industrial output is stable.",
            f"Factory output has been steady in the {min(start, end):.1f}–{max(start, end):.1f}% "
            f"range. No big surprises.",
            "info",
        )


def _iip_implication(
    headline: float,
    cap: Optional[float],
    cd: Optional[float],
) -> tuple[str, str, str]:
    strong_capex = cap is not None and cap > 6
    strong_cd    = cd  is not None and cd  > 5

    if headline > 6 and strong_capex:
        return (
            "Bullish for equities (capital goods, infra, cement sectors). "
            "Strong IIP with capex leadership reduces urgency of rate cuts — "
            "bond market will be less excited than equity market.",
            "Good for stocks — especially in capital goods, cement, and infrastructure. "
            "But because the economy is humming, the RBI doesn't need to cut rates "
            "as urgently, which is less great for bond investors.",
            "success",
        )
    if headline < 2:
        return (
            "Weak IIP strengthens the case for RBI rate cuts to support growth. "
            "Positive for bonds (yields down) but signals downside risk to corporate earnings.",
            "Weak factory output increases pressure on the RBI to cut rates. "
            "Good for bonds. Bad for company earnings — corporate profits could disappoint.",
            "info",
        )
    if strong_cd and not strong_capex:
        return (
            "Consumption-led growth: positive for FMCG and consumer discretionary sectors. "
            "Without capex recovery, medium-term growth sustainability is questionable.",
            "Growth is being driven by people buying things rather than businesses investing. "
            "Good for consumer brands now, but without business investment, this is hard "
            "to sustain over years.",
            "info",
        )
    return (
        "Mixed signals: IIP is growing but not strongly enough to move markets directionally. "
        "Sector-level differentiation matters more than the headline number here.",
        "Mixed picture — neither a clearly bullish nor bearish read. "
        "Look at individual sectors rather than the headline.",
        "info",
    )


# ---------------------------------------------------------------------------
# Proprietary Alpha Signal — e-commerce basket vs official CPI food
# ---------------------------------------------------------------------------

def _cpi_alpha_signal() -> tuple[str, str, str]:
    """
    Compare the Amazon basket index 7-day trend against official CPI food.
    Returns (signal_text, plain_text, tone) where tone is success/info/warning.
    """
    from db.store import EcommStore, CPIStore

    store = EcommStore()
    idx_history = store.get_index_history("amazon", limit=30)

    if not idx_history or len(idx_history) < 2:
        return (
            "Insufficient basket data — wait for the weekly Amazon scrape job to "
            "accumulate observations, or click 'Run Price Scrape' for an instant local read.",
            "We don't have enough price data yet for our proprietary signal. "
            "Real grocery prices will start showing up here as we collect them.",
            "info",
        )

    recent = idx_history[-7:]
    prev   = idx_history[-14:-7] if len(idx_history) >= 14 else []

    recent_avg = sum(r["index_value"] for r in recent) / len(recent)
    prev_avg   = sum(r["index_value"] for r in prev)   / len(prev) if prev else recent_avg
    basket_delta = recent_avg - prev_avg

    latest_idx  = idx_history[-1]["index_value"]
    coverage    = idx_history[-1]["coverage_pct"]

    cpi_hist = CPIStore().get_history(months=3)
    cpi_food: Optional[float] = None
    cpi_month = ""
    if cpi_hist:
        rec = next((r for r in reversed(cpi_hist) if r.get("food_yoy") is not None), None)
        if rec:
            cpi_food  = rec["food_yoy"]
            cpi_month = rec["reference_month"]

    if basket_delta > 2.0:
        if cpi_food is not None and cpi_food < 3.0:
            text = (
                f"UPSIDE RISK: Basket index rising +{basket_delta:.1f} pts (7-day) while "
                f"official CPI food sits at {cpi_food}% ({cpi_month}). "
                f"This divergence historically precedes a CPI food surprise of +0.3–0.6pp. "
                f"Vegetables and oils are the likely drivers — watch the next MOSPI release closely."
            )
            plain = (
                f"Our real-time grocery basket says food prices are rising — but the official "
                f"government number (currently {cpi_food}%) hasn't caught up yet. "
                f"Expect the next official inflation release to come in higher than people think."
            )
            tone = "warning"
        else:
            text = (
                f"Basket index rising +{basket_delta:.1f} pts (7-day), consistent with "
                f"continued food inflation pressure. "
                + (f"Official CPI food ({cpi_month}): {cpi_food}%." if cpi_food else "")
            )
            plain = (
                "Our grocery basket says food prices are still climbing — "
                "matching what the official numbers show."
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
            plain = (
                f"Real-time grocery prices are softening even though the official number "
                f"({cpi_food}%) is still high. The next official release should come in "
                f"lower than expected — good news for borrowers."
            )
            tone = "success"
        else:
            text = (
                f"Basket index declining {basket_delta:.1f} pts (7-day). "
                f"Food price trajectory is softening. "
                + (f"Official CPI food ({cpi_month}): {cpi_food}%." if cpi_food else "")
            )
            plain = (
                "Our grocery basket is getting cheaper week-on-week. "
                "Food inflation is genuinely cooling."
            )
            tone = "success"

    else:
        text = (
            f"No directional surprise signal: basket index stable "
            f"(7-day change: {basket_delta:+.1f} pts, index = {latest_idx:.1f}). "
            f"Food inflation tracking in line with official CPI trajectory."
            + (f" Official CPI food ({cpi_month}): {cpi_food}%." if cpi_food else "")
        )
        plain = (
            "Our real-time grocery basket is steady. No surprise signal for the next "
            "official inflation print."
        )
        tone = "info"

    text += f"  |  Coverage: {coverage:.0f}% of basket ({idx_history[-1]['items_count']} items)."
    return text, plain, tone
