"""
cowork_daily_summary.py — Daily 5 PM Cyprus trade summary.
Reads today's closed trades from data/trade_log.csv and outputs
a formatted summary block that the Cowork agent sends via Gmail.

Usage: python cowork_daily_summary.py
Output: prints JSON summary to stdout for the agent to use.
"""

import sys, os, io, json, datetime, csv
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

# ── Date context ─────────────────────────────────────────────────────────────
cyprus_tz = pytz.timezone("Asia/Nicosia")
now_cy    = datetime.datetime.now(cyprus_tz)
today_utc = datetime.datetime.utcnow().strftime("%Y-%m-%d")
today_cy  = now_cy.strftime("%Y-%m-%d")

CSV_PATH = r'C:\Users\asus\Alpha-Omega-System\data\trade_log.csv'


def load_trades(date_prefix: str) -> list:
    if not os.path.exists(CSV_PATH):
        return []
    trades = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("Date", "").startswith(date_prefix):
                trades.append(row)
    return trades


def load_all_trades() -> list:
    if not os.path.exists(CSV_PATH):
        return []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def safe_float(v, default=0.0):
    try:
        return float(v) if v not in ("", None) else default
    except Exception:
        return default


def compute_summary(trades: list, all_trades: list) -> dict:
    if not trades:
        return {
            "date": today_cy,
            "trades_today": 0,
            "total_pnl_dollar": 0,
            "total_pnl_pct": 0,
            "win_rate_today": 0,
            "best_trade": None,
            "worst_trade": None,
            "trades": [],
            "all_time_win_rate": compute_all_time_win_rate(all_trades),
            "all_time_trades": len(all_trades),
        }

    pnl_dollars  = [safe_float(t.get("P&L$"))  for t in trades if t.get("P&L$") not in ("", None)]
    pnl_pcts     = [safe_float(t.get("P&L%"))  for t in trades]
    winners      = [t for t in trades if safe_float(t.get("P&L%")) > 0]
    losers       = [t for t in trades if safe_float(t.get("P&L%")) <= 0]

    total_pnl_dollar = round(sum(pnl_dollars), 2) if pnl_dollars else 0
    total_pnl_pct    = round(sum(pnl_pcts) / len(pnl_pcts), 2) if pnl_pcts else 0
    win_rate         = round(len(winners) / len(trades) * 100, 1) if trades else 0

    # Best and worst
    if pnl_pcts:
        best_idx  = pnl_pcts.index(max(pnl_pcts))
        worst_idx = pnl_pcts.index(min(pnl_pcts))
        best  = trades[best_idx]
        worst = trades[worst_idx]
    else:
        best = worst = None

    # Format trade list
    formatted = []
    for t in sorted(trades, key=lambda x: safe_float(x.get("P&L%")), reverse=True):
        pct  = safe_float(t.get("P&L%"))
        dol  = t.get("P&L$", "")
        dol_str = f"  ${safe_float(dol):+.2f}" if dol not in ("", None) else ""
        formatted.append({
            "ticker":    t.get("Ticker", ""),
            "direction": t.get("Direction", "LONG"),
            "entry":     safe_float(t.get("Entry")),
            "exit":      safe_float(t.get("Exit")),
            "pnl_pct":   pct,
            "pnl_dollar":safe_float(dol) if dol not in ("", None) else None,
            "exit_reason": t.get("Exit Reason", ""),
            "conviction": safe_float(t.get("Conviction%")),
            "regime":    t.get("Regime", ""),
        })

    return {
        "date":              today_cy,
        "trades_today":      len(trades),
        "wins_today":        len(winners),
        "losses_today":      len(losers),
        "total_pnl_dollar":  total_pnl_dollar,
        "total_pnl_pct":     total_pnl_pct,
        "win_rate_today":    win_rate,
        "best_trade":        {"ticker": best.get("Ticker"), "pnl_pct": safe_float(best.get("P&L%")),
                              "exit_reason": best.get("Exit Reason")} if best else None,
        "worst_trade":       {"ticker": worst.get("Ticker"), "pnl_pct": safe_float(worst.get("P&L%")),
                              "exit_reason": worst.get("Exit Reason")} if worst else None,
        "trades":            formatted,
        "all_time_win_rate": compute_all_time_win_rate(all_trades),
        "all_time_trades":   len(all_trades),
    }


def compute_all_time_win_rate(all_trades: list) -> float:
    if not all_trades:
        return 0.0
    winners = [t for t in all_trades if safe_float(t.get("P&L%")) > 0]
    return round(len(winners) / len(all_trades) * 100, 1)


def format_email_html(s: dict) -> str:
    """Format the summary as clean HTML for Gmail."""
    win_emoji = "🟢" if s["win_rate_today"] >= 50 else "🔴"
    pnl_color = "color:#22c55e" if s["total_pnl_dollar"] >= 0 else "color:#ef4444"
    pnl_sign  = "+" if s["total_pnl_dollar"] >= 0 else ""

    trade_rows = ""
    for t in s["trades"]:
        pct_color = "#22c55e" if t["pnl_pct"] >= 0 else "#ef4444"
        pct_sign  = "+" if t["pnl_pct"] >= 0 else ""
        dol_str   = f" / ${t['pnl_dollar']:+.2f}" if t["pnl_dollar"] is not None else ""
        trade_rows += f"""
        <tr>
          <td style="padding:6px 8px;font-weight:600">{t['ticker']}</td>
          <td style="padding:6px 8px">${t['entry']:.2f}</td>
          <td style="padding:6px 8px">${t['exit']:.2f}</td>
          <td style="padding:6px 8px;color:{pct_color};font-weight:600">{pct_sign}{t['pnl_pct']:.2f}%{dol_str}</td>
          <td style="padding:6px 8px">{t['exit_reason']}</td>
          <td style="padding:6px 8px">{int(t['conviction'])}%</td>
          <td style="padding:6px 8px;font-size:11px;color:#888">{t['regime']}</td>
        </tr>"""

    best_str  = f"{s['best_trade']['ticker']} ({s['best_trade']['pnl_pct']:+.2f}% via {s['best_trade']['exit_reason']})"  if s.get("best_trade") else "—"
    worst_str = f"{s['worst_trade']['ticker']} ({s['worst_trade']['pnl_pct']:+.2f}% via {s['worst_trade']['exit_reason']})" if s.get("worst_trade") else "—"

    no_trades_msg = ""
    if s["trades_today"] == 0:
        no_trades_msg = "<p style='color:#888;font-style:italic'>No positions closed today.</p>"

    return f"""
<div style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto">
  <h2 style="background:#111;color:#fff;padding:16px 20px;margin:0;border-radius:8px 8px 0 0">
    📊 Alpha-Omega Daily Summary — {s['date']}
  </h2>

  <div style="background:#1a1a1a;color:#fff;padding:16px 20px;display:flex;gap:32px;border-bottom:1px solid #333">
    <div>
      <div style="font-size:12px;color:#888;text-transform:uppercase">Closed Today</div>
      <div style="font-size:24px;font-weight:700">{s['trades_today']} trade{'s' if s['trades_today']!=1 else ''}</div>
    </div>
    <div>
      <div style="font-size:12px;color:#888;text-transform:uppercase">Total P&amp;L</div>
      <div style="font-size:24px;font-weight:700;{pnl_color}">{pnl_sign}${s['total_pnl_dollar']:.2f}</div>
    </div>
    <div>
      <div style="font-size:12px;color:#888;text-transform:uppercase">Win Rate Today</div>
      <div style="font-size:24px;font-weight:700">{win_emoji} {s['win_rate_today']:.0f}%</div>
    </div>
    <div>
      <div style="font-size:12px;color:#888;text-transform:uppercase">All-Time W/R</div>
      <div style="font-size:24px;font-weight:700">{s['all_time_win_rate']:.0f}% <span style="font-size:14px;color:#888">({s['all_time_trades']} trades)</span></div>
    </div>
  </div>

  {"" if not s["best_trade"] else f'''
  <div style="background:#0f2d1f;padding:10px 20px;border-left:4px solid #22c55e">
    🏆 Best: <b>{best_str}</b>
  </div>
  <div style="background:#2d0f0f;padding:10px 20px;border-left:4px solid #ef4444">
    📉 Worst: <b>{worst_str}</b>
  </div>'''}

  <div style="padding:20px">
    {no_trades_msg}
    {"" if not s["trades"] else f'''
    <table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead>
        <tr style="background:#f5f5f5;text-align:left">
          <th style="padding:8px">Ticker</th>
          <th style="padding:8px">Entry</th>
          <th style="padding:8px">Exit</th>
          <th style="padding:8px">P&amp;L</th>
          <th style="padding:8px">Reason</th>
          <th style="padding:8px">Conv%</th>
          <th style="padding:8px">Regime</th>
        </tr>
      </thead>
      <tbody>{trade_rows}</tbody>
    </table>'''}
  </div>

  <div style="background:#f9f9f9;padding:12px 20px;font-size:11px;color:#888;border-top:1px solid #eee;border-radius:0 0 8px 8px">
    Alpha-Omega System | Generated {now_cy.strftime("%Y-%m-%d %H:%M")} Cyprus time
    | <a href="https://docs.google.com/spreadsheets/d/1G5f1AePhWKJEMJKmfHj1genbr18LMdlCWPsoBJC2ZxM/edit">View Full Trade Log</a>
  </div>
</div>
"""


if __name__ == "__main__":
    today_trades = load_trades(today_cy)
    # Also check UTC date in case of timezone edge
    if not today_trades:
        today_trades = load_trades(today_utc)

    all_trades = load_all_trades()
    summary    = compute_summary(today_trades, all_trades)
    html_body  = format_email_html(summary)

    # Output to stdout for the Cowork agent to use
    output = {
        "summary":    summary,
        "html_body":  html_body,
        "subject":    f"Alpha-Omega Daily Summary — {today_cy} | "
                      f"{summary['trades_today']} trades | "
                      f"P&L: {'+'if summary['total_pnl_dollar']>=0 else ''}${summary['total_pnl_dollar']:.2f} | "
                      f"WR: {summary['win_rate_today']:.0f}%",
        "to_email":   "ipurchesinfo@gmail.com",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
