"""
market_flow_agent.py - additive institutional-flow interpretation.

Uses existing OHLCV-derived fields from market_data.py. It is observer/scoring
metadata only; it does not open trades or modify execution gates.
"""
from __future__ import annotations

from typing import Any, Dict


def _tas_num(tas: str) -> int:
    try:
        return int(str(tas).split("/")[0])
    except Exception:
        return 0


def analyze_flow_snapshot(data: Dict[str, Any]) -> Dict[str, Any]:
    symbol = (data.get("symbol") or data.get("ticker") or "?").upper()
    vol_ratio = float(data.get("vol_ratio") or 1.0)
    vol_direction = (data.get("vol_direction") or "NEUTRAL").upper()
    body_pct = float(data.get("body_pct") or 0)
    bull_body = bool(data.get("bull_body", False))
    tas = data.get("tas", "0/4")
    tas_num = _tas_num(tas)
    rsi = float(data.get("rsi") or 50)

    score = 50
    reasons = []

    if vol_ratio >= 2.0:
        score += 15
        reasons.append(f"high relative volume {vol_ratio:.2f}x")
    elif vol_ratio >= 1.3:
        score += 7
        reasons.append(f"above-average volume {vol_ratio:.2f}x")
    elif vol_ratio < 0.8:
        score -= 10
        reasons.append(f"thin volume {vol_ratio:.2f}x")

    if vol_direction == "ACCUMULATION":
        score += 20
        reasons.append("accumulation signature")
    elif vol_direction == "DISTRIBUTION":
        score -= 20
        reasons.append("distribution signature")

    if bull_body and body_pct >= 0.5:
        score += 8
        reasons.append("strong bullish candle body")
    elif not bull_body and body_pct >= 0.5:
        score -= 8
        reasons.append("strong bearish candle body")

    if tas_num >= 3:
        score += 8
        reasons.append(f"trend alignment TAS {tas}")
    elif tas_num <= 1:
        score -= 8
        reasons.append(f"weak trend alignment TAS {tas}")

    if rsi > 75:
        score -= 6
        reasons.append("RSI extended")
    elif 45 <= rsi <= 65:
        score += 4
        reasons.append("RSI in constructive zone")

    score = max(0, min(100, round(score)))
    if score >= 70:
        signal = "ACCUMULATION"
    elif score <= 40:
        signal = "DISTRIBUTION"
    else:
        signal = "NEUTRAL"

    confidence = "HIGH" if abs(score - 50) >= 25 else "MEDIUM" if abs(score - 50) >= 12 else "LOW"
    return {
        "symbol": symbol,
        "flow_score": score,
        "flow_signal": signal,
        "confidence": confidence,
        "vol_ratio": round(vol_ratio, 2),
        "vol_direction": vol_direction,
        "reasons": reasons[:6],
        "summary": f"Market_flow {signal.lower()} score {score}/100 for {symbol}: " + "; ".join(reasons[:3]),
    }


def analyze_ticker_flow(symbol: str) -> Dict[str, Any]:
    from core.market_data import fetch_ticker_data
    data = fetch_ticker_data(symbol.upper())
    if "error" in data:
        return {"symbol": symbol.upper(), "error": data["error"], "flow_score": 0, "flow_signal": "UNKNOWN"}
    return analyze_flow_snapshot(data)
