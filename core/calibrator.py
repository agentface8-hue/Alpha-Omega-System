"""
calibrator.py — Auto-calibration loop for SwingTrader v4.4
Runs backtests iteratively, adjusts scoring until conviction % matches TP1 hit rate.

Process:
1. Run backtest → get accuracy by bracket
2. Compute calibration curve (raw score → real accuracy)
3. Generate adjusted parameters
4. Re-run and verify
"""
import json, os
import numpy as np
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

CALIB_DIR = Path(__file__).parent.parent / "calibration"
CALIB_DIR.mkdir(exist_ok=True)
CALIB_FILE = CALIB_DIR / "calibration_params.json"

# ── Supabase persistence helpers ──────────────────────────────────────────────

def _sb_client():
    """Return a Supabase client or None if credentials are missing."""
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


def _load_from_supabase() -> Dict[str, Any] | None:
    """Load calibration params from Supabase. Returns None on any failure."""
    try:
        sb = _sb_client()
        if not sb:
            return None
        resp = sb.table("calibration_params").select("params").eq("key", "default").limit(1).execute()
        rows = resp.data
        if rows:
            p = rows[0].get("params", {})
            if isinstance(p, dict):
                return p
        return None
    except Exception as e:
        print(f"[CALIB] Supabase load failed (will use local file): {e}")
        return None


def _save_to_supabase(params: Dict[str, Any]) -> bool:
    """Upsert calibration params to Supabase. Returns True on success."""
    try:
        sb = _sb_client()
        if not sb:
            return False
        sb.table("calibration_params").upsert(
            {"key": "default", "params": params, "updated_at": datetime.utcnow().isoformat()},
            on_conflict="key"
        ).execute()
        return True
    except Exception as e:
        print(f"[CALIB] Supabase save failed (will use local file): {e}")
        return False


def load_calibration() -> Dict[str, Any]:
    """Load saved calibration parameters.
    Priority: Supabase → local JSON file → hardcoded defaults.
    On Render (ephemeral fs) Supabase is the durable source.
    """
    # 1. Try Supabase first
    params = _load_from_supabase()
    if params:
        # Keep local file in sync for local dev / offline fallback
        try:
            CALIB_FILE.write_text(json.dumps(params, indent=2))
        except Exception:
            pass
        return params

    # 2. Fall back to local JSON
    if CALIB_FILE.exists():
        try:
            return json.loads(CALIB_FILE.read_text())
        except Exception:
            pass

    # 3. Hardcoded defaults
    return {"mode": "none", "scale": 1.0, "offset": 0}


def save_calibration(params: Dict[str, Any]):
    """Persist calibration params.
    Writes to BOTH Supabase and local file (dual-write for resilience).
    """
    params["updated_at"] = datetime.now().isoformat()

    # Always write local file (fast, zero-dep)
    try:
        CALIB_FILE.write_text(json.dumps(params, indent=2))
        print(f"[CALIB] Saved to {CALIB_FILE}")
    except Exception as e:
        print(f"[CALIB] Local file save failed: {e}")

    # Best-effort Supabase write
    ok = _save_to_supabase(params)
    if ok:
        print("[CALIB] Synced to Supabase calibration_params table")


# Defaults when learning loop has no regime sample yet
DEFAULT_REGIME_THRESHOLDS = {
    "Trending Bull": 78,
    "Choppy / Range": 65,
    "High-Vol Event": 70,
    "Trending Bear": 75,
}


def _conviction_bracket(conviction: int) -> str:
    if conviction >= 85:
        return "85-100"
    if conviction >= 75:
        return "75-84"
    if conviction >= 65:
        return "65-74"
    if conviction >= 60:
        return "60-64"
    return "50-59"


def apply_learning_offsets(raw_conviction: int, params: Dict[str, Any]) -> int:
    """Apply per-bracket offsets from learning_loop (closed-trade win rates)."""
    offsets = params.get("conviction_offsets") or {}
    if not offsets:
        return raw_conviction
    offset = float(offsets.get(_conviction_bracket(raw_conviction), 0))
    return max(0, min(100, round(raw_conviction + offset)))


def get_regime_conviction_threshold(regime: str) -> int:
    """Regime floor: max(hardcoded safe default, learned threshold)."""
    params = load_calibration()
    learned = params.get("regime_thresholds") or {}
    base = int(DEFAULT_REGIME_THRESHOLDS.get(regime, 70))
    if regime in learned and learned[regime] is not None:
        return max(base, int(learned[regime]))
    return base


def regime_conviction_penalty(regime: str) -> int:
    """Extra conviction required in historically weak regimes."""
    stats = (load_calibration().get("regime_stats") or {}).get(regime or "", {})
    wr = stats.get("win_rate")
    if regime == "Trending Bull":
        return 5
    if wr is not None and wr < 40:
        return 4
    if wr is not None and wr < 50:
        return 2
    return 0


def sector_conviction_penalty(sector: str) -> int:
    """Extra conviction % required for COLD sectors; small relief for HOT."""
    bias = (load_calibration().get("sector_bias") or {}).get(sector or "Unknown", "NEUTRAL")
    if bias == "COLD":
        return 5
    if bias == "HOT":
        return -2
    return 0


def apply_calibration(raw_conviction: int, params: Dict = None) -> int:
    """Apply learning offsets + optional linear/curve calibration."""
    if params is None:
        params = load_calibration()
    conviction = apply_learning_offsets(raw_conviction, params)
    mode = params.get("mode", "none")
    if mode == "linear":
        conviction = conviction * params["scale"] + params["offset"]
        return max(0, min(100, round(conviction)))
    if mode == "curve":
        mapping = params.get("mapping", [])
        if mapping:
            for m in mapping:
                if m["raw_min"] <= conviction <= m["raw_max"]:
                    return max(0, min(100, round(m["calibrated"])))
    return conviction


def run_calibration(symbols: List[str] = None,
                    lookback_days: int = 180,
                    forward_days: int = 15,
                    sample_every: int = 5,
                    iterations: int = 3) -> Dict[str, Any]:
    """
    Full auto-calibration loop:
    1. Run backtest with current scoring
    2. Measure accuracy gap per bracket
    3. Compute calibration curve
    4. Verify with adjusted scores
    """
    from core.backtester import run_backtest

    if symbols is None:
        symbols = ["AAPL","NVDA","MSFT","GOOGL","META",
                    "AMZN","TSLA","AMD","CRM","NFLX"]

    print(f"\n{'='*60}")
    print(f"AUTO-CALIBRATION: {len(symbols)} stocks, {lookback_days}d lookback")
    print(f"{'='*60}")

    # Step 1: Run backtest
    print("\n[STEP 1] Running baseline backtest...")
    bt = run_backtest(symbols, lookback_days, forward_days, sample_every)
    if "error" in bt:
        return {"error": bt["error"]}

    signals = bt.get("signals", [])
    if len(signals) < 20:
        return {"error": f"Only {len(signals)} signals — need 20+ for calibration"}

    # Step 2: Compute raw → actual mapping
    print("\n[STEP 2] Computing calibration curve...")
    brackets = bt.get("brackets", [])
    raw_points = []
    actual_points = []
    for b in brackets:
        if b["count"] >= 3:
            mid = (b["min"] + b["max"]) / 2
            raw_points.append(mid)
            actual_points.append(b["tp1_rate"])

    if len(raw_points) < 2:
        return {"error": "Not enough brackets with data for calibration"}

    raw_arr = np.array(raw_points)
    actual_arr = np.array(actual_points)

    # Method 1: Linear fit to WIN RATE (more useful than TP1 rate)
    win_points = []
    for b in brackets:
        if b["count"] >= 3:
            win_points.append(b["win_rate"])
    win_arr = np.array(win_points) if win_points else actual_arr

    # Fit to win rate
    if len(raw_arr) >= 2 and len(win_arr) == len(raw_arr):
        coeffs = np.polyfit(raw_arr, win_arr, 1)
        scale = round(float(coeffs[0]), 4)
        offset = round(float(coeffs[1]), 2)
    else:
        scale = 0.5
        offset = 0

    print(f"  Linear fit (win rate): calibrated = {scale} * raw + {offset}")
    print(f"  Example: raw 70% → calibrated {round(70*scale+offset)}%")
    print(f"  Example: raw 80% → calibrated {round(80*scale+offset)}%")

    # Method 2: Compute optimal TP1 distance for 85% hit rate
    print("\n[STEP 2b] Computing optimal TP distances...")
    tp_analysis = _compute_optimal_tp(signals)

    # Piecewise mapping per bracket (using win rate)
    mapping = []
    for i, b in enumerate(brackets):
        if b["count"] >= 3:
            mapping.append({
                "raw_min": b["min"], "raw_max": b["max"],
                "raw_mid": (b["min"] + b["max"]) / 2,
                "calibrated": round(win_points[i] if i < len(win_points) else b["win_rate"]),
                "tp1_rate": b["tp1_rate"],
                "win_rate": b["win_rate"],
                "count": b["count"],
            })

    # Step 3: Pillar analysis — which pillars predict wins?
    print("\n[STEP 3] Analyzing pillar predictiveness...")
    pillar_analysis = _analyze_pillars(signals)

    # Step 4: Generate tightened thresholds
    print("\n[STEP 4] Generating tightened thresholds...")
    thresholds = _compute_thresholds(signals, brackets)

    # Save calibration
    params = {
        "mode": "linear",
        "scale": scale,
        "offset": offset,
        "mapping": mapping,
        "pillar_analysis": pillar_analysis,
        "thresholds": thresholds,
        "tp_analysis": tp_analysis,
        "baseline_stats": bt["summary"],
        "brackets": brackets,
        "total_signals": len(signals),
    }
    save_calibration(params)

    # Step 5: Show what calibrated scores would look like
    print("\n[STEP 5] Calibrated score preview...")
    print(f"  {'Raw':>6} → {'Calibrated':>10} | {'Meaning'}")
    print(f"  {'-'*40}")
    for raw in [90, 85, 80, 75, 70, 65, 60, 55, 50, 45]:
        cal = max(0, min(100, round(raw * scale + offset)))
        label = "TOP" if cal >= 75 else "Hot" if cal >= 60 else "Neutral" if cal >= 45 else "Cold"
        print(f"  {raw:5}% → {cal:9}% | {label}")

    return {
        "calibration": params,
        "preview": {raw: max(0, min(100, round(raw * scale + offset))) for raw in range(40, 101, 5)},
        "recommendation": _generate_recommendations(brackets, pillar_analysis, thresholds, tp_analysis),
    }


def _compute_optimal_tp(signals: List[Dict]) -> Dict[str, Any]:
    """Find what TP1 distance achieves 85% hit rate."""
    gains = [s["max_gain"] for s in signals if s.get("max_gain", 0) > 0]
    if not gains:
        return {"error": "No positive trades"}

    # Test different TP levels (as % from entry)
    tp_levels = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 7.0, 10.0]
    tp_results = []
    for tp_pct in tp_levels:
        hits = sum(1 for g in gains if g >= tp_pct)
        rate = round(hits / len(signals) * 100, 1)
        tp_results.append({"tp_pct": tp_pct, "hit_rate": rate, "hits": hits})

    # Find level closest to 85%
    best_for_85 = None
    for tr in tp_results:
        if tr["hit_rate"] >= 80:  # relaxed to 80
            best_for_85 = tr

    # Find level closest to 70%
    best_for_70 = None
    for tr in tp_results:
        if tr["hit_rate"] >= 65:
            best_for_70 = tr

    print(f"  TP distance analysis ({len(signals)} signals, {len(gains)} with positive gain):")
    for tr in tp_results:
        marker = " <<<" if tr == best_for_85 else ""
        print(f"    TP +{tr['tp_pct']}% → hit rate {tr['hit_rate']}% ({tr['hits']} hits){marker}")

    return {
        "tp_results": tp_results,
        "best_for_85pct": best_for_85,
        "best_for_70pct": best_for_70,
        "total_signals": len(signals),
        "positive_signals": len(gains),
    }


def _analyze_pillars(signals: List[Dict]) -> Dict[str, Any]:
    """Analyze which factors actually predict wins vs losses."""
    wins = [s for s in signals if s.get("win")]
    losses = [s for s in signals if not s.get("win")]
    if not wins or not losses:
        return {"error": "Need both wins and losses"}

    # TAS comparison
    win_tas = np.mean([int(s["tas"].split("/")[0]) for s in wins if "/" in str(s.get("tas",""))])
    loss_tas = np.mean([int(s["tas"].split("/")[0]) for s in losses if "/" in str(s.get("tas",""))])

    # R:R comparison
    win_rr = np.mean([s.get("rr", 0) for s in wins])
    loss_rr = np.mean([s.get("rr", 0) for s in losses])

    # Conviction comparison
    win_conv = np.mean([s.get("conviction", 0) for s in wins])
    loss_conv = np.mean([s.get("conviction", 0) for s in losses])

    # Trend comparison
    win_bull = sum(1 for s in wins if s.get("trend") == "BULL") / len(wins) * 100
    loss_bull = sum(1 for s in losses if s.get("trend") == "BULL") / len(losses) * 100

    analysis = {
        "win_count": len(wins), "loss_count": len(losses),
        "avg_tas": {"wins": round(win_tas, 2), "losses": round(loss_tas, 2),
                    "delta": round(win_tas - loss_tas, 2)},
        "avg_rr": {"wins": round(win_rr, 2), "losses": round(loss_rr, 2),
                   "delta": round(win_rr - loss_rr, 2)},
        "avg_conviction": {"wins": round(win_conv, 1), "losses": round(loss_conv, 1),
                          "delta": round(win_conv - loss_conv, 1)},
        "bull_trend_pct": {"wins": round(win_bull, 1), "losses": round(loss_bull, 1)},
    }

    # Find strongest predictor
    predictors = []
    if analysis["avg_tas"]["delta"] > 0.3:
        predictors.append(f"TAS (wins avg {win_tas:.1f} vs losses {loss_tas:.1f})")
    if analysis["avg_rr"]["delta"] > 0.3:
        predictors.append(f"R:R (wins avg {win_rr:.1f} vs losses {loss_rr:.1f})")
    if win_bull - loss_bull > 10:
        predictors.append(f"BULL trend (wins {win_bull:.0f}% vs losses {loss_bull:.0f}%)")
    analysis["strongest_predictors"] = predictors

    for p in predictors:
        print(f"  Strong predictor: {p}")

    return analysis


def _compute_thresholds(signals: List[Dict], brackets: List[Dict]) -> Dict[str, Any]:
    """Compute tightened thresholds to close the accuracy gap."""
    wins = [s for s in signals if s.get("win")]
    losses = [s for s in signals if not s.get("win")]

    # Find minimum criteria that give 85% accuracy
    # Sort signals by conviction descending, find cutoff where win rate hits 85%
    sorted_sigs = sorted(signals, key=lambda x: x.get("conviction", 0), reverse=True)

    best_cutoff = 100
    best_rate = 0
    for cutoff in range(95, 39, -5):
        above = [s for s in sorted_sigs if s.get("conviction", 0) >= cutoff]
        if len(above) >= 5:
            rate = sum(1 for s in above if s.get("win")) / len(above) * 100
            if rate >= 80 and len(above) >= 5:  # relaxed to 80% with 5+ signals
                best_cutoff = cutoff
                best_rate = rate
                break

    # Calculate win rates at different TAS levels
    tas_rates = {}
    for tas_val in range(0, 5):
        tas_sigs = [s for s in signals if int(s.get("tas", "0/4").split("/")[0]) == tas_val]
        if len(tas_sigs) >= 3:
            rate = sum(1 for s in tas_sigs if s.get("win")) / len(tas_sigs) * 100
            tas_rates[f"TAS_{tas_val}"] = {"count": len(tas_sigs), "win_rate": round(rate, 1)}

    # R:R threshold
    rr_groups = {"under_2": [], "2_to_3": [], "over_3": []}
    for s in signals:
        rr = s.get("rr", 0)
        if rr < 2: rr_groups["under_2"].append(s)
        elif rr < 3: rr_groups["2_to_3"].append(s)
        else: rr_groups["over_3"].append(s)
    rr_rates = {}
    for k, v in rr_groups.items():
        if v:
            rr_rates[k] = {"count": len(v), "win_rate": round(sum(1 for s in v if s["win"]) / len(v) * 100, 1)}

    return {
        "min_conviction_for_85pct": best_cutoff,
        "win_rate_at_cutoff": round(best_rate, 1),
        "tas_win_rates": tas_rates,
        "rr_win_rates": rr_rates,
        "suggested_filters": _suggest_filters(tas_rates, rr_rates, best_cutoff),
    }


def _suggest_filters(tas_rates, rr_rates, best_cutoff):
    """Generate specific filter suggestions based on data."""
    filters = []

    # TAS filter
    best_tas = None
    best_tas_rate = 0
    for k, v in tas_rates.items():
        if v["win_rate"] > best_tas_rate and v["count"] >= 5:
            best_tas = k
            best_tas_rate = v["win_rate"]
    if best_tas:
        tas_num = best_tas.split("_")[1]
        filters.append(f"Require TAS >= {tas_num}/4 (win rate {best_tas_rate}%)")

    # R:R filter
    if rr_rates.get("over_3", {}).get("win_rate", 0) > rr_rates.get("under_2", {}).get("win_rate", 0) + 10:
        filters.append(f"Prefer R:R >= 3:1 (win rate {rr_rates['over_3']['win_rate']}% vs {rr_rates.get('under_2',{}).get('win_rate',0)}%)")

    # Conviction filter
    if best_cutoff < 100:
        filters.append(f"Only act on conviction >= {best_cutoff}% (achieves ~80%+ win rate)")

    return filters


def _generate_recommendations(brackets, pillar_analysis, thresholds, tp_analysis=None):
    """Generate human-readable recommendations."""
    recs = []

    # Check overall calibration
    overconfident = [b for b in brackets if b.get("count", 0) > 0
                     and b.get("tp1_rate", 0) < (b["min"] + b["max"]) / 2 - 15]
    if overconfident:
        recs.append("SCORING IS OVER-CONFIDENT: Conviction scores are higher than actual accuracy. "
                     "Apply calibration curve to scale scores down.")

    # TP target recommendation
    if tp_analysis and tp_analysis.get("best_for_85pct"):
        tp = tp_analysis["best_for_85pct"]
        recs.append(f"FOR 80%+ TP HIT RATE: Set TP1 at +{tp['tp_pct']}% from entry "
                     f"(backtested hit rate: {tp['hit_rate']}%)")
    elif tp_analysis and tp_analysis.get("best_for_70pct"):
        tp = tp_analysis["best_for_70pct"]
        recs.append(f"FOR 65%+ TP HIT RATE: Set TP1 at +{tp['tp_pct']}% from entry "
                     f"(backtested hit rate: {tp['hit_rate']}%)")
    else:
        recs.append("Current TP1 targets are too aggressive. Consider tighter targets.")

    # Threshold recommendation
    cutoff = thresholds.get("min_conviction_for_85pct", 100)
    rate = thresholds.get("win_rate_at_cutoff", 0)
    if cutoff < 100:
        recs.append(f"FOR 80%+ ACCURACY: Only trade signals with conviction >= {cutoff}% "
                     f"(backtested win rate: {rate}%)")
    else:
        recs.append("No conviction level achieved 80%+ accuracy. "
                     "Tighten pillar scoring or add more confluence requirements.")

    # Pillar recommendations
    predictors = pillar_analysis.get("strongest_predictors", [])
    if predictors:
        recs.append(f"STRONGEST PREDICTORS: {', '.join(predictors)}. "
                     "Consider increasing weight of these factors.")

    # Filter suggestions
    for f in thresholds.get("suggested_filters", []):
        recs.append(f"FILTER: {f}")

    return recs
