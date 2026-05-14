# Alpha-Omega System — Changes Log
# Session: 2026-05-14

---

## WHAT WE BUILT THIS SESSION

### 1. 3-ETF Sector Ranker (`core/sector_ranker.py`)
**Commit:** `53876cf`

**What:** Replaced single-ETF sector ranking with 3-ETF averaging per sector.

**How it works:**
- Each sector is measured by averaging returns across SPDR + iShares + Vanguard ETFs
- Example: Technology = average of XLK, IGM, VGT
- One batch yfinance download of all 34 unique ETFs + SPY
- 5-day and 20-day returns averaged → sector gets HOT / WARM / COLD label

**Why:** Single ETF is noisy (fund-specific flows). 3-ETF average is more reliable signal.

---

### 2. Momentum Pre-Screener (`core/momentum_screener.py`)
**Commits:** `a83da2b` (initial), `2144f8e` (memory fix)

**What:** New 2-stage pipeline — replaces the old "pick top stocks by market cap per sector" approach.

**Stage 1 — Momentum Pre-Screen:**
- Downloads ALL 377 stocks (>$10B universe) in chunks of 50
- Scores each stock: `5d_return × 0.5 + 20d_return × 0.3 + vol_surge_bonus × 0.2`
- Applies sector bias: HOT sector ×1.15, WARM ×1.00, COLD ×0.90
- Returns top 30 by adjusted_score
- Cache: 2 hours (`calibration/momentum_screen_cache.json`)

**Stage 2 — Conviction Deep Scan:**
- Autopilot deep-scans the top 30 momentum stocks
- 5-pillar conviction scoring
- Best conviction stocks become portfolio picks

**Why:** Old system only analyzed market-cap leaders and sector leaders. RKLB (Industrials, cold sector) was never analyzed. Now any >$10B stock with strong price action gets a fair shot.

**Memory fix (OOM crash):**
- Render free tier = 512MB RAM
- Old code: one download of 377 × 30 days = 400-600MB → crash
- Fix: chunks of 50 tickers, `del raw` + `gc.collect()` after each chunk, period 25d
- Each chunk uses ~40-80MB → safe under 512MB

---

### 3. Sector Tab Loads by Momentum (`backend/main.py` + endpoint)
**Commit:** `4bcb139`

**What:** Clicking a sector tab in Swing Scan now shows top 30 stocks ranked by momentum score, not market cap order.

**Endpoint:** `GET /api/sectors/watchlist/{sector_key}`
- Reads momentum screener cache
- Filters by sector → returns top 30 by adjusted_score
- Falls back to static universe order if cache is cold

**Before:** Info Tech → NVDA, AAPL, MSFT, AVGO... (pure market cap)
**After:** Info Tech → DDOG, AMD, INTC, MU, FTNT, QCOM, CRWD... (momentum ranked)

**Verified in Chrome:** Info Tech = 30 tickers, Health Care = 30 tickers (was crashing with "Maximum 30" error before).

---

### 4. Smart Scan Universe Button Fixed (`frontend/src/components/ScanDashboard.jsx`)
**Commit:** `f790bf1`

**What:** The "Smart Scan Universe" button was calling the old `/api/sectors/scan-universe` endpoint (market-cap order). Updated to call `/api/sectors/momentum-screen?top_n=30`.

**Before:** NVDA, AAPL, MSFT, AVGO... (old market-cap ranked)
**After:** Top 30 across ALL sectors by momentum score

**Fallback:** If momentum endpoint fails → falls back to old scan-universe endpoint.

---

### 5. Autopilot Uses Momentum Screener (`core/portfolio_manager.py`)
**Commit:** `a83da2b`

**What:** `autopilot_fill()` now uses the momentum screener as primary universe source.

**Flow:**
1. `screen_universe(top_n=30)` → momentum-ranked list
2. `run_scan(symbols)` → conviction deep scan on those 30
3. Best conviction stocks → open positions
4. Results saved to `calibration/last_portfolio_scan.json` (4h cache)

**Fallback chain:** momentum screener → sector ranker → watchlist

---

### 6. Shared Scan Cache (`calibration/last_portfolio_scan.json`)
**What:** Autopilot saves full scan results. The `/api/scan/candidates` endpoint reads from this cache to suggest bench candidates.

**TTL:** 4 hours

---

### 7. Fix: Sector Tab 30-Ticker Limit
**Commit:** `c7adac4`

**What:** Health Care has 45 tickers in universe. Clicking it was sending 45 to the API → "Maximum 30 tickers per scan" error. Fixed by slicing to 30 in `loadSector()` and `loadWatchlist()` in ScanDashboard.jsx.

---

### 8. Universe Cleanup (`core/universe_builder.py`)
**What:** Removed 7 delisted/unavailable tickers, added replacements.

Removed: SAMSF, DFS, K, WBA, HES, MRO, IPG, WRK
Added: APP, TTD, HOOD, COF, CELH, OKE, SPOT, BALL

Total: ~377 tickers across 11 GICS sectors, all >$10B market cap.

---

## NEW API ENDPOINTS

| Endpoint | What it does |
|---|---|
| `GET /api/sectors/momentum-screen?top_n=30` | Full momentum pre-screen, returns ranked results with scores |
| `GET /api/sectors/watchlist/{sector_key}` | Top 30 for a sector, momentum-sorted |
| `GET /api/scan/candidates` | Bench candidates from last autopilot scan cache |

---

## KEY FILES CHANGED

| File | Change |
|---|---|
| `core/momentum_screener.py` | NEW — chunked momentum pre-screener |
| `core/sector_ranker.py` | 3-ETF averaging instead of single ETF |
| `core/portfolio_manager.py` | autopilot_fill uses momentum screener |
| `core/universe_builder.py` | Cleaned up delisted tickers |
| `backend/main.py` | New endpoints: momentum-screen, watchlist, candidates |
| `frontend/src/components/ScanDashboard.jsx` | Smart Scan → momentum endpoint; sector tabs → slice to 30 |

---

## HOW THE STOCK SELECTION NOW WORKS (FULL PICTURE)

```
ALL 377 >$10B STOCKS
       ↓
  MOMENTUM PRE-SCREEN (Stage 1)
  5d return (50%) + 20d return (30%) + vol surge (20%)
  × sector bias (HOT +15%, COLD -10%)
  → Top 30 by adjusted_score
       ↓
  CONVICTION DEEP SCAN (Stage 2)
  5-pillar analysis on top 30
  → Scores 0-100%
       ↓
  PORTFOLIO SELECTION
  Best conviction → active trade
  Next best → BENCH candidates
```

---

## WHY YOUR CURRENT PORTFOLIO LOOKS THE WAY IT DOES

- **Old positions** (GOOGL, AMZN, AAPL etc.) → opened before momentum screener existed
- **New positions** (RKLB, HUM, SFM, GLW, PM, CVS) → opened by autopilot AFTER momentum screener deployed
- **NVDA has 73% conviction** but was NOT in top 30 by recent price momentum → was never deep-scanned by autopilot this cycle
- **MU** appears as bench candidate for Technology (outranked NVDA on 5d/20d returns)
- Portfolio is at 6/5 slots → next position opens when one closes

---

## PENDING / NEXT STEPS

- [ ] Verify Smart Scan Universe now loads momentum-sorted stocks in Chrome (Vercel deploy needed)
- [ ] Monitor Render for memory stability (chunked screener should hold under 512MB)
- [ ] Consider upgrading Render from free tier if screener run + portfolio manager overlap in RAM
- [ ] Consider pre-warming the momentum cache on startup (so first click is instant)
- [ ] Dynamic TP Phase 2 — wire conviction score to TP/SL adjustments (Task #30, in progress)
