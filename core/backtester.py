"""
backtester.py — Walk-Forward Backtesting Engine for SwingTrader v4.4
Runs the conviction scoring logic against historical data to measure real accuracy.
Answers: "When we scored 85%, did price actually hit TP1?"

Usage:
  from core.backtester import run_backtest
  results = run_backtest(["AAPL","NVDA","MSFT"], lookback_days=120, forward_days=15)
"""
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Any, List
from datetime import datetime, timedelta
import json, os
from pathlib import Path

RESULTS_DIR = Path(__file__).parent.parent / "backtest_results"
RESULTS_DIR.mkdir(exist_ok=True)

def _compute_indicators(daily: pd.DataFrame, idx: int) -> Dict[str, Any]:
    """Compute all indicators at a specific bar index (simulating that day's close)."""
    if idx < 160:  # need 150+ bars for MA150
        return None

    window = daily.iloc[:idx+1]
    last = window.iloc[-1]
    close = float(last["Close"])

    # EMAs — EMA9/21 dual confirmation (matches live engine)
    ema9  = window["Close"].ewm(span=9).mean()
    ema21 = window["Close"].ewm(span=21).mean()
    ema20 = window["Close"].ewm(span=20).mean()  # kept for vol_direction
    ma150 = window["Close"].ewm(span=150).mean()

    # Trend — EMA9/21 dual confirm
    ema9_val  = float(ema9.iloc[-1])
    ema21_val = float(ema21.iloc[-1])
    tf_daily = "BULL" if close > ema9_val and ema9_val > ema21_val else "BEAR"

    # Weekly approximation from daily (resample) — EMA9/21
    weekly = window["Close"].resample("W").last().dropna()
    if len(weekly) >= 21:
        w_ema9  = weekly.ewm(span=9).mean()
        w_ema21 = weekly.ewm(span=21).mean()
        w_close = float(weekly.iloc[-1])
        tf_weekly = "BULL" if w_close > float(w_ema9.iloc[-1]) and float(w_ema9.iloc[-1]) > float(w_ema21.iloc[-1]) else "BEAR"
    else:
        tf_weekly = "MIXED"

    # 4H/1H proxy — EMA9/21 on 5-bar and 9-bar daily windows
    ema5 = window["Close"].ewm(span=5).mean()
    ema8 = window["Close"].ewm(span=8).mean()
    ema9_5bar  = window["Close"].ewm(span=9).mean()   # same as ema9
    ema21_5bar = window["Close"].ewm(span=21).mean()  # same as ema21
    # Use shorter spans as proxies for intraday TFs
    tf_65m  = "BULL" if close > float(ema5.iloc[-1]) and float(ema5.iloc[-1]) > float(ema8.iloc[-1]) else "BEAR"
    tf_240m = "BULL" if close > float(ema8.iloc[-1]) and float(ema8.iloc[-1]) > float(ema9.iloc[-1]) else "BEAR"

    bull_count = sum(1 for t in [tf_65m, tf_240m, tf_daily, tf_weekly] if t == "BULL")
    tas = f"{bull_count}/4"

    # 150MA
    ma150_val = float(ma150.iloc[-1])
    ma150_pos = "above" if close > ma150_val else "below"

    # Volume
    vol_avg20 = window["Volume"].rolling(20).mean().iloc[-1]
    vol_ratio = round(float(last["Volume"]) / vol_avg20, 2) if vol_avg20 > 0 else 1.0

    bull_body = close > float(last["Open"])
    body = abs(close - float(last["Open"]))
    crange = float(last["High"]) - float(last["Low"])
    body_pct = body / crange if crange > 0 else 0
    upwick = float(last["High"]) - max(close, float(last["Open"]))
    long_upper_wick = upwick > crange * 0.5 if crange > 0 else False
    is_doji = body_pct < 0.1

    if vol_ratio >= 1.5 and bull_body and close > float(ema9.iloc[-1]):
        vol_dir = "ACCUMULATION"
    elif vol_ratio >= 1.5 and (not bull_body or is_doji or long_upper_wick):
        vol_dir = "DISTRIBUTION"
    else:
        vol_dir = "NEUTRAL"

    # Ichimoku
    tenkan = (window["High"].rolling(9).max() + window["Low"].rolling(9).min()) / 2
    kijun = (window["High"].rolling(26).max() + window["Low"].rolling(26).min()) / 2
    spanA = ((tenkan + kijun) / 2).shift(26)
    spanB = ((window["High"].rolling(52).max() + window["Low"].rolling(52).min()) / 2).shift(26)
    cloud_top = max(float(spanA.iloc[-1]) if not pd.isna(spanA.iloc[-1]) else 0,
                    float(spanB.iloc[-1]) if not pd.isna(spanB.iloc[-1]) else 0)
    cloud_bot = min(float(spanA.iloc[-1]) if not pd.isna(spanA.iloc[-1]) else 0,
                    float(spanB.iloc[-1]) if not pd.isna(spanB.iloc[-1]) else 0)
    cloud_pos = "above" if close > cloud_top else "below" if close < cloud_bot else "inside"

    # Fibonacci 55-bar
    tail55 = window.tail(55)
    fib_hi = float(tail55["High"].max())
    fib_lo = float(tail55["Low"].min())
    fib_rng = fib_hi - fib_lo
    fib_618 = round(fib_hi - fib_rng * 0.618, 2)

    # 35-bar for TP
    tail35 = window.tail(35)
    fib35_hi = float(tail35["High"].max())
    fib35_lo = float(tail35["Low"].min())
    fib35_rng = fib35_hi - fib35_lo
    fib35_382 = round(fib35_hi - fib35_rng * 0.382, 2)
    fib55_236 = round(fib_hi - fib_rng * 0.236, 2)

    # Coiling
    avg_rng10 = window["High"].tail(10).sub(window["Low"].tail(10)).mean()
    last3 = [float(window["High"].iloc[-i] - window["Low"].iloc[-i]) for i in range(1, 4)]
    coiling = all(r < float(avg_rng10) * 0.5 for r in last3)

    # ATR / SL / TP
    h, l, c = window["High"], window["Low"], window["Close"].shift(1)
    tr = pd.concat([h-l, (h-c).abs(), (l-c).abs()], axis=1).max(axis=1)
    atr_val = float(tr.rolling(14).mean().iloc[-1])
    swing_lo = float(window["Low"].tail(20).min())
    sl_cands = [close - atr_val * 1.5, swing_lo]
    if fib_618 < close:
        sl_cands.append(fib_618)
    sl = round(max(c for c in sl_cands if c < close) if any(c < close for c in sl_cands) else close * 0.95, 2)
    tp1 = round(fib35_382 if fib35_382 > close else close + (close - sl) * 2, 2)
    tp2 = round(fib55_236 if fib55_236 > close else close + (close - sl) * 3, 2)
    sl_dist = max(close - sl, 0.01)
    rr = round((tp1 - close) / sl_dist, 2) if sl_dist > 0 else 0

    # Sustained 65m proxy (consecutive days above EMA5)
    bull_candles = 0
    for k in range(1, min(6, len(window))):
        if float(window["Close"].iloc[-k]) > float(ema5.iloc[-k]):
            bull_candles += 1
        else:
            break
    sustained = bull_candles >= 3

    # FVG scan
    fvg_zones = []
    lookback = min(50, len(window) - 2)
    for k in range(2, lookback):
        c1_hi = float(window["High"].iloc[-k-2])
        c3_lo = float(window["Low"].iloc[-k])
        if c3_lo > c1_hi:
            fvg_zones.append({"type": "bullish", "top": c3_lo, "bottom": c1_hi})
    in_fvg = any(f["bottom"] <= close <= f["top"] for f in fvg_zones[:10])

    # LR channel
    lr_period = min(100, len(window) - 1)
    lr_close = window["Close"].tail(lr_period).values
    x = np.arange(lr_period)
    slope, intercept = np.polyfit(x, lr_close, 1)
    fitted = slope * x + intercept
    residuals = lr_close - fitted
    std_dev = np.std(residuals)
    lr_lower = fitted[-1] - 2 * std_dev
    lr_slope_pct = round(slope / max(float(lr_close[0]), 0.01) * 100, 4)
    at_lower_channel = close <= lr_lower * 1.005

    # POC
    price_min = float(window["Low"].tail(50).min())
    price_max = float(window["High"].tail(50).max())
    bins = np.linspace(price_min, price_max, 30)
    vol_hist = np.zeros(len(bins) - 1)
    for k in range(min(50, len(window))):
        bar_close = float(window["Close"].iloc[-k-1])
        bar_vol = float(window["Volume"].iloc[-k-1])
        bin_idx = np.digitize(bar_close, bins) - 1
        bin_idx = max(0, min(len(vol_hist)-1, bin_idx))
        vol_hist[bin_idx] += bar_vol
    poc_idx = np.argmax(vol_hist)
    poc = round((bins[poc_idx] + bins[poc_idx+1]) / 2, 2)
    near_poc = abs(close - poc) / close < 0.005

    date_str = window.index[-1].strftime("%Y-%m-%d")

    return {
        "symbol": "", "name": "", "sector": "",
        "last_close": round(close, 2), "last_date": date_str,
        "ma150_position": ma150_pos, "ma150_value": round(ma150_val, 2),
        "tas": tas, "tf_breakdown": {"tf_65m": tf_65m, "tf_240m": tf_240m, "tf_daily": tf_daily, "tf_weekly": tf_weekly},
        "vol_ratio": vol_ratio, "vol_direction": vol_dir,
        "coiling": coiling, "cloud_position": cloud_pos,
        "rsi": 50, "atr": round(atr_val, 2),
        "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": round(tp2 * 1.05, 2),
        "rr": rr, "qty": 0, "fib_levels": {},
        "confluence_zones": [], "earnings_warning": "Clear",
        "body_pct": round(body_pct, 3), "is_doji": is_doji,
        "long_upper_wick": long_upper_wick, "bull_body": bull_body,
        "entry_low": round(close * 0.99, 2), "entry_high": round(close * 1.005, 2),
        "sustained_65m": {"sustained": sustained, "bull_candles": bull_candles},
        "lr_channel": {"at_lower": at_lower_channel, "lower_2sd": round(lr_lower, 2), "slope_pct": lr_slope_pct},
        "fvg_zones": fvg_zones[:5], "in_fvg": in_fvg,
        "vol_profile": {"poc": poc}, "near_poc": near_poc,
        "mkt_cap_b": 0,
        "double_bottom": {"confirmed": False},   # skip costly pattern scan in backtest
        "coil_data": {"coil3": False, "coil5": False},
        "expanded_confluence": [], "near_confluence": False,
    }


def _check_outcome(daily: pd.DataFrame, entry_idx: int, sl: float, tp1: float, tp2: float, forward_days: int = 15) -> Dict[str, Any]:
    """Look forward from entry to see if TP1, TP2, or SL was hit first."""
    entry_price = float(daily["Close"].iloc[entry_idx])
    max_idx = min(entry_idx + forward_days, len(daily) - 1)

    hit_tp1 = False
    hit_tp2 = False
    hit_sl = False
    max_price = entry_price
    min_price = entry_price
    exit_day = 0
    exit_price = entry_price

    for i in range(entry_idx + 1, max_idx + 1):
        hi = float(daily["High"].iloc[i])
        lo = float(daily["Low"].iloc[i])
        cl = float(daily["Close"].iloc[i])
        max_price = max(max_price, hi)
        min_price = min(min_price, lo)
        days_held = i - entry_idx

        if lo <= sl and not hit_sl:
            hit_sl = True
            exit_day = days_held
            exit_price = sl
            break
        if hi >= tp1 and not hit_tp1:
            hit_tp1 = True
            if hi >= tp2:
                hit_tp2 = True
                exit_day = days_held
                exit_price = tp2
                break
            exit_day = days_held
            exit_price = tp1
        if hit_tp1 and hi >= tp2:
            hit_tp2 = True
            exit_day = days_held
            exit_price = tp2
            break

    if not hit_tp1 and not hit_sl:
        exit_price = float(daily["Close"].iloc[max_idx])
        exit_day = forward_days

    pnl_pct = round((exit_price - entry_price) / entry_price * 100, 2)
    max_drawdown = round((min_price - entry_price) / entry_price * 100, 2)
    max_gain = round((max_price - entry_price) / entry_price * 100, 2)

    outcome = "TP2_HIT" if hit_tp2 else "TP1_HIT" if hit_tp1 else "SL_HIT" if hit_sl else "TIMEOUT"
    win = hit_tp1 or (pnl_pct > 0)

    return {
        "outcome": outcome, "win": win, "pnl_pct": pnl_pct,
        "exit_day": exit_day, "exit_price": round(exit_price, 2),
        "max_gain": max_gain, "max_drawdown": max_drawdown,
        "hit_tp1": hit_tp1, "hit_tp2": hit_tp2, "hit_sl": hit_sl,
    }


def run_backtest(symbols: List[str], lookback_days: int = 120, forward_days: int = 15,
                 sample_every: int = 5) -> Dict[str, Any]:
    """
    Walk-forward backtest: score each ticker every N days, check outcomes.
    
    Args:
        symbols: List of tickers to test
        lookback_days: How many days back to start (from today)
        forward_days: How many days forward to check TP1/SL
        sample_every: Score every N days (5 = weekly sampling)
    
    Returns:
        Full backtest report with accuracy by conviction bracket.
    """
    from core.conviction_engine import score_ticker
    from core.market_data import fetch_market_regime

    regime = fetch_market_regime()
    all_signals = []
    errors = []
    buy_hold_returns = {}

    for sym in symbols:
        print(f"[BACKTEST] Processing {sym}...")
        try:
            tk = yf.Ticker(sym)
            daily = tk.history(period="2y", interval="1d")
            if daily.empty or len(daily) < 200:
                errors.append(f"{sym}: insufficient data ({len(daily)} bars)")
                continue

            total_bars = len(daily)
            start_idx = max(160, total_bars - lookback_days - forward_days)
            end_idx = total_bars - forward_days  # leave room for forward check

            # ── Buy & Hold benchmark for this ticker ──
            bh_start_price = float(daily["Close"].iloc[start_idx])
            bh_end_price   = float(daily["Close"].iloc[end_idx - 1])
            bh_return = round((bh_end_price - bh_start_price) / bh_start_price * 100, 2)
            buy_hold_returns[sym] = {
                "return_pct": bh_return,
                "start_price": round(bh_start_price, 2),
                "end_price": round(bh_end_price, 2),
                "start_date": daily.index[start_idx].strftime("%Y-%m-%d"),
                "end_date": daily.index[end_idx - 1].strftime("%Y-%m-%d"),
            }

            signals_for_sym = 0
            for idx in range(start_idx, end_idx, sample_every):
                data = _compute_indicators(daily, idx)
                if data is None:
                    continue

                data["symbol"] = sym
                scored = score_ticker(data, regime, skip_calibration=True)

                if scored.get("hard_fail"):
                    continue  # skip hard fails for accuracy measurement

                conv = scored.get("conviction_pct", 0)
                if conv < 40:
                    continue  # skip very low conviction

                sl = scored.get("sl", 0)
                tp1 = scored.get("tp1", 0)
                tp2 = scored.get("tp2", 0)
                outcome = _check_outcome(daily, idx, sl, tp1, tp2, forward_days)

                signal = {
                    "symbol": sym,
                    "date": daily.index[idx].strftime("%Y-%m-%d"),
                    "entry_price": scored["last_close"],
                    "conviction": conv,
                    "heat": scored["heat"],
                    "tas": scored["tas"],
                    "trend": scored["trend"],
                    "sl": sl, "tp1": tp1, "tp2": tp2, "rr": scored.get("rr", 0),
                    **outcome,
                }
                all_signals.append(signal)
                signals_for_sym += 1

            print(f"  [BACKTEST] {sym}: {signals_for_sym} signals generated")
        except Exception as e:
            errors.append(f"{sym}: {str(e)}")
            print(f"  [BACKTEST] {sym} ERROR: {e}")

    if not all_signals:
        return {"error": "No signals generated", "errors": errors}

    # ── Profit Density per signal (P&L% / days held, annualized) ──
    for s in all_signals:
        days = max(s.get("exit_day", 1), 1)
        s["profit_density"] = round(s["pnl_pct"] / days * 252, 2)  # annualized

    # ── Flag EMA-aligned signals ──
    for s in all_signals:
        s["ema_aligned"] = s.get("trend", "") == "BULL"

    # ── Rotation Strategy Benchmark ──
    # Simulates rotating capital between top signals (exit → immediately redeploy)
    from datetime import datetime as _dt, timedelta as _td
    rotation_capital = 100.0
    rotation_trades  = 0
    last_exit_date   = ""
    sorted_by_date   = sorted(all_signals, key=lambda x: x["date"])
    for s in sorted_by_date:
        if s["date"] >= last_exit_date and s["conviction"] >= 65:
            rotation_capital *= (1 + s["pnl_pct"] / 100)
            rotation_trades  += 1
            try:
                exit_dt = _dt.strptime(s["date"], "%Y-%m-%d") + _td(days=int(s.get("exit_day", forward_days) * 1.4))
                last_exit_date = exit_dt.strftime("%Y-%m-%d")
            except Exception:
                pass
    rotation_return  = round(rotation_capital - 100, 2)
    rotation_density = round(rotation_return / max(lookback_days, 1) * 252, 2)

    # Aggregate by conviction bracket
    brackets = [
        {"label": "85-100%", "min": 85, "max": 100},
        {"label": "75-84%", "min": 75, "max": 84},
        {"label": "65-74%", "min": 65, "max": 74},
        {"label": "60-64%", "min": 60, "max": 64},
        {"label": "50-59%", "min": 50, "max": 59},
        {"label": "40-49%", "min": 40, "max": 49},
    ]

    bracket_stats = []
    for b in brackets:
        in_bracket = [s for s in all_signals if b["min"] <= s["conviction"] <= b["max"]]
        if not in_bracket:
            bracket_stats.append({**b, "count": 0, "wins": 0, "win_rate": 0,
                                  "tp1_rate": 0, "tp2_rate": 0, "avg_pnl": 0,
                                  "avg_days": 0, "avg_drawdown": 0})
            continue

        wins = [s for s in in_bracket if s["win"]]
        tp1s = [s for s in in_bracket if s["hit_tp1"]]
        tp2s = [s for s in in_bracket if s["hit_tp2"]]
        pnls = [s["pnl_pct"] for s in in_bracket]
        days = [s["exit_day"] for s in in_bracket]
        dds  = [s["max_drawdown"] for s in in_bracket]
        densities = [s["profit_density"] for s in in_bracket]

        bracket_stats.append({
            **b, "count": len(in_bracket),
            "wins": len(wins),
            "win_rate":    round(len(wins) / len(in_bracket) * 100, 1),
            "tp1_rate":    round(len(tp1s) / len(in_bracket) * 100, 1),
            "tp2_rate":    round(len(tp2s) / len(in_bracket) * 100, 1),
            "avg_pnl":     round(sum(pnls) / len(pnls), 2),
            "avg_days":    round(sum(days) / len(days), 1),
            "avg_drawdown":round(sum(dds) / len(dds), 2),
            "profit_density": round(sum(densities) / len(densities), 2),
        })

    # Overall stats
    total = len(all_signals)
    total_wins = sum(1 for s in all_signals if s["win"])
    total_pnl = [s["pnl_pct"] for s in all_signals]
    total_tp1 = sum(1 for s in all_signals if s["hit_tp1"])

    # Find best and worst
    best = max(all_signals, key=lambda x: x["pnl_pct"])
    worst = min(all_signals, key=lambda x: x["pnl_pct"])

    # Profit Factor = gross wins / abs(gross losses)
    gross_wins   = sum(s["pnl_pct"] for s in all_signals if s["pnl_pct"] > 0)
    gross_losses = sum(abs(s["pnl_pct"]) for s in all_signals if s["pnl_pct"] < 0)
    profit_factor = round(gross_wins / gross_losses, 2) if gross_losses > 0 else 999

    win_pnls  = [s["pnl_pct"] for s in all_signals if s["pnl_pct"] > 0]
    loss_pnls = [abs(s["pnl_pct"]) for s in all_signals if s["pnl_pct"] < 0]
    avg_win  = round(sum(win_pnls) / len(win_pnls), 2) if win_pnls else 0
    avg_loss = round(sum(loss_pnls) / len(loss_pnls), 2) if loss_pnls else 0

    # Benchmark: avg buy-and-hold return across all tested tickers
    bh_returns = [v["return_pct"] for v in buy_hold_returns.values()]
    avg_bh_return = round(sum(bh_returns) / len(bh_returns), 2) if bh_returns else 0

    # Overall profit density
    all_densities = [s["profit_density"] for s in all_signals]
    avg_density = round(sum(all_densities) / len(all_densities), 2) if all_densities else 0
    ema_aligned_signals = [s for s in all_signals if s.get("ema_aligned")]
    ema_aligned_win_rate = round(sum(1 for s in ema_aligned_signals if s["win"]) / max(len(ema_aligned_signals), 1) * 100, 1)

    # Per-ticker stats: strategy avg pnl vs buy&hold
    per_ticker = []
    for sym in symbols:
        sym_signals = [s for s in all_signals if s["symbol"] == sym]
        if not sym_signals:
            continue
        sym_pnls = [s["pnl_pct"] for s in sym_signals]
        sym_tp1  = sum(1 for s in sym_signals if s["hit_tp1"])
        sym_dens = [s["profit_density"] for s in sym_signals]
        bh = buy_hold_returns.get(sym, {})
        per_ticker.append({
            "symbol":          sym,
            "signals":         len(sym_signals),
            "win_rate":        round(sum(1 for s in sym_signals if s["win"]) / len(sym_signals) * 100, 1),
            "tp1_rate":        round(sym_tp1 / len(sym_signals) * 100, 1),
            "avg_pnl":         round(sum(sym_pnls) / len(sym_pnls), 2),
            "avg_days":        round(sum(s["exit_day"] for s in sym_signals) / len(sym_signals), 1),
            "profit_density":  round(sum(sym_dens) / len(sym_dens), 2),
            "buy_hold_return": bh.get("return_pct", 0),
            "alpha":           round(sum(sym_pnls) / len(sym_pnls) - bh.get("return_pct", 0) / max(lookback_days / forward_days, 1), 2),
        })
    per_ticker.sort(key=lambda x: x["avg_pnl"], reverse=True)

    # Accuracy gap analysis
    accuracy_gap = []
    for bs in bracket_stats:
        if bs["count"] > 0:
            expected = (bs["min"] + bs["max"]) / 2
            actual = bs["tp1_rate"]
            gap = round(actual - expected, 1)
            accuracy_gap.append({
                "bracket": bs["label"], "expected": expected,
                "actual_tp1_rate": actual, "gap": gap,
                "verdict": "CALIBRATED" if abs(gap) < 10 else "OVER-CONFIDENT" if gap < -10 else "UNDER-RATED",
            })

    report = {
        "summary": {
            "total_signals":        total,
            "total_wins":           total_wins,
            "overall_win_rate":     round(total_wins / total * 100, 1) if total else 0,
            "overall_tp1_rate":     round(total_tp1 / total * 100, 1) if total else 0,
            "avg_pnl":              round(sum(total_pnl) / len(total_pnl), 2) if total_pnl else 0,
            "profit_factor":        profit_factor,
            "avg_win":              avg_win,
            "avg_loss":             avg_loss,
            "win_loss_ratio":       round(avg_win / avg_loss, 2) if avg_loss > 0 else 999,
            "avg_buy_hold_return":  avg_bh_return,
            # NEW: Profit Density & Rotation
            "avg_profit_density":   avg_density,
            "ema_aligned_win_rate": ema_aligned_win_rate,
            "ema_aligned_count":    len(ema_aligned_signals),
            "rotation_return":      rotation_return,
            "rotation_density":     rotation_density,
            "rotation_trades":      rotation_trades,
            "best_trade":  {"symbol": best["symbol"],  "date": best["date"],  "pnl": best["pnl_pct"]},
            "worst_trade": {"symbol": worst["symbol"], "date": worst["date"], "pnl": worst["pnl_pct"]},
            "symbols_tested": symbols,
            "lookback_days": lookback_days,
            "forward_days": forward_days,
        },
        "brackets": bracket_stats,
        "accuracy_gap": accuracy_gap,
        "per_ticker": per_ticker,
        "buy_hold_returns": buy_hold_returns,
        "signals": all_signals,
        "errors": errors,
    }

    # Save to file
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outfile = RESULTS_DIR / f"backtest_{ts}.json"
    outfile.write_text(json.dumps(report, indent=2, default=str))
    print(f"[BACKTEST] Results saved to {outfile}")

    return report
