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

from core.portfolio_manager import check_portfolio, get_portfolio
from datetime import datetime

print(f"[{datetime.now().strftime('%H:%M:%S')}] Running price check...")
result = check_portfolio()
pf = result["portfolio"]
s  = pf["stats"]
st = pf["state"]

print(f"\nPortfolio Value: ${st['total_value']:,.2f}")
print(f"Total P&L:  {'+' if s['total_pnl']>=0 else ''}{s['total_pnl']:,.2f}  ({s['total_pnl_pct']:+.2f}%)")
print(f"Unrealized: {'+' if s['total_unrealized_pnl']>=0 else ''}{s['total_unrealized_pnl']:,.2f}")
print(f"Cash: ${st['cash']:,.2f}\n")

for p in pf["open_positions"]:
    curr = p.get("current_price", p["entry_price"])
    upnl = p.get("unrealized_pnl", 0)
    pct  = p.get("unrealized_pnl_pct", 0)
    tp1h = " [TP1 HIT]" if p.get("tp1_hit") else ""
    print(f"  {p['ticker']:<6} ${curr:<8.2f}  Entry ${p['entry_price']:.2f}  "
          f"P&L: {'+' if upnl>=0 else ''}{upnl:.2f} ({pct:+.2f}%)  "
          f"SL:${p['sl']:.2f}  TP1:${p['tp1']:.2f}{tp1h}")

exits = [u for u in result.get("updates",[]) if u.get("action")]
if exits:
    print("\nEXITS THIS CHECK:")
    for ex in exits:
        print(f"  {ex['ticker']}  {ex['action']}")
