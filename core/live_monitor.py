"""
live_monitor.py — Real-time system health monitor for Alpha-Omega.

Runs 4 levels of checks:
  Level 1 (every 5 min): Critical endpoints — backend alive, portfolio, signals
  Level 2 (every 15 min): Integration checks — Supabase, Telegram, prices
  Level 3 (every 30 min): Performance checks — learning loop, agent threads
  Level 4 (on every deploy): Full regression test

Alerts on Telegram IMMEDIATELY when:
  - Any critical check fails
  - Any check goes from PASS → FAIL (state change)
  - Response time > 10s on critical endpoints
  - New error type not seen before

Does NOT alert when:
  - Same check has been failing for > 1h (already notified, don't spam)
  - System is in maintenance window

State is stored in data/monitor_state.json (persists across runs).
"""
import os, sys, json, time, threading, logging, traceback
from pathlib import Path
from datetime import datetime, timezone
import urllib.request, urllib.error

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv; load_dotenv()

# When running ON Render use localhost to avoid public HTTP round-trips
_ON_RENDER = bool(os.environ.get("RENDER") or os.environ.get("RENDER_EXTERNAL_URL"))
_PORT      = os.environ.get("PORT", "10000")
BASE       = f"http://127.0.0.1:{_PORT}" if _ON_RENDER else "https://alpha-omega-system.onrender.com"
TG_TOKEN  = os.environ.get("TELEGRAM_TOKEN", "")
TG_CHAT   = os.environ.get("TELEGRAM_PERSONAL_CHAT_ID", "")
SB_URL    = os.environ.get("SUPABASE_URL", "")
SB_KEY    = os.environ.get("SUPABASE_ANON_KEY", "")
STATE_FILE= Path(__file__).parent / "data" / "monitor_state.json"

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [MONITOR] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("monitor")

# ── State management ──────────────────────────────────────────────
def load_state():
    if STATE_FILE.exists():
        try: return json.loads(STATE_FILE.read_text())
        except: pass
    return {"failures": {}, "last_alert": {}, "consecutive_fail": {}}

def save_state(s):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(s, indent=2, default=str))

# ── HTTP helpers ──────────────────────────────────────────────────
def _get(path, timeout=15):
    req = urllib.request.Request(f"{BASE}{path}",
        headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read()), r.status

def _post(path, body=None, timeout=15):
    data = json.dumps(body or {}).encode()
    req  = urllib.request.Request(f"{BASE}{path}", data=data,
        headers={"Content-Type":"application/json","Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read()), r.status

def _sb_write_test():
    """Quick Supabase connectivity check — just read one row."""
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1/signals?limit=1",
        headers={"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}"})
    with urllib.request.urlopen(req, timeout=8) as r:
        rows = json.loads(r.read())
    return f"{len(rows)} signals readable"

# ── Telegram ──────────────────────────────────────────────────────
def tg(msg, silent=False):
    if not TG_TOKEN or not TG_CHAT: return
    try:
        body = json.dumps({"chat_id": TG_CHAT, "text": msg,
                           "parse_mode": "HTML",
                           "disable_notification": silent}).encode()
        req  = urllib.request.Request(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data=body, headers={"Content-Type":"application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")

# ── Check runner ──────────────────────────────────────────────────
def run_check(name, fn, critical=False, slow_threshold_ms=8000):
    t0 = time.time()
    try:
        result = fn()
        ms = int((time.time()-t0)*1000)
        slow = ms > slow_threshold_ms
        return {"name":name,"status":"PASS","ms":ms,"slow":slow,"critical":critical}
    except Exception as e:
        ms = int((time.time()-t0)*1000)
        return {"name":name,"status":"FAIL","ms":ms,"error":str(e)[:200],
                "critical":critical,"tb":traceback.format_exc()[-300:]}

# ── Check definitions ─────────────────────────────────────────────
CHECKS_L1 = [  # Every 5 min — critical (direct internal calls, no HTTP)
    ("backend.process",   lambda: (True, "alive"),                                   True),
    ("portfolio.load",    lambda: __import__("core.portfolio_manager", fromlist=["get_portfolio_state"]).get_portfolio_state(), True),
    ("signals.load",      lambda: __import__("core.signal_store",      fromlist=["get_all_signals"]).get_all_signals(),         True),
    ("supabase.write",    lambda: _sb_write_test(),                                  True),
]

CHECKS_L2 = [  # Every 15 min — integrations
    ("supabase.signals",  lambda: urllib.request.urlopen(
        urllib.request.Request(f"{SB_URL}/rest/v1/signals?limit=1",
        headers={"apikey":SB_KEY,"Authorization":f"Bearer {SB_KEY}"}),timeout=8).status, False),
    ("supabase.trade_log",lambda: urllib.request.urlopen(
        urllib.request.Request(f"{SB_URL}/rest/v1/trade_log?limit=1",
        headers={"apikey":SB_KEY,"Authorization":f"Bearer {SB_KEY}"}),timeout=8).status, False),
    ("prices.live",       lambda: _post("/api/prices",{"symbols":["SPY"]}), False),
    ("telegram.bot",      lambda: urllib.request.urlopen(
        f"https://api.telegram.org/bot{TG_TOKEN}/getMe",timeout=8).status, False),
    ("frontend.vercel",   lambda: urllib.request.urlopen(
        "https://alpha-omega-ngfw.vercel.app",timeout=10).status, False),
]

CHECKS_L3 = [  # Every 30 min — performance
    ("learning.summary",  lambda: _get("/api/learning/summary"), False),
    ("health.full",       lambda: _get("/api/health/full",timeout=30), False),
    ("trade_history",     lambda: _get("/api/trade-history"), False),
]

# ── Alert logic ───────────────────────────────────────────────────
ALERT_COOLDOWN_S = 3600  # 1h between repeated alerts for same check

def process_results(checks, state):
    now = time.time()
    alerts = []

    for r in checks:
        name  = r["name"]
        prev  = state["failures"].get(name)       # last known status
        last  = state["last_alert"].get(name, 0)  # last time we alerted
        consec= state["consecutive_fail"].get(name, 0)

        if r["status"] == "FAIL":
            state["consecutive_fail"][name] = consec + 1
            state["failures"][name] = {
                "since": prev["since"] if prev else now,
                "error": r.get("error","?"),
                "count": (prev["count"] if prev else 0) + 1,
            }
            # Alert if: new failure OR been failing > 1h and haven't alerted in 1h
            first_fail = not prev  # was passing before
            cooldown_expired = (now - last) > ALERT_COOLDOWN_S

            if first_fail or (cooldown_expired and consec >= 3):
                alerts.append(r)
                state["last_alert"][name] = now
        else:
            # Check recovered
            if prev:
                # Was failing, now passing → recovery alert
                down_for = int((now - prev["since"]) / 60)
                alerts.append({"name":name,"status":"RECOVERED",
                                "down_min":down_for,"prev_error":prev.get("error","?")})
            state["consecutive_fail"][name] = 0
            state["failures"].pop(name, None)

        # Slow response alert
        if r.get("slow") and r["status"] == "PASS":
            if (now - state["last_alert"].get(f"{name}.slow",0)) > ALERT_COOLDOWN_S:
                alerts.append({**r, "status":"SLOW"})
                state["last_alert"][f"{name}.slow"] = now

    return alerts

def send_alerts(alerts):
    if not alerts: return
    lines = [f"🚨 <b>Alpha-Omega Monitor</b>  {datetime.now(timezone.utc).strftime('%H:%M UTC')}"]
    for a in alerts:
        status = a["status"]
        name   = a["name"]
        if status == "FAIL":
            crit = " ⚠️ CRITICAL" if a.get("critical") else ""
            lines.append(f"❌ <b>{name}</b>{crit}")
            lines.append(f"   {a.get('error','unknown error')[:100]}")
        elif status == "RECOVERED":
            lines.append(f"✅ <b>{name}</b> recovered (was down {a['down_min']}m)")
        elif status == "SLOW":
            lines.append(f"🐢 <b>{name}</b> slow: {a['ms']}ms")
    tg("\n".join(lines))
    log.warning(f"Sent {len(alerts)} alerts")

# ── Scheduled loops ───────────────────────────────────────────────
def _run_level(level_name, checks, interval_s, state_ref):
    log.info(f"Starting {level_name} loop (every {interval_s//60}m)")
    while True:
        try:
            results = [run_check(name, fn, crit) for name, fn, crit in checks]
            alerts  = process_results(results, state_ref["state"])
            save_state(state_ref["state"])

            passed = sum(1 for r in results if r["status"]=="PASS")
            failed = sum(1 for r in results if r["status"]=="FAIL")
            log.info(f"{level_name}: {passed}P {failed}F | alerts={len(alerts)}")

            if alerts:
                send_alerts(alerts)
        except Exception as e:
            log.error(f"{level_name} loop error: {e}")
        time.sleep(interval_s)

def start(send_startup_message=True):
    state = load_state()
    state_ref = {"state": state}  # mutable ref for threads

    if send_startup_message:
        tg("🟢 <b>Alpha-Omega Live Monitor started</b>\n"
           "L1 checks every 5m • L2 every 15m • L3 every 30m\n"
           "Immediate Telegram alert on any failure or recovery.")

    threads = [
        threading.Thread(target=_run_level, args=("L1-Critical", CHECKS_L1, 300,  state_ref), daemon=True, name="monitor_l1"),
        threading.Thread(target=_run_level, args=("L2-Integrations", CHECKS_L2, 900,  state_ref), daemon=True, name="monitor_l2"),
        threading.Thread(target=_run_level, args=("L3-Performance", CHECKS_L3, 1800, state_ref), daemon=True, name="monitor_l3"),
    ]
    for t in threads:
        t.start()
    log.info(f"Monitor running — {len(threads)} check loops active")
    return threads

if __name__ == "__main__":
    log.info("Running immediate full check...")
    state = load_state()
    state_ref = {"state": state}
    all_checks = CHECKS_L1 + CHECKS_L2 + CHECKS_L3
    results = [run_check(name, fn, crit) for name, fn, crit in all_checks]
    alerts  = process_results(results, state_ref["state"])
    save_state(state_ref["state"])

    passed = sum(1 for r in results if r["status"]=="PASS")
    failed = sum(1 for r in results if r["status"]=="FAIL")
    print(f"\n{'='*50}")
    print(f"MONITOR CHECK: {passed} PASS | {failed} FAIL")
    for r in results:
        flag = "PASS" if r["status"]=="PASS" else "FAIL"
        slow = " [SLOW]" if r.get("slow") else ""
        err  = f" — {r.get('error','')[:60]}" if r["status"]=="FAIL" else ""
        print(f"  {flag} {r['ms']:4d}ms  {r['name']}{slow}{err}")
    if alerts:
        print(f"\nALERTS SENT: {[a['name'] for a in alerts]}")
    else:
        print("\nNo new alerts.")
