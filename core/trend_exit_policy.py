"""
trend_exit_policy.py — Shared exit and sector-concentration rules.

Widen trailing stops and HOT-sector caps in Trending Bull without loosening
global entry discipline.
"""
from __future__ import annotations

from typing import Optional, Tuple


def _sector_bias(sector: str) -> str:
    try:
        from core.calibrator import load_calibration
        return (load_calibration().get("sector_bias") or {}).get(sector or "Unknown", "NEUTRAL")
    except Exception:
        return "NEUTRAL"


def is_hot_trend(sector: str, regime: str) -> bool:
    return _sector_bias(sector) == "HOT" and (regime or "").startswith("Trending Bull")


def sector_cap_pct(sector: str, regime: str) -> float:
    return 40.0 if is_hot_trend(sector, regime) else 25.0


def max_sector_slots(portfolio_val: float, max_pos_size: float, sector: str, regime: str) -> int:
    cap_pct = sector_cap_pct(sector, regime) / 100.0
    pos_size = max_pos_size or 3340.0
    base = max(1, int(portfolio_val * cap_pct / pos_size))
    return base + (1 if is_hot_trend(sector, regime) else 0)


def portfolio_tsl_candidate(
    entry: float,
    atr: float,
    multiple: float,
    current_sl: float,
    tp1_hit: bool,
    sector: str,
    regime: str,
) -> Tuple[Optional[float], Optional[str]]:
    """Return (new_sl, note) when a trailing stop should ratchet up."""
    hot = is_hot_trend(sector, regime)
    bull = (regime or "").startswith("Trending Bull")

    if hot:
        tiers = [
            (2.5, entry + atr * 1.0, "TSL 2.5xATR -> entry+1xATR"),
            (2.0, entry + atr * 0.5, "TSL 2xATR -> entry+0.5xATR"),
        ]
        if tp1_hit:
            tiers.append((1.5, entry, "TSL 1.5xATR -> break-even after TP1"))
    elif bull:
        tiers = [
            (2.5, entry + atr * 1.0, "TSL 2.5xATR -> entry+1xATR"),
            (2.0, entry + atr * 0.5, "TSL 2xATR -> entry+0.5xATR"),
            (1.5, entry, "TSL 1.5xATR -> break-even"),
        ]
    else:
        tiers = [
            (2.0, entry + atr * 1.0, "TSL 2xATR -> entry+1xATR"),
            (1.5, entry + atr * 0.5, "TSL 1.5xATR -> entry+0.5xATR"),
            (1.25, entry, "TSL 1.25xATR -> break-even"),
        ]

    for threshold, sl, note in tiers:
        if multiple >= threshold:
            if sl > current_sl:
                return round(sl, 4), note
            return None, None
    return None, None


def fade_giveback_threshold(sector: str, regime: str, tp2_hit: bool = False) -> float:
    """Minimum MFE giveback % before momentum-fade auto-close."""
    if is_hot_trend(sector, regime):
        return 4.5 if tp2_hit else 999.0
    if (regime or "").startswith("Trending Bull"):
        return 3.5
    return 2.0


def signal_tsl_trigger_pct(regime: str) -> float:
    return 1.0 if (regime or "").startswith("Trending Bull") else 0.5


def signal_tsl_sl_mult(regime: str, sector: str, base_mult: float) -> float:
    if is_hot_trend(sector, regime) or (regime or "").startswith("Trending Bull"):
        return max(base_mult, 2.0)
    return base_mult
