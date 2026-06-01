"""
decision_audit.py - replay-grade audit records for Alpha-Omega decisions.

Supabase persistence uses the existing portfolio_state table as a compact
document store, so this works without a migration. JSON is always maintained as
a local fallback/cache.
"""
from __future__ import annotations

import datetime
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

AUDIT_DIR = Path(__file__).parent.parent / "signals" / "audit"
AUDIT_FILE = AUDIT_DIR / "decision_audit.json"
REMOTE_ID = "decision_audit_recent"
MAX_RECORDS = 250
MAX_STR = 1200
MAX_LIST = 40
MAX_DICT = 80
_REMOTE_DISABLED = False


def _now() -> str:
    return datetime.datetime.utcnow().isoformat()


def _sanitize(value: Any, depth: int = 0) -> Any:
    if depth > 5:
        return str(value)[:MAX_STR]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:MAX_STR]
    if isinstance(value, (list, tuple)):
        return [_sanitize(v, depth + 1) for v in list(value)[:MAX_LIST]]
    if isinstance(value, dict):
        out = {}
        for i, (k, v) in enumerate(value.items()):
            if i >= MAX_DICT:
                out["_truncated"] = True
                break
            out[str(k)[:120]] = _sanitize(v, depth + 1)
        return out
    return str(value)[:MAX_STR]


def _read_json() -> List[Dict[str, Any]]:
    if not AUDIT_FILE.exists():
        return []
    try:
        data = json.loads(AUDIT_FILE.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_json(records: List[Dict[str, Any]]) -> None:
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_FILE.write_text(json.dumps(records[:MAX_RECORDS], indent=2, default=str))


def _sb_client():
    if _REMOTE_DISABLED:
        return None
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


def _read_remote() -> Optional[List[Dict[str, Any]]]:
    sb = _sb_client()
    if not sb:
        return None
    try:
        res = sb.table("portfolio_state").select("data").eq("id", REMOTE_ID).execute()
        if res.data:
            rows = (res.data[0].get("data") or {}).get("records") or []
            return rows if isinstance(rows, list) else []
    except Exception:
        return None
    return []


def _write_remote(records: List[Dict[str, Any]]) -> None:
    sb = _sb_client()
    if not sb:
        return
    try:
        now = _now()
        sb.table("portfolio_state").upsert({
            "id": REMOTE_ID,
            "data": {"records": records[:MAX_RECORDS], "updated_at": now},
            "updated_at": now,
        }).execute()
    except Exception:
        pass


def _load_records() -> List[Dict[str, Any]]:
    remote = _read_remote()
    if remote is not None:
        _write_json(remote)
        return remote
    return _read_json()


def _save_records(records: List[Dict[str, Any]]) -> None:
    records = records[:MAX_RECORDS]
    _write_json(records)
    _write_remote(records)


def make_record(
    *,
    event_type: str,
    symbol: str = "",
    source: str = "",
    action: str = "",
    status: str = "recorded",
    verdict: str = "",
    confidence: Optional[float] = None,
    decision_id: Optional[Any] = None,
    inputs: Optional[Dict[str, Any]] = None,
    agent_outputs: Optional[Dict[str, Any]] = None,
    market_snapshot: Optional[Dict[str, Any]] = None,
    order: Optional[Dict[str, Any]] = None,
    outcome: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "ts": _now(),
        "event_type": event_type,
        "symbol": (symbol or "").upper(),
        "source": source,
        "action": action,
        "status": status,
        "verdict": verdict,
        "confidence": confidence,
        "decision_id": str(decision_id) if decision_id is not None else None,
        "inputs": _sanitize(inputs or {}),
        "agent_outputs": _sanitize(agent_outputs or {}),
        "market_snapshot": _sanitize(market_snapshot or {}),
        "order": _sanitize(order or {}),
        "outcome": _sanitize(outcome or {}),
        "metadata": _sanitize(metadata or {}),
    }


def record_audit(**kwargs) -> Dict[str, Any]:
    rec = make_record(**kwargs)
    records = _load_records()
    records = [rec] + [r for r in records if r.get("id") != rec["id"]]
    _save_records(records)
    return rec


def recent_audits(limit: int = 25) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 25), 100))
    return _load_records()[:limit]


def get_audit(audit_id: str) -> Optional[Dict[str, Any]]:
    for rec in _load_records():
        if rec.get("id") == audit_id or str(rec.get("decision_id")) == str(audit_id):
            return rec
    return None


def get_audits_for_symbol(symbol: str, limit: int = 25) -> List[Dict[str, Any]]:
    sym = (symbol or "").upper()
    rows = [r for r in _load_records() if r.get("symbol") == sym]
    return rows[:max(1, min(int(limit or 25), 100))]
