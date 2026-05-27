# ALPHA-OMEGA SYSTEM — FULL TECHNICAL PRD FOR CURSOR AI
**Version:** 4.0 (current as of 2026-05-27)
**Owner:** Avi
**Repo:** `github.com/agentface8-hue/Alpha-Omega-System`
**Local path:** `C:\Users\asus\Alpha-Omega-System`

---

## TABLE OF CONTENTS
1. [What This System Is](#1-what-this-system-is)
2. [System Architecture Overview](#2-system-architecture-overview)
3. [Deployment & Infrastructure](#3-deployment--infrastructure)
4. [Complete File Map](#4-complete-file-map)
5. [Backend: All API Endpoints](#5-backend-all-api-endpoints)
6. [Core Modules — Business Logic](#6-core-modules--business-logic)
7. [AI Agents — Council of Experts](#7-ai-agents--council-of-experts)
8. [Frontend: React App](#8-frontend-react-app)
9. [Data Storage Architecture](#9-data-storage-architecture)
10. [Integrations & API Keys](#10-integrations--api-keys)
11. [Background Services & Scheduled Tasks](#11-background-services--scheduled-tasks)
12. [Signal Tracker vs Portfolio — Critical Distinction](#12-signal-tracker-vs-portfolio--critical-distinction)
13. [Conviction Engine — 5-Pillar System](#13-conviction-engine--5-pillar-system)
14. [Portfolio System — Position Lifecycle](#14-portfolio-system--position-lifecycle)
15. [Health Monitor Architecture](#15-health-monitor-architecture)
16. [Current System State & Known Issues](#16-current-system-state--known-issues)
17. [Deploy Workflow](#17-deploy-workflow)
18. [Tech Stack Summary](#18-tech-stack-summary)
19. [Critical Rules for Working on This Codebase](#19-critical-rules-for-working-on-this-codebase)

---

## 1. WHAT THIS SYSTEM IS

Alpha-Omega is a fully deployed AI-powered paper trading and market analysis system. It:

- **Scans** 377 large-cap stocks using a 2-stage pipeline (momentum pre-screen → conviction deep scan)
- **Ranks** stocks by a 5-pillar conviction score (trend, volume, S/R, multi-timeframe, R:R)
- **Manages** a $25,000 paper trading portfolio with up to 8 simultaneous positions
- **Tracks** signals end-to-end with 79-point audit trails (entry context, price feed, MAE/MFE, case reports)
- **Monitors** itself via a 3-level health check system with real-time Telegram alerts
- **Learns** via a learning loop that analyzes trade history and adjusts calibration parameters
- **Dreams** — runs overnight AI analysis cycles generating market insights (Dreaming Agent)
- **Alerts** via Telegram bot (@AlphaOmegaCEO_bot) — position opens, TP hits, SL hits, system health
- **Executes** orders via IBKR TWS API (implemented, awaiting account approval)

The system has been running continuously since February 2026. It has processed 84+ historical trades stored in Supabase, runs scheduled morning briefings and market checks, and supports natural language commands via Telegram.

---

## 2. SYSTEM ARCHITECTURE OVERVIEW

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Vercel)                        │
│          React 18 + Vite 7 + Tailwind CSS                       │
│   alpha-omega-ngfw.vercel.app                                   │
│                                                                  │
│  Tabs: Council Analyze | Swing Scan | Backtester |               │
│        Signal Tracker | Portfolio | Deep Scan                    │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS REST API
┌──────────────────────────▼──────────────────────────────────────┐
│                      BACKEND (Render $25/mo)                     │
│         FastAPI + Uvicorn   alpha-omega-system.onrender.com      │
│                                                                  │
│  backend/main.py — 2200+ lines, ALL endpoints                   │
│  Startup: keepalive + live_monitor + telegram_agent +            │
│           learning_loop + ai_health_agent                        │
└──┬────────────────────────┬──────────────────────────┬──────────┘
   │                        │                          │
┌──▼──────────┐  ┌──────────▼──────────┐  ┌───────────▼─────────┐
│  core/      │  │  agents/            │  │  External Services  │
│  Business   │  │  AI Expert Council  │  │                     │
│  Logic      │  │  10 LLM agents      │  │  Supabase (DB)      │
│             │  │                     │  │  Finnhub (prices)   │
│  portfolio_ │  │  Gemini 2.0 Flash   │  │  Telegram Bot       │
│  manager.py │  │  Claude Opus 4.7    │  │  Airtable (trades)  │
│  signal_    │  │  Claude Sonnet 4.6  │  │  IBKR TWS (orders)  │
│  tracker.py │  │                     │  │                     │
│  conviction_│  └─────────────────────┘  └─────────────────────┘
│  engine.py  │
│  learning_  │
│  loop.py    │
│  ...        │
└─────────────┘
```

---

## 3. DEPLOYMENT & INFRASTRUCTURE

### Hosting

| Component | Platform | URL | Plan |
|-----------|----------|-----|------|
| Frontend | Vercel | https://alpha-omega-ngfw.vercel.app | Free |
| Backend | Render | https://alpha-omega-system.onrender.com | $25/mo Standard |
| Database | Supabase | (env var SUPABASE_URL) | Free tier |

### Git Remote
**Single remote** — one push deploys everything:
```
origin → github.com/agentface8-hue/Alpha-Omega-System
```
`git push origin main` triggers both Render (backend) and Vercel (frontend) simultaneously.

### Render Configuration (`render.yaml`)
```yaml
services:
  - type: web
    name: alpha-omega-api
    runtime: python
    region: oregon
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: "3.12"
```

### Important: Render is NOT ephemeral at $25/mo
The $25/mo Standard plan has persistent disk. Files written at runtime survive redeploys.
However, signals/active_signals.json and portfolio state are stored in **Supabase** (not disk) for reliability.

---

## 4. COMPLETE FILE MAP

```
C:\Users\asus\Alpha-Omega-System\
│
├── MASTER-KNOWLEDGE.md          ← System bible. Read this first every session.
├── COWORK-SKILLS.md             ← Step-by-step ops guide
├── CHANGES-LOG.md               ← Session-by-session feature log
├── SIGNAL-TRACKER-V2.md         ← Deep dive on signal tracker
│
├── .env                         ← API keys (gitignored, not on Render)
├── .env.example                 ← Template
├── requirements.txt             ← Python dependencies
├── render.yaml                  ← Render deploy config
│
├── backend/
│   ├── main.py                  ← FastAPI app — ALL 80+ endpoints (2,200+ lines)
│   ├── schemas.py               ← Pydantic request/response models
│   ├── auth.py                  ← User authentication (Supabase-backed)
│   ├── dreams_ingest.py         ← Dream log ingest routes
│   ├── portfolio_routes.py      ← Portfolio API routes
│   └── printing_routes.py       ← Printing portfolio routes
│
├── core/                        ← All business logic
│   ├── signal_tracker.py        ← Signal Tracker v2.0 (79-point audit trail)
│   ├── signal_store.py          ← Supabase-first storage for signals
│   ├── portfolio_manager.py     ← Portfolio engine v1.5 (position open/close/check)
│   ├── portfolio_store.py       ← Portfolio storage (Supabase)
│   ├── conviction_engine.py     ← 5-pillar conviction scoring
│   ├── market_data.py           ← yfinance data fetching
│   ├── price_feed.py            ← Finnhub (primary) + yfinance (fallback) prices
│   ├── momentum_screener.py     ← 377-stock momentum pre-screen (2h cache)
│   ├── sector_ranker.py         ← 3-ETF sector ranking (4h cache)
│   ├── universe_builder.py      ← Full 377-stock universe by sector
│   ├── watchlists.py            ← Static watchlists and sector maps
│   ├── orchestrator.py          ← V2 LangGraph agent orchestrator
│   ├── smart_analyze.py         ← Analysis fallback chain
│   ├── learning_loop.py         ← 5-dimension learning loop
│   ├── outcomes_grader.py       ← Post-trade grader (Claude Opus)
│   ├── ai_health_agent.py       ← AI-powered health monitoring
│   ├── system_health.py         ← 9-check health system (runs IN PARALLEL)
│   ├── live_monitor.py          ← 3-level background monitor (L1=5m, L2=15m, L3=30m)
│   ├── dreaming_agent.py        ← Overnight AI market analysis
│   ├── telegram_agent.py        ← Natural language Telegram command handler
│   ├── telegram_alerts.py       ← Alert sending functions
│   ├── order_executor.py        ← IBKR TWS order execution (paper + live)
│   ├── agent_council.py         ← Signal-level multi-agent review
│   ├── advisor.py               ← Opus signal advisor
│   ├── backtester.py            ← Historical backtesting engine
│   ├── calibrator.py            ← Auto-calibrate thresholds
│   ├── trade_log.py             ← Trade logging to Airtable
│   ├── trade_journal.py         ← Trade journal
│   ├── keepalive.py             ← Render keepalive pinger
│   ├── decision_ledger.py       ← Trade decision logging
│   ├── attribution.py           ← Performance attribution
│   ├── kelly_sizer.py           ← Kelly criterion position sizing
│   ├── regime_engine.py         ← Market regime detection
│   ├── futures_data.py          ← Futures market data
│   ├── sector_ranker.py         ← Sector momentum ranking
│   └── login_tracker.py         ← Login event tracking + IP geo
│
├── agents/                      ← AI Expert Council (10 agents)
│   ├── swing_scanner.py         ← Swing Scanner v4.4 (main scanner)
│   ├── base_agent.py            ← Base class
│   ├── historian.py             ← Technical analysis (50yr patterns)
│   ├── newsroom.py              ← Sentiment (news, SEC, social)
│   ├── macro_strategist.py      ← Macro (yields, VIX, Fed)
│   ├── risk_officer.py          ← Risk assessment
│   ├── contrarian.py            ← Devil's advocate
│   ├── executioner.py           ← Final buy/sell decision
│   ├── portfolio_architect.py   ← Position sizing (Kelly)
│   ├── bear_case_advocate.py    ← Bear case analysis
│   └── regime_detector.py       ← Market regime detection
│
├── frontend/src/
│   ├── App.jsx                  ← Main app, auth, tab routing
│   └── components/
│       ├── SignalTracker.jsx     ← Signal Tracker UI
│       ├── ScanDashboard.jsx    ← Swing Scanner + sector tabs
│       ├── BacktestDashboard.jsx← Backtester UI
│       ├── Terminal.jsx         ← Council Analyze terminal
│       ├── ResultCard.jsx       ← Analysis result display
│       ├── PortfolioTab.jsx     ← Portfolio management UI
│       ├── LiveTicker.jsx       ← Top price ticker bar
│       └── TopStocks.jsx        ← Top movers widget
│
├── signals/                     ← Runtime data
│   ├── active_signals.json      ← Current open signals (Supabase primary)
│   ├── closed_signals.json      ← Closed signals (Supabase primary)
│   ├── portfolio_positions.json ← Portfolio positions (Supabase primary)
│   ├── portfolio_state.json     ← Cash/equity state
│   └── dream_log.json           ← Dream agent outputs
│
├── calibration/
│   ├── calibration_params.json  ← Auto-tuned thresholds
│   ├── momentum_screen_cache.json ← 2h momentum screener cache
│   ├── sector_rank_cache.json   ← 4h sector ranker cache
│   ├── last_portfolio_scan.json ← 4h shared scan cache
│   └── session_log.json         ← Auto-updated session history
│
└── migrations/
    └── 001_create_tables.sql    ← Supabase schema
```

---

## 5. BACKEND: ALL API ENDPOINTS

All endpoints live in `backend/main.py`. Base URL: `https://alpha-omega-system.onrender.com`

### Core Analysis
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/analyze` | Council of Experts full analysis for one ticker |
| POST | `/api/scan` | Start async scan job (returns job_id) |
| GET | `/api/scan/status/{job_id}` | Poll scan job progress |
| POST | `/api/scan/stream` | SSE streaming scan — one event per ticker |
| POST | `/api/prices` | Batch price fetch (yfinance) |
| GET | `/api/watchlists` | List all watchlists |
| GET | `/api/watchlists/{name}` | Get specific watchlist tickers |

### Sector & Universe
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/universe` | Full 377-stock universe by sector |
| GET | `/api/universe/sector/{name}` | Tickers for one sector |
| GET | `/api/sectors/ranking` | Sector momentum rankings (3-ETF, 4h cache) |
| GET | `/api/sectors/scan-universe` | Top tickers from top sectors |
| GET | `/api/sectors/momentum-screen` | Top 30 by momentum across all stocks |
| GET | `/api/sectors/heat` | Sector heat map (ETF conviction scan) |
| GET | `/api/sectors/watchlist/{key}` | Top 30 tickers for one sector (momentum ranked) |

### Backtester & Calibration
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/backtest` | Run backtest on conviction engine |
| POST | `/api/calibrate` | Auto-calibrate thresholds |
| GET | `/api/calibration` | Get current calibration params |
| POST | `/api/calibration/reset` | Reset to defaults |

### Signal Tracker (paper trading signals)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/signals` | Get all signals + stats |
| POST | `/api/signals/check` | Refresh prices, detect TP/SL hits |
| POST | `/api/signals/close/{id}` | Manual close with audit trail |
| POST | `/api/signals/clear` | Clear all signals |
| POST | `/api/signals/turbo/{symbol}` | Launch ATR-based turbo signal |
| POST | `/api/signals/override-sl/{id}` | Override stop-loss |
| POST | `/api/signals/ask-advisor/{id}` | Ask Opus about a specific signal |
| GET | `/api/signals/report/{id}` | Case report for closed signal |
| GET | `/api/signals/reports` | All case reports |
| GET | `/api/signals/regime-performance` | Performance by market regime |
| POST | `/api/signals/council/{id}` | Run agent council on active signal |
| POST | `/api/signals/replay/{id}` | Re-simulate closed signal with current logic |

### Portfolio System (separate from Signal Tracker)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/portfolio` | All positions + state + stats |
| POST | `/api/portfolio/open` | Open new position |
| POST | `/api/portfolio/close/{id}` | Close position |
| POST | `/api/portfolio/check` | Run price refresh + TP/SL check |
| GET | `/api/scan/candidates` | Top 10 bench candidates from scan cache |
| POST | `/api/autopilot` | Full autopilot: scan → rank → fill open slots |
| POST | `/api/autopilot/crypto` | Crypto autopilot |

### Analytics & Learning
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analytics/performance` | Signal tracker performance stats |
| GET | `/api/analytics/portfolio` | Portfolio analytics (Sharpe, drawdown) |
| GET | `/api/learning/summary` | Calibration params + outcomes summary |
| POST | `/api/learning/run-fast` | Trigger fast learning cycle |
| POST | `/api/learning/run-deep` | Trigger deep learning cycle (5 dimensions) |
| GET | `/api/outcomes/summary` | Post-trade grades from Opus |
| GET | `/api/trade-history` | All historical trades from Supabase trade_log |

### System Health & Monitoring
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health/full` | All 9 health checks (parallel, 16s hard cap) |
| GET | `/api/health/quick` | Fast check: Supabase + portfolio state only |
| GET | `/api/health/agent` | Last AI health agent result |
| POST | `/api/health/agent/run` | Force immediate AI health check |
| GET | `/api/monitor/status` | Live monitor state (active failures, last checks) |
| POST | `/api/monitor/run` | Trigger immediate monitor check cycle |
| GET | `/api/memory` | Render process memory usage (RAM headroom) |

### Dreams & Agents
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dreams/latest` | Last N dream log entries |
| POST | `/api/dreams/run` | Trigger dream cycle immediately |
| POST | `/api/dreams/ingest` | Receive dream from local OpenClaw agent |
| GET | `/api/agent/status` | Background thread status |
| POST | `/api/agent/learn` | Trigger learning loop manually |
| POST | `/api/agent/ping` | Manual Telegram ping (system alive check) |

### Order Executor (IBKR)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/executor/status` | Broker connection status + mode |
| POST | `/api/executor/execute/{id}` | Execute signal as live/paper order |
| POST | `/api/executor/test` | Test execution with custom payload |

### Charts & Charts Data
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/chart/{symbol}` | OHLC candles + S/R levels + signals + MTF |

### Auth & Login
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Username/password login → JWT |
| POST | `/api/auth/register` | Register new user |
| POST | `/api/login-event` | Log browser fingerprint on login |
| GET | `/api/auth/users` | List all users (owner only) |

---

## 6. CORE MODULES — BUSINESS LOGIC

### `core/price_feed.py`
Price fetching with fallback chain:
1. **Finnhub** (primary) — real-time quotes via REST API, 60 calls/min free tier
2. **yfinance** (fallback) — kicks in if Finnhub rate-limited or key missing, 6s timeout

```python
from core.price_feed import get_price
price = get_price("AAPL", asset_type="stock")   # returns float or None
price = get_price("BTC", asset_type="crypto")   # uses CURRENCY_EXCHANGE_RATE
```

### `core/conviction_engine.py`
Scores a single ticker across 5 pillars. Entry point: `score_ticker(data, regime)`.

Returns dict with: `ticker`, `conviction_pct`, `heat` (HOT/WARM/COLD), `trend`, `pillar_scores` (dict of P1–P5), `tas` (trend alignment score), `sl`, `tp1`, `tp2`, `tp3`, `rr`, `entry_low`, `entry_high`, `hard_fail` (bool).

### `core/momentum_screener.py`
Two-stage pipeline:
1. Downloads 377 stocks in chunks of 50 (memory-safe, ~40-80MB per chunk)
2. Scores: `5d_return × 0.5 + 20d_return × 0.3 + vol_surge × 0.2` + sector bias (HOT×1.15, WARM×1.00, COLD×0.90)
3. Cache: 2 hours in `calibration/momentum_screen_cache.json`

```python
from core.momentum_screener import screen_universe
results = screen_universe(top_n=30)  # returns list of dicts with ticker, score, sector
```

### `core/sector_ranker.py`
- 3-ETF averaging per sector (SPDR + iShares + Vanguard)
- Ranks all 11 GICS sectors by 5d and 20d momentum
- Returns HOT/WARM/COLD labels + rank
- Cache: 4 hours in `calibration/sector_rank_cache.json`
- Used by: autopilot (sector gate), momentum screener (bias), portfolio manager

### `core/portfolio_manager.py`
Full position lifecycle engine. Key parameters:
```
MAX_POSITIONS = 8
STARTING_CASH = $25,000
MAX_POS_SIZE  = $3,340  (12.5% of portfolio)
MIN_POS_SIZE  = $2,500
MAX_RISK      = $500 per trade
FADE_CHECKS   = 5 consecutive lower prices → auto-close
FADE_GIVEBACK = 2.0% from MFE peak → auto-close
```

Sector Momentum Gate:
- Rank 9-11 → BLOCKED entirely
- Rank 7-8 → requires conviction ≥ 78%
- Rank 1-6 → normal threshold (72%)

Dynamic TP Phase 2 scaling:
```
conviction 85%+ → TP distances ×1.50
conviction 80%  → ×1.35
conviction 75%  → ×1.20
conviction 70%  → ×1.10
conviction 65%  → ×1.00 (baseline)
below 65%       → ×0.85
```

### `core/learning_loop.py`
Runs 5-dimension analysis on closed trades:
1. Conviction calibration (which conviction ranges perform best)
2. Timing analysis (session, time-of-day patterns)
3. Regime performance (Bull/Bear/Neutral/Volatile)
4. Sector performance
5. Risk/reward optimization (SL/TP distance adjustments)

Updates `calibration/calibration_params.json`. Runs every 30 min in background.

### `core/system_health.py`
Runs 9 checks **in parallel** (fixed 2026-05-27) with 14s hard cap:
1. Supabase connectivity
2. Anthropic API (claude-haiku ping, 6s timeout)
3. Finnhub (SPY price fetch)
4. Airtable (trade log connection)
5. Telegram (bot getMe)
6. Portfolio State (cash/equity integrity)
7. Signal Tracker (active/closed counts, stale check)
8. Learning Loop (calibration file age)
9. Dream Log (last dream timestamp)

Returns GREEN/YELLOW/RED per check. Sends Telegram alert on RED.

### `core/live_monitor.py`
3-level background loops:
- **L1 (every 5 min):** Direct Python imports — backend process, portfolio data, signals, Supabase reachable
- **L2 (every 15 min):** External HTTP — Supabase signals/trade_log, prices.live, Telegram bot, Vercel frontend
- **L3 (every 30 min):** Performance HTTP — learning.summary (12s timeout), health.full (18s timeout), trade_history (12s timeout)

Alert logic: fires on first failure, then 1h cooldown. Sends recovery alerts. Tracks slow responses (>8s).

---

## 7. AI AGENTS — COUNCIL OF EXPERTS

### Models in Use
| Component | Model | Purpose |
|-----------|-------|---------|
| Council / Oracle | claude-opus-4-7 | Deep analysis, grading |
| Advisor / Dreams | claude-sonnet-4-6 | Signal advice, dream cycles |
| Morning Briefing Scan | gemini-2.0-flash | Fast batch scanning |
| Fallback | claude-haiku-4-5 | Health check pings |

### The 10 Agents (agents/)
Each extends `base_agent.py` which handles LLM calls, retries, and structured output.

| Agent | File | Role |
|-------|------|------|
| The Historian | `historian.py` | 50yr historical patterns, fractals, EMA/MACD/RSI |
| The Newsroom | `newsroom.py` | Real-time news, sentiment, SEC filings, social |
| The Macro-Strategist | `macro_strategist.py` | Yields, VIX, Fed policy, geopolitics |
| The Risk Officer | `risk_officer.py` | Risk assessment, position sizing |
| The Contrarian | `contrarian.py` | Devil's advocate, finds flaws in bull thesis |
| The Executioner | `executioner.py` | Final decision maker, Kelly sizing |
| The Portfolio Architect | `portfolio_architect.py` | Portfolio-level position sizing |
| The Bear Case Advocate | `bear_case_advocate.py` | Full bear case |
| The Regime Detector | `regime_detector.py` | Current market regime |
| Swing Scanner v4.4 | `swing_scanner.py` | Conviction scoring across watchlist |

### Agent Council (`core/agent_council.py`)
Runs a mini-council of 3 agents on a specific open signal (not full analysis). Called via `/api/signals/council/{id}`. Returns verdict (HOLD/CLOSE/ADD), bull/bear split, key factor, size guidance.

---

## 8. FRONTEND: REACT APP

**Tech:** React 18, Vite 7, Tailwind CSS, Lucide React icons. No external UI library.

### Design System (UIKit — commit f6e0caa)
```javascript
// Dark theme color palette
bg:          '#050810'    // page background
card:        '#0a0f18'    // card background  
border:      '#1a2535'    // card borders
green:       '#00ff88'    // profit, up
red:         '#ff4466'    // loss, down
purple:      '#c084fc'    // accent
blue:        '#00d4ff'    // info
yellow:      '#fbbf24'    // warning
orange:      '#f7931a'    // crypto
```

### Tabs
| Tab | Component | Key Features |
|-----|-----------|-------------|
| Council Analyze | `Terminal.jsx` + `ResultCard.jsx` | Ticker input → streaming council output, full agent report, MTF analysis |
| Swing Scan v4.4 | `ScanDashboard.jsx` | Sector tabs (momentum-ranked), scan progress, conviction heatmap, trade plans |
| Backtester | `BacktestDashboard.jsx` | Symbol/date input, historical win rate, conviction breakdown charts |
| Signal Tracker | `SignalTracker.jsx` | Live paper trading, auto-refresh 30s, turbo launcher, autopilot buttons, stats cards |
| Portfolio | `PortfolioTab.jsx` | $25K paper, position cards with pillar bars, TAS, override SL, action log, period P&L chart |
| Deep Scan | Embedded in ScanDashboard | Deep conviction scan across momentum-ranked universe |

### Authentication (`App.jsx`)
- JWT-based, stored in localStorage
- Login calls `/api/auth/login`
- Owner role gets extra features (reset buttons, user list)
- Login events tracked: IP geo, browser fingerprint, visit count → Telegram alert

### API Communication
All fetch calls go to the Render backend URL. Frontend uses `VITE_API_URL` env var.
`frontend/.env.production` sets: `VITE_API_URL=https://alpha-omega-system.onrender.com`

---

## 9. DATA STORAGE ARCHITECTURE

### Primary: Supabase
All persistent state lives in Supabase PostgreSQL. Configured via env vars.

**Tables:**
| Table | Content |
|-------|---------|
| `signals` | Active + closed paper trading signals |
| `portfolio_positions` | Open/closed portfolio positions |
| `portfolio_state` | Cash, equity, drawdown state |
| `trade_log` | Full historical trade log (84+ trades) |
| `outcomes` | Post-trade AI grades from Opus |
| `dream_log` | Dream agent outputs |
| `login_events` | Login tracking with IP/browser data |
| `users` | Auth users |

### Fallback: Local JSON Files
If Supabase is down or not configured, falls back to JSON files in `signals/`:
- `signals/active_signals.json`
- `signals/closed_signals.json`
- `signals/portfolio_positions.json`
- `signals/portfolio_state.json`

### `core/signal_store.py` — Storage Abstraction
```python
from core import signal_store as store

active   = store.load_active()     # List of active signal dicts
closed   = store.load_closed()     # List of closed signal dicts
store.save_active(active)          # Write back
store.save_closed(closed)

# Supabase check:
if store._sb():
    # use Supabase
else:
    # use JSON fallback
```

### Caches (calibration/ directory)
| File | TTL | Content |
|------|-----|---------|
| `momentum_screen_cache.json` | 2h | 377-stock momentum scores |
| `sector_rank_cache.json` | 4h | Sector momentum rankings |
| `last_portfolio_scan.json` | 4h | Conviction scan results (shared with /api/scan/candidates) |
| `calibration_params.json` | Updated by learning loop | Tuned conviction thresholds |

### Airtable
Trade logging backup. Base: `appffQglWsLcswQMt`, table: `tblN7UWpYuaSVJnMf`.
71 trades loaded. Used as secondary trade record alongside Supabase.

---

## 10. INTEGRATIONS & API KEYS

All keys set in Render dashboard environment variables (NOT read from .env in production).

| Key | Service | Usage |
|-----|---------|-------|
| `GOOGLE_API_KEY` | Gemini 2.0 Flash | Morning briefing scan agents |
| `ANTHROPIC_API_KEY` | Claude API | Council, Advisor, Dreams, Grader |
| `SUPABASE_URL` | Supabase | Primary database URL |
| `SUPABASE_ANON_KEY` | Supabase | Auth key for REST API |
| `TELEGRAM_TOKEN` | @AlphaOmegaCEO_bot | All alerts and commands |
| `TELEGRAM_PERSONAL_CHAT_ID` | Telegram | Avi's personal chat ID |
| `TELEGRAM_GROUP_CHAT_ID` | Telegram | Group chat (if applicable) |
| `FINNHUB_API_KEY` | Finnhub | Live stock prices (primary) |
| `ALPHA_VANTAGE_API_KEY` | Alpha Vantage | Health check ping only (YELLOW, non-critical) |
| `AIRTABLE_API_KEY` | Airtable | Trade log backup |
| `OWNER_PASSWORD` | Auth system | Seed owner account on startup |
| `GITHUB_TOKEN` | GitHub | Session memory auto-commit |

### Price Feed Logic
```python
# core/price_feed.py — get_price() implementation:
# 1. Try Finnhub (60 calls/min free tier)
#    → stocks: /quote?symbol=X&token=KEY
#    → crypto: /quote?symbol=BINANCE:BTCUSDT&token=KEY
# 2. On failure/rate-limit → yfinance fallback (6s timeout)
# 3. Returns float price or None
```

---

## 11. BACKGROUND SERVICES & SCHEDULED TASKS

### Startup Services (launched in `startup_all()` in main.py)
1. **Owner account seed** — creates Avi's account if not exists
2. **Keepalive pinger** (`core/keepalive.py`) — pings Render to prevent sleep
3. **Live monitor** (`core/live_monitor.py`) — L1/L2/L3 health loops
4. **Telegram agent** (`core/telegram_agent.py`) — polls for commands
5. **Learning loop** (`core/learning_loop.py`) — background calibration
6. **AI Health Agent** (`core/ai_health_agent.py`) — AI-powered health checks (24h cooldown per fix)

### Scheduled Tasks (Render Cron)
| Task | Schedule | What it does |
|------|----------|-------------|
| Morning Briefing | 9 AM ET weekdays | Gemini scan, top picks, Telegram + email |
| Market Check | Every 30m, 3-10 PM UTC weekdays | Portfolio price refresh, TP/SL checks |
| Weekly Calibration | Sundays 6 PM UTC | Deep learning cycle, threshold updates |
| Daily Summary | 5 PM Cyprus weekdays | P&L summary via Gmail + Telegram |
| Health Check | 7 AM Cyprus weekdays | Full 9-check health run, Telegram report |

---

## 12. SIGNAL TRACKER VS PORTFOLIO — CRITICAL DISTINCTION

**These are TWO completely independent systems. Do NOT mix them up.**

| Dimension | Signal Tracker | Portfolio |
|-----------|---------------|-----------|
| Core module | `core/signal_tracker.py` | `core/portfolio_manager.py` |
| Storage module | `core/signal_store.py` | `core/portfolio_store.py` |
| API routes | `/api/signals/*` | `/api/portfolio/*` |
| Purpose | Paper-trade signals, audit trail | Position management, P&L |
| Created by | `create_turbo_signal()` or autopilot | `open_position()` manually |
| Position size | ATR-based targets only | Shares + dollar amounts |
| Unique features | 79-point entry snapshot, case reports, MAE/MFE | Sector gate, dynamic TP, momentum fade auto-close |

**Key rule:** Portfolio positions do NOT inherit Signal Tracker fields automatically. Pass them explicitly:
```python
# CORRECT
open_position(
    ticker, entry, sl, tp1, tp2, tp3, conviction,
    pillar_scores=scan_data.get("pillar_scores", {}),
    tas=scan_data.get("tas", ""),
    entry_market_context=market_ctx
)
```

---

## 13. CONVICTION ENGINE — 5-PILLAR SYSTEM

Scoring in `core/conviction_engine.py`. Each pillar 0–100, weighted equally (20% each).

| Pillar | What it measures | Key indicators |
|--------|-----------------|----------------|
| P1: Trend/Momentum | Price direction + strength | EMA 9/21/50 alignment, RSI (40-70 zone), MACD histogram |
| P2: Volume Profile | Institutional activity | Volume ratio vs 20d avg, accumulation/distribution, on-balance volume |
| P3: Support/Resistance | Position in range | Fibonacci levels, supply/demand zones, distance from S/R |
| P4: Multi-Timeframe | Cross-timeframe agreement | 65m, 240m, 1D, 1W alignment (TAS = timeframes agreeing / total) |
| P5: Risk/Reward | Trade viability | ATR-based R:R, position in daily range, SL distance from noise |

**Conviction thresholds:**
- ≥ 72% → HOT — portfolio autopilot threshold (data-driven, was 60% initially)
- 60-71% → WARM — manual review only
- < 60% → COLD — skip

**Volume gate (added 2026-05-25):**
- vol_ratio < 1.0x → BLOCKED (win rate 46% on 74-trade analysis)
- vol_ratio 1.0-1.3x → P3 score set to 52 (was 35)

**Regime adjustments:**
VIX > 25 (Volatile regime) → min R:R raised to 2.0:1
VIX 18-25 (Neutral) → min R:R 1.5:1
VIX < 18 (Bull) → min R:R 1.5:1

---

## 14. PORTFOLIO SYSTEM — POSITION LIFECYCLE

### Open Position Flow
```
autopilot_fill() or manual API call
    ↓
sector_gate check (rank 9-11 → block, 7-8 → need 78% conviction)
    ↓
_dtp_scale(conviction) → TP multiplier (0.85x to 1.50x)
    ↓
_size_position(entry, sl) → shares, risk, TP split sizes
    ↓
store.save_position() → Supabase
    ↓
Telegram alert: "📈 POSITION OPENED — AAPL"
```

### Check Positions Loop (every 30m via Render cron)
```
check_portfolio()  [uses threading.Lock to prevent concurrent runs]
    ↓
For each open position:
    price = _live_price(ticker)  [Finnhub → yfinance fallback]
    
    If price ≤ SL → STOPPED_OUT, close position, alert
    If price ≥ TP1 and not tp1_hit → record TP1 hit, sell tp1_shares
    If price ≥ TP2 and not tp2_hit → record TP2 hit, sell tp2_shares
    If price ≥ TP3 → FULL CLOSE, alert
    
    Trailing SL: after TP1, TSL = max(TSL, price - ATR×1.5)
    
    Momentum fade check: if consecutive_lower ≥ 5 AND
                         price fell ≥ 2% from MFE peak → AUTO-CLOSE
    ↓
Update state (cash, equity)
Alert Telegram on any change
```

### State Tracking
- `portfolio_state.json` / Supabase `portfolio_state` table
- Fields: `cash`, `total_value`, `unrealized_pnl`, `realized_pnl`, `max_drawdown`, `peak_value`, `positions_opened`, `positions_closed`

### Dynamic TP Phase 2
At position open time, conviction score scales all TP distances:
```python
conviction 85% → all TPs 50% further from entry
conviction 80% → 35% further
conviction 75% → 20% further
conviction 70% → 10% further  
conviction 65% → baseline (1.0x)
below 65%      → 15% tighter
```
TP3 can be extended up to 3 times if price keeps running (MAX_TP3_EXTENSIONS = 3).

---

## 15. HEALTH MONITOR ARCHITECTURE

### Why It Was Broken (Fixed 2026-05-27)
`system_health.py` ran 9 checks sequentially. Anthropic API alone had 15s timeout. Worst case: 80+ seconds total. Monitor expected 30s response → timeout cascade took down learning.summary and trade_history with it.

### Current Architecture (parallel)
```python
# system_health.py — run_full_check()
with concurrent.futures.ThreadPoolExecutor(max_workers=9) as ex:
    futures = [(ex.submit(_safe_run, name, fn), name) for name, fn in ALL_CHECKS]
    done, not_done = concurrent.futures.wait(futures, timeout=14)
    # timed-out checks → YELLOW (not RED, not blocking)
```

### Endpoint Hard Caps
```python
# backend/main.py
GET /api/health/full        → asyncio.wait_for(..., timeout=16.0)
GET /api/learning/summary   → asyncio.wait_for(..., timeout=10.0)
GET /api/trade-history      → asyncio.wait_for(..., timeout=10.0)
```

### Monitor Timeouts (live_monitor.py)
```python
CHECKS_L3 = [
    ("learning.summary", lambda: _get("/api/learning/summary", timeout=12), False),
    ("health.full",      lambda: _get("/api/health/full",      timeout=18), False),
    ("trade_history",    lambda: _get("/api/trade-history",    timeout=12), False),
]
```

---

## 16. CURRENT SYSTEM STATE & KNOWN ISSUES

### Features Live and Working (as of 2026-05-27)
| Feature | Status | Notes |
|---------|--------|-------|
| Council of Experts (10 agents) | ✅ Live | Opus 4.7 |
| Swing Scanner v4.4 + Momentum Screener | ✅ Live | 377 stocks → top 30 |
| Signal Tracker v2.0 | ✅ Live | 79-point audit trail |
| Portfolio Tab ($25K, 8 positions) | ✅ Live | Dynamic TP, sector gate |
| Dynamic TP Phase 2 | ✅ Live | Conviction-scaled TP distances |
| Dreaming Agent | ✅ Live | Claude Sonnet 4.6 |
| Dream Log tab | ✅ Live | Supabase storage |
| Telegram bot (@AlphaOmegaCEO_bot) | ✅ Live | Full alerts: open/TP/SL/close/health |
| Airtable trade log | ✅ Live | 71 trades |
| Daily 5PM summary | ✅ Live | Gmail + Telegram |
| Learning Loop v2.0 | ✅ Live | 5-dimension analysis |
| System Health Monitor | ✅ Fixed | 9 parallel checks (fixed 2026-05-27) |
| 3-ETF Sector Ranker | ✅ Live | SPDR + iShares + Vanguard |
| Volume gate | ✅ Live | vol<1.0x blocked |
| Order Executor (IBKR) | ✅ Built | Awaiting IBKR account approval |
| Trade history tab | ✅ Live | 84+ trades from Supabase |
| Portfolio chart (period P&L) | ✅ Live | Chart component in Portfolio tab |
| Mobile responsive layout | ✅ Live | |

### Known Issues / TODO
- [ ] IBKR account approval → set `EXECUTOR_MODE=ibkr` + `IBKR_HOST` + `IBKR_PORT` in Render
- [ ] `_inject_health_task.py` needs to run after Render restart (scheduled task registration)
- [ ] Chart screenshots in case reports (matplotlib at entry/exit) — not built yet
- [ ] Portfolio-level analytics (correlation matrix, sector exposure, drawdown by regime) — partial
- [ ] Historical signal replay — built but not wired to UI
- [ ] EXIT state in Dynamic TP Phase 2 — conviction rescan runs observe-only badges (RUNNING/DEVELOPING/PROTECTING/EXIT), auto-close on EXIT not fully wired

### Recent Commits (latest first)
```
9ec7893  fix_parallel_health_checks (2026-05-27)
1042109  auto: session memory 2026-05-26 19:00
528a17d  auto: session memory 2026-05-25 19:00
fix      L2/L3 monitor checks always use public URL
fix      L1 checks use direct Python imports (no HTTP self-call)
feat     live_monitor.py — 3-level check loops
fix      portfolio autopilot dynamic threshold
feat     trade history endpoint + Portfolio history tab
feat     volume gate (74-trade analysis)
```

---

## 17. DEPLOY WORKFLOW

### Standard Deploy (backend + frontend)
```bash
cd C:\Users\asus\Alpha-Omega-System

# If JSX/CSS changed:
cd frontend
npx vite build
cd ..
git add frontend/src/

# Always:
git add -A
git commit -m "description"
git push origin main    # triggers BOTH Render + Vercel
```

### Local Development
```bash
# Backend (terminal 1)
cd C:\Users\asus\Alpha-Omega-System
python -m uvicorn backend.main:app --reload --port 8000

# Frontend (terminal 2)
cd C:\Users\asus\Alpha-Omega-System\frontend
npm run dev
# → http://localhost:5173 (proxies API to localhost:8000)
```

### Quick Smoke Tests
```bash
cd C:\Users\asus\Alpha-Omega-System

# Backend loads?
python -c "from backend.main import app; print('FastAPI OK')"

# Signal tracker works?
python -c "from core.signal_tracker import check_signals; print('Signal Tracker OK')"

# Portfolio manager works?
python -c "from core.portfolio_manager import check_portfolio; print('Portfolio OK')"

# Health check (full system):
curl https://alpha-omega-system.onrender.com/api/health/full
```

### Verify Deploy
```bash
# Backend:
curl https://alpha-omega-system.onrender.com/health

# Frontend:
# https://alpha-omega-ngfw.vercel.app
```

---

## 18. TECH STACK SUMMARY

### Backend
| Technology | Version | Role |
|-----------|---------|------|
| Python | 3.12 | Runtime |
| FastAPI | latest | Web framework |
| Uvicorn | latest | ASGI server |
| yfinance | latest | Market data (fallback prices, historical OHLC) |
| Finnhub | REST API | Real-time prices (primary) |
| LangChain | latest | Agent framework |
| LangGraph | latest | Agent orchestration |
| langchain-google-genai | latest | Gemini 2.0 Flash |
| langchain-anthropic | latest | Claude API |
| anthropic | latest | Direct Claude API calls |
| supabase | latest | Database client |
| pandas + numpy | latest | Data processing |
| psutil | latest | Memory monitoring |
| pytz | latest | Timezone handling |
| python-dotenv | latest | Environment variables |

### Frontend
| Technology | Version | Role |
|-----------|---------|------|
| React | 18 | UI framework |
| Vite | 7 | Build tool + dev server |
| Tailwind CSS | 3 | Utility styling |
| Lucide React | 0.383.0 | Icons |
| recharts | - | Charts (portfolio P&L) |

### Infrastructure
| Service | Purpose | Cost |
|---------|---------|------|
| Render | Backend hosting | $25/mo |
| Vercel | Frontend hosting | Free |
| Supabase | PostgreSQL database | Free |
| GitHub | Code + CI/CD | Free |
| Finnhub | Live prices | Free (60 req/min) |
| Airtable | Trade log backup | Free |
| Telegram | Alerts + commands | Free |

---

## 19. CRITICAL RULES FOR WORKING ON THIS CODEBASE

### Rule 1: Supabase is primary, JSON is fallback
Never write directly to signal JSON files assuming that's the only storage. Always go through `signal_store.py` or `portfolio_store.py` — they handle Supabase-first with JSON fallback.

### Rule 2: Signal Tracker ≠ Portfolio
These are separate systems. Don't add signal tracker fields to portfolio code or vice versa. `/api/signals/*` → `core/signal_tracker.py` + `core/signal_store.py`. `/api/portfolio/*` → `core/portfolio_manager.py` + `core/portfolio_store.py`.

### Rule 3: Don't block the FastAPI event loop
All blocking I/O (HTTP calls, file reads, yfinance) must be wrapped in `asyncio.run_in_executor()` with a timeout. Blocking the event loop starves all other requests. See the fixed `/api/health/full` endpoint as the reference pattern:
```python
loop = asyncio.get_event_loop()
with concurrent.futures.ThreadPoolExecutor() as ex:
    result = await asyncio.wait_for(loop.run_in_executor(ex, sync_fn), timeout=16.0)
```

### Rule 4: Memory on Render Standard tier = 2GB
The momentum screener processes 377 stocks in chunks of 50 with `gc.collect()` between chunks. Never try to download all 377 tickers at once. Each chunk uses ~40-80MB.

### Rule 5: One git remote, one push
```
git push origin main
```
This deploys BOTH Render (backend) and Vercel (frontend). There are no separate remotes.

### Rule 6: All API keys are in Render dashboard
`.env` is for local dev only (gitignored). Production reads from Render environment variables. If a key is missing in production, it's missing from the Render dashboard — not from `.env`.

### Rule 7: Port is dynamic on Render
```python
startCommand: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```
Never hardcode port 8000 in Render-facing code. `$PORT` is set by Render.

### Rule 8: Health checks run in parallel now (post-2026-05-27 fix)
`system_health.py → run_full_check()` runs all 9 checks in parallel with a 14s total cap. The old sequential version caused cascading timeouts. Don't revert this to sequential.

### Rule 9: The conviction threshold is 72%, not 60%
Based on 74-trade analysis, 55-65% signals performed poorly. Autopilot threshold is 72%. `SECTOR_WARN_CONVICTION = 78%` for weak-sector positions.

### Rule 10: Frontend API URL
The frontend reads `VITE_API_URL` from `frontend/.env.production`. It's set to `https://alpha-omega-system.onrender.com`. Don't hardcode the URL anywhere in React components — always use `import.meta.env.VITE_API_URL`.

---

*End of PRD — last updated 2026-05-27 by Claude Sonnet 4.6*
*All information verified directly from source files in C:\Users\asus\Alpha-Omega-System*
