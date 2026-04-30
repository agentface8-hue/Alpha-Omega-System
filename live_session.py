"""
LIVE PAPER TRADING SESSION — Alpha-Omega System
"""
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

from datetime import datetime
from core.portfolio_store import clear_all_positions, load_state, save_state, _DEFAULT_STATE
from core.portfolio_manager import open_position, check_portfolio, get_portfolio
from core.watchlists import get_watchlist
from core.conviction_engine import run_scan
from core.market_data import fetch_market_regime

print("=" * 65)
print("   ALPHA-OMEGA  --  LIVE PAPER TRADING SESSION")
print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 65)

# Clean start
clear_all_positions()
print(f"\n[INIT] Portfolio reset -> $25,000 cash | 5 slots open\n")

# STEP 1 — Market regime
regime = fetch_market_regime()
print(f"[MARKET]  {regime['regime']} | VIX {regime['vix']} | SPY ${regime['spy_close']} ({regime['spy_change_pct']:+.2f}%)")
print()

# STEP 2 — Full scan (skip delisted SQ)
wl = get_watchlist("full_scan")
symbols = [s for s in wl["tickers"] if s != "SQ"]
print(f"[SCAN]  Scanning {len(symbols)} stocks with EMA9/21 + 5-pillar engine...")
scan = run_scan(symbols)

results = scan["results"]
qualified = [r for r in results if not r.get("hard_fail") and r.get("conviction_pct", 0) >= 65]
non_fail  = [r for r in results if not r.get("hard_fail")]

print(f"\n{'Ticker':<7} {'Conv':>5} {'Heat':<9} {'TAS':<5} {'R:R':>4}  {'Entry':>8}  {'TP1':>8}  {'SL':>8}  {'Note'}")
print("-" * 90)
for r in results[:20]:
    if r.get("hard_fail"):
        print(f"{r['ticker']:<7} {'SKIP':>5}  {'--':<9} {'':5}  {'':4}  {'':8}  {'':8}  {'':8}  {r.get('hard_fail_reason','')[:35]}")
    else:
        flag = " <<< TRADE" if r['conviction_pct'] >= 65 else ""
        print(f"{r['ticker']:<7} {r['conviction_pct']:>4}%  {r['heat']:<9} {r['tas']:<5} {r.get('rr',0):>4.1f}  ${r['entry_high']:>7.2f}  ${r['tp1']:>7.2f}  ${r['sl']:>7.2f}{flag}")

print(f"\n[RESULT]  {len(qualified)} qualifying signals (>= 65%) | {len(non_fail)} passed hard filters")

# STEP 3 — Open top 5 positions
print(f"\n{'='*65}")
print(f"   OPENING TOP {min(5, len(qualified))} POSITIONS")
print(f"{'='*65}")

opened = []
for r in qualified[:5]:
    pos = open_position(
        ticker=r["ticker"],
        entry_price=r.get("entry_high", r["last_close"]),
        sl=r["sl"], tp1=r["tp1"], tp2=r["tp2"], tp3=r["tp3"],
        conviction=r["conviction_pct"],
        asset_type="stock",
    )
    if "error" not in pos:
        opened.append((r, pos))
        print(f"  [OPEN]  {r['ticker']:<6}  Entry ${pos['entry_price']:.2f}  "
              f"SL ${pos['sl']:.2f}  TP1 ${pos['tp1']:.2f}  "
              f"Shares {pos['shares']}  Size ${pos['position_size']:,.0f}  "
              f"Risk ${pos['risk_actual']:,.0f}  Conv {r['conviction_pct']}%")
    else:
        print(f"  [SKIP]  {r['ticker']} -- {pos['error']}")

# STEP 4 — Portfolio snapshot
pf = get_portfolio()
s = pf["stats"]
st = pf["state"]
print(f"\n{'='*65}")
print(f"   PORTFOLIO SNAPSHOT  --  {datetime.now().strftime('%H:%M:%S')}")
print(f"{'='*65}")
print(f"  Cash:          ${st['cash']:>10,.2f}")
print(f"  In positions:  ${st['total_value'] - st['cash']:>10,.2f}")
print(f"  Total value:   ${st['total_value']:>10,.2f}")
print(f"  Open slots:    {5 - s['open_count']}/5")
print(f"\n  Positions open:")
for p in pf["open_positions"]:
    print(f"    {p['ticker']:<6}  {p['shares']} shares @ ${p['entry_price']:.2f}  "
          f"TP1: ${p['tp1']:.2f}  SL: ${p['sl']:.2f}  Risk: ${p['risk_actual']:.0f}")

print(f"\n[STATUS]  {len(opened)} positions open. Monitoring begins...")
print(f"\nNext: Run check_prices in 30-60 min to see P&L updates.")
print(f"Auto-exits will trigger when TP1/TP2/TP3 or SL is hit.")
