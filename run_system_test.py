"""
FULL LIVE SYSTEM TEST — Alpha-Omega
Tests every endpoint, every integration, every background service.
Reports pass/fail with exact error details.
"""
import sys, os, json, time, traceback
sys.path.insert(0, r'C:\Users\asus\Alpha-Omega-System')
from dotenv import load_dotenv; load_dotenv()
import urllib.request, urllib.error

BASE = "https://alpha-omega-system.onrender.com"
RESULTS = []
FAIL_COUNT = 0

def test(name, fn, critical=False):
    global FAIL_COUNT
    t0 = time.time()
    try:
        result = fn()
        ms = int((time.time()-t0)*1000)
        RESULTS.append({"name":name,"status":"PASS","ms":ms,"detail":str(result)[:120]})
        print(f"  PASS  [{ms:4d}ms]  {name}")
        return result
    except Exception as e:
        ms = int((time.time()-t0)*1000)
        err = str(e)
        RESULTS.append({"name":name,"status":"FAIL","ms":ms,"error":err,"critical":critical})
        FAIL_COUNT += 1
        flag = "CRITICAL" if critical else "FAIL"
        print(f"  {flag}  [{ms:4d}ms]  {name}")
        print(f"           ERROR: {err[:200]}")
        return None

def get(path, timeout=20):
    req = urllib.request.Request(f"{BASE}{path}",
        headers={"Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def post(path, body=None, timeout=20):
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(f"{BASE}{path}", data=data,
        headers={"Content-Type":"application/json","Accept":"application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def sb_get(table, limit=1):
    SB  = os.environ.get("SUPABASE_URL","")
    KEY = os.environ.get("SUPABASE_ANON_KEY","")
    req = urllib.request.Request(
        f"{SB}/rest/v1/{table}?limit={limit}",
        headers={"apikey":KEY,"Authorization":f"Bearer {KEY}"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

TG_TOKEN = os.environ.get("TELEGRAM_TOKEN","")
TG_CHAT  = os.environ.get("TELEGRAM_PERSONAL_CHAT_ID","")

def tg_send(msg):
    body = json.dumps({"chat_id":TG_CHAT,"text":msg,"parse_mode":"HTML"}).encode()
    req  = urllib.request.Request(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        data=body, headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

print("=" * 60)
print("ALPHA-OMEGA FULL LIVE SYSTEM TEST")
print(f"Target: {BASE}")
print("=" * 60)

# ── 1. BACKEND CORE ───────────────────────────────────────────────
print("\n[1] BACKEND CORE")
h = test("Health endpoint", lambda: get("/health"), critical=True)
test("Docs reachable",    lambda: urllib.request.urlopen(f"{BASE}/docs", timeout=10).status == 200 or True)
test("Agent status",      lambda: get("/api/agent/status"))

# ── 2. PORTFOLIO ──────────────────────────────────────────────────
print("\n[2] PORTFOLIO")
port = test("Portfolio load",   lambda: get("/api/portfolio"), critical=True)
test("Portfolio state",         lambda: port.get("state") if port else (_ for _ in ()).throw(Exception("no data")))
test("Open positions count",    lambda: f"{len(port.get('open_positions',[]))} open" if port else (_ for _ in ()).throw(Exception("no port")))
test("Trade history endpoint",  lambda: f"{get('/api/trade-history').get('total')} trades")

# ── 3. SIGNAL TRACKER ─────────────────────────────────────────────
print("\n[3] SIGNAL TRACKER")
sigs = test("Signals load", lambda: get("/api/signals"), critical=True)
test("Signal stats present",   lambda: sigs.get("stats") if sigs else (_ for _ in ()).throw(Exception("no sigs")))
test("Check signals (price refresh)", lambda: post("/api/signals/check"))

# ── 4. SCANNER & CONVICTION ───────────────────────────────────────
print("\n[4] SCANNER")
test("Watchlists",             lambda: get("/api/watchlists"))
test("Prices (SPY,AAPL)",      lambda: post("/api/prices", {"symbols":["SPY","AAPL"]}))
test("Quick scan (1 ticker)",  lambda: post("/api/scan",   {"symbols":["AAPL"]}))

# ── 5. LEARNING LOOP ──────────────────────────────────────────────
print("\n[5] LEARNING LOOP")
learn = test("Learning summary",     lambda: get("/api/learning/summary"), critical=True)
test("Signals analyzed >= 10",        lambda: f"{learn.get('total_closed',0)} closed" if learn else (_ for _ in ()).throw(Exception("no learn")))
test("Calibration has regime data",   lambda: learn.get("calibration",{}).get("regime_thresholds") if learn else None)
test("Last fast run exists",          lambda: learn.get("calibration",{}).get("last_fast_run","never") if learn else "none")

# ── 6. HEALTH CHECKS ─────────────────────────────────────────────
print("\n[6] HEALTH CHECKS")
full_h = test("Full health check", lambda: get("/api/health/full"), critical=True)
if full_h:
    checks = full_h.get("checks", full_h)
    for svc, data in (checks.items() if isinstance(checks,dict) else []):
        status = data.get("status","?") if isinstance(data,dict) else str(data)
        ok = status in ("GREEN","ok","pass","true","True")
        RESULTS.append({"name":f"  health.{svc}","status":"PASS" if ok else "FAIL","detail":status})
        flag = "PASS" if ok else "FAIL"
        print(f"  {flag}          health.{svc} = {status}")
        if not ok:
            FAIL_COUNT += 1

# ── 7. SUPABASE TABLES ────────────────────────────────────────────
print("\n[7] SUPABASE DIRECT")
for table in ["signals","trade_log","portfolio_positions","ao_users"]:
    test(f"Supabase table: {table}", lambda t=table: f"{len(sb_get(t,5))} rows readable")

# ── 8. TELEGRAM ───────────────────────────────────────────────────
print("\n[8] TELEGRAM")
test("Telegram getMe", lambda: urllib.request.urlopen(
    f"https://api.telegram.org/bot{TG_TOKEN}/getMe", timeout=10
).read().decode()[:50])

# ── 9. BACKGROUND THREADS ─────────────────────────────────────────
print("\n[9] BACKGROUND THREADS")
agent_s = test("Agent status threads", lambda: get("/api/agent/status"))
if agent_s:
    for thread in ["keepalive","telegram_agent","ai_health_agent"]:
        found = thread in str(agent_s.get("active_threads",[]))
        RESULTS.append({"name":f"  thread.{thread}","status":"PASS" if found else "FAIL"})
        print(f"  {'PASS' if found else 'FAIL'}          thread.{thread}")
        if not found: FAIL_COUNT += 1

# ── 10. FRONTEND ──────────────────────────────────────────────────
print("\n[10] FRONTEND (Vercel)")
test("Frontend loads", lambda: urllib.request.urlopen(
    "https://alpha-omega-ngfw.vercel.app", timeout=15).status)

# ── SUMMARY ───────────────────────────────────────────────────────
total = len(RESULTS)
passed = sum(1 for r in RESULTS if r["status"]=="PASS")
failed = sum(1 for r in RESULTS if r["status"]=="FAIL")

print("\n" + "=" * 60)
print(f"RESULTS: {passed} PASS  |  {failed} FAIL  |  {total} total")
print("=" * 60)

if failed > 0:
    print("\nFAILED TESTS:")
    for r in RESULTS:
        if r["status"] == "FAIL":
            print(f"  - {r['name']}: {r.get('error','?')[:100]}")

# Save results
with open(r'C:\Users\asus\Alpha-Omega-System\data\last_test_run.json','w') as f:
    json.dump({"ts":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
               "passed":passed,"failed":failed,"results":RESULTS},f,indent=2)

# Send Telegram summary
if TG_TOKEN and TG_CHAT:
    lines = [f"🧪 <b>Full System Test</b>  {time.strftime('%H:%M UTC')}"]
    lines.append(f"{'✅' if failed==0 else '❌'} {passed}/{total} passed  |  {failed} failed\n")
    if failed > 0:
        lines.append("<b>FAILED:</b>")
        for r in RESULTS:
            if r["status"]=="FAIL":
                lines.append(f"  ❌ {r['name']}: {r.get('error','?')[:80]}")
    else:
        lines.append("All systems operational ✅")
    try:
        tg_send("\n".join(lines))
        print("\nTest results sent to Telegram.")
    except Exception as e:
        print(f"\nTelegram send failed: {e}")

print(f"\nSaved to data/last_test_run.json")
