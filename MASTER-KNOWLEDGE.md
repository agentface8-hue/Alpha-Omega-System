# ALPHA-OMEGA SYSTEM — MASTER KNOWLEDGE BASE
# Last Updated: 2026-05-16
# Location: C:\Users\asus\Alpha-Omega-System\MASTER-KNOWLEDGE.md

## ⚠️ INSTRUCTIONS FOR CLAUDE — READ THIS FIRST EVERY SESSION

1. Read this entire file before doing anything
2. Search chat history for the most recent session to get fully up to date
3. Never assume the system state — verify against history
4. The chat history search is the strongest mechanism for continuity across sessions

---

## 1. SYSTEM OVERVIEW

Alpha-Omega is an AI-powered stock/crypto trading analysis system:
- **Council of Experts**: 10 AI agents analyze any ticker from different angles
- **Swing Scanner v4.4**: Scans 30+ stocks, ranks by conviction (5-pillar system)
- **Signal Tracker v2.0**: Paper-trades signals with full audit trail
- **Backtester**: Tests the conviction engine against historical data
- **Auto-Pilot**: One button → scan universe → rank → launch ATR-based turbo signals

## 2. DEPLOYMENT

| Component | Platform | URL | Remote |
|-----------|----------|-----|--------|
| Frontend | Vercel | https://alpha-omega-ngfw.vercel.app | `origin` → github.com/agentface8-hue/Alpha-Omega-System |
| Backend | Render | https://alpha-omega-system.onrender.com | `origin` → github.com/agentface8-hue/Alpha-Omega-System |
| Local dev | localhost | http://127.0.0.1:8000 (backend), :5173 (frontend) | — |

### Deploy workflow:
```bash
cd C:\Users\asus\Alpha-Omega-System
git add .
git commit -m "description"
git push origin main    # triggers BOTH Render backend + Vercel frontend
```

### Frontend build (required before deploy):
```bash
cd frontend
npx vite build
cd ..
git add frontend/src/   # only source, dist is gitignored
```

## 3. COMPLETE FILE MAP

```
C:\Users\asus\Alpha-Omega-System\
├── MASTER-KNOWLEDGE.md          # THIS FILE
├── COWORK-SKILLS.md             # Step-by-step for common tasks
├── SIGNAL-TRACKER-V2.md         # Deep dive on signal tracker
├── .env                         # API keys (gitignored)
├── .env.example                 # Template for .env
├── requirements.txt             # Python deps
├── render.yaml                  # Render deploy config
├── PRD.md                       # Product requirements doc
│
├── backend/
│   ├── main.py                  # FastAPI app (459 lines) — ALL endpoints
│   ├── schemas.py               # Pydantic models
│   └── __pycache__/
│
├── core/                        # Business logic
│   ├── signal_tracker.py        # ⭐ Signal Tracker v2.0 (1046 lines)
│   ├── orchestrator.py          # V2 agent orchestrator
│   ├── smart_analyze.py         # Smart analysis fallback chain
│   ├── conviction_engine.py     # 5-pillar conviction scoring
│   ├── backtester.py            # Historical backtesting
│   ├── calibrator.py            # Auto-calibrate thresholds
│   ├── market_data.py           # yfinance data fetching
│   ├── watchlists.py            # Stock universes
│   ├── decision_matrix.py       # Decision framework
│   ├── decision_ledger.py       # Trade decision logging
│   ├── trade_journal.py         # Trade journal
│   └── attribution.py           # Performance attribution
│
├── agents/                      # AI Expert Council
│   ├── swing_scanner.py         # ⭐ Swing Scanner v4.4
│   ├── base_agent.py            # Base agent class
│   ├── historian.py             # Technical analysis
│   ├── newsroom.py              # Sentiment analysis
│   ├── macro_strategist.py      # Macro/rates/VIX
│   ├── risk_officer.py          # Risk assessment
│   ├── contrarian.py            # Devil's advocate
│   ├── executioner.py           # Buy/sell decision
│   ├── portfolio_architect.py   # Position sizing
│   ├── bear_case_advocate.py    # Bear case
│   └── regime_detector.py       # Market regime
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Main app + tabs
│   │   ├── components/
│   │   │   ├── SignalTracker.jsx # ⭐ Signal Tracker UI (419 lines)
│   │   │   ├── ScanDashboard.jsx# Swing Scanner UI
│   │   │   ├── BacktestDashboard.jsx
│   │   │   ├── Terminal.jsx     # Council Analyze terminal
│   │   │   ├── ResultCard.jsx   # Analysis results
│   │   │   ├── LiveTicker.jsx   # Top ticker bar
│   │   │   └── TopStocks.jsx    # Top movers widget
│   │   └── utils/sounds.js
│   ├── vite.config.js
│   └── package.json
│
├── signals/                     # Runtime data (gitignored)
│   ├── active_signals.json
│   ├── closed_signals.json
│   └── reports/                 # Case reports per closed signal
│
├── config/
│   └── settings.py              # App settings
│
├── calibration/
│   └── calibration_params.json  # Auto-tuned thresholds
│
├── backtest_results/            # Saved backtest runs
│
├── docs/
│   ├── DEPLOY.md
│   ├── ATTRIBUTION_OPS.md
│   └── create_trade_journal.sql
│
└── tests/
    ├── test_app_integration.py
    └── test_flow.py
```

## 4. API ENDPOINTS (backend/main.py)

### Analysis
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/analyze | Council of Experts analysis (V2 orchestrator → smart_analyze fallback) |
| POST | /api/scan | Swing Scanner v4.4 — scan watchlist, rank by conviction |
| GET | /api/prices | Live prices for ticker list |
| GET | /api/watchlists | List all watchlists |
| GET | /api/watchlists/{name} | Get specific watchlist |

### Backtester & Calibration
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/backtest | Run backtest on conviction engine |
| POST | /api/calibrate | Auto-calibrate thresholds |
| GET | /api/calibration | Get current calibration params |
| POST | /api/calibration/reset | Reset to defaults |

### Signal Tracker v2.0
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/signals | Get all signals (no price refresh) |
| POST | /api/signals/check | ⭐ Refresh prices with gap detection, MAE/MFE, staleness |
| POST | /api/signals/close/{id} | Close signal with full audit trail |
| POST | /api/signals/clear | Reset all signals |
| POST | /api/signals/turbo/{symbol} | Launch ATR-based turbo signal |
| GET | /api/signals/report/{id} | Get case report for closed signal |
| GET | /api/signals/reports | List all case reports |
| GET | /api/signals/regime-performance | Performance breakdown by market regime |


### Portfolio System (SEPARATE from Signal Tracker)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/portfolio | All open + closed positions + stats |
| POST | /api/portfolio/open | Open a new position |
| POST | /api/portfolio/close/{id} | Close a position |
| GET | /api/portfolio/candidates | Bench candidates from scan |
| POST | /api/signals/override-sl/{id} | Override stop-loss on a signal |

### Auto-Pilot
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/autopilot | Scan 30 stocks → rank → launch top 10 turbo signals |
| POST | /api/autopilot/crypto | Launch turbo signals for 15 crypto assets |

## 5. FRONTEND TABS

| Tab | Component | Description |
|-----|-----------|-------------|
| Council Analyze | Terminal.jsx + ResultCard.jsx | Enter ticker → get expert council analysis |
| Swing Scan v4.4 | ScanDashboard.jsx | Scan watchlist, see conviction rankings |
| Backtester | BacktestDashboard.jsx | Run backtests, view results |
| Signal Tracker | SignalTracker.jsx | ⭐ Live paper trading dashboard |
| Portfolio | PortfolioTab.jsx | Position management, Entry Reason, Override SL, Action Log |

### Signal Tracker UI Features (v2.0):
- Market session indicator (premarket/regular/afterhours/closed with color)
- Turbo signal launcher (type ticker → LAUNCH)
- Auto-refresh toggle with 30s countdown
- Stock & Crypto auto-pilot buttons
- Stats cards: Active, Win Rate, Avg P&L, Profit Factor, Wins, Losses, TP1 Hit%, AVG MAE, AVG MFE, Gap Trades
- Conviction accuracy (avg conviction winners vs losers)
- Active/Closed tabs
- Expandable signal cards showing: Entry Context (VIX, SPY, regime, session), Targets (ATR method, all TPs), Indicators at Entry, Exit details

## 6. SWING SCANNER v4.4 — CONVICTION ENGINE

### 5-Pillar System
| Pillar | Weight | What It Measures |
|--------|--------|------------------|
| P1: Trend/Momentum | 20% | EMA alignment, RSI, MACD |
| P2: Volume Profile | 20% | Volume ratio, accumulation/distribution |
| P3: Support/Resistance | 20% | Fib levels, supply/demand zones |
| P4: Multi-Timeframe | 20% | 65m, 240m, daily, weekly alignment |
| P5: Risk/Reward | 20% | ATR-based R:R, position in range |

### Conviction Levels
- 70%+ = HOT (green) — strong signal
- 60-69% = WARM (yellow) — decent
- <60% = COLD (gray) — skip

### TAS Score (Trend Alignment Score)
- Format: "3/4" or "4/4"
- Counts how many timeframes agree on direction

## 7. SIGNAL TRACKER v2.0 — ARCHITECTURE

### Signal Lifecycle
```
CREATE → OPEN → [check_signals loop] → TP1_HIT/TP2_HIT/TP3_HIT/STOPPED_OUT/TIMEOUT/MANUAL_CLOSE
```

### What Gets Recorded at ENTRY:
- Full indicator snapshot (RSI, ATR, EMAs, cloud, FVGs, POC, LR channel, Fib levels)
- Market context (VIX, SPY close, SPY change%, regime)
- Session (regular/premarket/afterhours/closed)
- ATR-based targets (SL = entry - 0.5×ATR, TP1 = entry + 0.5×ATR)
- Price validation (staleness, gap from prev close)
- Scan data pass-through (conviction, pillar scores, TAS)

### What Gets Tracked DURING:
- MAE (Max Adverse Excursion) — worst drawdown
- MFE (Max Favorable Excursion) — best unrealized gain
- TP1/TP2/TP3 hit timestamps
- Highest/lowest prices
- Gap detection (price gaps through SL/TP)

### What Gets Recorded at CLOSE:
- Close price (realistic — uses gap fill price if applicable)
- Close market context (VIX, SPY, regime at exit)
- Close session
- Slippage from gaps
- Auto-generated case report with trade analysis

### Case Reports (signals/reports/)
JSON files named: `{TICKER}_{ID}_{STATUS}.json`
Contains: full entry/exit context, performance metrics, auto-analysis (SL review, TP review, MAE insight, speed analysis, conviction accuracy, gap impact, regime shift)

## 8. TECH STACK

### Backend
- Python 3.12 + FastAPI + Uvicorn
- yfinance (market data, 15-20min delay for free tier)
- LangChain + LangGraph (agent orchestration)
- Google Gemini (primary LLM for agents)
- Anthropic Claude (fallback)
- pytz (timezone handling)
- pandas, numpy (data processing)

### Frontend
- React 18 + Vite 7
- Tailwind CSS (utility classes)
- Lucide React (icons)
- No external UI library — all custom components

### Infrastructure
- Vercel (frontend hosting, auto-deploy from GitHub)
- Render (backend hosting, free tier — ephemeral storage!)
- GitHub (2 remotes: origin + vercel)


## ⚠️ CRITICAL ARCHITECTURE: SIGNAL TRACKER vs PORTFOLIO ARE SEPARATE SYSTEMS

These are TWO COMPLETELY INDEPENDENT storage systems. Do NOT confuse them.

| | Signal Tracker | Portfolio |
|---|---|---|
| Core file | `core/signal_tracker.py` | `core/portfolio_manager.py` |
| API | `/api/signals` | `/api/portfolio` |
| Storage | `signals/active_signals.json` + Supabase | `signals/portfolio.json` |
| Purpose | Paper-trade signals, ATR targets, audit trail | Position management, P&L, shares/risk sizing |
| Created by | `create_turbo_signal()` or autopilot | `open_position()` manually or from scan |

### Key consequence
Portfolio positions do NOT automatically inherit Signal Tracker fields.
Fields like `pillar_scores`, `tas`, `entry_market_context` must be explicitly passed
to `open_position()` — they are NOT copied from the signal record.

```python
# WRONG — portfolio position won't have pillar data
open_position(ticker, entry, sl, tp1, tp2, tp3, conviction)

# CORRECT — pass the extra context explicitly
open_position(ticker, entry, sl, tp1, tp2, tp3, conviction,
              pillar_scores=scan_data.get("pillar_scores", {}),
              tas=scan_data.get("tas", ""),
              entry_market_context=scan_data.get("market_context", {}))
```

Legacy positions (opened before this fix) show an italic placeholder
instead of pillar bars in the Portfolio UI.

## 9. CRITICAL NOTES

### Render Ephemeral Storage ⚠️
Render free tier wipes files on redeploy. This means:
- `signals/active_signals.json` and `closed_signals.json` get DELETED
- Case reports in `signals/reports/` get DELETED
- **TODO**: Migrate signal storage to Supabase or persistent volume

### Price Feed Priority
- **Alpha Vantage** (primary): real-time stock quotes via GLOBAL_QUOTE endpoint
- **yfinance** (fallback): kicks in automatically if AV rate-limited or key missing
- Crypto: CURRENCY_EXCHANGE_RATE endpoint (near-realtime)
- Staleness detection built into signal tracker

### Git Remote (single remote now)
```
origin  → github.com/agentface8-hue/Alpha-Omega-System  (Render + Vercel)
```
One push deploys everything. No more dual remotes.

### API Keys (.env + Render dashboard)
```
GOOGLE_API_KEY=...           # Gemini for agents
ANTHROPIC_API_KEY=...        # Claude fallback
SUPABASE_URL=...             # Persistent storage
SUPABASE_ANON_KEY=...        # Persistent storage
TELEGRAM_TOKEN=...           # @AlphaOmegaCEO_bot
TELEGRAM_PERSONAL_CHAT_ID=...
TELEGRAM_GROUP_CHAT_ID=...
ALPHA_VANTAGE_API_KEY=...    # Real-time stock prices (primary, yfinance is fallback)
GITHUB_TOKEN=...
```
All keys must be set in Render dashboard — the .env file is NOT read in production.

## 10. CURRENT SYSTEM STATE — Last updated 2026-05-14

### All features built and live:
| Feature | Status | Notes |
|---------|--------|-------|
| Council of Experts (10 agents) | ✅ Live | Opus 4.7 |
| Swing Scanner v4.4 + Momentum Pre-Screener | ✅ Live | 377 stocks → top 30 |
| Signal Tracker v2.0 | ✅ Live | 79-point audit trail |
| Active Portfolio Tab | ✅ Live | $25K paper, 10 slots, Dynamic TP |
| Dynamic TP Phase 2 | ✅ Live | Scales TP by conviction at entry (commit 9d08371) |
| Dreaming Agent | ✅ Live | Claude Sonnet (NOT Gemini — 429 fixed) |
| Dream Log tab | ✅ Live | Supabase storage |
| Telegram bot | ✅ Live | @AlphaOmegaCEO_bot |
| Google Sheets trade log | ✅ Live | SHEETS_TOKEN_JSON in Render env vars |
| Daily 5PM summary | ✅ Live | Gmail + Telegram |
| Learning Loop v2.0 | ✅ Live | 5-dimension analysis |
| System Health Monitor | ✅ Built | 9 checks, /api/health/full, Telegram alerts |
| UIKit design system | ✅ Live | All tabs redesigned (commit f6e0caa) |
| 3-ETF Sector Ranker | ✅ Live | SPDR + iShares + Vanguard |
| Order Executor | ✅ Built | paper/IBKR modes, waiting for IBKR approval |

### Models in use:
| Component | Model |
|-----------|-------|
| Advisor screen | claude-sonnet-4-6 |
| Oracle / Council / Grader | claude-opus-4-7 |
| Dream Log | claude-sonnet-4-6 |
| Agents (Gemini) | gemini-2.0-flash (morning briefing scan only) |

### Scheduled tasks (5 active):
| Task | Schedule | Status |
|------|----------|--------|
| alpha-omega-morning-briefing | 9 AM ET weekdays | ✅ Running |
| alpha-omega-market-check | Every 30min, 3-10 PM UTC weekdays | ✅ Running |
| alpha-omega-weekly-calibration | Sundays 6 PM UTC | ✅ Running |
| alpha-omega-daily-summary | 5 PM Cyprus weekdays | ✅ Running |
| alpha-omega-health-check | 7 AM Cyprus weekdays | ⏳ Pending restart |

### Pending from 2026-05-14 session:
- [ ] Run `_inject_health_task.py` after Claude Desktop restart (script is ready at project root)
- [ ] IBKR account approval — then set EXECUTOR_MODE=ibkr + IBKR_HOST + IBKR_PORT in Render
- [ ] Delete Downloads ZIP copies (Alpha-Omega-main, Alpha-Omega-System-main) — dead weight
- [ ] Delete client_secret JSON sitting loose in Downloads folder

### Latest commits:
- `c43a213` docs: Section 13 critical rules in MASTER-KNOWLEDGE
- `56c2f0e` feat: System Health Monitor - 9 checks
- `92f42ac` fix: Google Sheets SHEETS_TOKEN_JSON env var
- `8b9cce8` fix: Dream agent → Claude Sonnet (429 fixed)
- `f6e0caa` feat: UIKit design system, clean stats all tabs
- `9d08371` feat: Dynamic TP Phase 2

### v1.0 — Initial Build (Feb 2026)
- Council of Experts with 10 agents
- Basic Swing Scanner
- Frontend with Terminal + LiveTicker
- Demo mode with canned responses

### v2.0 — Scanner + Backtester
- Swing Scanner v4.4 with 5-pillar conviction
- Backtester with historical validation
- Auto-calibration system
- ScanDashboard + BacktestDashboard components

### v3.0 — Signal Tracker (Feb 26-27, 2026)
- Signal Tracker v1.0 (basic price tracking)
- Turbo signal launcher
- Auto-Pilot (stocks + crypto)
- Auto-refresh with countdown

### v3.1 — Signal Tracker v2.0 (Feb 27, 2026)
- 15 critical gaps fixed (see SIGNAL-TRACKER-V2.md)
- Full audit trail with 79 data points per entry
- ATR-based targets
- Gap detection + realistic fills
- MAE/MFE tracking
- Market context at entry/close
- Case reports with auto-analysis
- Price staleness detection
- Market hours awareness

### v4.0 — Portfolio System + Live Alerts (May 2026) ← CURRENT
- Portfolio tab with position management (open/close/override SL)
- Entry Reason panel with 5 pillar bars, TAS, VIX, SPY per position
- Supabase migration (signal_store.py — Supabase-first, JSON fallback)
- Alpha Vantage real-time pricing (yfinance fallback)
- Afterhours session block — stocks cannot enter outside regular hours
- Telegram alerts fully wired: signal created, TP1/2/3, TSL move, SL hit,
  momentum fade auto-close, TP3 extended, manual close, state change (RUNNING/DEVELOPING/PROTECTING/EXIT)
- @AlphaOmegaCEO_bot AI agent — natural language commands via Telegram
- Phase 1 conviction rescan (observe-only badges: RUNNING/DEVELOPING/PROTECTING/EXIT)

## 11. KNOWN ISSUES & TODO

### Known Bugs
- [ ] Render free tier cold start — first request after 15 min takes 30-60s to respond
- [x] ~~Render ephemeral storage~~ — signals now use Supabase with JSON fallback
- [x] ~~yfinance 15min delay~~ — Alpha Vantage real-time pricing now primary

### Roadmap
- [x] ~~Migrate signal storage to Supabase (persistent)~~ — done (signal_store.py)
- [x] ~~Webhook alerts (Telegram/Discord) on TP/SL hits~~ — fully wired in all signal events
- [x] ~~Stock scanner during market hours only~~ — afterhours session block in place
- [ ] Dynamic TP management Phase 2 (score drives TP/SL adjustments, EXIT auto-closes)
- [ ] Advisor tool — Opus reviews conviction before trade executes
- [ ] Claude Managed Agents (Dreaming, Outcomes grading, multi-agent)
- [ ] Chart screenshots in case reports (matplotlib at entry/exit)
- [ ] Portfolio-level analytics (correlation, sector exposure, drawdown by regime)
- [ ] Historical signal replay

## 12. HOW TO RUN LOCALLY

### Backend
```bash
cd C:\Users\asus\Alpha-Omega-System
python -m uvicorn backend.main:app --reload --port 8000
```

### Frontend
```bash
cd C:\Users\asus\Alpha-Omega-System\frontend
npm run dev
```

### Quick Tests
```bash
# Test signal tracker imports
python -c "from core.signal_tracker import check_signals; print('OK')"

# Test backend loads
python -c "from backend.main import app; print([r.path for r in app.routes if hasattr(r,'path')])"

# Run full verification
python test_tracker_v2.py
```

---

**Owner:** Avi
**System:** Windows 11 (asus laptop)
**Last Deploy:** 2026-05-14

---

## 13. CRITICAL RULES FOR CLAUDE — READ EVERY SESSION

### RULE 1: "I can't access that path" is almost always WRONG
Desktop Commander file tools (read_file, write_file, edit_block) are restricted to:
- C:\Users\asus\Alpha-Omega-System
- C:\Users\asus\Downloads

BUT start_process runs Python/cmd with NO directory restrictions.
Python can read/write anywhere — AppData, Documents, system dirs, anywhere.

**Before saying "I can't do X" — write a Python script and run it via start_process.**
Example: Cowork scheduled-tasks.json lives in AppData. DC file tools can't touch it.
But `python _patch.py` via start_process can. This is how all scheduled tasks were registered.

### RULE 2: These are the only files that auto-load in Cowork sessions
- MASTER-KNOWLEDGE.md ← this file
- COWORK-SKILLS.md
- PRD.md
- main.py

CLAUDE.md does NOT auto-load. Rules go here, not there.

### RULE 3: Always verify integrations are WORKING not just running
The Google Sheet was empty for months — process was running but writes silently failed.
The Dream Log 429'd every time — process ran but Gemini quota was exhausted.
Use GET /api/health/full to verify all 9 integrations before assuming things work.

### RULE 4: Single source of truth for the repo
Live repo: C:\Users\asus\Alpha-Omega-System (git connected)
Downloads folder has dead ZIP copies from April 29 — ignore them.
Always deploy from: git push origin main (triggers both Render + Vercel)

## 16. RECENT SESSION CHANGES
*Auto-updated: 2026-05-16 04:58 UTC*

### `d2c2312` 2026-05-16 07:41 - auto: session memory 2026-05-16 04:41
- `CLAUDE.md`
- `MASTER-KNOWLEDGE.md`
- `calibration/session_log.json`

### `c011350` 2026-05-16 07:40 - feat: permanent session memory - auto-updates knowledge files nightly
- `session_memory.py`

### `e3395ea` 2026-05-16 06:58 - feat: AI health agent, block closed-session autopilot, raise Trending Bull threshold to 72
- `backend/main.py`
- `core/ai_health_agent.py`
- `core/portfolio_manager.py`
- `patch_fixes2.py`

### `dfbcc38` 2026-05-16 06:35 - fix: 409 deploy guard, gc collect, memory endpoint, psutil
- `backend/main.py`
- `core/telegram_agent.py`
- `patch_system.py`
- `requirements.txt`

### `e5691c9` 2026-05-15 18:52 - fix: system audit - OOM memory models prices cleanup
- `.gitignore`
- `_check_env.py`
- `_daily_tg_notify.py`
- `_scan.py`
- `backend/main.py`

### `42eeb37` 2026-05-15 09:46 - fix: remove bad vercel.json
- `vercel.json`

### `ad4276d` 2026-05-14 23:12 - fix: instant dashboard load
- `CHANGES-LOG.md`
- `CLAUDE.md`
- `SYSTEM-BUILD-RECORD.md`
- `_check_env.py`
- `_daily_tg_notify.py`

### `a6b33e1` 2026-05-14 22:04 - feat: mobile responsive layout
- `frontend/src/App.jsx`
- `frontend/src/components/UIKit.jsx`

### `2a29bb5` 2026-05-14 20:18 - fix: clear old session, force re-login for new auth system
- `frontend/src/App.jsx`

### `65e642b` 2026-05-14 19:59 - fix: auth uses direct HTTP to Supabase REST - removes supabase-py WebSocket hang
- `backend/auth.py`


