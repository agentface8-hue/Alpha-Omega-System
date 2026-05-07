import os, sys
sys.path.insert(0, r'C:\Users\asus\Alpha-Omega-System')
for line in open(r'C:\Users\asus\Alpha-Omega-System\.env'):
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ[k.strip()] = v.strip()
from core.telegram_alerts import _send
_send('Morning briefing FAILED - NameError: lr_slope not defined in conviction_engine.py line 335. Check _build_result().')
print("Alert sent.")
