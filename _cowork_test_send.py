import os, sys
sys.path.insert(0, '.')
for line in open('.env'):
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ[k.strip()] = v.strip()
from core.telegram_alerts import _send
_send('<b>Cowork test starting</b> — running full briefing pipeline now')
print('SENT')
