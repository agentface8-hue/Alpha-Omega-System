"""
futures_data.py — Futures price, VWAP, and key-level fetcher.
Instruments: ES, NQ, RTY, CL, GC, SI
No duplication — uses yfinance directly (market_data.py only handles stocks).
"""
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Any
from datetime import datetime
import pytz

FUTURES_MAP = {
    "ES":  {"ticker": "ES=F",  "name": "E-mini S&P 500",    "category": "index",    "point_value": 50},
    "NQ":  {"ticker": "NQ=F",  "name": "E-mini Nasdaq-100",  "category": "index",    "point_value": 20},
    "RTY": {"ticker": "RTY=F", "name": "E-mini Russell 2000","category": "index",    "point_value": 50},
    "CL":  {"ticker": "CL=F",  "name": "Crude Oil",          "category": "commodity","point_value": 1000},
    "GC":  {"ticker": "GC=F",  "name": "Gold",               "category": "metal",    "point_value": 100},
    "SI":  {"ticker": "SI=F",  "name": "Silver",             "category": "metal",    "point_value": 5000},
}


def get_session_context() -> Dict[str, Any]:
    eastern = pytz.timezone("US/Eastern")
    now_et  = datetime.now(eastern)
    h = now_et.hour + now_et.minute / 60.0
    weekday = now_et.weekday()

    if weekday >= 5:
        return {"prime": False, "label": "Weekend", "et_time": now_et.strftime("%H:%M ET"), "color": "#4a6070"}
    if 9.5 <= h < 11.0:
        label, prime, color = "PRIME — Power Open (9:30-11AM ET)", True, "#00ff88"
    elif 15.0 <= h < 16.0:
        label, prime, color = "PRIME — Power Close (3-4PM ET)", True, "#00ff88"
    elif 9.5 <= h < 16.0:
        label, prime, color = "Regular Session", False, "#fbbf24"
    elif 4.0 <= h < 9.5:
        label, prime, color = "Pre-Market", False, "#94a3b8"
    elif 16.0 <= h < 20.0:
        label, prime, color = "After-Hours", False, "#94a3b8"
    else:
        label, prime, color = "Overnight Session", False, "#4a6070"

    return {"prime": prime, "label": label, "et_time": now_et.strftime("%H:%M ET"), "color": color}


def fetch_future(symbol: str) -> Dict[str, Any]:
    meta = FUTURES_MAP.get(symbol, {"ticker": symbol + "=F", "name": symbol,
                                    "category": "unknown", "point_value": 1})
    try:
        tk    = yf.Ticker(meta["ticker"])
        daily = tk.history(period="30d", interval="1d")
        hourly = tk.history(period="5d",  interval="1h")

        if daily.empty:
            return {"symbol": symbol, "error": "No data", **meta}

        close      = float(daily["Close"].iloc[-1])
        prev_close = float(daily["Close"].iloc[-2]) if len(daily) >= 2 else close
        chg_pct    = round((close - prev_close) / prev_close * 100, 2)

        # ATR-14
        h = daily["High"]; l = daily["Low"]; c = daily["Close"].shift(1)
        tr  = pd.concat([h - l, (h - c).abs(), (l - c).abs()], axis=1).max(axis=1)
        atr = round(float(tr.rolling(14).mean().iloc[-1]), 2)

        # Session VWAP from hourly
        vwap = None
        if not hourly.empty and len(hourly) >= 3:
            window = hourly.tail(8)
            tp     = (window["High"] + window["Low"] + window["Close"]) / 3
            cum_v  = window["Volume"].cumsum()
            cum_tv = (tp * window["Volume"]).cumsum()
            if float(cum_v.iloc[-1]) > 0:
                vwap = round(float(cum_tv.iloc[-1] / cum_v.iloc[-1]), 2)

        # EMA9/21 trend
        ema9  = float(daily["Close"].ewm(span=9).mean().iloc[-1])
        ema21 = float(daily["Close"].ewm(span=21).mean().iloc[-1])
        trend = "BULL" if close > ema9 and ema9 > ema21 else "BEAR"

        # Week high/low
        week_high = round(float(daily["High"].tail(5).max()), 2)
        week_low  = round(float(daily["Low"].tail(5).min()),  2)

        # ATR-based entry zones
        long_entry  = round(close - atr * 0.25, 2)
        long_sl     = round(close - atr * 1.5,  2)
        long_tp1    = round(close + atr * 2.0,  2)
        long_tp2    = round(close + atr * 3.5,  2)
        short_entry = round(close + atr * 0.25, 2)
        short_sl    = round(close + atr * 1.5,  2)
        short_tp1   = round(close - atr * 2.0,  2)
        short_tp2   = round(close - atr * 3.5,  2)

        rr_long  = round((long_tp1  - long_entry)  / max(long_entry  - long_sl,  0.01), 2)
        rr_short = round((short_entry - short_tp1) / max(short_sl - short_entry, 0.01), 2)

        return {
            "symbol":      symbol,
            "name":        meta["name"],
            "category":    meta["category"],
            "point_value": meta["point_value"],
            "price":       round(close, 2),
            "prev_close":  round(prev_close, 2),
            "change_pct":  chg_pct,
            "atr":         atr,
            "vwap":        vwap,
            "above_vwap":  (close > vwap) if vwap else None,
            "trend":       trend,
            "ema9":        round(ema9, 2),
            "ema21":       round(ema21, 2),
            "week_high":   week_high,
            "week_low":    week_low,
            "long_entry":  long_entry,  "long_sl":  long_sl,
            "long_tp1":    long_tp1,    "long_tp2": long_tp2,
            "short_entry": short_entry, "short_sl": short_sl,
            "short_tp1":   short_tp1,   "short_tp2": short_tp2,
            "rr_long":     rr_long,     "rr_short": rr_short,
            "tpt_ok":      max(rr_long, rr_short) >= 2.0,
        }
    except Exception as e:
        return {"symbol": symbol, "name": meta["name"], "error": str(e)}


def fetch_all_futures() -> Dict[str, Any]:
    session = get_session_context()
    futures = {sym: fetch_future(sym) for sym in FUTURES_MAP}
    return {"session": session, "futures": futures, "count": len(futures)}
