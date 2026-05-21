"""
price_feed.py — Real-time price fetcher for Alpha-Omega.

Priority:
  1. Finnhub  — real-time, 60 calls/min free tier
  2. yfinance — fallback (15-20 min delayed on stocks)

Used by: portfolio_manager.py, printing_portfolio.py
"""
import os
import json
import time
import logging
import urllib.request
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

_FH_KEY  = os.environ.get("FINNHUB_API_KEY", "")
_FH_BASE = "https://finnhub.io/api/v1/quote"

# In-memory cache: {ticker: (price, timestamp)}
_price_cache: dict = {}
_CACHE_TTL = 60  # seconds


def get_price(ticker: str, asset_type: str = "stock") -> Optional[float]:
    """
    Fetch real-time price. Finnhub first, yfinance fallback.
    Returns None if both fail.
    """
    sym = ticker.upper()
    if asset_type == "crypto" and not sym.endswith("-USD"):
        sym = sym + "-USD"

    cached = _price_cache.get(sym)
    if cached and (time.time() - cached[1]) < _CACHE_TTL:
        return cached[0]

    price = _finnhub_price(sym, asset_type)

    if price is None:
        logger.warning(f"[PRICE] Finnhub failed for {sym}, falling back to yfinance")
        price = _yf_price(sym, asset_type)

    if price is not None:
        _price_cache[sym] = (price, time.time())

    return price


def get_prices_parallel(tickers: list, asset_type: str = "stock") -> dict:
    """
    Fetch prices for multiple tickers in parallel (max 5 workers).
    Returns {ticker: price_or_None}
    """
    results = {}
    with ThreadPoolExecutor(max_workers=5, thread_name_prefix="price_feed") as ex:
        futures = {ex.submit(get_price, t, asset_type): t for t in tickers}
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                results[ticker] = future.result(timeout=15)
            except Exception as e:
                logger.warning(f"[PRICE] {ticker} fetch error: {e}")
                results[ticker] = None
    return results


# -- Finnhub ------------------------------------------------------------------

def _finnhub_price(sym: str, asset_type: str) -> Optional[float]:
    """Fetch real-time price from Finnhub (60 calls/min free tier)."""
    try:
        if not _FH_KEY:
            return None

        if asset_type == "crypto":
            base   = sym.replace("-USD", "").replace("USDT", "")
            fh_sym = f"BINANCE:{base}USDT"
        else:
            fh_sym = sym

        url = f"{_FH_BASE}?symbol={fh_sym}&token={_FH_KEY}"
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read())

        price = data.get("c")  # current price
        if price and float(price) > 0:
            return round(float(price), 4)
        return None

    except Exception as e:
        logger.debug(f"[PRICE] Finnhub error for {sym}: {e}")
        return None


# -- yfinance fallback --------------------------------------------------------

def _yf_price(sym: str, asset_type: str) -> Optional[float]:
    """yfinance fallback — 15-20 min delayed for stocks."""
    try:
        import yfinance as yf
        import gc
        tk   = yf.Ticker(sym)
        data = tk.history(period="1d", interval="1m", timeout=6)
        if not data.empty:
            price = round(float(data["Close"].iloc[-1]), 4)
            del data; gc.collect()
            return price
        data = tk.history(period="2d", timeout=6)
        if not data.empty:
            price = round(float(data["Close"].iloc[-1]), 4)
            del data; gc.collect()
            return price
    except Exception as e:
        logger.debug(f"[PRICE] yfinance error for {sym}: {e}")
    return None
