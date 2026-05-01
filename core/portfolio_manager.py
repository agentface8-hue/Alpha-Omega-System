"""
portfolio_manager.py — Paper trading portfolio engine v1.0
$25K capital, max 10 positions, $5,000 max/trade, split exits, trailing SL.
"""
import uuid, datetime, math
from typing import Dict, Any, List, Optional
import yfinance as yf
from core import portfolio_store as store

# ── Constants ──────────────────────────────────────────────────
MAX_POSITIONS   = 10
STARTING_CASH   = 25_000.0
MAX_POS_SIZE    = 5_000.0   # $5K per slot — 10 slots = full $50K notional
MIN_POS_SIZE    = 3_000.0   # floor for small-cap or high-priced names
MAX_RISK        = 500.0     # $500 = 2% of $25K
SPLIT_TP1_PCT   = 0.50
SPLIT_TP2_PCT   = 0.30
SPLIT_TP3_PCT   = 0.20


# ── Price fetch ────────────────────────────────────────────────
def _live_price(ticker: str, asset_type: str = "stock") -> Optional[float]:
    try:
        sym = ticker.upper()
        if asset_type == "crypto":
            sym = sym + "-USD" if not sym.endswith("-USD") else sym
        tk = yf.Ticker(sym)
        data = tk.history(period="1d", interval="1m")
        if not data.empty:
            return round(float(data["Close"].iloc[-1]), 4)
        data = tk.history(period="2d")
        if not data.empty:
            return round(float(data["Close"].iloc[-1]), 4)
    except:
        pass
    return None


# ── Position sizing ────────────────────────────────────────────
def _size_position(entry: float, sl: float) -> Dict:
    """
    Risk-based sizing: shares = MAX_RISK / (entry - sl).
    Position value capped at MAX_POS_SIZE, floor at MIN_POS_SIZE.
    """
    sl_dist = max(entry - sl, 0.01)
    shares_by_risk = math.floor(MAX_RISK / sl_dist)
    max_shares = math.floor(MAX_POS_SIZE / entry)
    min_shares = math.ceil(MIN_POS_SIZE / entry)
    shares = max(min_shares, min(shares_by_risk, max_shares))
    if shares < 1:
        shares = 1
    position_size = round(shares * entry, 2)
    risk_actual   = round(shares * sl_dist, 2)

    tp1_shares = max(1, round(shares * SPLIT_TP1_PCT))
    tp2_shares = max(1, round(shares * SPLIT_TP2_PCT))
    tp3_shares = shares - tp1_shares - tp2_shares
    if tp3_shares < 0:
        tp3_shares = 0

    return {
        "shares": shares,
        "position_size": position_size,
        "risk_actual": risk_actual,
        "tp1_shares": tp1_shares,
        "tp2_shares": tp2_shares,
        "tp3_shares": tp3_shares,
    }


# ── Open position ──────────────────────────────────────────────
def open_position(ticker: str, entry_price: float, sl: float,
                  tp1: float, tp2: float, tp3: float,
                  conviction: int = 0, asset_type: str = "stock",
                  signal_id: str = "") -> Dict:
    state = store.load_state()
    open_pos = store.load_positions("open")

    if len(open_pos) >= MAX_POSITIONS:
        return {"error": f"Max {MAX_POSITIONS} positions reached"}

    sizing = _size_position(entry_price, sl)

    if sizing["position_size"] > state["cash"]:
        min_shares = max(1, math.ceil(MIN_POS_SIZE / entry_price))
        min_size   = round(min_shares * entry_price, 2)
        if min_size <= state["cash"]:
            tp1_sh = max(1, round(min_shares * SPLIT_TP1_PCT))
            tp2_sh = max(1, round(min_shares * SPLIT_TP2_PCT))
            tp3_sh = max(0, min_shares - tp1_sh - tp2_sh)
            sizing = {
                "shares": min_shares, "position_size": min_size,
                "risk_actual": round(min_shares * max(entry_price - sl, 0.01), 2),
                "tp1_shares": tp1_sh, "tp2_shares": tp2_sh, "tp3_shares": tp3_sh,
            }
        else:
            return {"error": f"Insufficient cash (need ${min_size:.2f}, have ${state['cash']:.0f})"}

    now = datetime.datetime.utcnow().isoformat()
    pos = {
        "id": str(uuid.uuid4()),
        "ticker": ticker.upper(),
        "status": "open",
        "asset_type": asset_type,
        "entry_price": round(entry_price, 4),
        "entry_date": now,
        "shares": sizing["shares"],
        "shares_remaining": sizing["shares"],
        "tp1_shares": sizing["tp1_shares"],
        "tp2_shares": sizing["tp2_shares"],
        "tp3_shares": sizing["tp3_shares"],
        "position_size": sizing["position_size"],
        "risk_actual": sizing["risk_actual"],
        "sl": round(sl, 4),
        "sl_original": round(sl, 4),
        "tp1": round(tp1, 4),
        "tp2": round(tp2, 4),
        "tp3": round(tp3, 4),
        "tp1_hit": False,
        "tp2_hit": False,
        "tp3_hit": False,
        "current_price": round(entry_price, 4),
        "unrealized_pnl": 0.0,
        "unrealized_pnl_pct": 0.0,
        "realized_pnl": 0.0,
        "mae": 0.0,
        "mfe": 0.0,
        "conviction": conviction,
        "signal_id": signal_id,
        "close_reason": None,
        "trades": [{
            "id": str(uuid.uuid4()),
            "type": "entry",
            "price": round(entry_price, 4),
            "shares": sizing["shares"],
            "pnl": 0.0,
            "executed_at": now,
        }],
        "updated_at": now,
    }

    state["cash"] = round(state["cash"] - sizing["position_size"], 2)
    store.save_position(pos)
    store.save_state(state)
    return pos


# ── Price check + auto-exit ────────────────────────────────────
def check_portfolio() -> Dict:
    """
    Refresh all open positions. Auto-execute split exits.
    Returns updated portfolio snapshot.
    """
    open_pos = store.load_positions("open")
    state = store.load_state()
    updates = []
    closed_count = 0

    for pos in open_pos:
        ticker  = pos["ticker"]
        a_type  = pos.get("asset_type", "stock")
        price   = _live_price(ticker, a_type)
        if price is None:
            updates.append({"ticker": ticker, "status": "price_error"})
            continue

        entry   = pos["entry_price"]
        sl      = pos["sl"]
        tp1     = pos["tp1"]
        tp2     = pos["tp2"]
        tp3     = pos["tp3"]
        shares  = pos["shares_remaining"]

        pos["current_price"] = price
        gain_from_entry = price - entry
        pos["mae"] = round(min(pos.get("mae", 0), gain_from_entry), 4)
        pos["mfe"] = round(max(pos.get("mfe", 0), gain_from_entry), 4)
        pos["unrealized_pnl"] = round(shares * (price - entry), 2)
        pos["unrealized_pnl_pct"] = round((price - entry) / entry * 100, 2)

        now = datetime.datetime.utcnow().isoformat()
        action = None

        # ── SL hit ────────────────────────────────────────────
        if price <= sl and shares > 0:
            pnl = round(shares * (sl - entry), 2)
            pos["trades"].append({
                "id": str(uuid.uuid4()), "type": "sl_exit",
                "price": sl, "shares": shares, "pnl": pnl,
                "tp_level": "SL", "executed_at": now,
            })
            pos["realized_pnl"] = round(pos.get("realized_pnl", 0) + pnl, 2)
            state["cash"] = round(state["cash"] + shares * sl, 2)
            pos["shares_remaining"] = 0
            pos["status"] = "closed"
            pos["closed_at"] = now
            pos["close_reason"] = f"Stop-loss hit @ ${sl:.2f} (entry ${entry:.2f}, loss ${abs(pnl):.0f})"
            pos["unrealized_pnl"] = 0
            action = f"SL hit @ ${sl}"
            closed_count += 1

        # ── TP3 hit ───────────────────────────────────────────
        elif price >= tp3 and not pos.get("tp3_hit") and pos.get("tp2_hit"):
            tp3_sh = pos["shares_remaining"]
            pnl    = round(tp3_sh * (tp3 - entry), 2)
            pos["trades"].append({
                "id": str(uuid.uuid4()), "type": "partial_tp3",
                "price": tp3, "shares": tp3_sh, "pnl": pnl,
                "tp_level": "TP3", "executed_at": now,
            })
            pos["realized_pnl"] = round(pos.get("realized_pnl", 0) + pnl, 2)
            state["cash"] = round(state["cash"] + tp3_sh * tp3, 2)
            pos["tp3_hit"] = True
            pos["shares_remaining"] = 0
            pos["status"] = "closed"
            pos["closed_at"] = now
            pos["close_reason"] = f"TP3 hit @ ${tp3:.2f} — full target reached (+${pnl:.0f})"
            pos["unrealized_pnl"] = 0
            action = f"TP3 hit @ ${tp3}"
            closed_count += 1

        # ── TP2 hit ───────────────────────────────────────────
        elif price >= tp2 and not pos.get("tp2_hit") and pos.get("tp1_hit"):
            tp2_sh = min(pos.get("tp2_shares", 1), pos["shares_remaining"])
            pnl    = round(tp2_sh * (tp2 - entry), 2)
            pos["trades"].append({
                "id": str(uuid.uuid4()), "type": "partial_tp2",
                "price": tp2, "shares": tp2_sh, "pnl": pnl,
                "tp_level": "TP2", "executed_at": now,
            })
            pos["realized_pnl"] = round(pos.get("realized_pnl", 0) + pnl, 2)
            state["cash"] = round(state["cash"] + tp2_sh * tp2, 2)
            pos["tp2_hit"] = True
            pos["shares_remaining"] -= tp2_sh
            pos["status"] = "partial"
            pos["sl"] = round(tp1, 4)
            action = f"TP2 hit @ ${tp2}, SL -> TP1"

        # ── TP1 hit ───────────────────────────────────────────
        elif price >= tp1 and not pos.get("tp1_hit"):
            tp1_sh = min(pos.get("tp1_shares", 1), pos["shares_remaining"])
            pnl    = round(tp1_sh * (tp1 - entry), 2)
            pos["trades"].append({
                "id": str(uuid.uuid4()), "type": "partial_tp1",
                "price": tp1, "shares": tp1_sh, "pnl": pnl,
                "tp_level": "TP1", "executed_at": now,
            })
            pos["realized_pnl"] = round(pos.get("realized_pnl", 0) + pnl, 2)
            state["cash"] = round(state["cash"] + tp1_sh * tp1, 2)
            pos["tp1_hit"] = True
            pos["shares_remaining"] -= tp1_sh
            pos["status"] = "partial"
            pos["sl"] = round(entry, 4)
            action = f"TP1 hit @ ${tp1}, SL -> BE"

        pos["updated_at"] = now
        store.save_position(pos)
        updates.append({"ticker": ticker, "price": price, "action": action,
                        "pnl": pos["unrealized_pnl"], "status": pos["status"]})

        if pos["status"] == "closed":
            try:
                from core.trade_log import log_closed_position
                log_closed_position(pos)
            except Exception as _tl_err:
                print(f"  [TradeLog] warning: {_tl_err}")

    open_after = store.load_positions("open")
    positions_value = sum(
        p["shares_remaining"] * p.get("current_price", p["entry_price"])
        for p in open_after
    )
    state["total_value"] = round(state["cash"] + positions_value, 2)
    store.save_state(state)

    return {
        "updates": updates,
        "closed_this_check": closed_count,
        "portfolio": get_portfolio(),
    }


# ── Manual close ───────────────────────────────────────────────
def close_position(position_id: str, reason: str = "MANUAL") -> Dict:
    open_pos = store.load_positions("open")
    pos = next((p for p in open_pos if p["id"] == position_id), None)
    if not pos:
        return {"error": "Position not found"}

    state = store.load_state()
    price = _live_price(pos["ticker"], pos.get("asset_type", "stock")) or pos["current_price"]
    shares = pos["shares_remaining"]
    entry  = pos["entry_price"]
    pnl = round(shares * (price - entry), 2)
    now = datetime.datetime.utcnow().isoformat()

    pos["trades"].append({
        "id": str(uuid.uuid4()), "type": "manual_close",
        "price": price, "shares": shares, "pnl": pnl,
        "tp_level": reason, "executed_at": now,
    })
    pos["realized_pnl"] = round(pos.get("realized_pnl", 0) + pnl, 2)
    state["cash"] = round(state["cash"] + shares * price, 2)
    pos["shares_remaining"] = 0
    pos["status"] = "closed"
    pos["closed_at"] = now
    pos["close_reason"] = (
        f"Manual close @ ${price:.2f} — "
        f"{'profit' if pnl >= 0 else 'loss'} "
        f"{'+'if pnl>=0 else ''}{pnl:.0f}"
        + (f" ({reason})" if reason != "MANUAL" else "")
    )
    pos["unrealized_pnl"] = 0

    store.save_position(pos)
    open_after = [p for p in open_pos if p["id"] != position_id]
    positions_value = sum(p["shares_remaining"] * p.get("current_price", p["entry_price"]) for p in open_after)
    state["total_value"] = round(state["cash"] + positions_value, 2)
    store.save_state(state)

    try:
        from core.trade_log import log_closed_position
        log_closed_position(pos)
    except Exception as _tl_err:
        print(f"  [TradeLog] warning: {_tl_err}")

    return {"closed": True, "ticker": pos["ticker"], "pnl": pos["realized_pnl"]}


# ── Portfolio snapshot ─────────────────────────────────────────
def get_portfolio() -> Dict:
    state      = store.load_state()
    open_pos   = store.load_positions("open")
    closed_pos = store.load_positions("closed")

    all_closed = closed_pos
    winning = [p for p in all_closed if p.get("realized_pnl", 0) > 0]
    total_realized   = round(sum(p.get("realized_pnl", 0) for p in all_closed), 2)
    total_unrealized = round(sum(p.get("unrealized_pnl", 0) for p in open_pos), 2)
    total_pnl = round(total_realized + total_unrealized, 2)
    win_rate  = round(len(winning) / len(all_closed) * 100, 1) if all_closed else 0

    return {
        "state": state,
        "open_positions": open_pos,
        "closed_positions": closed_pos[-20:],
        "stats": {
            "open_count": len(open_pos),
            "slots_available": MAX_POSITIONS - len(open_pos),
            "total_closed": len(all_closed),
            "win_rate": win_rate,
            "total_realized_pnl": total_realized,
            "total_unrealized_pnl": total_unrealized,
            "total_pnl": total_pnl,
            "total_pnl_pct": round(total_pnl / state["starting_capital"] * 100, 2),
            "cash": state["cash"],
            "total_value": state["total_value"],
        }
    }


# ── Auto-fill from scanner ─────────────────────────────────────
def autopilot_fill(watchlist_name: str = "full_scan") -> Dict:
    """Scan + open positions for all available slots."""
    from core.market_data import fetch_market_regime
    from core.watchlists import get_watchlist
    from core.conviction_engine import run_scan

    state    = store.load_state()
    open_pos = store.load_positions("open")
    slots    = MAX_POSITIONS - len(open_pos)

    if slots == 0:
        return {"message": "Portfolio full", "opened": []}

    existing_tickers = {p["ticker"] for p in open_pos}
    wl_data = get_watchlist(watchlist_name)
    all_symbols = wl_data.get("tickers", []) if isinstance(wl_data, dict) else list(wl_data)
    symbols = [s for s in all_symbols if s not in existing_tickers]

    if not symbols:
        return {"message": "No new symbols to scan", "opened": []}

    scan_result = run_scan(symbols[:20])
    candidates = [r for r in scan_result.get("results", [])
                  if not r.get("hard_fail") and r.get("conviction_pct", 0) >= 65
                  and r["ticker"] not in existing_tickers]
    candidates = candidates[:slots]

    if not candidates:
        top_scores = [(r["ticker"], r.get("conviction_pct", 0), r.get("hard_fail_reason", "no fail")[:40])
                      for r in scan_result.get("results", [])[:8] if not r.get("hard_fail")]
        return {"message": "No qualifying signals (need conviction >= 65%)",
                "opened": [], "top_scores": top_scores}

    opened = []
    for c in candidates:
        result = open_position(
            ticker=c["ticker"],
            entry_price=c.get("entry_high", c["last_close"]),
            sl=c["sl"], tp1=c["tp1"], tp2=c["tp2"], tp3=c["tp3"],
            conviction=c["conviction_pct"],
            asset_type="stock",
        )
        if "error" not in result:
            opened.append({"ticker": c["ticker"], "conviction": c["conviction_pct"],
                           "entry": result["entry_price"], "shares": result["shares"]})

    return {"opened": opened, "slots_used": len(opened)}
