"""
observer.py — Collect full system snapshot for AMA cycles.
Never raises; errors are captured in snapshot.errors.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

RENDER_LIMIT_MB = 2048


def collect_snapshot() -> Dict[str, Any]:
    t0 = time.time()
    snap: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "errors": [],
        "health_checks": {},
        "health_overall": "UNKNOWN",
        "open_positions": [],
        "portfolio_state": {},
        "positions_at_risk": [],
        "active_signals": 0,
        "stale_signals": [],
        "memory_mb": 0.0,
        "memory_pct": 0.0,
        "finnhub_ok": False,
        "supabase_ok": False,
        "telegram_ok": False,
        "recent_errors": [],
        "failed_checks": [],
        "market_open": False,
        "spy_price": 0.0,
        "vix": 0.0,
        "regime": "UNKNOWN",
        "collect_ms": 0,
    }

    # Health
    try:
        from core.system_health import run_full_check
        h = run_full_check(send_telegram=False)
        snap["health_overall"] = h.get("overall", "UNKNOWN")
        for c in h.get("checks", []):
            snap["health_checks"][c.get("name", "?")] = c.get("status", "?")
            if c.get("status") == "RED":
                snap["failed_checks"].append(c.get("name", "?"))
    except Exception as e:
        snap["errors"].append(f"health: {e}")

    # Portfolio
    try:
        from core.portfolio_manager import get_portfolio
        pf = get_portfolio()
        snap["open_positions"] = pf.get("open_positions", [])
        snap["portfolio_state"] = pf.get("state", {})
        for pos in snap["open_positions"]:
            price = float(pos.get("current_price") or pos.get("entry_price") or 0)
            sl = float(pos.get("sl") or 0)
            if price > 0 and sl > 0 and price <= sl * 1.01:
                snap["positions_at_risk"].append(pos.get("ticker", "?"))
    except Exception as e:
        snap["errors"].append(f"portfolio: {e}")

    # Signals
    try:
        from core import signal_store as store
        active = store.load_active()
        snap["active_signals"] = len(active)
        now = datetime.now(timezone.utc)
        for s in active:
            updated = s.get("last_updated") or s.get("entry_time") or ""
            if not updated:
                continue
            try:
                ts = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                if (now - ts).total_seconds() > 7200:
                    snap["stale_signals"].append(s.get("ticker", s.get("id", "?")))
            except Exception:
                pass
    except Exception as e:
        snap["errors"].append(f"signals: {e}")

    # Memory
    try:
        import os
        import psutil
        proc = psutil.Process(os.getpid())
        rss = proc.memory_info().rss / 1024**2
        snap["memory_mb"] = round(rss, 1)
        snap["memory_pct"] = round(rss / RENDER_LIMIT_MB * 100, 1)
    except Exception as e:
        snap["errors"].append(f"memory: {e}")

    # Integrations
    try:
        from core.system_health import check_finnhub, check_supabase, check_telegram
        snap["finnhub_ok"] = check_finnhub().get("status") == "GREEN"
        snap["supabase_ok"] = check_supabase().get("status") == "GREEN"
        snap["telegram_ok"] = check_telegram().get("status") == "GREEN"
    except Exception as e:
        snap["errors"].append(f"integrations: {e}")

    # Market
    try:
        from core.signal_tracker import _is_us_market_open
        from core.market_data import fetch_market_regime
        mkt = _is_us_market_open()
        snap["market_open"] = bool(mkt.get("market_open"))
        regime = fetch_market_regime()
        snap["spy_price"] = float(regime.get("spy_close") or 0)
        snap["vix"] = float(regime.get("vix") or 0)
        snap["regime"] = regime.get("regime", "UNKNOWN")
    except Exception as e:
        snap["errors"].append(f"market: {e}")

    snap["collect_ms"] = int((time.time() - t0) * 1000)
    return snap
