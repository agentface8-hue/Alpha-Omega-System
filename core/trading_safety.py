"""
trading_safety.py - centralized halt and live-mode guardrails.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Dict, Optional

SAFETY_FILE = Path(__file__).parent.parent / "signals" / "safety_state.json"
DEFAULT_STATE = {
    "global_halt": False,
    "halt_reason": "",
    "halted_symbols": {},
    "max_daily_realized_loss": 1000.0,
    "max_open_risk": 2500.0,
    "max_new_positions_per_day": 5,
    "live_mode_confirmed": False,
    "live_mode_confirmed_at": None,
    "updated_at": None,
}


def _now() -> str:
    return datetime.datetime.utcnow().isoformat()


def load_state() -> Dict[str, Any]:
    if SAFETY_FILE.exists():
        try:
            data = json.loads(SAFETY_FILE.read_text())
            return {**DEFAULT_STATE, **data}
        except Exception:
            pass
    return dict(DEFAULT_STATE)


def save_state(state: Dict[str, Any]) -> Dict[str, Any]:
    state = {**DEFAULT_STATE, **(state or {}), "updated_at": _now()}
    SAFETY_FILE.parent.mkdir(exist_ok=True)
    SAFETY_FILE.write_text(json.dumps(state, indent=2, default=str))
    return state


def status() -> Dict[str, Any]:
    state = load_state()
    state["is_halted"] = bool(state.get("global_halt") or state.get("halted_symbols"))
    return state


def halt_all(reason: str = "manual halt") -> Dict[str, Any]:
    state = load_state()
    state["global_halt"] = True
    state["halt_reason"] = reason or "manual halt"
    saved = save_state(state)
    _audit("safety_halt_all", "SYSTEM", "HALT_ALL", saved["halt_reason"])
    return saved


def resume() -> Dict[str, Any]:
    state = load_state()
    state["global_halt"] = False
    state["halt_reason"] = ""
    saved = save_state(state)
    _audit("safety_resume", "SYSTEM", "RESUME", "Trading resumed")
    return saved


def halt_symbol(ticker: str, reason: str = "manual symbol halt") -> Dict[str, Any]:
    state = load_state()
    sym = (ticker or "").upper()
    state.setdefault("halted_symbols", {})[sym] = {"reason": reason, "halted_at": _now()}
    saved = save_state(state)
    _audit("safety_halt_symbol", sym, "HALT_SYMBOL", reason)
    return saved


def confirm_live_mode(ack: str) -> Dict[str, Any]:
    if ack != "I ACKNOWLEDGE LIVE TRADING RISK":
        return {"ok": False, "error": "Typed acknowledgement required"}
    state = load_state()
    state["live_mode_confirmed"] = True
    state["live_mode_confirmed_at"] = _now()
    saved = save_state(state)
    _audit("safety_live_mode_confirmed", "SYSTEM", "CONFIRM_LIVE", "Live mode acknowledged")
    return {"ok": True, "state": saved}


def check_trade_allowed(
    *,
    ticker: str = "",
    mode: str = "paper",
    new_position: bool = True,
    open_risk: Optional[float] = None,
    daily_realized_pnl: Optional[float] = None,
    new_positions_today: Optional[int] = None,
) -> Dict[str, Any]:
    state = load_state()
    sym = (ticker or "").upper()
    if state.get("global_halt"):
        return _blocked("GLOBAL_HALT", state.get("halt_reason", "Trading halted"))
    halted = state.get("halted_symbols") or {}
    if sym and sym in halted:
        return _blocked("SYMBOL_HALT", halted[sym].get("reason", "Symbol halted"))
    if "live" in (mode or "").lower() and not state.get("live_mode_confirmed"):
        return _blocked("LIVE_MODE_NOT_CONFIRMED", "Type acknowledgement before live execution")
    if daily_realized_pnl is not None and daily_realized_pnl <= -abs(float(state.get("max_daily_realized_loss") or 0)):
        return _blocked("DAILY_LOSS_LIMIT", "Daily realized loss limit reached")
    if open_risk is not None and open_risk > float(state.get("max_open_risk") or 0):
        return _blocked("OPEN_RISK_LIMIT", "Open risk limit reached")
    if new_position and new_positions_today is not None and new_positions_today >= int(state.get("max_new_positions_per_day") or 0):
        return _blocked("NEW_POSITION_LIMIT", "Max new positions per day reached")
    return {"allowed": True, "reason": "allowed"}


def _blocked(code: str, reason: str) -> Dict[str, Any]:
    return {"allowed": False, "code": code, "reason": reason}


def _audit(event_type: str, symbol: str, action: str, verdict: str) -> None:
    try:
        from core.decision_audit import record_audit
        record_audit(
            event_type=event_type,
            symbol=symbol,
            source="trading_safety",
            action=action,
            status="safety",
            verdict=verdict,
            metadata=status(),
        )
    except Exception:
        pass
