"""
printing_portfolio.py — Long + Short paper trading engine for Printing Profits tab.
Supports both directions. Isolated from portfolio_manager.py (different tables/state).
"""
import uuid, datetime, math
from typing import Dict, Any, List, Optional
import yfinance as yf
from core import printing_store as store
from core.kelly_sizer import kelly_size

MAX_POSITIONS = 8
STARTING_CASH = 25_000.0
SPLIT_TP1 = 0.50
SPLIT_TP2 = 0.30
SPLIT_TP3 = 0.20


def _live_price(ticker: str) -> Optional[float]:
    """Real-time price via Alpha Vantage (yfinance fallback)."""
    from core.price_feed import get_price
    asset_type = "crypto" if "-USD" in ticker.upper() else "stock"
    return get_price(ticker, asset_type)


def open_position(ticker: str, direction: str, entry_price: float,
                  sl: float, tp1: float, tp2: float, tp3: float,
                  conviction: int = 0, signal_id: str = "") -> Dict:
    """Open a LONG or SHORT paper position with Kelly sizing."""
    state    = store.load_state()
    open_pos = store.load_positions("open")

    if len(open_pos) >= MAX_POSITIONS:
        return {"error": f"Max {MAX_POSITIONS} positions reached"}

    sizing = kelly_size(conviction, entry_price, sl, state["cash"], direction)
    if sizing["skip"] or sizing["shares"] < 1:
        return {"error": f"Conviction {conviction}% below 65% threshold — skip"}
    if sizing["position_size"] > state["cash"]:
        # Try minimum viable
        min_sh = max(1, math.ceil(3000 / entry_price))
        min_sz = round(min_sh * entry_price, 2)
        if min_sz > state["cash"]:
            return {"error": f"Insufficient cash (need ${min_sz:.0f}, have ${state['cash']:.0f})"}
        sl_dist = abs(sl - entry_price)
        sizing = {"shares": min_sh, "position_size": min_sz,
                  "risk_usd": round(min_sh * sl_dist, 2), "risk_pct": 2.0, "skip": False}

    now = datetime.datetime.utcnow().isoformat()
    shares   = sizing["shares"]
    tp1_sh   = max(1, round(shares * SPLIT_TP1))
    tp2_sh   = max(1, round(shares * SPLIT_TP2))
    tp3_sh   = max(0, shares - tp1_sh - tp2_sh)

    pos = {
        "id":              str(uuid.uuid4()),
        "ticker":          ticker.upper(),
        "direction":       direction,            # "long" or "short"
        "status":          "open",
        "entry_price":     round(entry_price, 4),
        "entry_date":      now,
        "shares":          shares,
        "shares_remaining": shares,
        "tp1_shares":      tp1_sh,
        "tp2_shares":      tp2_sh,
        "tp3_shares":      tp3_sh,
        "position_size":   sizing["position_size"],
        "risk_usd":        sizing["risk_usd"],
        "sl":              round(sl, 4),
        "sl_original":     round(sl, 4),
        "tp1":             round(tp1, 4),
        "tp2":             round(tp2, 4),
        "tp3":             round(tp3, 4),
        "tp1_hit":         False,
        "tp2_hit":         False,
        "current_price":   round(entry_price, 4),
        "unrealized_pnl":  0.0,
        "unrealized_pnl_pct": 0.0,
        "realized_pnl":    0.0,
        "mae":             0.0,
        "mfe":             0.0,
        "conviction":      conviction,
        "signal_id":       signal_id,
        "trades":          [{"id": str(uuid.uuid4()), "type": "entry",
                             "price": round(entry_price, 4), "shares": shares,
                             "pnl": 0.0, "executed_at": now}],
        "updated_at":      now,
    }

    state["cash"] = round(state["cash"] - sizing["position_size"], 2)
    store.save_position(pos)
    store.save_state(state)
    return pos


def _pnl(pos: Dict, price: float) -> float:
    """P&L for either direction."""
    shares = pos["shares_remaining"]
    entry  = pos["entry_price"]
    if pos["direction"] == "short":
        return round(shares * (entry - price), 2)  # profit when price falls
    return round(shares * (price - entry), 2)       # profit when price rises


def check_portfolio() -> Dict:
    """Refresh all open positions. Auto-execute split exits for both directions."""
    open_pos  = store.load_positions("open")
    state     = store.load_state()
    updates   = []
    closed_ct = 0

    for pos in open_pos:
        price = _live_price(pos["ticker"])
        if price is None:
            updates.append({"ticker": pos["ticker"], "status": "price_error"})
            continue

        entry     = pos["entry_price"]
        sl        = pos["sl"]
        tp1       = pos["tp1"]
        tp2       = pos["tp2"]
        tp3       = pos["tp3"]
        shares    = pos["shares_remaining"]
        direction = pos.get("direction", "long")
        now       = datetime.datetime.utcnow().isoformat()

        pos["current_price"] = price

        # MAE/MFE from entry perspective
        raw_move = price - entry if direction == "long" else entry - price
        pos["mae"] = round(min(pos.get("mae", 0), raw_move), 4)
        pos["mfe"] = round(max(pos.get("mfe", 0), raw_move), 4)
        pos["unrealized_pnl"]     = _pnl(pos, price)
        pos["unrealized_pnl_pct"] = round(raw_move / entry * 100, 2)

        action = None
        is_long = (direction == "long")

        # ── SL check ─────────────────────────────────────────────────────────
        sl_hit = (price <= sl) if is_long else (price >= sl)

        if sl_hit and shares > 0:
            fill  = sl
            pnl   = round(shares * (fill - entry), 2) if is_long else round(shares * (entry - fill), 2)
            pos["trades"].append({"id": str(uuid.uuid4()), "type": "sl_exit",
                                   "price": fill, "shares": shares, "pnl": pnl,
                                   "tp_level": "SL", "executed_at": now})
            pos["realized_pnl"]  = round(pos.get("realized_pnl",0) + pnl, 2)
            state["cash"]        = round(state["cash"] + shares * fill, 2)
            pos["shares_remaining"] = 0
            pos["status"]        = "closed"
            pos["closed_at"]     = now
            pos["unrealized_pnl"] = 0
            action = f"SL hit @ ${fill}"
            closed_ct += 1

        # ── TP3 check ─────────────────────────────────────────────────────────
        elif (not pos.get("tp3_hit")) and pos.get("tp2_hit"):
            tp3_hit = (price >= tp3) if is_long else (price <= tp3)
            if tp3_hit:
                tp3_sh = pos["shares_remaining"]
                fill   = tp3
                pnl    = round(tp3_sh * (fill - entry), 2) if is_long else round(tp3_sh * (entry - fill), 2)
                pos["trades"].append({"id": str(uuid.uuid4()), "type": "partial_tp3",
                                       "price": fill, "shares": tp3_sh, "pnl": pnl,
                                       "tp_level": "TP3", "executed_at": now})
                pos["realized_pnl"]  = round(pos.get("realized_pnl",0) + pnl, 2)
                state["cash"]        = round(state["cash"] + tp3_sh * fill, 2)
                pos["tp3_hit"]       = True
                pos["shares_remaining"] = 0
                pos["status"]        = "closed"
                pos["closed_at"]     = now
                pos["unrealized_pnl"] = 0
                action = f"TP3 hit @ ${fill}"
                closed_ct += 1

        # ── TP2 check ─────────────────────────────────────────────────────────
        elif (not pos.get("tp2_hit")) and pos.get("tp1_hit"):
            tp2_hit = (price >= tp2) if is_long else (price <= tp2)
            if tp2_hit:
                tp2_sh = min(pos.get("tp2_shares",1), pos["shares_remaining"])
                fill   = tp2
                pnl    = round(tp2_sh * (fill - entry), 2) if is_long else round(tp2_sh * (entry - fill), 2)
                pos["trades"].append({"id": str(uuid.uuid4()), "type": "partial_tp2",
                                       "price": fill, "shares": tp2_sh, "pnl": pnl,
                                       "tp_level": "TP2", "executed_at": now})
                pos["realized_pnl"]  = round(pos.get("realized_pnl",0) + pnl, 2)
                state["cash"]        = round(state["cash"] + tp2_sh * fill, 2)
                pos["tp2_hit"]       = True
                pos["shares_remaining"] -= tp2_sh
                pos["status"]        = "partial"
                pos["sl"] = round(tp1, 4)  # trail SL to TP1
                action = f"TP2 hit @ ${fill}, SL -> TP1"

        # ── TP1 check ─────────────────────────────────────────────────────────
        elif not pos.get("tp1_hit"):
            tp1_hit = (price >= tp1) if is_long else (price <= tp1)
            if tp1_hit:
                tp1_sh = min(pos.get("tp1_shares",1), pos["shares_remaining"])
                fill   = tp1
                pnl    = round(tp1_sh * (fill - entry), 2) if is_long else round(tp1_sh * (entry - fill), 2)
                pos["trades"].append({"id": str(uuid.uuid4()), "type": "partial_tp1",
                                       "price": fill, "shares": tp1_sh, "pnl": pnl,
                                       "tp_level": "TP1", "executed_at": now})
                pos["realized_pnl"]  = round(pos.get("realized_pnl",0) + pnl, 2)
                state["cash"]        = round(state["cash"] + tp1_sh * fill, 2)
                pos["tp1_hit"]       = True
                pos["shares_remaining"] -= tp1_sh
                pos["status"]        = "partial"
                pos["sl"] = round(entry, 4)  # trail SL to breakeven
                action = f"TP1 hit @ ${fill}, SL -> BE"

        pos["updated_at"] = now
        store.save_position(pos)
        updates.append({"ticker": pos["ticker"], "direction": direction,
                        "price": price, "action": action,
                        "pnl": pos["unrealized_pnl"], "status": pos["status"]})

    # Recalc total
    open_after = store.load_positions("open")
    pos_value  = sum(p["shares_remaining"] * p.get("current_price", p["entry_price"])
                     for p in open_after)
    state["total_value"] = round(state["cash"] + pos_value, 2)
    store.save_state(state)
    return {"updates": updates, "closed": closed_ct, "portfolio": get_portfolio()}


def close_position(position_id: str, reason: str = "MANUAL") -> Dict:
    open_pos = store.load_positions("open")
    pos = next((p for p in open_pos if p["id"] == position_id), None)
    if not pos: return {"error": "Position not found"}

    state  = store.load_state()
    price  = _live_price(pos["ticker"]) or pos["current_price"]
    shares = pos["shares_remaining"]
    entry  = pos["entry_price"]
    is_long = pos.get("direction","long") == "long"
    pnl    = round(shares * (price - entry), 2) if is_long else round(shares * (entry - price), 2)
    now    = datetime.datetime.utcnow().isoformat()

    pos["trades"].append({"id": str(uuid.uuid4()), "type": "manual_close",
                           "price": price, "shares": shares, "pnl": pnl,
                           "tp_level": reason, "executed_at": now})
    pos["realized_pnl"]  = round(pos.get("realized_pnl",0) + pnl, 2)
    state["cash"]        = round(state["cash"] + shares * price, 2)
    pos["shares_remaining"] = 0
    pos["status"]        = "closed"
    pos["closed_at"]     = now
    pos["unrealized_pnl"] = 0
    store.save_position(pos)

    remaining = [p for p in open_pos if p["id"] != position_id]
    pos_value = sum(p["shares_remaining"] * p.get("current_price", p["entry_price"])
                    for p in remaining)
    state["total_value"] = round(state["cash"] + pos_value, 2)
    store.save_state(state)
    return {"closed": True, "ticker": pos["ticker"], "direction": pos["direction"],
            "pnl": pos["realized_pnl"]}


def get_portfolio() -> Dict:
    state      = store.load_state()
    open_pos   = store.load_positions("open")
    closed_pos = store.load_positions("closed")

    winning  = [p for p in closed_pos if p.get("realized_pnl", 0) > 0]
    realized = round(sum(p.get("realized_pnl",0) for p in closed_pos), 2)
    unreal   = round(sum(p.get("unrealized_pnl",0) for p in open_pos), 2)

    long_exp  = round(sum(p["shares_remaining"] * p.get("current_price", p["entry_price"])
                          for p in open_pos if p.get("direction","long") == "long"), 2)
    short_exp = round(sum(p["shares_remaining"] * p.get("current_price", p["entry_price"])
                          for p in open_pos if p.get("direction","long") == "short"), 2)

    return {
        "state":            state,
        "open_positions":   open_pos,
        "closed_positions": closed_pos[-20:],
        "stats": {
            "open_count":          len(open_pos),
            "slots_available":     MAX_POSITIONS - len(open_pos),
            "total_closed":        len(closed_pos),
            "win_rate":            round(len(winning)/len(closed_pos)*100,1) if closed_pos else 0,
            "total_realized_pnl":  realized,
            "total_unrealized_pnl": unreal,
            "total_pnl":           round(realized + unreal, 2),
            "total_pnl_pct":       round((realized+unreal) / state["starting_capital"] * 100, 2),
            "cash":                state["cash"],
            "total_value":         state["total_value"],
            "long_exposure":       long_exp,
            "short_exposure":      short_exp,
        },
    }


def autopilot_dual(watchlist_name: str = "full_scan") -> Dict:
    """Scan and open best long + short signals to fill available slots."""
    from core.printing_scanner import run_dual_scan
    state    = store.load_state()
    open_pos = store.load_positions("open")
    slots    = MAX_POSITIONS - len(open_pos)
    if slots == 0: return {"message": "Portfolio full", "opened": []}

    existing = {p["ticker"] for p in open_pos}
    scan     = run_dual_scan(watchlist_name=watchlist_name)
    mode     = scan["mode"]

    # Interleave best longs and shorts
    candidates = []
    longs  = [r for r in scan["longs"]  if r["ticker"] not in existing]
    shorts = [r for r in scan["shorts"] if r["ticker"] not in existing]

    if mode["mode"] == "BULL_MOMENTUM":
        candidates = longs[:slots]
    elif mode["mode"] == "BEAR_MOMENTUM":
        candidates = shorts[:slots]
    else:
        # Mix: alternate long/short up to slots
        for i in range(slots):
            if i % 2 == 0 and i // 2 < len(longs):  candidates.append(longs[i//2])
            elif (i // 2) < len(shorts):              candidates.append(shorts[i//2])
        if not candidates:
            candidates = (longs + shorts)[:slots]

    opened = []
    for c in candidates[:slots]:
        direction = c.get("direction", "long")
        entry  = c.get("entry_high", c["last_close"]) if direction == "long" else c.get("entry", c["last_close"])
        result = open_position(
            ticker=c["ticker"], direction=direction,
            entry_price=entry,
            sl=c["sl"], tp1=c["tp1"], tp2=c.get("tp2", c["tp1"]),
            tp3=c.get("tp3", c["tp1"]),
            conviction=c["conviction_pct"],
        )
        if "error" not in result:
            opened.append({"ticker": c["ticker"], "direction": direction,
                           "conviction": c["conviction_pct"],
                           "entry": result["entry_price"], "shares": result["shares"]})
    return {"opened": opened, "slots_used": len(opened), "mode": mode["mode"]}
