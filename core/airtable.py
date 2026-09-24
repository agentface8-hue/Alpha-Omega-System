"""
airtable.py - Airtable trade logging for Alpha-Omega.
Replaces Google Sheets. Permanent API key, no OAuth, no expiry.
"""
import os, json, logging, urllib.request, urllib.error, datetime, time, threading
from typing import Dict, Optional

logger = logging.getLogger(__name__)

APIKEY   = os.environ.get("AIRTABLE_API_KEY", "")
BASE_ID  = os.environ.get("AIRTABLE_BASE_ID",  "appffQglWsLcswQMt")
TABLE_ID = os.environ.get("AIRTABLE_TABLE_ID", "tblN7UWpYuaSVJnMf")
BASE_URL = f"https://api.airtable.com/v0/{BASE_ID}/{TABLE_ID}"


def _hdrs():
    return {"Authorization": f"Bearer {APIKEY}", "Content-Type": "application/json"}


def log_trade(signal: Dict) -> Optional[str]:
    """Write a closed trade to Airtable. Returns record ID or None on failure."""
    try:
        entry  = float(signal.get("entry_price",  0) or 0)
        exit_p = float(signal.get("close_price",  0) or signal.get("current_price", 0) or 0)
        pnl    = float(signal.get("pnl_pct",      0) or 0)
        ctx    = signal.get("entry_market_context") or {}
        fields = {
            "Ticker":       signal.get("ticker", "?"),
            "Direction":    signal.get("direction", "LONG"),
            "Entry Price":  round(entry,  4),
            "Exit Price":   round(exit_p, 4),
            "PnL %":        round(pnl, 2),
            "Trade Status": signal.get("status", "CLOSED"),
            "Regime":       ctx.get("regime") or signal.get("regime", "Unknown"),
            "Session":      signal.get("entry_session", "unknown"),
            "Conviction":   round(float(signal.get("conviction", 0) or 0), 1),
            "Asset Type":   signal.get("asset_type", "stock").upper(),
            "SL":           round(float(signal.get("sl",  0) or 0), 4),
            "TP1":          round(float(signal.get("tp1", 0) or 0), 4),
            "MAE %":        round(float(signal.get("mae_pct", 0) or 0), 2),
            "MFE %":        round(float(signal.get("mfe_pct", 0) or 0), 2),
            "Close Reason": signal.get("close_reason", ""),
            "Opened At":    signal.get("created_at", ""),
            "Closed At":    signal.get("closed_at", datetime.datetime.utcnow().isoformat()),
            "Signal ID":    signal.get("id", ""),
        }
        body = json.dumps({"records": [{"fields": fields}]}).encode()
        req  = urllib.request.Request(BASE_URL, data=body, headers=_hdrs())
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read())
        rec_id = resp["records"][0]["id"]
        logger.info(f"[AIRTABLE] {fields['Ticker']} PnL={pnl:+.1f}% -> {rec_id}")
        return rec_id
    except Exception as e:
        logger.warning(f"[AIRTABLE] log_trade failed: {e}")
        return None


_health_cache = None
_health_cache_until = 0.0
_health_lock = threading.Lock()


def check_connection() -> Dict:
    """Read-only probe; cache results so dashboard refreshes do not consume writes."""
    global _health_cache, _health_cache_until
    with _health_lock:
        if _health_cache is not None and time.monotonic() < _health_cache_until:
            return dict(_health_cache)
        ttl = 300
        try:
            if not APIKEY:
                return {"status": "YELLOW", "detail": "AIRTABLE_API_KEY missing"}
            req = urllib.request.Request(f"{BASE_URL}?maxRecords=1&pageSize=1", headers=_hdrs())
            with urllib.request.urlopen(req, timeout=10) as r:
                json.loads(r.read())
            result = {"status": "GREEN", "detail": "Read access verified; write access not tested"}
        except urllib.error.HTTPError as e:
            ttl = 60
            if e.code == 429:
                try:
                    ttl = max(30, min(3600, int(e.headers.get('Retry-After', '60'))))
                except (ValueError, TypeError):
                    ttl = 60
                result = {"status": "YELLOW", "detail": f"Airtable rate/quota limit (429); retry after {ttl}s"}
            else:
                result = {"status": "YELLOW", "detail": f"Airtable HTTP {e.code}"}
        except Exception as e:
            ttl = 60
            result = {"status": "YELLOW", "detail": f"Airtable probe failed: {type(e).__name__}"}
        _health_cache = dict(result)
        _health_cache_until = time.monotonic() + ttl
        return result
