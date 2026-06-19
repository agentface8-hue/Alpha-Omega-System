"""
jarvis_routes.py — Read-only summary for ATLAS JARVIS dashboard.
GET /api/jarvis/summary
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException

router = APIRouter()


def _today_utc() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


def _sector_gate_today() -> Dict[str, Any]:
    """Aggregate sector-gate blocks from today's audit + last scan cache."""
    blocked: List[Dict[str, str]] = []
    try:
        from core.decision_audit import recent_audits

        for rec in recent_audits(50):
            ts = str(rec.get("ts") or "")
            if not ts.startswith(_today_utc()):
                continue
            meta = rec.get("metadata") or {}
            for item in meta.get("sector_gate_blocked") or []:
                if isinstance(item, dict) and item.get("ticker"):
                    blocked.append({
                        "ticker": str(item["ticker"]),
                        "sector": str(item.get("sector") or "Unknown"),
                    })
    except Exception:
        pass

    status = "active"
    try:
        from core.sector_ranker import rank_sectors

        ranked = rank_sectors()
        if ranked:
            bottom = [r for r in ranked if r.get("rank", 99) >= 9]
            status = f"{len(bottom)} red sectors" if bottom else "sectors ranked"
    except Exception:
        status = "unknown"

    return {
        "status": status,
        "blocked_today": len(blocked),
        "blocked": blocked[:20],
    }


def _today_pnl_pct(portfolio: Dict[str, Any]) -> Optional[float]:
    """Realized closes today + open unrealized, as % of starting capital."""
    try:
        starting = float(
            (portfolio.get("state") or {}).get("starting_capital")
            or portfolio.get("stats", {}).get("total_value")
            or 25000
        )
        if starting <= 0:
            return None
        today = _today_utc()
        realized = 0.0
        for pos in portfolio.get("closed_positions") or []:
            closed_at = str(pos.get("closed_at") or "")
            if closed_at.startswith(today):
                realized += float(pos.get("realized_pnl") or 0)
        unrealized = float(portfolio.get("stats", {}).get("total_unrealized_pnl") or 0)
        return round((realized + unrealized) / starting * 100, 2)
    except Exception:
        return None


def _build_events(audits: List[Dict[str, Any]], signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    for rec in audits[:15]:
        ts = rec.get("ts")
        if not ts:
            continue
        action = rec.get("action") or rec.get("event_type") or "event"
        sym = rec.get("symbol") or ""
        verdict = rec.get("verdict") or rec.get("status") or ""
        level = "error" if rec.get("status") in ("fail", "error", "blocked") else "info"
        events.append({
            "ts": ts,
            "level": level,
            "text": f"{action} {sym}: {verdict}".strip(),
        })
    for sig in signals[:10]:
        ts = sig.get("created_at") or sig.get("updated_at") or sig.get("entry_date")
        if not ts:
            continue
        ticker = sig.get("ticker") or sig.get("symbol") or "?"
        conv = sig.get("conviction") or sig.get("conviction_pct")
        action = sig.get("status") or "active"
        text = f"{ticker} {action}"
        if conv is not None:
            text += f" · {conv}%"
        events.append({"ts": ts, "level": "info", "text": text})
    events.sort(key=lambda e: e["ts"], reverse=True)
    return events[:50]


@router.get("/summary")
async def jarvis_summary(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    token = os.environ.get("ALPHA_OMEGA_API_TOKEN") or os.environ.get("JARVIS_API_TOKEN")
    if token:
        if not authorization or authorization != f"Bearer {token}":
            raise HTTPException(status_code=401, detail="Unauthorized")

    from core.portfolio_manager import get_portfolio
    from core.signal_store import load_active, get_storage_status
    from core.trading_safety import status as safety_status
    from core.decision_audit import recent_audits

    portfolio = get_portfolio()
    safety = safety_status()
    global_halt = bool(safety.get("global_halt"))
    autopilot_on = not global_halt

    stats = portfolio.get("stats") or {}
    _OPEN_STATUSES = {"open", "partial"}
    open_positions = [
        p for p in (portfolio.get("open_positions") or []) if p.get("status") in _OPEN_STATUSES
    ]
    today_pnl = _today_pnl_pct(portfolio)
    sector_gate = _sector_gate_today()

    active_signals = load_active()
    signals_out = []
    for s in sorted(active_signals, key=lambda x: x.get("created_at") or "", reverse=True)[:10]:
        signals_out.append({
            "ts": s.get("created_at") or s.get("updated_at") or "",
            "ticker": s.get("ticker"),
            "conviction": s.get("conviction") or s.get("conviction_pct"),
            "action": s.get("status") or "active",
        })

    audits = recent_audits(25)
    events = _build_events(audits, active_signals)

    alerts: List[Dict[str, str]] = []
    if global_halt:
        alerts.append({
            "level": "error",
            "text": f"Trading halted: {safety.get('halt_reason') or 'global halt'}",
        })
    if sector_gate.get("blocked_today", 0) > 0:
        alerts.append({
            "level": "warn",
            "text": f"Sector gate blocked {sector_gate['blocked_today']} entries today",
        })

    storage = get_storage_status()
    conviction_engine = "Supabase" if storage.get("supabase") else "JSON local"

    swing_scanner = "ready"
    cache_path = Path(__file__).parent.parent / "calibration" / "last_portfolio_scan.json"
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text())
            ts = cache.get("cached_at") or cache.get("timestamp")
            if ts:
                swing_scanner = f"cache {str(ts)[:16]}"
        except Exception:
            swing_scanner = "cache unreadable"
    else:
        swing_scanner = "no scan cache"

    council_status = "idle"
    for sig in active_signals[:5]:
        v = sig.get("council_verdict")
        if v:
            council_status = f"{sig.get('ticker', '?')}: {v}"
            break

    regime = None
    sector_rankings: Dict[str, Any] = {}
    try:
        from core.market_data import fetch_market_regime
        regime = fetch_market_regime().get("regime")
    except Exception:
        pass
    try:
        from core.sector_ranker import rank_sectors
        ranked = rank_sectors()
        sector_rankings = {
            "top": ranked[:3] if ranked else [],
            "bottom": ranked[-3:] if len(ranked) >= 3 else [],
        }
    except Exception:
        sector_rankings = {}

    return {
        "autopilot_on": autopilot_on,
        "global_halt": global_halt,
        "open_positions": len(open_positions),
        "today_pnl_pct": today_pnl,
        "total_value": stats.get("total_value") or stats.get("equity"),
        "signals": signals_out,
        "conviction_engine": conviction_engine,
        "swing_scanner": swing_scanner,
        "sector_gate": sector_gate,
        "council_status": council_status,
        "market_regime": regime,
        "sector_rankings": sector_rankings,
        "events": events[:10],
        "alerts": alerts,
        "positions": [
            {
                "ticker": p.get("ticker"),
                "shares": p.get("shares_remaining") or p.get("shares"),
                "entry_price": p.get("entry_price"),
                "unrealized_pnl_pct": p.get("unrealized_pnl_pct"),
                "sector": p.get("sector"),
            }
            for p in open_positions
        ],
    }
