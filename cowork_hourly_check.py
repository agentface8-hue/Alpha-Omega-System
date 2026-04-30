"""
Cowork hourly portfolio check.
Refreshes prices, fires any TP/SL exits, alerts on Telegram for any action this round.
Called by the every-30-min scheduled task during US market hours.
Idempotent: safe to call repeatedly. If no positions or no changes, sends nothing.
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

import pytz

# DST guard — bail if outside 9:00 AM – 4:30 PM ET window
et_now = datetime.datetime.now(pytz.timezone('US/Eastern'))
if et_now.weekday() >= 5:
    print(f"[{et_now:%H:%M ET}] Weekend — skip")
    sys.exit(0)
mins = et_now.hour * 60 + et_now.minute
if not (9 * 60 <= mins <= 16 * 60 + 30):
    print(f"[{et_now:%H:%M ET}] Outside 09:00–16:30 ET window — skip")
    sys.exit(0)

try:
    from core.portfolio_manager import check_portfolio
    from core.telegram_alerts import _send

    print(f"[{et_now:%H:%M ET}] Running portfolio check...")
    result = check_portfolio()
    pf = result["portfolio"]
    s = pf["stats"]
    state = pf["state"]
    updates = result.get("updates", [])
    actions = [u for u in updates if u.get("action")]

    # Always log to console
    print(f"  Open: {s['open_count']}  Total P&L: {s['total_pnl']:+.2f} ({s['total_pnl_pct']:+.2f}%)  Cash: ${state['cash']:,.2f}")
    for p in pf["open_positions"]:
        curr = p.get("current_price", p["entry_price"])
        upnl = p.get("unrealized_pnl", 0)
        pct = p.get("unrealized_pnl_pct", 0)
        print(f"  {p['ticker']:<6} ${curr:<8.2f} P&L:{upnl:+.2f} ({pct:+.2f}%) SL:${p['sl']} TP1:${p['tp1']}")

    # Alert on any TP/SL action this round
    if actions:
        lines = [f"<b>EXITS — {et_now:%H:%M ET}</b>"]
        for u in actions:
            lines.append(
                f"  {u['ticker']:<6} {u['action']}  "
                f"P&L: {u.get('pnl', 0):+.2f}"
            )
        lines.append("")
        lines.append(f"Portfolio: ${state['total_value']:,.2f}  "
                     f"Realized: {s['total_realized_pnl']:+.2f}  "
                     f"Open: {s['open_count']}")
        _send("\n".join(lines))
        print(f"  -> Sent Telegram alert for {len(actions)} exit(s)")

    # Also alert on price errors (yfinance flake, ticker delisted, etc.)
    errors = [u for u in updates if u.get("status") == "price_error"]
    if errors:
        msg = f"<b>Price fetch failed at {et_now:%H:%M ET}</b>\n"
        msg += ", ".join(u["ticker"] for u in errors)
        _send(msg)
        print(f"  -> Sent Telegram alert for {len(errors)} price error(s)")

    # End-of-session summary (right after market close, only fires once)
    if et_now.hour == 16 and et_now.minute >= 0 and et_now.minute < 5:
        _send(
            f"<b>Market Close Summary — {et_now:%Y-%m-%d}</b>\n"
            f"Total P&L: {s['total_pnl']:+.2f} ({s['total_pnl_pct']:+.2f}%)\n"
            f"Realized: {s['total_realized_pnl']:+.2f}  Unrealized: {s['total_unrealized_pnl']:+.2f}\n"
            f"Open: {s['open_count']}  Closed today: {s.get('total_closed', 0)}\n"
            f"Win rate: {s.get('win_rate', 0)}%\n"
            f"Portfolio value: ${state['total_value']:,.2f}\n"
            f"Cash: ${state['cash']:,.2f}"
        )
        print("  -> Sent end-of-day summary")

except Exception:
    err_text = traceback.format_exc()
    print(err_text)
    try:
        from core.telegram_alerts import _send
        _send(f"<b>Hourly check FAILED at {et_now:%H:%M ET}</b>\n<pre>{err_text[:1500]}</pre>")
    except Exception:
        pass
    sys.exit(1)
