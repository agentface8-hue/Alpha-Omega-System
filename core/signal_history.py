"""
signal_history.py — Historical trade store for learning loop seeding.

Reads from Supabase signal_history table (85 enriched trades).
Provides a unified signal list that merges history + live closed signals
so the learning loop always has enough data, even after a fresh deploy.
"""
import os
import json
import logging
import urllib.request
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

_SB_URL = os.environ.get("SUPABASE_URL", "")
_SB_KEY = os.environ.get("SUPABASE_ANON_KEY", "")


def load_history() -> List[Dict]:
    """Load all rows from signal_history table."""
    if not _SB_URL or not _SB_KEY:
        return []
    try:
        req = urllib.request.Request(
            f"{_SB_URL}/rest/v1/signal_history?select=*&limit=500&order=date_closed.asc",
            headers={"apikey": _SB_KEY, "Authorization": f"Bearer {_SB_KEY}"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            rows = json.loads(r.read())
        return rows or []
    except Exception as e:
        logger.warning(f"[HISTORY] load failed: {e}")
        return []


def to_learning_format(row: Dict) -> Dict:
    """
    Convert a signal_history row into the same shape that
    learning_loop expects from signal_store.load_closed().
    Only the fields used by the 5 learning dimensions are populated.
    """
    pnl = float(row.get("pnl_pct") or 0)
    return {
        # Core fields used by all 5 dimensions
        "ticker":          row.get("ticker", ""),
        "pnl_pct":         pnl,
        "realized_pnl":    pnl,           # alias used by conviction analysis
        "conviction":      float(row.get("conviction") or 0),
        "exit_reason":     row.get("exit_reason", ""),
        "regime":          row.get("regime", "Unknown"),
        "asset_type":      row.get("asset_type", "stock"),
        "mae_pct":         float(row.get("mae_pct") or 0),
        "mfe_pct":         float(row.get("mfe_pct") or 0),
        "source":          "signal_history",  # marks as historical

        # entry_market_context shape (for regime analysis)
        "entry_market_context": {"regime": row.get("regime", "Unknown")},

        # Sector (unknown from trade_log — leave as Unknown)
        "sector": "Unknown",

        # Advisor fields (not available in history)
        "advisor_verdict": "",

        # TAS + vol for extended analysis
        "tas_num":        row.get("tas_num"),
        "vol_ratio":      row.get("vol_ratio"),
        "vol_direction":  row.get("vol_direction", "NEUTRAL"),

        # Date
        "closed_at": row.get("date_closed", ""),
    }


def load_merged(live_closed: List[Dict]) -> List[Dict]:
    """
    Return history + live_closed, deduped by (ticker, closed_at).
    History records come first (older), live records last (newer).
    This gives the learning loop a full picture from day 1.
    """
    history_raw  = load_history()
    history_sigs = [to_learning_format(r) for r in history_raw]

    # Build dedup key set from live signals
    live_keys = set()
    for s in live_closed:
        closed_at = str(s.get("closed_at", ""))[:10]
        live_keys.add((s.get("ticker", ""), closed_at))

    # Only add history rows not already in live
    unique_history = []
    for h in history_sigs:
        key = (h.get("ticker", ""), str(h.get("closed_at", ""))[:10])
        if key not in live_keys:
            unique_history.append(h)

    merged = unique_history + live_closed
    logger.info(f"[HISTORY] merged {len(unique_history)} history + {len(live_closed)} live = {len(merged)} total")
    return merged
