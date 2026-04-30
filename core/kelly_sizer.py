"""
kelly_sizer.py — Fractional Kelly position sizing for Printing Profits tab.
Pure math, no external dependencies. Imported by printing_scanner + printing_portfolio.
"""
from typing import Dict

STARTING_CAPITAL = 25_000.0


def kelly_size(conviction_pct: int, entry: float, sl: float,
               capital: float = STARTING_CAPITAL, direction: str = "long") -> Dict:
    """
    Scale risk by conviction using fractional Kelly tiers.

    85%+  → 2.0% risk  ($500 on $25K)
    75-84 → 1.5% risk  ($375)
    65-74 → 1.0% risk  ($250)
    <65   → skip (0 shares)
    """
    if conviction_pct >= 85:
        risk_pct = 0.020
    elif conviction_pct >= 75:
        risk_pct = 0.015
    elif conviction_pct >= 65:
        risk_pct = 0.010
    else:
        return {"shares": 0, "risk_usd": 0, "position_size": 0.0,
                "risk_pct": 0, "sl_dist": 0, "skip": True}

    risk_usd = round(capital * risk_pct, 2)

    # SL distance works for both long and short
    if direction == "short":
        sl_dist = max(sl - entry, 0.01)   # SL is above entry for shorts
    else:
        sl_dist = max(entry - sl, 0.01)   # SL is below entry for longs

    shares = max(1, int(risk_usd / sl_dist))

    # Cap position at 20% of capital
    max_shares = int(capital * 0.20 / entry)
    shares = min(shares, max_shares)
    shares = max(shares, 1)

    return {
        "shares": shares,
        "risk_usd": round(shares * sl_dist, 2),
        "risk_pct": round(risk_pct * 100, 1),
        "position_size": round(shares * entry, 2),
        "sl_dist": round(sl_dist, 4),
        "skip": False,
    }


def kelly_label(conviction_pct: int) -> str:
    if conviction_pct >= 85: return "FULL"
    if conviction_pct >= 75: return "3/4"
    if conviction_pct >= 65: return "1/2"
    return "SKIP"
