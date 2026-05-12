"""
portfolio_manager.py — Paper trading portfolio engine v1.3
v1.3: Shared scan cache — autopilot saves all results; bench reads from same scan
v1.2: Momentum fade → AUTO-CLOSE (5 checks/2%), Alpha-Mega symbols_override
v1.1: ATR at entry, trailing TP3
"""
import uuid, datetime, math, json, time
from pathlib import Path
from typing import Dict, Any, List, Optional
import yfinance as yf
from core import portfolio_store as store

SCAN_CACHE_PATH = Path(__file__).parent.parent / "calibration" / "last_portfolio_scan.json"
SCAN_CACHE_TTL  = 3600 * 4  # 4 hours

MAX_POSITIONS   = 10
STARTING_CASH   = 25_000.0
MAX_POS_SIZE    = 5_000.0
MIN_POS_SIZE    = 3_000.0
MAX_RISK        = 500.0
SPLIT_TP1_PCT   = 0.50
SPLIT_TP2_PCT   = 0.30
SPLIT_TP3_PCT   = 0.20
MAX_TP3_EXTENSIONS = 3

FADE_CHECKS_NEEDED = 5    # consecutive lower price checks before auto-close
FADE_GIVEBACK_PCT  = 2.0  # % given back from MFE peak before auto-close


def _live_price(ticker: str, asset_type: str = "stock") -> Optional[float]:
    try:
        sym = ticker.upper()
        if asset_type == "crypto":
            sym = sym + "-USD" if not sym.endswith("-USD") else sym
        tk   = yf.Ticker(sym)
        data = tk.history(period="1d", interval="1m")
        if not data.empty: return round(float(data["Close"].iloc[-1]), 4)
        data = tk.history(period="2d")
        if not data.empty: return round(float(data["Close"].iloc[-1]), 4)
    except: pass
    return None


def _size_position(entry: float, sl: float) -> Dict:
    sl_dist        = max(entry - sl, 0.01)
    shares_by_risk = math.floor(MAX_RISK / sl_dist)
    max_shares     = math.floor(MAX_POS_SIZE / entry)
    min_shares     = math.ceil(MIN_POS_SIZE / entry)
    shares         = max(min_shares, min(shares_by_risk, max_shares))
    if shares < 1: shares = 1
    position_size = round(shares * entry, 2)
    risk_actual   = round(shares * sl_dist, 2)
    tp1_shares = max(1, round(shares * SPLIT_TP1_PCT))
    tp2_shares = max(1, round(shares * SPLIT_TP2_PCT))
    tp3_shares = shares - tp1_shares - tp2_shares
    if tp3_shares < 0: tp3_shares = 0
    return {"shares": shares, "position_size": position_size, "risk_actual": risk_actual,
            "tp1_shares": tp1_shares, "tp2_shares": tp2_shares, "tp3_shares": tp3_shares}


def open_position(ticker: str, entry_price: float, sl: float,
                  tp1: float, tp2: float, tp3: float,
                  conviction: int = 0, asset_type: str = "stock",
                  signal_id: str = "",
                  pillar_scores: dict = None, tas: str = "",
                  entry_market_context: dict = None) -> Dict:
    state    = store.load_state()
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
            sizing = {"shares": min_shares, "position_size": min_size,
                      "risk_actual": round(min_shares * max(entry_price - sl, 0.01), 2),
                      "tp1_shares": tp1_sh, "tp2_shares": tp2_sh, "tp3_shares": tp3_sh}
        else:
            return {"error": f"Insufficient cash (need ${min_size:.2f}, have ${state['cash']:.0f})"}

    now          = datetime.datetime.utcnow().isoformat()
    # Real 14-day ATR via yfinance
    atr_at_entry = 0.0
    try:
        import pandas as pd
        _hist = yf.Ticker(ticker.upper()).history(period="30d", interval="1d")
        if not _hist.empty and len(_hist) >= 14:
            _h, _l, _cp = _hist["High"], _hist["Low"], _hist["Close"].shift(1)
            _tr = pd.concat([_h - _l, (_h - _cp).abs(), (_l - _cp).abs()], axis=1).max(axis=1)
            atr_at_entry = round(float(_tr.rolling(14).mean().iloc[-1]), 4)
    except Exception:
        pass
    if atr_at_entry <= 0:
        atr_at_entry = round((entry_price - sl) * 2, 4)  # fallback if fetch fails

    pos = {
        "id": str(uuid.uuid4()), "ticker": ticker.upper(), "status": "open",
        "asset_type": asset_type,
        "entry_price": round(entry_price, 4), "entry_date": now,
        "shares": sizing["shares"], "shares_remaining": sizing["shares"],
        "tp1_shares": sizing["tp1_shares"], "tp2_shares": sizing["tp2_shares"],
        "tp3_shares": sizing["tp3_shares"],
        "position_size": sizing["position_size"], "risk_actual": sizing["risk_actual"],
        "sl": round(sl, 4), "sl_original": round(sl, 4),
        "tp1": round(tp1, 4), "tp2": round(tp2, 4), "tp3": round(tp3, 4),
        "tp1_hit": False, "tp2_hit": False, "tp3_hit": False,
        "current_price": round(entry_price, 4),
        "unrealized_pnl": 0.0, "unrealized_pnl_pct": 0.0, "realized_pnl": 0.0,
        "mae": 0.0, "mfe": 0.0,
        "atr_at_entry": atr_at_entry,
        "tp3_extensions": 0, "trailing_active": False,
        "prev_check_price": round(entry_price, 4),
        "momentum_down_count": 0, "fade_alert_sent": False,
        "momentum_fade_close": False,
        "conviction": conviction, "signal_id": signal_id, "close_reason": None,
        "pillar_scores": pillar_scores or {},
        "tas": tas or "",
        "entry_market_context": entry_market_context or {},
        "trades": [{"id": str(uuid.uuid4()), "type": "entry",
                    "price": round(entry_price, 4), "shares": sizing["shares"],
                    "pnl": 0.0, "executed_at": now}],
        "updated_at": now,
    }

    state["cash"] = round(state["cash"] - sizing["position_size"], 2)
    store.save_position(pos)
    store.save_state(state)
    return pos


def check_portfolio() -> Dict:
    open_pos     = store.load_positions("open")
    state        = store.load_state()
    updates      = []
    closed_count = 0

    for pos in open_pos:
        ticker = pos["ticker"]; a_type = pos.get("asset_type","stock")
        price  = _live_price(ticker, a_type)
        if price is None:
            updates.append({"ticker": ticker, "status": "price_error"}); continue

        entry  = pos["entry_price"]; sl = pos["sl"]
        tp1    = pos["tp1"];         tp2 = pos["tp2"]; tp3 = pos["tp3"]
        shares = pos["shares_remaining"]

        # ── TP ordering guardrail — fix inversions from stale/dynamic TP data ─
        _atr_g = pos.get("atr_at_entry", 0) or abs(tp1 - entry) or abs(entry - sl)
        _fixed = False
        if tp2 > 0 and tp1 > 0 and tp2 <= tp1:
            pos["tp2"] = round(tp1 + _atr_g * 0.5, 4)
            tp2 = pos["tp2"]; _fixed = True
            print(f"  [TP-ORDER] {ticker}: TP2 corrected → ${tp2:.2f}")
        if tp3 > 0 and tp3 <= tp2:
            pos["tp3"] = round(tp2 + _atr_g * 0.5, 4)
            tp3 = pos["tp3"]; _fixed = True
            print(f"  [TP-ORDER] {ticker}: TP3 corrected → ${tp3:.2f}")
        elif tp3 > 0 and tp3 <= tp1:
            pos["tp3"] = round(tp1 + _atr_g * 1.0, 4)
            tp3 = pos["tp3"]; _fixed = True
            print(f"  [TP-ORDER] {ticker}: TP3 corrected → ${tp3:.2f}")

        pos["current_price"]      = price
        gain_from_entry           = price - entry
        pos["mae"]                = round(min(pos.get("mae",0), gain_from_entry), 4)
        pos["mfe"]                = round(max(pos.get("mfe",0), gain_from_entry), 4)
        pos["unrealized_pnl"]     = round(shares * (price - entry), 2)
        pos["unrealized_pnl_pct"] = round((price - entry) / entry * 100, 2)
        now = datetime.datetime.utcnow().isoformat(); action = None

        # ── ATR auto-refresh (once per position, replaces formula estimate) ───
        if not pos.get("atr_refreshed"):
            try:
                import pandas as pd
                _hist = yf.Ticker(ticker).history(period="30d", interval="1d")
                if not _hist.empty and len(_hist) >= 14:
                    _h, _l, _cp = _hist["High"], _hist["Low"], _hist["Close"].shift(1)
                    _tr = pd.concat([_h - _l, (_h - _cp).abs(), (_l - _cp).abs()], axis=1).max(axis=1)
                    _real_atr = round(float(_tr.rolling(14).mean().iloc[-1]), 4)
                    if _real_atr > 0:
                        old_atr = pos.get("atr_at_entry", 0)
                        pos["atr_at_entry"]  = _real_atr
                        pos["atr_refreshed"] = True
                        print(f"  [ATR-REFRESH] {ticker}: ${old_atr:.2f} → ${_real_atr:.2f}")
            except Exception as _ae:
                print(f"  [ATR-REFRESH] {ticker} failed: {_ae}")

        # ── Trailing Stop-Loss (TSL) — ratchet SL up as price rises ───────────
        # Runs on every check. SL only moves UP, never down.
        _atr = pos.get("atr_at_entry", 0)
        if _atr > 0 and price > entry and shares > 0:
            _multiple = (price - entry) / _atr
            _new_sl   = None
            _sl_note  = ""
            if _multiple >= 2.0:
                _cand = round(entry + _atr * 1.0, 4)
                if _cand > pos["sl"]: _new_sl = _cand; _sl_note = "TSL 2×ATR → entry+1×ATR"
            elif _multiple >= 1.5:
                _cand = round(entry + _atr * 0.5, 4)
                if _cand > pos["sl"]: _new_sl = _cand; _sl_note = "TSL 1.5×ATR → entry+0.5×ATR"
            elif _multiple >= 1.0:
                _cand = round(entry, 4)
                if _cand > pos["sl"]: _new_sl = _cand; _sl_note = "TSL 1×ATR → break-even"
            if _new_sl:
                _old_sl = pos["sl"]
                pos["sl"] = _new_sl
                if "sl_history" not in pos: pos["sl_history"] = []
                pos["sl_history"].append({"sl": _new_sl, "note": _sl_note, "ts": now, "label": "TSL"})
                action = f"TSL: SL raised ${_old_sl:.2f} → ${_new_sl:.2f} ({_sl_note})"
                print(f"  [TSL] {ticker}: ${_old_sl:.2f} → ${_new_sl:.2f}")

        # ── Momentum fade → AUTO-CLOSE ──────────────────────────────────────
        # After TP1 hit and in profit: if price declines FADE_CHECKS_NEEDED
        # consecutive times AND gives back FADE_GIVEBACK_PCT% from peak,
        # the system auto-closes to lock in profits. No human needed.
        if pos.get("tp1_hit") and pos["unrealized_pnl_pct"] > 0 and not pos.get("momentum_fade_close"):
            prev_p = pos.get("prev_check_price", price)
            if price < prev_p:
                pos["momentum_down_count"] = pos.get("momentum_down_count",0) + 1
            else:
                pos["momentum_down_count"] = 0
            pos["prev_check_price"] = price

            mfe_pct     = pos["mfe"] / entry * 100 if entry > 0 else 0
            curr_pnl    = pos["unrealized_pnl_pct"]
            giving_back = mfe_pct - curr_pnl

            if pos.get("momentum_down_count",0) >= FADE_CHECKS_NEEDED and giving_back >= FADE_GIVEBACK_PCT and not pos.get("fade_alert_sent"):
                pos["fade_alert_sent"]    = True
                pos["momentum_fade_close"] = True  # triggers auto-close below
                print(f"  [FADE-CLOSE] {ticker}: auto-closing — gave back {giving_back:.1f}% from MFE +{mfe_pct:.1f}%")

        # ── SL hit ──────────────────────────────────────────────────────────
        if price <= sl and shares > 0:
            pnl = round(shares * (sl - entry), 2)
            pos["trades"].append({"id":str(uuid.uuid4()),"type":"sl_exit",
                                   "price":sl,"shares":shares,"pnl":pnl,"tp_level":"SL","executed_at":now})
            pos["realized_pnl"] = round(pos.get("realized_pnl",0)+pnl, 2)
            state["cash"]       = round(state["cash"]+shares*sl, 2)
            pos["shares_remaining"] = 0; pos["status"] = "closed"; pos["closed_at"] = now
            pos["close_reason"] = f"Stop-loss hit @ ${sl:.2f} (entry ${entry:.2f}, loss ${abs(pnl):.0f})"
            pos["unrealized_pnl"] = 0; action = f"SL hit @ ${sl}"; closed_count += 1

        # ── Momentum fade AUTO-CLOSE ─────────────────────────────────────────
        elif pos.get("momentum_fade_close") and shares > 0:
            mfe_c    = pos["mfe"] / entry * 100 if entry > 0 else 0
            curr_pnl = pos["unrealized_pnl_pct"]
            gb       = round(mfe_c - curr_pnl, 2)
            pnl      = round(shares * (price - entry), 2)
            pos["trades"].append({"id":str(uuid.uuid4()),"type":"momentum_fade_close",
                                   "price":price,"shares":shares,"pnl":pnl,
                                   "tp_level":"FADE","executed_at":now})
            pos["realized_pnl"]     = round(pos.get("realized_pnl",0)+pnl, 2)
            state["cash"]           = round(state["cash"]+shares*price, 2)
            pos["shares_remaining"] = 0; pos["status"] = "closed"; pos["closed_at"] = now
            pos["close_reason"]     = (
                f"Auto-close: gave back {gb:.1f}% from peak +{mfe_c:.1f}% "
                f"— locked in +{curr_pnl:.1f}%"
            )
            pos["unrealized_pnl"] = 0
            action = f"Momentum fade auto-close @ ${price:.2f} (+{curr_pnl:.1f}%)"
            closed_count += 1
            try:
                from core.telegram_alerts import alert_momentum_fade_close
                alert_momentum_fade_close(
                    {"ticker":ticker,"entry_price":entry,"current_price":price,
                     "close_price":price,"pnl_pct":curr_pnl,"mfe_pct":mfe_c},
                    curr_pnl, mfe_c
                )
            except: pass

        # ── TP3 hit — TRAILING LOGIC ─────────────────────────────────────────
        elif price >= tp3 and not pos.get("tp3_hit") and pos.get("tp2_hit"):
            extensions = pos.get("tp3_extensions", 0)
            if extensions < MAX_TP3_EXTENSIONS and price > tp3 * 1.005:
                atr_est = pos.get("atr_at_entry", 0)
                if atr_est <= 0: atr_est = abs(tp1 - sl)
                new_tp3 = round(price + atr_est * 0.5, 4); old_tp3 = pos["tp3"]
                pos["tp3"] = new_tp3; pos["tp3_extensions"] = extensions+1; pos["trailing_active"] = True
                try:
                    from core.telegram_alerts import alert_tp_extended
                    alert_tp_extended({"ticker":ticker,"entry_price":entry,"current_price":price,"trailing_active":True},
                                      new_tp3, extensions+1)
                except: pass
                action = f"TP3 extended ${old_tp3:.2f} → ${new_tp3:.2f} (ext #{extensions+1})"
            else:
                tp3_sh = pos["shares_remaining"]; pnl = round(tp3_sh*(tp3-entry),2)
                pos["trades"].append({"id":str(uuid.uuid4()),"type":"partial_tp3",
                                       "price":tp3,"shares":tp3_sh,"pnl":pnl,"tp_level":"TP3","executed_at":now})
                pos["realized_pnl"] = round(pos.get("realized_pnl",0)+pnl, 2)
                state["cash"]       = round(state["cash"]+tp3_sh*tp3, 2)
                pos["tp3_hit"] = True; pos["shares_remaining"] = 0
                pos["status"]  = "closed"; pos["closed_at"] = now
                ext_count = pos.get("tp3_extensions",0)
                pos["close_reason"] = (
                    f"Trailing TP3 final close @ ${tp3:.2f} after {ext_count} extension{'s' if ext_count!=1 else ''} (+${pnl:.0f})"
                    if pos.get("trailing_active")
                    else f"TP3 hit @ ${tp3:.2f} — full target reached (+${pnl:.0f})"
                )
                pos["unrealized_pnl"] = 0
                action = f"TP3 {'trailing final' if pos.get('trailing_active') else 'hit'} @ ${tp3}"
                closed_count += 1

        # ── TP2 hit ──────────────────────────────────────────────────────────
        elif price >= tp2 and not pos.get("tp2_hit") and pos.get("tp1_hit"):
            tp2_sh = min(pos.get("tp2_shares",1), pos["shares_remaining"])
            pnl    = round(tp2_sh*(tp2-entry),2)
            pos["trades"].append({"id":str(uuid.uuid4()),"type":"partial_tp2",
                                   "price":tp2,"shares":tp2_sh,"pnl":pnl,"tp_level":"TP2","executed_at":now})
            pos["realized_pnl"]     = round(pos.get("realized_pnl",0)+pnl, 2)
            state["cash"]           = round(state["cash"]+tp2_sh*tp2, 2)
            pos["tp2_hit"]          = True; pos["shares_remaining"] -= tp2_sh
            pos["status"]           = "partial"; pos["sl"] = round(tp1,4)
            action = f"TP2 hit @ ${tp2}, SL → TP1"

        # ── TP1 hit ──────────────────────────────────────────────────────────
        elif price >= tp1 and not pos.get("tp1_hit"):
            tp1_sh = min(pos.get("tp1_shares",1), pos["shares_remaining"])
            pnl    = round(tp1_sh*(tp1-entry),2)
            pos["trades"].append({"id":str(uuid.uuid4()),"type":"partial_tp1",
                                   "price":tp1,"shares":tp1_sh,"pnl":pnl,"tp_level":"TP1","executed_at":now})
            pos["realized_pnl"]     = round(pos.get("realized_pnl",0)+pnl, 2)
            state["cash"]           = round(state["cash"]+tp1_sh*tp1, 2)
            pos["tp1_hit"]          = True; pos["shares_remaining"] -= tp1_sh
            pos["status"]           = "partial"; pos["sl"] = round(entry,4)
            action = f"TP1 hit @ ${tp1}, SL → BE"

        pos["updated_at"] = now
        store.save_position(pos)
        updates.append({"ticker":ticker,"price":price,"action":action,
                        "pnl":pos["unrealized_pnl"],"status":pos["status"]})

        if pos["status"] == "closed":
            try:
                from core.trade_log import log_closed_position; log_closed_position(pos)
            except Exception as e: print(f"  [TradeLog] warning: {e}")

    open_after = store.load_positions("open")
    positions_value = sum(p["shares_remaining"]*p.get("current_price",p["entry_price"]) for p in open_after)
    state["total_value"] = round(state["cash"]+positions_value, 2)
    store.save_state(state)
    return {"updates":updates,"closed_this_check":closed_count,"portfolio":get_portfolio()}


def close_position(position_id: str, reason: str = "MANUAL") -> Dict:
    open_pos = store.load_positions("open")
    pos = next((p for p in open_pos if p["id"]==position_id), None)
    if not pos: return {"error": "Position not found"}
    state  = store.load_state()
    price  = _live_price(pos["ticker"], pos.get("asset_type","stock")) or pos["current_price"]
    shares = pos["shares_remaining"]; entry = pos["entry_price"]
    pnl    = round(shares*(price-entry),2); now = datetime.datetime.utcnow().isoformat()
    pos["trades"].append({"id":str(uuid.uuid4()),"type":"manual_close",
                           "price":price,"shares":shares,"pnl":pnl,"tp_level":reason,"executed_at":now})
    pos["realized_pnl"]     = round(pos.get("realized_pnl",0)+pnl, 2)
    state["cash"]           = round(state["cash"]+shares*price, 2)
    pos["shares_remaining"] = 0; pos["status"] = "closed"; pos["closed_at"] = now
    pos["close_reason"]     = (
        f"Manual close @ ${price:.2f} — {'profit' if pnl>=0 else 'loss'} {'+' if pnl>=0 else ''}{pnl:.0f}"
        + (f" ({reason})" if reason!="MANUAL" else "")
    )
    pos["unrealized_pnl"] = 0
    store.save_position(pos)
    open_after = [p for p in open_pos if p["id"]!=position_id]
    positions_value = sum(p["shares_remaining"]*p.get("current_price",p["entry_price"]) for p in open_after)
    state["total_value"] = round(state["cash"]+positions_value, 2)
    store.save_state(state)
    try:
        from core.trade_log import log_closed_position; log_closed_position(pos)
    except Exception as e: print(f"  [TradeLog] warning: {e}")
    return {"closed":True,"ticker":pos["ticker"],"pnl":pos["realized_pnl"]}


def get_portfolio() -> Dict:
    state      = store.load_state()
    open_pos   = store.load_positions("open")
    closed_pos = store.load_positions("closed")
    winning    = [p for p in closed_pos if p.get("realized_pnl",0)>0]
    total_realized   = round(sum(p.get("realized_pnl",0) for p in closed_pos), 2)
    total_unrealized = round(sum(p.get("unrealized_pnl",0) for p in open_pos), 2)
    total_pnl = round(total_realized+total_unrealized, 2)
    win_rate  = round(len(winning)/len(closed_pos)*100,1) if closed_pos else 0
    return {
        "state": state, "open_positions": open_pos,
        "closed_positions": closed_pos[-20:],
        "stats": {
            "open_count": len(open_pos),
            "slots_available": MAX_POSITIONS - len(open_pos),
            "total_closed": len(closed_pos), "win_rate": win_rate,
            "total_realized_pnl": total_realized, "total_unrealized_pnl": total_unrealized,
            "total_pnl": total_pnl,
            "total_pnl_pct": round(total_pnl/state["starting_capital"]*100,2),
            "cash": state["cash"], "total_value": state["total_value"],
        }
    }


def autopilot_fill(watchlist_name: str = "full_scan", symbols_override: list = None) -> Dict:
    """
    Fill open slots using >$10B sector-ranked universe.
    Priority: symbols_override → sector ranker → watchlist fallback.
    Selection: top sectors by momentum, conviction >= 60%, sorted by conviction desc,
               sector cap of 2 positions, min R:R 1.8.
    """
    from core.conviction_engine import run_scan
    from core.market_data import fetch_market_regime
    state    = store.load_state()
    open_pos = store.load_positions("open")
    slots    = MAX_POSITIONS - len(open_pos)
    if slots == 0: return {"message": "Portfolio full", "opened": [], "slots_used": 0}
    existing_tickers = {p["ticker"] for p in open_pos}

    # ── Build scan universe ───────────────────────────────────────────────────
    if symbols_override:
        all_syms = symbols_override
        universe_source = f"alpha_mega ({len(all_syms)} stocks)"
    else:
        try:
            from core.momentum_screener import screen_universe, get_momentum_scan_universe
            screened = screen_universe(top_n=30)
            all_syms = [r["ticker"] for r in screened]
            top3 = ", ".join(
                f"{r['ticker']}({r['sector'][:5]})" for r in screened[:3]
            )
            universe_source = f"momentum_screen >$10B — top3: {top3}"
        except Exception as e:
            print(f"[AUTOPILOT] Momentum screener failed ({e}), falling back to sector ranker")
            try:
                from core.sector_ranker import get_scan_universe, rank_sectors
                rankings = rank_sectors()
                all_syms = get_scan_universe(total_slots=30, top_sectors=4)
                top3 = ", ".join(r["sector"] for r in rankings[:3])
                universe_source = f"sector_ranked >$10B (top: {top3})"
            except Exception as e2:
                print(f"[AUTOPILOT] Sector ranker also failed ({e2}), using watchlist")
                from core.watchlists import get_watchlist
                wl_data  = get_watchlist(watchlist_name)
                all_syms = wl_data.get("tickers", []) if isinstance(wl_data, dict) else list(wl_data)
                universe_source = f"watchlist:{watchlist_name}"

    symbols = [s for s in all_syms if s not in existing_tickers]
    if not symbols:
        return {"message": "No new symbols to scan", "opened": [], "universe": universe_source}

    print(f"[AUTOPILOT] Universe: {universe_source} → scanning {len(symbols)} tickers")

    # ── Regime-based conviction threshold ────────────────────────────────────
    try:
        regime = fetch_market_regime().get("regime", "Trending Bull")
    except Exception:
        regime = "Trending Bull"
    conv_threshold = 70 if regime in ("Choppy / Range", "Trending Bear", "High-Vol Event") else 60
    print(f"[AUTOPILOT] Regime: {regime} → conviction threshold: {conv_threshold}%")

    # ── Run conviction scan ───────────────────────────────────────────────────
    scan_result = run_scan(symbols)
    raw = scan_result.get("results", [])

    # ── Save full scan results to shared cache (bench reads from here) ────────
    try:
        SCAN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        SCAN_CACHE_PATH.write_text(json.dumps({
            "ts":            time.time(),
            "built_at":      datetime.datetime.utcnow().isoformat(),
            "universe":      universe_source,
            "regime":        regime,
            "conv_threshold": conv_threshold,
            "results":       raw,
        }))
    except Exception as _ce:
        print(f"[AUTOPILOT] Cache save failed: {_ce}")

    # ── Filter + sort by conviction desc ─────────────────────────────────────
    candidates = sorted(
        [r for r in raw
         if not r.get("hard_fail")
         and r.get("conviction_pct", 0) >= conv_threshold
         and r.get("rr", 0) >= 1.8
         and r["ticker"] not in existing_tickers],
        key=lambda x: x["conviction_pct"],
        reverse=True
    )

    if not candidates:
        top_scores = [(r["ticker"], r.get("conviction_pct", 0))
                      for r in raw if not r.get("hard_fail")][:8]
        return {
            "message": f"No qualifying signals (need conviction >= {conv_threshold}%, R:R >= 1.8)",
            "opened": [], "universe": universe_source,
            "top_scores": top_scores, "regime": regime,
        }

    # ── Sector cap: max 2 per sector ─────────────────────────────────────────
    try:
        from core.universe_builder import get_ticker_sector
    except Exception:
        def get_ticker_sector(t): return "Other"

    sector_counts: dict = {}
    already_held_sectors = {}
    for p in open_pos:
        s = get_ticker_sector(p["ticker"])
        already_held_sectors[s] = already_held_sectors.get(s, 0) + 1

    final_candidates = []
    for c in candidates:
        sector = get_ticker_sector(c["ticker"])
        held   = already_held_sectors.get(sector, 0)
        in_q   = sector_counts.get(sector, 0)
        if held + in_q < 2:
            sector_counts[sector] = in_q + 1
            final_candidates.append(c)
        if len(final_candidates) >= slots:
            break

    # ── Open positions ────────────────────────────────────────────────────────
    opened = []
    for c in final_candidates:
        result = open_position(
            ticker=c["ticker"],
            entry_price=c.get("entry_high", c["last_close"]),
            sl=c["sl"], tp1=c["tp1"], tp2=c["tp2"], tp3=c["tp3"],
            conviction=c["conviction_pct"], asset_type="stock",
        )
        if "error" not in result:
            opened.append({
                "ticker":     c["ticker"],
                "conviction": c["conviction_pct"],
                "sector":     get_ticker_sector(c["ticker"]),
                "entry":      result["entry_price"],
                "shares":     result["shares"],
                "rr":         c.get("rr", 0),
            })
    # ── Bench: qualifying candidates that weren't opened ─────────────────────
    opened_tickers = {o["ticker"] for o in opened}
    all_open_tickers = existing_tickers | opened_tickers
    bench = sorted(
        [r for r in raw
         if not r.get("hard_fail")
         and r.get("conviction_pct", 0) >= conv_threshold
         and r.get("rr", 0) >= 1.8
         and r["ticker"] not in all_open_tickers],
        key=lambda x: x["conviction_pct"],
        reverse=True
    )[:10]

    return {
        "opened": opened, "slots_used": len(opened),
        "universe": universe_source, "regime": regime,
        "conviction_threshold": conv_threshold,
        "bench_candidates": [
            {"ticker": b["ticker"], "conviction_pct": b.get("conviction_pct", 0),
             "rr": b.get("rr", 0), "sector": get_ticker_sector(b["ticker"]),
             "entry_price": b.get("entry_high", b.get("last_close", 0)),
             "sl": b.get("sl", 0), "tp1": b.get("tp1", 0),
             "tp2": b.get("tp2", 0), "tp3": b.get("tp3", 0)}
            for b in bench
        ],
    }
