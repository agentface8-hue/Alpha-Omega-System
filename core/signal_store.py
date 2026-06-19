"""
signal_store.py — Persistent signal storage with Supabase + JSON fallback.
Ensures signals survive Render redeploys.
"""
import os, json, datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

from core.storage_paths import signals_dir, use_supabase

logger = logging.getLogger(__name__)

SIGNALS_DIR = signals_dir()
SIGNALS_FILE = SIGNALS_DIR / "active_signals.json"
CLOSED_FILE = SIGNALS_DIR / "closed_signals.json"
REPORTS_DIR = SIGNALS_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# ── Supabase client (lazy init) ──
_sb = None
_sb_available = None  # None = not checked yet, True/False = checked
_startup_done = False  # Track one-time startup migration


def _startup_migrate_if_needed(sb):
    """On first successful Supabase connect: if Supabase is empty but local
    JSON has signals, migrate them automatically (one-time operation)."""
    global _startup_done
    if _startup_done:
        return
    _startup_done = True
    try:
        result = sb.table("signals").select("id").execute()
        sb_count = len(result.data)
        active = _load_json(SIGNALS_FILE)
        closed = _load_json(CLOSED_FILE)
        local_total = len(active) + len(closed)
        if sb_count == 0 and local_total > 0:
            logger.info(
                f"Supabase is empty -- migrating {len(active)} active + "
                f"{len(closed)} closed signals from local JSON"
            )
            migrated = 0
            for s in active + closed:
                if _sb_save_signal(s):
                    migrated += 1
            # Migrate case reports
            for f in sorted(REPORTS_DIR.glob("*.json")):
                try:
                    _sb_save_report(json.loads(f.read_text()))
                except Exception:
                    pass
            logger.info(f"One-time migration complete: {migrated}/{local_total} signals synced")
        else:
            logger.info(f"Supabase has {sb_count} signals -- no migration needed")
    except Exception as e:
        logger.warning(f"Startup migration check failed: {e}")


def _get_supabase():
    """Lazy-init Supabase client. Returns None if unavailable."""
    global _sb, _sb_available
    if not use_supabase():
        _sb_available = False
        return None
    if _sb_available is False:
        return None
    if _sb is not None:
        return _sb
    try:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_ANON_KEY", "")
        if not url or not key:
            _sb_available = False
            return None
        from supabase import create_client
        _sb = create_client(url, key)
        # Test connection by querying signals table
        _sb.table("signals").select("id").limit(1).execute()
        _sb_available = True
        logger.info("Supabase storage: CONNECTED")
        # Run one-time startup migration (JSON -> Supabase if Supabase is empty)
        _startup_migrate_if_needed(_sb)
        return _sb
    except Exception as e:
        logger.warning(f"Supabase unavailable: {e}. Using JSON fallback.")
        _sb_available = False
        _sb = None
        return None


# ══════════════════════════════════════════════════════════════
# JSON FILE I/O (local fallback)
# ══════════════════════════════════════════════════════════════

def _load_json(path: Path) -> List[Dict]:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            return []
    return []

def _save_json(path: Path, data: List[Dict]):
    path.write_text(json.dumps(data, indent=2, default=str))


# ══════════════════════════════════════════════════════════════
# SUPABASE I/O
# ══════════════════════════════════════════════════════════════

def _sb_load_signals(status_filter: str) -> Optional[List[Dict]]:
    """Load signals from Supabase. Returns None if unavailable."""
    sb = _get_supabase()
    if not sb:
        return None
    try:
        if status_filter == "active":
            result = sb.table("signals").select("data").neq("status", "closed").execute()
        else:
            result = sb.table("signals").select("data").eq("status", "closed").execute()
        return [row["data"] for row in result.data]
    except Exception as e:
        logger.error(f"Supabase load error: {e}")
        return None

def _sb_save_signal(signal: Dict):
    """Upsert a single signal to Supabase."""
    sb = _get_supabase()
    if not sb:
        return False
    try:
        is_closed = signal.get("status", "OPEN") not in ("OPEN",)
        row = {
            "id": signal["id"],
            "ticker": signal["ticker"],
            "status": "closed" if is_closed else "active",
            "asset_type": signal.get("asset_type", "stock"),
            "data": signal,
            "updated_at": datetime.datetime.utcnow().isoformat(),
        }
        if is_closed:
            row["closed_at"] = signal.get("closed_at", datetime.datetime.utcnow().isoformat())
        sb.table("signals").upsert(row).execute()
        return True
    except Exception as e:
        logger.error(f"Supabase save error: {e}")
        return False

def _sb_delete_signal(signal_id: str):
    """Delete a signal from Supabase."""
    sb = _get_supabase()
    if not sb:
        return False
    try:
        sb.table("signals").delete().eq("id", signal_id).execute()
        return True
    except Exception as e:
        logger.error(f"Supabase delete error: {e}")
        return False

def _sb_clear_all():
    """Clear all signals from Supabase."""
    sb = _get_supabase()
    if not sb:
        return False
    try:
        sb.table("signals").delete().neq("id", "").execute()
        sb.table("signal_reports").delete().neq("id", "").execute()
        return True
    except Exception as e:
        logger.error(f"Supabase clear error: {e}")
        return False

def _sb_save_report(report: Dict):
    """Save a case report to Supabase."""
    sb = _get_supabase()
    if not sb:
        return False
    try:
        row = {
            "id": f"{report.get('ticker', 'UNK')}_{report.get('signal_id', '')}",
            "signal_id": report.get("signal_id", ""),
            "ticker": report.get("ticker", ""),
            "data": report,
        }
        sb.table("signal_reports").upsert(row).execute()
        return True
    except Exception as e:
        logger.error(f"Supabase report save error: {e}")
        return False

def _sb_load_reports() -> Optional[List[Dict]]:
    """Load all case reports from Supabase."""
    sb = _get_supabase()
    if not sb:
        return None
    try:
        result = sb.table("signal_reports").select("data").execute()
        return [row["data"] for row in result.data]
    except Exception as e:
        logger.error(f"Supabase reports load error: {e}")
        return None

def _sb_load_report(signal_id: str) -> Optional[Dict]:
    """Load a single case report by signal_id."""
    sb = _get_supabase()
    if not sb:
        return None
    try:
        result = sb.table("signal_reports").select("data").eq("signal_id", signal_id).execute()
        if result.data:
            return result.data[0]["data"]
        return None
    except Exception as e:
        logger.error(f"Supabase report load error: {e}")
        return None


def _sb_append_action_log(signal_id: str, ticker: str, entry: Dict) -> bool:
    """Insert a single action entry into the action_log table.
    Silently skips if the table does not exist (optional analytics table)."""
    sb = _get_supabase()
    if not sb:
        return False
    try:
        sb.table("action_log").insert({
            "signal_id": signal_id,
            "ticker":    ticker,
            "entry":     entry,
        }).execute()
        return True
    except Exception as e:
        logger.debug(f"action_log insert skipped: {e}")
        return False


# ══════════════════════════════════════════════════════════════
# PUBLIC API — Supabase-first with JSON fallback
# ══════════════════════════════════════════════════════════════

def load_active() -> List[Dict]:
    """Load active signals. Tries Supabase first, falls back to JSON."""
    sb_data = _sb_load_signals("active")
    if sb_data is not None:
        # Also save to local JSON as cache
        _save_json(SIGNALS_FILE, sb_data)
        return sb_data
    return _load_json(SIGNALS_FILE)

def load_closed() -> List[Dict]:
    """Load closed signals. Tries Supabase first, falls back to JSON."""
    sb_data = _sb_load_signals("closed")
    if sb_data is not None:
        _save_json(CLOSED_FILE, sb_data)
        return sb_data
    return _load_json(CLOSED_FILE)

def save_active(signals: List[Dict]):
    """Save active signals to both Supabase and JSON."""
    # Always save JSON (fast, local cache)
    _save_json(SIGNALS_FILE, signals)
    # Sync each signal to Supabase
    sb = _get_supabase()
    if sb:
        try:
            # Get current Supabase active IDs
            result = sb.table("signals").select("id").eq("status", "active").execute()
            sb_ids = {r["id"] for r in result.data}
            local_ids = {s["id"] for s in signals}
            # Delete signals removed from active (they were closed or cleared)
            for old_id in sb_ids - local_ids:
                # Don't delete — they might have been moved to closed
                pass
            # Upsert all active signals
            for s in signals:
                _sb_save_signal(s)
        except Exception as e:
            logger.error(f"Supabase sync error: {e}")

def save_closed(signals: List[Dict]):
    """Save closed signals to both Supabase and JSON."""
    _save_json(CLOSED_FILE, signals)
    for s in signals:
        _sb_save_signal(s)

def save_single_signal(signal: Dict):
    """Save/update a single signal (used for frequent updates like price checks)."""
    _sb_save_signal(signal)
    # JSON is saved in bulk by the caller


def append_action_log(signal_id: str, ticker: str, entry: Dict):
    """Write a single action entry to the Supabase action_log table.
    Non-blocking: never raises, silently skips if table is absent."""
    try:
        _sb_append_action_log(signal_id, ticker, entry)
    except Exception:
        pass

def save_report(report: Dict):
    """Save a case report to both Supabase and local JSON."""
    # Local file
    ticker = report.get("ticker", "UNK")
    sig_id = report.get("signal_id", "unknown")
    status = report.get("exit", {}).get("status", "CLOSED")
    filename = f"{ticker}_{sig_id}_{status}.json"
    report_path = REPORTS_DIR / filename
    report_path.write_text(json.dumps(report, indent=2, default=str))
    # Supabase
    _sb_save_report(report)
    return filename

def load_report(signal_id: str) -> Optional[Dict]:
    """Load a case report by signal ID."""
    # Try Supabase first
    sb_report = _sb_load_report(signal_id)
    if sb_report:
        return sb_report
    # Fallback: scan local files
    for f in REPORTS_DIR.glob("*.json"):
        if signal_id in f.name:
            try:
                return json.loads(f.read_text())
            except:
                pass
    return None

def load_all_reports() -> List[Dict]:
    """Load all case reports."""
    sb_reports = _sb_load_reports()
    if sb_reports is not None:
        return sb_reports
    # Fallback: local files
    reports = []
    for f in sorted(REPORTS_DIR.glob("*.json")):
        try:
            reports.append(json.loads(f.read_text()))
        except:
            pass
    return reports

def clear_all():
    """Clear all signals and reports."""
    _save_json(SIGNALS_FILE, [])
    _save_json(CLOSED_FILE, [])
    _sb_clear_all()
    # Clear local reports
    for f in REPORTS_DIR.glob("*.json"):
        f.unlink()

def sync_local_to_supabase():
    """Push local JSON data to Supabase (run after tables are created)."""
    sb = _get_supabase()
    if not sb:
        return {"synced": False, "reason": "Supabase unavailable"}
    
    active = _load_json(SIGNALS_FILE)
    closed = _load_json(CLOSED_FILE)
    synced = 0
    
    for s in active:
        if _sb_save_signal(s):
            synced += 1
    for s in closed:
        if _sb_save_signal(s):
            synced += 1
    
    # Sync reports
    report_count = 0
    for f in REPORTS_DIR.glob("*.json"):
        try:
            report = json.loads(f.read_text())
            if _sb_save_report(report):
                report_count += 1
        except:
            pass
    
    return {
        "synced": True,
        "signals": synced,
        "reports": report_count,
        "total": synced + report_count
    }

def get_storage_status() -> Dict:
    """Check which storage backend is active."""
    sb = _get_supabase()
    return {
        "supabase": _sb_available or False,
        "json_fallback": True,
        "active_file": str(SIGNALS_FILE),
        "closed_file": str(CLOSED_FILE),
        "reports_dir": str(REPORTS_DIR),
    }
