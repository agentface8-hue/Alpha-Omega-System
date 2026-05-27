"""Hardcoded AMA rules — Layer 1 deterministic decisions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from core.ama import memory as ama_memory


@dataclass
class Rule:
    name: str
    condition: Callable[[Dict[str, Any]], bool]
    action: str
    priority: int = 3
    cooldown_minutes: int = 30
    telegram: bool = False
    message: str = ""


def _last_portfolio_check_age_min() -> float:
    ts = ama_memory.get_state("last_portfolio_check_ts")
    if not ts:
        return 9999.0
    from datetime import datetime, timezone
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - t).total_seconds() / 60
    except Exception:
        return 9999.0


def _last_learning_run_age_min() -> float:
    try:
        from core.learning_loop import _load_calibration
        p = _load_calibration()
        last = p.get("last_fast_run") or p.get("last_deep_run") or ""
        if not last:
            return 9999.0
        from datetime import datetime, timezone
        t = datetime.fromisoformat(last.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - t).total_seconds() / 60
    except Exception:
        return 9999.0


def _minutes_until_open() -> int:
    try:
        from core.signal_tracker import _is_us_market_open
        m = _is_us_market_open()
        if m.get("market_open"):
            return 0
        # Approximate: premarket within 15 min not available — use session hint
        return 30 if m.get("session") == "premarket" else 120
    except Exception:
        return 999


def _minutes_since_close() -> int:
    try:
        from core.signal_tracker import _is_us_market_open
        m = _is_us_market_open()
        if m.get("market_open"):
            return -1
        if m.get("session") == "afterhours":
            return 5
        return 60
    except Exception:
        return -1


RULES: List[Rule] = [
    Rule(
        name="memory_critical",
        condition=lambda s: s.get("memory_pct", 0) > 90,
        action="gc_collect",
        priority=1,
        cooldown_minutes=5,
        telegram=True,
        message="Memory {memory_mb:.0f}MB ({memory_pct:.0f}%) — forcing GC",
    ),
    Rule(
        name="supabase_down",
        condition=lambda s: not s.get("supabase_ok"),
        action="alert_only",
        priority=1,
        cooldown_minutes=60,
        telegram=True,
        message="Supabase unreachable — using JSON fallback if available",
    ),
    Rule(
        name="position_near_sl",
        condition=lambda s: len(s.get("positions_at_risk", [])) > 0,
        action="check_portfolio_now",
        priority=2,
        cooldown_minutes=10,
        telegram=True,
        message="Position near SL: {positions_at_risk}",
    ),
    Rule(
        name="portfolio_check_overdue",
        condition=lambda s: s.get("market_open") and _last_portfolio_check_age_min() > 35,
        action="check_portfolio_now",
        priority=2,
        cooldown_minutes=30,
        telegram=False,
        message="Portfolio check overdue — running now",
    ),
    Rule(
        name="health_red",
        condition=lambda s: s.get("health_overall") == "RED",
        action="run_health_fix",
        priority=2,
        cooldown_minutes=120,
        telegram=True,
        message="Health RED: {failed_checks}",
    ),
    Rule(
        name="stale_signals",
        condition=lambda s: len(s.get("stale_signals", [])) > 0,
        action="refresh_signals",
        priority=3,
        cooldown_minutes=30,
        telegram=False,
        message="Stale signals: {stale_signals}",
    ),
    Rule(
        name="learning_overdue",
        condition=lambda s: _last_learning_run_age_min() > 120,
        action="run_learning_fast",
        priority=4,
        cooldown_minutes=120,
        telegram=False,
        message="Learning loop overdue — running fast cycle",
    ),
    Rule(
        name="market_opens_soon",
        condition=lambda s: _minutes_until_open() in range(5, 16),
        action="run_morning_scan",
        priority=3,
        cooldown_minutes=1440,
        telegram=True,
        message="Market opens soon — running morning scan",
    ),
    Rule(
        name="market_closed_cleanup",
        condition=lambda s: not s.get("market_open") and _minutes_since_close() == 5,
        action="run_eod_summary",
        priority=3,
        cooldown_minutes=1440,
        telegram=True,
        message="Market closed — running EOD summary",
    ),
]
