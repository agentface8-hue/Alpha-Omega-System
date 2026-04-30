"""
conviction_engine.py — SwingTrader AI v4.4 Conviction Scoring Engine
UPGRADED: Reversal-hunting + expanded confluence + weighted MTF.
No LLM calls — deterministic scoring from market data.
"""
from typing import Dict, Any, List


def score_ticker(data: Dict[str, Any], regime: Dict[str, Any], skip_calibration: bool = False) -> Dict[str, Any]:
    if "error" in data:
        return {**data, "hard_fail": True, "hard_fail_reason": data["error"],
                "conviction_pct": 0, "heat": "Cold", "trend": "MIXED",
                "pillar_scores": {"p1": 0, "p2": 0, "p3": 0, "p4": 0, "p5": 0}}

    tf = data.get("tf_breakdown", {})
    tf_daily = tf.get("tf_daily", "MIXED")
    tf_weekly = tf.get("tf_weekly", "MIXED")
    tf_65m = tf.get("tf_65m", "MIXED")
    tf_240m = tf.get("tf_240m", "MIXED")
    tas_str = data.get("tas", "0/4")
    tas_num = int(tas_str.split("/")[0]) if "/" in tas_str else 0
    ma150_pos = data.get("ma150_position", "below")
    cloud_pos = data.get("cloud_position", "below")
    vol_ratio = data.get("vol_ratio", 1.0)
    vol_dir = data.get("vol_direction", "NEUTRAL")
    rr = data.get("rr", 0)
    coiling = data.get("coiling", False)
    body_pct = data.get("body_pct", 0.5)
    is_doji = data.get("is_doji", False)
    long_upper_wick = data.get("long_upper_wick", False)
    bull_body = data.get("bull_body", False)
    close = data.get("last_close", 0)
    earnings = data.get("earnings_warning", "Clear")
    min_rr = regime.get("min_rr", 2.5)

    # NEW v4.4 data
    sustained_65m = data.get("sustained_65m", {})
    lr_channel = data.get("lr_channel", {})
    fvg_zones = data.get("fvg_zones", [])
    vol_profile = data.get("vol_profile", {})
    coil_data = data.get("coil_data", {})
    near_confluence = data.get("near_confluence", False)
    expanded_confluence = data.get("expanded_confluence", [])
    double_bottom = data.get("double_bottom", {})
    lr_slope = lr_channel.get("slope_pct", 0)

    hard_fail = False
    hard_fail_reason = ""
    caps = []
    ta_notes = []

    # ══════════════════════════════════════════════════
    # PHASE 1: MTF GATE — v4.4 REVERSAL-AWARE
    # ══════════════════════════════════════════════════

    # OLD: Weekly BEAR + Daily BEAR = instant kill
    # NEW: If 65m+4H are BULL (lead-time reversal), allow with cap
    if tf_weekly == "BEAR" and tf_daily == "BEAR":
        if tf_65m == "BULL" and tf_240m == "BULL" and sustained_65m.get("sustained", False):
            # REVERSAL DIVERGENCE — lower TFs leading the turn
            caps.append(70)
            ta_notes.append("Reversal Divergence: 65m+4H BULL vs W+D BEAR, sustained → cap 70%")
            if near_confluence:
                caps[-1] = 75  # bonus if at structural floor
                ta_notes.append("At confluence zone → reversal cap raised to 75%")
        elif tf_65m == "BULL" or tf_240m == "BULL":
            # Partial reversal — only one lower TF flipped
            caps.append(55)
            ta_notes.append("Partial reversal: only 1 lower TF BULL → cap 55%")
        else:
            hard_fail = True
            hard_fail_reason = "Weekly BEAR + Daily BEAR, no lower TF reversal → HARD FAIL"

    # Below 150MA + Weekly BEAR — allow reversal if at structural floor
    if ma150_pos == "below" and tf_weekly == "BEAR" and not hard_fail:
        if near_confluence and tf_65m == "BULL" and sustained_65m.get("sustained", False):
            caps.append(65)
            ta_notes.append("Below 150MA+W BEAR but at confluence w/ 65m sustained → cap 65%")
        elif tf_65m == "BULL" and tf_240m == "BULL":
            caps.append(55)
            ta_notes.append("Below 150MA+W BEAR, lower TFs bull → cap 55%")
        else:
            hard_fail = True
            hard_fail_reason = "Below 150MA + Weekly BEAR, no reversal signal → HARD FAIL"

    # TAS 0/4 — still hard fail (no timeframe is bullish)
    if tas_num == 0 and not hard_fail:
        hard_fail = True
        hard_fail_reason = f"TAS {tas_str} — Full bear alignment → HARD FAIL"

    # TAS-based caps
    if tas_num == 2:
        caps.append(65)
    if tas_num == 1:
        caps.append(55)
    if tf_weekly == "BEAR" and tf_daily == "BULL":
        caps.append(65)
    if ma150_pos == "below" and tf_weekly != "BEAR":
        caps.append(70)

    if hard_fail:
        return _build_result(data, regime, 0, {"p1":0,"p2":0,"p3":0,"p4":0,"p5":0},
                             True, hard_fail_reason, ta_notes)

    # ══════════════════════════════════════════════════
    # P1 — Trend & Cloud (25%) — WEIGHTED MTF
    # ══════════════════════════════════════════════════
    # v4.4: Weight 65m=1.5, 4H=1.5, Daily=1, Weekly=1 (total 5)
    weighted_bull = 0
    if tf_65m == "BULL": weighted_bull += 1.5
    if tf_240m == "BULL": weighted_bull += 1.5
    if tf_daily == "BULL": weighted_bull += 1.0
    if tf_weekly == "BULL": weighted_bull += 1.0
    weighted_tas = round(weighted_bull, 1)
    # Map to P1 score
    if weighted_tas >= 4.0: p1 = 90
    elif weighted_tas >= 3.0: p1 = 75
    elif weighted_tas >= 2.0: p1 = 60
    elif weighted_tas >= 1.5: p1 = 45
    else: p1 = 30

    # Cloud adjustments
    if cloud_pos == "above":
        p1 = min(p1 + 5, 100)
        ta_notes.append("Above cloud → P1 +5%")
    elif cloud_pos == "inside":
        caps.append(65)
        ta_notes.append("Inside cloud → cap 65%")
    elif cloud_pos == "below":
        caps.append(45)
        ta_notes.append("Below cloud → cap 45%")
    p1 = max(0, min(100, p1))

    # 65m sustained bonus
    bull_candles = sustained_65m.get("bull_candles", 0)
    if bull_candles >= 5:
        p1 = min(p1 + 8, 100)
        ta_notes.append(f"65m sustained {bull_candles} candles → P1 +8")
    elif bull_candles >= 3:
        p1 = min(p1 + 4, 100)
        ta_notes.append(f"65m sustained {bull_candles} candles → P1 +4")

    # Ascending channel bonus (LR channel slope > 0.03% per bar = clear uptrend)
    if lr_slope > 0.03:
        p1 = min(p1 + 8, 100)
        ta_notes.append(f"Ascending channel (slope +{lr_slope:.3f}%/bar) → P1 +8")
    elif lr_slope <= -0.03 and tas_num <= 2:
        # Declining channel with weak TF alignment = no good trend, cap it
        caps.append(58)
        ta_notes.append(f"Declining channel (slope {lr_slope:.3f}%/bar) + weak TAS → cap 58%")

    # ══════════════════════════════════════════════════
    # P2 — Price Structure + Level Precision (25%)
    # ══════════════════════════════════════════════════
    p2 = 50

    # Coiling — v4.4: 5-bar tighter = stronger
    if coil_data.get("coil5"):
        p2 += 25
        ta_notes.append("5-bar coiling → P2 +25 (tight spring)")
    elif coil_data.get("coil3") or coiling:
        p2 += 15
        ta_notes.append("3-bar coiling → P2 +15")

    if body_pct > 0.5: p2 += 10
    if bull_body: p2 += 5
    if is_doji: p2 -= 10

    # NEW v4.4: Level precision bonuses
    # At -2 StdDev of regression channel (structural floor)
    if lr_channel.get("at_lower"):
        p2 += 15
        ta_notes.append(f"At LR channel -2σ (${lr_channel['lower_2sd']}) → P2 +15")

    # In a Fair Value Gap (institutional entry zone)
    bullish_fvgs = [f for f in fvg_zones if f["type"] == "bullish"]
    in_fvg = any(f["bottom"] <= close <= f["top"] for f in bullish_fvgs)
    if in_fvg:
        p2 += 12
        ta_notes.append("Price in bullish FVG → P2 +12")

    # Near POC (high volume support)
    poc = vol_profile.get("poc", 0)
    if poc > 0 and abs(close - poc) / close < 0.005:
        p2 += 10
        ta_notes.append(f"At POC ${poc} → P2 +10")

    # Expanded confluence bonus (multiple floors overlap)
    if near_confluence:
        p2 += 15
        ta_notes.append(f"At expanded confluence ({len(expanded_confluence)} zones) → P2 +15")

    # Double bottom breakout — strongest reversal signal
    if double_bottom.get("confirmed"):
        p2 = min(p2 + 20, 100)
        ta_notes.append(f"Double bottom breakout (neckline ${double_bottom['neckline']}) → P2 +20")

    # Yellow Candle Exhaustion
    yellow_candle = (long_upper_wick and body_pct < 0.15 and vol_ratio > 1.8)
    if yellow_candle:
        caps.append(60)
        ta_notes.append("Yellow Candle Exhaustion → cap 60%")

    p2 = max(0, min(100, p2))

    # ══════════════════════════════════════════════════
    # P3 — Institutional Flow (20%) — REFINED CLIMAX
    # ══════════════════════════════════════════════════
    # v4.4: Distinguish big-red distribution vs small-body/green reversal accumulation
    if vol_dir == "ACCUMULATION" and tas_num >= 3:
        p3 = 85
        ta_notes.append("Accumulation on aligned trend → P3 STRONG")
    elif vol_dir == "ACCUMULATION" and tas_num < 3:
        # Accumulation against trend — possible early reversal
        p3 = 65
        ta_notes.append("Accumulation against trend → P3 reversal signal")
    elif vol_dir == "DISTRIBUTION":
        # v4.4: Check if it's a climax reversal (small body + high vol = potential spring)
        if body_pct < 0.25 and vol_ratio > 2.0:
            # Small body on high volume = absorption, not distribution
            p3 = 70
            ta_notes.append(f"Climax absorption: small body {body_pct:.0%} + vol {vol_ratio}x → P3 reversal")
        else:
            p3 = 45
            ta_notes.append("Distribution (big red + high vol) → P3 WEAK")
    elif vol_ratio < 1.3:
        p3 = 35
        ta_notes.append(f"Vol {vol_ratio}x too low → P3 WEAK")
    else:
        p3 = 60

    # Climax Reversal Risk (vol > 3x on low TAS)
    if vol_ratio > 3.0 and tas_num <= 2:
        ta_notes.append(f"Climax Reversal Risk (vol {vol_ratio}x, TAS {tas_str})")
        p3 = min(p3, 35)

    # ══════════════════════════════════════════════════
    # P4 — Risk/Reward Geometry (20%)
    # ══════════════════════════════════════════════════
    if rr < 1.5:
        hard_fail = True
        hard_fail_reason = f"R:R {rr}:1 below absolute min 1.5:1 → INSTANT FAIL"
        return _build_result(data, regime, 0, {"p1":p1,"p2":p2,"p3":p3,"p4":0,"p5":0},
                             True, hard_fail_reason, ta_notes)
    if rr < min_rr:
        p4 = 40
        caps.append(55)
        ta_notes.append(f"R:R {rr}:1 below regime min {min_rr}:1 → cap 55%")
    else:
        p4 = 90 if rr >= 3.0 else 80 if rr >= 2.5 else 70 if rr >= 2.0 else 50

    # ══════════════════════════════════════════════════
    # P5 — Catalyst & Timing (10%)
    # ══════════════════════════════════════════════════
    p5 = 80
    if "HARD FAIL" in earnings:
        hard_fail = True
        hard_fail_reason = f"Earnings {earnings} → HARD FAIL"
        return _build_result(data, regime, 0, {"p1":p1,"p2":p2,"p3":p3,"p4":p4,"p5":0},
                             True, hard_fail_reason, ta_notes)
    elif "Half size" in earnings:
        p5 = 50
        ta_notes.append(f"Earnings {earnings} → half size")

    # ══════════════════════════════════════════════════
    # CONVICTION SYNTHESIS
    # ══════════════════════════════════════════════════
    pillar_scores = {"p1": p1, "p2": p2, "p3": p3, "p4": p4, "p5": p5}
    raw_cv = round(p1 * 0.25 + p2 * 0.25 + p3 * 0.20 + p4 * 0.20 + p5 * 0.10)
    conviction = raw_cv
    for cap in caps:
        conviction = min(conviction, cap)

    # Apply calibration if available (skip during backtesting)
    if not skip_calibration:
        try:
            from core.calibrator import apply_calibration
            calibrated = apply_calibration(conviction)
            if calibrated != conviction:
                ta_notes.append(f"Calibrated: {conviction}% → {calibrated}%")
                conviction = calibrated
        except Exception:
            pass  # calibration not available, use raw

    return _build_result(data, regime, conviction, pillar_scores, False, "", ta_notes)


def _build_result(data: Dict, regime: Dict, conviction: int, pillars: Dict,
                  hard_fail: bool, hard_fail_reason: str, ta_notes: List[str]) -> Dict[str, Any]:
    if hard_fail: heat = "Cold"
    elif conviction >= 75: heat = "TOP"
    elif conviction >= 60: heat = "Hot"
    elif conviction >= 45: heat = "Neutral"
    else: heat = "Cold"

    tf = data.get("tf_breakdown", {})
    bulls = sum(1 for v in tf.values() if v == "BULL")
    trend = "BULL" if bulls >= 3 else "BEAR" if bulls <= 1 else "MIXED"

    return {
        "ticker": data.get("symbol", "?"),
        "name": data.get("name", ""),
        "sector": data.get("sector", ""),
        "last_close": data.get("last_close", 0),
        "last_date": data.get("last_date", ""),
        "stale": False,
        "mkt_cap_b": data.get("mkt_cap_b", 0),
        "conviction_pct": conviction,
        "heat": heat,
        "trend": trend,
        "tas": data.get("tas", "0/4"),
        "ma150_position": data.get("ma150_position", "below"),
        "tf_breakdown": data.get("tf_breakdown", {}),
        "entry_low": data.get("entry_low", 0),
        "entry_high": data.get("entry_high", 0),
        "sl": data.get("sl", 0),
        "tp1": data.get("tp1", 0),
        "tp2": data.get("tp2", 0),
        "tp3": data.get("tp3", 0),
        "qty": data.get("qty", 0),
        "vol_ratio": data.get("vol_ratio", 0),
        "vol_direction": data.get("vol_direction", "NEUTRAL"),
        "earnings_warning": data.get("earnings_warning", "Clear"),
        "hard_fail": hard_fail,
        "hard_fail_reason": hard_fail_reason,
        "coiling": data.get("coiling", False),
        "pillar_scores": pillars,
        "confluence_zones": data.get("confluence_zones", []),
        "fvg_zones": data.get("fvg_zones", []),
        "ta_note": " · ".join(ta_notes) if ta_notes else f"TAS {data.get('tas','?')}. RSI {data.get('rsi',50)}.",
        "rr": data.get("rr", 0),
        "plan": "",
        "rsi": data.get("rsi", 50),
    }


def run_scan(symbols: List[str]) -> Dict[str, Any]:
    from core.market_data import fetch_market_regime, fetch_multiple_tickers
    print(f"[SCAN] Fetching market regime...")
    regime = fetch_market_regime()
    print(f"[SCAN] Regime: {regime['regime']} | VIX: {regime['vix']}")
    print(f"[SCAN] Fetching data for {len(symbols)} tickers...")
    raw_data = fetch_multiple_tickers(symbols)
    print(f"[SCAN] Scoring with v4.4 5-pillar framework...")
    results = []
    for data in raw_data:
        scored = score_ticker(data, regime)
        results.append(scored)
    non_fails = sorted([r for r in results if not r["hard_fail"]],
                       key=lambda x: x["conviction_pct"], reverse=True)
    fails = [r for r in results if r["hard_fail"]]
    sorted_results = non_fails + fails

    for i, r in enumerate(sorted_results[:3]):
        if not r["hard_fail"]:
            r["plan"] = (f"Entry: decisive close ${r['entry_low']}-${r['entry_high']} in final 30min. "
                         f"SL: ${r['sl']} (ATR triple-guard). "
                         f"TP1: ${r['tp1']} (exit 40%, move SL to BE). "
                         f"TP2: ${r['tp2']} (exit 45%). R:R {r.get('rr', '?')}:1.")

    spy_chg = regime.get("spy_change_pct", 0)
    direction = "up" if spy_chg > 0 else "down"
    header = (f"SPY {direction} {abs(spy_chg)}% at ${regime.get('spy_close',0)}. "
              f"VIX at {regime['vix']} — {regime['regime']} regime. "
              f"Min R:R requirement: {regime['min_rr']}:1.")

    return {
        "market_header": header,
        "market_regime": regime["regime"],
        "vix_estimate": regime["vix"],
        "results": sorted_results
    }
