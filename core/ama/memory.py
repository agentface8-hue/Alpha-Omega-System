"""AMA persistent memory — Supabase-first, JSON fallback."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA = Path(__file__).parent.parent.parent / "data"
_STATE_FILE = _DATA / "ama_state.json"
_LOG_FILE = _DATA / "ama_memory.json"
_MAX_LOG = 100


def _sb():
    try:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_ANON_KEY", "")
        if not url or not key:
            return None
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


def _load_json(path: Path, default: Any) -> Any:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return default


def _save_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))


class AgentMemory:
  def __init__(self):
    self.recent_actions: List[Dict] = []
    self.action_cooldowns: Dict[str, str] = {}
    self.repeated_failures: Dict[str, int] = {}
    self.fix_attempts: Dict[str, int] = {}
    self.session_start = datetime.now(timezone.utc).isoformat()
    self.actions_today = 0
    self.alerts_today = 0
    self.last_cycle_ts: Optional[str] = None
    self.paused = False
    self.what_worked: List[str] = []
    self.what_failed: List[str] = []
    self._load()

  def _load(self):
    state = _load_json(_STATE_FILE, {})
    self.action_cooldowns = state.get("action_cooldowns", {})
    self.repeated_failures = state.get("repeated_failures", {})
    self.fix_attempts = state.get("fix_attempts", {})
    self.actions_today = int(state.get("actions_today", 0))
    self.alerts_today = int(state.get("alerts_today", 0))
    self.last_cycle_ts = state.get("last_cycle_ts")
    self.paused = bool(state.get("paused", False))
    self.what_worked = state.get("what_worked", [])[-20:]
    self.what_failed = state.get("what_failed", [])[-20:]
    self.recent_actions = _load_json(_LOG_FILE, [])[-_MAX_LOG:]
    sb = _sb()
    if sb:
      try:
        r = sb.table("ama_state").select("value").eq("key", "agent").limit(1).execute()
        if r.data and isinstance(r.data[0].get("value"), dict):
          merged = r.data[0]["value"]
          self.action_cooldowns = merged.get("action_cooldowns", self.action_cooldowns)
          self.repeated_failures = merged.get("repeated_failures", self.repeated_failures)
          self.fix_attempts = merged.get("fix_attempts", self.fix_attempts)
          self.actions_today = int(merged.get("actions_today", self.actions_today))
          self.alerts_today = int(merged.get("alerts_today", self.alerts_today))
          self.last_cycle_ts = merged.get("last_cycle_ts", self.last_cycle_ts)
          self.paused = bool(merged.get("paused", self.paused))
      except Exception as e:
        logger.debug(f"[AMA] Supabase state load: {e}")

  def save(self):
    state = {
      "action_cooldowns": self.action_cooldowns,
      "repeated_failures": self.repeated_failures,
      "fix_attempts": self.fix_attempts,
      "actions_today": self.actions_today,
      "alerts_today": self.alerts_today,
      "last_cycle_ts": self.last_cycle_ts,
      "paused": self.paused,
      "what_worked": self.what_worked,
      "what_failed": self.what_failed,
      "session_start": self.session_start,
    }
    _save_json(_STATE_FILE, state)
    sb = _sb()
    if sb:
      try:
        sb.table("ama_state").upsert({"key": "agent", "value": state}).execute()
      except Exception as e:
        logger.debug(f"[AMA] Supabase state save: {e}")

  def on_cooldown(self, action_name: str, minutes: int) -> bool:
    last = self.action_cooldowns.get(action_name)
    if not last:
      return False
    try:
      t = datetime.fromisoformat(last.replace("Z", "+00:00"))
      return (datetime.now(timezone.utc) - t).total_seconds() < minutes * 60
    except Exception:
      return False

  def mark_action(self, action_name: str):
    self.action_cooldowns[action_name] = datetime.now(timezone.utc).isoformat()
    self.actions_today += 1

  def record(self, trigger: str, action: str, success: bool, detail: str, snapshot: Dict):
    entry = {
      "ts": datetime.now(timezone.utc).isoformat(),
      "action": action,
      "trigger": trigger,
      "success": success,
      "detail": detail[:500],
      "snapshot_summary": {
        "health": snapshot.get("health_overall"),
        "open": len(snapshot.get("open_positions", [])),
        "memory_pct": snapshot.get("memory_pct"),
      },
    }
    self.recent_actions.append(entry)
    self.recent_actions = self.recent_actions[-_MAX_LOG:]
    _save_json(_LOG_FILE, self.recent_actions)
    sb = _sb()
    if sb:
      try:
        sb.table("ama_memory").insert({
          "action": action,
          "trigger": trigger,
          "success": success,
          "detail": detail[:500],
          "snapshot_json": snapshot,
        }).execute()
      except Exception as e:
        logger.debug(f"[AMA] Supabase log insert: {e}")
    if success:
      if detail not in self.what_worked:
        self.what_worked.append(detail)
    else:
      if detail not in self.what_failed:
        self.what_failed.append(detail)
    self.save()


_memory: Optional[AgentMemory] = None


def get_memory() -> AgentMemory:
  global _memory
  if _memory is None:
    _memory = AgentMemory()
  return _memory


def get_state(key: str) -> Optional[str]:
  state = _load_json(_STATE_FILE, {})
  return state.get(key)


def set_state(key: str, value: str):
  state = _load_json(_STATE_FILE, {})
  state[key] = value
  _save_json(_STATE_FILE, state)


def get_history(limit: int = 50) -> List[Dict]:
  return get_memory().recent_actions[-limit:][::-1]


def clear_memory():
  global _memory
  _memory = AgentMemory()
  _save_json(_LOG_FILE, [])
  _memory.save()
