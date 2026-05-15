from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from backend.schemas import AnalysisRequest, AnalysisResponse, ScanRequest, ScanResponse, BacktestRequest
import traceback
import random
import time
import uuid
import threading
import os
from typing import Dict, Any

# ── In-memory async scan job store ──────────────────────────────────────────
scan_jobs: Dict[str, Any] = {}


def _run_scan_background(job_id: str, symbols: list):
    """Background thread: runs scan per-ticker so we can report real progress."""
    try:
        from core.market_data import fetch_market_regime, fetch_ticker_data
        from core.conviction_engine import score_ticker
        n = len(symbols)
        scan_jobs[job_id]["progress"] = f"0/{n} stocks scanned"

        regime = fetch_market_regime()
        results = []
        for i, sym in enumerate(symbols):
            scan_jobs[job_id]["progress"] = f"{i}/{n} stocks scanned"
            raw = score_ticker(fetch_ticker_data(sym), regime)
            results.append(raw)
            scan_jobs[job_id]["progress"] = f"{i + 1}/{n} stocks scanned"

        # Sort: non-fails by conviction desc, then hard-fails
        non_fails = sorted([r for r in results if not r["hard_fail"]],
                           key=lambda x: x["conviction_pct"], reverse=True)
        fails = [r for r in results if r["hard_fail"]]
        sorted_results = non_fails + fails

        # Trade plans for top 3 (same logic as run_scan)
        for r in sorted_results[:3]:
            if not r["hard_fail"]:
                r["plan"] = (
                    f"Entry: decisive close ${r['entry_low']}-${r['entry_high']} in final 30min. "
                    f"SL: ${r['sl']} (ATR triple-guard). "
                    f"TP1: ${r['tp1']} (exit 40%, move SL to BE). "
                    f"TP2: ${r['tp2']} (exit 45%). R:R {r.get('rr', '?')}:1."
                )

        spy_chg = regime.get("spy_change_pct", 0)
        direction = "up" if spy_chg > 0 else "down"
        header = (
            f"SPY {direction} {abs(spy_chg)}% at ${regime.get('spy_close', 0)}. "
            f"VIX at {regime['vix']} — {regime['regime']} regime. "
            f"Min R:R requirement: {regime['min_rr']}:1."
        )
        final = {
            "market_header": header,
            "market_regime": regime["regime"],
            "vix_estimate": regime["vix"],
            "results": sorted_results,
        }
        try:
            from core.trade_journal import log_scan
            log_scan(final)
        except Exception as je:
            print(f"[JOURNAL] Log failed: {je}")

        scan_jobs[job_id]["status"] = "complete"
        scan_jobs[job_id]["results"] = final
        scan_jobs[job_id]["progress"] = f"{n}/{n} stocks scanned"

    except Exception as e:
        traceback.print_exc()
        scan_jobs[job_id]["status"] = "error"
        scan_jobs[job_id]["error"] = str(e)
        scan_jobs[job_id]["progress"] = "scan failed"

app = FastAPI(title="Alpha-Omega API")

# ── Seed owner account on startup ─────────────────────────────────────────────


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://alpha-omega-ngfw.vercel.app",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "online", "ts": __import__("datetime").datetime.utcnow().isoformat()}

@app.on_event("startup")
async def startup_all():
    """Single startup handler — auth seed + background services."""
    import logging
    log = logging.getLogger(__name__)

    # 1. Seed owner account
    try:
        owner_pass = os.environ.get("OWNER_PASSWORD", "")
        if owner_pass:
            from backend.auth import ensure_owner_exists
            ensure_owner_exists("avi", owner_pass)
            log.info("[STARTUP] Owner account seeded")
    except Exception as e:
        log.warning(f"[STARTUP] Auth seed skipped: {e}")

    # 2. Keepalive pinger
    try:
        from core.keepalive import start as start_keepalive
        start_keepalive(); log.info("[STARTUP] Keepalive started")
    except Exception as e:
        log.warning(f"[STARTUP] Keepalive failed: {e}")

    # 3. Telegram AI agent
    try:
        from core.telegram_agent import start as start_agent
        start_agent(); log.info("[STARTUP] Telegram agent started")
    except Exception as e:
        log.warning(f"[STARTUP] Telegram agent failed: {e}")

    # 4. Learning loop
    try:
        from core.learning_loop import start as start_learning
        start_learning(); log.info("[STARTUP] Learning loop started")
    except Exception as e:
        log.warning(f"[STARTUP] Learning loop failed: {e}")

# --- Demo Mode Data ---
DEMO_SCENARIOS = {
    "bullish": {
        "consensus_view": "Strong bullish momentum across all signals. Technical breakout confirmed with rising volume, positive sentiment from institutional upgrades, and favorable macro conditions with declining yields supporting growth equities.",
        "confidence_score": 0.87,
        "executioner_decision": "BUY — Enter long position. Allocate 4.2% of portfolio via Kelly Criterion. Set stop-loss at -3.5% below entry. Target: +12% upside over 30-day horizon.",
        "historian": "Price has broken above the 50-day and 200-day moving averages with a Golden Cross forming. RSI at 62 indicates strong momentum without overbought conditions. Volume profile confirms institutional accumulation over the past 5 sessions. MACD histogram expanding bullishly.",
        "newsroom": "Sentiment is overwhelmingly positive. 3 major analyst upgrades in the past week. Social media buzz index at 8.2/10. No significant negative catalysts detected. Earnings whisper numbers suggest a potential beat next quarter.",
        "macro": "10Y yield at 4.12%, declining from 4.35% peak. VIX at 14.2, well below fear threshold. Yield curve normalizing — positive for risk assets. Fed policy: rate cuts expected in coming meetings. No major geopolitical headwinds.",
        "trade_params": {"entry_low": 329.56, "entry_high": 334.55, "sl": 312.62, "sl_note": "ATR triple-guard", "tp1": 373.43, "tp2": 412.18, "rr": 2.0, "qty": 3, "risk_usd": 75},
        "mtf_analysis": {"tf_1h": "BULL", "tf_4h": "BULL", "tf_1d": "BULL", "tf_1w": "BULL"}
    },
    "bearish": {
        "consensus_view": "Bearish divergence detected. Price action weakening despite market strength, negative sentiment shift from insider selling reports, and macro headwinds from rising yields creating unfavorable conditions.",
        "confidence_score": 0.72,
        "executioner_decision": "HALT — Do not enter. Risk/reward unfavorable. Multiple sell signals detected. If holding, tighten stop-loss to -2% and reduce position by 50%. Wait for mean reversion signal before re-entry.",
        "historian": "Bearish divergence on RSI — price making higher highs while RSI makes lower highs. Volume declining on up-days. Price rejected at resistance for the 3rd time. MACD crossover to the downside. Support at the 200-day MA is the last defense.",
        "newsroom": "Insider selling reported — CEO and CFO sold combined $12M in shares. Mixed analyst sentiment with 2 downgrades. Short interest rising to 8.4% of float. Social sentiment shifting negative on Reddit and Twitter.",
        "macro": "10Y yield spiking to 4.52%, creating headwinds for growth stocks. VIX elevated at 22.8. Dollar strengthening, negative for multinational earnings. Fed rhetoric hawkish — 'higher for longer' narrative dominant.",
        "trade_params": {"entry_low": 155.20, "entry_high": 158.50, "sl": 164.80, "sl_note": "above resistance", "tp1": 141.30, "tp2": 134.50, "rr": 1.8, "qty": 5, "risk_usd": 95},
        "mtf_analysis": {"tf_1h": "BEAR", "tf_4h": "BEAR", "tf_1d": "BEAR", "tf_1w": "NEUTRAL"}
    },
    "neutral": {
        "consensus_view": "Mixed signals across all dimensions. Technical indicators are range-bound, sentiment is neutral with no strong catalysts, and macro environment is transitional. No clear edge for directional positioning.",
        "confidence_score": 0.51,
        "executioner_decision": "HOLD — No action. Confidence below threshold (0.51 < 0.85). Signals are contradictory. Monitor for a decisive breakout above resistance or breakdown below support before committing capital.",
        "historian": "Price consolidating in a tight range between support ($142) and resistance ($158). Bollinger Bands squeezing — a big move is brewing but direction is unclear. Volume is average. RSI flat at 50, perfectly neutral.",
        "newsroom": "No major catalysts on the horizon. Earnings are 6 weeks out. Analyst consensus is 'Hold' with a median price target at current levels. Social media activity is muted.",
        "macro": "10Y yield stable at 4.25%. VIX at 17.5 — neither complacent nor fearful. Market awaiting next FOMC meeting for direction. Economic data mixed — strong jobs but cooling PMI.",
        "trade_params": None,
        "mtf_analysis": {"tf_1h": "NEUTRAL", "tf_4h": "BULL", "tf_1d": "BEAR", "tf_1w": "NEUTRAL"}
    }
}


def get_demo_response(symbol: str) -> AnalysisResponse:
    scenario_key = random.choice(["bullish", "bearish", "neutral"])
    scenario = DEMO_SCENARIOS[scenario_key]
    time.sleep(random.uniform(1.0, 3.0))
    return AnalysisResponse(
        symbol=symbol.upper(),
        consensus_view=scenario["consensus_view"],
        confidence_score=scenario["confidence_score"],
        executioner_decision=scenario["executioner_decision"],
        full_report={"historian": scenario["historian"], "newsroom": scenario["newsroom"], "macro": scenario["macro"]},
        trade_params=scenario.get("trade_params"),
        mtf_analysis=scenario.get("mtf_analysis")
    )


@app.get("/")
async def root():
    return {"status": "System Online", "version": "1.0.0", "mode": "demo"}


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_stock(request: AnalysisRequest):
    try:
        symbol = request.symbol.upper()
        try:
            from core.orchestrator import Orchestrator
            orchestrator = Orchestrator()
            context = orchestrator.run_cycle_v2(symbol)
            rec = context.get("recommendation", "HOLD")
            vetoed = context.get("vetoed", False)
            executioner_decision = f"{rec} (vetoed)" if vetoed else rec
            if context.get("position_size_pct") is not None:
                executioner_decision += f" — position size: {context['position_size_pct']:.1f}%"
            return AnalysisResponse(
                symbol=symbol,
                consensus_view=context.get("consensus_view", "N/A"),
                confidence_score=context.get("confidence_score", 0.0),
                executioner_decision=executioner_decision,
                full_report=context.get("reports", {}),
            )
        except Exception as real_err:
            print(f"[V2 FAILED] {real_err}, falling back to smart_analyze...")
            try:
                from core.smart_analyze import analyze
                result = analyze(symbol)
                if "error" in result:
                    return get_demo_response(symbol)
                return AnalysisResponse(**result)
            except Exception as sa_err:
                print(f"[SMART FAILED] {sa_err}, using demo data.")
                return get_demo_response(symbol)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scan")
async def scan_stocks(request: ScanRequest):
    """Start a scan job and return immediately with a job_id for polling."""
    symbols = [s.upper().strip() for s in request.symbols if s.strip()]
    if not symbols:
        raise HTTPException(status_code=400, detail="No symbols provided")
    if len(symbols) > 30:
        raise HTTPException(status_code=400, detail="Maximum 30 tickers per scan")
    job_id = f"scan_{uuid.uuid4().hex[:8]}"
    scan_jobs[job_id] = {
        "status": "running",
        "progress": f"0/{len(symbols)} stocks scanned",
        "results": None,
        "error": None,
    }
    t = threading.Thread(target=_run_scan_background, args=(job_id, symbols), daemon=True)
    t.start()
    return {"job_id": job_id, "status": "running"}


@app.get("/api/scan/status/{job_id}")
async def scan_status(job_id: str):
    """Poll for scan job completion."""
    job = scan_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "status": job["status"],
        "progress": job["progress"],
        "results": job.get("results"),
        "error": job.get("error"),
    }


@app.post("/api/scan/stream")
async def scan_stocks_stream(request: ScanRequest):
    """Stream scan results via SSE — one progress event per ticker, final complete event.
    Avoids in-memory job store and polling; connection stays open for duration of scan."""
    import json as _json
    from fastapi.responses import StreamingResponse as _SR

    symbols = [s.upper().strip() for s in request.symbols if s.strip()]
    if not symbols:
        raise HTTPException(status_code=400, detail="No symbols provided")
    if len(symbols) > 30:
        raise HTTPException(status_code=400, detail="Maximum 30 tickers per scan")

    # Custom encoder to handle numpy scalars from conviction engine
    class _NpEncoder(_json.JSONEncoder):
        def default(self, obj):
            import numpy as _np
            if isinstance(obj, _np.integer): return int(obj)
            if isinstance(obj, _np.floating): return float(obj)
            if isinstance(obj, (_np.bool_,)): return bool(obj)
            if isinstance(obj, _np.ndarray): return obj.tolist()
            return super().default(obj)

    def _dumps(payload):
        return _json.dumps(payload, cls=_NpEncoder)

    async def generate():
        import asyncio
        loop = asyncio.get_event_loop()
        try:
            n = len(symbols)
            yield f"data: {_dumps({'type': 'progress', 'progress': 'Fetching market data...'})}\n\n"

            def _regime():
                from core.market_data import fetch_market_regime
                return fetch_market_regime()

            regime = await loop.run_in_executor(None, _regime)
            results = []

            for i, sym in enumerate(symbols):
                yield f"data: {_dumps({'type': 'progress', 'progress': f'{i}/{n} stocks scanned', 'current': sym})}\n\n"

                def _score(_sym=sym, _regime=regime):
                    from core.market_data import fetch_ticker_data
                    from core.conviction_engine import score_ticker
                    return score_ticker(fetch_ticker_data(_sym), _regime)

                try:
                    raw = await loop.run_in_executor(None, _score)
                except Exception as _e:
                    raw = {"ticker": sym, "hard_fail": True, "error": str(_e)}

                results.append(raw)
                yield f"data: {_dumps({'type': 'progress', 'progress': f'{i+1}/{n} stocks scanned'})}\n\n"

            # Sort: non-fails by conviction desc, then hard-fails
            non_fails = sorted([r for r in results if not r.get("hard_fail")],
                               key=lambda x: x.get("conviction_pct", 0), reverse=True)
            fails = [r for r in results if r.get("hard_fail")]
            sorted_results = non_fails + fails

            # Trade plans for top 3
            for r in sorted_results[:3]:
                if not r.get("hard_fail"):
                    r["plan"] = (
                        f"Entry: decisive close ${r.get('entry_low', 0)}-${r.get('entry_high', 0)} in final 30min. "
                        f"SL: ${r.get('sl', 0)} (ATR triple-guard). "
                        f"TP1: ${r.get('tp1', 0)} (exit 40%, move SL to BE). "
                        f"TP2: ${r.get('tp2', 0)} (exit 45%). R:R {r.get('rr', '?')}:1."
                    )

            spy_chg = regime.get("spy_change_pct", 0)
            direction = "up" if spy_chg > 0 else "down"
            header = (
                f"SPY {direction} {abs(spy_chg)}% at ${regime.get('spy_close', 0)}. "
                f"VIX at {regime['vix']} — {regime['regime']} regime. "
                f"Min R:R requirement: {regime['min_rr']}:1."
            )
            final = {
                "market_header": header,
                "market_regime": regime["regime"],
                "vix_estimate": regime["vix"],
                "results": sorted_results,
            }
            try:
                from core.trade_journal import log_scan
                log_scan(final)
            except Exception as je:
                print(f"[JOURNAL] Log failed: {je}")

            yield f"data: {_dumps({'type': 'complete', 'results': final})}\n\n"

        except Exception as e:
            traceback.print_exc()
            yield f"data: {_dumps({'type': 'error', 'error': str(e)})}\n\n"

    return _SR(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/prices")
async def get_prices(request: ScanRequest):
    try:
        import yfinance as yf
        prices = []
        for sym in request.symbols[:12]:
            try:
                tk = yf.Ticker(sym.upper().strip())
                hist = tk.history(period="5d")
                if len(hist) >= 2:
                    close = float(hist["Close"].iloc[-1]); prev = float(hist["Close"].iloc[-2])
                    chg = round((close - prev) / prev * 100, 2)
                    prices.append({"symbol": sym.upper(), "price": round(close, 2), "change": chg})
                else:
                    prices.append({"symbol": sym.upper(), "price": 0, "change": 0})
            except Exception:
                prices.append({"symbol": sym.upper(), "price": 0, "change": 0})
        return {"prices": prices}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/watchlists")
async def get_watchlists():
    from core.watchlists import list_watchlists, WATCHLISTS
    return {"watchlists": {k: {"label": v["label"], "count": len(v["tickers"])} for k, v in WATCHLISTS.items()}}


@app.get("/api/watchlists/{name}")
async def get_watchlist(name: str):
    from core.watchlists import get_watchlist as gw
    wl = gw(name)
    return {"name": name, "label": wl["label"], "tickers": wl["tickers"]}


@app.post("/api/backtest")
async def run_backtest_endpoint(request: BacktestRequest):
    try:
        symbols = [s.upper().strip() for s in request.symbols if s.strip()]
        if not symbols: raise HTTPException(status_code=400, detail="No symbols provided")
        if len(symbols) > 10: raise HTTPException(status_code=400, detail="Maximum 10 tickers per backtest")
        from core.backtester import run_backtest
        result = run_backtest(symbols, request.lookback_days, request.forward_days, request.sample_every)
        if "error" in result: raise HTTPException(status_code=500, detail=result["error"])
        return result
    except HTTPException: raise
    except Exception as e:
        traceback.print_exc(); raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/calibrate")
async def run_calibration_endpoint(request: BacktestRequest):
    try:
        symbols = [s.upper().strip() for s in request.symbols if s.strip()]
        if not symbols: raise HTTPException(status_code=400, detail="No symbols provided")
        from core.calibrator import run_calibration
        result = run_calibration(symbols, request.lookback_days, request.forward_days, request.sample_every)
        if "error" in result: raise HTTPException(status_code=500, detail=result["error"])
        return result
    except HTTPException: raise
    except Exception as e:
        traceback.print_exc(); raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/calibration")
async def get_calibration():
    from core.calibrator import load_calibration
    return load_calibration()


@app.post("/api/calibration/reset")
async def reset_calibration():
    from core.calibrator import save_calibration
    save_calibration({"mode": "none", "scale": 1.0, "offset": 0})
    return {"status": "reset", "mode": "none"}


# ══════════════════════════════════════════
# SIGNAL TRACKER ENDPOINTS v2.0
# ══════════════════════════════════════════

@app.get("/api/signals")
async def get_signals():
    from core.signal_tracker import get_all_signals
    return get_all_signals()


@app.post("/api/signals/check")
async def check_signals():
    from core.signal_tracker import check_signals as cs
    return cs()


@app.post("/api/signals/close/{signal_id}")
async def close_signal(signal_id: str):
    from core.signal_tracker import close_signal as cls
    result = cls(signal_id)
    if not result: raise HTTPException(status_code=404, detail="Signal not found")
    return result


@app.post("/api/signals/clear")
async def clear_signals():
    from core.signal_tracker import clear_all
    return clear_all()


@app.post("/api/signals/turbo/{symbol}")
async def turbo_signal(symbol: str, asset_type: str = "stock"):
    from core.signal_tracker import create_turbo_signal
    result = create_turbo_signal(symbol, asset_type)
    if "error" in result: raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/signals/override-sl/{signal_id}")
async def override_sl(signal_id: str, new_sl: float):
    from core.signal_tracker import override_signal_sl
    result = override_signal_sl(signal_id, new_sl)
    if not result: raise HTTPException(status_code=404, detail="Signal not found")
    return result


@app.post("/api/signals/ask-advisor/{signal_id}")
async def ask_advisor(signal_id: str, request: Request):
    """Ask Opus a free-text question about a specific signal."""
    body = await request.json()
    question = (body.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question field required")
    # Find signal in active or closed
    from core.signal_tracker import get_all_signals
    all_sigs = get_all_signals()
    signal = next(
        (s for s in all_sigs.get("active", []) + all_sigs.get("closed", [])
         if s.get("id") == signal_id),
        None
    )
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    from core.advisor import ask_opus
    result = ask_opus(signal, question)
    return {"signal_id": signal_id, "ticker": signal.get("ticker"), **result}


@app.get("/api/signals/report/{signal_id}")
async def get_signal_report(signal_id: str):
    from core.signal_tracker import get_signal_report as gsr
    report = gsr(signal_id)
    if not report: raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.get("/api/signals/reports")
async def get_all_reports():
    from core.signal_tracker import get_all_reports as gar
    return {"reports": gar()}


@app.get("/api/signals/regime-performance")
async def get_regime_performance():
    from core.signal_tracker import get_regime_performance as grp
    return grp()


@app.get("/api/scan/candidates")
async def scan_candidates(exclude: str = "", force: bool = False):
    """
    Return top 10 bench candidates from the shared portfolio scan cache.
    Cache is written by autopilot_fill(). If cache is stale/missing, runs a
    fresh sector-ranked scan of top 30 stocks (same universe as autopilot).
    Query param: exclude=CRWD,NET,MRVL  (comma-separated, case-insensitive)
    """
    import json as _json, time as _time
    from pathlib import Path as _Path
    try:
        excluded = {t.strip().upper() for t in exclude.split(",") if t.strip()} if exclude else set()

        SCAN_CACHE = _Path("calibration/last_portfolio_scan.json")
        CACHE_TTL  = 3600 * 4  # 4 hours — same as sector ranker

        raw        = []
        regime     = "Unknown"
        source     = "cache"

        # ── Try shared cache first ────────────────────────────────────────────
        if not force and SCAN_CACHE.exists():
            try:
                cached = _json.loads(SCAN_CACHE.read_text())
                if _time.time() - cached.get("ts", 0) < CACHE_TTL:
                    raw    = cached.get("results", [])
                    regime = cached.get("regime", "Unknown")
            except Exception:
                pass

        # ── Cache miss → fresh momentum-screened scan (top 30, all sectors) ───
        if not raw:
            source = "fresh_scan"
            from core.momentum_screener import get_momentum_scan_universe
            from core.conviction_engine import run_scan
            symbols = get_momentum_scan_universe(top_n=30)
            symbols = [s for s in symbols if s not in excluded]
            result  = run_scan(symbols)
            raw     = result.get("results", [])
            regime  = result.get("market_regime", "Unknown")
            # Save for next call
            try:
                SCAN_CACHE.parent.mkdir(parents=True, exist_ok=True)
                SCAN_CACHE.write_text(_json.dumps({
                    "ts": _time.time(), "built_at": __import__("datetime").datetime.utcnow().isoformat(),
                    "universe": "sector_ranked_top30", "regime": regime, "results": raw,
                }))
            except Exception:
                pass

        # ── Filter, sort, shape ───────────────────────────────────────────────
        filtered = sorted(
            [r for r in raw
             if not r.get("hard_fail")
             and r.get("conviction_pct", 0) > 0
             and r.get("ticker", "").upper() not in excluded],
            key=lambda x: x.get("conviction_pct", 0),
            reverse=True
        )

        candidates = [
            {
                "ticker":         r["ticker"],
                "conviction_pct": r.get("conviction_pct", 0),
                "rr":             r.get("rr", 0),
                "heat":           r.get("heat", ""),
                "trend":          r.get("trend", ""),
                "regime":         regime,
                "sector":         r.get("sector", ""),
                "sl":             r.get("sl", 0),
                "tp1":            r.get("tp1", 0),
                "tp2":            r.get("tp2", 0),
                "tp3":            r.get("tp3", 0),
                "entry_price":    r.get("entry_high", r.get("last_close", 0)),
            }
            for r in filtered[:10]
        ]

        return {
            "candidates":    candidates,
            "market_regime": regime,
            "scanned":       len(raw),
            "excluded":      list(excluded),
            "source":        source,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/autopilot")
async def run_autopilot(top_n: int = 10, watchlist: str = "full_scan"):
    """
    AUTO-PILOT: Scan → rank → launch turbo signals for top N.
    Universe: Alpha-Mega ranked stocks (if cache fresh) → fallback to watchlist.
    """
    try:
        from agents.swing_scanner import SwingScanner
        from core.signal_tracker import create_turbo_signal, get_all_signals
        from core.watchlists import get_watchlist
        import time as _tm

        # ── Step 1: Universe — Alpha-Mega first, watchlist fallback ──────────
        alpha_mega_syms = []
        if _ALPHA_MEGA_CACHE.get("data") and (_tm.time() - _ALPHA_MEGA_CACHE.get("ts", 0)) < _CACHE_TTL:
            alpha_mega_syms = [r["ticker"] for r in (_ALPHA_MEGA_CACHE["data"] or [])]
            print(f"[AUTOPILOT] Alpha-Mega universe: {alpha_mega_syms}")

        if alpha_mega_syms:
            symbols = alpha_mega_syms
            universe_source = "Alpha-Mega"
        else:
            wl = get_watchlist(watchlist)
            symbols = wl["tickers"]
            universe_source = watchlist
            print(f"[AUTOPILOT] Alpha-Mega cache empty, using {watchlist}")

        # ── Step 2: Scan ─────────────────────────────────────────────────────
        scanner = SwingScanner()
        scan_result = scanner.scan(symbols)
        results = scan_result.get("results", [])

        # ── Step 3: Filter and rank ───────────────────────────────────────────
        valid = [r for r in results if not r.get("hard_fail") and r.get("conviction_pct", 0) > 0]
        ranked = sorted(valid, key=lambda x: x.get("conviction_pct", 0), reverse=True)
        top = ranked[:top_n]

        # ── Step 4: Avoid duplicates ──────────────────────────────────────────
        existing = get_all_signals()
        active_tickers = {s["ticker"] for s in existing.get("active", [])}

        # ── Step 5: Launch turbo signals with full scan data ──────────────────
        launched = []; skipped = []
        for r in top:
            ticker = r["ticker"]
            if ticker in active_tickers:
                skipped.append({"ticker": ticker, "reason": "already active"}); continue
            sig = create_turbo_signal(ticker, scan_data=r)
            if "error" not in sig:
                launched.append({
                    "ticker": ticker, "conviction": r.get("conviction_pct", 0),
                    "heat": r.get("heat", ""), "entry": sig.get("entry_price", 0),
                    "sl": sig.get("sl", 0), "tp1": sig.get("tp1", 0),
                    "atr": sig.get("atr_at_entry", 0),
                    "target_method": sig.get("target_method", ""),
                    "regime": sig.get("regime", ""),
                })
                active_tickers.add(ticker)
            else:
                skipped.append({"ticker": ticker, "reason": sig["error"]})

        try:
            from core.telegram_alerts import alert_autopilot_launched
            alert_autopilot_launched(len(launched), "stocks", source=universe_source)
        except Exception:
            pass

        return {
            "status": "ok", "universe_source": universe_source,
            "scanned": len(symbols), "passed_filter": len(valid),
            "launched": launched, "skipped": skipped,
            "top_ranked": [{"ticker": r["ticker"], "conviction": r.get("conviction_pct", 0),
                            "heat": r.get("heat", ""), "tas": r.get("tas", "")} for r in top],
            "market_regime": scan_result.get("market_regime", ""),
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


CRYPTO_UNIVERSE = [
    "BTC", "ETH", "SOL", "XRP", "ADA", "AVAX", "DOGE", "DOT",
    "MATIC", "LINK", "NEAR", "UNI", "AAVE", "LTC", "ATOM",
]


@app.post("/api/autopilot/crypto")
async def run_crypto_autopilot(top_n: int = 10):
    try:
        from core.signal_tracker import create_turbo_signal, get_all_signals
        import yfinance as yf
        existing = get_all_signals()
        active_tickers = {s["ticker"] for s in existing.get("active", [])}
        crypto_data = []
        for sym in CRYPTO_UNIVERSE:
            if sym in active_tickers: continue
            try:
                tk = yf.Ticker(f"{sym}-USD"); fi = tk.fast_info
                price = fi.get("lastPrice") or fi.get("last_price", 0)
                if price and price > 0:
                    crypto_data.append({"ticker": sym, "price": float(price)})
            except Exception: pass
        top = crypto_data[:top_n]
        launched = []; skipped = []
        for c in top:
            sig = create_turbo_signal(c["ticker"], asset_type="crypto")
            if "error" not in sig:
                launched.append({"ticker": c["ticker"], "conviction": 0, "heat": "CRYPTO",
                                  "entry": sig.get("entry_price", 0), "sl": sig.get("sl", 0),
                                  "tp1": sig.get("tp1", 0), "atr": sig.get("atr_at_entry", 0),
                                  "target_method": sig.get("target_method", "")})
            else:
                skipped.append({"ticker": c["ticker"], "reason": sig["error"]})
        return {"status": "ok", "scanned": len(CRYPTO_UNIVERSE), "passed_filter": len(crypto_data),
                "launched": launched, "skipped": skipped, "market_regime": "Crypto 24/7"}
    except Exception as e:
        traceback.print_exc(); raise HTTPException(status_code=500, detail=str(e))


# ── Storage Management ──────────────────────────────────────
@app.get("/api/signals/storage-status")
async def storage_status():
    from core.signal_store import get_storage_status
    return get_storage_status()

@app.post("/api/signals/sync")
async def sync_signals():
    from core.signal_store import sync_local_to_supabase
    return sync_local_to_supabase()

@app.get("/api/signals/storage-debug")
async def storage_debug():
    import os
    url = os.environ.get("SUPABASE_URL", ""); key = os.environ.get("SUPABASE_ANON_KEY", "")
    result = {"url_set": bool(url), "key_set": bool(key), "url_prefix": url[:30] if url else ""}
    try:
        from supabase import create_client
        sb = create_client(url, key); sb.table("signals").select("id").limit(1).execute()
        result["connection"] = "OK"
    except Exception as e:
        result["connection"] = f"FAIL: {str(e)[:200]}"
    return result


# ── Telegram Test ────────────────────────────────────────────
@app.post("/api/alerts/test")
async def test_telegram_alert():
    try:
        from core.telegram_alerts import test_alert
        ok = test_alert()
        return {"status": "sent" if ok else "failed", "message": "Check your Telegram"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Chart Data ──────────────────────────────────────────────
@app.get("/api/chart/{symbol}")
async def get_chart_data(symbol: str, interval: str = "1d", period: str = "6M"):
    try:
        import yfinance as yf
        import numpy as np
        import pandas as pd
        ticker = yf.Ticker(symbol.upper())
        period_map = {"1M":"1mo","3M":"3mo","6M":"6mo","1Y":"1y","3Y":"2y","5Y":"5y"}
        yf_period = period_map.get(period, "6mo")
        if interval == "1h":
            yf_period = period_map.get(period, "1mo") if period in ["1M","3M"] else "1mo"
            hist = ticker.history(period=yf_period, interval="60m")
        elif interval == "4h":
            yf_period = period_map.get(period, "3mo") if period in ["1M","3M","6M"] else "3mo"
            h1 = ticker.history(period=yf_period, interval="60m")
            if not h1.empty:
                hist = h1.resample("4h").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
            else: hist = h1
        elif interval == "1w":
            hist = ticker.history(period=yf_period, interval="1wk")
        else:
            hist = ticker.history(period=yf_period, interval="1d")
        if hist.empty:
            return {"symbol":symbol.upper(),"interval":interval,"period":period,
                    "candles":[],"sr_levels":[],"channel":None,"signals":[],"mtf":{}}
        def fmt_ts(ts):
            try: return ts.strftime("%Y-%m-%d %H:%M") if interval in ["1h","4h"] else ts.strftime("%Y-%m-%d")
            except: return str(ts)[:16]
        candles = [{"t":fmt_ts(ts),"o":round(float(row["Open"]),2),"h":round(float(row["High"]),2),
                    "l":round(float(row["Low"]),2),"c":round(float(row["Close"]),2),"v":int(row["Volume"])}
                   for ts, row in hist.iterrows()]
        closes = hist["Close"].values; highs = hist["High"].values; lows = hist["Low"].values
        sr_levels = []
        for i in range(2, len(closes)-2):
            if highs[i]>highs[i-1] and highs[i]>highs[i-2] and highs[i]>highs[i+1] and highs[i]>highs[i+2]:
                sr_levels.append({"level":round(float(highs[i]),2),"type":"resistance"})
            if lows[i]<lows[i-1] and lows[i]<lows[i-2] and lows[i]<lows[i+1] and lows[i]<lows[i+2]:
                sr_levels.append({"level":round(float(lows[i]),2),"type":"support"})
        filtered_sr = []
        for lvl in sr_levels:
            if not any(abs(l["level"]-lvl["level"])/max(lvl["level"],1)<0.005 for l in filtered_sr):
                filtered_sr.append(lvl)
        x = np.arange(len(closes)); m, b = np.polyfit(x, closes, 1)
        std = float(np.std(closes-(m*x+b))); n = len(closes)-1
        channel = {
            "upper":[round(float(b+2*std),2),round(float(m*n+b+2*std),2)],
            "mid":  [round(float(b),2),      round(float(m*n+b),2)],
            "lower":[round(float(b-2*std),2),round(float(m*n+b-2*std),2)]
        }
        close_s=hist["Close"]; ema20=close_s.ewm(span=20,adjust=False).mean(); ema50=close_s.ewm(span=50,adjust=False).mean()
        signals=[]
        for i in range(1,len(close_s)):
            pd_=float(ema20.iloc[i-1])-float(ema50.iloc[i-1]); cd=float(ema20.iloc[i])-float(ema50.iloc[i])
            if pd_<=0 and cd>0: signals.append({"t":fmt_ts(hist.index[i]),"type":"BUY","price":round(float(close_s.iloc[i]),2)})
            elif pd_>=0 and cd<0: signals.append({"t":fmt_ts(hist.index[i]),"type":"SELL","price":round(float(close_s.iloc[i]),2)})
        def mtf_trend(iv,per):
            try:
                h=ticker.history(period=per,interval=iv)
                if h.empty or len(h)<5: return "NEUTRAL"
                if iv=="60m" and per=="4h_resample":
                    h=h.resample("4h").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
                c=h["Close"]; e=c.ewm(span=20,adjust=False).mean()
                return "BULL" if float(c.iloc[-1])>float(e.iloc[-1]) else "BEAR"
            except: return "NEUTRAL"
        mtf = {"tf_1h":mtf_trend("60m","5d"),"tf_4h":mtf_trend("60m","4h_resample"),
               "tf_1d":mtf_trend("1d","3mo"),"tf_1w":mtf_trend("1wk","1y")}
        return {"symbol":symbol.upper(),"interval":interval,"period":period,
                "candles":candles,"sr_levels":filtered_sr[:10],"channel":channel,"signals":signals,"mtf":mtf}
    except HTTPException: raise
    except Exception as e:
        traceback.print_exc(); raise HTTPException(status_code=500, detail=str(e))


# ── Universe endpoint ────────────────────────────────────────
@app.get("/api/universe")
async def universe_endpoint(force: bool = False):
    from core.universe_builder import build_universe
    return build_universe(force=force)

@app.get("/api/universe/sector/{sector_name}")
async def universe_sector(sector_name: str):
    from core.universe_builder import get_universe
    uni = get_universe()
    sector_map = {v.lower().replace(" ", "_"): v for v in uni["sectors"]}
    sector = sector_map.get(sector_name.lower(), sector_name)
    tickers = uni["sectors"].get(sector, [])
    if not tickers:
        raise HTTPException(status_code=404, detail=f"Sector '{sector_name}' not found")
    return {"sector": sector, "tickers": tickers, "count": len(tickers)}

@app.get("/api/sectors/ranking")
async def sector_ranking(force: bool = False):
    """Rank sectors by 5d+20d ETF momentum vs SPY. Cached 4h."""
    from core.sector_ranker import rank_sectors
    import asyncio
    loop = asyncio.get_event_loop()
    rankings = await loop.run_in_executor(None, lambda: rank_sectors(force=force))
    return {"rankings": rankings, "count": len(rankings)}

@app.get("/api/sectors/scan-universe")
async def sectors_scan_universe(slots: int = 40, top_sectors: int = 4):
    """Return scan-ready ticker list from top N leading sectors."""
    from core.sector_ranker import get_scan_universe
    import asyncio
    loop = asyncio.get_event_loop()
    tickers = await loop.run_in_executor(None, lambda: get_scan_universe(slots, top_sectors))
    return {"tickers": tickers, "count": len(tickers)}

@app.get("/api/sectors/momentum-screen")
async def momentum_screen(top_n: int = 30, force: bool = False):
    """
    Fast price-momentum pre-screen across all 377 >$10B stocks.
    Returns top_n ranked by: 5d return (50%) + 20d return (30%) + vol surge (20%)
    with sector bias applied. Cached 2h.
    """
    import asyncio
    from core.momentum_screener import screen_universe
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, lambda: screen_universe(top_n=top_n, force=force))
    return {
        "tickers": [r["ticker"] for r in results],
        "results": results,
        "count":   len(results),
        "top_n":   top_n,
    }

# ── Sector Heat (legacy — now backed by momentum ranker) ─────
@app.get("/api/sectors/heat")
async def sector_heat():
    try:
        from core.watchlists import SECTOR_WATCHLISTS
        from agents.swing_scanner import SwingScanner
        scanner = SwingScanner()
        etfs = [v["etf"] for v in SECTOR_WATCHLISTS.values()]
        results = scanner.scan(etfs)
        scored = []
        for key, meta in SECTOR_WATCHLISTS.items():
            etf = meta["etf"]
            match = next((r for r in results if r.get("ticker")==etf and not r.get("hard_fail")), None)
            score = match["conviction_pct"] if match else 0
            trend = match.get("trend","—") if match else "—"
            scored.append({"key":key,"label":meta["label"],"etf":etf,"score":score,"trend":trend,
                           "heat":"HOT" if score>=70 else "WARM" if score>=55 else "COLD"})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return {"sectors": scored}
    except Exception as e:
        traceback.print_exc(); raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sectors/watchlist/{sector_key}")
async def sector_watchlist(sector_key: str):
    """
    Return top 30 tickers for a sector, ranked by momentum score.
    Reads from momentum screener cache (2h TTL) — instant if warm,
    ~15s batch download if cold. Falls back to static universe order.
    """
    import asyncio, json as _json, time as _time
    from pathlib import Path as _Path
    from core.sector_ranker import SECTOR_KEY_MAP, SECTOR_ETFS
    from core.watchlists import SECTOR_WATCHLISTS

    # Map sector_key → GICS name
    reverse_map = {v: k for k, v in SECTOR_KEY_MAP.items()}
    gics_name   = reverse_map.get(sector_key)

    if not gics_name:
        # Fallback: legacy watchlist
        if sector_key in SECTOR_WATCHLISTS:
            s = SECTOR_WATCHLISTS[sector_key]
            return {"key": sector_key, "label": s["label"], "etf": s["etf"],
                    "tickers": s["tickers"][:30], "source": "legacy"}
        raise HTTPException(status_code=404, detail=f"Sector '{sector_key}' not found")

    # ── Try momentum screener cache first (fast path) ─────────────────────
    SCREEN_CACHE = _Path("calibration/momentum_screen_cache.json")
    CACHE_TTL    = 3600 * 2
    tickers      = []
    source       = "momentum_screen"

    if SCREEN_CACHE.exists():
        try:
            cached = _json.loads(SCREEN_CACHE.read_text())
            if _time.time() - cached.get("ts", 0) < CACHE_TTL:
                # Filter to this sector, already sorted by adjusted_score desc
                tickers = [
                    r["ticker"] for r in cached.get("results", [])
                    if r.get("sector") == gics_name
                ][:30]
        except Exception:
            pass

    # ── Cache miss → run screener for this sector ─────────────────────────
    if not tickers:
        try:
            from core.momentum_screener import screen_universe
            loop    = asyncio.get_event_loop()
            all_res = await loop.run_in_executor(None, lambda: screen_universe(top_n=377))
            tickers = [r["ticker"] for r in all_res if r.get("sector") == gics_name][:30]
        except Exception:
            source = "static_universe"

    # ── Final fallback: static universe order ─────────────────────────────
    if not tickers:
        from core.universe_builder import get_universe
        uni     = get_universe()
        tickers = uni["sectors"].get(gics_name, [])[:30]
        source  = "static_universe"

    etf = SECTOR_ETFS.get(gics_name, ("",))[0]
    return {
        "key":    sector_key,
        "label":  gics_name,
        "etf":    etf,
        "tickers": tickers,
        "count":  len(tickers),
        "source": source,
    }


# ── Alpha-Mega Dashboard ─────────────────────────────────────
import time as _time_mod
_ALPHA_MEGA_CACHE = {"ts": 0.0, "data": None}
_CACHE_TTL = 86400  # 24 hours

@app.get("/api/alpha-mega")
async def alpha_mega(lookback_days: int = 30):
    """Top 20 stocks scored by conviction+MTF+patterns, market cap >$10B, daily cached."""
    global _ALPHA_MEGA_CACHE
    try:
        from core.watchlists import SECTOR_WATCHLISTS
        from agents.swing_scanner import SwingScanner
        import yfinance as yf
        now = _time_mod.time()
        if now - _ALPHA_MEGA_CACHE["ts"] > _CACHE_TTL or not _ALPHA_MEGA_CACHE["data"]:
            candidates = {}
            for key, meta in SECTOR_WATCHLISTS.items():
                for t in meta["tickers"][:5]:
                    if t not in candidates: candidates[t] = key
            scanner = SwingScanner()
            raw_result = scanner.scan(list(candidates.keys()))
            raw = raw_result.get("results",[]) if isinstance(raw_result,dict) else (raw_result or [])
            filtered = [r for r in raw
                        if not r.get("hard_fail") and (r.get("mkt_cap_b") or 0)>=10 and r.get("conviction_pct",0)>0]
            for r in filtered:
                tf = r.get("tf_breakdown") or {}
                bull_tfs = sum(1 for k in ["tf_65m","tf_240m","tf_daily","tf_weekly"] if tf.get(k)=="BULL")
                mtf_score = (bull_tfs/4)*100; trend_sc = 80 if r.get("trend")=="BULL" else 20
                vol_sc = min(100,(r.get("vol_ratio") or 1)*40)
                r["alpha_score"] = round(r["conviction_pct"]*0.4+mtf_score*0.3+trend_sc*0.2+vol_sc*0.1,1)
                r["sector_key"]  = candidates.get(r["ticker"],"")
            filtered.sort(key=lambda x: x["alpha_score"], reverse=True)
            _ALPHA_MEGA_CACHE["ts"] = now; _ALPHA_MEGA_CACHE["data"] = filtered[:20]
        top20 = _ALPHA_MEGA_CACHE["data"] or []
        period_map = {30:"1mo",90:"3mo",180:"6mo",360:"1y"}
        yf_period = period_map.get(lookback_days,"1mo")
        results = []
        for r in top20:
            pnl_pct = 0.0
            try:
                hist = yf.Ticker(r["ticker"]).history(period=yf_period)
                if len(hist)>=2:
                    pnl_pct = round((hist["Close"].iloc[-1]-hist["Close"].iloc[0])/hist["Close"].iloc[0]*100,2)
            except: pass
            results.append({**r,"pnl_pct":pnl_pct})
        seen_sectors, portfolio = set(), []
        for r in results:
            sk = r.get("sector_key","")
            if sk not in seen_sectors and len(portfolio)<5:
                portfolio.append(r["ticker"]); seen_sectors.add(sk)
        return {"top20":results,"portfolio":portfolio,"lookback_days":lookback_days,
                "last_updated":int(_ALPHA_MEGA_CACHE["ts"]),"total_scanned":len(_ALPHA_MEGA_CACHE["data"] or [])}
    except Exception as e:
        traceback.print_exc(); raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# EARNINGS CALENDAR
# ═══════════════════════════════════════════════════════════════════
@app.get("/api/earnings/{symbol}")
async def get_earnings(symbol: str):
    try:
        import yfinance as yf
        from datetime import date
        tk = yf.Ticker(symbol.upper()); cal = tk.calendar
        result = {"symbol":symbol.upper(),"earnings_date":None,"days_until":None,"warning":False,"warning_msg":""}
        if cal is not None and not cal.empty:
            try:
                col = cal.columns[0]; dt = col
                if hasattr(dt,'date'): dt = dt.date()
                elif isinstance(dt,str): dt = date.fromisoformat(dt[:10])
                days = (dt-date.today()).days
                result["earnings_date"] = str(dt); result["days_until"] = days
                if 0<=days<=7:
                    result["warning"] = True
                    result["warning_msg"] = f"EARNINGS IN {days} DAY{'S' if days!=1 else ''} — high volatility risk"
            except Exception: pass
        return result
    except Exception as e:
        traceback.print_exc(); raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# PORTFOLIO RISK LAYER
# ═══════════════════════════════════════════════════════════════════
SECTOR_MAP = {
    "AAPL":"Tech","MSFT":"Tech","NVDA":"Tech","AMD":"Tech","GOOGL":"Tech","META":"Tech","AMZN":"Tech",
    "TSLA":"Consumer","NFLX":"Consumer","DIS":"Consumer","NKE":"Consumer","SBUX":"Consumer",
    "JPM":"Finance","GS":"Finance","BAC":"Finance","V":"Finance","MA":"Finance","BRK-B":"Finance",
    "JNJ":"Health","PFE":"Health","UNH":"Health","ABBV":"Health","LLY":"Health","MRK":"Health",
    "XOM":"Energy","CVX":"Energy","COP":"Energy","SLB":"Energy",
    "BA":"Industrials","CAT":"Industrials","HON":"Industrials","GE":"Industrials",
    "BTC":"Crypto","ETH":"Crypto","SOL":"Crypto","XRP":"Crypto","ADA":"Crypto",
}

@app.get("/api/portfolio/risk")
async def portfolio_risk():
    try:
        from core import signal_store as store
        active = store.load_active()
        if not active:
            return {"risk_level":"LOW","signals":0,"warnings":[],"sector_exposure":{},"worst_case_loss_pct":0}
        sector_exposure: dict = {}
        for s in active:
            sec = SECTOR_MAP.get(s["ticker"],"Other")
            sector_exposure[sec] = sector_exposure.get(sec,0)+1
        warnings = []
        for sec, cnt in sector_exposure.items():
            if cnt>=3: warnings.append(f"HIGH CONCENTRATION: {cnt} open signals in {sec}")
            elif cnt==2: warnings.append(f"MODERATE: 2 signals in {sec}")
        total_risk_pct = 0.0; signal_risks = []
        for s in active:
            entry = s.get("entry_price",0); sl = s.get("targets",{}).get("sl") or s.get("sl",0)
            if entry>0 and sl>0:
                risk_pct = round((sl-entry)/entry*100,2)
                signal_risks.append({"ticker":s["ticker"],"risk_pct":risk_pct}); total_risk_pct+=risk_pct
            else: signal_risks.append({"ticker":s["ticker"],"risk_pct":0})
        worst_case = round(total_risk_pct/len(active),2) if active else 0
        max_conc = max(sector_exposure.values()) if sector_exposure else 0
        if max_conc>=4 or len(active)>=8: risk_level="HIGH"
        elif max_conc>=3 or len(active)>=5: risk_level="MEDIUM"
        else: risk_level="LOW"
        if worst_case<-3: warnings.append(f"WORST CASE: all SLs hit = {worst_case:.1f}% portfolio loss")
        return {"risk_level":risk_level,"signals":len(active),"warnings":warnings,
                "sector_exposure":sector_exposure,"signal_risks":signal_risks,"worst_case_loss_pct":worst_case}
    except Exception as e:
        traceback.print_exc(); raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# LEARNING LOOP / ANALYTICS
# ═══════════════════════════════════════════════════════════════════
@app.get("/api/analytics/performance")
async def analytics_performance():
    try:
        from core import signal_store as store
        closed = store.load_closed()
        if not closed:
            return {"total":0,"message":"No closed signals yet. Run Auto-Pilot to generate signals."}
        wins=[s for s in closed if s.get("pnl_pct",0)>0]; losses=[s for s in closed if s.get("pnl_pct",0)<=0]
        total=len(closed); win_rate=round(len(wins)/total*100,1) if total else 0
        avg_win  = round(sum(s["pnl_pct"] for s in wins)/len(wins),2) if wins else 0
        avg_loss = round(sum(s["pnl_pct"] for s in losses)/len(losses),2) if losses else 0
        gp=sum(s["pnl_pct"] for s in wins) if wins else 0
        gl=abs(sum(s["pnl_pct"] for s in losses)) if losses else 1
        profit_factor=round(gp/gl,2) if gl else 0
        buckets={"50-59":[],"60-69":[],"70-79":[],"80-89":[],"90+":[]}
        for s in closed:
            c=s.get("conviction",s.get("scan_data",{}).get("conviction_pct",0)) or 0
            b="50-59" if c<60 else "60-69" if c<70 else "70-79" if c<80 else "80-89" if c<90 else "90+"
            buckets[b].append(s)
        conviction_breakdown={}
        for b,sigs in buckets.items():
            if sigs:
                w=sum(1 for s in sigs if s.get("pnl_pct",0)>0)
                conviction_breakdown[b]={"trades":len(sigs),"win_rate":round(w/len(sigs)*100,1)}
        regime_breakdown={}
        for s in closed:
            reg=s.get("market_context",{}).get("regime","Unknown")
            if reg not in regime_breakdown: regime_breakdown[reg]={"trades":0,"wins":0}
            regime_breakdown[reg]["trades"]+=1
            if s.get("pnl_pct",0)>0: regime_breakdown[reg]["wins"]+=1
        for reg in regime_breakdown:
            t=regime_breakdown[reg]["trades"]; w=regime_breakdown[reg]["wins"]
            regime_breakdown[reg]["win_rate"]=round(w/t*100,1) if t else 0
        tp1_hits=sum(1 for s in closed if s.get("tp1_hit"))
        tp2_hits=sum(1 for s in closed if s.get("tp2_hit"))
        stopped=sum(1 for s in closed if "STOPPED" in s.get("status",""))
        avg_mae=round(sum(s.get("mae_pct",0) for s in closed)/total,2) if total else 0
        avg_mfe=round(sum(s.get("mfe_pct",0) for s in closed)/total,2) if total else 0
        return {"total":total,"wins":len(wins),"losses":len(losses),"win_rate":win_rate,
                "avg_win_pct":avg_win,"avg_loss_pct":avg_loss,"profit_factor":profit_factor,
                "tp1_hit_rate":round(tp1_hits/total*100,1) if total else 0,
                "tp2_hit_rate":round(tp2_hits/total*100,1) if total else 0,
                "stopped_out_rate":round(stopped/total*100,1) if total else 0,
                "avg_mae_pct":avg_mae,"avg_mfe_pct":avg_mfe,
                "conviction_breakdown":conviction_breakdown,"regime_breakdown":regime_breakdown}
    except Exception as e:
        traceback.print_exc(); raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/analytics/portfolio")
async def analytics_portfolio():
    """
    Portfolio-level analytics: Sharpe, drawdown, sector/session/monthly breakdown.
    Complements /api/analytics/performance with richer metrics.
    """
    try:
        import math
        from core import signal_store as store
        closed = store.load_closed()
        if not closed:
            return {"total_signals": 0, "message": "No closed signals yet."}

        total = len(closed)
        wins   = [s for s in closed if s.get("pnl_pct", 0) > 0]
        losses = [s for s in closed if s.get("pnl_pct", 0) <= 0]
        pnls   = [s.get("pnl_pct", 0) for s in closed]

        win_rate    = round(len(wins) / total * 100, 1) if total else 0
        avg_pnl_pct = round(sum(pnls) / total, 2) if total else 0
        gp = sum(s["pnl_pct"] for s in wins)  if wins   else 0
        gl = abs(sum(s["pnl_pct"] for s in losses)) if losses else 0.01
        profit_factor = round(gp / gl, 2)

        # Avg hold days
        hold_days = []
        for s in closed:
            try:
                import datetime as _dt
                e = _dt.datetime.fromisoformat(s["entry_time"])
                c = _dt.datetime.fromisoformat(s["closed_at"])
                hold_days.append((c - e).total_seconds() / 86400)
            except Exception:
                pass
        avg_hold_days = round(sum(hold_days) / len(hold_days), 1) if hold_days else 0

        # Sharpe ratio (daily P&L series, risk-free = 0)
        import numpy as np
        pnl_arr = np.array(pnls, dtype=float)
        sharpe = round(float(pnl_arr.mean() / pnl_arr.std()) * math.sqrt(252), 2) \
                 if len(pnl_arr) > 1 and pnl_arr.std() > 0 else 0.0

        # Max drawdown (cumulative P&L equity curve)
        cumulative = np.cumsum(pnl_arr)
        peak = np.maximum.accumulate(cumulative)
        drawdown = cumulative - peak
        max_drawdown_pct = round(float(drawdown.min()), 2) if len(drawdown) else 0.0

        # Best / Worst trade
        best  = max(closed, key=lambda s: s.get("pnl_pct", 0))
        worst = min(closed, key=lambda s: s.get("pnl_pct", 0))
        best_trade  = {"ticker": best["ticker"],  "pnl_pct": best.get("pnl_pct", 0),  "date": (best.get("closed_at","")[:10])}
        worst_trade = {"ticker": worst["ticker"], "pnl_pct": worst.get("pnl_pct", 0), "date": (worst.get("closed_at","")[:10])}

        # By regime
        by_regime = {}
        for s in closed:
            reg = (s.get("entry_market_context") or {}).get("regime") or s.get("regime", "Unknown")
            if reg not in by_regime:
                by_regime[reg] = {"wins": 0, "losses": 0, "pnls": []}
            by_regime[reg]["pnls"].append(s.get("pnl_pct", 0))
            if s.get("pnl_pct", 0) > 0:
                by_regime[reg]["wins"] += 1
            else:
                by_regime[reg]["losses"] += 1
        for reg in by_regime:
            d = by_regime[reg]
            d["avg_pnl"] = round(sum(d["pnls"]) / len(d["pnls"]), 2) if d["pnls"] else 0
            del d["pnls"]

        # By sector
        by_sector = {}
        for s in closed:
            sec = SECTOR_MAP.get(s.get("ticker", "").upper(), "Other")
            if sec not in by_sector:
                by_sector[sec] = {"wins": 0, "losses": 0, "pnls": []}
            by_sector[sec]["pnls"].append(s.get("pnl_pct", 0))
            if s.get("pnl_pct", 0) > 0:
                by_sector[sec]["wins"] += 1
            else:
                by_sector[sec]["losses"] += 1
        for sec in by_sector:
            d = by_sector[sec]
            d["avg_pnl"] = round(sum(d["pnls"]) / len(d["pnls"]), 2) if d["pnls"] else 0
            del d["pnls"]

        # By session
        by_session = {}
        for s in closed:
            sess = s.get("entry_session", "unknown")
            if sess not in by_session:
                by_session[sess] = {"wins": 0, "losses": 0}
            if s.get("pnl_pct", 0) > 0:
                by_session[sess]["wins"] += 1
            else:
                by_session[sess]["losses"] += 1

        # Monthly P&L
        monthly = {}
        for s in closed:
            month = (s.get("closed_at", "") or "")[:7]
            if not month:
                continue
            if month not in monthly:
                monthly[month] = {"pnl": 0.0, "trades": 0}
            monthly[month]["pnl"]    += s.get("pnl_pct", 0)
            monthly[month]["trades"] += 1
        monthly_pnl = sorted(
            [{"month": m, "pnl": round(d["pnl"], 2), "trades": d["trades"]}
             for m, d in monthly.items()],
            key=lambda x: x["month"]
        )

        return {
            "total_signals":    total,
            "win_rate":         win_rate,
            "avg_pnl_pct":      avg_pnl_pct,
            "avg_hold_days":    avg_hold_days,
            "profit_factor":    profit_factor,
            "sharpe_ratio":     sharpe,
            "max_drawdown_pct": max_drawdown_pct,
            "best_trade":       best_trade,
            "worst_trade":      worst_trade,
            "by_regime":        by_regime,
            "by_sector":        by_sector,
            "by_session":       by_session,
            "monthly_pnl":      monthly_pnl,
        }
    except Exception as e:
        traceback.print_exc(); raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# REAL-TIME DATA — Alpaca (optional, falls back to yfinance)
# ═══════════════════════════════════════════════════════════════════
@app.get("/api/price/live/{symbol}")
async def get_live_price(symbol: str):
    import os, yfinance as yf
    sym=symbol.upper(); alpaca_key=os.environ.get("ALPACA_API_KEY",""); alpaca_secret=os.environ.get("ALPACA_SECRET_KEY","")
    if alpaca_key and alpaca_secret:
        try:
            import urllib.request, json as _json
            url=f"https://data.alpaca.markets/v2/stocks/{sym}/trades/latest"
            req=urllib.request.Request(url,headers={"APCA-API-KEY-ID":alpaca_key,"APCA-API-SECRET-KEY":alpaca_secret,"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req,timeout=5) as r:
                data=_json.loads(r.read().decode()); price=float(data["trade"]["p"])
                return {"symbol":sym,"price":price,"source":"alpaca","realtime":True,"delay_min":0}
        except Exception: pass
    try:
        tk=yf.Ticker(sym); hist=tk.history(period="1d",interval="1m")
        if not hist.empty:
            return {"symbol":sym,"price":round(float(hist["Close"].iloc[-1]),4),"source":"yfinance","realtime":False,"delay_min":15}
    except Exception: pass
    raise HTTPException(status_code=404, detail=f"Could not fetch price for {sym}")


@app.get("/api/data/source")
async def get_data_source():
    import os
    alpaca_key=os.environ.get("ALPACA_API_KEY","")
    return {"source":"alpaca" if alpaca_key else "yfinance","realtime":bool(alpaca_key),
            "delay_min":0 if alpaca_key else 15,"label":"LIVE" if alpaca_key else "DELAYED ~15min"}


# ═══════════════════════════════════════════════════════════════════
# SECTOR FLIP ALERTS
# ═══════════════════════════════════════════════════════════════════
_SECTOR_TREND_CACHE: dict = {}

@app.post("/api/alerts/sector-check")
async def check_sector_flips():
    import time, yfinance as yf
    SECTOR_ETFS = {
        "XLK":"Info Tech","XLF":"Financials","XLV":"Health Care","XLI":"Industrials",
        "XLY":"Cons. Disc.","XLP":"Cons. Staples","XLE":"Energy","XLC":"Comm. Svcs",
        "XLU":"Utilities","XLB":"Materials","XLRE":"Real Estate",
    }
    flips=[]
    for etf,name in SECTOR_ETFS.items():
        try:
            hist=yf.Ticker(etf).history(period="5d",interval="1d")
            if hist.empty or len(hist)<2: continue
            close=hist["Close"]; ema20=float(close.ewm(span=20,adjust=False).mean().iloc[-1])
            current=float(close.iloc[-1]); trend="BULL" if current>ema20 else "BEAR"
            prev=_SECTOR_TREND_CACHE.get(etf,{}).get("trend")
            _SECTOR_TREND_CACHE[etf]={"trend":trend,"ts":time.time()}
            if prev and prev!=trend:
                flips.append({"etf":etf,"sector":name,"from":prev,"to":trend})
                try:
                    from core.telegram_alerts import _send
                    emoji="🟢" if trend=="BULL" else "🔴"
                    _send(f"{emoji} <b>SECTOR FLIP — {name}</b>\n{etf}: {prev} → <b>{trend}</b>\n🕐 {__import__('datetime').datetime.utcnow().strftime('%H:%M UTC')}")
                except Exception: pass
        except Exception: pass
    return {"checked":len(SECTOR_ETFS),"flips":flips,"flips_count":len(flips)}


# ══════════════════════════════════════════════════════════════
# PORTFOLIO TAB — Paper Trading Engine
# ══════════════════════════════════════════════════════════════

@app.get("/api/portfolio")
async def get_portfolio_endpoint():
    from core.portfolio_manager import get_portfolio
    return get_portfolio()

@app.post("/api/portfolio/check")
async def check_portfolio_endpoint():
    from core.portfolio_manager import check_portfolio
    return check_portfolio()

@app.post("/api/portfolio/open")
async def open_position_endpoint(body: dict):
    from core.portfolio_manager import open_position
    ticker=body.get("ticker","").upper(); entry=float(body.get("entry_price",0))
    sl=float(body.get("sl",0)); tp1=float(body.get("tp1",0))
    tp2=float(body.get("tp2",0)); tp3=float(body.get("tp3",0))
    conviction=int(body.get("conviction",0)); asset_type=body.get("asset_type","stock")
    signal_id=body.get("signal_id","")
    pillar_scores=body.get("pillar_scores") or {}
    tas=body.get("tas","")
    entry_market_context=body.get("entry_market_context") or {}
    if not ticker or not entry or not sl or not tp1:
        raise HTTPException(status_code=400, detail="ticker, entry_price, sl, tp1 required")
    return open_position(ticker,entry,sl,tp1,tp2,tp3,conviction,asset_type,signal_id,
                         pillar_scores=pillar_scores,tas=tas,entry_market_context=entry_market_context)

@app.post("/api/portfolio/close/{position_id}")
async def close_position_endpoint(position_id: str, body: dict = {}):
    from core.portfolio_manager import close_position
    return close_position(position_id, (body or {}).get("reason","MANUAL"))

@app.post("/api/portfolio/autopilot")
async def portfolio_autopilot_endpoint(body: dict = {}):
    """
    Portfolio autopilot — uses Alpha-Mega ranked stocks as scan universe if cache is fresh.
    Falls back to watchlist if cache is empty.
    """
    from core.portfolio_manager import autopilot_fill
    import time as _tm
    watchlist = (body or {}).get("watchlist","full_scan")
    # ── Use Alpha-Mega ranked symbols if cache is fresh ──
    alpha_mega_syms = None
    if _ALPHA_MEGA_CACHE.get("data") and (_tm.time() - _ALPHA_MEGA_CACHE.get("ts",0)) < _CACHE_TTL:
        alpha_mega_syms = [r["ticker"] for r in (_ALPHA_MEGA_CACHE["data"] or [])]
        print(f"[AUTOPILOT-PORTFOLIO] Injecting Alpha-Mega universe ({len(alpha_mega_syms)} stocks)")
    return autopilot_fill(watchlist, symbols_override=alpha_mega_syms)

@app.post("/api/portfolio/reset")
async def reset_portfolio_endpoint():
    from core.portfolio_store import clear_all_positions
    clear_all_positions()
    return {"reset":True,"message":"Portfolio reset to $25,000"}

@app.get("/api/portfolio/status")
async def portfolio_storage_status_endpoint():
    from core.portfolio_store import supabase_ready
    return {"supabase":supabase_ready(),"storage":"supabase" if supabase_ready() else "json_fallback"}


# ══════════════════════════════════════════════════════════════
# PRINTING PROFITS — Dual Long/Short Trading Engine
# ══════════════════════════════════════════════════════════════

@app.post("/api/printing/scan")
async def printing_scan_endpoint(body: dict = {}):
    from core.printing_scanner import run_dual_scan
    watchlist=(body or {}).get("watchlist","full_scan"); symbols=(body or {}).get("symbols",None)
    return run_dual_scan(symbols=symbols,watchlist_name=watchlist)

@app.get("/api/printing/futures")
async def printing_futures_endpoint():
    from core.futures_data import fetch_all_futures
    return fetch_all_futures()

@app.get("/api/printing/regime")
async def printing_regime_endpoint():
    from core.market_data import fetch_market_regime
    from core.regime_engine import get_strategy_mode
    regime=fetch_market_regime()
    return {"regime":regime,"mode":get_strategy_mode(regime)}

@app.get("/api/printing/portfolio")
async def printing_portfolio_endpoint():
    from core.printing_portfolio import get_portfolio
    return get_portfolio()

@app.post("/api/printing/portfolio/check")
async def printing_check_endpoint():
    from core.printing_portfolio import check_portfolio
    return check_portfolio()

@app.post("/api/printing/portfolio/open")
async def printing_open_endpoint(body: dict):
    from core.printing_portfolio import open_position
    ticker=body.get("ticker","").upper(); direction=body.get("direction","long")
    entry=float(body.get("entry_price",0)); sl=float(body.get("sl",0))
    tp1=float(body.get("tp1",0)); tp2=float(body.get("tp2",0)); tp3=float(body.get("tp3",0))
    conv=int(body.get("conviction",65))
    if not ticker or not entry or not sl or not tp1:
        raise HTTPException(status_code=400,detail="ticker, entry_price, sl, tp1 required")
    return open_position(ticker,direction,entry,sl,tp1,tp2,tp3,conv)

@app.post("/api/printing/portfolio/close/{position_id}")
async def printing_close_endpoint(position_id: str, body: dict = {}):
    from core.printing_portfolio import close_position
    return close_position(position_id,(body or {}).get("reason","MANUAL"))

@app.post("/api/printing/portfolio/autopilot")
async def printing_autopilot_endpoint(body: dict = {}):
    from core.printing_portfolio import autopilot_dual
    return autopilot_dual((body or {}).get("watchlist","full_scan"))

@app.post("/api/printing/portfolio/reset")
async def printing_reset_endpoint():
    from core.printing_store import clear_all
    clear_all()
    return {"reset":True,"message":"Printing Profits portfolio reset to $25,000"}

@app.get("/api/printing/status")
async def printing_status_endpoint():
    from core.printing_store import supabase_ready
    return {"supabase":supabase_ready(),"storage":"supabase" if supabase_ready() else "json_fallback"}


# ══════════════════════════════════════════════════════════════
# AGENT / SYSTEM MANAGEMENT ENDPOINTS
# ══════════════════════════════════════════════════════════════

@app.post("/api/agent/learn")
async def trigger_learning():
    from core.learning_loop import run_once
    return run_once()

@app.post("/api/agent/ping")
async def manual_ping():
    from core.telegram_alerts import _send
    _send("Manual ping from dashboard — system online")
    return {"sent":True}

@app.get("/api/agent/status")
async def agent_status():
    import threading
    threads={t.name:t.is_alive() for t in threading.enumerate()}
    return {"keepalive_running":threads.get("keepalive",False),
            "agent_running":threads.get("telegram_agent",False),
            "learning_running":threads.get("learning_loop",False),
            "active_threads":list(threads.keys())}


# ── Dreaming Agent ────────────────────────────────────────────────────────────
@app.get("/api/dreams/latest")
async def get_dream_log(limit: int = 10):
    from core.dreaming_agent import load_dream_log
    return {"dreams": load_dream_log(limit=limit)}

@app.post("/api/dreams/run")
async def trigger_dream_cycle(request: Request):
    body  = await request.json() if request.headers.get("content-type","").startswith("application/json") else {}
    force = body.get("force", False)
    from core.dreaming_agent import run_dream_cycle
    return run_dream_cycle(force=force)


# ── Outcomes Grader ───────────────────────────────────────────────────────────
@app.get("/api/outcomes/summary")
async def get_outcomes_summary():
    from core.outcomes_grader import load_outcomes_summary
    return load_outcomes_summary()


# ── Agent Council ─────────────────────────────────────────────────────────────
@app.post("/api/signals/council/{signal_id}")
async def run_signal_council(signal_id: str, request: Request):
    from core import signal_store as store
    active = store.load_active()
    signal = next((s for s in active if s.get("id") == signal_id), None)
    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")
    from core.agent_council import run_council
    from core.signal_tracker import _fetch_market_context
    try:
        ctx = _fetch_market_context()
    except Exception:
        ctx = {}
    result = run_council(signal, ctx)
    for s in active:
        if s.get("id") == signal_id:
            s["council_verdict"]       = result.get("verdict")
            s["council_reasoning"]     = result.get("reasoning")
            s["council_key_factor"]    = result.get("key_factor")
            s["council_size_guidance"] = result.get("size_guidance")
            s["council_bull_case"]     = result.get("bull_case")
            s["council_bear_case"]     = result.get("bear_case")
            s["council_bull_reasons"]  = result.get("bull_reasons", [])
            s["council_bear_risks"]    = result.get("bear_risks", [])
            s["council_bull_conf"]     = result.get("bull_confidence")
            s["council_bear_conf"]     = result.get("bear_confidence")
            break
    store.save_active(active)
    return result


# ═══════════════════════════════════════════════════════════════════
# SIGNAL REPLAY — re-simulate a closed signal with current system settings
# ═══════════════════════════════════════════════════════════════════

@app.post("/api/signals/replay/{signal_id}")
async def replay_signal(signal_id: str):
    """
    Re-simulate a closed signal through historical OHLC data using the
    current TSL + Dynamic TP Phase 2 logic. Read-only — never touches live data.
    """
    try:
        import math, datetime as _dt
        import numpy as np
        import yfinance as yf
        from core import signal_store as store

        # 1. Load the closed signal
        closed = store.load_closed()
        signal = next((s for s in closed if s.get("id") == signal_id), None)
        if not signal:
            raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found in closed signals")

        ticker     = signal.get("ticker", "")
        asset_type = signal.get("asset_type", "stock")
        entry_price = float(signal.get("entry_price", 0))
        if entry_price <= 0:
            raise HTTPException(status_code=400, detail="Signal has no valid entry_price")

        entry_time  = signal.get("entry_time", "")[:10]
        closed_at   = signal.get("closed_at", "")[:10]
        atr_at_entry = float(signal.get("atr_at_entry", 0))
        orig_sl      = float(signal.get("sl", 0)) or float(signal.get("original_sl", 0))
        tp1_orig     = float(signal.get("tp1", 0))
        tp2_orig     = float(signal.get("tp2", 0))
        tp3_orig     = float(signal.get("tp3", 0))

        if atr_at_entry <= 0:
            # Estimate ATR from the price (1% proxy)
            atr_at_entry = round(entry_price * 0.01, 4)

        # 2. Fetch historical OHLC: entry date + 30-day buffer beyond closed_at
        sym = ticker
        if asset_type == "crypto" and not sym.endswith("-USD"):
            sym += "-USD"
        try:
            close_dt  = _dt.datetime.fromisoformat(closed_at)
        except Exception:
            close_dt  = _dt.datetime.utcnow()
        end_fetch = (close_dt + _dt.timedelta(days=35)).strftime("%Y-%m-%d")
        df = yf.download(sym, start=entry_time, end=end_fetch, progress=False, auto_adjust=True)
        if df is None or df.empty:
            raise HTTPException(status_code=502, detail=f"No historical data for {sym}")

        closes = df["Close"].squeeze()
        dates  = [str(d)[:10] for d in df.index]

        # 3. Replay simulation
        sl   = orig_sl if orig_sl > 0 else round(entry_price - atr_at_entry * 1.5, 4)
        tp1  = tp1_orig if tp1_orig > 0 else round(entry_price + atr_at_entry * 0.75, 4)
        tp2  = tp2_orig if tp2_orig > 0 else round(entry_price + atr_at_entry * 1.5,  4)
        tp3  = tp3_orig if tp3_orig > 0 else round(entry_price + atr_at_entry * 2.5,  4)

        highest  = entry_price
        tp1_hit  = False
        tp2_hit  = False
        exit_reason = "TIMEOUT"
        exit_pnl    = 0.0
        exit_day    = 0
        price_series = []
        events       = []

        for day_idx, (date, close) in enumerate(zip(dates, closes)):
            price = float(close)
            if day_idx >= 30:
                exit_reason = "TIMEOUT"
                exit_pnl    = round((price - entry_price) / entry_price * 100, 2)
                exit_day    = day_idx
                events.append({"date": date, "type": "TIMEOUT", "detail": f"30-day limit · exit ${price:.2f}"})
                price_series.append({"date": date, "close": round(price, 4), "sl": round(sl, 4), "tp1": round(tp1, 4)})
                break

            # Update high-water mark
            if price > highest:
                highest = price

            # ── TSL (1.5×ATR, floored at entry) ──────────────────────────
            tsl_level = round(highest - atr_at_entry * 1.5, 4)
            tsl_level = max(tsl_level, entry_price)
            if tsl_level > sl:
                old_sl = sl
                sl = tsl_level
                events.append({"date": date, "type": "TSL_MOVE", "detail": f"TSL ${old_sl:.2f} → ${sl:.2f} (1.5×ATR)"})

            # ── Dynamic TP Phase 2 — RUNNING state only ───────────────────
            pnl_now = (price - entry_price) / entry_price * 100
            if pnl_now > 0:  # only push in profit
                new_tp1 = round(price + atr_at_entry * 1.0, 4)
                new_tp2 = round(price + atr_at_entry * 2.0, 4)
                if new_tp1 > tp1 and not tp1_hit:
                    tp1 = new_tp1
                    events.append({"date": date, "type": "DTP", "detail": f"TP1 pushed → ${tp1:.2f}"})
                if new_tp2 > tp2 and not tp2_hit:
                    tp2 = new_tp2

            # ── SL hit ────────────────────────────────────────────────────
            if price <= sl:
                exit_reason = "STOPPED_OUT"
                exit_pnl    = round((sl - entry_price) / entry_price * 100, 2)
                exit_day    = day_idx
                events.append({"date": date, "type": "SL_HIT", "detail": f"SL hit @ ${sl:.2f} · PnL {exit_pnl:+.2f}%"})
                price_series.append({"date": date, "close": round(price, 4), "sl": round(sl, 4), "tp1": round(tp1, 4)})
                break

            # ── TP hits ───────────────────────────────────────────────────
            if price >= tp3:
                exit_reason = "TP3_HIT"
                exit_pnl    = round((tp3 - entry_price) / entry_price * 100, 2)
                exit_day    = day_idx
                events.append({"date": date, "type": "TP3_HIT", "detail": f"TP3 hit @ ${tp3:.2f} · PnL {exit_pnl:+.2f}%"})
                price_series.append({"date": date, "close": round(price, 4), "sl": round(sl, 4), "tp1": round(tp1, 4)})
                break
            if price >= tp2 and not tp2_hit:
                tp2_hit = True
                events.append({"date": date, "type": "TP2_HIT", "detail": f"TP2 hit @ ${tp2:.2f}"})
            if price >= tp1 and not tp1_hit:
                tp1_hit = True
                events.append({"date": date, "type": "TP1_HIT", "detail": f"TP1 hit @ ${tp1:.2f}"})

            price_series.append({"date": date, "close": round(price, 4), "sl": round(sl, 4), "tp1": round(tp1, 4)})
        else:
            # Loop exhausted without break
            if price_series:
                last_price = price_series[-1]["close"]
                exit_pnl   = round((last_price - entry_price) / entry_price * 100, 2)
                exit_day   = len(price_series)
                exit_reason = "TIMEOUT"

        # 4. Original result
        orig_pnl   = float(signal.get("pnl_pct", 0))
        orig_reason = signal.get("status", signal.get("close_reason", "UNKNOWN"))
        orig_bars  = int(signal.get("bars_held", 0))

        return {
            "signal_id": signal_id,
            "ticker":    ticker,
            "original": {
                "exit_reason": orig_reason,
                "pnl_pct":     orig_pnl,
                "hold_days":   orig_bars,
            },
            "replay": {
                "exit_reason": exit_reason,
                "pnl_pct":     exit_pnl,
                "hold_days":   exit_day,
            },
            "improvement_pct": round(exit_pnl - orig_pnl, 2),
            "price_series":    price_series[:60],   # cap at 60 points for chart
            "events":          events,
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Dream Log endpoints ──────────────────────────────────────────────────────

@app.post("/api/dreams/run")
async def run_dream_now(request: Request):
    """Trigger a dream cycle immediately (force=True bypasses schedule check)."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    force = body.get("force", True)
    from core.dreaming_agent import run_dream_cycle
    result = run_dream_cycle(force=force)
    return result

@app.get("/api/dreams/latest")
async def get_dream_log(limit: int = 10):
    """Return the most recent dream log entries."""
    from core.dreaming_agent import load_dream_log
    dreams = load_dream_log(limit=limit)
    return {"dreams": dreams, "count": len(dreams)}


# ── Order Executor endpoints ─────────────────────────────────────────────────

@app.get("/api/executor/status")
async def executor_status():
    """Check broker connection and current execution mode."""
    from core.order_executor import check_connection, EXECUTOR_MODE, IBKR_HOST, IBKR_PORT
    conn = check_connection()
    conn["executor_mode"] = EXECUTOR_MODE
    conn["ibkr_host"]     = IBKR_HOST
    conn["ibkr_port"]     = IBKR_PORT
    conn["env"]           = "PAPER" if IBKR_PORT == 7497 else "LIVE"
    return conn

@app.post("/api/executor/execute/{signal_id}")
async def execute_live_signal(signal_id: str):
    """
    Execute a specific signal as a live/paper broker order.
    Reads the signal from store, routes to order_executor.
    """
    from core.signal_tracker import get_signal_by_id
    from core.order_executor import execute_signal
    signal = get_signal_by_id(signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")
    result = execute_signal(signal)
    return result

@app.post("/api/executor/test")
async def executor_test(request: Request):
    """
    Test execution with a custom payload — no real order placed in paper mode.
    Body: { ticker, entry_price, sl, tp1, tp2, tp3, shares }
    """
    from core.order_executor import execute_signal
    body = await request.json()
    result = execute_signal(body)
    return result


# ── Learning Loop endpoints ──────────────────────────────────────────────────

@app.get("/api/learning/summary")
async def learning_summary():
    """Current calibration params + outcomes summary."""
    from core.learning_loop import _load_calibration, _load_closed
    from core.outcomes_grader import load_outcomes_summary
    params   = _load_calibration()
    outcomes = load_outcomes_summary()
    closed   = _load_closed()
    return {
        "calibration":  params,
        "outcomes":     outcomes,
        "total_closed": len(closed),
    }

@app.post("/api/learning/run-fast")
async def run_fast_learning():
    """Trigger a fast learning cycle manually."""
    from core.learning_loop import run_fast
    return run_fast()

@app.post("/api/learning/run-deep")
async def run_deep_learning():
    """Trigger a full deep learning cycle (all 5 dimensions)."""
    from core.learning_loop import run_deep
    return run_deep()


# ── System Health endpoints ──────────────────────────────────────────────────

@app.get("/api/health/full")
async def full_health_check(telegram: bool = False):
    """Run all 9 health checks. Set ?telegram=true to also fire Telegram alert."""
    from core.system_health import run_full_check
    return run_full_check(send_telegram=telegram)

@app.get("/api/health/quick")
async def quick_health():
    """Fast status check — Supabase + portfolio state only."""
    from core.system_health import check_supabase, check_portfolio_state
    results = [check_supabase(), check_portfolio_state()]
    reds = [r for r in results if r["status"] == "RED"]
    return {"overall": "RED" if reds else "GREEN", "checks": results}


# ── Login tracking ────────────────────────────────────────────────────────────
from pydantic import BaseModel

class LoginEventRequest(BaseModel):
    username:    str
    user_agent:  str = ""
    screen:      str = ""
    timezone:    str = ""
    language:    str = ""
    visitor_id:  str = ""
    visit_count: int = 1

@app.post("/api/login-event")
async def login_event(payload: LoginEventRequest, request: Request):
    """
    Called by frontend after successful login.
    Collects browser fingerprint + IP geolocation → Telegram alert.
    """
    # Extract real IP (Render sits behind a proxy)
    real_ip = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or request.headers.get("X-Real-IP", "")
        or request.client.host
    )
    from core.login_tracker import track_login
    result = track_login(
        username=payload.username,
        real_ip=real_ip,
        user_agent=payload.user_agent or request.headers.get("user-agent", ""),
        screen=payload.screen,
        timezone=payload.timezone,
        language=payload.language,
        visitor_id=payload.visitor_id,
        visit_count=payload.visit_count,
    )
    return result


# ── User auth endpoints ───────────────────────────────────────────────────────

class AuthLoginRequest(BaseModel):
    username: str
    password: str

class AuthRegisterRequest(BaseModel):
    username:     str
    password:     str
    display_name: str = ""

@app.post("/api/auth/login")
async def auth_login(payload: AuthLoginRequest, request: Request):
    """Validate credentials → return role + display name."""
    try:
        from backend.auth import login
        user = login(payload.username, payload.password)
        # Fire login tracking async (don't block)
        real_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.headers.get("X-Real-IP", "")
            or request.client.host
        )
        try:
            from core.login_tracker import track_login
            track_login(
                username=user["username"],
                real_ip=real_ip,
                user_agent=request.headers.get("user-agent", ""),
                screen="", timezone="", language="",
                visitor_id="", visit_count=1,
            )
        except Exception:
            pass
        return user
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.post("/api/auth/register")
async def auth_register(payload: AuthRegisterRequest):
    """Create a new visitor account."""
    try:
        from backend.auth import register
        user = register(payload.username, payload.password, payload.display_name)
        return user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/auth/users")
async def auth_users():
    """List all users — owner dashboard."""
    from backend.auth import list_users
    return {"users": list_users()}
