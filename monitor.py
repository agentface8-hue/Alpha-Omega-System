"""Price monitor — checks P&L every 30 seconds, 10 rounds"""
import sys, os, io, time
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

ROUNDS = 20
WAIT   = 60  # seconds between checks

print(f"\n{'='*65}")
print(f"   PRICE MONITOR  --  {ROUNDS} checks x {WAIT}s intervals")
print(f"   Auto-exits fire when TP/SL hit")
print(f"{'='*65}\n")

for i in range(1, ROUNDS + 1):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[CHECK {i:02d}/{ROUNDS}]  {now}  Refreshing prices...")
    
    result = check_portfolio()
    pf     = result["portfolio"]
    s      = pf["stats"]
    state  = pf["state"]

    total_pnl  = s["total_pnl"]
    unrealized = s["total_unrealized_pnl"]
    realized   = s["total_realized_pnl"]
    pnl_pct    = s["total_pnl_pct"]

    print(f"  Portfolio:  ${state['total_value']:>10,.2f}  |  "
          f"P&L: {'+' if total_pnl>=0 else ''}{total_pnl:,.2f} ({pnl_pct:+.2f}%)")
    print(f"  Unrealized: {'+' if unrealized>=0 else ''}{unrealized:,.2f}   "
          f"Realized: {'+' if realized>=0 else ''}{realized:,.2f}   "
          f"Cash: ${state['cash']:,.2f}")
    
    # Show each open position
    for p in pf["open_positions"]:
        curr  = p.get("current_price", p["entry_price"])
        upnl  = p.get("unrealized_pnl", 0)
        pct   = p.get("unrealized_pnl_pct", 0)
        flag  = ""
        if p.get("tp1_hit"): flag = " [TP1 HIT]"
        if p.get("tp2_hit"): flag = " [TP2 HIT]"
        status = "PARTIAL" if p["status"] == "partial" else "OPEN"
        print(f"    {p['ticker']:<6} {status:<8} ${curr:<8.2f}  "
              f"P&L: {'+' if upnl>=0 else ''}{upnl:>7.2f} ({pct:+.2f}%)  "
              f"Shares: {p['shares_remaining']}/{p['shares']}{flag}")
    
    # Show any exits this round
    exits = [u for u in result.get("updates", []) if u.get("action")]
    for ex in exits:
        print(f"    >>> EXIT: {ex['ticker']}  {ex['action']}  P&L: {ex.get('pnl',0):+.2f}")

    if s["open_count"] == 0:
        print(f"\n  All positions closed! Final P&L: {'+' if total_pnl>=0 else ''}{total_pnl:,.2f}")
        break

    # Show closed positions if any
    if pf["closed_positions"]:
        print(f"\n  CLOSED ({len(pf['closed_positions'])} total):")
        for c in pf["closed_positions"][-3:]:
            rpnl = c.get("realized_pnl", 0)
            print(f"    {c['ticker']:<6}  Realized: {'+' if rpnl>=0 else ''}{rpnl:,.2f}")

    print()
    if i < ROUNDS:
        time.sleep(WAIT)

print(f"\n{'='*65}")
print(f"   SESSION COMPLETE")
pf = get_portfolio()
s  = pf["stats"]
print(f"   Total P&L:  {'+' if s['total_pnl']>=0 else ''}{s['total_pnl']:,.2f} ({s['total_pnl_pct']:+.2f}%)")
print(f"   Win Rate:   {s['win_rate']}%  |  Closed: {s['total_closed']}")
print(f"   Final value: ${pf['state']['total_value']:,.2f}")
print(f"{'='*65}")
