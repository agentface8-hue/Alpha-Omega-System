"""
portfolio_store.py — Persistent portfolio storage.
Supabase-first (survives Render redeploys), JSON fallback.
Tables required: portfolio_positions, portfolio_state
See docs/portfolio_migration.sql to create them.
"""
import os, json, datetime, logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

PORTFOLIO_DIR = Path(__file__).parent.parent / "signals"
PORTFOLIO_DIR.mkdir(exist_ok=True)
POSITIONS_FILE  = PORTFOLIO_DIR / "portfolio_positions.json"
STATE_FILE      = PORTFOLIO_DIR / "portfolio_state.json"

_DEFAULT_STATE = {
    "cash": 25000.0,
    "total_value": 25000.0,
    "starting_capital": 25000.0,
    "max_positions": 5,
    "max_position_size": 10000.0,
    "min_position_size": 5000.0,
    "max_risk_per_trade": 500.0,
    "split_tp1_pct": 50,
    "split_tp2_pct": 30,
    "split_tp3_pct": 20,
    "trailing_enabled": True,
}

_sb = None
_sb_ok = None


def _get_sb():
    global _sb, _sb_ok
    if _sb_ok is False:
        return None
    if _sb is not None:
        return _sb
    try:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_ANON_KEY", "")
        if not url or not key:
            _sb_ok = False
            return None
        from supabase import create_client
        _sb = create_client(url, key)
        _sb.table("portfolio_state").select("id").limit(1).execute()
        _sb_ok = True
        return _sb
    except Exception as e:
        logger.warning(f"Portfolio Supabase unavailable: {e}")
        _sb_ok = False
        _sb = None
        return None


# ── JSON helpers ──────────────────────────────────────────────
def _jload(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except:
            pass
    return default

def _jsave(path: Path, data):
    path.write_text(json.dumps(data, indent=2, default=str))


# ── State ─────────────────────────────────────────────────────
def load_state() -> Dict:
    sb = _get_sb()
    if sb:
        try:
            r = sb.table("portfolio_state").select("data").eq("id", "main").execute()
            if r.data:
                state = r.data[0]["data"]
                _jsave(STATE_FILE, state)
                return state
        except Exception as e:
            logger.error(f"State load error: {e}")
    return _jload(STATE_FILE, dict(_DEFAULT_STATE))

def save_state(state: Dict):
    state["updated_at"] = datetime.datetime.utcnow().isoformat()
    _jsave(STATE_FILE, state)
    sb = _get_sb()
    if sb:
        try:
            sb.table("portfolio_state").upsert({
                "id": "main",
                "data": state,
                "updated_at": state["updated_at"],
            }).execute()
        except Exception as e:
            logger.error(f"State save error: {e}")

def reset_state():
    save_state(dict(_DEFAULT_STATE))


# ── Positions ─────────────────────────────────────────────────
def load_positions(status: str = "all") -> List[Dict]:
    """Load positions. status = 'open'|'closed'|'all'"""
    sb = _get_sb()
    if sb:
        try:
            q = sb.table("portfolio_positions").select("data")
            if status == "open":
                q = q.in_("status", ["open", "partial"])
            elif status == "closed":
                q = q.eq("status", "closed")
            r = q.execute()
            positions = [row["data"] for row in r.data]
            if status == "all":
                _jsave(POSITIONS_FILE, positions)
            return positions
        except Exception as e:
            logger.error(f"Positions load error: {e}")
    all_pos = _jload(POSITIONS_FILE, [])
    if status == "open":
        return [p for p in all_pos if p.get("status") in ("open", "partial")]
    elif status == "closed":
        return [p for p in all_pos if p.get("status") == "closed"]
    return all_pos

def save_position(pos: Dict):
    pos["updated_at"] = datetime.datetime.utcnow().isoformat()
    # Update JSON cache
    all_pos = _jload(POSITIONS_FILE, [])
    idx = next((i for i, p in enumerate(all_pos) if p["id"] == pos["id"]), None)
    if idx is not None:
        all_pos[idx] = pos
    else:
        all_pos.append(pos)
    _jsave(POSITIONS_FILE, all_pos)
    # Supabase upsert
    sb = _get_sb()
    if sb:
        try:
            row = {
                "id": pos["id"],
                "ticker": pos["ticker"],
                "status": pos["status"],
                "asset_type": pos.get("asset_type", "stock"),
                "data": pos,
                "updated_at": pos["updated_at"],
            }
            if pos["status"] == "closed":
                row["closed_at"] = pos.get("closed_at", pos["updated_at"])
            sb.table("portfolio_positions").upsert(row).execute()
        except Exception as e:
            logger.error(f"Position save error: {e}")

def delete_position(position_id: str):
    all_pos = _jload(POSITIONS_FILE, [])
    _jsave(POSITIONS_FILE, [p for p in all_pos if p["id"] != position_id])
    sb = _get_sb()
    if sb:
        try:
            sb.table("portfolio_positions").delete().eq("id", position_id).execute()
        except Exception as e:
            logger.error(f"Position delete error: {e}")

def clear_all_positions():
    _jsave(POSITIONS_FILE, [])
    _jsave(STATE_FILE, dict(_DEFAULT_STATE))
    sb = _get_sb()
    if sb:
        try:
            sb.table("portfolio_positions").delete().neq("id", "").execute()
            sb.table("portfolio_state").upsert({
                "id": "main", "data": dict(_DEFAULT_STATE),
            }).execute()
        except Exception as e:
            logger.error(f"Clear error: {e}")

def supabase_ready() -> bool:
    return _get_sb() is not None
