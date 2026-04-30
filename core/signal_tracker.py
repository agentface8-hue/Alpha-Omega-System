"""
signal_tracker.py — Live signal tracking for paper validation v2.0
COMPLETE REWRITE: Full audit trail, indicator snapshots, gap detection,
realistic fills, MAE/MFE, market context, staleness checks, case reports.
Zero-mistake paper trading system.
"""
import os, json, datetime, uuid, math
from pathlib import Path
from typing import Dict, Any, List, Optional
import yfinance as yf
import numpy as np
import pandas as pd
from core import signal_store as store

SIGNALS_DIR = Path(__file__).parent.parent / "signals"
SIGNALS_DIR.mkdir(exist_ok=True)
SIGNALS_FILE = SIGNALS_DIR / "active_signals.json"
CLOSED_FILE = SIGNALS_DIR / "closed_signals.json"
REPORTS_DIR = SIGNALS_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def _load(path: Path) -> List[Dict]:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return []
    return []

def _save(path: Path, data: List[Dict]):
    path.write_text(json.dumps(data, indent=2, default=str))


def _is_us_market_open() -> Dict[str, Any]:
    """Check if US stock market is currently in regular trading hours."""
    import pytz
    now_utc = datetime.datetime.now(pytz.UTC)
    eastern = pytz.timezone("US/Eastern")
    now_et = now_utc.astimezone(eastern)
    weekday = now_et.weekday()  # 0=Mon, 6=Sun
    hour = now_et.hour
    minute = now_et.minute
    time_decimal = hour + minute / 60.0

    is_weekday = weekday < 5
    is_regular_hours = 9.5 <= time_decimal < 16.0  # 9:30 AM - 4:00 PM ET
    is_premarket = 4.0 <= time_decimal < 9.5
    is_afterhours = 16.0 <= time_decimal < 20.0

    return {
        "market_open": is_weekday and is_regular_hours,
        "premarket": is_weekday and is_premarket,
        "afterhours": is_weekday and is_afterhours,
        "weekend": not is_weekday,
        "et_time": now_et.strftime("%H:%M ET"),
        "session": "regular" if (is_weekday and is_regular_hours) else
                   "premarket" if (is_weekday and is_premarket) else
                   "afterhours" if (is_weekday and is_afterhours) else "closed"
    }


def _fetch_market_context() -> Dict[str, Any]:
    """Fetch current VIX, SPY, regime — saved with every signal."""
    try:
        vix_tk = yf.Ticker("^VIX")
        vix_data = vix_tk.history(period="5d")
        vix = float(vix_data["Close"].iloc[-1]) if not vix_data.empty else 0

        spy_tk = yf.Ticker("SPY")
        spy_data = spy_tk.history(period="5d")
        spy_close = float(spy_data["Close"].iloc[-1]) if not spy_data.empty else 0
        spy_prev = float(spy_data["Close"].iloc[-2]) if len(spy_data) >= 2 else spy_close
        spy_chg = round((spy_close - spy_prev) / spy_prev * 100, 2) if spy_prev else 0

        if vix > 30: regime = "High-Vol Event"
        elif vix > 25: regime = "Trending Bear"
        elif vix > 20: regime = "Choppy / Range"
        else: regime = "Trending Bull"

        return {
            "vix": round(vix, 1),
            "spy_close": round(spy_close, 2),
            "spy_change_pct": spy_chg,
            "regime": regime,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {"vix": 0, "spy_close": 0, "spy_change_pct": 0, "regime": "unknown", "error": str(e)}


def _fetch_indicator_snapshot(symbol: str, asset_type: str = "stock") -> Dict[str, Any]:
    """Capture FULL indicator state for a ticker — the complete technical picture."""
    lookup = f"{symbol}-USD" if asset_type == "crypto" and not symbol.endswith("-USD") else symbol
    try:
        tk = yf.Ticker(lookup)
        daily = tk.history(period="1y", interval="1d")
        if daily.empty:
            return {"error": f"No data for {lookup}"}

        hourly = tk.history(period="60d", interval="1h")
        close = float(daily["Close"].iloc[-1])
        last = daily.iloc[-1]

        # EMAs
        ema10 = float(daily["Close"].ewm(span=10).mean().iloc[-1])
        ema20 = float(daily["Close"].ewm(span=20).mean().iloc[-1])
        ema50 = float(daily["Close"].ewm(span=50).mean().iloc[-1])
        ma150 = float(daily["Close"].ewm(span=150).mean().iloc[-1]) if len(daily) >= 150 else 0
        ma200 = float(daily["Close"].ewm(span=200).mean().iloc[-1]) if len(daily) >= 200 else 0

        # ATR
        h, l, c_prev = daily["High"], daily["Low"], daily["Close"].shift(1)
        tr = pd.concat([h-l, (h-c_prev).abs(), (l-c_prev).abs()], axis=1).max(axis=1)
        atr14 = float(tr.rolling(14).mean().iloc[-1]) if len(daily) >= 14 else 0

        # RSI
        delta = daily["Close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        rsi_series = 100 - (100 / (1 + rs))
        rsi = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else 50

        # Volume
        vol_avg20 = float(daily["Volume"].rolling(20).mean().iloc[-1])
        vol_ratio = round(float(last["Volume"]) / vol_avg20, 2) if vol_avg20 > 0 else 1.0

        # Candle analysis
        body = abs(close - float(last["Open"]))
        crange = float(last["High"]) - float(last["Low"])
        body_pct = body / crange if crange > 0 else 0
        bull_body = close > float(last["Open"])

        # Volume direction
        if vol_ratio >= 1.5 and bull_body and close > ema20:
            vol_dir = "ACCUMULATION"
        elif vol_ratio >= 1.5 and (not bull_body or body_pct < 0.1):
            vol_dir = "DISTRIBUTION"
        else:
            vol_dir = "NEUTRAL"

        # MTF Trends
        tf_daily = "BULL" if close > ema20 else "BEAR"
        tf_weekly = "MIXED"
        weekly = tk.history(period="2y", interval="1wk")
        if not weekly.empty and len(weekly) >= 20:
            w_ema20 = float(weekly["Close"].ewm(span=20).mean().iloc[-1])
            tf_weekly = "BULL" if float(weekly["Close"].iloc[-1]) > w_ema20 else "BEAR"

        tf_65m, tf_240m = "MIXED", "MIXED"
        if not hourly.empty and len(hourly) >= 20:
            h_ema20 = hourly["Close"].ewm(span=20).mean()
            tf_65m = "BULL" if float(hourly["Close"].iloc[-1]) > float(h_ema20.iloc[-1]) else "BEAR"
            h4 = hourly["Close"].resample("4h").last().dropna()
            if len(h4) >= 20:
                h4_ema20 = h4.ewm(span=20).mean()
                tf_240m = "BULL" if float(h4.iloc[-1]) > float(h4_ema20.iloc[-1]) else "BEAR"

        bull_count = sum(1 for t in [tf_65m, tf_240m, tf_daily, tf_weekly] if t == "BULL")

        # Ichimoku Cloud
        tenkan = (daily["High"].rolling(9).max() + daily["Low"].rolling(9).min()) / 2
        kijun = (daily["High"].rolling(26).max() + daily["Low"].rolling(26).min()) / 2
        spanA = ((tenkan + kijun) / 2).shift(26)
        spanB = ((daily["High"].rolling(52).max() + daily["Low"].rolling(52).min()) / 2).shift(26)
        sA = float(spanA.iloc[-1]) if not pd.isna(spanA.iloc[-1]) else 0
        sB = float(spanB.iloc[-1]) if not pd.isna(spanB.iloc[-1]) else 0
        cloud_top = max(sA, sB)
        cloud_bot = min(sA, sB)
        cloud_pos = "above" if close > cloud_top else "below" if close < cloud_bot else "inside"

        # Fibonacci levels
        fib_hi = float(daily["High"].tail(55).max())
        fib_lo = float(daily["Low"].tail(55).min())
        fib_rng = fib_hi - fib_lo
        fib_levels = {
            "0": round(fib_hi, 2), "0.236": round(fib_hi - fib_rng * 0.236, 2),
            "0.382": round(fib_hi - fib_rng * 0.382, 2), "0.5": round(fib_hi - fib_rng * 0.5, 2),
            "0.618": round(fib_hi - fib_rng * 0.618, 2), "1.0": round(fib_lo, 2),
        }

        # Linear Regression Channel
        lr_lower, lr_upper, lr_mid = 0, 0, 0
        try:
            closes_arr = daily["Close"].tail(100).values
            if len(closes_arr) >= 100:
                x = np.arange(len(closes_arr))
                slope, intercept = np.polyfit(x, closes_arr, 1)
                fitted = slope * x + intercept
                std = np.std(closes_arr - fitted)
                lr_mid = round(float(fitted[-1]), 2)
                lr_lower = round(lr_mid - 2 * std, 2)
                lr_upper = round(lr_mid + 2 * std, 2)
        except Exception:
            pass

        # Volume Profile POC
        poc = 0
        try:
            data50 = daily.tail(50)
            if len(data50) >= 10:
                lows_arr = data50["Low"].values
                highs_arr = data50["High"].values
                vols_arr = data50["Volume"].values
                bins = np.linspace(float(np.min(lows_arr)), float(np.max(highs_arr)), 51)
                vol_at = np.zeros(50)
                for i in range(len(data50)):
                    lo_v, hi_v, vol_v = float(lows_arr[i]), float(highs_arr[i]), float(vols_arr[i])
                    for b in range(50):
                        if bins[b+1] >= lo_v and bins[b] <= hi_v:
                            overlap = min(hi_v, float(bins[b+1])) - max(lo_v, float(bins[b]))
                            total_r = hi_v - lo_v if hi_v > lo_v else 1
                            vol_at[b] += vol_v * (overlap / total_r)
                poc_idx = np.argmax(vol_at)
                poc = round((float(bins[poc_idx]) + float(bins[poc_idx+1])) / 2, 2)
        except Exception:
            pass

        # 20-day swing low for SL reference
        swing_lo_20 = float(daily["Low"].tail(20).min())

        return {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "price": round(close, 4),
            "open": round(float(last["Open"]), 4),
            "high": round(float(last["High"]), 4),
            "low": round(float(last["Low"]), 4),
            "volume": int(last["Volume"]),
            # Moving Averages
            "ema10": round(ema10, 4),
            "ema20": round(ema20, 4),
            "ema50": round(ema50, 4),
            "ma150": round(ma150, 4),
            "ma200": round(ma200, 4),
            # Momentum
            "rsi14": round(rsi, 1),
            "atr14": round(atr14, 4),
            # Volume
            "vol_ratio": vol_ratio,
            "vol_avg20": round(vol_avg20, 0),
            "vol_direction": vol_dir,
            # Candle
            "body_pct": round(body_pct, 3),
            "bull_body": bull_body,
            # MTF Trends
            "tf_65m": tf_65m, "tf_240m": tf_240m,
            "tf_daily": tf_daily, "tf_weekly": tf_weekly,
            "tas": f"{bull_count}/4",
            # Cloud
            "cloud_position": cloud_pos,
            "cloud_top": round(cloud_top, 2),
            "cloud_bottom": round(cloud_bot, 2),
            # Structure
            "fib_levels": fib_levels,
            "lr_channel": {"lower": lr_lower, "mid": lr_mid, "upper": lr_upper},
            "poc": poc,
            "swing_lo_20": round(swing_lo_20, 2),
            # Distances from key levels (as %)
            "dist_ema20_pct": round((close - ema20) / ema20 * 100, 2) if ema20 else 0,
            "dist_ma150_pct": round((close - ma150) / ma150 * 100, 2) if ma150 else 0,
            "dist_poc_pct": round((close - poc) / poc * 100, 2) if poc else 0,
        }
    except Exception as e:
        return {"error": str(e), "timestamp": datetime.datetime.utcnow().isoformat()}


def _fetch_live_price(symbol: str, asset_type: str = "stock") -> Dict[str, Any]:
    """Fetch live price with staleness detection and validation."""
    lookup = f"{symbol}-USD" if asset_type == "crypto" and not symbol.endswith("-USD") else symbol
    try:
        tk = yf.Ticker(lookup)
        fi = tk.fast_info
        price = fi.get("lastPrice") or fi.get("last_price") or fi.get("previousClose", 0)
        prev_close = fi.get("previousClose", 0)

        if not price or price <= 0:
            return {"price": 0, "valid": False, "reason": "no_price"}

        price = float(price)
        prev_close = float(prev_close) if prev_close else price

        # Staleness check: if price == previousClose exactly AND market is open,
        # yfinance might be returning stale data
        market = _is_us_market_open()
        is_stale = False
        if asset_type == "stock" and market["market_open"] and price == prev_close:
            is_stale = True  # Likely stale — market is open but price hasn't changed

        # Gap detection: difference between prev close and current
        gap_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0

        return {
            "price": round(price, 4),
            "prev_close": round(prev_close, 4),
            "gap_pct": gap_pct,
            "is_stale": is_stale,
            "valid": True,
            "session": market["session"],
            "source": "yfinance_fast_info",
            "delay_warning": "15-20min delayed" if asset_type == "stock" else "near-realtime"
        }
    except Exception as e:
        return {"price": 0, "valid": False, "reason": str(e)}


def _detect_gap_fill(signal: Dict, current_price: float, prev_close: float) -> Dict[str, Any]:
    """
    GAP DETECTION: If price gaps through SL/TP overnight, use realistic fill price.
    In real trading, a stop at $130 with a gap-down open at $125 fills at $125, not $130.
    """
    entry = signal["entry_price"]
    sl = signal["sl"]
    tp1 = signal["tp1"]
    tp3 = signal["tp3"]
    is_turbo = signal.get("turbo", False)

    result = {"gap_detected": False, "fill_price": current_price, "gap_type": None, "slippage_pct": 0}

    # Gap DOWN through SL
    if prev_close > sl and current_price <= sl:
        # Price gapped through our stop — fill at current (open), not SL level
        actual_fill = current_price  # In reality this would be the open price
        intended_fill = sl
        slippage = round((intended_fill - actual_fill) / intended_fill * 100, 2)
        result = {
            "gap_detected": True, "fill_price": actual_fill,
            "gap_type": "gap_through_sl", "intended_sl": intended_fill,
            "slippage_pct": slippage,
            "note": f"SL was ${intended_fill} but price gapped to ${actual_fill} (slippage {slippage}%)"
        }

    # Gap UP through TP
    tp_target = tp1 if is_turbo else tp3
    if prev_close < tp_target and current_price >= tp_target:
        actual_fill = current_price
        result = {
            "gap_detected": True, "fill_price": actual_fill,
            "gap_type": "gap_through_tp",
            "note": f"TP gapped — filled at ${actual_fill} instead of ${tp_target}"
        }

    return result


# ══════════════════════════════════════════════════════════════
# SIGNAL CREATION
# ══════════════════════════════════════════════════════════════

def record_signal(scan_result: Dict[str, Any], asset_type: str = "stock") -> List[Dict]:
    """Auto-record signals for tickers scoring >= 60% conviction. Full audit trail."""
    active = store.load_active()
    active_tickers = {s["ticker"] for s in active}
    new_signals = []

    # Capture market context ONCE for all signals in this batch
    market_ctx = _fetch_market_context()

    for r in scan_result.get("results", []):
        if r.get("hard_fail") or r.get("conviction_pct", 0) < 60:
            continue
        ticker = r["ticker"]
        if ticker in active_tickers:
            continue

        signal = {
            "id": str(uuid.uuid4())[:8],
            "ticker": ticker,
            "asset_type": asset_type,
            "entry_price": r["last_close"],
            "entry_time": datetime.datetime.utcnow().isoformat(),
            "conviction": r["conviction_pct"],
            "heat": r["heat"],
            "sl": r["sl"], "tp1": r["tp1"], "tp2": r["tp2"], "tp3": r["tp3"],
            "rr": r["rr"], "qty": r["qty"],
            "regime": scan_result.get("market_regime", ""),
            "tas": r["tas"], "trend": r["trend"],
            "pillar_scores": r.get("pillar_scores", {}),
            "ta_note": r.get("ta_note", ""),
            # ── NEW: Full entry context ──
            "entry_market_context": market_ctx,
            "entry_snapshot": {
                "rsi": r.get("rsi", 0),
                "atr": r.get("atr", 0) if "atr" in r else 0,
                "vol_ratio": r.get("vol_ratio", 0),
                "vol_direction": r.get("vol_direction", ""),
                "cloud_position": r.get("cloud_position", ""),
                "ma150_position": r.get("ma150_position", ""),
                "coiling": r.get("coiling", False),
                "fib_levels": r.get("fib_levels", {}),
                "tf_breakdown": r.get("tf_breakdown", {}),
                "confluence_zones": r.get("confluence_zones", []),
                "fvg_zones": r.get("fvg_zones", []),
                "lr_channel": r.get("lr_channel", {}),
                "sector": r.get("sector", ""),
                "body_pct": r.get("body_pct", 0),
                "near_confluence": r.get("near_confluence", False),
            },
            "entry_session": _is_us_market_open()["session"],
            # ── Tracking state ──
            "status": "OPEN", "current_price": r["last_close"],
            "pnl_pct": 0, "highest_price": r["last_close"], "lowest_price": r["last_close"],
            "mae_pct": 0, "mfe_pct": 0,
            "tp1_hit": False, "tp2_hit": False, "tp3_hit": False,
            "closed_at": None, "close_reason": None, "bars_held": 0,
            # ── Close data (filled on close) ──
            "close_price": None, "close_snapshot": None,
            "close_market_context": None, "close_session": None,
            "gap_info": None, "slippage_pct": 0,
            "turbo": False,
        }
        active.append(signal)
        active_tickers.add(ticker)
        new_signals.append(signal)

    store.save_active(active)
    return new_signals


def create_turbo_signal(symbol: str, asset_type: str = "stock",
                        scan_data: Dict = None) -> Dict:
    """
    Create turbo scalp signal with ATR-BASED targets (not fixed %).
    Backtester proved TP1 at +0.5% ATR = 87.5% hit rate.
    If scan_data provided, saves full conviction + indicators.
    """
    sym = symbol.upper()
    lookup = f"{sym}-USD" if asset_type == "crypto" and not sym.endswith("-USD") else sym

    # Fetch live price with validation
    price_data = _fetch_live_price(sym, asset_type)
    if not price_data["valid"]:
        return {"error": f"Could not fetch price for {lookup}: {price_data.get('reason','')}"}

    price = price_data["price"]
    if price <= 0:
        return {"error": f"Invalid price ${price} for {lookup}"}

    # ── ATR-based targets (not hardcoded %) ──
    atr_val = 0
    try:
        tk = yf.Ticker(lookup)
        daily = tk.history(period="30d", interval="1d")
        if not daily.empty and len(daily) >= 14:
            h, l, c_prev = daily["High"], daily["Low"], daily["Close"].shift(1)
            tr = pd.concat([h-l, (h-c_prev).abs(), (l-c_prev).abs()], axis=1).max(axis=1)
            atr_val = float(tr.rolling(14).mean().iloc[-1])
    except Exception:
        pass

    # Fallback to percentage-based if ATR fetch fails
    if atr_val > 0:
        sl = round(price - atr_val * 0.5, 4)       # SL at 0.5x ATR
        tp1 = round(price + atr_val * 0.5, 4)      # TP1 at 0.5x ATR (87.5% hit rate)
        tp2 = round(price + atr_val * 1.0, 4)      # TP2 at 1x ATR
        tp3 = round(price + atr_val * 1.5, 4)      # TP3 at 1.5x ATR
        rr = round((tp1 - price) / (price - sl), 2) if price > sl else 1.0
        target_method = "atr"
    else:
        sl = round(price * 0.998, 4)
        tp1 = round(price * 1.005, 4)
        tp2 = round(price * 1.008, 4)
        tp3 = round(price * 1.012, 4)
        rr = 2.5
        target_method = "pct_fallback"

    # Extract conviction data from scan if provided (FIXES Gap 2)
    conviction = 0
    pillar_scores = {}
    heat = "TURBO"
    tas = "—"
    trend = "TURBO"
    ta_note = ""
    entry_snapshot_data = {}

    if scan_data:
        conviction = scan_data.get("conviction_pct", 0)
        pillar_scores = scan_data.get("pillar_scores", {})
        heat = scan_data.get("heat", "TURBO")
        tas = scan_data.get("tas", "—")
        trend = scan_data.get("trend", "TURBO")
        ta_note = scan_data.get("ta_note", "")
        entry_snapshot_data = {
            "rsi": scan_data.get("rsi", 0),
            "vol_ratio": scan_data.get("vol_ratio", 0),
            "vol_direction": scan_data.get("vol_direction", ""),
            "cloud_position": scan_data.get("cloud_position", ""),
            "ma150_position": scan_data.get("ma150_position", ""),
            "coiling": scan_data.get("coiling", False),
            "tf_breakdown": scan_data.get("tf_breakdown", {}),
            "fib_levels": scan_data.get("fib_levels", {}),
            "fvg_zones": scan_data.get("fvg_zones", []),
            "sector": scan_data.get("sector", ""),
            "near_confluence": scan_data.get("near_confluence", False),
        }

    # Capture market context
    market_ctx = _fetch_market_context()
    market_status = _is_us_market_open()

    signal = {
        "id": str(uuid.uuid4())[:8],
        "ticker": sym,
        "asset_type": asset_type,
        "entry_price": round(price, 4),
        "entry_time": datetime.datetime.utcnow().isoformat(),
        "conviction": conviction,
        "heat": heat,
        "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3,
        "rr": rr, "qty": 0,
        "regime": market_ctx.get("regime", "turbo_scalp"),
        "tas": tas, "trend": trend,
        "pillar_scores": pillar_scores,
        "ta_note": ta_note,
        # ── Full entry audit trail ──
        "entry_market_context": market_ctx,
        "entry_snapshot": entry_snapshot_data if entry_snapshot_data else {
            "atr14": round(atr_val, 4), "price_data": price_data
        },
        "entry_session": market_status["session"],
        "target_method": target_method,
        "atr_at_entry": round(atr_val, 4),
        # ── Price staleness flag ──
        "price_stale_at_entry": price_data.get("is_stale", False),
        "price_delay_warning": price_data.get("delay_warning", ""),
        # ── Tracking state ──
        "status": "OPEN", "current_price": round(price, 4),
        "pnl_pct": 0, "highest_price": round(price, 4), "lowest_price": round(price, 4),
        "mae_pct": 0, "mfe_pct": 0,
        "tp1_hit": False, "tp2_hit": False, "tp3_hit": False,
        "closed_at": None, "close_reason": None, "bars_held": 0,
        # ── Close data (filled on close) ──
        "close_price": None, "close_snapshot": None,
        "close_market_context": None, "close_session": None,
        "gap_info": None, "slippage_pct": 0,
        "turbo": True,
    }

    active = store.load_active()
    active.append(signal)
    store.save_active(active)

    # ── Earnings proximity check ──
    try:
        import yfinance as yf
        from datetime import date
        cal = yf.Ticker(sym).calendar
        if cal is not None and not cal.empty:
            col = cal.columns[0]
            dt = col.date() if hasattr(col, 'date') else date.fromisoformat(str(col)[:10])
            days = (dt - date.today()).days
            if 0 <= days <= 7:
                signal["earnings_warning"] = f"⚠ EARNINGS IN {days} DAY{'S' if days!=1 else ''} — targets unreliable"
                signal["earnings_date"] = str(dt)
                store.save_active(active)
                # Telegram earnings warning
                from core.telegram_alerts import _send
                _send(f"⚠ <b>EARNINGS WARNING — {sym}</b>\nEarnings in <b>{days} day{'s' if days!=1 else ''}</b> ({dt})\nSignal created but targets may be unreliable.")
    except Exception:
        pass

    # ── Telegram alert ──
    try:
        from core.telegram_alerts import alert_signal_created
        alert_signal_created(signal)
    except Exception:
        pass

    return signal


# ══════════════════════════════════════════════════════════════
# SIGNAL MONITORING — THE CORE LOOP
# ══════════════════════════════════════════════════════════════

def check_signals() -> Dict[str, Any]:
    """
    Check all active signals against current prices.
    v2.0: Gap detection, realistic fills, MAE/MFE, close snapshots,
    market hours awareness, staleness checks.
    """
    active = store.load_active()
    closed = store.load_closed()
    if not active:
        return {"active": [], "closed": closed, "stats": _calc_stats(closed),
                "market_status": _is_us_market_open()}

    market_status = _is_us_market_open()

    # ── Batch fetch prices with validation ──
    prices = {}
    for s in active:
        sym = s["ticker"]
        lookup = f"{sym}-USD" if s["asset_type"] == "crypto" and not sym.endswith("-USD") else sym
        try:
            price_data = _fetch_live_price(sym, s["asset_type"])
            if price_data["valid"]:
                prices[sym] = price_data
                print(f"  [LIVE] {sym} = ${price_data['price']:.4f} "
                      f"(gap:{price_data['gap_pct']}% stale:{price_data['is_stale']} "
                      f"session:{price_data['session']})")
            else:
                print(f"  [SKIP] {sym} invalid: {price_data.get('reason','')}")
        except Exception as e:
            print(f"  [ERR] {sym}: {e}")

    newly_closed = []
    still_active = []
    warnings = []

    for s in active:
        sym = s["ticker"]
        pd_result = prices.get(sym, None)

        if not pd_result:
            still_active.append(s)
            continue

        price = pd_result["price"]
        prev_close = pd_result.get("prev_close", price)

        # ── Staleness warning ──
        if pd_result.get("is_stale"):
            warnings.append({"ticker": sym, "warning": "Price may be stale (equal to prev close during market hours)"})

        # ── Market hours awareness for stocks ──
        if s["asset_type"] == "stock" and not market_status["market_open"]:
            # Don't trigger SL/TP on stale after-hours prices for stocks
            s["current_price"] = round(price, 4)
            s["price_note"] = f"Market closed ({market_status['session']}). Price delayed."
            # Still update tracking but skip close decisions
            entry = s["entry_price"]
            s["pnl_pct"] = round((price - entry) / entry * 100, 2) if entry else 0
            try:
                entry_dt = datetime.datetime.fromisoformat(s["entry_time"])
                s["bars_held"] = (datetime.datetime.utcnow() - entry_dt).days
            except Exception:
                pass
            still_active.append(s)
            continue

        # ── Gap detection ──
        gap_info = _detect_gap_fill(s, price, prev_close)
        if gap_info["gap_detected"]:
            price = gap_info["fill_price"]  # Use realistic fill
            print(f"  [GAP] {sym}: {gap_info['note']}")

        s["current_price"] = round(price, 4)

        # ── Days held ──
        try:
            entry_dt = datetime.datetime.fromisoformat(s["entry_time"])
            s["bars_held"] = (datetime.datetime.utcnow() - entry_dt).days
        except Exception:
            pass

        # ── Track high/low watermarks ──
        if price > s["highest_price"]:
            s["highest_price"] = round(price, 4)
        if price < s["lowest_price"]:
            s["lowest_price"] = round(price, 4)

        # ── MAE / MFE (Max Adverse/Favorable Excursion) ──
        entry = s["entry_price"]
        if entry > 0:
            s["pnl_pct"] = round((price - entry) / entry * 100, 2)
            s["mae_pct"] = round((s["lowest_price"] - entry) / entry * 100, 2)  # negative = drawdown
            s["mfe_pct"] = round((s["highest_price"] - entry) / entry * 100, 2)  # positive = max gain

        # ── Check TP targets ──
        if price >= s["tp1"] and not s["tp1_hit"]:
            s["tp1_hit"] = True
            s["tp1_hit_time"] = datetime.datetime.utcnow().isoformat()
            try:
                from core.telegram_alerts import alert_tp_hit
                alert_tp_hit(s, "tp1", price)
            except Exception:
                pass
        if price >= s["tp2"] and not s["tp2_hit"]:
            s["tp2_hit"] = True
            s["tp2_hit_time"] = datetime.datetime.utcnow().isoformat()
            try:
                from core.telegram_alerts import alert_tp_hit
                alert_tp_hit(s, "tp2", price)
            except Exception:
                pass
        if price >= s["tp3"] and not s["tp3_hit"]:
            s["tp3_hit"] = True
            s["tp3_hit_time"] = datetime.datetime.utcnow().isoformat()
            try:
                from core.telegram_alerts import alert_tp_hit
                alert_tp_hit(s, "tp3", price)
            except Exception:
                pass

        # ── Close conditions ──
        is_turbo = s.get("turbo", False)
        should_close = False
        close_status = ""
        close_reason = ""

        if price <= s["sl"]:
            close_status = "STOPPED_OUT"
            actual_fill = gap_info["fill_price"] if gap_info["gap_detected"] else s["sl"]
            close_reason = f"SL hit at ${s['sl']}"
            if gap_info["gap_detected"]:
                close_reason += f" (gap fill at ${actual_fill}, slippage {gap_info.get('slippage_pct',0)}%)"
                s["slippage_pct"] = gap_info.get("slippage_pct", 0)
            s["close_price"] = round(actual_fill, 4)
            s["pnl_pct"] = round((actual_fill - entry) / entry * 100, 2)
            should_close = True
            try:
                from core.telegram_alerts import alert_sl_hit
                alert_sl_hit(s, actual_fill)
            except Exception:
                pass

        elif is_turbo and s["tp1_hit"]:
            close_status = "TP1_HIT"
            close_reason = f"Turbo TP1 hit at ${s['tp1']}"
            s["close_price"] = round(price, 4)
            should_close = True

        elif s["tp3_hit"]:
            close_status = "TP3_HIT"
            close_reason = f"TP3 hit at ${s['tp3']}"
            s["close_price"] = round(price, 4)
            should_close = True

        elif s["bars_held"] >= 30:
            close_status = "TIMEOUT"
            close_reason = f"30-day timeout at ${price}"
            s["close_price"] = round(price, 4)
            should_close = True

        if should_close:
            s["status"] = close_status
            s["close_reason"] = close_reason
            s["closed_at"] = datetime.datetime.utcnow().isoformat()
            s["close_session"] = market_status["session"]
            s["gap_info"] = gap_info if gap_info["gap_detected"] else None

            # ── Close-time market context ──
            try:
                s["close_market_context"] = _fetch_market_context()
            except Exception:
                s["close_market_context"] = {"error": "failed to fetch"}

            # ── Close-time indicator snapshot (lightweight — skip for bulk) ──
            # Full snapshot is expensive, so we do a light version
            s["close_snapshot"] = {
                "price": s["close_price"],
                "pnl_pct": s["pnl_pct"],
                "mae_pct": s["mae_pct"],
                "mfe_pct": s["mfe_pct"],
                "bars_held": s["bars_held"],
                "highest_price": s["highest_price"],
                "lowest_price": s["lowest_price"],
                "slippage_pct": s.get("slippage_pct", 0),
            }

            # ── Generate case report ──
            _save_case_report(s)

            # ── Trade log ──
            try:
                from core.trade_log import log_closed_signal
                log_closed_signal(s)
            except Exception as _tl_err:
                print(f"  [TradeLog] warning: {_tl_err}")

            newly_closed.append(s)
        else:
            still_active.append(s)

    # Save
    closed.extend(newly_closed)
    store.save_active(still_active)
    store.save_closed(closed)
    stats = _calc_stats(closed)

    return {
        "active": still_active,
        "recently_closed": newly_closed,
        "closed": closed,
        "stats": stats,
        "market_status": market_status,
        "warnings": warnings,
    }


# ══════════════════════════════════════════════════════════════
# CASE REPORT GENERATOR
# ══════════════════════════════════════════════════════════════

def _save_case_report(signal: Dict):
    """Save a detailed JSON case report for each closed signal."""
    try:
        report = {
            "report_version": "2.0",
            "generated_at": datetime.datetime.utcnow().isoformat(),
            # ── IDENTITY ──
            "signal_id": signal["id"],
            "ticker": signal["ticker"],
            "asset_type": signal["asset_type"],
            # ── ENTRY ──
            "entry": {
                "price": signal["entry_price"],
                "time": signal["entry_time"],
                "session": signal.get("entry_session", "unknown"),
                "conviction": signal["conviction"],
                "heat": signal["heat"],
                "pillar_scores": signal["pillar_scores"],
                "tas": signal["tas"],
                "trend": signal["trend"],
                "ta_note": signal.get("ta_note", ""),
                "regime": signal["regime"],
                "market_context": signal.get("entry_market_context", {}),
                "indicator_snapshot": signal.get("entry_snapshot", {}),
                "target_method": signal.get("target_method", "unknown"),
                "atr_at_entry": signal.get("atr_at_entry", 0),
                "price_stale_at_entry": signal.get("price_stale_at_entry", False),
            },
            # ── TARGETS ──
            "targets": {
                "sl": signal["sl"], "tp1": signal["tp1"],
                "tp2": signal["tp2"], "tp3": signal["tp3"],
                "rr": signal["rr"], "turbo": signal.get("turbo", False),
            },
            # ── EXIT ──
            "exit": {
                "price": signal.get("close_price"),
                "time": signal.get("closed_at"),
                "status": signal["status"],
                "reason": signal["close_reason"],
                "session": signal.get("close_session", "unknown"),
                "market_context": signal.get("close_market_context", {}),
                "snapshot": signal.get("close_snapshot", {}),
            },
            # ── PERFORMANCE ──
            "performance": {
                "pnl_pct": signal["pnl_pct"],
                "mae_pct": signal.get("mae_pct", 0),
                "mfe_pct": signal.get("mfe_pct", 0),
                "highest_price": signal["highest_price"],
                "lowest_price": signal["lowest_price"],
                "bars_held": signal["bars_held"],
                "tp1_hit": signal["tp1_hit"],
                "tp2_hit": signal["tp2_hit"],
                "tp3_hit": signal["tp3_hit"],
                "slippage_pct": signal.get("slippage_pct", 0),
                "gap_info": signal.get("gap_info"),
            },
            # ── ANALYSIS (auto-generated) ──
            "analysis": _generate_trade_analysis(signal),
        }

        filename = store.save_report(report)
        print(f"  [REPORT] Saved: {filename}")
    except Exception as e:
        print(f"  [REPORT] Error saving report for {signal.get('ticker','?')}: {e}")


def _generate_trade_analysis(signal: Dict) -> Dict[str, Any]:
    """Auto-generate trade analysis insights from the data."""
    analysis = {}
    entry = signal["entry_price"]
    mae = signal.get("mae_pct", 0)
    mfe = signal.get("mfe_pct", 0)
    pnl = signal["pnl_pct"]
    status = signal["status"]
    bars = signal["bars_held"]

    # Was SL too tight?
    if status == "STOPPED_OUT" and mfe > 0.5:
        analysis["sl_review"] = f"Trade went +{mfe}% before reversing to SL. MFE suggests SL may be too tight."
    elif status == "STOPPED_OUT" and mfe <= 0:
        analysis["sl_review"] = "Trade never went positive — entry timing was poor or direction was wrong."

    # Was TP too ambitious?
    if status == "TIMEOUT" and mfe > 0:
        analysis["tp_review"] = f"Trade hit +{mfe}% but didn't reach TP. Consider tighter targets."
    if signal["tp1_hit"] and not signal["tp3_hit"] and status == "STOPPED_OUT":
        analysis["tp_review"] = "TP1 was hit but trade reversed to SL. Consider taking profit at TP1."

    # MAE analysis — how far did winning trades drawdown?
    if pnl > 0 and mae < -0.5:
        analysis["mae_insight"] = f"Winner but saw {mae}% drawdown. Risk management held."
    if pnl < 0 and mae < -2:
        analysis["mae_insight"] = f"Severe drawdown of {mae}%. SL may need adjustment."

    # Speed analysis
    if bars <= 1 and abs(pnl) > 1:
        analysis["speed"] = "Fast move — signal resolved within 1 day."
    elif bars > 14 and abs(pnl) < 1:
        analysis["speed"] = "Slow grind — low P&L after 2+ weeks. Consider time-based exit rules."

    # Conviction accuracy check
    conv = signal.get("conviction", 0)
    if conv >= 70 and pnl < 0:
        analysis["conviction_accuracy"] = f"HIGH conviction ({conv}%) but LOSS. Investigate pillar scores."
    elif conv < 50 and pnl > 2:
        analysis["conviction_accuracy"] = f"LOW conviction ({conv}%) but BIG WIN (+{pnl}%). Scoring may underweight something."

    # Gap impact
    if signal.get("gap_info"):
        slip = signal.get("slippage_pct", 0)
        analysis["gap_impact"] = f"Gap detected. Slippage: {slip}%. Real fills would differ from target."

    # Entry session
    if signal.get("entry_session") == "premarket":
        analysis["session_note"] = "Entered during pre-market. Prices may have been less reliable."
    elif signal.get("entry_session") == "closed":
        analysis["session_note"] = "Entered while market was closed. Entry price was previous close."

    # Regime comparison
    entry_regime = signal.get("entry_market_context", {}).get("regime", "")
    close_regime = signal.get("close_market_context", {}).get("regime", "")
    if entry_regime and close_regime and entry_regime != close_regime:
        analysis["regime_shift"] = f"Regime changed from '{entry_regime}' to '{close_regime}' during trade."

    return analysis


# ══════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════════

def close_signal(signal_id: str, reason: str = "manual") -> Optional[Dict]:
    """Manually close a signal with full audit trail."""
    active = store.load_active()
    closed = store.load_closed()
    target = None
    remaining = []

    for s in active:
        if s["id"] == signal_id:
            s["status"] = "MANUAL_CLOSE"
            s["close_reason"] = reason
            s["closed_at"] = datetime.datetime.utcnow().isoformat()
            s["close_session"] = _is_us_market_open()["session"]
            s["close_price"] = s["current_price"]

            # MAE/MFE final calc
            entry = s["entry_price"]
            if entry > 0:
                s["mae_pct"] = round((s["lowest_price"] - entry) / entry * 100, 2)
                s["mfe_pct"] = round((s["highest_price"] - entry) / entry * 100, 2)

            try:
                s["close_market_context"] = _fetch_market_context()
            except Exception:
                s["close_market_context"] = {}

            s["close_snapshot"] = {
                "price": s["close_price"], "pnl_pct": s["pnl_pct"],
                "mae_pct": s.get("mae_pct", 0), "mfe_pct": s.get("mfe_pct", 0),
                "bars_held": s["bars_held"],
            }
            _save_case_report(s)
            target = s
            closed.append(s)
        else:
            remaining.append(s)

    store.save_active(remaining)
    store.save_closed(closed)

    # ── Trade log ──
    if target:
        try:
            from core.trade_log import log_closed_signal
            log_closed_signal(target)
        except Exception as _tl_err:
            print(f"  [TradeLog] warning: {_tl_err}")

    # ── Telegram alert: manual close ──
    if target:
        try:
            from core.telegram_alerts import alert_signal_closed
            alert_signal_closed(target, reason, target.get("close_price", 0))
        except Exception:
            pass

    return target


def get_all_signals() -> Dict[str, Any]:
    """Get all signals without price refresh (fast)."""
    active = store.load_active()
    closed = store.load_closed()
    return {
        "active": active,
        "closed": closed,
        "stats": _calc_stats(closed),
        "market_status": _is_us_market_open(),
    }


def clear_all() -> Dict[str, str]:
    """Reset all signals (for testing)."""
    store.clear_all()
    return {"status": "cleared"}


def get_signal_report(signal_id: str) -> Optional[Dict]:
    """Retrieve a case report for a specific signal."""
    return store.load_report(signal_id)


def get_all_reports() -> List[Dict]:
    """Get all case reports."""
    return store.load_all_reports()


def get_regime_performance() -> Dict[str, Any]:
    """Analyze performance broken down by market regime."""
    closed = store.load_closed()
    if not closed:
        return {"regimes": {}}

    regimes = {}
    for s in closed:
        regime = s.get("entry_market_context", {}).get("regime", s.get("regime", "unknown"))
        if regime not in regimes:
            regimes[regime] = {"trades": 0, "wins": 0, "total_pnl": 0, "pnls": []}
        regimes[regime]["trades"] += 1
        regimes[regime]["total_pnl"] += s["pnl_pct"]
        regimes[regime]["pnls"].append(s["pnl_pct"])
        if s["pnl_pct"] > 0:
            regimes[regime]["wins"] += 1

    result = {}
    for regime, data in regimes.items():
        result[regime] = {
            "trades": data["trades"],
            "wins": data["wins"],
            "win_rate": round(data["wins"] / data["trades"] * 100, 1) if data["trades"] else 0,
            "avg_pnl": round(data["total_pnl"] / data["trades"], 2) if data["trades"] else 0,
            "best": round(max(data["pnls"]), 2) if data["pnls"] else 0,
            "worst": round(min(data["pnls"]), 2) if data["pnls"] else 0,
        }
    return {"regimes": result}


def _calc_stats(closed: List[Dict]) -> Dict[str, Any]:
    """Calculate comprehensive win/loss stats from closed signals."""
    if not closed:
        return {
            "total_closed": 0, "wins": 0, "losses": 0, "timeouts": 0,
            "win_rate": 0, "avg_pnl": 0, "best_trade": 0, "worst_trade": 0,
            "avg_bars_held": 0, "tp1_hit_rate": 0, "tp2_hit_rate": 0,
            "avg_mae": 0, "avg_mfe": 0, "profit_factor": 0,
            "total_gap_slippage": 0, "gap_affected_trades": 0,
            "avg_conviction_winners": 0, "avg_conviction_losers": 0,
        }

    wins = [s for s in closed if s["pnl_pct"] > 0]
    losses = [s for s in closed if s["pnl_pct"] <= 0]
    timeouts = [s for s in closed if s["status"] == "TIMEOUT"]
    tp1_hits = [s for s in closed if s.get("tp1_hit")]
    tp2_hits = [s for s in closed if s.get("tp2_hit")]
    pnls = [s["pnl_pct"] for s in closed]
    bars = [s.get("bars_held", 0) for s in closed]

    # MAE / MFE aggregates
    maes = [s.get("mae_pct", 0) for s in closed]
    mfes = [s.get("mfe_pct", 0) for s in closed]

    # Profit factor
    gross_profit = sum(s["pnl_pct"] for s in wins) if wins else 0
    gross_loss = abs(sum(s["pnl_pct"] for s in losses)) if losses else 0.01
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0

    # Gap impact
    gap_trades = [s for s in closed if s.get("gap_info")]
    total_slippage = sum(abs(s.get("slippage_pct", 0)) for s in gap_trades)

    # Conviction accuracy
    avg_conv_w = round(sum(s.get("conviction",0) for s in wins) / len(wins), 1) if wins else 0
    avg_conv_l = round(sum(s.get("conviction",0) for s in losses) / len(losses), 1) if losses else 0

    return {
        "total_closed": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "timeouts": len(timeouts),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "avg_pnl": round(sum(pnls) / len(pnls), 2) if pnls else 0,
        "best_trade": round(max(pnls), 2) if pnls else 0,
        "worst_trade": round(min(pnls), 2) if pnls else 0,
        "avg_bars_held": round(sum(bars) / len(bars), 1) if bars else 0,
        "tp1_hit_rate": round(len(tp1_hits) / len(closed) * 100, 1) if closed else 0,
        "tp2_hit_rate": round(len(tp2_hits) / len(closed) * 100, 1) if closed else 0,
        # ── NEW v2.0 stats ──
        "avg_mae": round(sum(maes) / len(maes), 2) if maes else 0,
        "avg_mfe": round(sum(mfes) / len(mfes), 2) if mfes else 0,
        "profit_factor": profit_factor,
        "total_gap_slippage": round(total_slippage, 2),
        "gap_affected_trades": len(gap_trades),
        "avg_conviction_winners": avg_conv_w,
        "avg_conviction_losers": avg_conv_l,
    }
