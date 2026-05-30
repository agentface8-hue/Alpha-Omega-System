"""
portfolio_manager.py — Paper trading portfolio engine v1.5
v1.5: Sector Momentum Gate — blocks new positions in bottom-ranked sectors
      Exit alert when open position's sector drops to bottom 3
v1.4: Dynamic TP Phase 2 — conviction score scales TP distances at entry
v1.3: Shared scan cache — autopilot saves all results; bench reads from same scan
v1.2: Momentum fade -> AUTO-CLOSE (5 checks/2%), Alpha-Mega symbols_override
v1.1: ATR at entry, trailing TP3
"""
import uuid, datetime, math, json, time
from pathlib import Path
from typing import Dict, Any, List, Optional
import threading
import yfinance as yf
from core import portfolio_store as store

SCAN_CACHE_PATH = Path(__file__).parent.parent / "calibration" / "last_portfolio_scan.json"
SCAN_CACHE_TTL  = 3600 * 4  # 4 hours

# Prevent concurrent check_portfolio() runs from stacking up and exhausting threads
_CHECK_LOCK = threading.Lock()

MAX_POSITIONS   = 8
STARTING_CASH   = 25_000.0
MAX_POS_SIZE    = 3_340.0   # 12.5% of ~$26,740 -- council rule
MIN_POS_SIZE    = 2_500.0
MAX_RISK        = 500.0
SPLIT_TP1_PCT   = 0.50
SPLIT_TP2_PCT   = 0.30
SPLIT_TP3_PCT   = 0.20
MAX_TP3_EXTENSIONS = 3

FADE_CHECKS_NEEDED = 5    # consecutive lower price checks before auto-close
FADE_GIVEBACK_PCT  = 2.0  # % given back from MFE peak before auto-close

# Sector Momentum Gate thresholds
SECTOR_BLOCK_RANK      = 9    # sectors ranked 9,10,11 -> BLOCKED entirely
SECTOR_WARN_RANK       = 7    # sectors ranked 7,8 -> need higher conviction
SECTOR_WARN_CONVICTION = 78   # minimum conviction required for weak sectors


# -- Dynamic TP Phase 2 -------------------------------------------------------
def _dtp_scale(conviction: int) -> tuple:
    if   conviction >= 85: return 1.50, f"DTP +50% (conviction {conviction}%)"
    elif conviction >= 80: return 1.35, f"DTP +35% (conviction {conviction}%)"
    elif conviction >= 75: return 1.20, f"DTP +20% (conviction {conviction}%)"
    elif conviction >= 70: return 1.10, f"DTP +10% (conviction {conviction}%)"
    elif conviction >= 65: return 1.00, f"DTP baseline (conviction {conviction}%)"
    else:                  return 0.85, f"DTP -15% (conviction {conviction}%)"


def _live_price(ticker: str, asset_type: str = "stock") -> Optional[float]:
    from core.price_feed import get_price
    return get_price(ticker, asset_type)


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


def _entry_themes_for(ticker: str, sector: str) -> List[str]:
    try:
        from core.theme_engine import get_ticker_themes
        return get_ticker_themes(ticker, sector)
    except Exception:
        return []


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

    # -- Duplicate company blocker --------------------------------------------
    _SIBLING_MAP = {
        'GOOGL':'ALPHABET','GOOG':'ALPHABET',
        'BRK.A':'BERKSHIRE','BRK.B':'BERKSHIRE',
        'META':'META','FB':'META',
    }
    _fam = _SIBLING_MAP.get(ticker.upper(), ticker.upper())
    for _p in open_pos:
        _p_fam = _SIBLING_MAP.get(_p['ticker'], _p['ticker'])
        if _p_fam == _fam and _p['ticker'] != ticker.upper():
            return {"error": f"Duplicate company blocked: {ticker} same company as {_p['ticker']} ({_fam})"}

    # -- Sector checks (concentration + momentum gate) ------------------------
    _sector = "Unknown"
    try:
        from core.universe_builder import get_ticker_sector as _gts
        _sector = _gts(ticker.upper())

        # 1. Concentration: max 25% of portfolio per sector
        _total_val  = state.get("total_value", STARTING_CASH) or STARTING_CASH
        _sector_val = sum(p.get("position_size", 0) for p in open_pos
                          if _gts(p["ticker"]) == _sector)
        _sector_pct = (_sector_val / _total_val * 100) if _total_val > 0 else 0
        if _sector_pct >= 25.0:
            return {"error": f"Sector limit: {_sector} already at {_sector_pct:.0f}% (max 25%)"}

        # 2. Sector Momentum Gate: live ranking from Sector Momentum Universe
        try:
            from core.sector_ranker import rank_sectors as _rank_secs
            _rankings   = _rank_secs()
            _total_secs = len(_rankings) or 11
            _rank_entry = next((r for r in _rankings if r.get("sector") == _sector), None)
            _rank_num   = _rank_entry.get("rank", 0) if _rank_entry else 0

            if _rank_num >= SECTOR_BLOCK_RANK:
                # Bottom sectors (rank 9,10,11): BLOCKED -- this is exactly why SECTOR MOMENTUM was built
                return {
                    "error": (
                        f"Sector blocked: {_sector} ranked "
                        f"#{_rank_num}/{_total_secs} in Sector Momentum Universe "
                        f"(bottom 3 -- system says avoid)"
                    )
                }
            elif _rank_num >= SECTOR_WARN_RANK and conviction < SECTOR_WARN_CONVICTION:
                # Weak sectors (rank 7-8): need stronger signal
                return {
                    "error": (
                        f"Sector weak: {_sector} ranked #{_rank_num}/{_total_secs} -- "
                        f"need conviction >= {SECTOR_WARN_CONVICTION}% "
                        f"(have {conviction}%)"
                    )
                }
            elif _rank_num > 0:
                score = _rank_entry.get("score", 0) if _rank_entry else 0
                print(f"  [SECTOR-GATE] {ticker}: {_sector} #{_rank_num}/{_total_secs} score={score:.2f} -- OK")
        except Exception as _se:
            print(f"  [SECTOR-GATE] rank check skipped: {_se}")

    except Exception:
        pass  # If sector lookup fails, allow the trade

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

    # -- Dynamic TP Phase 2 ---------------------------------------------------
    dtp_scale_val, dtp_note = _dtp_scale(conviction)
    if dtp_scale_val != 1.0:
        _sl_dist = max(entry_price - sl, 0.01)
        tp1 = round(entry_price + (tp1 - entry_price) * dtp_scale_val, 4)
        tp2 = round(entry_price + (tp2 - entry_price) * dtp_scale_val, 4)
        tp3 = round(entry_price + (tp3 - entry_price) * dtp_scale_val, 4)
        if tp2 <= tp1: tp2 = round(tp1 + _sl_dist * 0.5, 4)
        if tp3 <= tp2: tp3 = round(tp2 + _sl_dist * 0.5, 4)
        print(f"  [DTP] {ticker}: scale={dtp_scale_val}x TP1=${tp1:.2f} TP2=${tp2:.2f} TP3=${tp3:.2f} ({dtp_note})")

    now          = datetime.datetime.utcnow().isoformat()
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
        atr_at_entry = round((entry_price - sl) * 2, 4)

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
        "dtp_scale": dtp_scale_val, "dtp_note": dtp_note,
        "pillar_scores": pillar_scores or {},
        "tas": tas or "",
        "sector": _sector,
        "entry_themes": _entry_themes_for(ticker, _sector),
        "entry_market_context": entry_market_context or {},
        "trades": [{"id": str(uuid.uuid4()), "type": "entry",
                    "price": round(entry_price, 4), "shares": sizing["shares"],
                    "pnl": 0.0, "executed_at": now}],
        "updated_at": now,
    }

    state["cash"] = round(state["cash"] - sizing["position_size"], 2)
    store.save_position(pos)
    store.save_state(state)
    # Telegram alert — position opened
    try:
        from core.telegram_alerts import alert_signal_created
        alert_signal_created({**pos, "regime": entry_market_context.get("regime","") if entry_market_context else "",
                               "target_method": "atr"})
    except Exception: pass
    return pos


def check_portfolio() -> Dict:
    # If already running, return current state immediately — prevents thread-pool exhaustion
    if not _CHECK_LOCK.acquire(blocking=False):
        return {**get_portfolio(), "skipped": True, "reason": "check already in progress"}
    try:
        return _check_portfolio_inner()
    finally:
        _CHECK_LOCK.release()


def _check_portfolio_inner() -> Dict:
    open_pos     = store.load_positions("open")
    state        = store.load_state()
    updates      = []
    closed_count = 0

    # Fetch sector rankings ONCE per cycle (not once per position)
    _sector_ranks = {}
    try:
        from core.sector_ranker import rank_sectors as _rs
        for r in (_rs() or []):
            _sector_ranks[r.get("sector", "")] = r.get("rank", 0)
    except Exception:
        pass

    for pos in open_pos:
        ticker = pos["ticker"]; a_type = pos.get("asset_type","stock")
        price  = _live_price(ticker, a_type)
        if price is None:
            updates.append({"ticker": ticker, "status": "price_error"}); continue

        entry  = pos["entry_price"]; sl = pos["sl"]
        tp1    = pos["tp1"];         tp2 = pos["tp2"]; tp3 = pos["tp3"]
        shares = pos["shares_remaining"]

        # -- TP ordering guardrail --------------------------------------------
        _atr_g = pos.get("atr_at_entry", 0) or abs(tp1 - entry) or abs(entry - sl)
        if tp2 > 0 and tp1 > 0 and tp2 <= tp1:
            pos["tp2"] = round(tp1 + _atr_g * 0.5, 4); tp2 = pos["tp2"]
            print(f"  [TP-ORDER] {ticker}: TP2 corrected to ${tp2:.2f}")
        if tp3 > 0 and tp3 <= tp2:
            pos["tp3"] = round(tp2 + _atr_g * 0.5, 4); tp3 = pos["tp3"]
            print(f"  [TP-ORDER] {ticker}: TP3 corrected to ${tp3:.2f}")
        elif tp3 > 0 and tp3 <= tp1:
            pos["tp3"] = round(tp1 + _atr_g * 1.0, 4); tp3 = pos["tp3"]

        pos["current_price"]      = price
        gain_from_entry           = price - entry
        pos["mae"]                = round(min(pos.get("mae",0), gain_from_entry), 4)
        pos["mfe"]                = round(max(pos.get("mfe",0), gain_from_entry), 4)
        pos["unrealized_pnl"]     = round(shares * (price - entry), 2)
        pos["unrealized_pnl_pct"] = round((price - entry) / entry * 100, 2)
        now = datetime.datetime.utcnow().isoformat(); action = None

        # -- ATR auto-refresh (with timeout guard) ----------------------------
        if not pos.get("atr_refreshed"):
            try:
                import pandas as pd
                _hist = yf.Ticker(ticker).history(period="30d", interval="1d", timeout=5)
                if not _hist.empty and len(_hist) >= 14:
                    _h, _l, _cp = _hist["High"], _hist["Low"], _hist["Close"].shift(1)
                    _tr = pd.concat([_h - _l, (_h - _cp).abs(), (_l - _cp).abs()], axis=1).max(axis=1)
                    _real_atr = round(float(_tr.rolling(14).mean().iloc[-1]), 4)
                    if _real_atr > 0:
                        pos["atr_at_entry"] = _real_atr; pos["atr_refreshed"] = True
            except Exception: pass

        # -- Sector Momentum exit alert (uses pre-fetched ranks) --------------
        if not pos.get("sector_exit_alerted"):
            try:
                _pos_sector = pos.get("sector", "")
                if _pos_sector and _pos_sector != "Unknown" and _sector_ranks:
                    _rank_num = _sector_ranks.get(_pos_sector, 0)
                    if _rank_num >= SECTOR_BLOCK_RANK:
                        pos["sector_exit_alerted"] = True
                        pnl_str = f"{pos['unrealized_pnl_pct']:+.1f}%"
                        print(f"  [SECTOR-EXIT] {ticker}: {_pos_sector} now #{_rank_num} -- consider closing ({pnl_str})")
                        try:
                            from core.telegram_alerts import _send
                            _send(
                                f"SECTOR EXIT ALERT -- {ticker}\n"
                                f"{_pos_sector} dropped to #{_rank_num}/11 in Sector Momentum Universe\n"
                                f"Position PnL: {pnl_str}\n"
                                f"Sector momentum says AVOID -- consider closing"
                            )
                        except Exception: pass
            except Exception: pass

        # -- Trailing Stop-Loss -----------------------------------------------
        _atr = pos.get("atr_at_entry", 0)
        if _atr > 0 and price > entry and shares > 0:
            _multiple = (price - entry) / _atr
            _new_sl = None; _sl_note = ""
            if   _multiple >= 2.0:
                _cand = round(entry + _atr * 1.0, 4)
                if _cand > pos["sl"]: _new_sl = _cand; _sl_note = "TSL 2xATR -> entry+1xATR"
            elif _multiple >= 1.5:
                _cand = round(entry + _atr * 0.5, 4)
                if _cand > pos["sl"]: _new_sl = _cand; _sl_note = "TSL 1.5xATR -> entry+0.5xATR"
            elif _multiple >= 1.0:
                _cand = round(entry, 4)
                if _cand > pos["sl"]: _new_sl = _cand; _sl_note = "TSL 1xATR -> break-even"
            if _new_sl:
                _old_sl = pos["sl"]; pos["sl"] = _new_sl
                if "sl_history" not in pos: pos["sl_history"] = []
                pos["sl_history"].append({"sl": _new_sl, "note": _sl_note, "ts": now, "label": "TSL"})
                action = f"TSL: SL raised ${_old_sl:.2f} -> ${_new_sl:.2f} ({_sl_note})"
                print(f"  [TSL] {ticker}: ${_old_sl:.2f} -> ${_new_sl:.2f}")

        # -- Momentum fade -> AUTO-CLOSE --------------------------------------
        if pos.get("tp1_hit") and pos["unrealized_pnl_pct"] > 0 and not pos.get("momentum_fade_close"):
            prev_p = pos.get("prev_check_price", price)
            pos["momentum_down_count"] = pos.get("momentum_down_count",0) + 1 if price < prev_p else 0
            pos["prev_check_price"] = price
            mfe_pct     = pos["mfe"] / entry * 100 if entry > 0 else 0
            curr_pnl    = pos["unrealized_pnl_pct"]
            giving_back = mfe_pct - curr_pnl
            if pos.get("momentum_down_count",0) >= FADE_CHECKS_NEEDED and giving_back >= FADE_GIVEBACK_PCT and not pos.get("fade_alert_sent"):
                pos["fade_alert_sent"] = True; pos["momentum_fade_close"] = True
                print(f"  [FADE-CLOSE] {ticker}: gave back {giving_back:.1f}% from MFE +{mfe_pct:.1f}%")

        # -- SL hit -----------------------------------------------------------
        if price <= sl and shares > 0:
            pnl = round(shares * (sl - entry), 2)
            pos["trades"].append({"id":str(uuid.uuid4()),"type":"sl_exit","price":sl,"shares":shares,"pnl":pnl,"tp_level":"SL","executed_at":now})
            pos["realized_pnl"] = round(pos.get("realized_pnl",0)+pnl, 2)
            state["cash"]       = round(state["cash"]+shares*sl, 2)
            pos["shares_remaining"] = 0; pos["status"] = "closed"; pos["closed_at"] = now
            pos["close_reason"] = f"Stop-loss hit @ ${sl:.2f} (entry ${entry:.2f}, loss ${abs(pnl):.0f})"
            pos["unrealized_pnl"] = 0; action = f"SL hit @ ${sl}"; closed_count += 1

        # -- Momentum fade AUTO-CLOSE -----------------------------------------
        elif pos.get("momentum_fade_close") and shares > 0:
            mfe_c = pos["mfe"] / entry * 100 if entry > 0 else 0
            curr_pnl = pos["unrealized_pnl_pct"]; gb = round(mfe_c - curr_pnl, 2)
            pnl = round(shares * (price - entry), 2)
            pos["trades"].append({"id":str(uuid.uuid4()),"type":"momentum_fade_close","price":price,"shares":shares,"pnl":pnl,"tp_level":"FADE","executed_at":now})
            pos["realized_pnl"] = round(pos.get("realized_pnl",0)+pnl, 2)
            state["cash"]       = round(state["cash"]+shares*price, 2)
            pos["shares_remaining"] = 0; pos["status"] = "closed"; pos["closed_at"] = now
            pos["close_reason"] = f"Auto-close: gave back {gb:.1f}% from peak +{mfe_c:.1f}% -- locked in +{curr_pnl:.1f}%"
            pos["unrealized_pnl"] = 0; action = f"Momentum fade auto-close @ ${price:.2f} (+{curr_pnl:.1f}%)"; closed_count += 1
            try:
                from core.telegram_alerts import alert_momentum_fade_close
                alert_momentum_fade_close({"ticker":ticker,"entry_price":entry,"current_price":price,"close_price":price,"pnl_pct":curr_pnl,"mfe_pct":mfe_c}, curr_pnl, mfe_c)
            except: pass

        # -- TP3 hit -- TRAILING LOGIC ----------------------------------------
        elif price >= tp3 and not pos.get("tp3_hit") and pos.get("tp2_hit"):
            extensions = pos.get("tp3_extensions", 0)
            if extensions < MAX_TP3_EXTENSIONS and price > tp3 * 1.005:
                atr_est = pos.get("atr_at_entry", 0) or abs(tp1 - sl)
                new_tp3 = round(price + atr_est * 0.5, 4); old_tp3 = pos["tp3"]
                pos["tp3"] = new_tp3; pos["tp3_extensions"] = extensions+1; pos["trailing_active"] = True
                try:
                    from core.telegram_alerts import alert_tp_extended
                    alert_tp_extended({"ticker":ticker,"entry_price":entry,"current_price":price,"trailing_active":True}, new_tp3, extensions+1)
                except: pass
                action = f"TP3 extended ${old_tp3:.2f} -> ${new_tp3:.2f} (ext #{extensions+1})"
            else:
                tp3_sh = pos["shares_remaining"]; pnl = round(tp3_sh*(tp3-entry),2)
                pos["trades"].append({"id":str(uuid.uuid4()),"type":"partial_tp3","price":tp3,"shares":tp3_sh,"pnl":pnl,"tp_level":"TP3","executed_at":now})
                pos["realized_pnl"] = round(pos.get("realized_pnl",0)+pnl, 2)
                state["cash"]       = round(state["cash"]+tp3_sh*tp3, 2)
                pos["tp3_hit"] = True; pos["shares_remaining"] = 0; pos["status"] = "closed"; pos["closed_at"] = now
                ext_count = pos.get("tp3_extensions",0)
                pos["close_reason"] = (f"Trailing TP3 final close @ ${tp3:.2f} after {ext_count} extensions (+${pnl:.0f})" if pos.get("trailing_active") else f"TP3 hit @ ${tp3:.2f} (+${pnl:.0f})")
                pos["unrealized_pnl"] = 0; action = f"TP3 hit @ ${tp3}"; closed_count += 1
                try:
                    from core.telegram_alerts import alert_tp_hit
                    alert_tp_hit(pos, "tp3", tp3)
                except Exception: pass

        # -- TP2 hit ----------------------------------------------------------
        elif price >= tp2 and not pos.get("tp2_hit") and pos.get("tp1_hit"):
            tp2_sh = min(pos.get("tp2_shares",1), pos["shares_remaining"])
            pnl    = round(tp2_sh*(tp2-entry),2)
            pos["trades"].append({"id":str(uuid.uuid4()),"type":"partial_tp2","price":tp2,"shares":tp2_sh,"pnl":pnl,"tp_level":"TP2","executed_at":now})
            pos["realized_pnl"] = round(pos.get("realized_pnl",0)+pnl, 2); state["cash"] = round(state["cash"]+tp2_sh*tp2, 2)
            pos["tp2_hit"] = True; pos["shares_remaining"] -= tp2_sh; pos["status"] = "partial"; pos["sl"] = round(tp1,4)
            action = f"TP2 hit @ ${tp2}, SL -> TP1"
            try:
                from core.telegram_alerts import alert_tp_hit
                alert_tp_hit(pos, "tp2", tp2)
            except Exception: pass

        # -- TP1 hit ----------------------------------------------------------
        elif price >= tp1 and not pos.get("tp1_hit"):
            tp1_sh = min(pos.get("tp1_shares",1), pos["shares_remaining"])
            pnl    = round(tp1_sh*(tp1-entry),2)
            pos["trades"].append({"id":str(uuid.uuid4()),"type":"partial_tp1","price":tp1,"shares":tp1_sh,"pnl":pnl,"tp_level":"TP1","executed_at":now})
            pos["realized_pnl"] = round(pos.get("realized_pnl",0)+pnl, 2); state["cash"] = round(state["cash"]+tp1_sh*tp1, 2)
            pos["tp1_hit"] = True; pos["shares_remaining"] -= tp1_sh; pos["status"] = "partial"; pos["sl"] = round(entry,4)
            action = f"TP1 hit @ ${tp1}, SL -> BE"
            try:
                from core.telegram_alerts import alert_tp_hit
                alert_tp_hit(pos, "tp1", tp1)
            except Exception: pass

        pos["updated_at"] = now
        store.save_position(pos)
        updates.append({"ticker":ticker,"price":price,"action":action,"pnl":pos["unrealized_pnl"],"status":pos["status"]})

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
    pos["trades"].append({"id":str(uuid.uuid4()),"type":"manual_close","price":price,"shares":shares,"pnl":pnl,"tp_level":reason,"executed_at":now})
    pos["realized_pnl"] = round(pos.get("realized_pnl",0)+pnl, 2); state["cash"] = round(state["cash"]+shares*price, 2)
    pos["shares_remaining"] = 0; pos["status"] = "closed"; pos["closed_at"] = now
    pos["close_reason"] = f"Manual close @ ${price:.2f} -- {'profit' if pnl>=0 else 'loss'} {'+' if pnl>=0 else ''}{pnl:.0f}" + (f" ({reason})" if reason!="MANUAL" else "")
    pos["unrealized_pnl"] = 0
    store.save_position(pos)
    # Telegram alert — position closed
    try:
        from core.telegram_alerts import alert_signal_closed
        alert_signal_closed(pos, reason, price)
    except Exception: pass
    open_after = [p for p in open_pos if p["id"]!=position_id]
    positions_value = sum(p["shares_remaining"]*p.get("current_price",p["entry_price"]) for p in open_after)
    state["total_value"] = round(state["cash"]+positions_value, 2)
    store.save_state(state)
    try:
        from core.trade_log import log_closed_position; log_closed_position(pos)
    except Exception as e: print(f"  [TradeLog] warning: {e}")
    return {"closed":True,"ticker":pos["ticker"],"pnl":pos["realized_pnl"]}


def get_portfolio() -> Dict:
    state      = store.load_state() or {}
    open_pos   = store.load_positions("open")
    closed_pos = store.load_positions("closed")
    winning    = [p for p in closed_pos if p.get("realized_pnl", 0) > 0]
    total_realized   = round(sum(p.get("realized_pnl", 0) for p in closed_pos), 2)
    total_unrealized = round(sum(p.get("unrealized_pnl", 0) for p in open_pos), 2)
    total_pnl = round(total_realized + total_unrealized, 2)
    win_rate  = round(len(winning) / len(closed_pos) * 100, 1) if closed_pos else 0
    starting_capital = state.get("starting_capital") or 25000.0
    return {
        "state": state, "open_positions": open_pos, "closed_positions": closed_pos[-20:],
        "stats": {
            "open_count":          len(open_pos),
            "slots_available":     MAX_POSITIONS - len(open_pos),
            "total_closed":        len(closed_pos),
            "win_rate":            win_rate,
            "total_realized_pnl":  total_realized,
            "total_unrealized_pnl": total_unrealized,
            "total_pnl":           total_pnl,
            "total_pnl_pct":       round(total_pnl / starting_capital * 100, 2),
            "cash":                state.get("cash", 25000.0),
            "total_value":         state.get("total_value", 25000.0),
        }
    }


def autopilot_fill(watchlist_name: str = "full_scan", symbols_override: list = None) -> Dict:
    """Fill open slots using sector-ranked universe. open_position() enforces the sector gate."""
    from core.conviction_engine import run_scan
    from core.market_data import fetch_market_regime
    from core.signal_tracker import _is_us_market_open
    mkt = _is_us_market_open()
    # Paper trading — allow autopilot in any session; prices use 15-min delayed data anyway.
    # Just surface a soft warning in the response instead of hard-blocking.
    session_note = None if mkt["market_open"] else f"Note: market is in {mkt['session']} — using delayed prices"

    state    = store.load_state()
    open_pos = store.load_positions("open")
    slots    = MAX_POSITIONS - len(open_pos)
    if slots == 0: return {"message": "Portfolio full", "opened": [], "slots_used": 0}
    existing_tickers = {p["ticker"] for p in open_pos}

    if symbols_override:
        all_syms = symbols_override
        universe_source = f"alpha_mega ({len(all_syms)} stocks)"
    else:
        try:
            from core.momentum_screener import screen_universe
            screened = screen_universe(top_n=30)
            all_syms = [r["ticker"] for r in screened]
            top3 = ", ".join(f"{r['ticker']}({r['sector'][:5]})" for r in screened[:3])
            universe_source = f"momentum_screen >$10B -- top3: {top3}"
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

    print(f"[AUTOPILOT] Universe: {universe_source} -> scanning {len(symbols)} tickers")

    try:
        regime = fetch_market_regime().get("regime", "Trending Bull")
    except Exception:
        regime = "Trending Bull"

    from core.calibrator import get_regime_conviction_threshold, sector_conviction_penalty, regime_conviction_penalty
    from core.theme_engine import theme_conviction_adjustment
    conv_threshold = get_regime_conviction_threshold(regime)
    regime_penalty = regime_conviction_penalty(regime)
    print(f"[AUTOPILOT] Regime: {regime} -> threshold {conv_threshold}% + penalty {regime_penalty}%")

    scan_result = run_scan(symbols)
    raw = scan_result.get("results", [])

    try:
        SCAN_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        SCAN_CACHE_PATH.write_text(json.dumps({"ts": time.time(), "built_at": datetime.datetime.utcnow().isoformat(), "universe": universe_source, "regime": regime, "conv_threshold": conv_threshold, "results": raw}))
    except Exception as _ce:
        print(f"[AUTOPILOT] Cache save failed: {_ce}")

    try:
        from core.universe_builder import get_ticker_sector as _gts_early
    except Exception:
        def _gts_early(t): return "Other"

    def _learning_gate(r: dict) -> bool:
        if r.get("hard_fail") or r.get("rr", 0) < 1.5 or r["ticker"] in existing_tickers:
            return False
        sector = _gts_early(r["ticker"])
        theme_bonus = theme_conviction_adjustment(r["ticker"], sector)
        need = conv_threshold + sector_conviction_penalty(sector) + regime_penalty - theme_bonus
        return r.get("conviction_pct", 0) >= need

    candidates = sorted(
        [r for r in raw if _learning_gate(r)],
        key=lambda x: (
            x["conviction_pct"]
            - sector_conviction_penalty(_gts_early(x["ticker"]))
            + theme_conviction_adjustment(x["ticker"], _gts_early(x["ticker"]))
        ),
        reverse=True,
    )

    # ── VOL GATE: data-driven from 74-trade analysis ──────────────────────────
    # vol < 1.0x → WR 46%, avg +1.31%  |  vol ≥ 1.0x or ACCUMULATION → WR 67%+
    vol_blocked = []
    vol_passed  = []
    for c in candidates:
        vol   = c.get("vol_ratio", 0)
        vdir  = c.get("vol_direction", "NEUTRAL")
        if vol >= 1.0 or vdir == "ACCUMULATION":
            vol_passed.append(c)
        else:
            vol_blocked.append({"ticker": c["ticker"], "vol": round(vol, 2),
                                 "reason": f"vol {vol:.2f}x < 1.0x (74-trade gate)"})
    if vol_blocked:
        print(f"[AUTOPILOT] Vol gate blocked {len(vol_blocked)}: {[b['ticker'] for b in vol_blocked]}")
    candidates = vol_passed

    if not candidates:
        top_scores = [(r["ticker"], r.get("conviction_pct", 0)) for r in raw if not r.get("hard_fail")][:8]
        return {"message": f"No qualifying signals (conviction >= {conv_threshold}%, vol >= 1.0x, R:R >= 1.5)", "opened": [], "universe": universe_source, "top_scores": top_scores, "regime": regime}

    # ── SECTOR GATE: block red-sector stocks ─────────────────────────────────
    try:
        from core.sector_ranker import get_ticker_sector_rank
        sector_gate_blocked = []
        gated_candidates = []
        for c in candidates:
            sr = get_ticker_sector_rank(c["ticker"])
            if not sr["allowed"]:
                sector_gate_blocked.append({
                    "ticker": c["ticker"],
                    "sector": sr["sector"],
                    "score":  sr["score"],
                    "reason": f"Sector gate: {sr['sector']} score={sr['score']:.2f} (rank #{sr['rank']})"
                })
                print(f"  [SECTOR GATE] Blocking {c['ticker']} — {sr['sector']} score={sr['score']:.2f}")
            else:
                c["sector_rank"] = sr
                gated_candidates.append(c)
        candidates = gated_candidates
        if sector_gate_blocked:
            print(f"  [SECTOR GATE] Blocked {len(sector_gate_blocked)} tickers from red sectors")
    except Exception as _sge:
        sector_gate_blocked = []
        print(f"  [SECTOR GATE] Failed ({_sge}) — proceeding without gate")

    if not candidates:
        return {
            "message": f"All candidates blocked by sector gate (need score > 0)",
            "opened": [], "universe": universe_source,
            "sector_gate_blocked": sector_gate_blocked, "regime": regime,
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

    _portfolio_val    = state.get("total_value", STARTING_CASH) or STARTING_CASH
    _max_sector_slots = max(1, int(_portfolio_val * 0.25 / (MAX_POS_SIZE or 3340)))

    final_candidates = []
    for c in candidates:
        sector = get_ticker_sector(c["ticker"])
        held   = already_held_sectors.get(sector, 0)
        in_q   = sector_counts.get(sector, 0)
        if held + in_q < _max_sector_slots:
            sector_counts[sector] = in_q + 1
            final_candidates.append(c)
        if len(final_candidates) >= slots:
            break

    opened = []
    for c in final_candidates:
        result = open_position(
            ticker=c["ticker"], entry_price=c.get("entry_high", c["last_close"]),
            sl=c["sl"], tp1=c["tp1"], tp2=c["tp2"], tp3=c["tp3"],
            conviction=c["conviction_pct"], asset_type="stock",
        )
        if "error" not in result:
            opened.append({"ticker": c["ticker"], "conviction": c["conviction_pct"], "sector": get_ticker_sector(c["ticker"]), "entry": result["entry_price"], "shares": result["shares"], "rr": c.get("rr", 0)})
        else:
            print(f"  [AUTOPILOT] {c['ticker']} blocked: {result['error']}")

    opened_tickers   = {o["ticker"] for o in opened}
    all_open_tickers = existing_tickers | opened_tickers
    bench = sorted(
        [r for r in raw if not r.get("hard_fail") and r.get("conviction_pct", 0) >= conv_threshold and r.get("rr", 0) >= 1.8 and r["ticker"] not in all_open_tickers],
        key=lambda x: x["conviction_pct"], reverse=True
    )[:10]

    result = {
        "opened": opened, "slots_used": len(opened),
        "universe": universe_source, "regime": regime,
        "conviction_threshold": conv_threshold,
        "bench_candidates": [{"ticker": b["ticker"], "conviction_pct": b.get("conviction_pct", 0), "rr": b.get("rr", 0), "sector": get_ticker_sector(b["ticker"]), "entry_price": b.get("entry_high", b.get("last_close", 0)), "sl": b.get("sl", 0), "tp1": b.get("tp1", 0), "tp2": b.get("tp2", 0), "tp3": b.get("tp3", 0)} for b in bench],
    }
    if session_note:
        result["session_note"] = session_note
    return result
