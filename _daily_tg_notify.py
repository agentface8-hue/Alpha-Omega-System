import urllib.request, urllib.parse

token = "8246500243:AAFXsq94Fia3RimL4_Q-AM6sdDJpZNoxTYM"
chat_id = "5812682751"

date = "2026-05-14"
trades = 0
pnl = 0.0
wr = 0.0
all_time_wr = 0.0
all_time_trades = 1
best = ""
worst = ""

sign = "+" if pnl >= 0 else ""
emoji = "🟢" if pnl >= 0 else "🔴"
best_line = f"\n🏆 Best: {best}" if best else ""
worst_line = f"\n📉 Worst: {worst}" if worst else ""

msg = (
    f"{emoji} *Alpha-Omega Daily Summary — {date}*\n"
    f"📊 Trades closed: {trades}\n"
    f"💰 P&L: {sign}${pnl:.2f}\n"
    f"🎯 Win rate today: {wr:.0f}%"
    f"{best_line}"
    f"{worst_line}\n"
    f"📈 All-time W/R: {all_time_wr:.0f}% ({all_time_trades} trades)\n"
    f"🔗 [Trade Log](https://docs.google.com/spreadsheets/d/1G5f1AePhWKJEMJKmfHj1genbr18LMdlCWPsoBJC2ZxM/edit)"
)

params = urllib.parse.urlencode({"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"})
url = f"https://api.telegram.org/bot{token}/sendMessage"
data = params.encode()
req = urllib.request.Request(url, data=data)
with urllib.request.urlopen(req, timeout=10) as r:
    print(r.read().decode())
print("Telegram sent.")
