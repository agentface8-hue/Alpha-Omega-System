"""
signal_tracker.py — Live signal tracking for paper validation v2.1
v2.1 UPGRADES:
  - Regime-based ATR targets at entry (bull = wider, chop = tighter)
  - Trailing TP3: price blows through TP3 with momentum → extend instead of close
  - Momentum fade detection: 3+ consecutive lower prices while in profit → Telegram alert
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
CLOSED_FILE  = SIGNALS_DIR / "closed_signals.json"
REPORTS_DIR  = SIGNALS_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# ── Regime-based ATR multipliers ────────────────────────────────────────────────
# Trending Bull  : wider targets — capture the swing, don't cap early
# Choppy / Range : tight targets — get in and out, don't overstay
# Trending Bear  : moderate targets — counter-trend bounces are sharp but brief
# High-Vol Event : smallest targets — survive the noise first
REGIME_MULTIPLIERS = {
    "Trending Bull":  {"sl": 0.5, "tp1": 0.75, "tp2": 1.5,  "tp3": 2.5},
    "Choppy / Range": {"sl": 0.4, "tp1": 0.50, "tp2": 0.9,  "tp3": 1.4},
    "Trending Bear":  {"sl": 0.4, "tp1": 0.50, "tp2": 1.0,  "tp3": 1.5},
    "High-Vol Event": {"sl": 0.35,"tp1": 0.40, "tp2": 0.7,  "tp3": 1.0},
}
_DEFAULT_MULTS = REGIME_MULTIPLIERS["Trending Bull"]

# Max times TP3 can trail upward on a single signal before forcing close
MAX_TP3_EXTENSIONS = 3


def _get_atr_multipliers(regime_str: str) -> dict:
    """Return ATR multipliers for the current regime."""
    return REGIME_MULTIPLIERS.get(regime_str, _DEFAULT_MULTS)


# ════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════

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
    import pytz
    now_utc = datetime.datetime.now(pytz.UTC)
    eastern = pytz.timezone("US/Eastern")
    now_et  = now_utc.astimezone(eastern)
    weekday = now_et.weekday()
    hour    = now_et.hour
    minute  = now_et.minute
    time_decimal = hour + minute / 60.0
    is_weekday     = weekday < 5
    is_regular     = 9.5 <= time_decimal < 16.0
    is_premarket   = 4.0 <= time_decimal < 9.5
    is_afterhours  = 16.0 <= time_decimal < 20.0
    return {
        "market_open": is_weekday and is_regular,
        "premarket":   is_weekday and is_premarket,
        "afterhours":  is_weekday and is_afterhours,
        "weekend":     not is_weekday,
        "et_time":     now_et.strftime("%H:%M ET"),
        "session":     "regular"    if (is_weekday and is_regular)    else
                       "premarket"  if (is_weekday and is_premarket)  else
                       "afterhours" if (is_weekday and is_afterhours) else "closed"
    }


def _fetch_market_context() -> Dict[str, Any]:
    try:
        vix_tk   = yf.Ticker("^VIX")
        vix_data = vix_tk.history(period="5d")
        vix      = float(vix_data["Close"].iloc[-1]) if not vix_data.empty else 0
        spy_tk   = yf.Ticker("SPY")
        spy_data = spy_tk.history(period="5d")
        spy_close = float(spy_data["Close"].iloc[-1]) if not spy_data.empty else 0
        spy_prev  = float(spy_data["Close"].iloc[-2]) if len(spy_data) >= 2 else spy_close
        spy_chg   = round((spy_close - spy_prev) / spy_prev * 100, 2) if spy_prev else 0
        if vix > 30:   regime = "High-Vol Event"
        elif vix > 25: regime = "Trending Bear"
        elif vix > 20: regime = "Choppy / Range"
        else:          regime = "Trending Bull"
        return {
            "vix": round(vix, 1), "spy_close": round(spy_close, 2),
            "spy_change_pct": spy_chg, "regime": regime,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {"vix": 0, "spy_close": 0, "spy_change_pct": 0,
                "regime": "Trending Bull", "error": str(e)}


def _fetch_indicator_snapshot(symbol: str, asset_type: str = "stock") -> Dict[str, Any]:
    lookup = f"{symbol}-USD" if asset_type == "crypto" and not symbol.endswith("-USD") else symbol
    try:
        tk    = yf.Ticker(lookup)
        daily = tk.history(period="1y", interval="1d")
        if daily.empty:
            return {"error": f"No data for {lookup}"}
        hourly = tk.history(period="60d", interval="1h")
        close  = float(daily["Close"].iloc[-1])
        last   = daily.iloc[-1]
        ema10  = float(daily["Close"].ewm(span=10).mean().iloc[-1])
        ema20  = float(daily["Close"].ewm(span=20).mean().iloc[-1])
        ema50  = float(daily["Close"].ewm(span=50).mean().iloc[-1])
        ma150  = float(daily["Close"].ewm(span=150).mean().iloc[-1]) if len(daily) >= 150 else 0
        ma200  = float(daily["Close"].ewm(span=200).mean().iloc[-1]) if len(daily) >= 200 else 0
        h, l, c_prev = daily["High"], daily["Low"], daily["Close"].shift(1)
        tr    = pd.concat([h-l, (h-c_prev).abs(), (l-c_prev).abs()], axis=1).max(axis=1)
        atr14 = float(tr.rolling(14).mean().iloc[-1]) if len(daily) >= 14 else 0
        delta = daily["Close"].diff()
        gain  = delta.where(delta > 0, 0).rolling(14).mean()
        loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs    = gain / loss
        rsi_s = 100 - (100 / (1 + rs))
        rsi   = float(rsi_s.iloc[-1]) if not pd.isna(rsi_s.iloc[-1]) else 50
        vol_avg20 = float(daily["Volume"].rolling(20).mean().iloc[-1])
        vol_ratio = round(float(last["Volume"]) / vol_avg20, 2) if vol_avg20 > 0 else 1.0
        body  = abs(close - float(last["Open"]))
        crange = float(last["High"]) - float(last["Low"])
        body_pct  = body / crange if crange > 0 else 0
        bull_body = close > float(last["Open"])
        if vol_ratio >= 1.5 and bull_body and close > ema20: vol_dir = "ACCUMULATION"
        elif vol_ratio >= 1.5 and (not bull_body or body_pct < 0.1): vol_dir = "DISTRIBUTION"
        else: vol_dir = "NEUTRAL"
        tf_daily  = "BULL" if close > ema20 else "BEAR"
        tf_weekly = "MIXED"
        weekly = tk.history(period="2y", interval="1wk")
        if not weekly.empty and len(weekly) >= 20:
            w_ema20   = float(weekly["Close"].ewm(span=20).mean().iloc[-1])
            tf_weekly = "BULL" if float(weekly["Close"].iloc[-1]) > w_ema20 else "BEAR"
        tf_65m, tf_240m = "MIXED", "MIXED"
        if not hourly.empty and len(hourly) >= 20:
            h_ema20 = hourly["Close"].ewm(span=20).mean()
            tf_65m  = "BULL" if float(hourly["Close"].iloc[-1]) > float(h_ema20.iloc[-1]) else "BEAR"
            h4 = hourly["Close"].resample("4h").last().dropna()
            if len(h4) >= 20:
                h4_ema20 = h4.ewm(span=20).mean()
                tf_240m  = "BULL" if float(h4.iloc[-1]) > float(h4_ema20.iloc[-1]) else "BEAR"
        bull_count = sum(1 for t in [tf_65m, tf_240m, tf_daily, tf_weekly] if t == "BULL")
        tenkan = (daily["High"].rolling(9).max()  + daily["Low"].rolling(9).min())  / 2
        kijun  = (daily["High"].rolling(26).max() + daily["Low"].rolling(26).min()) / 2
        spanA  = ((tenkan + kijun) / 2).shift(26)
        spanB  = ((daily["High"].rolling(52).max() + daily["Low"].rolling(52).min()) / 2).shift(26)
        sA = float(spanA.iloc[-1]) if not pd.isna(spanA.iloc[-1]) else 0
        sB = float(spanB.iloc[-1]) if not pd.isna(spanB.iloc[-1]) else 0
        cloud_top = max(sA, sB); cloud_bot = min(sA, sB)
        cloud_pos = "above" if close > cloud_top else "below" if close < cloud_bot else "inside"
        fib_hi  = float(daily["High"].tail(55).max())
        fib_lo  = float(daily["Low"].tail(55).min())
        fib_rng = fib_hi - fib_lo
        fib_levels = {
            "0": round(fib_hi, 2), "0.236": round(fib_hi - fib_rng*0.236, 2),
            "0.382": round(fib_hi - fib_rng*0.382, 2), "0.5": round(fib_hi - fib_rng*0.5, 2),
            "0.618": round(fib_hi - fib_rng*0.618, 2), "1.0": round(fib_lo, 2),
        }
        lr_lower = lr_upper = lr_mid = 0
        try:
            closes_arr = daily["Close"].tail(100).values
            if len(closes_arr) >= 100:
                x = np.arange(len(closes_arr))
                slope, intercept = np.polyfit(x, closes_arr, 1)
                fitted = slope * x + intercept
                std    = np.std(closes_arr - fitted)
                lr_mid   = round(float(fitted[-1]), 2)
                lr_lower = round(lr_mid - 2*std, 2)
                lr_upper = round(lr_mid + 2*std, 2)
        except Exception: pass
        poc = 0
        try:
            data50 = daily.tail(50)
            if len(data50) >= 10:
                lows_a = data50["Low"].values; highs_a = data50["High"].values; vols_a = data50["Volume"].values
                bins = np.linspace(float(np.min(lows_a)), float(np.max(highs_a)), 51)
                vol_at = np.zeros(50)
                for i in range(len(data50)):
                    lo_v, hi_v, vol_v = float(lows_a[i]), float(highs_a[i]), float(vols_a[i])
                    for b in range(50):
                        if bins[b+1] >= lo_v and bins[b] <= hi_v:
                            overlap = min(hi_v, float(bins[b+1])) - max(lo_v, float(bins[b]))
                            total_r = hi_v - lo_v if hi_v > lo_v else 1
                            vol_at[b] += vol_v * (overlap / total_r)
                poc_idx = np.argmax(vol_at)
                poc = round((float(bins[poc_idx]) + float(bins[poc_idx+1])) / 2, 2)
        except Exception: pass
        swing_lo_20 = float(daily["Low"].tail(20).min())
        return {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "price": round(close, 4), "open": round(float(last["Open"]), 4),
            "high": round(float(last["High"]), 4), "low": round(float(last["Low"]), 4),
            "volume": int(last["Volume"]),
            "ema10": round(ema10, 4), "ema20": round(ema20, 4), "ema50": round(ema50, 4),
            "ma150": round(ma150, 4), "ma200": round(ma200, 4),
            "rsi14": round(rsi, 1), "atr14": round(atr14, 4),
            "vol_ratio": vol_ratio, "vol_avg20": round(vol_avg20, 0), "vol_direction": vol_dir,
            "body_pct": round(body_pct, 3), "bull_body": bull_body,
            "tf_65m": tf_65m, "tf_240m": tf_240m, "tf_daily": tf_daily, "tf_weekly": tf_weekly,
            "tas": f"{bull_count}/4",
            "cloud_position": cloud_pos, "cloud_top": round(cloud_top, 2), "cloud_bottom": round(cloud_bot, 2),
            "fib_levels": fib_levels, "lr_channel": {"lower": lr_lower, "mid": lr_mid, "upper": lr_upper},
            "poc": poc, "swing_lo_20": round(swing_lo_20, 2),
            "dist_ema20_pct": round((close-ema20)/ema20*100, 2) if ema20 else 0,
            "dist_ma150_pct": round((close-ma150)/ma150*100, 2) if ma150 else 0,
            "dist_poc_pct":   round((close-poc)/poc*100, 2) if poc else 0,
        }
    except Exception as e:
        return {"error": str(e), "timestamp": datetime.datetime.utcnow().isoformat()}


def _fetch_live_price(symbol: str, asset_type: str = "stock") -> Dict[str, Any]:
    lookup = f"{symbol}-USD" if asset_type == "crypto" and not symbol.endswith("-USD") else symbol
    try:
        tk = yf.Ticker(lookup)
        fi = tk.fast_info
        price      = fi.get("lastPrice") or fi.get("last_price") or fi.get("previousClose", 0)
        prev_close = fi.get("previousClose", 0)
        if not price or price <= 0:
            return {"price": 0, "valid": False, "reason": "no_price"}
        price = float(price); prev_close = float(prev_close) if prev_close else price
        market   = _is_us_market_open()
        is_stale = asset_type == "stock" and market["market_open"] and price == prev_close
        gap_pct  = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0
        return {
            "price": round(price, 4), "prev_close": round(prev_close, 4),
            "gap_pct": gap_pct, "is_stale": is_stale, "valid": True,
            "session": market["session"],
            "delay_warning": "15-20min delayed" if asset_type == "stock" else "near-realtime"
        }
    except Exception as e:
        return {"price": 0, "valid": False, "reason": str(e)}


def _detect_gap_fill(signal: Dict, current_price: float, prev_close: float) -> Dict[str, Any]:
    entry = signal["entry_price"]; sl = signal["sl"]
    tp1   = signal["tp1"];         tp3 = signal["tp3"]
    is_turbo = signal.get("turbo", False)
    result = {"gap_detected": False, "fill_price": current_price, "gap_type": None, "slippage_pct": 0}
    if prev_close > sl and current_price <= sl:
        actual_fill = current_price; intended_fill = sl
        slippage = round((intended_fill - actual_fill) / intended_fill * 100, 2)
        result = {
            "gap_detected": True, "fill_price": actual_fill,
            "gap_type": "gap_through_sl", "intended_sl": intended_fill,
            "slippage_pct": slippage,
            "note": f"SL was ${intended_fill} but price gapped to ${actual_fill} (slippage {slippage}%)"
        }
    tp_target = tp1 if is_turbo else tp3
    if prev_close < tp_target and current_price >= tp_target:
        result = {
            "gap_detected": True, "fill_price": current_price,
            "gap_type": "gap_through_tp",
            "note": f"TP gapped — filled at ${current_price} instead of ${tp_target}"
        }
    return result


# ════════════════════════════════════════════════════════════
# SIGNAL CREATION
# ════════════════════════════════════════════════════════════

def record_signal(scan_result: Dict[str, Any], asset_type: str = "stock") -> List[Dict]:
    active         = store.load_active()
    active_tickers = {s["ticker"] for s in active}
    new_signals    = []
    market_ctx     = _fetch_market_context()
    for r in scan_result.get("results", []):
        if r.get("hard_fail") or r.get("conviction_pct", 0) < 60:
            continue
        ticker = r["ticker"]
        if ticker in active_tickers:
            continue
        signal = {
            "id": str(uuid.uuid4())[:8], "ticker": ticker, "asset_type": asset_type,
            "entry_price": r["last_close"], "entry_time": datetime.datetime.utcnow().isoformat(),
            "conviction": r["conviction_pct"], "heat": r["heat"],
            "sl": r["sl"], "tp1": r["tp1"], "tp2": r["tp2"], "tp3": r["tp3"],
            "rr": r["rr"], "qty": r["qty"],
            "regime": scan_result.get("market_regime", ""),
            "tas": r["tas"], "trend": r["trend"],
            "pillar_scores": r.get("pillar_scores", {}),
            "ta_note": r.get("ta_note", ""),
            "entry_market_context": market_ctx,
            "entry_snapshot": {
                "rsi": r.get("rsi", 0), "atr": r.get("atr", 0), "vol_ratio": r.get("vol_ratio", 0),
                "vol_direction": r.get("vol_direction", ""), "cloud_position": r.get("cloud_position", ""),
                "ma150_position": r.get("ma150_position", ""), "coiling": r.get("coiling", False),
                "fib_levels": r.get("fib_levels", {}), "tf_breakdown": r.get("tf_breakdown", {}),
                "confluence_zones": r.get("confluence_zones", []), "fvg_zones": r.get("fvg_zones", []),
                "lr_channel": r.get("lr_channel", {}), "sector": r.get("sector", ""),
                "body_pct": r.get("body_pct", 0), "near_confluence": r.get("near_confluence", False),
            },
            "entry_session": _is_us_market_open()["session"],
            "status": "OPEN", "current_price": r["last_close"],
            "pnl_pct": 0, "highest_price": r["last_close"], "lowest_price": r["last_close"],
            "mae_pct": 0, "mfe_pct": 0,
            "tp1_hit": False, "tp2_hit": False, "tp3_hit": False,
            "tp3_extensions": 0, "trailing_active": False,
            "momentum_down_count": 0, "fade_alert_sent": False,
            "closed_at": None, "close_reason": None, "bars_held": 0,
            "close_price": None, "close_snapshot": None,
            "close_market_context": None, "close_session": None,
            "gap_info": None, "slippage_pct": 0, "turbo": False,
        }
        active.append(signal)
        active_tickers.add(ticker)
        new_signals.append(signal)
    store.save_active(active)
    return new_signals


def create_turbo_signal(symbol: str, asset_type: str = "stock",
                        scan_data: Dict = None) -> Dict:
    """
    Create turbo scalp signal with REGIME-AWARE ATR targets.
    v2.1: Targets are wider in Trending Bull, tighter in Choppy/Bear.
    """
    sym    = symbol.upper()
    lookup = f"{sym}-USD" if asset_type == "crypto" and not sym.endswith("-USD") else sym

    # ─ Fetch live price ─────────────────────────────────────────────────────
    price_data = _fetch_live_price(sym, asset_type)
    if not price_data["valid"]:
        return {"error": f"Could not fetch price for {lookup}: {price_data.get('reason','')}"}
    price = price_data["price"]
    if price <= 0:
        return {"error": f"Invalid price ${price} for {lookup}"}

    # ─ Fetch market context FIRST (needed for regime-based targets) ──────────
    market_ctx    = _fetch_market_context()
    market_status = _is_us_market_open()
    regime_str    = market_ctx.get("regime", "Trending Bull")

    # ─ ATR calculation ─────────────────────────────────────────────────────
    atr_val = 0
    try:
        tk    = yf.Ticker(lookup)
        daily = tk.history(period="30d", interval="1d")
        if not daily.empty and len(daily) >= 14:
            h, l, c_prev = daily["High"], daily["Low"], daily["Close"].shift(1)
            tr      = pd.concat([h-l, (h-c_prev).abs(), (l-c_prev).abs()], axis=1).max(axis=1)
            atr_val = float(tr.rolling(14).mean().iloc[-1])
    except Exception:
        pass

    # ─ Regime-aware targets ─────────────────────────────────────────────
    if atr_val > 0:
        mults = _get_atr_multipliers(regime_str)
        sl  = round(price - atr_val * mults["sl"],  4)
        tp1 = round(price + atr_val * mults["tp1"], 4)
        tp2 = round(price + atr_val * mults["tp2"], 4)
        tp3 = round(price + atr_val * mults["tp3"], 4)
        rr  = round((tp1 - price) / (price - sl), 2) if price > sl else 1.0
        target_method = f"atr_{regime_str.lower().replace(' ','_').replace('/','').replace('-','')}"
        print(f"  [TARGETS] {sym} regime={regime_str}: SL={sl:.2f} TP1={tp1:.2f} TP2={tp2:.2f} TP3={tp3:.2f} (ATR={atr_val:.2f})")
    else:
        sl  = round(price * 0.998, 4)
        tp1 = round(price * 1.005, 4)
        tp2 = round(price * 1.008, 4)
        tp3 = round(price * 1.012, 4)
        rr  = 2.5
        target_method = "pct_fallback"

    # ─ Scan data pass-through ───────────────────────────────────────────────
    conviction = 0; pillar_scores = {}; heat = "TURBO"; tas = "—"; trend = "TURBO"; ta_note = ""; entry_snapshot_data = {}
    if scan_data:
        conviction         = scan_data.get("conviction_pct", 0)
        pillar_scores      = scan_data.get("pillar_scores", {})
        heat               = scan_data.get("heat", "TURBO")
        tas                = scan_data.get("tas", "—")
        trend              = scan_data.get("trend", "TURBO")
        ta_note            = scan_data.get("ta_note", "")
        entry_snapshot_data = {
            "rsi": scan_data.get("rsi", 0), "vol_ratio": scan_data.get("vol_ratio", 0),
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

    signal = {
        "id": str(uuid.uuid4())[:8], "ticker": sym, "asset_type": asset_type,
        "entry_price": round(price, 4), "entry_time": datetime.datetime.utcnow().isoformat(),
        "conviction": conviction, "heat": heat,
        "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3,
        "rr": rr, "qty": 0,
        "regime": regime_str,
        "tas": tas, "trend": trend,
        "pillar_scores": pillar_scores, "ta_note": ta_note,
        "entry_market_context": market_ctx,
        "entry_snapshot": entry_snapshot_data if entry_snapshot_data else {
            "atr14": round(atr_val, 4), "price_data": price_data
        },
        "entry_session": market_status["session"],
        "target_method": target_method,
        "atr_at_entry": round(atr_val, 4),
        "regime_multipliers": _get_atr_multipliers(regime_str),   # stored for audit
        "price_stale_at_entry": price_data.get("is_stale", False),
        "price_delay_warning": price_data.get("delay_warning", ""),
        # ─ Tracking state ─
        "status": "OPEN", "current_price": round(price, 4),
        "pnl_pct": 0, "highest_price": round(price, 4), "lowest_price": round(price, 4),
        "mae_pct": 0, "mfe_pct": 0,
        "tp1_hit": False, "tp2_hit": False, "tp3_hit": False,
        # ─ Trailing TP state ─
        "tp3_extensions": 0, "trailing_active": False,
        # ─ Momentum fade state ─
        "prev_check_price": round(price, 4),
        "momentum_down_count": 0, "fade_alert_sent": False,
        # ─ Close data ─
        "closed_at": None, "close_reason": None, "bars_held": 0,
        "close_price": None, "close_snapshot": None,
        "close_market_context": None, "close_session": None,
        "gap_info": None, "slippage_pct": 0, "turbo": True,
    }

    active = store.load_active()
    active.append(signal)
    store.save_active(active)

    # Earnings proximity check
    try:
        from datetime import date
        cal = yf.Ticker(sym).calendar
        if cal is not None and not cal.empty:
            col = cal.columns[0]
            dt  = col.date() if hasattr(col, 'date') else date.fromisoformat(str(col)[:10])
            days = (dt - date.today()).days
            if 0 <= days <= 7:
                signal["earnings_warning"] = f"⚠ EARNINGS IN {days} DAY{'S' if days!=1 else ''} — targets unreliable"
                signal["earnings_date"] = str(dt)
                store.save_active(active)
                from core.telegram_alerts import _send
                _send(f"⚠ <b>EARNINGS WARNING — {sym}</b>\nEarnings in <b>{days} day{'s' if days!=1 else ''}</b> ({dt})\nSignal created but targets may be unreliable.")
    except Exception:
        pass

    # Telegram alert
    try:
        from core.telegram_alerts import alert_signal_created
        alert_signal_created(signal)
    except Exception:
        pass

    return signal


# ════════════════════════════════════════════════════════════
# SIGNAL MONITORING
# ════════════════════════════════════════════════════════════

def check_signals() -> Dict[str, Any]:
    active = store.load_active()
    closed = store.load_closed()
    if not active:
        return {"active": [], "closed": closed, "stats": _calc_stats(closed),
                "market_status": _is_us_market_open()}

    market_status = _is_us_market_open()

    prices = {}
    for s in active:
        sym    = s["ticker"]
        try:
            pd_result = _fetch_live_price(sym, s["asset_type"])
            if pd_result["valid"]:
                prices[sym] = pd_result
                print(f"  [LIVE] {sym} = ${pd_result['price']:.4f} "
                      f"(gap:{pd_result['gap_pct']}% stale:{pd_result['is_stale']} "
                      f"session:{pd_result['session']})")
            else:
                print(f"  [SKIP] {sym} invalid: {pd_result.get('reason','')}")
        except Exception as e:
            print(f"  [ERR] {sym}: {e}")

    newly_closed = []
    still_active = []
    warnings     = []

    for s in active:
        sym       = s["ticker"]
        pd_result = prices.get(sym)

        if not pd_result:
            still_active.append(s)
            continue

        price      = pd_result["price"]
        prev_close = pd_result.get("prev_close", price)

        if pd_result.get("is_stale"):
            warnings.append({"ticker": sym, "warning": "Price may be stale"})

        # After-hours: update price but skip close logic for stocks
        if s["asset_type"] == "stock" and not market_status["market_open"]:
            s["current_price"] = round(price, 4)
            s["price_note"] = f"Market closed ({market_status['session']})"
            entry = s["entry_price"]
            s["pnl_pct"] = round((price - entry) / entry * 100, 2) if entry else 0
            try:
                entry_dt    = datetime.datetime.fromisoformat(s["entry_time"])
                s["bars_held"] = (datetime.datetime.utcnow() - entry_dt).days
            except Exception: pass
            still_active.append(s)
            continue

        gap_info = _detect_gap_fill(s, price, prev_close)
        if gap_info["gap_detected"]:
            price = gap_info["fill_price"]
            print(f"  [GAP] {sym}: {gap_info['note']}")

        s["current_price"] = round(price, 4)

        try:
            entry_dt    = datetime.datetime.fromisoformat(s["entry_time"])
            s["bars_held"] = (datetime.datetime.utcnow() - entry_dt).days
        except Exception: pass

        if price > s["highest_price"]: s["highest_price"] = round(price, 4)
        if price < s["lowest_price"]:  s["lowest_price"]  = round(price, 4)

        entry = s["entry_price"]
        if entry > 0:
            s["pnl_pct"] = round((price - entry) / entry * 100, 2)
            s["mae_pct"] = round((s["lowest_price"]  - entry) / entry * 100, 2)
            s["mfe_pct"] = round((s["highest_price"] - entry) / entry * 100, 2)

        # ─ TP hit tracking ───────────────────────────────────────────────
        if price >= s["tp1"] and not s["tp1_hit"]:
            s["tp1_hit"] = True
            s["tp1_hit_time"] = datetime.datetime.utcnow().isoformat()
            try:
                from core.telegram_alerts import alert_tp_hit
                alert_tp_hit(s, "tp1", price)
            except Exception: pass
        if price >= s["tp2"] and not s["tp2_hit"]:
            s["tp2_hit"] = True
            s["tp2_hit_time"] = datetime.datetime.utcnow().isoformat()
            try:
                from core.telegram_alerts import alert_tp_hit
                alert_tp_hit(s, "tp2", price)
            except Exception: pass
        if price >= s["tp3"] and not s["tp3_hit"]:
            s["tp3_hit"] = True
            s["tp3_hit_time"] = datetime.datetime.utcnow().isoformat()
            try:
                from core.telegram_alerts import alert_tp_hit
                alert_tp_hit(s, "tp3", price)
            except Exception: pass

        # ─ Momentum fade detection ─────────────────────────────────────────
        # Fire Telegram alert when a winning trade starts giving back gains.
        # Condition: TP1 already hit + price declining 3+ consecutive checks + giving back 1.5%+
        if s.get("tp1_hit") and s.get("pnl_pct", 0) > 0:
            prev_p = s.get("prev_check_price", price)
            if price < prev_p:
                s["momentum_down_count"] = s.get("momentum_down_count", 0) + 1
            else:
                s["momentum_down_count"] = 0   # reset on any up-tick
            s["prev_check_price"] = round(price, 4)

            mfe         = s.get("mfe_pct", 0)
            pnl         = s.get("pnl_pct", 0)
            giving_back = mfe - pnl
            fade_count  = s.get("momentum_down_count", 0)

            if fade_count >= 3 and giving_back >= 1.5 and not s.get("fade_alert_sent"):
                s["fade_alert_sent"] = True
                print(f"  [FADE] {sym}: momentum fading, giving back {giving_back:.1f}% from MFE")
                try:
                    from core.telegram_alerts import alert_momentum_fade
                    alert_momentum_fade(s, pnl, mfe)
                except Exception: pass

        # ─ Close conditions ───────────────────────────────────────────────
        is_turbo     = s.get("turbo", False)
        should_close = False
        close_status = ""
        close_reason = ""

        if price <= s["sl"]:
            close_status = "STOPPED_OUT"
            actual_fill  = gap_info["fill_price"] if gap_info["gap_detected"] else s["sl"]
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
            except Exception: pass

        elif is_turbo and s["tp1_hit"]:
            close_status = "TP1_HIT"
            close_reason = f"Turbo TP1 hit at ${s['tp1']}"
            s["close_price"] = round(price, 4)
            should_close = True

        elif s["tp3_hit"]:
            extensions = s.get("tp3_extensions", 0)
            # ─ TRAILING TP3: extend instead of closing if price blew through cleanly ─
            # Condition: price must be >0.5% above TP3 (not just touching), and < MAX extensions
            if extensions < MAX_TP3_EXTENSIONS and price > s["tp3"] * 1.005:
                atr_est = s.get("atr_at_entry", 0)
                if atr_est <= 0:
                    # Fallback: estimate ATR from original targets
                    tp1_orig = s.get("tp1", 0)
                    sl_orig  = s.get("sl", 0)
                    atr_est  = abs(tp1_orig - entry) / 0.75 if tp1_orig and entry else 0
                new_tp3 = round(price + (atr_est * 0.5 if atr_est > 0 else price * 0.01), 4)
                old_tp3 = s["tp3"]
                s["tp3"]            = new_tp3
                s["tp3_hit"]        = False   # reset — still running
                s["tp3_extensions"] = extensions + 1
                s["trailing_active"] = True
                print(f"  [TRAIL] {sym}: TP3 extended {old_tp3:.2f} → {new_tp3:.2f} (ext #{extensions+1})")
                try:
                    from core.telegram_alerts import alert_tp_extended
                    alert_tp_extended(s, new_tp3, extensions + 1)
                except Exception: pass
                # Don't close — fall through to still_active
            else:
                # Max extensions reached or price just barely touching TP3 — close
                close_status = "TP3_HIT"
                ext_count    = s.get("tp3_extensions", 0)
                close_reason = (
                    f"Trailing TP3 final close at ${s['tp3']:.2f} after "
                    f"{ext_count} extension{'s' if ext_count != 1 else ''}"
                    if s.get("trailing_active")
                    else f"TP3 hit at ${s['tp3']}"
                )
                s["close_price"] = round(price, 4)
                should_close = True

        elif s["bars_held"] >= 30:
            close_status = "TIMEOUT"
            close_reason = f"30-day timeout at ${price}"
            s["close_price"] = round(price, 4)
            should_close = True

        if should_close:
            s["status"]       = close_status
            s["close_reason"] = close_reason
            s["closed_at"]    = datetime.datetime.utcnow().isoformat()
            s["close_session"] = market_status["session"]
            s["gap_info"]     = gap_info if gap_info["gap_detected"] else None
            try:
                s["close_market_context"] = _fetch_market_context()
            except Exception:
                s["close_market_context"] = {"error": "failed"}
            s["close_snapshot"] = {
                "price": s["close_price"], "pnl_pct": s["pnl_pct"],
                "mae_pct": s["mae_pct"], "mfe_pct": s["mfe_pct"],
                "bars_held": s["bars_held"],
                "highest_price": s["highest_price"], "lowest_price": s["lowest_price"],
                "slippage_pct": s.get("slippage_pct", 0),
                "tp3_extensions": s.get("tp3_extensions", 0),
                "trailing_active": s.get("trailing_active", False),
            }
            _save_case_report(s)
            try:
                from core.trade_log import log_closed_signal
                log_closed_signal(s)
            except Exception as e:
                print(f"  [TradeLog] warning: {e}")
            newly_closed.append(s)
        else:
            still_active.append(s)

    closed.extend(newly_closed)
    store.save_active(still_active)
    store.save_closed(closed)

    return {
        "active": still_active, "recently_closed": newly_closed,
        "closed": closed, "stats": _calc_stats(closed),
        "market_status": market_status, "warnings": warnings,
    }


# ════════════════════════════════════════════════════════════
# CASE REPORT GENERATOR
# ════════════════════════════════════════════════════════════

def _save_case_report(signal: Dict):
    try:
        report = {
            "report_version": "2.1",
            "generated_at": datetime.datetime.utcnow().isoformat(),
            "signal_id": signal["id"], "ticker": signal["ticker"], "asset_type": signal["asset_type"],
            "entry": {
                "price": signal["entry_price"], "time": signal["entry_time"],
                "session": signal.get("entry_session", "unknown"),
                "conviction": signal["conviction"], "heat": signal["heat"],
                "pillar_scores": signal["pillar_scores"], "tas": signal["tas"], "trend": signal["trend"],
                "ta_note": signal.get("ta_note", ""), "regime": signal["regime"],
                "market_context": signal.get("entry_market_context", {}),
                "indicator_snapshot": signal.get("entry_snapshot", {}),
                "target_method": signal.get("target_method", "unknown"),
                "atr_at_entry": signal.get("atr_at_entry", 0),
                "regime_multipliers": signal.get("regime_multipliers", {}),
                "price_stale_at_entry": signal.get("price_stale_at_entry", False),
            },
            "targets": {
                "sl": signal["sl"], "tp1": signal["tp1"], "tp2": signal["tp2"], "tp3": signal["tp3"],
                "rr": signal["rr"], "turbo": signal.get("turbo", False),
                "tp3_extensions": signal.get("tp3_extensions", 0),
                "trailing_active": signal.get("trailing_active", False),
            },
            "exit": {
                "price": signal.get("close_price"), "time": signal.get("closed_at"),
                "status": signal["status"], "reason": signal["close_reason"],
                "session": signal.get("close_session", "unknown"),
                "market_context": signal.get("close_market_context", {}),
                "snapshot": signal.get("close_snapshot", {}),
            },
            "performance": {
                "pnl_pct": signal["pnl_pct"], "mae_pct": signal.get("mae_pct", 0),
                "mfe_pct": signal.get("mfe_pct", 0),
                "highest_price": signal["highest_price"], "lowest_price": signal["lowest_price"],
                "bars_held": signal["bars_held"], "tp1_hit": signal["tp1_hit"],
                "tp2_hit": signal["tp2_hit"], "tp3_hit": signal["tp3_hit"],
                "slippage_pct": signal.get("slippage_pct", 0),
                "gap_info": signal.get("gap_info"),
                "tp3_extensions": signal.get("tp3_extensions", 0),
            },
            "analysis": _generate_trade_analysis(signal),
        }
        filename = store.save_report(report)
        print(f"  [REPORT] Saved: {filename}")
    except Exception as e:
        print(f"  [REPORT] Error for {signal.get('ticker','?')}: {e}")


def _generate_trade_analysis(signal: Dict) -> Dict[str, Any]:
    analysis = {}
    entry  = signal["entry_price"]
    mae    = signal.get("mae_pct", 0)
    mfe    = signal.get("mfe_pct", 0)
    pnl    = signal["pnl_pct"]
    status = signal["status"]
    bars   = signal["bars_held"]

    if status == "STOPPED_OUT" and mfe > 0.5:
        analysis["sl_review"] = f"Trade went +{mfe}% before reversing to SL. MFE suggests SL may be too tight."
    elif status == "STOPPED_OUT" and mfe <= 0:
        analysis["sl_review"] = "Trade never went positive — entry timing was poor."
    if status == "TIMEOUT" and mfe > 0:
        analysis["tp_review"] = f"Trade hit +{mfe}% but didn't reach TP. Consider tighter targets."
    if signal["tp1_hit"] and not signal["tp3_hit"] and status == "STOPPED_OUT":
        analysis["tp_review"] = "TP1 was hit but trade reversed to SL. Consider taking profit at TP1."
    if pnl > 0 and mae < -0.5:
        analysis["mae_insight"] = f"Winner but saw {mae}% drawdown. Risk management held."
    if pnl < 0 and mae < -2:
        analysis["mae_insight"] = f"Severe drawdown of {mae}%. SL may need adjustment."
    if bars <= 1 and abs(pnl) > 1:
        analysis["speed"] = "Fast move — signal resolved within 1 day."
    elif bars > 14 and abs(pnl) < 1:
        analysis["speed"] = "Slow grind — low P&L after 2+ weeks. Consider time-based exit."
    conv = signal.get("conviction", 0)
    if conv >= 70 and pnl < 0:
        analysis["conviction_accuracy"] = f"HIGH conviction ({conv}%) but LOSS. Investigate pillar scores."
    elif conv < 50 and pnl > 2:
        analysis["conviction_accuracy"] = f"LOW conviction ({conv}%) but BIG WIN (+{pnl}%). Scoring underweights something."
    if signal.get("gap_info"):
        analysis["gap_impact"] = f"Gap detected. Slippage: {signal.get('slippage_pct',0)}%."
    if signal.get("entry_session") == "premarket":
        analysis["session_note"] = "Entered during pre-market. Prices may have been less reliable."
    entry_regime = signal.get("entry_market_context", {}).get("regime", "")
    close_regime = signal.get("close_market_context", {}).get("regime", "")
    if entry_regime and close_regime and entry_regime != close_regime:
        analysis["regime_shift"] = f"Regime changed '{entry_regime}' → '{close_regime}' during trade."
    if signal.get("trailing_active"):
        ext = signal.get("tp3_extensions", 0)
        analysis["trailing_tp"] = (
            f"Trailing TP3 activated — {ext} extension{'s' if ext!=1 else ''}. "
            f"Final exit at ${signal.get('close_price', '?')} vs original TP3."
        )
    if signal.get("fade_alert_sent"):
        analysis["momentum_fade"] = "Momentum fade alert was fired during this trade."
    return analysis


# ════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ════════════════════════════════════════════════════════════

def close_signal(signal_id: str, reason: str = "manual") -> Optional[Dict]:
    active = store.load_active()
    closed = store.load_closed()
    target = None; remaining = []
    for s in active:
        if s["id"] == signal_id:
            s["status"] = "MANUAL_CLOSE"; s["close_reason"] = reason
            s["closed_at"] = datetime.datetime.utcnow().isoformat()
            s["close_session"] = _is_us_market_open()["session"]
            s["close_price"] = s["current_price"]
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
                "tp3_extensions": s.get("tp3_extensions", 0),
            }
            _save_case_report(s); target = s; closed.append(s)
        else:
            remaining.append(s)
    store.save_active(remaining); store.save_closed(closed)
    if target:
        try:
            from core.trade_log import log_closed_signal
            log_closed_signal(target)
        except Exception as e:
            print(f"  [TradeLog] warning: {e}")
    if target:
        try:
            from core.telegram_alerts import alert_signal_closed
            alert_signal_closed(target, reason, target.get("close_price", 0))
        except Exception: pass
    return target


def get_all_signals() -> Dict[str, Any]:
    active = store.load_active(); closed = store.load_closed()
    return {
        "active": active, "closed": closed,
        "stats": _calc_stats(closed), "market_status": _is_us_market_open(),
    }


def clear_all() -> Dict[str, str]:
    store.clear_all(); return {"status": "cleared"}


def get_signal_report(signal_id: str) -> Optional[Dict]:
    return store.load_report(signal_id)


def get_all_reports() -> List[Dict]:
    return store.load_all_reports()


def get_regime_performance() -> Dict[str, Any]:
    closed = store.load_closed()
    if not closed: return {"regimes": {}}
    regimes = {}
    for s in closed:
        regime = s.get("entry_market_context", {}).get("regime", s.get("regime", "unknown"))
        if regime not in regimes:
            regimes[regime] = {"trades": 0, "wins": 0, "total_pnl": 0, "pnls": []}
        regimes[regime]["trades"] += 1
        regimes[regime]["total_pnl"] += s["pnl_pct"]
        regimes[regime]["pnls"].append(s["pnl_pct"])
        if s["pnl_pct"] > 0: regimes[regime]["wins"] += 1
    result = {}
    for regime, data in regimes.items():
        result[regime] = {
            "trades": data["trades"], "wins": data["wins"],
            "win_rate": round(data["wins"] / data["trades"] * 100, 1) if data["trades"] else 0,
            "avg_pnl": round(data["total_pnl"] / data["trades"], 2) if data["trades"] else 0,
            "best": round(max(data["pnls"]), 2) if data["pnls"] else 0,
            "worst": round(min(data["pnls"]), 2) if data["pnls"] else 0,
        }
    return {"regimes": result}


def _calc_stats(closed: List[Dict]) -> Dict[str, Any]:
    if not closed:
        return {
            "total_closed": 0, "wins": 0, "losses": 0, "timeouts": 0,
            "win_rate": 0, "avg_pnl": 0, "best_trade": 0, "worst_trade": 0,
            "avg_bars_held": 0, "tp1_hit_rate": 0, "tp2_hit_rate": 0,
            "avg_mae": 0, "avg_mfe": 0, "profit_factor": 0,
            "total_gap_slippage": 0, "gap_affected_trades": 0,
            "avg_conviction_winners": 0, "avg_conviction_losers": 0,
            "trailing_tp_trades": 0, "avg_tp3_extensions": 0,
        }
    wins     = [s for s in closed if s["pnl_pct"] > 0]
    losses   = [s for s in closed if s["pnl_pct"] <= 0]
    timeouts = [s for s in closed if s["status"] == "TIMEOUT"]
    tp1_hits = [s for s in closed if s.get("tp1_hit")]
    tp2_hits = [s for s in closed if s.get("tp2_hit")]
    pnls     = [s["pnl_pct"] for s in closed]
    bars     = [s.get("bars_held", 0) for s in closed]
    maes     = [s.get("mae_pct", 0) for s in closed]
    mfes     = [s.get("mfe_pct", 0) for s in closed]
    trailing_trades  = [s for s in closed if s.get("trailing_active")]
    extensions_total = sum(s.get("tp3_extensions", 0) for s in closed)
    gross_profit = sum(s["pnl_pct"] for s in wins)   if wins   else 0
    gross_loss   = abs(sum(s["pnl_pct"] for s in losses)) if losses else 0.01
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 0
    gap_trades    = [s for s in closed if s.get("gap_info")]
    total_slippage = sum(abs(s.get("slippage_pct", 0)) for s in gap_trades)
    avg_conv_w = round(sum(s.get("conviction",0) for s in wins)   / len(wins),   1) if wins   else 0
    avg_conv_l = round(sum(s.get("conviction",0) for s in losses) / len(losses), 1) if losses else 0
    return {
        "total_closed": len(closed), "wins": len(wins), "losses": len(losses),
        "timeouts": len(timeouts),
        "win_rate":     round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "avg_pnl":      round(sum(pnls) / len(pnls), 2) if pnls else 0,
        "best_trade":   round(max(pnls), 2) if pnls else 0,
        "worst_trade":  round(min(pnls), 2) if pnls else 0,
        "avg_bars_held": round(sum(bars) / len(bars), 1) if bars else 0,
        "tp1_hit_rate": round(len(tp1_hits) / len(closed) * 100, 1) if closed else 0,
        "tp2_hit_rate": round(len(tp2_hits) / len(closed) * 100, 1) if closed else 0,
        "avg_mae":      round(sum(maes) / len(maes), 2) if maes else 0,
        "avg_mfe":      round(sum(mfes) / len(mfes), 2) if mfes else 0,
        "profit_factor": profit_factor,
        "total_gap_slippage": round(total_slippage, 2),
        "gap_affected_trades": len(gap_trades),
        "avg_conviction_winners": avg_conv_w,
        "avg_conviction_losers":  avg_conv_l,
        # New v2.1 trailing stats
        "trailing_tp_trades":  len(trailing_trades),
        "avg_tp3_extensions":  round(extensions_total / len(closed), 2) if closed else 0,
    }
