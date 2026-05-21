"""
long_base_scanner.py — Weekly "Sleeping Giants" scanner.
Finds stocks in 1-3yr consolidation showing early breakout signals.

5 signals:
  1. SMA 150 flat (slope < 8% over 52w)
  2. Price compressed (ATR/price < 4%)
  3. Volume drying up (< 85% of prior year avg)
  4. SMA 150 curling up (slope turned +3% in last 8w)
  5. Volume explosion on breakout (recent 4w > 1.8x base avg)

Score 3+  = sleeping  (watchlist)
Score 4   = early     (enter now)
Score 5   = confirmed (move started)
"""
import datetime, logging
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)

_CACHE: dict = {"ts": 0, "data": None}
_CACHE_TTL = 86400 * 7  # 7 days


def _compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h, l, cp = df["High"], df["Low"], df["Close"].shift(1)
    tr = pd.concat([h - l, (h - cp).abs(), (l - cp).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def score_ticker(ticker: str) -> dict | None:
    try:
        df = yf.Ticker(ticker).history(period="3y", interval="1wk", timeout=10)
        if df is None or len(df) < 80:
            return None

        close  = df["Close"]
        volume = df["Volume"]
        sma150 = close.rolling(150).mean()
        atr14  = _compute_atr(df, 14)

        # Need enough history
        if sma150.dropna().empty or len(sma150.dropna()) < 60:
            return None

        price_now = round(float(close.iloc[-1]), 2)

        # Signal 1 — SMA 150 flat over past 52 weeks
        s1_val   = sma150.iloc[-1]
        s1_52w   = sma150.iloc[-52] if len(sma150) > 52 else sma150.iloc[0]
        sma_slope_1y = abs((s1_val - s1_52w) / s1_52w) if s1_52w else 1
        sig1 = sma_slope_1y < 0.08

        # Signal 2 — Low ATR (price compressed)
        atr_base   = float(atr14.iloc[-30:-4].mean()) if len(atr14) > 34 else 0
        atr_pct    = (atr_base / price_now) if price_now > 0 else 1
        sig2 = atr_pct < 0.04

        # Signal 3 — Volume drying up
        vol_recent_base = float(volume.iloc[-52:-4].mean()) if len(volume) > 56 else 0
        vol_prior_year  = float(volume.iloc[-104:-52].mean()) if len(volume) > 104 else vol_recent_base
        sig3 = (vol_recent_base < vol_prior_year * 0.85) if vol_prior_year > 0 else False

        # Signal 4 — SMA 150 curling up recently
        s4_now  = sma150.iloc[-1]
        s4_8w   = sma150.iloc[-8] if len(sma150) > 8 else sma150.iloc[0]
        sma_slope_8w = (s4_now - s4_8w) / s4_8w if s4_8w else 0
        sig4 = sma_slope_8w > 0.03

        # Signal 5 — Volume explosion
        vol_last_4w = float(volume.iloc[-4:].mean())
        sig5 = (vol_last_4w > vol_recent_base * 1.8) if vol_recent_base > 0 else False

        score  = sum([sig1, sig2, sig3, sig4, sig5])
        if score < 3:
            return None

        stage = "confirmed" if score == 5 else ("early" if score == 4 else "sleeping")

        return {
            "ticker":    ticker,
            "score":     score,
            "stage":     stage,
            "price":     price_now,
            "sma150":    round(float(s1_val), 2),
            "atr_pct":   round(atr_pct * 100, 2),
            "signals": {
                "sma_flat":     sig1,
                "compressed":   sig2,
                "vol_dry":      sig3,
                "curling":      sig4,
                "vol_explosion": sig5,
            },
            "scanned_at": datetime.datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.debug(f"[SLEEPER] {ticker} error: {e}")
        return None


def run_scan(universe: list = None) -> dict:
    global _CACHE
    import time

    # Serve cache if fresh
    if _CACHE["data"] and (time.time() - _CACHE["ts"]) < _CACHE_TTL:
        return {"results": _CACHE["data"], "from_cache": True,
                "cached_at": datetime.datetime.utcfromtimestamp(_CACHE["ts"]).isoformat()}

    if universe is None:
        # S&P 500 large caps — covers most WDC-type setups
        universe = [
            "AAPL","MSFT","NVDA","GOOGL","META","AMZN","TSLA","BRK.B","JPM","V",
            "UNH","XOM","JNJ","PG","MA","HD","CVX","MRK","ABBV","PEP","KO","COST",
            "WMT","BAC","LLY","AVGO","TMO","DHR","MCD","CSCO","ABT","NKE","ACN",
            "VZ","ADBE","NFLX","TXN","NEE","BMY","PM","RTX","HON","QCOM","AMGN",
            "IBM","GE","CAT","LOW","SPGI","BLK","SBUX","MDLZ","AXP","GS","MS",
            "DE","MMC","CB","ADP","ISRG","TGT","MO","DUK","SO","PLD","CCI","AMT",
            "SHW","ZTS","GILD","MMM","TJX","CVS","WM","ITW","ICE","USB","PNC",
            "ETN","EMR","APD","SYK","BSX","ELV","HCA","FIS","MCK","CME","AON",
            "LRCX","KLAC","MCHP","ANET","CDNS","SNPS","NXPI","WDC","MU","STX"
        ]

    results = []
    for ticker in universe:
        result = score_ticker(ticker)
        if result:
            results.append(result)

    results = sorted(results, key=lambda x: (x["score"], x["stage"] == "early"), reverse=True)

    _CACHE = {"ts": time.time(), "data": results}

    # Persist to Supabase if available
    try:
        from core.portfolio_store import _get_sb
        sb = _get_sb()
        if sb:
            sb.table("sleeping_giants").upsert({
                "id": "latest",
                "data": results,
                "updated_at": datetime.datetime.utcnow().isoformat()
            }).execute()
    except Exception as e:
        logger.debug(f"[SLEEPER] Supabase save skipped: {e}")

    return {"results": results, "from_cache": False,
            "scanned_at": datetime.datetime.utcnow().isoformat(),
            "universe_size": len(universe)}
