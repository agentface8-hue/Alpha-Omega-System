"""Execute AMA actions with timeouts."""
from __future__ import annotations

import gc
import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_ACTION_TIMEOUT = 30


@dataclass
class ActionResult:
    action: str
    success: bool
    detail: str
    duration_ms: int = 0
    side_effects: List[str] = field(default_factory=list)


def _run_timed(fn, timeout: int = _ACTION_TIMEOUT) -> Any:
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        return fut.result(timeout=timeout)


def gc_collect(snapshot: Dict = None) -> ActionResult:
    t0 = time.time()
    try:
        before = snapshot.get("memory_mb", 0) if snapshot else 0
        gc.collect()
        return ActionResult("gc_collect", True, f"GC run (was {before:.0f}MB)", int((time.time() - t0) * 1000), ["gc"])
    except Exception as e:
        return ActionResult("gc_collect", False, str(e)[:200], int((time.time() - t0) * 1000))


def alert_only(message: str, snapshot: Dict = None) -> ActionResult:
    t0 = time.time()
    try:
        from core.ama.report import send_alert
        send_alert(message)
        return ActionResult("alert_only", True, message[:200], int((time.time() - t0) * 1000), ["telegram"])
    except Exception as e:
        return ActionResult("alert_only", False, str(e)[:200], int((time.time() - t0) * 1000))


def check_portfolio_now(snapshot: Dict = None) -> ActionResult:
    t0 = time.time()
    try:
        def _do():
            from core.portfolio_manager import check_portfolio
            return check_portfolio()
        result = _run_timed(_do)
        from core.ama import memory as ama_memory
        from datetime import datetime, timezone
        ama_memory.set_state("last_portfolio_check_ts", datetime.now(timezone.utc).isoformat())
        n = len(result.get("portfolio", {}).get("open_positions", []))
        return ActionResult("check_portfolio_now", True, f"Checked {n} positions", int((time.time() - t0) * 1000))
    except FuturesTimeout:
        return ActionResult("check_portfolio_now", False, "timeout 30s", int((time.time() - t0) * 1000))
    except Exception as e:
        return ActionResult("check_portfolio_now", False, str(e)[:200], int((time.time() - t0) * 1000))


def run_health_fix(failed_checks: List[str] = None, snapshot: Dict = None) -> ActionResult:
    t0 = time.time()
    fixes = []
    try:
        if snapshot and snapshot.get("memory_pct", 0) > 85:
            gc.collect()
            fixes.append("gc")
        for name in (failed_checks or snapshot.get("failed_checks") or []):
            if "Finnhub" in name or "finnhub" in name.lower():
                time.sleep(2)
                fixes.append("finnhub_wait")
            if "Memory" in name or snapshot and snapshot.get("memory_pct", 0) > 80:
                gc.collect()
                fixes.append("memory_gc")
        def _recheck():
            from core.system_health import run_full_check
            return run_full_check(send_telegram=False)
        h = _run_timed(_recheck, 20)
        ok = h.get("overall") != "RED"
        return ActionResult(
            "run_health_fix", ok,
            f"fixes={fixes} overall={h.get('overall')}",
            int((time.time() - t0) * 1000),
        )
    except Exception as e:
        return ActionResult("run_health_fix", False, str(e)[:200], int((time.time() - t0) * 1000))


def refresh_signals(snapshot: Dict = None) -> ActionResult:
    t0 = time.time()
    try:
        def _do():
            from core.signal_tracker import check_signals
            return check_signals()
        r = _run_timed(_do)
        return ActionResult("refresh_signals", True, f"signals checked", int((time.time() - t0) * 1000))
    except Exception as e:
        return ActionResult("refresh_signals", False, str(e)[:200], int((time.time() - t0) * 1000))


def run_learning_fast(snapshot: Dict = None) -> ActionResult:
    t0 = time.time()
    try:
        def _do():
            from core.learning_loop import run_fast
            return run_fast()
        r = _run_timed(_do, 45)
        return ActionResult("run_learning_fast", r.get("status") == "ok", str(r.get("status")), int((time.time() - t0) * 1000))
    except Exception as e:
        return ActionResult("run_learning_fast", False, str(e)[:200], int((time.time() - t0) * 1000))


def run_morning_scan(snapshot: Dict = None) -> ActionResult:
    t0 = time.time()
    try:
        def _do():
            from core.momentum_screener import screen_universe
            top = screen_universe(top_n=5)
            from core.telegram_alerts import _send
            lines = ["🌅 <b>AMA Morning Scan</b>"] + [
                f"  {x.get('ticker')} score={x.get('score', 0):.2f}" for x in (top or [])[:5]
            ]
            _send("\n".join(lines))
            return top
        _run_timed(_do, 120)
        return ActionResult("run_morning_scan", True, "top 5 momentum sent", int((time.time() - t0) * 1000), ["telegram"])
    except Exception as e:
        return ActionResult("run_morning_scan", False, str(e)[:200], int((time.time() - t0) * 1000))


def run_eod_summary(snapshot: Dict = None) -> ActionResult:
    t0 = time.time()
    try:
        def _do():
            from core.portfolio_manager import get_portfolio
            pf = get_portfolio()
            stats = pf.get("stats", {})
            from core.telegram_alerts import _send
            msg = (
                f"📊 <b>AMA EOD Summary</b>\n"
                f"Open: {len(pf.get('open_positions', []))}\n"
                f"Total: ${stats.get('total_value', 0):,.0f}\n"
                f"P&L: {stats.get('total_pnl_pct', 0):+.2f}%"
            )
            _send(msg)
        _run_timed(_do, 30)
        return ActionResult("run_eod_summary", True, "EOD sent", int((time.time() - t0) * 1000), ["telegram"])
    except Exception as e:
        return ActionResult("run_eod_summary", False, str(e)[:200], int((time.time() - t0) * 1000))


def clear_cache(cache_name: str = "momentum", snapshot: Dict = None) -> ActionResult:
    t0 = time.time()
    try:
        from pathlib import Path
        base = Path(__file__).parent.parent.parent / "calibration"
        files = {
            "momentum": base / "momentum_screen_cache.json",
            "sector": base / "sector_rank_cache.json",
            "scan": base / "last_portfolio_scan.json",
        }
        p = files.get(cache_name)
        if p and p.exists():
            p.unlink()
        return ActionResult("clear_cache", True, f"cleared {cache_name}", int((time.time() - t0) * 1000))
    except Exception as e:
        return ActionResult("clear_cache", False, str(e)[:200], int((time.time() - t0) * 1000))


def escalate_to_llm(snapshot: Dict, context: str) -> ActionResult:
    t0 = time.time()
    try:
        from core.ama.decision_engine import call_llm_agent
        plan = call_llm_agent(snapshot, context)
        if plan.get("action"):
            return run_action(plan["action"], snapshot, plan.get("params", {}))
        return ActionResult("escalate_to_llm", True, plan.get("reasoning", "observe"), int((time.time() - t0) * 1000))
    except Exception as e:
        return ActionResult("escalate_to_llm", False, str(e)[:200], int((time.time() - t0) * 1000))


_ACTIONS = {
    "gc_collect": lambda s, p: gc_collect(s),
    "alert_only": lambda s, p: alert_only(p.get("message", "AMA alert"), s),
    "check_portfolio_now": lambda s, p: check_portfolio_now(s),
    "run_health_fix": lambda s, p: run_health_fix(p.get("failed_checks"), s),
    "refresh_signals": lambda s, p: refresh_signals(s),
    "run_learning_fast": lambda s, p: run_learning_fast(s),
    "run_morning_scan": lambda s, p: run_morning_scan(s),
    "run_eod_summary": lambda s, p: run_eod_summary(s),
    "clear_cache": lambda s, p: clear_cache(p.get("cache_name", "momentum"), s),
    "escalate_to_llm": lambda s, p: escalate_to_llm(s, p.get("context", "")),
}


def run_action(action_name: str, snapshot: Dict, params: Optional[Dict] = None) -> ActionResult:
    fn = _ACTIONS.get(action_name)
    if not fn:
        return ActionResult(action_name, False, "unknown action", 0)
    return fn(snapshot, params or {})
