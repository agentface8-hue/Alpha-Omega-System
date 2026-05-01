"""
telegram_alerts.py — Push trading alerts to Telegram.
Sends to the alphaomega group chat only.
"""
import os
import urllib.request
import urllib.parse
import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN   = "8691159247:AAEfGEBQgXBqXvA9RCO67cFCwwtDaFrNRH4"
PERSONAL_CHAT_ID = "5812682751"   # kept for reference / ALLOWED_CHAT_IDS
GROUP_CHAT_ID    = "-5228475615"
CHAT_IDS         = [GROUP_CHAT_ID]  # alerts → group only


def _send(text: str, parse_mode: str = "HTML") -> bool:
    """Send message to all configured chat IDs."""
    success = False
    for chat_id in CHAT_IDS:
        try:
            url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            body = json.dumps({
                "chat_id":    chat_id,
                "text":       text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }).encode()
            req = urllib.request.Request(url, data=body,
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                result = json.loads(r.read().decode())
                if result.get("ok"):
                    success = True
        except Exception as e:
            logger.error(f"Telegram send error to {chat_id}: {e}")
    return success


# ── Alert formatters ────────────────────────────────────────

def alert_signal_created(signal: dict):
    """New turbo signal launched."""
    ticker   = signal.get("ticker", "?")
    entry    = signal.get("entry_price", 0)
    sl       = signal.get("targets", {}).get("sl", 0)
    tp1      = signal.get("targets", {}).get("tp1", 0)
    conv     = signal.get("conviction", 0)
    atype    = signal.get("asset_type", "stock").upper()
    text = (
        f"🚀 <b>NEW SIGNAL — {ticker}</b> ({atype})\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📥 Entry:  <b>${entry}</b>\n"
        f"🛑 SL:     <b>${sl}</b>\n"
        f"🎯 TP1:    <b>${tp1}</b>\n"
        f"💡 Conviction: <b>{conv}%</b>\n"
        f"🕐 {datetime.utcnow().strftime('%H:%M UTC')}"
    )
    return _send(text)


def alert_tp_hit(signal: dict, tp_level: str, price: float):
    """TP1, TP2, or TP3 hit."""
    ticker  = signal.get("ticker", "?")
    entry   = signal.get("entry_price", 0)
    pnl_pct = ((price - entry) / entry * 100) if entry else 0
    emoji   = {"tp1": "🎯", "tp2": "🎯🎯", "tp3": "🏆"}.get(tp_level, "🎯")
    text = (
        f"{emoji} <b>{tp_level.upper()} HIT — {ticker}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Price:  <b>${price:.2f}</b>\n"
        f"📈 P&L:    <b>+{pnl_pct:.1f}%</b>\n"
        f"📥 Entry:  ${entry}\n"
        f"🕐 {datetime.utcnow().strftime('%H:%M UTC')}"
    )
    return _send(text)


def alert_sl_hit(signal: dict, price: float):
    """Stop loss hit."""
    ticker  = signal.get("ticker", "?")
    entry   = signal.get("entry_price", 0)
    pnl_pct = ((price - entry) / entry * 100) if entry else 0
    text = (
        f"🛑 <b>STOPPED OUT — {ticker}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💸 Price:  <b>${price:.2f}</b>\n"
        f"📉 P&L:    <b>{pnl_pct:.1f}%</b>\n"
        f"📥 Entry:  ${entry}\n"
        f"🕐 {datetime.utcnow().strftime('%H:%M UTC')}"
    )
    return _send(text)


def alert_signal_closed(signal: dict, reason: str, price: float):
    """Signal manually closed or timed out."""
    ticker  = signal.get("ticker", "?")
    entry   = signal.get("entry_price", 0)
    pnl_pct = ((price - entry) / entry * 100) if entry else 0
    emoji   = "✅" if pnl_pct > 0 else "❌"
    text = (
        f"{emoji} <b>CLOSED — {ticker}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📌 Reason: <b>{reason}</b>\n"
        f"💰 Exit:   <b>${price:.2f}</b>\n"
        f"📊 P&L:    <b>{'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%</b>\n"
        f"📥 Entry:  ${entry}\n"
        f"🕐 {datetime.utcnow().strftime('%H:%M UTC')}"
    )
    return _send(text)


def alert_autopilot_launched(count: int, asset_type: str = "stocks"):
    """Auto-pilot scan completed."""
    text = (
        f"🤖 <b>AUTO-PILOT LAUNCHED</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 Signals: <b>{count} {asset_type}</b>\n"
        f"🔗 Dashboard: alpha-omega-ngfw.vercel.app\n"
        f"🕐 {datetime.utcnow().strftime('%H:%M UTC')}"
    )
    return _send(text)


def alert_system_online():
    """Backend came online (startup)."""
    text = (
        f"✅ <b>Alpha-Omega System Online</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔗 alpha-omega-ngfw.vercel.app\n"
        f"🕐 {datetime.utcnow().strftime('%H:%M UTC')}"
    )
    return _send(text)


def test_alert():
    """Send a test message to verify everything works."""
    text = (
        f"🧪 <b>Alpha-Omega Alert Test</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✅ Group chat: working\n"
        f"🕐 {datetime.utcnow().strftime('%H:%M UTC')}"
    )
    return _send(text)
