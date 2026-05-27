"""
Alpha-Omega Autonomous Management Agent (AMA) — main loop.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from core.ama.action_runner import ActionResult, run_action
from core.ama.decision_engine import PlannedAction, decide
from core.ama.memory import get_memory
from core.ama.observer import collect_snapshot
from core.ama.report import report_cycle, send_alert

logger = logging.getLogger(__name__)

CYCLE_INTERVAL_SECONDS = int(os.environ.get("AMA_CYCLE_INTERVAL", "300"))
MAX_ACTIONS_PER_CYCLE = 3


class AMAAgent:
    def __init__(self):
        self.cycle_number = 0
        self.running = False
        self._thread = None

    def start(self):
        if os.environ.get("AMA_ENABLED", "true").lower() in ("0", "false", "no"):
            logger.info("[AMA] Disabled via AMA_ENABLED")
            return
        if self._thread and self._thread.is_alive():
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, name="ama_agent", daemon=True)
        self._thread.start()
        logger.info(f"[AMA] Started — cycle every {CYCLE_INTERVAL_SECONDS}s")
        try:
            send_alert("🟢 AMA online — autonomous management active")
        except Exception:
            pass

    def _run_loop(self):
        time.sleep(90)  # warm-up after other services
        while self.running:
            try:
                self._run_cycle()
            except Exception as e:
                logger.error(f"[AMA] Cycle crash: {e}")
            time.sleep(CYCLE_INTERVAL_SECONDS)

    def _run_cycle(self) -> Dict[str, Any]:
        self.cycle_number += 1
        t0 = time.time()
        memory = get_memory()
        memory.last_cycle_ts = datetime.now(timezone.utc).isoformat()

        snapshot = collect_snapshot()
        actions: List[PlannedAction] = decide(snapshot, memory)
        actions = actions[:MAX_ACTIONS_PER_CYCLE]

        results: List[ActionResult] = []
        for plan in actions:
            params = dict(plan.params)
            if plan.action == "alert_only" and plan.message:
                params.setdefault("message", plan.message)
            result = run_action(plan.action, snapshot, params)
            results.append(result)
            memory.mark_action(plan.action)
            memory.record(plan.trigger, plan.action, result.success, result.detail, snapshot)
            if plan.telegram and result.success:
                send_alert(f"{plan.name}: {result.detail[:120]}")
            if not result.success:
                memory.fix_attempts[plan.action] = memory.fix_attempts.get(plan.action, 0) + 1

        if results:
            report_cycle(self.cycle_number, snapshot, results)
        memory.save()

        elapsed = int((time.time() - t0) * 1000)
        logger.info(f"[AMA] Cycle {self.cycle_number} {elapsed}ms — {len(results)} actions")
        return {
            "cycle": self.cycle_number,
            "actions": len(results),
            "results": [
                {"action": r.action, "success": r.success, "detail": r.detail, "duration_ms": r.duration_ms}
                for r in results
            ],
            "elapsed_ms": elapsed,
            "health": snapshot.get("health_overall"),
        }


_agent = AMAAgent()


def start():
    _agent.start()


def get_status() -> Dict[str, Any]:
    mem = get_memory()
    return {
        "running": _agent.running and (_agent._thread.is_alive() if _agent._thread else False),
        "cycle_number": _agent.cycle_number,
        "actions_today": mem.actions_today,
        "last_cycle": mem.last_cycle_ts,
        "paused": mem.paused,
        "interval_seconds": CYCLE_INTERVAL_SECONDS,
    }


def run_cycle_now() -> Dict[str, Any]:
    return _agent._run_cycle()


def pause():
    get_memory().paused = True
    get_memory().save()


def resume():
    get_memory().paused = False
    get_memory().save()
