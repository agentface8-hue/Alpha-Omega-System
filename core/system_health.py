"""
system_health.py — Alpha-Omega full system health monitor v1.0

Checks every integration is ACTUALLY WORKING, not just running.
The Google Sheet was empty for months because syscheck.py never tested it.
This module tests real writes/reads to every external service.

Health levels:
  GREEN  = working perfectly
  YELLOW = working but degraded (stale data, slow, etc.)
  RED    = broken — needs immediate fix

Run via:
  - GET /api/health/full          → full check, returns JSON
  - python core/system_health.py  → terminal output
  - Scheduled Cowork task         → daily Telegram alert

Every check is isolated — one failure never blocks the others.
"""
import os
import json
import datetime
import time
import logging
from typing import Dict, List, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Result builder ────────────────────────────────────────────────────────────

def _ok(name: str, detail: str = "") -> Dict:
    return {"name": name, "status": "GREEN", "detail": detail, "ts": _now()}

def _warn(name: str, detail: str) -> Dict:
    return {"name": name, "status": "YELLOW", "detail": detail, "ts": _now()}

def _fail(name: str, detail: str) -> Dict:
    return {"name": name, "status": "RED", "detail": detail, "ts": _now()}

def _now() -> str:
    return datetime.datetime.utcnow().strftime("%H:%M:%S UTC")


# ── Individual checks ─────────────────────────────────────────────────────────

def check_supabase() -> Dict:
    """Test Supabase read — verifies URL, key, and connectivity via direct HTTP."""
    try:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_ANON_KEY", "")
        if not url or not key:
            return _fail("Supabase", "SUPABASE_URL or SUPABASE_ANON_KEY missing from env")
        import urllib.request
        req = urllib.request.Request(
            f"{url}/rest/v1/portfolio_positions?limit=1",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Accept": "application/json",
            }
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
        return _ok("Supabase", "Connected — portfolio_positions readable")
    except Exception as e:
        return _fail("Supabase", f"{type(e).__name__}: {str(e)[:80]}")


def check_anthropic_api() -> Dict:
    """Test Anthropic API with minimal call."""
    try:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            return _fail("Anthropic API", "ANTHROPIC_API_KEY missing from env")
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": "Reply: OK"}],
        )
        return _ok("Anthropic API", f"claude-haiku responded: {msg.content[0].text[:20]}")
    except Exception as e:
        return _fail("Anthropic API", f"{type(e).__name__}: {str(e)[:80]}")


def check_alpha_vantage() -> Dict:
    """Test Alpha Vantage price fetch for SPY."""
    try:
        key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
        if not key:
            return _warn("Alpha Vantage", "ALPHA_VANTAGE_API_KEY missing — yfinance fallback active")
        import urllib.request
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol=SPY&apikey={key}"
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read().decode())
        price = data.get("Global Quote", {}).get("05. price", "")
        if not price:
            return _warn("Alpha Vantage", "API responded but no price data — possible rate limit")
        return _ok("Alpha Vantage", f"SPY @ ${float(price):.2f}")
    except Exception as e:
        return _fail("Alpha Vantage", f"{type(e).__name__}: {str(e)[:80]}")


def check_google_sheets() -> Dict:
    """Test Google Sheets — write a test row, verify it exists, then delete it."""
    try:
        token_json = os.environ.get("SHEETS_TOKEN_JSON", "")
        base_dir = Path(__file__).parent.parent
        token_file = base_dir / "data" / "sheets_token.json"

        if not token_json and not token_file.exists():
            return _fail("Google Sheets", "SHEETS_TOKEN_JSON env var not set and local token missing")

        import gspread
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        creds_data = json.loads(token_json) if token_json else json.loads(token_file.read_text())
        creds = Credentials(
            token=creds_data.get("token"),
            refresh_token=creds_data.get("refresh_token"),
            token_uri=creds_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=creds_data.get("client_id"),
            client_secret=creds_data.get("client_secret"),
            scopes=creds_data.get("scopes", ["https://www.googleapis.com/auth/spreadsheets"]),
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        gc = gspread.authorize(creds)
        SHEET_ID = "1G5f1AePhWKJEMJKmfHj1genbr18LMdlCWPsoBJC2ZxM"
        ws = gc.open_by_key(SHEET_ID).sheet1

        # Write a health-check row
        test_row = ["HEALTH_CHECK", "TEST", "—", "—", "—", "0", "0", "0",
                    f"health_check_{_now()}", "—"]
        ws.append_row(test_row, value_input_option="USER_ENTERED")

        # Verify it's there and delete it
        all_vals = ws.get_all_values()
        last_row = len(all_vals)
        if all_vals and all_vals[-1][0] == "HEALTH_CHECK":
            ws.delete_rows(last_row)
            return _ok("Google Sheets", f"Write+delete verified — sheet has {last_row - 1} trade rows")
        return _warn("Google Sheets", "Write succeeded but verify failed — check manually")
    except Exception as e:
        return _fail("Google Sheets", f"{type(e).__name__}: {str(e)[:100]}")


def check_telegram() -> Dict:
    """Test Telegram bot can send a message."""
    try:
        token = os.environ.get("TELEGRAM_TOKEN", "")
        chat_id = os.environ.get("TELEGRAM_PERSONAL_CHAT_ID", "")
        if not token or not chat_id:
            return _fail("Telegram", "TELEGRAM_TOKEN or TELEGRAM_PERSONAL_CHAT_ID missing")
        import urllib.request, urllib.parse
        msg = f"🔧 Health check ping — {_now()}"
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}).encode()
        with urllib.request.urlopen(url, data=data, timeout=8) as r:
            resp = json.loads(r.read())
        if resp.get("ok"):
            return _ok("Telegram", "Message sent successfully")
        return _fail("Telegram", f"API returned ok=false: {resp}")
    except Exception as e:
        return _fail("Telegram", f"{type(e).__name__}: {str(e)[:80]}")


def check_portfolio_state() -> Dict:
    """Verify portfolio state is valid — no corrupted positions."""
    try:
        from core import portfolio_store as store
        state = store.load_state()
        positions = store.load_positions("open")
        cash = float(state.get("cash", 0))
        total = float(state.get("total_value", 0))

        if cash < 0:
            return _fail("Portfolio State", f"Negative cash: ${cash:.2f} — data corruption")
        if total < 0:
            return _fail("Portfolio State", f"Negative total value: ${total:.2f}")

        corrupted = [p["ticker"] for p in positions if not p.get("entry_price") or p.get("entry_price", 0) <= 0]
        if corrupted:
            return _warn("Portfolio State", f"Positions with missing entry price: {corrupted}")

        return _ok("Portfolio State",
                   f"{len(positions)} open | Cash: ${cash:.0f} | Total: ${total:.0f}")
    except Exception as e:
        return _fail("Portfolio State", f"{type(e).__name__}: {str(e)[:80]}")


def check_signal_tracker() -> Dict:
    """Verify signal store is readable and active signals are fresh."""
    try:
        from core import signal_store as store
        active = store.load_active()
        closed = store.load_closed()

        stale = []
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(hours=48)
        for s in active:
            updated = s.get("updated_at", "")
            if updated:
                try:
                    dt = datetime.datetime.fromisoformat(updated)
                    if dt < cutoff:
                        stale.append(s.get("ticker", "?"))
                except Exception:
                    pass

        detail = f"{len(active)} active, {len(closed)} closed"
        if stale:
            return _warn("Signal Tracker", f"{detail} — {len(stale)} signals not updated in 48h: {stale}")
        return _ok("Signal Tracker", detail)
    except Exception as e:
        return _fail("Signal Tracker", f"{type(e).__name__}: {str(e)[:80]}")


def check_learning_loop() -> Dict:
    """Verify calibration file is present and reasonably fresh."""
    try:
        cal_path = Path(__file__).parent.parent / "calibration" / "calibration_params.json"
        if not cal_path.exists():
            return _warn("Learning Loop", "calibration_params.json missing — will be created on first close")
        data = json.loads(cal_path.read_text())
        last = data.get("last_updated", "")
        if last:
            try:
                dt = datetime.datetime.fromisoformat(last)
                age_days = (datetime.datetime.utcnow() - dt).days
                if age_days > 14:
                    return _warn("Learning Loop", f"Calibration is {age_days} days old — run /api/learning/run-deep")
                return _ok("Learning Loop", f"Last updated {age_days}d ago | {data.get('signals_analyzed', '?')} signals analyzed")
            except Exception:
                pass
        return _ok("Learning Loop", "Calibration file present")
    except Exception as e:
        return _fail("Learning Loop", f"{type(e).__name__}: {str(e)[:80]}")


def check_dream_log() -> Dict:
    """Check if dream log has run recently on market days. Uses direct HTTP."""
    try:
        import pytz
        now_et = datetime.datetime.now(pytz.timezone("US/Eastern"))
        is_market_day = now_et.weekday() < 5

        log_path = Path(__file__).parent.parent / "signals" / "dream_log.json"
        if log_path.exists():
            entries = json.loads(log_path.read_text())
            if entries:
                last_ts = entries[-1].get("ts", "")
                dt = datetime.datetime.fromisoformat(last_ts)
                age_h = (datetime.datetime.utcnow() - dt).total_seconds() / 3600
                if age_h > 12 and is_market_day:
                    return _warn("Dream Log", f"Last dream {age_h:.0f}h ago — expected every 4h on market days")
                return _ok("Dream Log", f"Last dream {age_h:.0f}h ago — model: {entries[-1].get('model','?')}")

        # Check Supabase via direct HTTP (no supabase-py WebSocket)
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_ANON_KEY", "")
        if url and key:
            import urllib.request
            req = urllib.request.Request(
                f"{url}/rest/v1/dream_log?order=created_at.desc&limit=1&select=created_at,model",
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Accept": "application/json",
                }
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode())
            if data:
                dt = datetime.datetime.fromisoformat(data[0].get("created_at", data[0].get("ts","")))
                age_h = (datetime.datetime.utcnow() - dt).total_seconds() / 3600
                if age_h > 12 and is_market_day:
                    return _ok("Dream Log", f"Last dream {age_h:.0f}h ago (Supabase)")
                return _ok("Dream Log", f"Last dream {age_h:.0f}h ago (Supabase)")

        return _warn("Dream Log", "No dream log found — check /api/dreams/run")
    except Exception as e:
        return _warn("Dream Log", f"Could not check: {str(e)[:60]}")


# ── Master health check ───────────────────────────────────────────────────────

ALL_CHECKS = [
    ("Supabase",        check_supabase),
    ("Anthropic API",   check_anthropic_api),
    ("Alpha Vantage",   check_alpha_vantage),
    ("Google Sheets",   check_google_sheets),
    ("Telegram",        check_telegram),
    ("Portfolio State", check_portfolio_state),
    ("Signal Tracker",  check_signal_tracker),
    ("Learning Loop",   check_learning_loop),
    ("Dream Log",       check_dream_log),
]

def run_full_check(send_telegram: bool = True) -> Dict[str, Any]:
    """
    Run all health checks. Returns full report.
    If any RED found and send_telegram=True, fires Telegram alert.
    """
    results = []
    for name, fn in ALL_CHECKS:
        try:
            result = fn()
        except Exception as e:
            result = _fail(name, f"Check crashed: {str(e)[:80]}")
        results.append(result)

    reds    = [r for r in results if r["status"] == "RED"]
    yellows = [r for r in results if r["status"] == "YELLOW"]
    greens  = [r for r in results if r["status"] == "GREEN"]

    overall = "RED" if reds else "YELLOW" if yellows else "GREEN"

    report = {
        "overall":  overall,
        "checked_at": datetime.datetime.utcnow().isoformat(),
        "summary": {
            "green":  len(greens),
            "yellow": len(yellows),
            "red":    len(reds),
            "total":  len(results),
        },
        "checks": results,
        "reds":    reds,
        "yellows": yellows,
    }

    if send_telegram and (reds or yellows):
        _send_health_alert(report)

    return report


def _send_health_alert(report: Dict):
    """Send Telegram alert summarizing health issues."""
    try:
        from core.telegram_alerts import _send
        icon = "🔴" if report["overall"] == "RED" else "🟡"
        lines = [
            f"{icon} <b>ALPHA-OMEGA HEALTH ALERT</b>",
            f"━━━━━━━━━━━━━━━━━━",
            f"🟢 {report['summary']['green']} OK  "
            f"🟡 {report['summary']['yellow']} WARN  "
            f"🔴 {report['summary']['red']} FAIL",
            "",
        ]
        for r in report["reds"]:
            lines.append(f"🔴 <b>{r['name']}</b>: {r['detail']}")
        for r in report["yellows"]:
            lines.append(f"🟡 <b>{r['name']}</b>: {r['detail']}")
        lines.append(f"\n🕐 {report['checked_at'][:16].replace('T',' ')} UTC")
        _send("\n".join(lines))
    except Exception as e:
        logger.warning(f"[HEALTH] Telegram alert failed: {e}")


# ── Terminal runner ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from dotenv import load_dotenv
    load_dotenv()

    print("\n" + "="*55)
    print("  ALPHA-OMEGA FULL SYSTEM HEALTH CHECK")
    print("="*55)

    report = run_full_check(send_telegram=False)

    STATUS_ICON = {"GREEN": "✅", "YELLOW": "⚠️ ", "RED": "❌"}
    for r in report["checks"]:
        icon = STATUS_ICON[r["status"]]
        print(f"\n{icon} {r['name']}")
        print(f"   {r['detail']}")

    print("\n" + "="*55)
    overall_icon = STATUS_ICON[report["overall"]]
    s = report["summary"]
    print(f"  {overall_icon} OVERALL: {report['overall']}")
    print(f"  ✅ {s['green']} GREEN  ⚠️  {s['yellow']} YELLOW  ❌ {s['red']} RED")
    print("="*55 + "\n")

    if report["reds"] or report["yellows"]:
        print("ACTION REQUIRED:")
        for r in report["reds"] + report["yellows"]:
            print(f"  [{r['status']}] {r['name']}: {r['detail']}")
        sys.exit(1)
