"""
dreaming_agent.py — Scheduled background market analyst.

Runs every 4h on market days (wired into cron / cowork_hourly_check.py).
No user trigger needed. Reads market context, quick-scans top tickers,
asks Gemini Flash for the most interesting edge, logs to Supabase,
fires Telegram only if edge_level == "HIGH".

Main entry point: run_dream_cycle()
"""
import os
import json
import logging
import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Tickers to scan during dream cycle (top conviction candidates)
DREAM_WATCHLIST = [
    "NVDA", "AAPL", "MSFT", "TSLA", "AMZN",
    "GOOGL", "META", "CRWD", "MRVL", "AMD",
]

_DREAM_SYSTEM = """You are the Alpha-Omega Dreaming Agent — a background market analyst that runs every 4 hours.
You receive a compact market snapshot and the top conviction scores for a watchlist.
Your job: identify the single most interesting edge or setup right now.

Return ONLY a valid JSON object:
{
  "edge_level": "HIGH" | "MEDIUM" | "LOW",
  "top_ticker": "<ticker or null>",
  "analysis": "<2-3 sentences: what the market is setting up, what the edge is, what to watch>",
  "key_risk": "<1 sentence: biggest risk to watch>",
  "action": "WATCH_CLOSELY" | "MONITOR" | "WAIT"
}

Be specific. If nothing interesting, say LOW and explain why. No markdown, no extra keys."""


def _is_market_day_and_hour() -> bool:
    """Return True if we should run a dream cycle right now."""
    import pytz
    now_et = datetime.datetime.now(pytz.timezone("US/Eastern"))
    if now_et.weekday() >= 5:
        return False  # weekend
    hour = now_et.hour
    # Run at 10:00, 12:00, 14:00, 15:30 ET
    return hour in (10, 12, 14, 15)


def _quick_scan_top_tickers(tickers: List[str]) -> List[Dict]:
    """Score top tickers quickly — returns list of {ticker, conviction_pct, heat}."""
    results = []
    try:
        from core.market_data import fetch_ticker_data, fetch_market_regime
        from core.conviction_engine import score_ticker
        regime = fetch_market_regime()
        for ticker in tickers[:6]:  # cap at 6 to stay fast
            try:
                data = fetch_ticker_data(ticker)
                scored = score_ticker(data, regime)
                if scored and not scored.get("hard_fail"):
                    results.append({
                        "ticker": ticker,
                        "conviction_pct": scored.get("conviction_pct", 0),
                        "heat": scored.get("heat", "COLD"),
                        "tas": scored.get("tas", "?"),
                    })
            except Exception as e:
                logger.debug(f"[DREAM] {ticker} scan failed: {e}")
        results.sort(key=lambda x: x["conviction_pct"], reverse=True)
    except Exception as e:
        logger.warning(f"[DREAM] Quick scan failed: {e}")
    return results


def _build_dream_prompt(market_ctx: Dict, scan_results: List[Dict]) -> str:
    vix     = market_ctx.get("vix", "?")
    spy_chg = market_ctx.get("spy_change_pct", "?")
    regime  = market_ctx.get("regime", "?")
    now     = datetime.datetime.utcnow().strftime("%H:%M UTC")

    lines = [
        f"Time: {now}",
        f"Regime: {regime}  |  VIX: {vix}  |  SPY today: {spy_chg}%",
        "",
        "Top conviction scores right now:",
    ]
    if scan_results:
        for r in scan_results[:5]:
            lines.append(f"  {r['ticker']}: {r['conviction_pct']}% ({r['heat']}) TAS={r['tas']}")
    else:
        lines.append("  (scan unavailable)")

    return "\n".join(lines)


def _call_gemini(prompt: str) -> Dict[str, Any]:
    """Call Gemini Flash for the dream analysis."""
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")

    import urllib.request as _ur
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"gemini-2.0-flash:generateContent?key={api_key}")
    full_prompt = _DREAM_SYSTEM + "\n\nMarket snapshot:\n" + prompt
    body = json.dumps({
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"maxOutputTokens": 250},
    }).encode()
    req = _ur.Request(url, data=body, headers={"Content-Type": "application/json"})
    with _ur.urlopen(req, timeout=15) as r:
        resp = json.loads(r.read().decode())
    raw = resp["candidates"][0]["content"]["parts"][0]["text"].strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


def _save_dream(dream: Dict) -> bool:
    """Persist dream to Supabase dream_log table. Falls back to local JSON."""
    try:
        from core import signal_store as store
        # Try Supabase
        if store._sb():
            store._sb().table("dream_log").insert(dream).execute()
            return True
    except Exception as e:
        logger.debug(f"[DREAM] Supabase save failed: {e}")

    # JSON fallback
    try:
        from pathlib import Path
        log_path = Path(__file__).parent.parent / "signals" / "dream_log.json"
        existing = []
        if log_path.exists():
            try:
                existing = json.loads(log_path.read_text())
            except Exception:
                pass
        existing.append(dream)
        existing = existing[-50:]  # keep last 50
        log_path.write_text(json.dumps(existing, indent=2, default=str))
        return True
    except Exception as e:
        logger.error(f"[DREAM] JSON fallback save failed: {e}")
        return False


def load_dream_log(limit: int = 10) -> List[Dict]:
    """Load recent dream log entries (Supabase first, JSON fallback)."""
    try:
        from core import signal_store as store
        if store._sb():
            result = (store._sb().table("dream_log")
                      .select("*")
                      .order("ts", desc=True)
                      .limit(limit)
                      .execute())
            return result.data or []
    except Exception:
        pass

    try:
        from pathlib import Path
        log_path = Path(__file__).parent.parent / "signals" / "dream_log.json"
        if log_path.exists():
            entries = json.loads(log_path.read_text())
            return list(reversed(entries))[:limit]
    except Exception:
        pass
    return []


def _send_dream_alert(dream: Dict):
    """Fire Telegram alert for HIGH edge dreams only."""
    try:
        from core.telegram_alerts import _send
        ticker  = dream.get("top_ticker") or "Market"
        action  = dream.get("action", "MONITOR")
        analysis = dream.get("analysis", "")[:180]
        risk    = dream.get("key_risk", "")[:100]
        _send(
            f"\U0001f4ad <b>DREAM — HIGH EDGE DETECTED</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"\U0001f3af Focus: <b>{ticker}</b>  |  Action: <b>{action}</b>\n"
            f"\U0001f4ca {analysis}\n"
            f"⚠️ Risk: {risk}\n"
            f"\U0001f550 {datetime.datetime.utcnow().strftime('%H:%M UTC')}"
        )
    except Exception as e:
        logger.warning(f"[DREAM] Telegram alert failed: {e}")


# ── Public entry point ────────────────────────────────────────────────────────

def run_dream_cycle(force: bool = False) -> Dict[str, Any]:
    """
    Run one dream cycle. Call from scheduler or /api/dreams/run endpoint.

    Args:
        force: If True, skips the market-day/hour check (for testing).

    Returns:
        dict with dream result + metadata.
    """
    if not force and not _is_market_day_and_hour():
        return {"status": "skipped", "reason": "outside dream schedule"}

    logger.info("[DREAM] Starting dream cycle...")

    try:
        from core.signal_tracker import _fetch_market_context
        market_ctx = _fetch_market_context()
    except Exception as e:
        market_ctx = {"vix": 0, "spy_change_pct": 0, "regime": "Unknown", "error": str(e)}

    scan_results = _quick_scan_top_tickers(DREAM_WATCHLIST)

    try:
        prompt   = _build_dream_prompt(market_ctx, scan_results)
        analysis = _call_gemini(prompt)
    except Exception as e:
        logger.error(f"[DREAM] Gemini call failed: {e}")
        analysis = {
            "edge_level": "LOW",
            "top_ticker": None,
            "analysis": f"Dream cycle failed: {str(e)[:80]}",
            "key_risk": "System error",
            "action": "WAIT",
        }

    dream = {
        "ts":           datetime.datetime.utcnow().isoformat(),
        "regime":       market_ctx.get("regime", "?"),
        "vix":          market_ctx.get("vix", 0),
        "spy_change":   market_ctx.get("spy_change_pct", 0),
        "edge_level":   analysis.get("edge_level", "LOW"),
        "top_ticker":   analysis.get("top_ticker"),
        "analysis":     analysis.get("analysis", ""),
        "key_risk":     analysis.get("key_risk", ""),
        "action":       analysis.get("action", "WAIT"),
        "model":        "gemini-2.0-flash",
        "scan_tickers": [r["ticker"] for r in scan_results[:5]],
    }

    _save_dream(dream)

    if dream["edge_level"] == "HIGH":
        _send_dream_alert(dream)

    logger.info(f"[DREAM] Cycle complete — edge={dream['edge_level']} ticker={dream['top_ticker']}")
    return {"status": "ok", "dream": dream}
