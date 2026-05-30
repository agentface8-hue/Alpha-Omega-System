"""
daily_pipeline.py — Unifies Alpha-Omega features into one operational run.

Steps: health → regime → sectors → themes → dream → portfolio check → autopilot → learning → monitor
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _step(name: str, fn, timeout_note: str = "") -> Dict[str, Any]:
    t0 = time.time()
    try:
        out = fn()
        ms = int((time.time() - t0) * 1000)
        return {"name": name, "status": "ok", "ms": ms, "result": out}
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        logger.warning(f"[PIPELINE] {name} failed: {e}")
        return {"name": name, "status": "fail", "ms": ms, "error": str(e)[:300], "note": timeout_note}


def run_daily_pipeline(
    *,
    run_dream: bool = True,
    run_autopilot: bool = True,
    run_learning: bool = True,
    dream_force: bool = False,
) -> Dict[str, Any]:
    """Execute the full Alpha-Omega daily workflow."""
    started = datetime.now(timezone.utc).isoformat()
    steps: List[Dict[str, Any]] = []

    def health():
        return {"online": True}

    steps.append(_step("health", health))

    regime_data: Dict[str, Any] = {}

    def regime():
        nonlocal regime_data
        from core.market_data import fetch_market_regime
        regime_data = fetch_market_regime()
        from core.calibrator import get_regime_conviction_threshold
        rname = regime_data.get("regime", "Trending Bull")
        return {
            "regime": rname,
            "vix": regime_data.get("vix"),
            "conviction_threshold": get_regime_conviction_threshold(rname),
        }

    steps.append(_step("regime", regime))

    def sectors():
        from core.sector_ranker import rank_sectors
        ranked = rank_sectors()
        top = ranked[:3] if ranked else []
        bottom = ranked[-3:] if len(ranked) >= 3 else []
        return {"top": top, "bottom": bottom, "count": len(ranked)}

    steps.append(_step("sector_momentum", sectors))

    def themes():
        from core.theme_engine import refresh_themes, get_active_themes
        reg = refresh_themes(use_llm=False)
        active = get_active_themes()
        return {"active_ids": [t["id"] for t in active], "count": len(active)}

    steps.append(_step("theme_learning", themes, "sector+headline scan"))

    dream_result = None

    if run_dream:
        def dream():
            nonlocal dream_result
            from core.dreaming_agent import run_dream_cycle
            dream_result = run_dream_cycle(force=dream_force)
            return dream_result

        steps.append(_step("dream", dream, "Gemini/Claude quota"))

    def portfolio_check():
        from core.portfolio_manager import get_portfolio, check_portfolio
        pf = get_portfolio()
        open_n = pf.get("stats", {}).get("open_count", 0)
        chk = check_portfolio() if open_n else {"skipped": True, "reason": "no open positions"}
        return {"open_count": open_n, "check": chk}

    steps.append(_step("portfolio_check", portfolio_check, "price refresh can take up to 90s"))

    autopilot_result = None

    if run_autopilot:
        def autopilot():
            nonlocal autopilot_result
            from core.portfolio_manager import get_portfolio, autopilot_fill
            slots = get_portfolio().get("stats", {}).get("slots_available", 0)
            if slots <= 0:
                return {"skipped": True, "reason": "portfolio full"}
            autopilot_result = autopilot_fill("full_scan")
            return {
                "opened": len(autopilot_result.get("opened") or []),
                "message": autopilot_result.get("message"),
                "regime": autopilot_result.get("regime"),
            }

        steps.append(_step("portfolio_autopilot", autopilot, "scan+open up to 90s"))

    if run_learning:
        def learning():
            from core.learning_loop import _load_closed, run_fast
            from core.autoresearch import profit_readiness
            from core.outcomes_grader import backfill_ungraded_outcomes
            closed = _load_closed()
            backfill = backfill_ungraded_outcomes(limit=5)
            if len(closed) < 10:
                return {"skipped": True, "count": len(closed), "backfill": backfill}
            fast = run_fast(closed)
            ready = profit_readiness(closed)
            return {"fast": fast, "readiness": ready, "backfill": backfill}

        steps.append(_step("learning_fast", learning))

    def monitor():
        from core.live_monitor import CHECKS_L1, run_check, load_state, save_state, process_results
        state = load_state()
        ref = {"state": state}
        results = [run_check(n, f, c) for n, f, c in CHECKS_L1[:2]]
        process_results(results, ref["state"])
        save_state(ref["state"])
        return {"l1_sample": [{"name": r["name"], "status": r["status"]} for r in results]}

    steps.append(_step("monitor_l1", monitor))

    ok = sum(1 for s in steps if s["status"] == "ok")
    fail = sum(1 for s in steps if s["status"] == "fail")

    theme_step = next((s for s in steps if s.get("name") == "theme_learning" and s.get("status") == "ok"), None)
    active_themes = (theme_step or {}).get("result", {}).get("active_ids") or []

    summary = {
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "steps_ok": ok,
        "steps_fail": fail,
        "regime": regime_data.get("regime"),
        "active_themes": active_themes,
        "dream_edge": (dream_result or {}).get("edge_level") if dream_result else None,
        "dream_ticker": (dream_result or {}).get("top_ticker") if dream_result else None,
        "autopilot_opened": len((autopilot_result or {}).get("opened") or []) if autopilot_result else 0,
    }

    try:
        from core.telegram_alerts import _send
        lines = [
            f"🔄 <b>Alpha-Omega Pipeline</b>  {ok} ok / {fail} fail",
            f"Regime: {summary.get('regime', '?')}",
        ]
        if summary.get("dream_ticker"):
            lines.append(f"Dream: {summary['dream_edge']} → {summary['dream_ticker']}")
        if summary.get("autopilot_opened"):
            lines.append(f"Autopilot opened: {summary['autopilot_opened']}")
        if summary.get("active_themes"):
            lines.append(f"Themes: {', '.join(summary['active_themes'][:5])}")
        _send("\n".join(lines))
    except Exception:
        pass

    return {"status": "ok" if fail == 0 else "partial", "summary": summary, "steps": steps}
