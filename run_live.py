import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, 'C:\\Users\\asus\\Alpha-Omega-System')

env_path = 'C:\\Users\\asus\\Alpha-Omega-System\\.env'
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ[k.strip()] = v.strip()

from core.telegram_alerts import _send
from datetime import datetime

# Step 1 — Market Regime
print("Fetching regime...")
from core.market_data import fetch_market_regime
from core.regime_engine import get_strategy_mode
regime = fetch_market_regime()
mode   = get_strategy_mode(regime)
_send(
    f"<b>Step 1/3 — Market Regime</b>\n"
    f"Regime: <b>{regime['regime']}</b>\n"
    f"VIX: <b>{regime['vix']}</b>\n"
    f"SPY: ${regime['spy_close']} ({regime['spy_change_pct']:+.2f}%)\n"
    f"Mode: <b>{mode['label']}</b>\n"
    f"{mode['description']}\n"
    f"Longs: {'YES' if mode['long_enabled'] else 'NO'}  Shorts: {'YES' if mode['short_enabled'] else 'NO'}"
)
print("Regime sent")

# Step 2 — Dual Scan
print("Running dual scan (this takes ~2 min)...")
_send("Running dual scan on 29 stocks... this takes ~90 seconds")

from core.printing_scanner import run_dual_scan
scan   = run_dual_scan()
longs  = scan.get("longs", [])[:5]
shorts = scan.get("shorts", [])[:5]

lines = [f"<b>Step 2/3 — Dual Scan Results</b>\n{scan['market_header']}\n"]
if longs:
    lines.append("LONG SIGNALS:")
    for r in longs:
        lines.append(f"  {r['ticker']} {r['conviction_pct']}% | Entry ${r.get('entry_high',r['last_close']):.2f} | TP1 ${r['tp1']:.2f} | SL ${r['sl']:.2f} | R:R {r.get('rr',0):.1f}")
if shorts:
    lines.append("\nSHORT SIGNALS:")
    for r in shorts:
        lines.append(f"  {r['ticker']} {r['conviction_pct']}% | Entry ${r.get('entry',r['last_close']):.2f} | TP1 ${r['tp1']:.2f} | SL ${r['sl']:.2f}")
_send("\n".join(lines))
print("Scan sent")

# Step 3 — Autopilot
print("Running autopilot...")
_send("Running autopilot — filling all slots with top signals...")

from core.printing_store import clear_all
clear_all()

from core.printing_portfolio import autopilot_dual
result = autopilot_dual()
opened = result.get("opened", [])

if opened:
    lines = [f"<b>Step 3/3 — Autopilot Filled {len(opened)} Slots</b>\n"]
    total_risk = 0
    for o in opened:
        lines.append(f"  {'LONG' if o['direction']=='long' else 'SHORT'} {o['ticker']} @ ${o['entry']:.2f}  Conv:{o['conviction']}%  Shares:{o['shares']}")
        total_risk += o.get('shares', 0)
    lines.append(f"\nAll positions live. Auto-refresh monitoring every 30s.")
    lines.append(f"I will alert you when TP1/TP2/TP3 or SL is hit.")
    _send("\n".join(lines))
else:
    msg = result.get("message", "No qualifying signals")
    _send(f"<b>Step 3/3 — Autopilot</b>\n{msg}\nTry again after market open (9:30 AM ET)")

# Final status
from core.printing_portfolio import get_portfolio
pf   = get_portfolio()
stat = pf['stats']
st   = pf['state']
_send(
    f"<b>SYSTEM FULLY ACTIVE</b>\n"
    f"Portfolio: ${st['total_value']:,.2f}\n"
    f"Open positions: {stat['open_count']}/5\n"
    f"Cash: ${stat['cash']:,.2f}\n"
    f"Auto-monitoring every 30s\n"
    f"I will message you on every exit.\n"
    f"Dashboard: alpha-omega-ngfw.vercel.app"
)
print("All done.")
