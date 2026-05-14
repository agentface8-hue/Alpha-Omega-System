"""
market_data.py — Real market data fetcher for SwingTrader v4.3 integration
Uses yfinance to compute all metrics needed by the 5-pillar framework.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


def fetch_ticker_data(symbol: str) -> Dict[str, Any]:
    """
    Fetch comprehensive market data for a single ticker.
    Returns all metrics needed for v4.3 5-pillar scoring.
    """
    try:
        tk = yf.Ticker(symbol)

        # Daily data (1 year for 150MA + 55-bar fib)
        daily = tk.history(period="1y", interval="1d")
        if daily.empty:
            return {"error": f"No data for {symbol}", "symbol": symbol}

        # Weekly data (1 year is enough for EMA9/21 on weekly)
        weekly = tk.history(period="1y", interval="1wk")

        # Hourly data (30d is enough for 65m/240m signals — saves ~50% RAM vs 60d)
        hourly = tk.history(period="30d", interval="1h")

        # Info
        info = {}
        try:
            info = tk.info or {}
        except Exception:
            pass

        last = daily.iloc[-1]
        close = float(last["Close"])
        last_date = daily.index[-1].strftime("%Y-%m-%d")

        # ── Core indicators ──
        ema9  = daily["Close"].ewm(span=9).mean()
        ema21 = daily["Close"].ewm(span=21).mean()
        ema10 = daily["Close"].ewm(span=10).mean()
        ema20 = daily["Close"].ewm(span=20).mean()  # kept for legacy reference
        ma150 = daily["Close"].ewm(span=150).mean()
        atr14 = _atr(daily, 14)

        # RSI
        rsi14 = _rsi(daily["Close"], 14)

        # Volume
        vol_avg20 = daily["Volume"].rolling(20).mean().iloc[-1]
        vol_ratio = round(float(last["Volume"]) / vol_avg20, 2) if vol_avg20 > 0 else 1.0

        # Volume direction
        bull_body = close > float(last["Open"])
        body = abs(close - float(last["Open"]))
        crange = float(last["High"]) - float(last["Low"])
        body_pct = body / crange if crange > 0 else 0
        upwick = float(last["High"]) - max(close, float(last["Open"]))
        long_upper_wick = upwick > crange * 0.5 if crange > 0 else False
        is_doji = body_pct < 0.1

        if vol_ratio >= 1.5 and bull_body and close > float(ema9.iloc[-1]):
            vol_direction = "ACCUMULATION"
        elif vol_ratio >= 1.5 and (not bull_body or is_doji or long_upper_wick):
            vol_direction = "DISTRIBUTION"
        else:
            vol_direction = "NEUTRAL"

        # ── MTF Trend Assessment — EMA9/21 dual confirmation ──
        # Daily: close > EMA9 AND EMA9 > EMA21 (fast trend + confirmation)
        ema9_val  = float(ema9.iloc[-1])
        ema21_val = float(ema21.iloc[-1])
        tf_daily = "BULL" if close > ema9_val and ema9_val > ema21_val else "BEAR"

        # Weekly: close vs weekly EMA9/21
        if not weekly.empty and len(weekly) >= 21:
            w_ema9  = weekly["Close"].ewm(span=9).mean()
            w_ema21 = weekly["Close"].ewm(span=21).mean()
            w_close = float(weekly["Close"].iloc[-1])
            tf_weekly = "BULL" if w_close > float(w_ema9.iloc[-1]) and float(w_ema9.iloc[-1]) > float(w_ema21.iloc[-1]) else "BEAR"
        else:
            tf_weekly = "MIXED"

        # 4H approximation from hourly — EMA9/21
        tf_240m = "MIXED"
        tf_65m  = "MIXED"
        if not hourly.empty and len(hourly) >= 21:
            h_ema9  = hourly["Close"].ewm(span=9).mean()
            h_ema21 = hourly["Close"].ewm(span=21).mean()
            h_close = float(hourly["Close"].iloc[-1])
            tf_65m = "BULL" if h_close > float(h_ema9.iloc[-1]) and float(h_ema9.iloc[-1]) > float(h_ema21.iloc[-1]) else "BEAR"
            # 4H: resample hourly to 4H
            h4 = hourly["Close"].resample("4h").last().dropna()
            if len(h4) >= 21:
                h4_ema9  = h4.ewm(span=9).mean()
                h4_ema21 = h4.ewm(span=21).mean()
                h4_close = float(h4.iloc[-1])
                tf_240m = "BULL" if h4_close > float(h4_ema9.iloc[-1]) and float(h4_ema9.iloc[-1]) > float(h4_ema21.iloc[-1]) else "BEAR"

        # TAS
        bull_count = sum(1 for t in [tf_65m, tf_240m, tf_daily, tf_weekly] if t == "BULL")
        tas = f"{bull_count}/4"

        # 150MA position
        ma150_val = float(ma150.iloc[-1]) if len(ma150) >= 150 else float(ema20.iloc[-1])
        ma150_position = "above" if close > ma150_val else "below"

        # ── Fibonacci (55-bar) ──
        fib_hi = float(daily["High"].tail(55).max())
        fib_lo = float(daily["Low"].tail(55).min())
        fib_rng = fib_hi - fib_lo
        fib_levels = {
            "0": round(fib_hi, 2),
            "0.236": round(fib_hi - fib_rng * 0.236, 2),
            "0.382": round(fib_hi - fib_rng * 0.382, 2),
            "0.500": round(fib_hi - fib_rng * 0.500, 2),
            "0.618": round(fib_hi - fib_rng * 0.618, 2),
            "0.786": round(fib_hi - fib_rng * 0.786, 2),
            "1.0": round(fib_lo, 2),
        }

        # 35-bar fib for confluence
        fib35_hi = float(daily["High"].tail(35).max())
        fib35_lo = float(daily["Low"].tail(35).min())
        fib35_rng = fib35_hi - fib35_lo
        fib35_382 = round(fib35_hi - fib35_rng * 0.382, 2)
        fib55_236 = fib_levels["0.236"]

        # Confluence zones (where 35-bar and 55-bar fibs overlap within 0.5%)
        confluence_zones = []
        for f35 in [round(fib35_hi - fib35_rng * r, 2) for r in [0.236, 0.382, 0.5, 0.618]]:
            for f55 in [fib_levels["0.236"], fib_levels["0.382"], fib_levels["0.500"], fib_levels["0.618"]]:
                if abs(f35 - f55) / max(f35, 0.01) < 0.005:
                    confluence_zones.append(round((f35 + f55) / 2, 2))
        confluence_zones = sorted(set(confluence_zones))[:4]

        # ── Patterns ──
        avg_rng10 = daily["High"].tail(10).sub(daily["Low"].tail(10)).mean()
        last3_rngs = [float(daily["High"].iloc[-i] - daily["Low"].iloc[-i]) for i in range(1, 4)]
        coiling = all(r < float(avg_rng10) * 0.5 for r in last3_rngs)

        # ── NEW: Coiling 3 vs 5 candle ──
        coil_data = _coiling_check(daily)

        # ── NEW: Linear Regression Channel ──
        lr_channel = _linear_regression_channel(daily, 100)

        # ── NEW: Fair Value Gaps ──
        fvg_zones = _fair_value_gaps(daily, 50)

        # ── NEW: Volume Profile / POC ──
        vol_profile = _volume_profile_poc(daily, 50)

        # ── NEW: 65m Sustained Bull Check ──
        sustained_65m = _sustained_65m_check(hourly, 3)

        # ── NEW: Double Bottom Pattern ──
        double_bottom = _double_bottom_check(daily)

        # ── NEW: Expanded confluence (Fib + FVG + Channel -2σ + POC) ──
        all_support_levels = list(confluence_zones)
        if lr_channel["lower_2sd"] > 0:
            all_support_levels.append(lr_channel["lower_2sd"])
        if vol_profile["poc"] > 0:
            all_support_levels.append(vol_profile["poc"])
        for fvg in fvg_zones:
            if fvg["type"] == "bullish":
                all_support_levels.append(fvg["top"])
        expanded_confluence = []
        for lvl in all_support_levels:
            overlap_count = 0
            for other in all_support_levels:
                if lvl != other and abs(lvl - other) / max(lvl, 0.01) < 0.005:
                    overlap_count += 1
            if overlap_count >= 1:
                expanded_confluence.append(round(lvl, 2))
        expanded_confluence = sorted(set(expanded_confluence))[:6]
        near_confluence = any(abs(close - z) / close < 0.005 for z in expanded_confluence) if expanded_confluence else False

        # Ichimoku cloud
        tenkan = (daily["High"].rolling(9).max() + daily["Low"].rolling(9).min()) / 2
        kijun = (daily["High"].rolling(26).max() + daily["Low"].rolling(26).min()) / 2
        spanA = ((tenkan + kijun) / 2).shift(26)
        spanB = ((daily["High"].rolling(52).max() + daily["Low"].rolling(52).min()) / 2).shift(26)

        cloud_top = max(float(spanA.iloc[-1]) if not pd.isna(spanA.iloc[-1]) else 0,
                        float(spanB.iloc[-1]) if not pd.isna(spanB.iloc[-1]) else 0)
        cloud_bot = min(float(spanA.iloc[-1]) if not pd.isna(spanA.iloc[-1]) else 0,
                        float(spanB.iloc[-1]) if not pd.isna(spanB.iloc[-1]) else 0)
        if close > cloud_top:
            cloud_position = "above"
        elif close < cloud_bot:
            cloud_position = "below"
        else:
            cloud_position = "inside"

        # SL / TP (v4.3 Triple-Guard)
        swing_lo = float(daily["Low"].tail(20).min())
        atr_val = float(atr14.iloc[-1]) if not pd.isna(atr14.iloc[-1]) else (crange * 1.5)
        # SL must be BELOW current price for longs
        sl_candidates = [close - atr_val * 1.5, swing_lo]
        # Only include fib 0.618 if it's below price
        if fib_levels["0.618"] < close:
            sl_candidates.append(fib_levels["0.618"])
        sl = round(max(c for c in sl_candidates if c < close) if any(c < close for c in sl_candidates) else close * 0.95, 2)
        tp1 = round(fib35_382, 2) if fib35_382 > close else round(close + (close - sl) * 2, 2)
        tp2 = round(fib55_236, 2) if fib55_236 > close else round(close + (close - sl) * 3, 2)
        tp3 = round(fib_lo + fib_rng * 1.272, 2)

        # R:R
        sl_dist = max(close - sl, 0.01)
        rr = round((tp1 - close) / sl_dist, 2) if sl_dist > 0 else 0

        # Qty (risk $75 per trade on $7500 capital)
        qty = max(int(75 / sl_dist), 1) if sl_dist > 0.01 else 0

        # Earnings
        earnings_warning = "Clear"
        try:
            cal = tk.calendar
            if cal is not None and not cal.empty:
                next_earnings = cal.columns[0] if hasattr(cal, 'columns') else None
                if next_earnings:
                    days_to_earnings = (pd.Timestamp(next_earnings) - pd.Timestamp.now()).days
                    if days_to_earnings < 5:
                        earnings_warning = f"⚠ {days_to_earnings}d — HARD FAIL"
                    elif days_to_earnings < 10:
                        earnings_warning = f"⚠ {days_to_earnings}d — Half size"
        except Exception:
            pass

        # Market cap
        mkt_cap_b = round(info.get("marketCap", 0) / 1e9, 1) if info.get("marketCap") else 0

        # Sector
        sector = info.get("sector", "Unknown")
        name = info.get("shortName", symbol)

        # Free large DataFrames before returning — reduces peak RAM on Render
        import gc as _gc
        del daily, weekly, hourly
        _gc.collect()

        return {
            "symbol": symbol,
            "name": name,
            "sector": sector,
            "last_close": round(close, 2),
            "last_date": last_date,
            "mkt_cap_b": mkt_cap_b,
            "ma150_position": ma150_position,
            "ma150_value": round(ma150_val, 2),
            "tas": tas,
            "tf_breakdown": {
                "tf_65m": tf_65m, "tf_240m": tf_240m,
                "tf_daily": tf_daily, "tf_weekly": tf_weekly
            },
            "vol_ratio": vol_ratio,
            "vol_direction": vol_direction,
            "coiling": coiling,
            "cloud_position": cloud_position,
            "rsi": round(float(rsi14.iloc[-1]), 1) if not pd.isna(rsi14.iloc[-1]) else 50,
            "atr": round(atr_val, 2),
            "sl": sl, "tp1": tp1, "tp2": tp2, "tp3": tp3,
            "rr": rr, "qty": qty,
            "fib_levels": fib_levels,
            "confluence_zones": confluence_zones,
            "earnings_warning": earnings_warning,
            "body_pct": round(body_pct, 3),
            "is_doji": is_doji,
            "long_upper_wick": long_upper_wick,
            "bull_body": bull_body,
            "entry_low": round(close * 0.99, 2),
            "entry_high": round(close * 1.005, 2),
            # NEW v4.4 indicators
            "lr_channel": lr_channel,
            "fvg_zones": fvg_zones,
            "vol_profile": vol_profile,
            "sustained_65m": sustained_65m,
            "coil_data": coil_data,
            "expanded_confluence": expanded_confluence,
            "near_confluence": near_confluence,
            "double_bottom": double_bottom,
        }
    except Exception as e:
        return {"error": str(e), "symbol": symbol}


def fetch_market_regime() -> Dict[str, Any]:
    """Fetch VIX, SPY, QQQ, IWM for market regime classification."""
    try:
        vix = yf.Ticker("^VIX")
        vix_data = vix.history(period="5d")
        vix_close = float(vix_data["Close"].iloc[-1]) if not vix_data.empty else 20.0

        spy = yf.Ticker("SPY")
        spy_data = spy.history(period="5d")
        spy_close = float(spy_data["Close"].iloc[-1]) if not spy_data.empty else 0
        spy_prev = float(spy_data["Close"].iloc[-2]) if len(spy_data) >= 2 else spy_close
        spy_chg = round((spy_close - spy_prev) / spy_prev * 100, 2) if spy_prev else 0

        if vix_close > 30:
            regime = "High-Vol Event"
        elif vix_close > 25:
            regime = "Trending Bear"
        elif vix_close > 20:
            regime = "Choppy / Range"
        else:
            regime = "Trending Bull"

        min_rr = 2.0 if regime == "Trending Bull" else 2.5 if regime == "Choppy / Range" else 3.0

        return {
            "vix": round(vix_close, 1),
            "regime": regime,
            "min_rr": min_rr,
            "spy_close": round(spy_close, 2),
            "spy_change_pct": spy_chg,
        }
    except Exception as e:
        return {"vix": 20.0, "regime": "Choppy / Range", "min_rr": 2.5, "error": str(e)}


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range."""
    h = df["High"]
    l = df["Low"]
    c = df["Close"].shift(1)
    tr = pd.concat([h - l, (h - c).abs(), (l - c).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def fetch_multiple_tickers(symbols: List[str]) -> List[Dict[str, Any]]:
    """Fetch data for multiple tickers — gc.collect() after each to keep RAM low on Render."""
    import gc
    results = []
    for sym in symbols:
        print(f"  [DATA] Fetching {sym}...")
        data = fetch_ticker_data(sym)
        results.append(data)
        gc.collect()   # free DataFrames from previous ticker immediately
    return results


def _linear_regression_channel(daily: pd.DataFrame, period: int = 100) -> Dict[str, Any]:
    """100-period Linear Regression Channel with ±2 StdDev bands."""
    try:
        closes = daily["Close"].tail(period).values
        if len(closes) < period:
            return {"lower_2sd": 0, "upper_2sd": 0, "midline": 0, "at_lower": False}
        x = np.arange(len(closes))
        slope, intercept = np.polyfit(x, closes, 1)
        fitted = slope * x + intercept
        residuals = closes - fitted
        std = np.std(residuals)
        midline = float(fitted[-1])
        lower_2sd = round(midline - 2 * std, 2)
        upper_2sd = round(midline + 2 * std, 2)
        # slope as % change per bar relative to starting price
        slope_pct = round(slope / max(float(closes[0]), 0.01) * 100, 4)
        current = float(closes[-1])
        at_lower = current <= lower_2sd * 1.005  # within 0.5% of -2sd
        return {"lower_2sd": lower_2sd, "upper_2sd": upper_2sd, "midline": round(midline, 2),
                "slope_pct": slope_pct, "at_lower": at_lower}
    except Exception:
        return {"lower_2sd": 0, "upper_2sd": 0, "midline": 0, "at_lower": False}


def _fair_value_gaps(daily: pd.DataFrame, lookback: int = 50) -> List[Dict[str, float]]:
    """Find Fair Value Gaps (FVG) — bullish gaps where candle[i] high < candle[i+2] low."""
    fvgs = []
    data = daily.tail(lookback)
    if len(data) < 3:
        return fvgs
    highs = data["High"].values
    lows = data["Low"].values
    closes = data["Close"].values
    for i in range(len(data) - 2):
        # Bullish FVG: candle i high < candle i+2 low (gap up)
        if highs[i] < lows[i + 2]:
            fvgs.append({"top": round(float(lows[i + 2]), 2), "bottom": round(float(highs[i]), 2), "type": "bullish"})
        # Bearish FVG: candle i low > candle i+2 high (gap down)
        if lows[i] > highs[i + 2]:
            fvgs.append({"top": round(float(lows[i]), 2), "bottom": round(float(highs[i + 2]), 2), "type": "bearish"})
    # Keep only recent unfilled gaps near current price
    current = float(closes[-1])
    relevant = [g for g in fvgs if abs(g["top"] - current) / current < 0.05 or abs(g["bottom"] - current) / current < 0.05]
    return relevant[-6:]  # max 6 most recent


def _volume_profile_poc(daily: pd.DataFrame, lookback: int = 50) -> Dict[str, Any]:
    """Calculate Point of Control — price level with highest traded volume."""
    try:
        data = daily.tail(lookback)
        if len(data) < 10:
            return {"poc": 0, "high_vol_nodes": []}
        lows = data["Low"].values
        highs = data["High"].values
        volumes = data["Volume"].values
        # Create price bins
        price_min = float(np.min(lows))
        price_max = float(np.max(highs))
        num_bins = 50
        bins = np.linspace(price_min, price_max, num_bins + 1)
        vol_at_price = np.zeros(num_bins)
        for i in range(len(data)):
            lo, hi, vol = float(lows[i]), float(highs[i]), float(volumes[i])
            for b in range(num_bins):
                if bins[b + 1] >= lo and bins[b] <= hi:
                    overlap = min(hi, float(bins[b + 1])) - max(lo, float(bins[b]))
                    total_range = hi - lo if hi > lo else 1
                    vol_at_price[b] += vol * (overlap / total_range)
        poc_idx = np.argmax(vol_at_price)
        poc = round((float(bins[poc_idx]) + float(bins[poc_idx + 1])) / 2, 2)
        # High volume nodes (top 3 besides POC)
        sorted_idx = np.argsort(vol_at_price)[::-1]
        hvn = []
        for idx in sorted_idx[1:4]:
            hvn.append(round((float(bins[idx]) + float(bins[idx + 1])) / 2, 2))
        return {"poc": poc, "high_vol_nodes": hvn}
    except Exception:
        return {"poc": 0, "high_vol_nodes": []}


def _sustained_65m_check(hourly: pd.DataFrame, min_candles: int = 3) -> Dict[str, Any]:
    """Check if 65m (hourly) BULL trend sustained — uses EMA9 for faster response."""
    try:
        if hourly.empty or len(hourly) < 21:
            return {"sustained": False, "bull_candles": 0}
        ema9 = hourly["Close"].ewm(span=9).mean()
        # Check last N candles all above EMA9
        count = 0
        for i in range(1, min(len(hourly), 10) + 1):
            idx = -i
            if float(hourly["Close"].iloc[idx]) > float(ema9.iloc[idx]):
                count += 1
            else:
                break
        return {"sustained": count >= min_candles, "bull_candles": count}
    except Exception:
        return {"sustained": False, "bull_candles": 0}


def _coiling_check(daily: pd.DataFrame) -> Dict[str, Any]:
    """Check both 3-candle and 5-candle contraction patterns."""
    try:
        avg_rng10 = float(daily["High"].tail(10).sub(daily["Low"].tail(10)).mean())
        threshold = avg_rng10 * 0.5
        last5 = [float(daily["High"].iloc[-i] - daily["Low"].iloc[-i]) for i in range(1, 6)]
        coil3 = all(r < threshold for r in last5[:3])
        coil5 = all(r < threshold for r in last5)
        return {"coil3": coil3, "coil5": coil5, "tightest": "5-bar" if coil5 else "3-bar" if coil3 else "none"}
    except Exception:
        return {"coil3": False, "coil5": False, "tightest": "none"}


def _double_bottom_check(daily: pd.DataFrame, lookback: int = 60) -> Dict[str, Any]:
    """
    Detect double bottom pattern:
    - Two swing lows within 2% of each other
    - A neckline (swing high between them) at least 3% above the lows
    - Current price above neckline (confirmed breakout)
    """
    try:
        data = daily.tail(lookback)
        if len(data) < 20:
            return {"confirmed": False}

        lows  = data["Low"].values
        highs = data["High"].values
        closes = data["Close"].values
        current = float(closes[-1])

        # Find swing lows: lower than 2 bars on each side
        swing_lows = []
        for i in range(2, len(lows) - 2):
            if (lows[i] < lows[i-1] and lows[i] < lows[i-2] and
                    lows[i] < lows[i+1] and lows[i] < lows[i+2]):
                swing_lows.append((i, float(lows[i])))

        if len(swing_lows) < 2:
            return {"confirmed": False}

        # Test all pairs of swing lows
        for a in range(len(swing_lows) - 1):
            i, low1 = swing_lows[a]
            for b in range(a + 1, len(swing_lows)):
                j, low2 = swing_lows[b]
                # Lows within 2% of each other
                if abs(low1 - low2) / max(low1, 0.01) > 0.02:
                    continue
                # At least 5 bars between the two bottoms
                if j - i < 5:
                    continue
                # Neckline = highest high between the two lows
                neckline = float(np.max(highs[i:j + 1]))
                avg_low = (low1 + low2) / 2
                # Neckline must be at least 3% above lows
                if neckline < avg_low * 1.03:
                    continue
                # Breakout confirmed: price above neckline
                if current > neckline:
                    return {
                        "confirmed": True,
                        "low1": round(low1, 2),
                        "low2": round(low2, 2),
                        "neckline": round(neckline, 2),
                        "bars_between": j - i,
                    }

        return {"confirmed": False}
    except Exception:
        return {"confirmed": False}
