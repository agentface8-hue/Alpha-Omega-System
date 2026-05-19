"""
trade_log.py - Unified trade logger for Alpha-Omega System.

Writes every closed trade to:
  1. Supabase trade_log table  (PRIMARY - persistent, free, no API limits)
  2. data/trade_log.csv        (local backup - ephemeral on Render)

Airtable removed as primary due to Free plan API call limits (May 2026).
"""

import csv
import datetime
import logging
import os
import json
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

CSV_PATH = DATA_DIR / "trade_log.csv"
COLUMNS  = ["Date", "Ticker", "Direction", "Entry", "Exit",
             "P&L$", "P&L%", "Conviction%", "Exit Reason", "Regime"]


# -- CSV (local backup) -------------------------------------------------------

def _ensure_csv_headers():
    if not CSV_PATH.exists():
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(COLUMNS)

def _append_csv(row: dict):
    _ensure_csv_headers()
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=COLUMNS).writerow(row)


# -- Supabase (primary) -------------------------------------------------------

def _log_to_supabase(record: dict):
    """Insert into Supabase trade_log. Logs warning on failure, never silent."""
    supa_url = os.environ.get("SUPABASE_URL", "")
    supa_key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not supa_url or not supa_key:
        logger.warning("[TradeLog] Supabase env vars missing")
        return
    try:
        body = json.dumps(record, default=str).encode()
        req  = urllib.request.Request(
            f"{supa_url}/rest/v1/trade_log",
            data=body,
            headers={
                "apikey":        supa_key,
                "Authorization": f"Bearer {supa_key}",
                "Content-Type":  "application/json",
                "Prefer":        "return=minimal",
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
        logger.info(f"[TradeLog] Supabase OK -> {record.get('ticker')}")
    except Exception as e:
        logger.warning(f"[TradeLog] Supabase failed: {e}")


# -- Public API ---------------------------------------------------------------

def log_closed_signal(signal: dict):
    """Log a closed signal (from signal_tracker). Supabase primary, CSV backup."""
    try:
        entry      = signal.get("entry_price", 0)
        exit_price = signal.get("close_price") or signal.get("current_price", entry)
        pnl_pct    = signal.get("pnl_pct", 0)
        shares     = signal.get("qty", 0)
        pnl_dollar = round(shares * (float(exit_price) - float(entry)), 2) if shares and entry else 0

        status = signal.get("status", "")
        exit_reason = {"STOPPED_OUT": "SL", "TP1_HIT": "TP1", "TP2_HIT": "TP2",
                       "TP3_HIT": "TP3", "MANUAL_CLOSE": "MANUAL", "TIMEOUT": "TIMEOUT"
                       }.get(status, status)
        regime = signal.get("entry_market_context", {}).get("regime",
                 signal.get("regime", ""))

        closed_at = signal.get("closed_at", datetime.datetime.utcnow().isoformat())
        try:
            date_str = datetime.datetime.fromisoformat(closed_at).strftime("%Y-%m-%d %H:%M")
        except Exception:
            date_str = str(closed_at)[:16]

        _append_csv({
            "Date":        date_str,
            "Ticker":      signal.get("ticker", ""),
            "Direction":   "LONG",
            "Entry":       round(float(entry), 4),
            "Exit":        round(float(exit_price), 4) if exit_price else "",
            "P&L$":        pnl_dollar,
            "P&L%":        round(float(pnl_pct), 2),
            "Conviction%": signal.get("conviction", 0),
            "Exit Reason": exit_reason,
            "Regime":      regime or "-",
        })

        _log_to_supabase({
            "ticker":      signal.get("ticker", ""),
            "date_closed": date_str,
            "direction":   "LONG",
            "entry_price": round(float(entry), 4),
            "exit_price":  round(float(exit_price), 4) if exit_price else None,
            "pnl_dollar":  pnl_dollar,
            "pnl_pct":     round(float(pnl_pct), 2),
            "conviction":  signal.get("conviction", 0),
            "exit_reason": exit_reason,
            "regime":      regime or "",
            "asset_type":  signal.get("asset_type", "stock"),
            "signal_id":   signal.get("id", ""),
            "mae_pct":     signal.get("mae_pct", 0),
            "mfe_pct":     signal.get("mfe_pct", 0),
            "source":      "signal_tracker",
        })

        print(f"  [TradeLog] {signal.get('ticker','?')} -> {exit_reason} PnL: {pnl_pct:+.2f}%")

    except Exception as e:
        logger.error(f"[TradeLog] log_closed_signal failed: {e}")


def log_closed_position(pos: dict):
    """Log a closed portfolio position (from portfolio_manager). Supabase primary."""
    try:
        trades     = pos.get("trades", [])
        entry      = pos.get("entry_price", 0)
        exit_price = pos.get("current_price", entry)
        exit_reason = "MANUAL"
        if trades:
            last_t      = trades[-1]
            exit_price  = last_t.get("price", exit_price)
            exit_reason = last_t.get("tp_level", last_t.get("type", "MANUAL")).upper()

        pnl_dollar = round(pos.get("realized_pnl", 0), 2)
        pnl_pct    = round((float(exit_price) - float(entry)) / float(entry) * 100, 2) if entry else 0
        conviction = pos.get("conviction", 0)
        regime     = pos.get("regime", "")

        if not regime:
            try:
                from core.signal_store import load_closed
                sig = next((s for s in load_closed() if s.get("id") == pos.get("signal_id")), None)
                if sig:
                    regime = sig.get("entry_market_context", {}).get("regime", "")
            except Exception:
                pass

        closed_at = pos.get("closed_at", datetime.datetime.utcnow().isoformat())
        try:
            date_str = datetime.datetime.fromisoformat(closed_at).strftime("%Y-%m-%d %H:%M")
        except Exception:
            date_str = str(closed_at)[:16]

        _append_csv({
            "Date":        date_str,
            "Ticker":      pos.get("ticker", ""),
            "Direction":   "LONG",
            "Entry":       round(float(entry), 4),
            "Exit":        round(float(exit_price), 4),
            "P&L$":        pnl_dollar,
            "P&L%":        pnl_pct,
            "Conviction%": conviction,
            "Exit Reason": exit_reason,
            "Regime":      regime or "-",
        })

        _log_to_supabase({
            "ticker":      pos.get("ticker", ""),
            "date_closed": date_str,
            "direction":   "LONG",
            "entry_price": round(float(entry), 4),
            "exit_price":  round(float(exit_price), 4),
            "pnl_dollar":  pnl_dollar,
            "pnl_pct":     pnl_pct,
            "conviction":  conviction,
            "exit_reason": exit_reason,
            "regime":      regime or "",
            "asset_type":  pos.get("asset_type", "stock"),
            "signal_id":   pos.get("id", ""),
            "mae_pct":     pos.get("mae_pct", 0),
            "mfe_pct":     pos.get("mfe_pct", 0),
            "source":      "portfolio",
        })

        print(f"  [TradeLog] {pos.get('ticker','?')} (position) -> {exit_reason} P&L: ${pnl_dollar:+.2f} ({pnl_pct:+.2f}%)")

    except Exception as e:
        logger.error(f"[TradeLog] log_closed_position failed: {e}")


def get_today_trades() -> list:
    _ensure_csv_headers()
    today  = datetime.datetime.utcnow().strftime("%Y-%m-%d")
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
    """Fetch all trades from Supabase (primary), fallback to CSV."""
    supa_url = os.environ.get("SUPABASE_URL", "")
    supa_key = os.environ.get("SUPABASE_ANON_KEY", "")
    if supa_url and supa_key:
        try:
            req = urllib.request.Request(
                f"{supa_url}/rest/v1/trade_log?order=created_at.desc&limit=500",
                headers={"apikey": supa_key, "Authorization": f"Bearer {supa_key}"}
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            logger.warning(f"[TradeLog] Supabase fetch failed, using CSV: {e}")
    _ensure_csv_headers()
    try:
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []
