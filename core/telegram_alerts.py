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

TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "8246500243:AAFXsq94Fia3RimL4_Q-AM6sdDJpZNoxTYM")
PERSONAL_CHAT_ID = os.environ.get("TELEGRAM_PERSONAL_CHAT_ID", "5812682751")
GROUP_CHAT_ID    = os.environ.get("TELEGRAM_GROUP_CHAT_ID", "-5228475615")
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


# ── Alert formatters ────────────────────────────────────────────

def alert_signal_created(signal: dict):
    """New turbo signal launched."""
    ticker  = signal.get("ticker", "?")
    entry   = signal.get("entry_price", 0)
    sl      = signal.get("sl", signal.get("targets", {}).get("sl", 0))
    tp1     = signal.get("tp1", signal.get("targets", {}).get("tp1", 0))
    tp3     = signal.get("tp3", 0)
    conv    = signal.get("conviction", 0)
    atype   = signal.get("asset_type", "stock").upper()
    regime  = signal.get("regime", "")
    method  = signal.get("target_method", "atr")
    text = (
        f"\U0001f680 <b>NEW SIGNAL — {ticker}</b> ({atype})\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"\U0001f4e5 Entry:  <b>${entry}</b>\n"
        f"\U0001f6d1 SL:     <b>${sl}</b>\n"
        f"\U0001f3af TP1:    <b>${tp1}</b>\n"
        f"\U0001f3c6 TP3:    <b>${tp3}</b>\n"
        f"\U0001f4a1 Conviction: <b>{conv}%</b>\n"
        f"\U0001f30d Regime: {regime} | {method}\n"
        f"\U0001f550 {datetime.utcnow().strftime('%H:%M UTC')}"
    )
    return _send(text)


def alert_tp_hit(signal: dict, tp_level: str, price: float):
    """TP1, TP2, or TP3 hit."""
    ticker  = signal.get("ticker", "?")
    entry   = signal.get("entry_price", 0)
    pnl_pct = ((price - entry) / entry * 100) if entry else 0
    emoji   = {"tp1": "\U0001f3af", "tp2": "\U0001f3af\U0001f3af", "tp3": "\U0001f3c6"}.get(tp_level, "\U0001f3af")
    trailing = " \U0001f4c8 TRAILING" if signal.get("trailing_active") else ""
    text = (
        f"{emoji} <b>{tp_level.upper()} HIT — {ticker}</b>{trailing}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"\U0001f4b0 Price:  <b>${price:.2f}</b>\n"
        f"\U0001f4c8 P&L:    <b>+{pnl_pct:.1f}%</b>\n"
        f"\U0001f4e5 Entry:  ${entry}\n"
        f"\U0001f550 {datetime.utcnow().strftime('%H:%M UTC')}"
    )
    return _send(text)


def alert_tp_extended(signal: dict, new_tp3: float, extension_count: int):
    """
    TP3 was extended because price blew through cleanly.
    The trade keeps running — trailing mode active.
    """
    ticker  = signal.get("ticker", "?")
    entry   = signal.get("entry_price", 0)
    price   = signal.get("current_price", new_tp3)
    pnl_pct = ((price - entry) / entry * 100) if entry else 0
    ordinal = {1: "1st", 2: "2nd", 3: "3rd"}.get(extension_count, f"{extension_count}th")
    text = (
        f"\U0001f4c8 <b>TP3 EXTENDED — {ticker}</b> ({ordinal} extension)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"\U0001f3af New TP3: <b>${new_tp3:.2f}</b>\n"
        f"\U0001f4b0 Current: <b>${price:.2f}</b> (+{pnl_pct:.1f}%)\n"
        f"\U0001f4e5 Entry:   ${entry}\n"
        f"\u26a1 Momentum still strong — letting it ride\n"
        f"\U0001f550 {datetime.utcnow().strftime('%H:%M UTC')}"
    )
    return _send(text)


def alert_momentum_fade(signal: dict, current_pnl_pct: float, peak_mfe_pct: float):
    """
    Price has declined 3+ consecutive checks and is giving back gains from peak.
    Warning: consider exiting to protect profits.
    """
    ticker      = signal.get("ticker", "?")
    entry       = signal.get("entry_price", 0)
    curr_price  = signal.get("current_price", 0)
    giving_back = round(peak_mfe_pct - current_pnl_pct, 2)
    text = (
        f"\u26a0\ufe0f <b>MOMENTUM FADING — {ticker}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"\U0001f4c9 Giving back: <b>{giving_back:.1f}%</b> from peak\n"
        f"\U0001f4ca Current P&L: <b>+{current_pnl_pct:.1f}%</b>\n"
        f"\U0001f3c6 Peak MFE:    <b>+{peak_mfe_pct:.1f}%</b>\n"
        f"\U0001f4b2 Price: ${curr_price:.2f} | Entry: ${entry}\n"
        f"\U0001f4ac Consider exiting to lock in gains\n"
        f"\U0001f550 {datetime.utcnow().strftime('%H:%M UTC')}"
    )
    return _send(text)


def alert_sl_hit(signal: dict, price: float):
    """Stop loss hit."""
    ticker  = signal.get("ticker", "?")
    entry   = signal.get("entry_price", 0)
    pnl_pct = ((price - entry) / entry * 100) if entry else 0
    text = (
        f"\U0001f6d1 <b>STOPPED OUT — {ticker}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"\U0001f4b8 Price:  <b>${price:.2f}</b>\n"
        f"\U0001f4c9 P&L:    <b>{pnl_pct:.1f}%</b>\n"
        f"\U0001f4e5 Entry:  ${entry}\n"
        f"\U0001f550 {datetime.utcnow().strftime('%H:%M UTC')}"
    )
    return _send(text)


def alert_signal_closed(signal: dict, reason: str, price: float):
    """Signal manually closed or timed out."""
    ticker  = signal.get("ticker", "?")
    entry   = signal.get("entry_price", 0)
    pnl_pct = ((price - entry) / entry * 100) if entry else 0
    emoji   = "\u2705" if pnl_pct > 0 else "\u274c"
    ext     = signal.get("tp3_extensions", 0)
    ext_note = f" | {ext} TP3 extension{'s' if ext != 1 else ''}" if ext else ""
    text = (
        f"{emoji} <b>CLOSED — {ticker}</b>{ext_note}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"\U0001f4cc Reason: <b>{reason}</b>\n"
        f"\U0001f4b0 Exit:   <b>${price:.2f}</b>\n"
        f"\U0001f4ca P&L:    <b>{'+' if pnl_pct >= 0 else ''}{pnl_pct:.1f}%</b>\n"
        f"\U0001f4e5 Entry:  ${entry}\n"
        f"\U0001f550 {datetime.utcnow().strftime('%H:%M UTC')}"
    )
    return _send(text)


def alert_autopilot_launched(count: int, asset_type: str = "stocks"):
    """Auto-pilot scan completed."""
    text = (
        f"\U0001f916 <b>AUTO-PILOT LAUNCHED</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"\U0001f4ca Signals: <b>{count} {asset_type}</b>\n"
        f"\U0001f517 Dashboard: alpha-omega-ngfw.vercel.app\n"
        f"\U0001f550 {datetime.utcnow().strftime('%H:%M UTC')}"
    )
    return _send(text)


def alert_system_online():
    """Backend came online (startup)."""
    text = (
        f"\u2705 <b>Alpha-Omega System Online</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"\U0001f517 alpha-omega-ngfw.vercel.app\n"
        f"\U0001f550 {datetime.utcnow().strftime('%H:%M UTC')}"
    )
    return _send(text)


def test_alert():
    """Send a test message to verify everything works."""
    text = (
        f"\U0001f9ea <b>Alpha-Omega Alert Test</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"\u2705 Group chat: working\n"
        f"\U0001f550 {datetime.utcnow().strftime('%H:%M UTC')}"
    )
    return _send(text)
