from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend.schemas import AnalysisRequest, AnalysisResponse, ScanRequest, ScanResponse, BacktestRequest
import traceback
import random
import time

app = FastAPI(title="Alpha-Omega API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    """Generate a realistic demo response for any ticker."""
    # Pick a random scenario
    scenario_key = random.choice(["bullish", "bearish", "neutral"])
    scenario = DEMO_SCENARIOS[scenario_key]
    
    # Simulate processing time (1-3 seconds)
    time.sleep(random.uniform(1.0, 3.0))
    
    return AnalysisResponse(
        symbol=symbol.upper(),
        consensus_view=scenario["consensus_view"],
        confidence_score=scenario["confidence_score"],
        executioner_decision=scenario["executioner_decision"],
        full_report={
            "historian": scenario["historian"],
            "newsroom": scenario["newsroom"],
            "macro": scenario["macro"]
        },
        trade_params=scenario.get("trade_params"),
        mtf_analysis=scenario.get("mtf_analysis")
    )


@app.get("/")
async def root():
    return {"status": "System Online", "version": "1.0.0", "mode": "demo"}


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_stock(request: AnalysisRequest):
    """
    Analyze a stock ticker. Uses demo mode with realistic mock data.
    To use the real AI agents, set DEMO_MODE=false in .env and ensure
    your GOOGLE_API_KEY has the Generative Language API enabled.
    """
    try:
        symbol = request.symbol.upper()
        
        # Try real analysis first (V2: council + ledger + regime), fall back to demo
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


@app.post("/api/scan", response_model=ScanResponse)
async def scan_stocks(request: ScanRequest):
    """
    SwingTrader AI v4.3 scan endpoint.
    Fetches real market data via yfinance, then scores using Gemini + 5-pillar framework.
    """
    try:
        symbols = [s.upper().strip() for s in request.symbols if s.strip()]
        if not symbols:
            raise HTTPException(status_code=400, detail="No symbols provided")
        if len(symbols) > 30:
            raise HTTPException(status_code=400, detail="Maximum 30 tickers per scan")

        from agents.swing_scanner import SwingScanner
        scanner = SwingScanner()
        result = scanner.scan(symbols)

        # Log to trade journal
        try:
            from core.trade_journal import log_scan
            log_scan(result)
        except Exception as je:
            print(f"[JOURNAL] Log failed: {je}")

        if "error" in result and not result.get("results"):
            raise HTTPException(status_code=500, detail=result["error"])

        return ScanResponse(
            market_header=result.get("market_header", ""),
            market_regime=result.get("market_regime", ""),
            vix_estimate=result.get("vix_estimate", 0),
            results=result.get("results", []),
            error=result.get("error"),
        )
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/prices")
async def get_prices(request: ScanRequest):
    """Quick price + daily change for sidebar."""
    try:
        import yfinance as yf
        prices = []
        for sym in request.symbols[:12]:
            try:
                tk = yf.Ticker(sym.upper().strip())
                hist = tk.history(period="5d")
                if len(hist) >= 2:
                    close = float(hist["Close"].iloc[-1])
                    prev = float(hist["Close"].iloc[-2])
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
    """List available preset watchlists."""
    from core.watchlists import list_watchlists, WATCHLISTS
    return {"watchlists": {k: {"label": v["label"], "count": len(v["tickers"])} for k, v in WATCHLISTS.items()}}


@app.get("/api/watchlists/{name}")
async def get_watchlist(name: str):
    """Get tickers for a specific watchlist."""
    from core.watchlists import get_watchlist as gw
    wl = gw(name)
    return {"name": name, "label": wl["label"], "tickers": wl["tickers"]}


@app.post("/api/backtest")
async def run_backtest_endpoint(request: BacktestRequest):
    """Walk-forward backtest: score historical data, check if TP1 was hit."""
    try:
        symbols = [s.upper().strip() for s in request.symbols if s.strip()]
        if not symbols:
            raise HTTPException(status_code=400, detail="No symbols provided")
        if len(symbols) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 tickers per backtest")
        from core.backtester import run_backtest
        result = run_backtest(
            symbols, request.lookback_days, request.forward_days, request.sample_every
        )
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/calibrate")
async def run_calibration_endpoint(request: BacktestRequest):
    """Run auto-calibration: backtest + analyze + compute calibration curve."""
    try:
        symbols = [s.upper().strip() for s in request.symbols if s.strip()]
        if not symbols:
            raise HTTPException(status_code=400, detail="No symbols provided")
        from core.calibrator import run_calibration
        result = run_calibration(
            symbols, request.lookback_days, request.forward_days, request.sample_every
        )
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/calibration")
async def get_calibration():
    """Get current calibration parameters."""
    from core.calibrator import load_calibration
    return load_calibration()


@app.post("/api/calibration/reset")
async def reset_calibration():
    """Reset calibration to uncalibrated (raw scores)."""
    from core.calibrator import save_calibration
    save_calibration({"mode": "none", "scale": 1.0, "offset": 0})
    return {"status": "reset", "mode": "none"}


# ══════════════════════════════════════════
# SIGNAL TRACKER ENDPOINTS v2.0
# ══════════════════════════════════════════

@app.get("/api/signals")
async def get_signals():
    """Get all signals without price refresh (fast). Includes market status."""
    from core.signal_tracker import get_all_signals
    return get_all_signals()


@app.post("/api/signals/check")
async def check_signals():
    """Refresh live prices with gap detection, MAE/MFE, staleness checks."""
    from core.signal_tracker import check_signals as cs
    return cs()


@app.post("/api/signals/close/{signal_id}")
async def close_signal(signal_id: str):
    """Manually close a signal with full audit trail."""
    from core.signal_tracker import close_signal as cls
    result = cls(signal_id)
    if not result:
        raise HTTPException(status_code=404, detail="Signal not found")
    return result


@app.post("/api/signals/clear")
async def clear_signals():
    """Reset all signals."""
    from core.signal_tracker import clear_all
    return clear_all()


@app.post("/api/signals/turbo/{symbol}")
async def turbo_signal(symbol: str, asset_type: str = "stock"):
    """Launch ATR-based turbo signal with full audit trail."""
    from core.signal_tracker import create_turbo_signal
    result = create_turbo_signal(symbol, asset_type)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/signals/report/{signal_id}")
async def get_signal_report(signal_id: str):
    """Get detailed case report for a closed signal."""
    from core.signal_tracker import get_signal_report as gsr
    report = gsr(signal_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@app.get("/api/signals/reports")
async def get_all_reports():
    """Get all case reports (most recent first)."""
    from core.signal_tracker import get_all_reports as gar
    return {"reports": gar()}


@app.get("/api/signals/regime-performance")
async def get_regime_performance():
    """Performance breakdown by market regime."""
    from core.signal_tracker import get_regime_performance as grp
    return grp()


@app.post("/api/autopilot")
async def run_autopilot(top_n: int = 10, watchlist: str = "full_scan"):
    """
    AUTO-PILOT: Scan universe → rank by conviction → launch turbo signals for top N.
    One button to rule them all.
    """
    try:
        from agents.swing_scanner import SwingScanner
        from core.signal_tracker import create_turbo_signal, get_all_signals
        from core.watchlists import get_watchlist

        # Step 1: Get universe
        wl = get_watchlist(watchlist)
        symbols = wl["tickers"]

        # Step 2: Scan all
        scanner = SwingScanner()
        scan_result = scanner.scan(symbols)
        results = scan_result.get("results", [])

        # Step 3: Filter and rank
        valid = [r for r in results if not r.get("hard_fail") and r.get("conviction_pct", 0) > 0]
        ranked = sorted(valid, key=lambda x: x.get("conviction_pct", 0), reverse=True)
        top = ranked[:top_n]

        # Step 4: Get existing active tickers to avoid duplicates
        existing = get_all_signals()
        active_tickers = {s["ticker"] for s in existing.get("active", [])}

        # Step 5: Launch turbo signals WITH full scan data (audit trail)
        launched = []
        skipped = []
        for r in top:
            ticker = r["ticker"]
            if ticker in active_tickers:
                skipped.append({"ticker": ticker, "reason": "already active"})
                continue
            sig = create_turbo_signal(ticker, scan_data=r)
            if "error" not in sig:
                launched.append({
                    "ticker": ticker,
                    "conviction": r.get("conviction_pct", 0),
                    "heat": r.get("heat", ""),
                    "entry": sig.get("entry_price", 0),
                    "sl": sig.get("sl", 0),
                    "tp1": sig.get("tp1", 0),
                    "atr": sig.get("atr_at_entry", 0),
                    "target_method": sig.get("target_method", ""),
                })
                active_tickers.add(ticker)
            else:
                skipped.append({"ticker": ticker, "reason": sig["error"]})

        result = {
            "status": "ok",
            "scanned": len(symbols),
            "passed_filter": len(valid),
            "launched": launched,
            "skipped": skipped,
            "top_ranked": [{"ticker": r["ticker"], "conviction": r.get("conviction_pct",0),
                           "heat": r.get("heat",""), "tas": r.get("tas","")} for r in top],
            "market_regime": scan_result.get("market_regime", ""),
        }

        # ── Telegram alert: autopilot launched ──
        try:
            from core.telegram_alerts import alert_autopilot_launched
            alert_autopilot_launched(len(launched), "stocks")
        except Exception:
            pass

        return result

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


CRYPTO_UNIVERSE = [
    "BTC", "ETH", "SOL", "XRP", "ADA", "AVAX", "DOGE", "DOT",
    "MATIC", "LINK", "NEAR", "UNI", "AAVE", "LTC", "ATOM",
]


@app.post("/api/autopilot/crypto")
async def run_crypto_autopilot(top_n: int = 10):
    """
    CRYPTO AUTO-PILOT: Launch turbo signals for top crypto assets.
    Crypto trades 24/7 so results show immediately.
    """
    try:
        from core.signal_tracker import create_turbo_signal, get_all_signals
        import yfinance as yf

        existing = get_all_signals()
        active_tickers = {s["ticker"] for s in existing.get("active", [])}

        crypto_data = []
        for sym in CRYPTO_UNIVERSE:
            if sym in active_tickers:
                continue
            try:
                tk = yf.Ticker(f"{sym}-USD")
                fi = tk.fast_info
                price = fi.get("lastPrice") or fi.get("last_price", 0)
                if price and price > 0:
                    crypto_data.append({"ticker": sym, "price": float(price)})
            except Exception:
                pass

        top = crypto_data[:top_n]

        launched = []
        skipped = []
        for c in top:
            sig = create_turbo_signal(c["ticker"], asset_type="crypto")
            if "error" not in sig:
                launched.append({
                    "ticker": c["ticker"],
                    "conviction": 0,
                    "heat": "CRYPTO",
                    "entry": sig.get("entry_price", 0),
                    "sl": sig.get("sl", 0),
                    "tp1": sig.get("tp1", 0),
                    "atr": sig.get("atr_at_entry", 0),
                    "target_method": sig.get("target_method", ""),
                })
            else:
                skipped.append({"ticker": c["ticker"], "reason": sig["error"]})

        return {
            "status": "ok",
            "scanned": len(CRYPTO_UNIVERSE),
            "passed_filter": len(crypto_data),
            "launched": launched,
            "skipped": skipped,
            "market_regime": "Crypto 24/7",
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Storage Management ──────────────────────────────────────
@app.get("/api/signals/storage-status")
async def storage_status():
    """Check which storage backend is active."""
    from core.signal_store import get_storage_status
    return get_storage_status()

@app.post("/api/signals/sync")
async def sync_signals():
    """Push local JSON data to Supabase."""
    from core.signal_store import sync_local_to_supabase
    return sync_local_to_supabase()

@app.get("/api/signals/storage-debug")
async def storage_debug():
    """Debug Supabase connection."""
    import os
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    result = {"url_set": bool(url), "key_set": bool(key), "url_prefix": url[:30] if url else ""}
    try:
        from supabase import create_client
        sb = create_client(url, key)
        sb.table("signals").select("id").limit(1).execute()
        result["connection"] = "OK"
    except Exception as e:
        result["connection"] = f"FAIL: {str(e)[:200]}"
    return result


# ── Telegram Test ────────────────────────────────────────────
@app.post("/api/alerts/test")
async def test_telegram_alert():
    """Send a test alert to Telegram to verify setup."""
    try:
        from core.telegram_alerts import test_alert
        ok = test_alert()
        return {"status": "sent" if ok else "failed", "message": "Check your Telegram"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Chart Data ──────────────────────────────────────────────
@app.get("/api/chart/{symbol}")
async def get_chart_data(symbol: str, interval: str = "1d", period: str = "6M"):
    """Return OHLC candles + S/R + channel + buy/sell signals + MTF analysis."""
    try:
        import yfinance as yf
        import numpy as np
        import pandas as pd

        ticker = yf.Ticker(symbol.upper())

        # Period → yfinance string
        period_map = {"1M":"1mo","3M":"3mo","6M":"6mo","1Y":"1y","3Y":"2y","5Y":"5y"}
        yf_period  = period_map.get(period, "6mo")

        # Fetch data based on interval
        if interval == "1h":
            yf_period = period_map.get(period, "1mo") if period in ["1M","3M"] else "1mo"
            hist = ticker.history(period=yf_period, interval="60m")
        elif interval == "4h":
            yf_period = period_map.get(period, "3mo") if period in ["1M","3M","6M"] else "3mo"
            h1 = ticker.history(period=yf_period, interval="60m")
            if not h1.empty:
                hist = h1.resample("4h").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
            else:
                hist = h1
        elif interval == "1w":
            hist = ticker.history(period=yf_period, interval="1wk")
        else:  # 1d default
            hist = ticker.history(period=yf_period, interval="1d")

        if hist.empty:
            return {"symbol": symbol.upper(), "interval": interval, "period": period,
                    "candles": [], "sr_levels": [], "channel": None, "signals": [], "mtf": {}}

        # Format timestamps
        def fmt_ts(ts):
            try:
                return ts.strftime("%Y-%m-%d %H:%M") if interval in ["1h","4h"] else ts.strftime("%Y-%m-%d")
            except:
                return str(ts)[:16]

        candles = []
        for ts, row in hist.iterrows():
            candles.append({
                "t": fmt_ts(ts),
                "o": round(float(row["Open"]), 2),
                "h": round(float(row["High"]), 2),
                "l": round(float(row["Low"]), 2),
                "c": round(float(row["Close"]), 2),
                "v": int(row["Volume"])
            })

        closes = hist["Close"].values
        highs  = hist["High"].values
        lows   = hist["Low"].values

        # S/R levels from swing pivots
        sr_levels = []
        for i in range(2, len(closes) - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                sr_levels.append({"level": round(float(highs[i]), 2), "type": "resistance"})
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                sr_levels.append({"level": round(float(lows[i]), 2), "type": "support"})
        filtered_sr = []
        for lvl in sr_levels:
            if not any(abs(l["level"] - lvl["level"]) / max(lvl["level"], 1) < 0.005 for l in filtered_sr):
                filtered_sr.append(lvl)

        # Linear regression channel
        x = np.arange(len(closes))
        m, b = np.polyfit(x, closes, 1)
        std  = float(np.std(closes - (m * x + b)))
        n    = len(closes) - 1
        channel = {
            "upper": [round(float(b + 2*std), 2), round(float(m*n + b + 2*std), 2)],
            "mid":   [round(float(b), 2),          round(float(m*n + b), 2)],
            "lower": [round(float(b - 2*std), 2),  round(float(m*n + b - 2*std), 2)]
        }

        # Buy/Sell signals via EMA20/EMA50 crossover
        close_s = hist["Close"]
        ema20   = close_s.ewm(span=20, adjust=False).mean()
        ema50   = close_s.ewm(span=50, adjust=False).mean()
        signals = []
        for i in range(1, len(close_s)):
            prev_diff = float(ema20.iloc[i-1]) - float(ema50.iloc[i-1])
            curr_diff = float(ema20.iloc[i])   - float(ema50.iloc[i])
            if prev_diff <= 0 and curr_diff > 0:
                signals.append({"t": fmt_ts(hist.index[i]), "type": "BUY",  "price": round(float(close_s.iloc[i]), 2)})
            elif prev_diff >= 0 and curr_diff < 0:
                signals.append({"t": fmt_ts(hist.index[i]), "type": "SELL", "price": round(float(close_s.iloc[i]), 2)})

        # MTF analysis — BULL if price > EMA20 on each timeframe
        def mtf_trend(iv, per):
            try:
                h = ticker.history(period=per, interval=iv)
                if h.empty or len(h) < 5: return "NEUTRAL"
                if iv == "60m" and per == "4h_resample":
                    h = h.resample("4h").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
                c  = h["Close"]
                e  = c.ewm(span=20, adjust=False).mean()
                return "BULL" if float(c.iloc[-1]) > float(e.iloc[-1]) else "BEAR"
            except:
                return "NEUTRAL"

        mtf = {
            "tf_1h": mtf_trend("60m",  "5d"),
            "tf_4h": mtf_trend("60m",  "4h_resample"),
            "tf_1d": mtf_trend("1d",   "3mo"),
            "tf_1w": mtf_trend("1wk",  "1y"),
        }

        return {"symbol": symbol.upper(), "interval": interval, "period": period,
                "candles": candles, "sr_levels": filtered_sr[:10],
                "channel": channel, "signals": signals, "mtf": mtf}

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Sector Heat ─────────────────────────────────────────────
@app.get("/api/sectors/heat")
async def sector_heat():
    """Score all 11 GICS sectors via their benchmark ETF using the conviction engine."""
    try:
        from core.watchlists import SECTOR_WATCHLISTS
        from agents.swing_scanner import SwingScanner
        scanner = SwingScanner()
        etfs = [v["etf"] for v in SECTOR_WATCHLISTS.values()]
        results = scanner.scan(etfs)
        scored = []
        for key, meta in SECTOR_WATCHLISTS.items():
            etf = meta["etf"]
            match = next((r for r in results if r.get("ticker") == etf and not r.get("hard_fail")), None)
            score = match["conviction_pct"] if match else 0
            trend = match.get("trend", "—") if match else "—"
            scored.append({
                "key": key, "label": meta["label"], "etf": etf,
                "score": score, "trend": trend,
                "heat": "HOT" if score >= 70 else "WARM" if score >= 55 else "COLD"
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return {"sectors": scored}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sectors/watchlist/{sector_key}")
async def sector_watchlist(sector_key: str):
    """Get tickers for a specific sector."""
    from core.watchlists import SECTOR_WATCHLISTS
    if sector_key not in SECTOR_WATCHLISTS:
        raise HTTPException(status_code=404, detail=f"Sector '{sector_key}' not found")
    s = SECTOR_WATCHLISTS[sector_key]
    return {"key": sector_key, "label": s["label"], "etf": s["etf"], "tickers": s["tickers"]}


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

        # Rebuild scan only if cache stale
        if now - _ALPHA_MEGA_CACHE["ts"] > _CACHE_TTL or not _ALPHA_MEGA_CACHE["data"]:
            # Universe: top 5 tickers per sector
            candidates = {}
            for key, meta in SECTOR_WATCHLISTS.items():
                for t in meta["tickers"][:5]:
                    if t not in candidates:
                        candidates[t] = key

            scanner = SwingScanner()
            raw_result = scanner.scan(list(candidates.keys()))
            raw = raw_result.get("results", []) if isinstance(raw_result, dict) else (raw_result or [])

            # Filter: no hard fail, market cap >= $10B, has conviction score
            filtered = [r for r in raw
                        if not r.get("hard_fail")
                        and (r.get("mkt_cap_b") or 0) >= 10
                        and r.get("conviction_pct", 0) > 0]

            # Compute alpha score: conviction 40% + MTF 30% + trend 20% + vol 10%
            for r in filtered:
                tf = r.get("tf_breakdown") or {}
                bull_tfs = sum(1 for k in ["tf_65m","tf_240m","tf_daily","tf_weekly"] if tf.get(k) == "BULL")
                mtf_score = (bull_tfs / 4) * 100
                trend_sc  = 80 if r.get("trend") == "BULL" else 20
                vol_sc    = min(100, (r.get("vol_ratio") or 1) * 40)
                r["alpha_score"] = round(r["conviction_pct"]*0.4 + mtf_score*0.3 + trend_sc*0.2 + vol_sc*0.1, 1)
                r["sector_key"]  = candidates.get(r["ticker"], "")

            filtered.sort(key=lambda x: x["alpha_score"], reverse=True)
            _ALPHA_MEGA_CACHE["ts"]   = now
            _ALPHA_MEGA_CACHE["data"] = filtered[:20]

        top20 = _ALPHA_MEGA_CACHE["data"] or []

        # P&L always fresh (cheap yfinance call)
        period_map = {30:"1mo", 90:"3mo", 180:"6mo", 360:"1y"}
        yf_period  = period_map.get(lookback_days, "1mo")
        results = []
        for r in top20:
            pnl_pct = 0.0
            try:
                hist = yf.Ticker(r["ticker"]).history(period=yf_period)
                if len(hist) >= 2:
                    pnl_pct = round((hist["Close"].iloc[-1] - hist["Close"].iloc[0]) / hist["Close"].iloc[0] * 100, 2)
            except:
                pass
            results.append({**r, "pnl_pct": pnl_pct})

        # Portfolio: top 5 diversified across sectors
        seen_sectors, portfolio = set(), []
        for r in results:
            sk = r.get("sector_key", "")
            if sk not in seen_sectors and len(portfolio) < 5:
                portfolio.append(r["ticker"])
                seen_sectors.add(sk)

        return {
            "top20": results, "portfolio": portfolio,
            "lookback_days": lookback_days,
            "last_updated": int(_ALPHA_MEGA_CACHE["ts"]),
            "total_scanned": len(_ALPHA_MEGA_CACHE["data"] or [])
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# #1  EARNINGS CALENDAR
# ═══════════════════════════════════════════════════════════════════
@app.get("/api/earnings/{symbol}")
async def get_earnings(symbol: str):
    """Return next earnings date + days until + EPS estimates."""
    try:
        import yfinance as yf
        from datetime import date, datetime
        tk = yf.Ticker(symbol.upper())
        cal = tk.calendar
        result = {"symbol": symbol.upper(), "earnings_date": None, "days_until": None,
                  "warning": False, "warning_msg": ""}
        if cal is not None and not cal.empty:
            try:
                # calendar is a DataFrame with dates as columns
                col = cal.columns[0]
                dt = col
                if hasattr(dt, 'date'):
                    dt = dt.date()
                elif isinstance(dt, str):
                    dt = date.fromisoformat(dt[:10])
                today = date.today()
                days = (dt - today).days
                result["earnings_date"] = str(dt)
                result["days_until"] = days
                if 0 <= days <= 7:
                    result["warning"] = True
                    result["warning_msg"] = f"⚠ EARNINGS IN {days} DAY{'S' if days != 1 else ''} — high volatility risk"
            except Exception:
                pass
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))



# ═══════════════════════════════════════════════════════════════════
# #2  PORTFOLIO RISK LAYER
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
    """
    Analyse current open signals for concentration risk, drawdown, and correlation.
    """
    try:
        from core import signal_store as store
        active = store.load_active()

        if not active:
            return {"risk_level": "LOW", "signals": 0, "warnings": [],
                    "sector_exposure": {}, "worst_case_loss_pct": 0}

        # Sector exposure
        sector_exposure: dict = {}
        for s in active:
            sec = SECTOR_MAP.get(s["ticker"], "Other")
            sector_exposure[sec] = sector_exposure.get(sec, 0) + 1

        # Concentration warnings
        warnings = []
        for sec, cnt in sector_exposure.items():
            if cnt >= 3:
                warnings.append(f"🔴 HIGH CONCENTRATION: {cnt} open signals in {sec}")
            elif cnt == 2:
                warnings.append(f"🟡 MODERATE: 2 signals in {sec}")

        # Worst-case drawdown if ALL SLs hit simultaneously
        total_risk_pct = 0.0
        signal_risks = []
        for s in active:
            entry = s.get("entry_price", 0)
            sl    = s.get("targets", {}).get("sl") or s.get("sl", 0)
            if entry > 0 and sl > 0:
                risk_pct = round((sl - entry) / entry * 100, 2)
                signal_risks.append({"ticker": s["ticker"], "risk_pct": risk_pct})
                total_risk_pct += risk_pct
            else:
                signal_risks.append({"ticker": s["ticker"], "risk_pct": 0})

        worst_case = round(total_risk_pct / len(active), 2) if active else 0

        # Overall risk level
        max_conc = max(sector_exposure.values()) if sector_exposure else 0
        if max_conc >= 4 or len(active) >= 8:
            risk_level = "HIGH"
        elif max_conc >= 3 or len(active) >= 5:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        if worst_case < -3:
            warnings.append(f"🔴 WORST CASE: all SLs hit = {worst_case:.1f}% portfolio loss")

        return {
            "risk_level": risk_level,
            "signals": len(active),
            "warnings": warnings,
            "sector_exposure": sector_exposure,
            "signal_risks": signal_risks,
            "worst_case_loss_pct": worst_case,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))



# ═══════════════════════════════════════════════════════════════════
# #3  LEARNING LOOP / ANALYTICS
# ═══════════════════════════════════════════════════════════════════
@app.get("/api/analytics/performance")
async def analytics_performance():
    """
    Derive win rates, conviction accuracy, and regime performance from closed signals.
    This IS the learning loop — the system reflects on its own trades.
    """
    try:
        from core import signal_store as store
        closed = store.load_closed()

        if not closed:
            return {"total": 0, "message": "No closed signals yet. Run Auto-Pilot to generate signals."}

        wins   = [s for s in closed if s.get("pnl_pct", 0) > 0]
        losses = [s for s in closed if s.get("pnl_pct", 0) <= 0]
        total  = len(closed)
        win_rate = round(len(wins) / total * 100, 1) if total else 0

        # Average P&L
        avg_win  = round(sum(s["pnl_pct"] for s in wins)  / len(wins),  2) if wins  else 0
        avg_loss = round(sum(s["pnl_pct"] for s in losses) / len(losses), 2) if losses else 0

        # Profit factor
        gross_profit = sum(s["pnl_pct"] for s in wins)  if wins   else 0
        gross_loss   = abs(sum(s["pnl_pct"] for s in losses)) if losses else 1
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss else 0

        # Win rate by conviction bucket
        buckets = {"50-59": [], "60-69": [], "70-79": [], "80-89": [], "90+": []}
        for s in closed:
            c = s.get("conviction", s.get("scan_data", {}).get("conviction_pct", 0)) or 0
            b = "50-59" if c < 60 else "60-69" if c < 70 else "70-79" if c < 80 else "80-89" if c < 90 else "90+"
            buckets[b].append(s)
        conviction_breakdown = {}
        for b, sigs in buckets.items():
            if sigs:
                w = sum(1 for s in sigs if s.get("pnl_pct", 0) > 0)
                conviction_breakdown[b] = {"trades": len(sigs), "win_rate": round(w/len(sigs)*100, 1)}

        # Win rate by market regime
        regime_breakdown = {}
        for s in closed:
            reg = s.get("market_context", {}).get("regime", "Unknown")
            if reg not in regime_breakdown:
                regime_breakdown[reg] = {"trades": 0, "wins": 0}
            regime_breakdown[reg]["trades"] += 1
            if s.get("pnl_pct", 0) > 0:
                regime_breakdown[reg]["wins"] += 1
        for reg in regime_breakdown:
            t = regime_breakdown[reg]["trades"]
            w = regime_breakdown[reg]["wins"]
            regime_breakdown[reg]["win_rate"] = round(w/t*100, 1) if t else 0

        # TP/SL hit rates
        tp1_hits = sum(1 for s in closed if s.get("tp1_hit")) 
        tp2_hits = sum(1 for s in closed if s.get("tp2_hit"))
        stopped  = sum(1 for s in closed if "STOPPED" in s.get("status", ""))

        # MAE/MFE averages
        avg_mae = round(sum(s.get("mae_pct", 0) for s in closed) / total, 2) if total else 0
        avg_mfe = round(sum(s.get("mfe_pct", 0) for s in closed) / total, 2) if total else 0

        return {
            "total": total,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "avg_win_pct": avg_win,
            "avg_loss_pct": avg_loss,
            "profit_factor": profit_factor,
            "tp1_hit_rate": round(tp1_hits / total * 100, 1) if total else 0,
            "tp2_hit_rate": round(tp2_hits / total * 100, 1) if total else 0,
            "stopped_out_rate": round(stopped / total * 100, 1) if total else 0,
            "avg_mae_pct": avg_mae,
            "avg_mfe_pct": avg_mfe,
            "conviction_breakdown": conviction_breakdown,
            "regime_breakdown": regime_breakdown,
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))



# ═══════════════════════════════════════════════════════════════════
# #4  REAL-TIME DATA — Alpaca (optional, falls back to yfinance)
# ═══════════════════════════════════════════════════════════════════
@app.get("/api/price/live/{symbol}")
async def get_live_price(symbol: str):
    """
    Try Alpaca first (real-time), fall back to yfinance (15-20min delayed).
    Returns price + source + delay indicator.
    """
    import os, yfinance as yf
    sym = symbol.upper()
    alpaca_key    = os.environ.get("ALPACA_API_KEY", "")
    alpaca_secret = os.environ.get("ALPACA_SECRET_KEY", "")

    # Try Alpaca real-time
    if alpaca_key and alpaca_secret:
        try:
            import urllib.request, json as _json
            url = f"https://data.alpaca.markets/v2/stocks/{sym}/trades/latest"
            req = urllib.request.Request(url, headers={
                "APCA-API-KEY-ID": alpaca_key,
                "APCA-API-SECRET-KEY": alpaca_secret,
                "User-Agent": "Mozilla/5.0"
            })
            with urllib.request.urlopen(req, timeout=5) as r:
                data = _json.loads(r.read().decode())
                price = float(data["trade"]["p"])
                return {"symbol": sym, "price": price, "source": "alpaca", "realtime": True, "delay_min": 0}
        except Exception:
            pass  # Fall through to yfinance

    # yfinance fallback
    try:
        tk = yf.Ticker(sym)
        hist = tk.history(period="1d", interval="1m")
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
            return {"symbol": sym, "price": round(price, 4), "source": "yfinance", "realtime": False, "delay_min": 15}
    except Exception:
        pass

    raise HTTPException(status_code=404, detail=f"Could not fetch price for {sym}")


@app.get("/api/data/source")
async def get_data_source():
    """Returns which data source is active: alpaca (real-time) or yfinance (delayed)."""
    import os
    alpaca_key = os.environ.get("ALPACA_API_KEY", "")
    return {
        "source": "alpaca" if alpaca_key else "yfinance",
        "realtime": bool(alpaca_key),
        "delay_min": 0 if alpaca_key else 15,
        "label": "LIVE" if alpaca_key else "DELAYED ~15min"
    }


# ═══════════════════════════════════════════════════════════════════
# #5  SECTOR FLIP ALERTS (called from check_signals or on demand)
# ═══════════════════════════════════════════════════════════════════
_SECTOR_TREND_CACHE: dict = {}  # {etf: {"trend": "BULL"/"BEAR", "ts": float}}

@app.post("/api/alerts/sector-check")
async def check_sector_flips():
    """
    Check all 11 sector ETFs for BULL→BEAR or BEAR→BULL flips.
    Fires Telegram alert on flip. Call this periodically or manually.
    """
    import time, yfinance as yf
    import pandas as pd
    SECTOR_ETFS = {
        "XLK": "Info Tech",   "XLF": "Financials",  "XLV": "Health Care",
        "XLI": "Industrials", "XLY": "Cons. Disc.",  "XLP": "Cons. Staples",
        "XLE": "Energy",      "XLC": "Comm. Svcs",   "XLU": "Utilities",
        "XLB": "Materials",   "XLRE": "Real Estate",
    }
    flips = []
    for etf, name in SECTOR_ETFS.items():
        try:
            tk = yf.Ticker(etf)
            hist = tk.history(period="5d", interval="1d")
            if hist.empty or len(hist) < 2:
                continue
            close = hist["Close"]
            ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
            current = float(close.iloc[-1])
            trend = "BULL" if current > ema20 else "BEAR"
            prev = _SECTOR_TREND_CACHE.get(etf, {}).get("trend")
            _SECTOR_TREND_CACHE[etf] = {"trend": trend, "ts": time.time()}
            if prev and prev != trend:
                flips.append({"etf": etf, "sector": name, "from": prev, "to": trend})
                try:
                    from core.telegram_alerts import _send
                    emoji = "🟢" if trend == "BULL" else "🔴"
                    _send(f"{emoji} <b>SECTOR FLIP — {name}</b>\n{etf}: {prev} → <b>{trend}</b>\n🕐 {__import__('datetime').datetime.utcnow().strftime('%H:%M UTC')}")
                except Exception:
                    pass
        except Exception:
            pass
    return {"checked": len(SECTOR_ETFS), "flips": flips, "flips_count": len(flips)}


# ══════════════════════════════════════════════════════════════
# PORTFOLIO TAB — Paper Trading Engine v1.0
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
    reason = (body or {}).get("reason", "MANUAL")
    return close_position(position_id, reason)

@app.post("/api/portfolio/autopilot")
async def portfolio_autopilot_endpoint(body: dict = {}):
    from core.portfolio_manager import autopilot_fill
    watchlist = (body or {}).get("watchlist", "full_scan")
    return autopilot_fill(watchlist)

@app.post("/api/portfolio/reset")
async def reset_portfolio_endpoint():
    from core.portfolio_store import clear_all_positions
    clear_all_positions()
    return {"reset": True, "message": "Portfolio reset to $25,000"}

@app.get("/api/portfolio/status")
async def portfolio_storage_status_endpoint():
    from core.portfolio_store import supabase_ready
    return {"supabase": supabase_ready(), "storage": "supabase" if supabase_ready() else "json_fallback"}


# ══════════════════════════════════════════════════════════════
# PRINTING PROFITS — Dual Long/Short Trading Engine
# All routes prefixed /api/printing/ — zero collision with existing routes
# ══════════════════════════════════════════════════════════════

@app.post("/api/printing/scan")
async def printing_scan_endpoint(body: dict = {}):
    from core.printing_scanner import run_dual_scan
    watchlist = (body or {}).get("watchlist", "full_scan")
    symbols   = (body or {}).get("symbols", None)
    return run_dual_scan(symbols=symbols, watchlist_name=watchlist)

@app.get("/api/printing/futures")
async def printing_futures_endpoint():
    from core.futures_data import fetch_all_futures
    return fetch_all_futures()

@app.get("/api/printing/regime")
async def printing_regime_endpoint():
    from core.market_data import fetch_market_regime
    from core.regime_engine import get_strategy_mode
    regime = fetch_market_regime()
    return {"regime": regime, "mode": get_strategy_mode(regime)}

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
    ticker = body.get("ticker","").upper()
    direction = body.get("direction","long")
    entry = float(body.get("entry_price",0))
    sl    = float(body.get("sl",0))
    tp1   = float(body.get("tp1",0))
    tp2   = float(body.get("tp2",0))
    tp3   = float(body.get("tp3",0))
    conv  = int(body.get("conviction",65))
    if not ticker or not entry or not sl or not tp1:
        raise HTTPException(status_code=400, detail="ticker, entry_price, sl, tp1 required")
    return open_position(ticker, direction, entry, sl, tp1, tp2, tp3, conv)

@app.post("/api/printing/portfolio/close/{position_id}")
async def printing_close_endpoint(position_id: str, body: dict = {}):
    from core.printing_portfolio import close_position
    return close_position(position_id, (body or {}).get("reason","MANUAL"))

@app.post("/api/printing/portfolio/autopilot")
async def printing_autopilot_endpoint(body: dict = {}):
    from core.printing_portfolio import autopilot_dual
    return autopilot_dual((body or {}).get("watchlist","full_scan"))

@app.post("/api/printing/portfolio/reset")
async def printing_reset_endpoint():
    from core.printing_store import clear_all
    clear_all()
    return {"reset": True, "message": "Printing Profits portfolio reset to $25,000"}

@app.get("/api/printing/status")
async def printing_status_endpoint():
    from core.printing_store import supabase_ready
    return {"supabase": supabase_ready(),
            "storage": "supabase" if supabase_ready() else "json_fallback"}

