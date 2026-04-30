"""
Cowork weekly self-calibration.
Reads closed signals, analyzes win-rate per conviction bracket, adjusts thresholds.
learning_loop.run_once() handles its own Telegram summary.
"""
import sys, os, io, datetime, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r'C:\Users\asus\Alpha-Omega-System')

env_path = r'C:\Users\asus\Alpha-Omega-System\.env'
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ[k.strip()] = v.strip()

try:
    from core.learning_loop import run_once
    from core.telegram_alerts import _send

    _send(f"<b>Sunday Self-Calibration starting</b>\nReviewing closed signals & retuning thresholds...")
    result = run_once()
    print(f"Calibration result: {result}")

    if result.get("status") == "insufficient_data":
        _send(f"Calibration deferred: {result.get('message')}")

except Exception:
    err = traceback.format_exc()
    print(err)
    try:
        from core.telegram_alerts import _send
        _send(f"<b>Weekly calibration FAILED</b>\n<pre>{err[:1500]}</pre>")
    except Exception:
        pass
    sys.exit(1)
