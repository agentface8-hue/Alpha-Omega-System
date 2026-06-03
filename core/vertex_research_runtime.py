"""
vertex_research_runtime.py - observer-only Vertex research shadow runtime.

Routes shadow tasks for AI Radar, Dreaming Agent, and model evals without
mutating portfolio, signals, or execution state. Paid Vertex calls happen
only when VERTEX_SHADOW_ENABLED=true and GCP project credentials are present.
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

SHADOW_LOG = Path(__file__).parent.parent / "signals" / "vertex_shadow_log.json"
MAX_LOG = 30
DEFAULT_VERTEX_MODEL = "gemini-2.0-flash"


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


def _env_true(name: str) -> bool:
    return _env(name).lower() in {"1", "true", "yes", "on"}


def _now() -> str:
    return datetime.datetime.utcnow().isoformat()


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


def status() -> Dict[str, Any]:
    enabled = _env_true("VERTEX_SHADOW_ENABLED") and bool(_env("GOOGLE_CLOUD_PROJECT"))
    sdk_available = False
    try:
        import vertexai  # noqa: F401

        sdk_available = True
    except Exception:
        sdk_available = False

    return {
        "provider": "vertex_research_runtime",
        "observer_only": True,
        "trading_mutation_allowed": False,
        "enabled": enabled,
        "external_calls_made": False,
        "trade_action": "none",
        "project": _env("GOOGLE_CLOUD_PROJECT") or None,
        "location": _env("VERTEX_LOCATION") or "us-central1",
        "model": _env("VERTEX_MODEL") or DEFAULT_VERTEX_MODEL,
        "sdk_available": sdk_available,
        "missing": [
            name
            for name, ok in (
                ("VERTEX_SHADOW_ENABLED", _env_true("VERTEX_SHADOW_ENABLED")),
                ("GOOGLE_CLOUD_PROJECT", bool(_env("GOOGLE_CLOUD_PROJECT"))),
            )
            if not ok
        ],
        "allowed_tasks": ["dream", "radar", "eval"],
        "uses_existing_modules": ["ai_radar", "dreaming_agent", "thinking_machines_benchmark"],
    }


def _vertex_generate(prompt: str) -> Dict[str, Any]:
    """Optional Vertex generation. Falls back to stub when SDK or auth is unavailable."""
    cfg = status()
    if not cfg["enabled"]:
        return {
            "ok": False,
            "provider": "vertex_disabled",
            "text": "",
            "error": "Vertex shadow disabled. Set VERTEX_SHADOW_ENABLED=true and GOOGLE_CLOUD_PROJECT.",
        }

    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel
    except Exception as e:
        return {
            "ok": False,
            "provider": "vertex_stub",
            "text": "Vertex SDK unavailable; shadow prompt prepared only.",
            "error": f"vertex SDK missing: {str(e)[:120]}",
        }

    try:
        vertexai.init(project=cfg["project"], location=cfg["location"])
        model = GenerativeModel(cfg["model"])
        response = model.generate_content(prompt)
        text = getattr(response, "text", "") or str(response)
        return {"ok": True, "provider": "vertex", "text": text[:4000], "error": None}
    except Exception as e:
        return {
            "ok": False,
            "provider": "vertex",
            "text": "",
            "error": str(e)[:180],
        }


def _shadow_dream(force: bool = False) -> Dict[str, Any]:
    from core.dreaming_agent import DREAM_WATCHLIST, _build_dream_prompt, _quick_scan_top_tickers

    try:
        from core.signal_tracker import _fetch_market_context

        market_ctx = _fetch_market_context()
    except Exception as e:
        market_ctx = {"regime": "Unknown", "error": str(e)[:120]}

    scan_results = _quick_scan_top_tickers(DREAM_WATCHLIST)
    prompt = _build_dream_prompt(market_ctx, scan_results)
    vertex = _vertex_generate(prompt)

    return {
        "task": "dream",
        "observer_only": True,
        "trade_action": "none",
        "saved_to_dream_log": False,
        "market_ctx": market_ctx,
        "scan_tickers": [r.get("ticker") for r in scan_results[:5]],
        "vertex": vertex,
        "prompt_chars": len(prompt),
        "force": force,
    }


def _shadow_radar(force: bool = False) -> Dict[str, Any]:
    from core.ai_radar import load_radar_log, run_radar_cycle

    if force:
        brief = run_radar_cycle(force=True)
    else:
        latest = load_radar_log(limit=1)
        brief = latest[0] if latest else run_radar_cycle(force=True)

    return {
        "task": "radar",
        "observer_only": True,
        "trade_action": "none",
        "reused_existing_radar": True,
        "brief": {
            "ts": brief.get("ts"),
            "count": brief.get("count"),
            "summary": brief.get("summary"),
            "source": brief.get("source"),
        },
    }


def _shadow_eval(symbols: Optional[List[str]] = None) -> Dict[str, Any]:
    from core.thinking_machines_benchmark import _baseline_alpha_omega

    syms = [s.upper() for s in (symbols or ["NVDA"])][:5]
    rows = []
    for symbol in syms:
        baseline = _baseline_alpha_omega(symbol)
        prompt = (
            "Observer-only Alpha-Omega model eval. Do not recommend execution.\n"
            f"Baseline for {symbol}: {baseline}\n"
            "Return agreement, missing risks, and eval verdict."
        )
        vertex = _vertex_generate(prompt)
        rows.append({"symbol": symbol, "baseline": baseline, "vertex": vertex})

    return {
        "task": "eval",
        "observer_only": True,
        "trade_action": "none",
        "symbols": syms,
        "results": rows,
    }


def run_shadow_task(task: str, *, force: bool = False, symbols: Optional[List[str]] = None) -> Dict[str, Any]:
    """Run one Vertex shadow task without touching trading core."""
    task = (task or "eval").strip().lower()
    cfg = status()

    if task == "dream":
        result = _shadow_dream(force=force)
    elif task == "radar":
        result = _shadow_radar(force=force)
    elif task == "eval":
        result = _shadow_eval(symbols=symbols)
    else:
        return {
            "observer_only": True,
            "trade_action": "none",
            "status": "error",
            "error": f"Unknown task '{task}'. Allowed: dream, radar, eval.",
        }

    result["enabled"] = cfg["enabled"]
    vertex_ok = False
    if task == "dream":
        vertex_ok = bool((result.get("vertex") or {}).get("ok"))
    elif task == "eval":
        vertex_ok = any((row.get("vertex") or {}).get("ok") for row in (result.get("results") or []))
    result["external_calls_made"] = bool(cfg["enabled"] and vertex_ok)
    result["status"] = "ok"
    _append_log({"ts": _now(), "task": task, "enabled": cfg["enabled"], "status": result["status"]})
    return result


def load_shadow_log(limit: int = 10) -> List[Dict[str, Any]]:
    if not SHADOW_LOG.exists():
        return []
    try:
        rows = json.loads(SHADOW_LOG.read_text(encoding="utf-8"))
    except Exception:
        return []
    return rows[:limit]
