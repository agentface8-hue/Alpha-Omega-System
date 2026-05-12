"""
momentum_screener.py -- Fast price-momentum pre-screen across full >$10B universe.

Stage 1 of 2-stage pipeline:
  1. Download tickers in chunks of 50 (memory-safe for Render 512MB)
  2. Score each by: 5d return (50%) + 20d return (30%) + volume surge (20%)
  3. Apply sector bias multiplier from sector ranker (HOT=+15%, COLD=-10%)
  4. Return top N by adjusted score -- covers all sectors and all cap sizes fairly

Cache: 2 hours.
"""
import gc
import json
import time
import datetime
from pathlib import Path
from typing import List, Dict

import yfinance as yf
import pandas as pd

CACHE_PATH = Path(__file__).parent.parent / "calibration" / "momentum_screen_cache.json"
CACHE_TTL  = 3600 * 2   # 2 hours
CHUNK_SIZE = 50          # tickers per yfinance call — keeps RAM under 200MB per chunk


# Sector bias multipliers keyed by heat label
SECTOR_MULT = {"HOT": 1.15, "WARM": 1.0, "COLD": 0.90}


def _pct(series: pd.Series, days: int) -> float:
    try:
        s = series.dropna()
        if len(s) < days + 1:
            return 0.0
        return float((s.iloc[-1] - s.iloc[-(days + 1)]) / s.iloc[-(days + 1)] * 100)
    except Exception:
        return 0.0


def _vol_surge(vol: pd.Series) -> float:
    """Recent 5-day avg volume vs 20-day avg volume ratio."""
    try:
        v = vol.dropna()
        if len(v) < 20:
            return 1.0
        recent   = float(v.iloc[-5:].mean())
        baseline = float(v.iloc[-20:].mean())
        return round(recent / baseline, 3) if baseline > 0 else 1.0
    except Exception:
        return 1.0


def _score_chunk(chunk: List[str], closes: pd.DataFrame,
                 volumes: pd.DataFrame, sector_heat: Dict,
                 get_ticker_sector) -> List[Dict]:
    """Process one chunk of tickers into scored records."""
    records = []
    for ticker in chunk:
        try:
            if ticker not in closes.columns:
                continue
            close  = closes[ticker].dropna()
            volume = volumes[ticker].dropna() if ticker in volumes.columns else pd.Series(dtype=float)

            if len(close) < 6:
                continue

            mom5   = _pct(close, 5)
            mom20  = _pct(close, 20)
            vsurge = _vol_surge(volume)

            vol_bonus = 2.0 if vsurge >= 1.5 else (1.0 if vsurge >= 1.2 else 0.0)
            raw_score = mom5 * 0.5 + mom20 * 0.3 + vol_bonus * 0.2

            sector = get_ticker_sector(ticker)
            heat   = sector_heat.get(sector, "WARM")
            mult   = SECTOR_MULT.get(heat, 1.0)
            adj    = round(raw_score * mult, 4)

            records.append({
                "ticker":         ticker,
                "sector":         sector,
                "heat":           heat,
                "momentum_5d":    round(mom5,  2),
                "momentum_20d":   round(mom20, 2),
                "vol_surge":      vsurge,
                "raw_score":      round(raw_score, 4),
                "sector_mult":    mult,
                "adjusted_score": adj,
            })
        except Exception:
            continue
    return records


def screen_universe(top_n: int = 30, force: bool = False) -> List[Dict]:
    """
    Download all >$10B universe tickers in 50-ticker chunks,
    compute momentum score for each, return top_n sorted best first.
    """
    if not force and CACHE_PATH.exists():
        try:
            cached = json.loads(CACHE_PATH.read_text())
            if time.time() - cached.get("ts", 0) < CACHE_TTL:
                print(f"[MOMENTUM] Cache hit — {len(cached['results'])} stocks pre-screened")
                return cached["results"][:top_n]
        except Exception:
            pass

    from core.universe_builder import get_all_tickers, get_ticker_sector
    from core.sector_ranker import rank_sectors

    all_tickers = get_all_tickers()          # ~377 tickers
    rankings    = rank_sectors()
    sector_heat = {r["sector"]: r["heat"] for r in rankings}

    # Split into chunks to keep memory usage low
    chunks = [all_tickers[i:i + CHUNK_SIZE] for i in range(0, len(all_tickers), CHUNK_SIZE)]
    print(f"[MOMENTUM] Screening {len(all_tickers)} stocks in {len(chunks)} chunks of {CHUNK_SIZE}...")

    results = []
    failed_chunks = 0

    for i, chunk in enumerate(chunks):
        try:
            raw = yf.download(
                chunk, period="25d", interval="1d",
                progress=False, auto_adjust=True
            )

            if raw.empty:
                failed_chunks += 1
                continue

            # Extract Close / Volume — default MultiIndex is (field, ticker)
            if isinstance(raw.columns, pd.MultiIndex):
                closes  = raw["Close"]  if "Close"  in raw.columns.get_level_values(0) else pd.DataFrame()
                volumes = raw["Volume"] if "Volume" in raw.columns.get_level_values(0) else pd.DataFrame()
            else:
                closes  = raw[["Close"]]  if "Close"  in raw.columns else pd.DataFrame()
                volumes = raw[["Volume"]] if "Volume" in raw.columns else pd.DataFrame()

            if not closes.empty:
                chunk_results = _score_chunk(chunk, closes, volumes, sector_heat, get_ticker_sector)
                results.extend(chunk_results)

            # Free memory immediately after processing each chunk
            del raw, closes, volumes
            gc.collect()

        except Exception as e:
            print(f"[MOMENTUM] Chunk {i+1} failed: {e}")
            failed_chunks += 1
            gc.collect()
            continue

    if not results:
        print("[MOMENTUM] All chunks failed, using fallback")
        return _fallback(top_n)
    results.sort(key=lambda x: x["adjusted_score"], reverse=True)

    payload = {
        "ts":            time.time(),
        "built_at":      datetime.datetime.utcnow().isoformat(),
        "screened":      len(results),
        "chunks":        len(chunks),
        "failed_chunks": failed_chunks,
        "results":       results,
    }
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(payload))
    except Exception as ce:
        print("[MOMENTUM] Cache write failed: " + str(ce))

    top3 = ", ".join(r["ticker"] for r in results[:3])
    print("[MOMENTUM] Done: " + str(len(results)) + " stocks scored. Top 3: " + top3)
    return results[:top_n]


def get_momentum_scan_universe(top_n=30, force=False):
    """Return top_n ticker symbols ranked by momentum-adjusted score."""
    return [r["ticker"] for r in screen_universe(top_n=top_n, force=force)]


def _fallback(top_n):
    """If all chunks fail, fall back to sector-weighted list."""
    print("[MOMENTUM] Using fallback (sector-weighted by market cap order)")
    from core.sector_ranker import get_scan_universe
    from core.universe_builder import get_ticker_sector
    symbols = get_scan_universe(total_slots=top_n, top_sectors=4)
    return [
        {"ticker": t, "sector": get_ticker_sector(t), "heat": "WARM",
         "momentum_5d": 0, "momentum_20d": 0, "vol_surge": 1.0,
         "raw_score": 0, "sector_mult": 1.0, "adjusted_score": 0}
        for t in symbols[:top_n]
    ]
