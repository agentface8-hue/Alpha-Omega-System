"""
signal_history.py — Historical trade store for learning loop seeding.

Uses the existing trade_log Supabase table (85 rows, no new table needed).
The trade_log already has: ticker, pnl_pct, conviction, regime,
exit_reason, mae_pct, mfe_pct — enough for all 5 learning dimensions.

TAS/vol data from local enriched_trades.json is merged in when available
(on the dev laptop). On Render those fields are simply left null — the
learning loop gracefully handles missing values.
"""
import os
import json
import logging
import urllib.request
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)

_SB_URL = os.environ.get("SUPABASE_URL", "")
_SB_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

# Optional enrichment from local JSON (dev only)
_ENRICHED_PATH = Path(__file__).parent.parent / "data" / "enriched_trades.json"


def _load_enriched_index() -> Dict:
    """Build (ticker, date) → enriched data index from local JSON if available."""
    if not _ENRICHED_PATH.exists():
        return {}
    try:
        rows = json.loads(_ENRICHED_PATH.read_text())
        idx  = {}
        for r in rows:
            key = (str(r.get("ticker","")).upper(),
                   str(r.get("date_closed", r.get("date", "")))[:10])
            idx[key] = r
        return idx
    except Exception:
        return {}


def load_history() -> List[Dict]:
    """Load all rows from trade_log table."""
    if not _SB_URL or not _SB_KEY:
        return []
    try:
        req = urllib.request.Request(
            f"{_SB_URL}/rest/v1/trade_log?select=*&limit=500&order=date_closed.asc",
            headers={"apikey": _SB_KEY, "Authorization": f"Bearer {_SB_KEY}"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            rows = json.loads(r.read())
        logger.info(f"[HISTORY] loaded {len(rows)} rows from trade_log")
        return rows or []
    except Exception as e:
        logger.warning(f"[HISTORY] trade_log load failed: {e}")
        return []


def to_learning_format(row: Dict, enriched: Dict = None) -> Dict:
    """
    Convert a trade_log row into the shape learning_loop expects.
    Merges TAS/vol from enriched index when available.
    """
    pnl = float(row.get("pnl_pct") or 0)
    e   = enriched or {}
    return {
        "ticker":               row.get("ticker", ""),
        "pnl_pct":              pnl,
        "realized_pnl":         pnl,
        "conviction":           float(row.get("conviction") or 0),
        "exit_reason":          row.get("exit_reason", ""),
        "regime":               row.get("regime", "Unknown"),
        "asset_type":           row.get("asset_type", "stock"),
        "mae_pct":              float(row.get("mae_pct") or 0),
        "mfe_pct":              float(row.get("mfe_pct") or 0),
        "source":               "trade_log",
        "entry_market_context": {"regime": row.get("regime", "Unknown")},
        "sector":               "Unknown",
        "advisor_verdict":      "",
        "closed_at":            row.get("date_closed", ""),
        # Enriched TAS/vol (from local JSON, None on Render)
        "tas_num":              e.get("tas_num"),
        "vol_ratio":            e.get("vol_ratio"),
        "vol_direction":        e.get("vol_dir", e.get("vol_direction", "NEUTRAL")),
    }


def load_merged(live_closed: List[Dict]) -> List[Dict]:
    """
    Merge trade_log history + live closed signals.
    History comes first (older), live signals last (newer).
    Deduplicates by (ticker, closed_at date).
    """
    history_raw  = load_history()
    enriched_idx = _load_enriched_index()

    # Build dedup key set from live signals
    live_keys = set()
    for s in live_closed:
        key = (str(s.get("ticker","")).upper(),
               str(s.get("closed_at",""))[:10])
        live_keys.add(key)

    unique_history = []
    for row in history_raw:
        ticker     = str(row.get("ticker","")).upper()
        date_closed= str(row.get("date_closed",""))[:10]
        key        = (ticker, date_closed)
        if key not in live_keys:
            enriched = enriched_idx.get(key)
            unique_history.append(to_learning_format(row, enriched))

    merged = unique_history + live_closed
    logger.info(f"[HISTORY] merged {len(unique_history)} history + "
                f"{len(live_closed)} live = {len(merged)} total")
    return merged
