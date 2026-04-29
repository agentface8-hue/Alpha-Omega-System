# ALPHA-OMEGA SYSTEM — MASTER KNOWLEDGE BASE
# Last Updated: 2026-02-27
# Location: C:\Users\asus\Alpha-Omega-System\MASTER-KNOWLEDGE.md

## WHAT IS THIS FILE?
This is the complete system bible. Read this first in any new session.
It contains architecture, file locations, deployment info, and current state.

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
| Backend | Render | https://alpha-omega-api.onrender.com | `origin` → github.com/agentface8-hue/Alpha-Omega-System |
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

## 9. CRITICAL NOTES

### Render Ephemeral Storage ⚠️
Render free tier wipes files on redeploy. This means:
- `signals/active_signals.json` and `closed_signals.json` get DELETED
- Case reports in `signals/reports/` get DELETED
- **TODO**: Migrate signal storage to Supabase or persistent volume

### yfinance Delay
- Free tier has 15-20 minute delay on stock prices
- Crypto is near-realtime
- Signal tracker has staleness detection built in

### Git Remote (single remote now)
```
origin  → github.com/agentface8-hue/Alpha-Omega-System  (Render + Vercel)
```
One push deploys everything. No more dual remotes.

### API Keys (.env)
```
GOOGLE_API_KEY=...      # Gemini for agents
ANTHROPIC_API_KEY=...   # Claude fallback
SUPABASE_URL=...        # Database (if used)
SUPABASE_ANON_KEY=...   # Database (if used)
```

## 10. EVOLUTION HISTORY

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

### v3.1 — Signal Tracker v2.0 (Feb 27, 2026) ← CURRENT
- 15 critical gaps fixed (see SIGNAL-TRACKER-V2.md)
- Full audit trail with 79 data points per entry
- ATR-based targets
- Gap detection + realistic fills
- MAE/MFE tracking
- Market context at entry/close
- Case reports with auto-analysis
- Price staleness detection
- Market hours awareness

## 11. KNOWN ISSUES & TODO

### Bugs
- [ ] Render ephemeral storage — signals lost on redeploy
- [ ] yfinance 15min delay on stocks (staleness detection mitigates)
- [ ] Frontend occasionally doesn't show signals on cold load (Render free tier spins down)

### Roadmap
- [ ] Migrate signal storage to Supabase (persistent)
- [ ] Add chart screenshots to case reports (matplotlib)
- [ ] Stock scanner during market hours only
- [ ] Historical signal replay
- [ ] Portfolio-level analytics (correlation, sector exposure)
- [ ] Webhook alerts (Telegram/Discord) on TP/SL hits
- [ ] Multi-strategy support (not just turbo)

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
**Last Deploy:** 2026-02-27 commit ffdb3e8
