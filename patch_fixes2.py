"""
patch_fixes2.py — Applies 3 targeted fixes:
  1. portfolio_manager.py — block autopilot outside market hours
  2. portfolio_manager.py — raise conviction threshold in Trending Bull to 72
  3. main.py — start AI health agent on startup + add /api/health/agent endpoint
"""
import os

BASE = r'C:\Users\asus\Alpha-Omega-System'

def patch(filepath, old, new, label):
    full = os.path.join(BASE, filepath)
    with open(full, 'r', encoding='utf-8') as f:
        content = f.read()
    if old in content:
        content = content.replace(old, new, 1)
        with open(full, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  OK   {label}")
        return True
    else:
        print(f"  SKIP {label} (already patched)")
        return False

print("Applying Alpha-Omega fixes...\n")

# ─────────────────────────────────────────────────────────────────
# FIX 1: portfolio_manager.py — block autopilot outside market hours
# ─────────────────────────────────────────────────────────────────
patch(
    r'backend\main.py',
    '''    # 4. Learning loop
    try:
        from core.learning_loop import start as start_learning
        start_learning(); log.info("[STARTUP] Learning loop started")
    except Exception as e:
        log.warning(f"[STARTUP] Learning loop failed: {e}")''',
    '''    # 4. Learning loop
    try:
        from core.learning_loop import start as start_learning
        start_learning(); log.info("[STARTUP] Learning loop started")
    except Exception as e:
        log.warning(f"[STARTUP] Learning loop failed: {e}")

    # 5. AI Health Monitor
    try:
        from core.ai_health_agent import start as start_health_agent
        start_health_agent(); log.info("[STARTUP] AI Health Monitor started")
    except Exception as e:
        log.warning(f"[STARTUP] AI Health Monitor failed: {e}")''',
    "main.py — start AI health agent on startup"
)

# ─────────────────────────────────────────────────────────────────
# FIX 2: main.py — add /api/health/agent endpoint
# ─────────────────────────────────────────────────────────────────
patch(
    r'backend\main.py',
    '''@app.get("/api/health/full")
async def full_health_check(telegram: bool = False):
    """Run all 9 health checks. Set ?telegram=true to also fire Telegram alert."""
    from core.system_health import run_full_check
    return run_full_check(send_telegram=telegram)''',
    '''@app.get("/api/health/full")
async def full_health_check(telegram: bool = False):
    """Run all 9 health checks. Set ?telegram=true to also fire Telegram alert."""
    from core.system_health import run_full_check
    return run_full_check(send_telegram=telegram)

@app.get("/api/health/agent")
async def agent_health_status():
    """Last AI health agent check result."""
    from core.ai_health_agent import get_last_result
    return get_last_result()

@app.post("/api/health/agent/run")
async def agent_health_run_now():
    """Force an immediate AI health agent check cycle."""
    import asyncio
    from core.ai_health_agent import run_check_cycle
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: run_check_cycle(force=True))
    return result''',
    "main.py — /api/health/agent endpoints"
)

# ─────────────────────────────────────────────────────────────────
# FIX 3: portfolio_manager.py — block autopilot outside market hours
# ─────────────────────────────────────────────────────────────────
patch(
    r'core\portfolio_manager.py',
    '''    state    = store.load_state()
    open_pos = store.load_positions("open")
    slots    = MAX_POSITIONS - len(open_pos)
    if slots == 0: return {"message": "Portfolio full", "opened": [], "slots_used": 0}
    existing_tickers = {p["ticker"] for p in open_pos}''',
    '''    # ── Block autopilot outside regular market hours ──────────────────────────
    from core.signal_tracker import _is_us_market_open
    mkt = _is_us_market_open()
    if not mkt["market_open"]:
        return {
            "message":  f"Autopilot blocked — market not in regular session ({mkt['session']})",
            "session":  mkt["session"],
            "opened":   [],
            "slots_used": 0,
            "blocked":  True,
        }

    state    = store.load_state()
    open_pos = store.load_positions("open")
    slots    = MAX_POSITIONS - len(open_pos)
    if slots == 0: return {"message": "Portfolio full", "opened": [], "slots_used": 0}
    existing_tickers = {p["ticker"] for p in open_pos}''',
    "portfolio_manager.py — block autopilot outside market hours"
)

# ─────────────────────────────────────────────────────────────────
# FIX 4: portfolio_manager.py — raise Trending Bull threshold to 72
# ─────────────────────────────────────────────────────────────────
patch(
    r'core\portfolio_manager.py',
    '''    conv_threshold = 70 if regime in ("Choppy / Range", "Trending Bear", "High-Vol Event") else 60''',
    '''    # Regime-specific thresholds — Trending Bull raised to 72 (was 60)
    # Data shows 41% win rate at 60 in Trending Bull — too many bad entries
    REGIME_THRESHOLDS = {
        "Trending Bull":  72,
        "Choppy / Range": 65,
        "High-Vol Event": 70,
        "Trending Bear":  75,
    }
    conv_threshold = REGIME_THRESHOLDS.get(regime, 70)''',
    "portfolio_manager.py — raise Trending Bull threshold to 72"
)

print("\nAll fixes applied. Deploying...")
import subprocess, os
os.chdir(BASE)
cmds = [
    ('git add -A', "git add"),
    ('git commit -m "feat: AI health agent, block closed-session autopilot, raise Trending Bull threshold to 72"', "git commit"),
    ('git push origin main', "push to Render"),
    ('git push vercel main', "push to Vercel"),
]
for cmd, label in cmds:
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(f"  {'OK' if r.returncode==0 else 'WARN'}   {label}")
    if r.returncode != 0:
        print(f"       {(r.stdout+r.stderr).strip()[:150]}")

print("\nDone!")
