import json, datetime
from pathlib import Path

path = Path(r'C:\Users\asus\Alpha-Omega-System\calibration\calibration_params.json')
cal  = json.loads(path.read_text())

cal['regime_thresholds'] = {
    'Trending Bull':  72,
    'Choppy / Range': 65,
    'High-Vol Event': 70,
    'Trending Bear':  75,
}
cal['march_fix_note'] = 'March 2026 losses from loose initial settings (threshold=60). Fixed 2026-05-16: Trending Bull raised to 72, closed-session blocked.'
cal['last_updated'] = datetime.datetime.utcnow().isoformat()

path.write_text(json.dumps(cal, indent=2))
print('Calibration updated. Regime thresholds:', cal['regime_thresholds'])
