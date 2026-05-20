"""
sector_ranker.py -- Rank GICS sectors by ETF momentum vs SPY.
Uses 3 ETFs per sector (SPDR + iShares + Vanguard) -- averaged for a more
reliable signal than any single fund. One batch yfinance download.
Cache: 4 hours.

SCORE FORMULA v2 (updated 2026-05-19 — council decision):
  score = 0.25 * rel5d + 0.75 * rel20d
  Rationale: 20-day trend captures structural megatrends (AI/Tech) better
  than 5-day noise. Council unanimous 4/5 on 25/75 split.
  Previous formula was 0.60 * rel5d + 0.40 * rel20d — over-penalized
  sectors with one bad week despite strong structural momentum.
"""
import json, time, datetime
from pathlib import Path
from typing import Dict, List, Tuple

import yfinance as yf
import pandas as pd

CACHE_PATH = Path(__file__).parent.parent / "calibration" / "sector_rank_cache.json"
CACHE_TTL  = 3600 * 4  # 4 hours

# 3 ETFs per sector: [SPDR, iShares, Vanguard]
SECTOR_ETFS: Dict[str, Tuple[str, str, str]] = {
    "Technology":             ("XLK",  "IGM",  "VGT"),
    "Financials":             ("XLF",  "IYF",  "VFH"),
    "Health Care":            ("XLV",  "IYH",  "VHT"),
    "Industrials":            ("XLI",  "IYJ",  "VIS"),
    "Consumer Discretionary": ("XLY",  "IYC",  "VCR"),
    "Consumer Staples":       ("XLP",  "IYK",  "VDC"),
    "Energy":                 ("XLE",  "IYE",  "VDE"),
    "Communication Services": ("XLC",  "IYZ",  "VOX"),
    "Utilities":              ("XLU",  "IDU",  "VPU"),
    "Materials":              ("XLB",  "IYM",  "VAW"),
    "Real Estate":            ("XLRE", "IYR",  "VNQ"),
}

# Maps GICS sector names to legacy sector_key used in ScanDashboard
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


def _pct_chg(series, days):
    try:
        s = series.dropna()
        if len(s) < days + 1:
            return 0.0
        return float((s.iloc[-1] - s.iloc[-(days + 1)]) / s.iloc[-(days + 1)] * 100)
    except Exception:
        return 0.0


def rank_sectors(force=False):
    if not force and CACHE_PATH.exists():
        try:
            cached = json.loads(CACHE_PATH.read_text())
            if time.time() - cached.get("ts", 0) < CACHE_TTL:
                return cached["rankings"]
        except Exception:
            pass

    # Collect all unique ETF tickers across all sectors + SPY
    all_etfs = ["SPY"]
    for trio in SECTOR_ETFS.values():
        all_etfs.extend(trio)
    all_etfs = list(dict.fromkeys(all_etfs))   # deduplicate, preserve order

    try:
        raw = yf.download(all_etfs, period="35d", interval="1d",
                          progress=False, auto_adjust=True)
        closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
    except Exception as e:
        print(f"[SECTOR-RANK] Download failed: {e}")
        return _fallback()

    spy_5d  = _pct_chg(closes.get("SPY", pd.Series(dtype=float)), 5)
    spy_20d = _pct_chg(closes.get("SPY", pd.Series(dtype=float)), 20)

    rankings = []
    for sector, (etf_spdr, etf_ishares, etf_vanguard) in SECTOR_ETFS.items():
        etf_returns = []
        for etf in (etf_spdr, etf_ishares, etf_vanguard):
            col = closes.get(etf)
            if col is not None and not col.dropna().empty:
                etf_returns.append((etf, _pct_chg(col, 5), _pct_chg(col, 20)))

        if not etf_returns:
            continue

        # Average across available ETFs
        avg_5d  = sum(r[1] for r in etf_returns) / len(etf_returns)
        avg_20d = sum(r[2] for r in etf_returns) / len(etf_returns)
        rel5    = round(avg_5d  - spy_5d,  2)
        rel20   = round(avg_20d - spy_20d, 2)

        # v2 formula: 25% short-term + 75% medium-term
        # Captures structural trends (AI megatrend) without ignoring recent momentum
        score = round(rel5 * 0.25 + rel20 * 0.75, 3)

        rankings.append({
            "sector":      sector,
            "etfs":        [e[0] for e in etf_returns],
            "etf":         etf_spdr,
            "sector_key":  SECTOR_KEY_MAP.get(sector, sector.lower()),
            "return_5d":   round(avg_5d,  2),
            "return_20d":  round(avg_20d, 2),
            "vs_spy_5d":   rel5,
            "vs_spy_20d":  rel20,
            "score":       score,
            "leading":     score > 0,
            "heat":        "HOT" if score > 1.0 else "WARM" if score > -0.5 else "COLD",
            "etf_detail":  [
                {"etf": e, "5d": round(r5, 2), "20d": round(r20, 2)}
                for e, r5, r20 in etf_returns
            ],
        })

    rankings.sort(key=lambda x: x["score"], reverse=True)
    for i, r in enumerate(rankings):
        r["rank"] = i + 1

    payload = {
        "ts":        time.time(),
        "built_at":  datetime.datetime.utcnow().isoformat(),
        "spy_5d":    round(spy_5d, 2),
        "spy_20d":   round(spy_20d, 2),
        "score_formula": "0.25 * rel5d + 0.75 * rel20d",
        "rankings":  rankings,
    }
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(payload))
    top3 = ", ".join(r["sector"] for r in rankings[:3])
    print(f"[SECTOR-RANK] Top 3: {top3}")
    return rankings


def get_leading_sectors(top_n=4):
    return [r["sector"] for r in rank_sectors()[:top_n]]


def get_scan_universe(total_slots=40, top_sectors=4):
    from core.universe_builder import get_universe
    universe  = get_universe()
    rankings  = rank_sectors()[:top_sectors]
    if not rankings:
        return universe["all_tickers"][:total_slots]

    weights   = [max(r["score"] + 3.0, 0.5) for r in rankings]
    total_w   = sum(weights)

    result = []
    seen   = set()
    for r, w in zip(rankings, weights):
        alloc = max(4, round(total_slots * w / total_w))
        for t in universe["sectors"].get(r["sector"], [])[:alloc]:
            if t not in seen:
                seen.add(t)
                result.append(t)

    return result[:total_slots]


def is_sector_allowed(sector_name: str, min_score: float = 0.0) -> bool:
    """Return True if sector momentum score is above min_score (default 0 = positive only)."""
    try:
        rankings = rank_sectors()
        match = next((r for r in rankings if r["sector"].lower() == sector_name.lower()), None)
        if not match:
            return True  # Unknown sector -- don't block
        return match["score"] > min_score
    except Exception:
        return True  # Fail open -- don't block on error


def get_ticker_sector_rank(ticker: str) -> dict:
    """Return sector name + rank + score + allowed for a ticker."""
    try:
        from core.universe_builder import get_ticker_sector
        sector = get_ticker_sector(ticker)
        rankings = rank_sectors()
        match = next((r for r in rankings if r["sector"].lower() == sector.lower()), None)
        if not match:
            return {"sector": sector, "rank": 99, "score": 0.0, "allowed": True}
        return {
            "sector":  match["sector"],
            "rank":    match["rank"],
            "score":   match["score"],
            "heat":    match["heat"],
            "allowed": match["score"] > 0.0,
        }
    except Exception:
        return {"sector": "Unknown", "rank": 99, "score": 0.0, "allowed": True}


def _fallback():
    return [
        {"sector": s, "etfs": list(etfs), "etf": etfs[0],
         "sector_key": SECTOR_KEY_MAP.get(s, s.lower()),
         "return_5d": 0, "return_20d": 0, "vs_spy_5d": 0, "vs_spy_20d": 0,
         "score": 0, "leading": False, "heat": "WARM", "rank": i + 1,
         "etf_detail": [{"etf": e, "5d": 0, "20d": 0} for e in etfs]}
        for i, (s, etfs) in enumerate(SECTOR_ETFS.items())
    ]
