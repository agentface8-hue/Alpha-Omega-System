"""Rule evaluation + optional LLM escalation."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.ama.memory import AgentMemory
from core.ama.rules import RULES, Rule

logger = logging.getLogger(__name__)

SONNET_MODEL = "claude-sonnet-4-6"
_MAX_ACTIONS_PER_HOUR = int(os.environ.get("AMA_MAX_ACTIONS_PER_HOUR", "12"))


@dataclass
class PlannedAction:
    name: str
    action: str
    trigger: str
    priority: int = 3
    telegram: bool = False
    message: str = ""
    params: Dict[str, Any] = field(default_factory=dict)


def _format_message(rule: Rule, snapshot: Dict) -> str:
    try:
        return rule.message.format(**snapshot)
    except Exception:
        return rule.message


def _actions_this_hour(memory: AgentMemory) -> int:
    from datetime import datetime, timezone, timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
    n = 0
    for a in memory.recent_actions:
        try:
            t = datetime.fromisoformat(a["ts"].replace("Z", "+00:00"))
            if t >= cutoff:
                n += 1
        except Exception:
            pass
    return n


def _should_escalate_to_llm(snapshot: Dict, fired: List[PlannedAction], memory: AgentMemory) -> bool:
    if fired:
        return False
    if snapshot.get("health_overall") == "YELLOW":
        memory.repeated_failures["health_yellow"] = memory.repeated_failures.get("health_yellow", 0) + 1
        if memory.repeated_failures["health_yellow"] >= 3:
            return True
    else:
        memory.repeated_failures["health_yellow"] = 0
    if len(snapshot.get("errors", [])) >= 3:
        return True
    try:
        dd = float(snapshot.get("portfolio_state", {}).get("max_drawdown") or 0)
        if dd > 5:
            return True
    except Exception:
        pass
    return False


def call_llm_agent(snapshot: Dict, context: str) -> Dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return {"action": "alert_only", "params": {"message": "AMA: no API key for LLM"}, "reasoning": "skipped"}
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    prompt = (
        f"Context: {context}\n\nSystem snapshot:\n"
        f"{json.dumps({k: snapshot.get(k) for k in ['health_overall', 'failed_checks', 'memory_pct', 'open_positions', 'market_open', 'regime']}, default=str)[:3000]}\n\n"
        "Choose ONE action from: alert_only, check_portfolio_now, run_health_fix, refresh_signals, "
        "run_learning_fast, gc_collect, clear_cache. Return JSON: "
        '{"action":"...","params":{},"reasoning":"..."}'
    )
    msg = client.messages.create(
        model=SONNET_MODEL,
        max_tokens=400,
        system="You are Alpha-Omega AMA. Conservative SRE. Prefer observe/alert over intervention.",
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def decide(snapshot: Dict, memory: AgentMemory) -> List[PlannedAction]:
    if memory.paused:
        return []
    if _actions_this_hour(memory) >= _MAX_ACTIONS_PER_HOUR:
        logger.warning("[AMA] Hourly action cap reached")
        return []

    planned: List[PlannedAction] = []
    for rule in sorted(RULES, key=lambda r: r.priority):
        if memory.on_cooldown(rule.action, rule.cooldown_minutes):
            continue
        try:
            if not rule.condition(snapshot):
                continue
        except Exception as e:
            logger.debug(f"[AMA] rule {rule.name} condition error: {e}")
            continue
        planned.append(PlannedAction(
            name=rule.name,
            action=rule.action,
            trigger=rule.name,
            priority=rule.priority,
            telegram=rule.telegram,
            message=_format_message(rule, snapshot),
            params={"message": _format_message(rule, snapshot),
                    "failed_checks": snapshot.get("failed_checks", [])},
        ))

    if not planned and _should_escalate_to_llm(snapshot, planned, memory):
        planned.append(PlannedAction(
            name="llm_escalation",
            action="escalate_to_llm",
            trigger="llm_agent",
            priority=5,
            telegram=True,
            message="LLM escalation",
            params={"context": "No rules matched; ambiguous system state"},
        ))

    planned.sort(key=lambda p: p.priority)
    return planned
