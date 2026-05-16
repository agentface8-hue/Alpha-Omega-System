"""
patch_system.py — applies all fixes to Alpha-Omega in one shot.
Run: python patch_system.py
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
    else:
        print(f"  SKIP {label} (already patched or not found)")

print("Applying Alpha-Omega system fixes...\n")

# ─────────────────────────────────────────────────────────────────
# FIX 1: Telegram 409 — backoff + 10s deploy guard
# ─────────────────────────────────────────────────────────────────
patch(
    r'core\telegram_agent.py',
    'def _poll_loop():\n    global _last_update_id\n    logger.info("[AGENT] Telegram polling loop started")\n    while True:\n        try:\n            updates = _get_updates(_last_update_id + 1)\n            for update in updates:\n                _last_update_id = max(_last_update_id, update.get("update_id", 0))\n                _executor.submit(_handle_message, update)\n        except Exception as e:\n            logger.error(f"[AGENT] Poll error: {e}")\n        time.sleep(4)\n\n\ndef start():\n    logger.info("[AGENT] Deleting webhook before polling...")\n    _delete_webhook()',
    'def _poll_loop():\n    global _last_update_id\n    logger.info("[AGENT] Telegram polling loop started")\n    _consecutive_409 = 0\n    while True:\n        try:\n            updates = _get_updates(_last_update_id + 1)\n            _consecutive_409 = 0\n            for update in updates:\n                _last_update_id = max(_last_update_id, update.get("update_id", 0))\n                _executor.submit(_handle_message, update)\n        except Exception as e:\n            if "409" in str(e):\n                _consecutive_409 += 1\n                wait = min(30, 5 * _consecutive_409)\n                logger.warning(f"[AGENT] 409 Conflict — another instance polling. Waiting {wait}s...")\n                time.sleep(wait)\n                continue\n            else:\n                logger.error(f"[AGENT] Poll error: {e}")\n        time.sleep(4)\n\n\ndef start():\n    # 10s delay: lets old Render instance die before new one polls\n    # Prevents 409 during zero-downtime redeploys on Standard tier\n    logger.info("[AGENT] Waiting 10s before polling (deploy guard)...")\n    time.sleep(10)\n    logger.info("[AGENT] Deleting webhook before polling...")\n    _delete_webhook()',
    "telegram_agent.py — 409 fix + deploy guard"
)

# ─────────────────────────────────────────────────────────────────
# FIX 2: main.py — gc.collect() in background scan thread
# ─────────────────────────────────────────────────────────────────
patch(
    r'backend\main.py',
    'scan_jobs: Dict[str, Any] = {}\n\n\ndef _run_scan_background(job_id: str, symbols: list):',
    'scan_jobs: Dict[str, Any] = {}\n\n\ndef _run_scan_background(job_id: str, symbols: list):\n    import gc as _gc',
    "main.py — import gc in scan background"
)

patch(
    r'backend\main.py',
    '            raw = score_ticker(fetch_ticker_data(sym), regime)\n            results.append(raw)\n            scan_jobs[job_id]["progress"] = f"{i + 1}/{n} stocks scanned"',
    '            raw = score_ticker(fetch_ticker_data(sym), regime)\n            results.append(raw)\n            _gc.collect()  # free DataFrame memory after each ticker\n            scan_jobs[job_id]["progress"] = f"{i + 1}/{n} stocks scanned"',
    "main.py — gc.collect() after each ticker in scan"
)

# ─────────────────────────────────────────────────────────────────
# FIX 3: main.py — /api/memory endpoint
# ─────────────────────────────────────────────────────────────────
patch(
    r'backend\main.py',
    '@app.get("/health")\nasync def health():\n    return {"status": "online", "ts": __import__("datetime").datetime.utcnow().isoformat()}',
    '@app.get("/health")\nasync def health():\n    return {"status": "online", "ts": __import__("datetime").datetime.utcnow().isoformat()}\n\n@app.get("/api/memory")\nasync def memory_status():\n    """Live memory usage — monitor Render instance health."""\n    try:\n        import psutil, os as _os\n        proc = psutil.Process(_os.getpid())\n        mem  = proc.memory_info()\n        vm   = psutil.virtual_memory()\n        rss  = round(mem.rss / 1024**2, 1)\n        limit = 2048  # Standard tier = 2GB\n        return {\n            "process_rss_mb":  rss,\n            "system_used_mb":  round(vm.used / 1024**2, 1),\n            "system_avail_mb": round(vm.available / 1024**2, 1),\n            "system_percent":  vm.percent,\n            "render_limit_mb": limit,\n            "headroom_mb":     round(limit - rss, 1),\n            "status":          "OK" if rss < limit * 0.8 else "WARNING",\n        }\n    except Exception as e:\n        return {"error": str(e)}',
    "main.py — /api/memory endpoint"
)

# ─────────────────────────────────────────────────────────────────
# FIX 4: requirements.txt — add psutil
# ─────────────────────────────────────────────────────────────────
req_path = os.path.join(BASE, 'requirements.txt')
with open(req_path, 'r', encoding='utf-8') as f:
    reqs = f.read()
if 'psutil' not in reqs:
    with open(req_path, 'a', encoding='utf-8') as f:
        f.write('\npsutil\n')
    print("  OK   requirements.txt — added psutil")
else:
    print("  SKIP requirements.txt — psutil already present")

print("\nAll fixes applied. Deploying now...")

# ─────────────────────────────────────────────────────────────────
# DEPLOY
# ─────────────────────────────────────────────────────────────────
import subprocess

os.chdir(BASE)

cmds = [
    ('git add -A',                                                    "git add"),
    ('git commit -m "fix: 409 deploy guard, gc collect, memory endpoint, psutil"', "git commit"),
    ('git push origin main',                                          "push to Render"),
    ('git push vercel main',                                          "push to Vercel"),
]

for cmd, label in cmds:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"  OK   {label}")
    else:
        out = (result.stdout + result.stderr).strip()[:200]
        print(f"  WARN {label}: {out}")

print("\nDone! Deploy triggered on Render + Vercel.")
print("Check: https://alpha-omega-system.onrender.com/api/memory")
