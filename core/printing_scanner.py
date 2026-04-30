"""
printing_scanner.py — Dual-direction scanner (LONG + SHORT) for Printing Profits tab.

LONG signals:  reuses score_ticker() from conviction_engine — zero duplication.
SHORT signals: new score_short() with inverted logic.
               Stocks the existing scanner hard-fails as BEAR = short candidates.

Imports (read-only, no mutation of existing modules):
  core.market_data       → fetch_market_regime, fetch_multiple_tickers
  core.conviction_engine → score_ticker  (for longs)
  core.watchlists        → get_watchlist
  core.kelly_sizer       → kelly_size    (new)
  core.regime_engine     → get_strategy_mode (new)
"""
from typing import Dict, Any, List
import math


# ── Short conviction scoring ────────────────────────────────────────────────

def score_short(data: Dict[str, Any], regime: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score a ticker as a SHORT candidate.
    High conviction = strong bearish setup.

    Inverted 5-pillar logic:
      P1 — Bearish trend alignment  (all TFs bear = strong)
      P2 — Price at resistance / distribution structure
      P3 — Institutional distribution flow
      P4 — Short R:R geometry
      P5 — No earnings catalyst risk
    """
    if "error" in data:
        return {**data, "direction": "short", "conviction_pct": 0,
                "hard_fail": True, "hard_fail_reason": data["error"],
                "heat": "Cold", "pillar_scores": {}}

    tf        = data.get("tf_breakdown", {})
    tf_daily  = tf.get("tf_daily",  "MIXED")
    tf_weekly = tf.get("tf_weekly", "MIXED")
    tf_65m    = tf.get("tf_65m",    "MIXED")
    tf_240m   = tf.get("tf_240m",   "MIXED")
    tas_str   = data.get("tas", "0/4")
    tas_bear  = 4 - int(tas_str.split("/")[0]) if "/" in tas_str else 0  # inverted TAS

    ma150_pos  = data.get("ma150_position", "below")
    cloud_pos  = data.get("cloud_position", "above")
    vol_ratio  = data.get("vol_ratio", 1.0)
    vol_dir    = data.get("vol_direction", "NEUTRAL")
    rsi        = data.get("rsi", 50)
    close      = data.get("last_close", 0)
    earnings   = data.get("earnings_warning", "Clear")
    lr_channel = data.get("lr_channel", {})
    lr_slope   = lr_channel.get("slope_pct", 0)
    body_pct   = data.get("body_pct", 0.5)
    is_doji    = data.get("is_doji", False)

    hard_fail = False
    hard_fail_reason = ""
    caps = []
    ta_notes = []

    # ── HARD PASS gate — need actual bearish conditions ──────────────────────
    # If ALL timeframes are BULL → not a short candidate
    if tf_daily == "BULL" and tf_weekly == "BULL" and tf_65m == "BULL" and tf_240m == "BULL":
        return {
            "symbol": data.get("symbol", "?"), "direction": "short",
            "conviction_pct": 0, "hard_fail": True,
            "hard_fail_reason": "All TFs BULL — no short setup",
            "heat": "Cold", "pillar_scores": {}, "ta_note": "4/4 BULL, skip short",
        }

    # ── P1 — Bearish Trend Alignment (weighted MTF) ──────────────────────────
    bear_weight = 0
    if tf_65m  == "BEAR": bear_weight += 1.5
    if tf_240m == "BEAR": bear_weight += 1.5
    if tf_daily == "BEAR": bear_weight += 1.0
    if tf_weekly == "BEAR": bear_weight += 1.0

    if bear_weight >= 4.0:    p1 = 90
    elif bear_weight >= 3.0:  p1 = 75
    elif bear_weight >= 2.0:  p1 = 60
    elif bear_weight >= 1.5:  p1 = 45
    else:                     p1 = 30

    # Cloud position — below cloud = bearish confirmation
    if cloud_pos == "below":
        p1 = min(p1 + 8, 100)
        ta_notes.append("Below cloud → short P1 +8")
    elif cloud_pos == "above":
        caps.append(50)
        ta_notes.append("Above cloud → short capped 50%")

    # Below 150MA bonus
    if ma150_pos == "below":
        p1 = min(p1 + 5, 100)
        ta_notes.append("Below 150MA → short P1 +5")

    # Declining channel
    if lr_slope < -0.03:
        p1 = min(p1 + 8, 100)
        ta_notes.append(f"Declining channel ({lr_slope:.3f}%/bar) → short P1 +8")

    p1 = max(0, min(100, p1))

    # ── P2 — Distribution Structure ──────────────────────────────────────────
    p2 = 50
    # Bearish candle structure
    if not data.get("bull_body") and body_pct > 0.5:
        p2 += 15
        ta_notes.append("Strong bearish candle body → short P2 +15")
    if data.get("long_upper_wick"):
        p2 += 10
        ta_notes.append("Long upper wick rejection → short P2 +10")
    if is_doji:
        p2 += 5

    # At upper LR channel (resistance)
    lr_upper = lr_channel.get("upper_2sd", 0)
    if lr_upper > 0 and close >= lr_upper * 0.997:
        p2 += 15
        ta_notes.append(f"At LR channel +2σ resistance → short P2 +15")

    # RSI overbought
    if rsi > 70:
        p2 += 15
        ta_notes.append(f"RSI {rsi} overbought → short P2 +15")
    elif rsi > 65:
        p2 += 8
        ta_notes.append(f"RSI {rsi} elevated → short P2 +8")

    p2 = max(0, min(100, p2))

    # ── P3 — Institutional Distribution ──────────────────────────────────────
    if vol_dir == "DISTRIBUTION" and not data.get("bull_body"):
        p3 = 85
        ta_notes.append("Distribution (big red + high vol) → short P3 STRONG")
    elif vol_dir == "DISTRIBUTION":
        p3 = 65
        ta_notes.append("Distribution volume → short P3 solid")
    elif vol_dir == "ACCUMULATION":
        caps.append(55)
        p3 = 35
        ta_notes.append("Accumulation signal — limits short conviction")
    elif vol_ratio < 1.3:
        p3 = 40
    else:
        p3 = 55

    # Climax exhaustion (very high vol + small body = potential reversal → bearish)
    if vol_ratio > 3.0 and body_pct < 0.2 and not data.get("bull_body"):
        p3 = min(p3 + 15, 100)
        ta_notes.append(f"Climax selling ({vol_ratio}x vol) → short P3 +15")

    # ── P4 — Short R:R Geometry ───────────────────────────────────────────────
    # For shorts: entry near current price, SL above, TP below
    atr_val   = data.get("atr", close * 0.02)
    short_sl  = round(close + atr_val * 1.5, 2)
    short_tp1 = round(close - atr_val * 2.0, 2)
    short_tp2 = round(close - atr_val * 3.5, 2)
    sl_dist   = max(short_sl - close, 0.01)
    tp1_dist  = max(close - short_tp1, 0.01)
    rr        = round(tp1_dist / sl_dist, 2)

    min_rr = regime.get("min_rr", 2.0)
    if rr < 1.5:
        hard_fail = True
        hard_fail_reason = f"Short R:R {rr}:1 below 1.5 minimum → skip"
        return {
            "symbol": data.get("symbol", "?"), "direction": "short",
            "conviction_pct": 0, "hard_fail": True, "hard_fail_reason": hard_fail_reason,
            "heat": "Cold", "pillar_scores": {}, "ta_note": hard_fail_reason,
        }

    p4 = 90 if rr >= 3.0 else 80 if rr >= 2.5 else 70 if rr >= 2.0 else 50
    if rr < min_rr:
        p4 = 40
        caps.append(55)

    # ── P5 — Catalyst / Timing ────────────────────────────────────────────────
    p5 = 80
    if "HARD FAIL" in earnings:
        hard_fail = True
        hard_fail_reason = f"Earnings {earnings} → skip short too"
        return {
            "symbol": data.get("symbol", "?"), "direction": "short",
            "conviction_pct": 0, "hard_fail": True, "hard_fail_reason": hard_fail_reason,
            "heat": "Cold", "pillar_scores": {}, "ta_note": hard_fail_reason,
        }
    elif "Half size" in earnings:
        p5 = 50

    # ── Conviction synthesis ──────────────────────────────────────────────────
    pillar_scores = {"p1": p1, "p2": p2, "p3": p3, "p4": p4, "p5": p5}
    raw = round(p1 * 0.25 + p2 * 0.25 + p3 * 0.20 + p4 * 0.20 + p5 * 0.10)
    conviction = raw
    for cap in caps:
        conviction = min(conviction, cap)

    if conviction >= 75: heat = "TOP"
    elif conviction >= 60: heat = "Hot"
    elif conviction >= 45: heat = "Neutral"
    else: heat = "Cold"

    # Kelly sizing for short
    from core.kelly_sizer import kelly_size
    sizing = kelly_size(conviction, close, short_sl, direction="short")

    return {
        "symbol":        data.get("symbol", "?"),
        "name":          data.get("name", ""),
        "sector":        data.get("sector", ""),
        "direction":     "short",
        "last_close":    round(close, 2),
        "last_date":     data.get("last_date", ""),
        "conviction_pct": conviction,
        "heat":          heat,
        "tas":           data.get("tas", "0/4"),
        "tas_bear":      tas_bear,
        "trend":         "BEAR",
        "ma150_position": ma150_pos,
        "tf_breakdown":  data.get("tf_breakdown", {}),
        "rsi":           rsi,
        "vol_ratio":     vol_ratio,
        "vol_direction": vol_dir,
        "entry":         round(close, 2),
        "sl":            short_sl,
        "tp1":           short_tp1,
        "tp2":           short_tp2,
        "rr":            rr,
        "pillar_scores": pillar_scores,
        "hard_fail":     False,
        "ta_note":       " · ".join(ta_notes) if ta_notes else f"Short TAS {4-tas_bear}/4 bear.",
        "kelly_shares":  sizing["shares"],
        "kelly_risk_usd": sizing["risk_usd"],
        "kelly_label":   f"{sizing['risk_pct']}% risk",
        "earnings_warning": earnings,
    }


# ── Dual scanner ─────────────────────────────────────────────────────────────

def run_dual_scan(symbols: List[str] = None, watchlist_name: str = "full_scan") -> Dict[str, Any]:
    """
    Run LONG scan + SHORT scan simultaneously on the same data.
    No re-fetching — one data pull, two scoring passes.
    """
    from core.market_data import fetch_market_regime, fetch_multiple_tickers
    from core.conviction_engine import score_ticker
    from core.watchlists import get_watchlist
    from core.kelly_sizer import kelly_size
    from core.regime_engine import get_strategy_mode

    if symbols is None:
        wl = get_watchlist(watchlist_name)
        symbols = wl.get("tickers", []) if isinstance(wl, dict) else list(wl)

    regime  = fetch_market_regime()
    mode    = get_strategy_mode(regime)
    raw_data = fetch_multiple_tickers(symbols)

    longs  = []
    shorts = []

    for data in raw_data:
        # ── LONG scoring — reuse existing engine ──────────────────────────
        if mode["long_enabled"]:
            scored_long = score_ticker(data, regime, skip_calibration=True)
            if not scored_long.get("hard_fail") and scored_long.get("conviction_pct", 0) >= mode["conviction_min"]:
                sizing = kelly_size(scored_long["conviction_pct"],
                                    scored_long["last_close"],
                                    scored_long["sl"],
                                    direction="long")
                scored_long["direction"] = "long"
                scored_long["kelly_shares"]   = sizing["shares"]
                scored_long["kelly_risk_usd"] = sizing["risk_usd"]
                scored_long["kelly_label"]    = f"{sizing['risk_pct']}% risk"
                longs.append(scored_long)

        # ── SHORT scoring — new engine ────────────────────────────────────
        if mode["short_enabled"]:
            scored_short = score_short(data, regime)
            if not scored_short.get("hard_fail") and scored_short.get("conviction_pct", 0) >= mode["conviction_min"]:
                shorts.append(scored_short)

    longs.sort(key=lambda x: x["conviction_pct"], reverse=True)
    shorts.sort(key=lambda x: x["conviction_pct"], reverse=True)

    spy_chg = regime.get("spy_change_pct", 0)
    header = (f"SPY {'+' if spy_chg>=0 else ''}{spy_chg}% · "
              f"VIX {regime['vix']} · {regime['regime']} · "
              f"Mode: {mode['label']} · "
              f"Long candidates: {len(longs)} · Short candidates: {len(shorts)}")

    return {
        "market_header": header,
        "regime":        regime,
        "mode":          mode,
        "longs":         longs[:10],
        "shorts":        shorts[:10],
        "long_count":    len(longs),
        "short_count":   len(shorts),
    }
