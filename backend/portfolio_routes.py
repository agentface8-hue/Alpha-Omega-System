

# ══════════════════════════════════════════════════════════════
# PORTFOLIO TAB — Paper Trading Engine v1.0
# ══════════════════════════════════════════════════════════════

@app.get("/api/portfolio")
async def get_portfolio():
    from core.portfolio_manager import get_portfolio
    return get_portfolio()

@app.post("/api/portfolio/check")
async def check_portfolio():
    from core.portfolio_manager import check_portfolio
    return check_portfolio()

@app.post("/api/portfolio/open")
async def open_position(body: dict):
    from core.portfolio_manager import open_position
    ticker     = body.get("ticker", "").upper()
    entry      = float(body.get("entry_price", 0))
    sl         = float(body.get("sl", 0))
    tp1        = float(body.get("tp1", 0))
    tp2        = float(body.get("tp2", 0))
    tp3        = float(body.get("tp3", 0))
    conviction = int(body.get("conviction", 0))
    asset_type = body.get("asset_type", "stock")
    signal_id  = body.get("signal_id", "")
    if not ticker or not entry or not sl or not tp1:
        raise HTTPException(status_code=400, detail="ticker, entry_price, sl, tp1 required")
    return open_position(ticker, entry, sl, tp1, tp2, tp3, conviction, asset_type, signal_id)

@app.post("/api/portfolio/close/{position_id}")
async def close_position_endpoint(position_id: str, body: dict = {}):
    from core.portfolio_manager import close_position
    reason = body.get("reason", "MANUAL") if body else "MANUAL"
    return close_position(position_id, reason)

@app.post("/api/portfolio/autopilot")
async def portfolio_autopilot(body: dict = {}):
    from core.portfolio_manager import autopilot_fill
    watchlist = (body or {}).get("watchlist", "full_scan")
    return autopilot_fill(watchlist)

@app.post("/api/portfolio/reset")
async def reset_portfolio():
    from core.portfolio_store import clear_all_positions
    from core.portfolio_manager import get_portfolio
    clear_all_positions()
    portfolio = get_portfolio()
    return {"reset": True, "message": "Portfolio reset to $25,000", **portfolio}

@app.get("/api/portfolio/status")
async def portfolio_storage_status():
    from core.portfolio_store import supabase_ready
    return {"supabase": supabase_ready(), "storage": "supabase" if supabase_ready() else "json_fallback"}
