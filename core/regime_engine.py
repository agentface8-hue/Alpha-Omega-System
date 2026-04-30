"""
regime_engine.py — Regime-aware strategy selector for Printing Profits tab.
Imports fetch_market_regime from market_data — zero duplication.
"""
from typing import Dict, Any


def get_strategy_mode(regime: Dict[str, Any]) -> Dict[str, Any]:
    """
    Given market regime dict (from fetch_market_regime), return
    optimal strategy configuration for the current environment.
    """
    vix = regime.get("vix", 20)

    if vix < 18:
        return {
            "mode": "BULL_MOMENTUM",
            "label": "Bull Momentum",
            "description": "Strong trend — swing long, hold 3-10 days",
            "long_enabled": True,
            "short_enabled": False,
            "scalp_enabled": False,
            "prime_strategy": "Swing Long",
            "expected_edge": "HIGH",
            "color": "#00ff88",
            "conviction_min": 65,
            "vix": vix,
        }
    elif vix < 25:
        return {
            "mode": "MIXED_TACTICAL",
            "label": "Mixed / Tactical",
            "description": "Choppy market — long + short + intraday",
            "long_enabled": True,
            "short_enabled": True,
            "scalp_enabled": True,
            "prime_strategy": "Long + Short",
            "expected_edge": "MEDIUM",
            "color": "#fbbf24",
            "conviction_min": 70,
            "vix": vix,
        }
    elif vix < 30:
        return {
            "mode": "BEAR_MOMENTUM",
            "label": "Bear Momentum",
            "description": "Trending bear — short momentum is the edge",
            "long_enabled": False,
            "short_enabled": True,
            "scalp_enabled": True,
            "prime_strategy": "Swing Short",
            "expected_edge": "HIGH",
            "color": "#ff4466",
            "conviction_min": 65,
            "vix": vix,
        }
    else:
        return {
            "mode": "HIGH_VOL_SCALP",
            "label": "High Vol Event",
            "description": "Extreme volatility — scalp both directions, half size",
            "long_enabled": True,
            "short_enabled": True,
            "scalp_enabled": True,
            "prime_strategy": "Scalp Both",
            "expected_edge": "SELECTIVE",
            "color": "#a855f7",
            "conviction_min": 75,
            "vix": vix,
        }
