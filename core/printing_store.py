"""
printing_store.py — Isolated Supabase + JSON storage for Printing Profits tab.
Tables: printing_positions, printing_state  (separate from portfolio_* tables)
"""
import os, json, datetime, logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.storage_paths import signals_dir, use_supabase

logger = logging.getLogger(__name__)

STORE_DIR      = signals_dir()
POSITIONS_FILE = STORE_DIR / "printing_positions.json"
STATE_FILE     = STORE_DIR / "printing_state.json"

_DEFAULT_STATE = {
    "cash": 25000.0, "total_value": 25000.0,
    "starting_capital": 25000.0, "long_exposure": 0.0, "short_exposure": 0.0,
}

_sb = None; _sb_ok = None

def _get_sb():
    global _sb, _sb_ok
    if not use_supabase():
        _sb_ok = False
        return None
    if _sb_ok is False: return None
    if _sb is not None: return _sb
    try:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_ANON_KEY", "")
        if not url or not key: _sb_ok = False; return None
        from supabase import create_client
        _sb = create_client(url, key)
        _sb.table("printing_state").select("id").limit(1).execute()
        _sb_ok = True; return _sb
    except Exception as e:
        logger.warning(f"Printing Supabase unavailable: {e}")
        _sb_ok = False; _sb = None; return None

def _jload(path, default):
    if path.exists():
        try: return json.loads(path.read_text())
        except: pass
    return default

def _jsave(path, data):
    path.write_text(json.dumps(data, indent=2, default=str))

# ── State ─────────────────────────────────────────────────────────────────────
def load_state() -> Dict:
    sb = _get_sb()
    if sb:
        try:
            r = sb.table("printing_state").select("data").eq("id","main").execute()
            if r.data:
                s = r.data[0]["data"]; _jsave(STATE_FILE, s); return s
        except Exception as e: logger.error(f"Printing state load: {e}")
    return _jload(STATE_FILE, dict(_DEFAULT_STATE))

def save_state(state: Dict):
    state["updated_at"] = datetime.datetime.utcnow().isoformat()
    _jsave(STATE_FILE, state)
    sb = _get_sb()
    if sb:
        try: sb.table("printing_state").upsert({"id":"main","data":state}).execute()
        except Exception as e: logger.error(f"Printing state save: {e}")

def reset_state():
    save_state(dict(_DEFAULT_STATE))

# ── Positions ─────────────────────────────────────────────────────────────────
def load_positions(status: str = "all") -> List[Dict]:
    sb = _get_sb()
    if sb:
        try:
            q = sb.table("printing_positions").select("data")
            if status == "open":   q = q.in_("status", ["open","partial"])
            elif status == "closed": q = q.eq("status","closed")
            r = q.execute()
            positions = [row["data"] for row in r.data]
            if status == "all": _jsave(POSITIONS_FILE, positions)
            return positions
        except Exception as e: logger.error(f"Printing positions load: {e}")
    all_pos = _jload(POSITIONS_FILE, [])
    if status == "open":   return [p for p in all_pos if p.get("status") in ("open","partial")]
    if status == "closed": return [p for p in all_pos if p.get("status") == "closed"]
    return all_pos

def save_position(pos: Dict):
    pos["updated_at"] = datetime.datetime.utcnow().isoformat()
    all_pos = _jload(POSITIONS_FILE, [])
    idx = next((i for i, p in enumerate(all_pos) if p["id"] == pos["id"]), None)
    if idx is not None: all_pos[idx] = pos
    else: all_pos.append(pos)
    _jsave(POSITIONS_FILE, all_pos)
    sb = _get_sb()
    if sb:
        try:
            row = {"id": pos["id"], "ticker": pos["ticker"],
                   "status": pos["status"], "direction": pos.get("direction","long"),
                   "data": pos, "updated_at": pos["updated_at"]}
            if pos["status"] == "closed":
                row["closed_at"] = pos.get("closed_at", pos["updated_at"])
            sb.table("printing_positions").upsert(row).execute()
        except Exception as e: logger.error(f"Printing position save: {e}")

def clear_all():
    _jsave(POSITIONS_FILE, [])
    _jsave(STATE_FILE, dict(_DEFAULT_STATE))
    sb = _get_sb()
    if sb:
        try:
            sb.table("printing_positions").delete().neq("id","").execute()
            sb.table("printing_state").upsert({"id":"main","data":dict(_DEFAULT_STATE)}).execute()
        except Exception as e: logger.error(f"Printing clear: {e}")

def supabase_ready() -> bool:
    return _get_sb() is not None
