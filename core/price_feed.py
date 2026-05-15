"""
price_feed.py — Real-time price fetcher for Alpha-Omega.

Priority:
  1. Alpha Vantage  — real-time (no delay), used for all live trading decisions
  2. yfinance       — fallback only (15-20 min delayed on stocks)

Alpha Vantage free tier: 25 requests/day standard, but GLOBAL_QUOTE is generous.
For bulk checks use ThreadPoolExecutor (max 5 workers) to stay within rate limits.

Used by: portfolio_manager.py, signal_tracker.py, printing_portfolio.py
"""
import os
import json
import time
import logging
import urllib.request
import urllib.error
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

_AV_KEY = os.environ.get("ALPHA_VANTAGE_API_KEY", "KK4N32ZEFV5LUO8N")
_AV_BASE = "https://www.alphavantage.co/query"

# Simple in-memory cache: {ticker: (price, timestamp)}
_price_cache: dict = {}
_CACHE_TTL = 60  # seconds — reuse price if fetched within last 60s


def get_price(ticker: str, asset_type: str = "stock") -> Optional[float]:
    """
    Fetch real-time price. Alpha Vantage first, yfinance fallback.
    Returns None if both fail.
    """
    sym = ticker.upper()
    if asset_type == "crypto" and not sym.endswith("-USD"):
        sym = sym + "-USD"

    # Check cache first
    cached = _price_cache.get(sym)
    if cached and (time.time() - cached[1]) < _CACHE_TTL:
        return cached[0]

    # Try Alpha Vantage
    price = _av_price(sym, asset_type)

    # Fallback to yfinance if AV fails
    if price is None:
        logger.warning(f"[PRICE] AV failed for {sym}, falling back to yfinance")
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


# ── Alpha Vantage ─────────────────────────────────────────────────────────────

def _av_price(sym: str, asset_type: str) -> Optional[float]:
    """Fetch real-time price from Alpha Vantage GLOBAL_QUOTE."""
    try:
        if not _AV_KEY:
            return None

        # Crypto uses CURRENCY_EXCHANGE_RATE endpoint
        if asset_type == "crypto":
            base = sym.replace("-USD", "")
            url = (f"{_AV_BASE}?function=CURRENCY_EXCHANGE_RATE"
                   f"&from_currency={base}&to_currency=USD&apikey={_AV_KEY}")
            with urllib.request.urlopen(url, timeout=8) as r:
                data = json.loads(r.read())
            rate = data.get("Realtime Currency Exchange Rate", {}).get("5. Exchange Rate")
            if rate:
                return round(float(rate), 6)
            return None

        # Stocks / ETFs
        url = f"{_AV_BASE}?function=GLOBAL_QUOTE&symbol={sym}&apikey={_AV_KEY}"
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read())

        quote = data.get("Global Quote", {})
        price = quote.get("05. price")

        # Check for rate limit message
        if "Note" in data or "Information" in data:
            logger.warning(f"[PRICE] Alpha Vantage rate limited for {sym}")
            return None

        if price:
            return round(float(price), 4)
        return None

    except Exception as e:
        logger.debug(f"[PRICE] AV error for {sym}: {e}")
        return None


# ── yfinance fallback ─────────────────────────────────────────────────────────

def _yf_price(sym: str, asset_type: str) -> Optional[float]:
    """yfinance fallback — 15-20 min delayed for stocks."""
    try:
        import yfinance as yf
        import gc
        tk   = yf.Ticker(sym)
        data = tk.history(period="1d", interval="1m")
        if not data.empty:
            price = round(float(data["Close"].iloc[-1]), 4)
            del data; gc.collect()
            return price
        data = tk.history(period="2d")
        if not data.empty:
            price = round(float(data["Close"].iloc[-1]), 4)
            del data; gc.collect()
            return price
    except Exception as e:
        logger.debug(f"[PRICE] yfinance error for {sym}: {e}")
    return None
