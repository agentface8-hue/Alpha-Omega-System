import sys, os
sys.path.insert(0, r"C:\Users\asus\Alpha-Omega-System")
os.chdir(r"C:\Users\asus\Alpha-Omega-System")
from dotenv import load_dotenv
load_dotenv()
import core.signal_store as ss
import core.portfolio_store as ps

active = ss.load_active()
closed = ss.load_closed()
wins = [s for s in closed if float(s.get("pnl_pct") or 0) > 0]
losses = [s for s in closed if float(s.get("pnl_pct") or 0) <= 0]
pnls = [float(s.get("pnl_pct") or 0) for s in closed]

print("=" * 45)
print("ALPHA-OMEGA SYSTEM PERFORMANCE CHECK")
print("=" * 45)
print(f"\nSIGNAL TRACKER v2.0")
print(f"  Active signals : {len(active)}")
print(f"  Closed signals : {len(closed)}")
if closed:
    gp = sum(p for p in pnls if p > 0)
    gl = abs(sum(p for p in pnls if p < 0))
    pf = round(gp/gl, 2) if gl else 999
    wr = round(len(wins)/len(closed)*100, 1)
    ap = round(sum(pnls)/len(pnls), 2)
    print(f"  Win Rate       : {wr}%")
    print(f"  Avg P&L        : {ap}%")
    print(f"  Profit Factor  : {pf}")
    print(f"  Wins / Losses  : {len(wins)} / {len(losses)}")
    print(f"\n  Last 5 closed trades:")
    recent = sorted(closed, key=lambda x: str(x.get("close_time","")), reverse=True)[:5]
    for s in recent:
        p = float(s.get("pnl_pct") or 0)
        sign = "+" if p > 0 else ""
        print(f"    {s.get('symbol','?'):6} | {s.get('status','?'):16} | {sign}{p:.1f}% | {str(s.get('close_time',''))[:10]}")

state = ps.load_state()
positions = ps.load_positions()
open_pos = [p for p in positions if p.get("status") == "OPEN"]
closed_pos = [p for p in positions if p.get("status") == "CLOSED"]

print(f"\nPORTFOLIO ($25K paper)")
print(f"  Total P&L  : ${float(state.get('total_pnl',0)):.0f} ({float(state.get('total_pnl_pct',0)):.2f}%)")
print(f"  Realized   : ${float(state.get('realized_pnl',0)):.0f}")
print(f"  Unrealized : ${float(state.get('unrealized_pnl',0)):.0f}")
print(f"  Win Rate   : {float(state.get('win_rate',0)):.0f}%")
print(f"  Open       : {len(open_pos)} / 5 slots")
if open_pos:
    print(f"\n  Open positions:")
    for p in open_pos:
        pn = float(p.get("pnl_pct") or 0)
        sign = "+" if pn > 0 else ""
        print(f"    {p.get('symbol','?'):6} | {sign}{pn:.2f}% | Entry: ${p.get('entry_price','?')}")
