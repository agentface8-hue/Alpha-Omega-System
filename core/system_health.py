"""
system_health.py - Alpha-Omega full system health monitor v2.3
"""
import os
import json
import datetime
import logging
from typing import Dict, List, Any
from pathlib import Path

logger = logging.getLogger(__name__)


def _ok(name: str, detail: str = "") -> Dict:
    return {"name": name, "status": "GREEN", "detail": detail, "ts": _now()}

def _warn(name: str, detail: str) -> Dict:
    return {"name": name, "status": "YELLOW", "detail": detail, "ts": _now()}

def _fail(name: str, detail: str) -> Dict:
    return {"name": name, "status": "RED", "detail": detail, "ts": _now()}

def _now() -> str:
    return datetime.datetime.utcnow().strftime("%H:%M:%S UTC")


def check_supabase() -> Dict:
    try:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_ANON_KEY", "")
        if not url or not key:
            return _fail("Supabase", "SUPABASE_URL or SUPABASE_ANON_KEY missing")
        import urllib.request
        req = urllib.request.Request(
            f"{url}/rest/v1/portfolio_positions?limit=1",
            headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
        return _ok("Supabase", "Connected - portfolio_positions readable")
    except Exception as e:
        return _fail("Supabase", f"{type(e).__name__}: {str(e)[:80]}")


def check_anthropic_api() -> Dict:
    try:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            return _fail("Anthropic API", "ANTHROPIC_API_KEY missing")
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=10,
            messages=[{"role": "user", "content": "Reply: OK"}],
        )
        return _ok("Anthropic API", f"claude-haiku responded: {msg.content[0].text[:20]}")
    except Exception as e:
        return _fail("Anthropic API", f"{type(e).__name__}: {str(e)[:80]}")


def check_alpha_vantage() -> Dict:
    try:
        key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
        if not key:
            return _warn("Alpha Vantage", "API key missing - yfinance fallback active")
        import urllib.request
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=SPY&apikey={key}"
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())
        price = data.get("Global Quote", {}).get("05. price", "")
        if not price:
            return _warn("Alpha Vantage", "API responded but no price - possible rate limit")
        return _ok("Alpha Vantage", f"SPY @ ${float(price):.2f}")
    except Exception as e:
        return _fail("Alpha Vantage", f"{type(e).__name__}: {str(e)[:80]}")


def check_airtable() -> Dict:
    try:
        from core.airtable import check_connection
        result = check_connection()
        if result["status"] == "GREEN":
            return _ok("Airtable", result["detail"])
        return _warn("Airtable", result["detail"])
    except Exception as e:
        return _warn("Airtable", f"{type(e).__name__}: {str(e)[:80]}")


def check_telegram() -> Dict:
    try:
        token = os.environ.get("TELEGRAM_TOKEN", "")
        if not token:
            return _fail("Telegram", "TELEGRAM_TOKEN missing")
        import urllib.request
        url = f"https://api.telegram.org/bot{token}/getMe"
        with urllib.request.urlopen(url, timeout=8) as r:
            resp = json.loads(r.read())
        if resp.get("ok"):
            return _ok("Telegram", f"Bot @{resp.get('result',{}).get('username','?')} reachable")
        return _fail("Telegram", "API returned ok=false")
    except Exception as e:
        return _fail("Telegram", f"{type(e).__name__}: {str(e)[:80]}")


def check_portfolio_state() -> Dict:
    try:
        from core import portfolio_store as store
        state     = store.load_state()
        positions = store.load_positions("open")
        cash  = float(state.get("cash", 0))
        total = float(state.get("total_value", 0))
        if cash < 0:
            return _fail("Portfolio State", f"Negative cash: ${cash:.2f}")
        if total < 0:
            return _fail("Portfolio State", f"Negative total: ${total:.2f}")
        corrupted = [p["ticker"] for p in positions if not p.get("entry_price") or p.get("entry_price", 0) <= 0]
        if corrupted:
            return _warn("Portfolio State", f"Missing entry price: {corrupted}")
        return _ok("Portfolio State", f"{len(positions)} open | Cash: ${cash:.0f} | Total: ${total:.0f}")
    except Exception as e:
        return _fail("Portfolio State", f"{type(e).__name__}: {str(e)[:80]}")


def check_signal_tracker() -> Dict:
    try:
        from core import signal_store as store
        active = store.load_active()
        closed = store.load_closed()
        stale  = []
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=48)
        for s in active:
            updated = s.get("updated_at", "")
            if updated:
                try:
                    if datetime.datetime.fromisoformat(updated) < cutoff:
                        stale.append(s.get("ticker", "?"))
                except Exception:
                    pass
        detail = f"{len(active)} active, {len(closed)} closed"
        if stale:
            return _warn("Signal Tracker", f"{detail} - {len(stale)} stale: {stale}")
        return _ok("Signal Tracker", detail)
    except Exception as e:
        return _fail("Signal Tracker", f"{type(e).__name__}: {str(e)[:80]}")


def check_learning_loop() -> Dict:
    try:
        cal = Path(__file__).parent.parent / "calibration" / "calibration_params.json"
        if not cal.exists():
            return _warn("Learning Loop", "calibration_params.json missing")
        data = json.loads(cal.read_text())
        last = data.get("last_updated", "")
        if last:
            age_days = (datetime.datetime.utcnow() - datetime.datetime.fromisoformat(last)).days
            if age_days > 14:
                return _warn("Learning Loop", f"Calibration {age_days}d old - run /api/learning/run-deep")
            return _ok("Learning Loop", f"Last updated {age_days}d ago | {data.get('signals_analyzed','?')} signals")
        return _ok("Learning Loop", "Calibration file present")
    except Exception as e:
        return _fail("Learning Loop", f"{type(e).__name__}: {str(e)[:80]}")


def check_dream_log() -> Dict:
    """Read dream_log.json directly — no HTTP call to self (avoids circular timeout)."""
    try:
        log_path = Path(__file__).parent.parent / "signals" / "dream_log.json"

        if not log_path.exists():
            return _ok("Dream Log", "Dreaming agent active - no dreams yet")

        dreams = json.loads(log_path.read_text())

        if not dreams:
            return _ok("Dream Log", "Dreaming agent active - no dreams yet")

        # Newest first
        latest = dreams[0] if isinstance(dreams, list) else dreams
        ts = latest.get("ts") or latest.get("created_at", "")

        if ts:
            try:
                dt    = datetime.datetime.fromisoformat(ts.replace("Z", "").replace("+00:00", ""))
                age_h = (datetime.datetime.utcnow() - dt).total_seconds() / 3600
                edge  = latest.get("edge_level", "?")
                ticker = latest.get("top_ticker") or "market scan"
                label = f"Last dream {age_h:.0f}h ago | edge={edge} | {ticker}"
                # Warn only on weekdays if dream is very old
                import pytz
                is_market_day = datetime.datetime.now(pytz.timezone("US/Eastern")).weekday() < 5
                if age_h > 12 and is_market_day:
                    return _warn("Dream Log", label + " (overdue)")
                return _ok("Dream Log", label)
            except Exception:
                pass

        return _ok("Dream Log", f"{len(dreams)} dreams logged")

    except Exception as e:
        return _warn("Dream Log", f"Could not read: {str(e)[:60]}")


ALL_CHECKS = [
    ("Supabase",        check_supabase),
    ("Anthropic API",   check_anthropic_api),
    ("Alpha Vantage",   check_alpha_vantage),
    ("Airtable",        check_airtable),
    ("Telegram",        check_telegram),
    ("Portfolio State", check_portfolio_state),
    ("Signal Tracker",  check_signal_tracker),
    ("Learning Loop",   check_learning_loop),
    ("Dream Log",       check_dream_log),
]


def run_full_check(send_telegram: bool = True) -> Dict[str, Any]:
    results = []
    for name, fn in ALL_CHECKS:
        try:
            results.append(fn())
        except Exception as e:
            results.append(_fail(name, f"Check crashed: {str(e)[:80]}"))

    reds    = [r for r in results if r["status"] == "RED"]
    yellows = [r for r in results if r["status"] == "YELLOW"]
    greens  = [r for r in results if r["status"] == "GREEN"]
    overall = "RED" if reds else "YELLOW" if yellows else "GREEN"

    report = {
        "overall": overall,
        "checked_at": datetime.datetime.utcnow().isoformat(),
        "summary": {"green": len(greens), "yellow": len(yellows), "red": len(reds), "total": len(results)},
        "checks": results, "reds": reds, "yellows": yellows,
    }
    if send_telegram and reds:
        _send_health_alert(report)
    return report


def _send_health_alert(report: Dict):
    try:
        from core.telegram_alerts import _send
        lines = ["ALPHA-OMEGA HEALTH ALERT",
                 f"GREEN={report['summary']['green']} WARN={report['summary']['yellow']} FAIL={report['summary']['red']}", ""]
        for r in report["reds"]:
            lines.append(f"FAIL {r['name']}: {r['detail'][:80]}")
        lines.append(f"{report['checked_at'][:16].replace('T',' ')} UTC")
        _send("\n".join(lines))
    except Exception as e:
        logger.warning(f"[HEALTH] Alert failed: {e}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from dotenv import load_dotenv
    load_dotenv()
    print("\n" + "="*50 + "\n  ALPHA-OMEGA HEALTH CHECK\n" + "="*50)
    report = run_full_check(send_telegram=False)
    for r in report["checks"]:
        print(f"[{r['status'][:2]}] {r['name']}: {r['detail']}")
    print(f"\nOVERALL: {report['overall']}")
    if report["reds"] or report["yellows"]:
        sys.exit(1)
