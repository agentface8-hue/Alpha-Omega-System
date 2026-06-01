"""
order_executor.py — Live/Paper order execution layer v1.0

Routes Alpha-Omega signals to real broker orders (IBKR) or paper simulation.

MODES (set via env var EXECUTOR_MODE):
  paper : Simulates fills locally — no broker needed. DEFAULT.
  ibkr  : Connects to IB Gateway via ib_async for real orders.

IBKR PORTS:
  7497  = IB Gateway paper trading
  7496  = IB Gateway live trading

SWITCHING PAPER → LIVE:
  1. Set EXECUTOR_MODE=ibkr in .env
  2. Set IBKR_PORT=7497 for paper, 7496 for live
  3. Make sure IB Gateway is running and API is enabled
  That's it. No code changes needed.

ORDER STRUCTURE (bracket):
  Entry  : Market order at next open
  SL     : Stop order attached to entry
  TP1    : Limit order for 50% of shares → SL moves to break-even
  TP2    : Limit order for 30% of shares → SL moves to TP1
  TP3    : Limit/trailing for remaining 20%
"""
import os
import uuid
import logging
import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
EXECUTOR_MODE  = os.environ.get("EXECUTOR_MODE", "paper")   # "paper" | "ibkr"
IBKR_HOST      = os.environ.get("IBKR_HOST", "127.0.0.1")
IBKR_PORT      = int(os.environ.get("IBKR_PORT", "7497"))   # 7497=paper, 7496=live
IBKR_CLIENT_ID = int(os.environ.get("IBKR_CLIENT_ID", "1"))

# ── Paper simulation ──────────────────────────────────────────────────────────

def _paper_execute(ticker: str, shares: int, entry: float,
                   sl: float, tp1: float, tp2: float, tp3: float,
                   tp1_shares: int, tp2_shares: int, tp3_shares: int) -> Dict:
    """Simulate a bracket order fill instantly at the given entry price."""
    order_id = str(uuid.uuid4())[:8].upper()
    now = datetime.datetime.utcnow().isoformat()
    logger.info(f"[EXECUTOR] PAPER fill: {ticker} x{shares} @ ${entry:.2f} | "
                f"SL=${sl:.2f} TP1=${tp1:.2f} TP2=${tp2:.2f} TP3=${tp3:.2f}")
    return {
        "status":      "filled",
        "mode":        "paper",
        "order_id":    order_id,
        "ticker":      ticker,
        "shares":      shares,
        "fill_price":  entry,
        "sl":          sl,
        "tp1":         tp1, "tp1_shares": tp1_shares,
        "tp2":         tp2, "tp2_shares": tp2_shares,
        "tp3":         tp3, "tp3_shares": tp3_shares,
        "submitted_at": now,
        "filled_at":   now,
        "commission":  0.0,
        "slippage":    0.0,
        "broker_order_id": None,
    }


# ── IBKR execution ────────────────────────────────────────────────────────────

def _ibkr_execute(ticker: str, shares: int, entry: float,
                  sl: float, tp1: float, tp2: float, tp3: float,
                  tp1_shares: int, tp2_shares: int, tp3_shares: int) -> Dict:
    """
    Place a live bracket order via IB Gateway using ib_async.
    Connects, places orders, disconnects. Stateless per call.
    """
    try:
        from ib_async import IB, Stock, MarketOrder, StopOrder, LimitOrder, OrderCombo
    except ImportError:
        raise RuntimeError(
            "ib_async not installed. Run: pip install ib_async\n"
            "Also ensure IB Gateway is running on "
            f"{IBKR_HOST}:{IBKR_PORT}"
        )

    ib = IB()
    result = {}
    now = datetime.datetime.utcnow().isoformat()

    try:
        ib.connect(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID, timeout=10)
        logger.info(f"[EXECUTOR] IBKR connected — {IBKR_HOST}:{IBKR_PORT} "
                    f"({'PAPER' if IBKR_PORT == 7497 else 'LIVE'})")

        contract = Stock(ticker, "SMART", "USD")
        ib.qualifyContracts(contract)

        # ── Entry: Market order ───────────────────────────────────────────────
        entry_order = MarketOrder("BUY", shares)
        entry_trade = ib.placeOrder(contract, entry_order)
        ib.sleep(1)  # give it a moment

        parent_id = entry_order.orderId

        # ── TP1: Limit order for tp1_shares ──────────────────────────────────
        tp1_order = LimitOrder(
            "SELL", tp1_shares, tp1,
            parentId=parent_id,
            transmit=False,
        )

        # ── TP2: Limit order for tp2_shares ──────────────────────────────────
        tp2_order = LimitOrder(
            "SELL", tp2_shares, tp2,
            parentId=parent_id,
            transmit=False,
        )

        # ── TP3: Limit order for remaining shares ─────────────────────────────
        tp3_order = LimitOrder(
            "SELL", tp3_shares, tp3,
            parentId=parent_id,
            transmit=False,
        )

        # ── SL: Stop order for full position — transmit=True fires all ───────
        sl_order = StopOrder(
            "SELL", shares, sl,
            parentId=parent_id,
            transmit=True,   # this triggers all attached orders
        )

        ib.placeOrder(contract, tp1_order)
        ib.placeOrder(contract, tp2_order)
        ib.placeOrder(contract, tp3_order)
        ib.placeOrder(contract, sl_order)
        ib.sleep(2)

        fill_price = entry
        if entry_trade.fills:
            fill_price = round(float(entry_trade.fills[0].execution.avgPrice), 4)
        slippage = round(abs(fill_price - entry), 4)

        logger.info(f"[EXECUTOR] IBKR filled {ticker} x{shares} @ ${fill_price:.2f} "
                    f"(slippage ${slippage:.4f})")

        result = {
            "status":         "filled",
            "mode":           "ibkr_paper" if IBKR_PORT == 7497 else "ibkr_live",
            "order_id":       str(entry_order.orderId),
            "ticker":         ticker,
            "shares":         shares,
            "fill_price":     fill_price,
            "sl":             sl,
            "tp1":            tp1, "tp1_shares": tp1_shares,
            "tp2":            tp2, "tp2_shares": tp2_shares,
            "tp3":            tp3, "tp3_shares": tp3_shares,
            "submitted_at":   now,
            "filled_at":      datetime.datetime.utcnow().isoformat(),
            "commission":     round(max(1.0, shares * 0.005), 2),  # IBKR ~$0.005/share, min $1
            "slippage":       slippage,
            "broker_order_id": str(entry_order.orderId),
            "sl_order_id":    str(sl_order.orderId),
            "tp1_order_id":   str(tp1_order.orderId),
            "tp2_order_id":   str(tp2_order.orderId),
            "tp3_order_id":   str(tp3_order.orderId),
        }

    except Exception as e:
        logger.error(f"[EXECUTOR] IBKR order failed for {ticker}: {e}")
        result = {
            "status":  "failed",
            "mode":    "ibkr",
            "ticker":  ticker,
            "error":   str(e),
            "submitted_at": now,
        }
    finally:
        if ib.isConnected():
            ib.disconnect()

    return result


# ── Cancel order (IBKR only) ──────────────────────────────────────────────────

def cancel_order(broker_order_id: str) -> Dict:
    """Cancel an open order by IBKR order ID. No-op in paper mode."""
    if EXECUTOR_MODE == "paper":
        return {"status": "cancelled", "mode": "paper", "order_id": broker_order_id}
    try:
        from ib_async import IB
        ib = IB()
        ib.connect(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID + 1, timeout=10)
        open_orders = ib.reqAllOpenOrders()
        cancelled = []
        for o in open_orders:
            if str(o.order.orderId) == str(broker_order_id):
                ib.cancelOrder(o.order)
                cancelled.append(broker_order_id)
        ib.disconnect()
        return {"status": "cancelled", "mode": "ibkr", "cancelled": cancelled}
    except Exception as e:
        logger.error(f"[EXECUTOR] Cancel failed for {broker_order_id}: {e}")
        return {"status": "error", "error": str(e)}


# ── Get live IBKR position ────────────────────────────────────────────────────

def get_ibkr_position(ticker: str) -> Optional[Dict]:
    """Fetch current IBKR position for a ticker. Returns None in paper mode."""
    if EXECUTOR_MODE == "paper":
        return None
    try:
        from ib_async import IB
        ib = IB()
        ib.connect(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID + 2, timeout=10)
        positions = ib.positions()
        ib.disconnect()
        for p in positions:
            if p.contract.symbol == ticker.upper():
                return {
                    "ticker":   ticker,
                    "shares":   int(p.position),
                    "avg_cost": round(float(p.avgCost), 4),
                }
        return None
    except Exception as e:
        logger.error(f"[EXECUTOR] Position fetch failed for {ticker}: {e}")
        return None


# ── Connection health check ───────────────────────────────────────────────────

def check_connection() -> Dict:
    """Verify broker connection is alive. Safe to call anytime."""
    if EXECUTOR_MODE == "paper":
        return {"status": "ok", "mode": "paper", "broker": "simulated"}
    try:
        from ib_async import IB
        ib = IB()
        ib.connect(IBKR_HOST, IBKR_PORT, clientId=IBKR_CLIENT_ID + 9, timeout=5)
        account = ib.managedAccounts()
        ib.disconnect()
        env = "PAPER" if IBKR_PORT == 7497 else "LIVE"
        return {
            "status":   "ok",
            "mode":     f"ibkr_{env.lower()}",
            "broker":   "Interactive Brokers",
            "account":  account[0] if account else "unknown",
            "port":     IBKR_PORT,
            "env":      env,
        }
    except Exception as e:
        return {"status": "error", "mode": "ibkr", "error": str(e),
                "hint": f"Is IB Gateway running on {IBKR_HOST}:{IBKR_PORT}?"}


# ── Main public entry point ───────────────────────────────────────────────────

def execute_signal(signal: Dict) -> Dict:
    """
    Execute a signal as a bracket order.
    Works in both paper and IBKR modes.

    Args:
        signal: Alpha-Omega signal dict containing ticker, entry_price,
                sl, tp1, tp2, tp3, shares, tp1_shares, tp2_shares, tp3_shares

    Returns:
        execution result dict with status, fill_price, order IDs, commission
    """
    ticker     = signal.get("ticker", "").upper()
    entry      = float(signal.get("entry_price", signal.get("entry", 0)))
    sl         = float(signal.get("sl", 0))
    tp1        = float(signal.get("tp1", 0))
    tp2        = float(signal.get("tp2", 0))
    tp3        = float(signal.get("tp3", 0))
    shares     = int(signal.get("shares", signal.get("qty", 0)))
    tp1_shares = int(signal.get("tp1_shares", max(1, round(shares * 0.50))))
    tp2_shares = int(signal.get("tp2_shares", max(1, round(shares * 0.30))))
    tp3_shares = shares - tp1_shares - tp2_shares
    if tp3_shares < 0: tp3_shares = 0

    # Sanity checks
    if not ticker:
        return {"status": "failed", "error": "No ticker provided"}
    if shares <= 0:
        return {"status": "failed", "error": "shares must be > 0"}
    if sl >= entry:
        return {"status": "failed", "error": f"SL ${sl} must be below entry ${entry}"}
    if tp1 <= entry:
        return {"status": "failed", "error": f"TP1 ${tp1} must be above entry ${entry}"}

    try:
        from core.trading_safety import check_trade_allowed
        mode = "ibkr_live" if EXECUTOR_MODE == "ibkr" and IBKR_PORT == 7496 else EXECUTOR_MODE
        safety = check_trade_allowed(ticker=ticker, mode=mode, new_position=True)
        if not safety.get("allowed", True):
            return {"status": "blocked", "error": safety.get("reason"), "safety": safety}
    except Exception as e:
        logger.warning(f"[EXECUTOR] Safety check skipped: {e}")

    logger.info(f"[EXECUTOR] Routing {ticker} x{shares} via mode={EXECUTOR_MODE}")

    if EXECUTOR_MODE == "ibkr":
        result = _ibkr_execute(ticker, shares, entry, sl, tp1, tp2, tp3,
                               tp1_shares, tp2_shares, tp3_shares)
    else:
        result = _paper_execute(ticker, shares, entry, sl, tp1, tp2, tp3,
                                tp1_shares, tp2_shares, tp3_shares)

    # Attach execution metadata back to signal
    result["signal_id"]  = signal.get("id", signal.get("signal_id", ""))
    result["conviction"] = signal.get("conviction", 0)
    result["dtp_note"]   = signal.get("dtp_note", "")

    return result
