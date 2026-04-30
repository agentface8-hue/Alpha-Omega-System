"""
Printing Profits API routes — all under /api/printing/
Appended to backend/main.py. Zero collision with existing routes.
"""

# ══════════════════════════════════════════════════════════════
# PRINTING PROFITS — Dual Long/Short Trading Engine
# ══════════════════════════════════════════════════════════════

@app.post("/api/printing/scan")
async def printing_scan(body: dict = {}):
    from core.printing_scanner import run_dual_scan
    watchlist = (body or {}).get("watchlist", "full_scan")
    symbols   = (body or {}).get("symbols", None)
    return run_dual_scan(symbols=symbols, watchlist_name=watchlist)

@app.get("/api/printing/futures")
async def printing_futures():
    from core.futures_data import fetch_all_futures
    return fetch_all_futures()

@app.get("/api/printing/regime")
async def printing_regime():
    from core.market_data import fetch_market_regime
    from core.regime_engine import get_strategy_mode
    regime = fetch_market_regime()
    mode   = get_strategy_mode(regime)
    return {"regime": regime, "mode": mode}

@app.get("/api/printing/portfolio")
async def printing_portfolio():
    from core.printing_portfolio import get_portfolio
    return get_portfolio()

@app.post("/api/printing/portfolio/check")
async def printing_check():
    from core.printing_portfolio import check_portfolio
    return check_portfolio()

@app.post("/api/printing/portfolio/open")
async def printing_open(body: dict):
    from core.printing_portfolio import open_position
    ticker    = body.get("ticker","").upper()
    direction = body.get("direction","long")
    entry     = float(body.get("entry_price", 0))
    sl        = float(body.get("sl", 0))
    tp1       = float(body.get("tp1", 0))
    tp2       = float(body.get("tp2", 0))
    tp3       = float(body.get("tp3", 0))
    conv      = int(body.get("conviction", 65))
    if not ticker or not entry or not sl or not tp1:
        raise HTTPException(status_code=400, detail="ticker, entry_price, sl, tp1 required")
    return open_position(ticker, direction, entry, sl, tp1, tp2, tp3, conv)

@app.post("/api/printing/portfolio/close/{position_id}")
async def printing_close(position_id: str, body: dict = {}):
    from core.printing_portfolio import close_position
    reason = (body or {}).get("reason", "MANUAL")
    return close_position(position_id, reason)

@app.post("/api/printing/portfolio/autopilot")
async def printing_autopilot(body: dict = {}):
    from core.printing_portfolio import autopilot_dual
    watchlist = (body or {}).get("watchlist", "full_scan")
    return autopilot_dual(watchlist)

@app.post("/api/printing/portfolio/reset")
async def printing_reset():
    from core.printing_store import clear_all
    clear_all()
    return {"reset": True, "message": "Printing Profits portfolio reset to $25,000"}

@app.get("/api/printing/status")
async def printing_status():
    from core.printing_store import supabase_ready
    return {"supabase": supabase_ready(),
            "storage": "supabase" if supabase_ready() else "json_fallback"}
