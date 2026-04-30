"""
trade_log.py — Unified trade logger for Alpha-Omega System.

Writes every closed trade to:
  1. data/trade_log.csv  (always — no external auth needed)
  2. Google Sheet "Alpha-Omega Trade Log" (if gspread is set up via setup_sheets_auth.py)

Columns: Date | Ticker | Direction | Entry | Exit | P&L$ | P&L% | Conviction% | Exit Reason | Regime

Called from:
  - core.portfolio_manager  → log_closed_position(pos)
  - core.signal_tracker     → log_closed_signal(signal)
"""

import csv
import datetime
import os
from pathlib import Path
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────
BASE_DIR   = Path(__file__).parent.parent
DATA_DIR   = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

CSV_PATH       = DATA_DIR / "trade_log.csv"
SHEET_ID       = "1G5f1AePhWKJEMJKmfHj1genbr18LMdlCWPsoBJC2ZxM"  # Alpha-Omega Trade Log
CREDENTIALS_FILE = BASE_DIR / "credentials.json"   # OAuth client secret (one-time setup)
TOKEN_FILE       = BASE_DIR / "data" / "sheets_token.json"  # Saved OAuth token

COLUMNS = ["Date", "Ticker", "Direction", "Entry", "Exit",
           "P&L$", "P&L%", "Conviction%", "Exit Reason", "Regime"]


# ── CSV helpers ───────────────────────────────────────────────────────────────

def _ensure_csv_headers():
    """Create CSV with header row if it doesn't exist yet."""
    if not CSV_PATH.exists():
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(COLUMNS)


def _append_csv(row: dict):
    """Append one trade row to the CSV."""
    _ensure_csv_headers()
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writerow(row)


# ── Google Sheets helpers ─────────────────────────────────────────────────────

def _get_sheet():
    """
    Return the gspread worksheet, or None if not set up.
    Requires setup_sheets_auth.py to have been run once.
    """
    try:
        import gspread
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        import json

        if not TOKEN_FILE.exists():
            return None

        creds_data = json.loads(TOKEN_FILE.read_text())
        creds = Credentials(
            token=creds_data.get("token"),
            refresh_token=creds_data.get("refresh_token"),
            token_uri=creds_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=creds_data.get("client_id"),
            client_secret=creds_data.get("client_secret"),
            scopes=creds_data.get("scopes", ["https://www.googleapis.com/auth/spreadsheets"]),
        )

        # Auto-refresh if expired
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed token
            updated = {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": list(creds.scopes) if creds.scopes else [],
            }
            TOKEN_FILE.write_text(json.dumps(updated, indent=2))

        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        return sh.sheet1

    except Exception:
        return None


def _ensure_sheet_headers(ws):
    """Add header row to sheet if it's empty."""
    try:
        if ws.row_count == 0 or not ws.row_values(1):
            ws.append_row(COLUMNS, value_input_option="USER_ENTERED")
    except Exception:
        pass


def _append_sheet(row: dict):
    """Append one trade row to the Google Sheet."""
    ws = _get_sheet()
    if ws is None:
        return  # Not configured — silently skip
    try:
        _ensure_sheet_headers(ws)
        values = [row.get(col, "") for col in COLUMNS]
        ws.append_row(values, value_input_option="USER_ENTERED")
    except Exception as e:
        print(f"  [TradeLog] Sheet append failed: {e}")


# ── Public API ────────────────────────────────────────────────────────────────

def log_closed_position(pos: dict):
    """
    Log a closed paper trading position (from portfolio_manager).
    Call this whenever pos["status"] == "closed".
    """
    try:
        # Determine exit price from last trade record
        trades = pos.get("trades", [])
        exit_price = pos.get("current_price", pos.get("entry_price", 0))
        exit_reason = "MANUAL"
        if trades:
            last_t = trades[-1]
            exit_price  = last_t.get("price", exit_price)
            exit_reason = last_t.get("tp_level", last_t.get("type", "MANUAL")).upper()

        entry     = pos.get("entry_price", 0)
        shares    = pos.get("shares", 1)
        pnl_dollar = round(pos.get("realized_pnl", 0), 2)
        pnl_pct    = round((exit_price - entry) / entry * 100, 2) if entry else 0
        conviction = pos.get("conviction", 0)
        regime     = pos.get("regime", "")

        # Try to get regime from signal_id lookup if not directly stored
        if not regime:
            try:
                from core.signal_store import load_closed
                closed_sigs = load_closed()
                sig = next((s for s in closed_sigs if s.get("id") == pos.get("signal_id")), None)
                if sig:
                    regime = sig.get("entry_market_context", {}).get("regime", "")
            except Exception:
                pass

        # Parse closed_at date
        closed_at = pos.get("closed_at", datetime.datetime.utcnow().isoformat())
        try:
            date_str = datetime.datetime.fromisoformat(closed_at).strftime("%Y-%m-%d %H:%M")
        except Exception:
            date_str = str(closed_at)[:16]

        row = {
            "Date":        date_str,
            "Ticker":      pos.get("ticker", ""),
            "Direction":   "LONG",
            "Entry":       round(entry, 4),
            "Exit":        round(exit_price, 4),
            "P&L$":        pnl_dollar,
            "P&L%":        pnl_pct,
            "Conviction%": conviction,
            "Exit Reason": exit_reason,
            "Regime":      regime or "—",
        }

        _append_csv(row)
        _append_sheet(row)
        print(f"  [TradeLog] {pos.get('ticker')} → {exit_reason}  P&L: ${pnl_dollar:+.2f} ({pnl_pct:+.2f}%)")

    except Exception as e:
        print(f"  [TradeLog] Error logging position: {e}")


def log_closed_signal(signal: dict):
    """
    Log a closed signal (from signal_tracker).
    Call this when signal["status"] in (STOPPED_OUT, TP1_HIT, TP2_HIT, TP3_HIT, MANUAL_CLOSE, TIMEOUT).
    """
    try:
        entry       = signal.get("entry_price", 0)
        exit_price  = signal.get("close_price") or signal.get("current_price", entry)
        pnl_pct     = signal.get("pnl_pct", 0)
        # For signals, estimate $ P&L using a notional $3,000 position size if not available
        shares_est  = signal.get("qty", 0)
        if shares_est > 0 and entry > 0:
            pnl_dollar = round(shares_est * (exit_price - entry), 2)
        else:
            pnl_dollar = ""  # unknown — signal tracker doesn't always know position size

        conviction  = signal.get("conviction", 0)
        exit_reason = signal.get("close_reason", signal.get("status", "UNKNOWN")).upper()
        # Shorten verbose close reasons for the sheet
        status = signal.get("status", "")
        if status == "STOPPED_OUT":
            exit_reason = "SL"
        elif status == "TP1_HIT":
            exit_reason = "TP1"
        elif status == "TP2_HIT":
            exit_reason = "TP2"
        elif status == "TP3_HIT":
            exit_reason = "TP3"
        elif status == "MANUAL_CLOSE":
            exit_reason = "MANUAL"
        elif status == "TIMEOUT":
            exit_reason = "TIMEOUT"

        regime = signal.get("entry_market_context", {}).get("regime",
                 signal.get("regime", "—"))

        closed_at = signal.get("closed_at", datetime.datetime.utcnow().isoformat())
        try:
            date_str = datetime.datetime.fromisoformat(closed_at).strftime("%Y-%m-%d %H:%M")
        except Exception:
            date_str = str(closed_at)[:16]

        row = {
            "Date":        date_str,
            "Ticker":      signal.get("ticker", ""),
            "Direction":   "LONG",
            "Entry":       round(entry, 4),
            "Exit":        round(float(exit_price), 4) if exit_price else "",
            "P&L$":        pnl_dollar,
            "P&L%":        round(pnl_pct, 2),
            "Conviction%": conviction,
            "Exit Reason": exit_reason,
            "Regime":      regime or "—",
        }

        _append_csv(row)
        _append_sheet(row)
        ticker = signal.get("ticker", "?")
        print(f"  [TradeLog] {ticker} (signal) → {exit_reason}  P&L%: {pnl_pct:+.2f}%")

    except Exception as e:
        print(f"  [TradeLog] Error logging signal: {e}")


def get_today_trades() -> list:
    """Return all trades closed today (UTC date). Used by daily summary."""
    _ensure_csv_headers()
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    trades = []
    try:
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("Date", "").startswith(today):
                    trades.append(row)
    except Exception:
        pass
    return trades


def get_all_trades() -> list:
    """Return all trades from the CSV."""
    _ensure_csv_headers()
    trades = []
    try:
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            trades = list(csv.DictReader(f))
    except Exception:
        pass
    return trades
