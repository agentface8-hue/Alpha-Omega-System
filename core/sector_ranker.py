"""
sector_ranker.py — Rank GICS sectors by ETF momentum vs SPY.
One batch yfinance download (11 ETFs + SPY) → 5d + 20d relative return → ranked list.
Cache: 4 hours (refreshes automatically on next call after TTL).
"""
import json, time, datetime
from pathlib import Path
from typing import Dict, List

import yfinance as yf
import pandas as pd

CACHE_PATH = Path(__file__).parent.parent / "calibration" / "sector_rank_cache.json"
CACHE_TTL  = 3600 * 4  # 4 hours

SECTOR_ETFS: Dict[str, str] = {
    "Technology":             "XLK",
    "Financials":             "XLF",
    "Health Care":            "XLV",
    "Industrials":            "XLI",
    "Consumer Discretionary": "XLY",
    "Consumer Staples":       "XLP",
    "Energy":                 "XLE",
    "Communication Services": "XLC",
    "Utilities":              "XLU",
    "Materials":              "XLB",
    "Real Estate":            "XLRE",
}

# Maps GICS sector names → legacy sector_key used in ScanDashboard
SECTOR_KEY_MAP: Dict[str, str] = {
    "Technology":             "information_technology",
    "Financials":             "financials",
    "Health Care":            "health_care",
    "Industrials":            "industrials",
    "Consumer Discretionary": "consumer_discretionary",
    "Consumer Staples":       "consumer_staples",
    "Energy":                 "energy",
    "Communication Services": "communication_services",
    "Utilities":              "utilities",
    "Materials":              "materials",
    "Real Estate":            "real_estate",
}


def _pct_chg(series: "pd.Series", days: int) -> float:
    try:
        s = series.dropna()
        if len(s) < days + 1:
            return 0.0
        return float((s.iloc[-1] - s.iloc[-(days + 1)]) / s.iloc[-(days + 1)] * 100)
    except Exception:
        return 0.0


def rank_sectors(force: bool = False) -> List[Dict]:
    """
    Return list of sector dicts ranked by momentum score (best first).
    Each dict: sector, etf, sector_key, return_5d, return_20d,
               vs_spy_5d, vs_spy_20d, score, rank, leading, heat
    """
    if not force and CACHE_PATH.exists():
        try:
            cached = json.loads(CACHE_PATH.read_text())
            if time.time() - cached.get("ts", 0) < CACHE_TTL:
                return cached["rankings"]
        except Exception:
            pass

    etfs = list(SECTOR_ETFS.values()) + ["SPY"]
    try:
        raw = yf.download(etfs, period="35d", interval="1d",
                          progress=False, auto_adjust=True)
        # Handle both multi-index and single-index
        if isinstance(raw.columns, pd.MultiIndex):
            closes = raw["Close"]
        else:
            closes = raw
    except Exception as e:
        print(f"[SECTOR-RANK] Download failed: {e}")
        return _fallback()

    spy_5d  = _pct_chg(closes.get("SPY", pd.Series(dtype=float)), 5)
    spy_20d = _pct_chg(closes.get("SPY", pd.Series(dtype=float)), 20)

    rankings: List[Dict] = []
    for sector, etf in SECTOR_ETFS.items():
        col = closes.get(etf)
        if col is None or col.dropna().empty:
            continue
        r5  = _pct_chg(col, 5)
        r20 = _pct_chg(col, 20)
        rel5  = round(r5  - spy_5d,  2)
        rel20 = round(r20 - spy_20d, 2)
        score = round(rel5 * 0.6 + rel20 * 0.4, 3)
        rankings.append({
            "sector":      sector,
            "etf":         etf,
            "sector_key":  SECTOR_KEY_MAP.get(sector, sector.lower()),
            "return_5d":   round(r5,  2),
            "return_20d":  round(r20, 2),
            "vs_spy_5d":   rel5,
            "vs_spy_20d":  rel20,
            "score":       score,
            "leading":     score > 0,
            "heat":        "HOT" if score > 1.0 else "WARM" if score > -0.5 else "COLD",
        })

    rankings.sort(key=lambda x: x["score"], reverse=True)
    for i, r in enumerate(rankings):
        r["rank"] = i + 1

    payload = {
        "ts":        time.time(),
        "built_at":  datetime.datetime.utcnow().isoformat(),
        "spy_5d":    round(spy_5d, 2),
        "spy_20d":   round(spy_20d, 2),
        "rankings":  rankings,
    }
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(payload))
    top3 = ", ".join(r["sector"] for r in rankings[:3])
    print(f"[SECTOR-RANK] Top 3: {top3}")
    return rankings


def get_leading_sectors(top_n: int = 4) -> List[str]:
    """Return sector names (GICS) of top N leaders."""
    return [r["sector"] for r in rank_sectors()[:top_n]]


def get_scan_universe(total_slots: int = 40, top_sectors: int = 4) -> List[str]:
    """
    Build a scan list from the top N leading sectors.
    Slots allocated proportionally by score weight.
    Returns deduplicated list of tickers, leading sectors first.
    """
    from core.universe_builder import get_universe
    universe  = get_universe()
    rankings  = rank_sectors()[:top_sectors]
    if not rankings:
        return universe["all_tickers"][:total_slots]

    # Weight by score (floor at 0.1 so even laggards get a few slots)
    weights   = [max(r["score"] + 3.0, 0.5) for r in rankings]   # shift so all positive
    total_w   = sum(weights)

    result: List[str] = []
    seen:   set        = set()
    for r, w in zip(rankings, weights):
        alloc = max(4, round(total_slots * w / total_w))
        for t in universe["sectors"].get(r["sector"], [])[:alloc]:
            if t not in seen:
                seen.add(t)
                result.append(t)

    return result[:total_slots]


def _fallback() -> List[Dict]:
    return [
        {"sector": s, "etf": e, "sector_key": SECTOR_KEY_MAP.get(s, s.lower()),
         "return_5d": 0, "return_20d": 0, "vs_spy_5d": 0, "vs_spy_20d": 0,
         "score": 0, "leading": False, "heat": "WARM", "rank": i + 1}
        for i, (s, e) in enumerate(SECTOR_ETFS.items())
    ]
