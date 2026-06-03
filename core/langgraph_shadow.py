"""
langgraph_shadow.py - observer-only LangGraph research workflow shadow.

Reuses Alpha-Omega's existing market/regime/scoring stack inside a LangGraph
state machine for checkpoints and replay. Does not open trades or mutate
portfolio, signal, or Supabase state.
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, TypedDict

SHADOW_LOG = Path(__file__).parent.parent / "signals" / "langgraph_shadow_log.json"
MAX_LOG = 30

PROTECTED_MODULES = [
    "portfolio_manager",
    "signal_tracker",
    "order_executor",
    "trading_safety",
]


class ResearchState(TypedDict, total=False):
    symbol: str
    regime: Dict[str, Any]
    ticker: Dict[str, Any]
    score: Dict[str, Any]
    checkpoints: List[Dict[str, Any]]
    error: str


def _env_true(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _now() -> str:
    return datetime.datetime.utcnow().isoformat()


def _checkpoint(step: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"ts": _now(), "step": step, "payload": payload}


def _append_log(entry: Dict[str, Any]) -> None:
    rows: List[Dict[str, Any]] = []
    if SHADOW_LOG.exists():
        try:
            rows = json.loads(SHADOW_LOG.read_text(encoding="utf-8"))
        except Exception:
            rows = []
    rows.insert(0, entry)
    SHADOW_LOG.parent.mkdir(parents=True, exist_ok=True)
    SHADOW_LOG.write_text(json.dumps(rows[:MAX_LOG], indent=2), encoding="utf-8")


def _load_context(state: ResearchState) -> ResearchState:
    from core.market_data import fetch_market_regime, fetch_ticker_data

    symbol = (state.get("symbol") or "").upper()
    regime = fetch_market_regime()
    ticker = fetch_ticker_data(symbol)
    checkpoints = list(state.get("checkpoints") or [])
    checkpoints.append(_checkpoint("load_context", {"regime": regime, "ticker_ok": not ticker.get("error")}))
    if ticker.get("error"):
        return {
            **state,
            "symbol": symbol,
            "regime": regime,
            "ticker": ticker,
            "checkpoints": checkpoints,
            "error": str(ticker.get("error")),
        }
    return {**state, "symbol": symbol, "regime": regime, "ticker": ticker, "checkpoints": checkpoints}


def _score_ticker_node(state: ResearchState) -> ResearchState:
    from core.conviction_engine import score_ticker

    checkpoints = list(state.get("checkpoints") or [])
    if state.get("error"):
        checkpoints.append(_checkpoint("score_ticker", {"skipped": True, "reason": state["error"]}))
        return {**state, "checkpoints": checkpoints}

    scored = score_ticker(state["ticker"], state.get("regime") or {})
    checkpoints.append(
        _checkpoint(
            "score_ticker",
            {
                "decision": scored.get("decision") or scored.get("recommendation"),
                "confidence": scored.get("confidence") or scored.get("score"),
            },
        )
    )
    return {**state, "score": scored, "checkpoints": checkpoints}


def _invoke_research(state: ResearchState) -> ResearchState:
    try:
        from langgraph.graph import END, StateGraph

        graph = StateGraph(ResearchState)
        graph.add_node("load_context", _load_context)
        graph.add_node("score_ticker", _score_ticker_node)
        graph.set_entry_point("load_context")
        graph.add_edge("load_context", "score_ticker")
        graph.add_edge("score_ticker", END)
        return graph.compile().invoke(state)
    except ImportError:
        current = _load_context(state)
        return _score_ticker_node(current)


def status() -> Dict[str, Any]:
    enabled = _env_true("LANGGRAPH_SHADOW_ENABLED")
    langgraph_installed = True
    try:
        import langgraph  # noqa: F401
    except ImportError:
        langgraph_installed = False

    return {
        "provider": "langgraph_shadow",
        "observer_only": True,
        "trading_mutation_allowed": False,
        "enabled": enabled,
        "trade_action": "none",
        "langgraph_installed": langgraph_installed,
        "uses_existing_modules": ["market_data", "conviction_engine"],
        "blocked_modules": PROTECTED_MODULES,
    }


def run_shadow_research(symbol: str) -> Dict[str, Any]:
    """Run a read-only LangGraph research shadow for one symbol."""
    if not _env_true("LANGGRAPH_SHADOW_ENABLED"):
        return {
            "observer_only": True,
            "trade_action": "none",
            "enabled": False,
            "status": "disabled",
            "reason": "Set LANGGRAPH_SHADOW_ENABLED=true to run LangGraph shadow.",
        }

    sym = (symbol or "NVDA").upper()
    final_state = _invoke_research({"symbol": sym, "checkpoints": []})
    result = {
        "observer_only": True,
        "trade_action": "none",
        "enabled": True,
        "status": "ok" if not final_state.get("error") else "error",
        "symbol": sym,
        "regime": final_state.get("regime"),
        "score": final_state.get("score"),
        "checkpoints": final_state.get("checkpoints") or [],
        "error": final_state.get("error"),
    }
    _append_log({"ts": _now(), "symbol": sym, "status": result["status"], "checkpoints": len(result["checkpoints"])})
    return result


def load_shadow_log(limit: int = 10) -> List[Dict[str, Any]]:
    if not SHADOW_LOG.exists():
        return []
    try:
        rows = json.loads(SHADOW_LOG.read_text(encoding="utf-8"))
    except Exception:
        return []
    return rows[:limit]
