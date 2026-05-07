# CLAUDE.md — Alpha-Omega System
# Read this before doing ANYTHING in this repo.

---

## YOU HAVE SUPERPOWERS

This project has Superpowers skills installed in `.claude/skills/`. **You must use them.**

Before writing any code, before making any plan, before touching any file:
1. Check which skill applies
2. Invoke it via the Skill tool
3. Follow it — it is mandatory, not optional

**Skill → Task mapping (non-exhaustive):**

| What you're about to do | Skill to invoke FIRST |
|---|---|
| Build a new feature or component | `brainstorming` |
| Start implementing after design approved | `writing-plans` |
| Execute a written plan | `subagent-driven-development` or `executing-plans` |
| Write any feature or bugfix code | `test-driven-development` |
| Hit a bug or test failure | `systematic-debugging` |
| Claim something is done/fixed | `verification-before-completion` |
| Finish a feature branch | `finishing-a-development-branch` |
| Multiple independent failures to fix | `dispatching-parallel-agents` |
| Receive code review | `receiving-code-review` |
| Doing a code review | `requesting-code-review` |
| Starting a new feature branch | `using-git-worktrees` |

**If there's even a 1% chance a skill applies — use it. This is not negotiable.**

---

## PROJECT OVERVIEW

Alpha-Omega is an AI-powered stock/crypto trading analysis system:
- **Council of Experts**: 10 AI agents analyze any ticker from different angles
- **Swing Scanner v4.4**: Scans 30+ stocks, ranks by conviction (5-pillar system)
- **Signal Tracker v2.0**: Paper-trades signals with full audit trail
- **Backtester**: Tests the conviction engine against historical data
- **Auto-Pilot**: One button → scan universe → rank → launch ATR-based turbo signals

---

## DEPLOYMENT

| Component | Platform | URL |
|---|---|---|
| Frontend | Vercel | https://alpha-omega-ngfw.vercel.app |
| Backend | Render | https://alpha-omega-system.onrender.com |
| Local dev | localhost | http://127.0.0.1:8000 (backend), :5173 (frontend) |

### Git remotes:
- `origin` → github.com/agentface8-hue/Alpha-Omega-System (triggers Render)
- `vercel` → triggers Vercel frontend deploy

### Deploy workflow:
```bash
cd C:\Users\asus\Alpha-Omega-System

# If JSX/CSS changed, build frontend first:
cd frontend && npx vite build && cd ..

# Commit and push to BOTH remotes:
git add -A
git commit -m "descriptive message"
git push origin main   # Render backend
git push vercel main   # Vercel frontend
```

### Render free tier notes:
- Spins down after 15 min inactivity → first request takes 30-60s
- **Ephemeral filesystem** — signals/ files deleted on every deploy
- Supabase migration is the #1 infrastructure priority (see PRD.md)

---

## ARCHITECTURE & FILE MAP

```
C:\Users\asus\Alpha-Omega-System\
├── CLAUDE.md                    # THIS FILE — read first
├── MASTER-KNOWLEDGE.md          # Extended system bible
├── COWORK-SKILLS.md             # Step-by-step ops guide
├── SIGNAL-TRACKER-V2.md         # Signal tracker deep dive
├── PRD.md                       # Product requirements
├── .env                         # API keys (gitignored)
├── requirements.txt             # Python deps
├── render.yaml                  # Render deploy config
│
├── .claude/
│   └── skills/                  # Superpowers skills (14 skills)
│
├── backend/
│   ├── main.py                  # FastAPI app — ALL endpoints
│   └── schemas.py               # Pydantic models
│
├── core/                        # Business logic
│   ├── signal_tracker.py        # ⭐ Signal Tracker v2.0
│   ├── orchestrator.py          # Agent orchestrator
│   ├── smart_analyze.py         # Smart analysis fallback chain
│   ├── conviction_engine.py     # 5-pillar conviction scoring
│   ├── backtester.py            # Historical backtesting
│   ├── calibrator.py            # Auto-calibrate thresholds
│   ├── market_data.py           # yfinance data fetching
│   ├── watchlists.py            # Stock universes
│   ├── decision_matrix.py       # Decision framework
│   ├── decision_ledger.py       # Trade decision logging
│   ├── trade_journal.py         # Trade journal
│   └── attribution.py          # Performance attribution
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
│   └── regime_detector.py      # Market regime
│
├── frontend/
│   └── src/
│       ├── App.jsx              # Main app + tabs
│       └── components/
│           ├── SignalTracker.jsx # Signal Tracker UI
│           ├── ScanDashboard.jsx # Swing Scanner UI
│           ├── BacktestDashboard.jsx
│           ├── Terminal.jsx     # Council Analyze terminal
│           ├── ResultCard.jsx   # Analysis results
│           ├── LiveTicker.jsx   # Top ticker bar
│           └── TopStocks.jsx   # Top movers widget
│
├── signals/
│   ├── active_signals.json      # Currently tracking
│   ├── closed_signals.json      # Completed trades
│   └── reports/*.json           # Case reports
│
├── tests/
│   ├── test_app_integration.py
│   └── test_flow.py
│
└── docs/
    ├── DEPLOY.md
    ├── ATTRIBUTION_OPS.md
    └── superpowers/
        └── plans/               # Implementation plans go here
```

---

## TECH STACK

- **Backend**: Python, FastAPI, Uvicorn
- **Frontend**: React (Vite), Tailwind basics, lucide-react icons
- **AI**: Google Gemini (primary), Claude (Anthropic), OpenAI — via env keys
- **Data**: yfinance, Polygon.io (optional)
- **Storage**: JSON files (ephemeral on Render) → Supabase (planned)
- **LangChain**: langchain-google-genai, langchain-anthropic, langchain-openai

### Frontend style guide:
- Dark theme: bg `#050810`, cards `#0a0f18`, borders `#1a2535`
- Green (profit): `#00ff88` | Red (loss): `#ff4466`
- Purple (accent): `#c084fc` | Blue (info): `#00d4ff`
- Yellow (warning): `#fbbf24` | Orange (crypto): `#f7931a`
- Font: monospace for data, sans-serif for labels
- All inline styles (no external CSS classes beyond Tailwind basics)

---

## DEVELOPMENT PRINCIPLES (from superpowers)

### TDD is mandatory
Write the failing test first. Watch it fail. Then write code. If you didn't watch it fail, you don't know if it tests the right thing. The test files live in `tests/`.

```bash
# Run tests
python tests/test_app_integration.py
python tests/test_flow.py
python test_tracker_v2.py
```

### No fixes without root cause
Use `systematic-debugging` before proposing any fix. Symptom patches are failure.

### No completion claims without evidence
Run the verification commands. Check output. Then and only then say it's done.

### Plans go in docs/superpowers/plans/
Format: `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`

---

## QUICK SMOKE TESTS

```bash
cd C:\Users\asus\Alpha-Omega-System

# Backend loads?
python -c "from backend.main import app; print('FastAPI OK')"

# Signal tracker works?
python -c "from core.signal_tracker import SignalTracker; print('Signal Tracker OK')"

# Scanner works?
python -c "from agents.swing_scanner import SwingScanner; print('Scanner OK')"

# Conviction engine works?
python -c "from core.conviction_engine import ConvictionEngine; print('Conviction OK')"
```

---

## COMMON ERRORS

| Error | Cause | Fix |
|---|---|---|
| ModuleNotFoundError | Missing pip package | `pip install <package>` |
| yfinance rate limit | Too many requests | Add `time.sleep(1)` between calls |
| CORS error in browser | Backend not running | Check Render status |
| Signals disappear | Render redeployed (ephemeral) | Re-run autopilot |
| 502/timeout on Render | Cold start (free tier sleeping) | Wait 30-60s, retry |

---

## KEY PRIORITIES (from PRD)

1. **Supabase migration** — persistent signals storage (highest infra priority)
2. **Sharpe Ratio > 2.5** — core KPI
3. **Max drawdown < 15%** — hard limit
4. **Circuit breakers** — auto-shutdown on drawdown breach
5. **XAI thesis** — every signal must have human-readable explanation
6. **Paper trading first** — 6 months minimum before live capital

---

## SIGNAL TRACKER KEY FUNCTIONS

```python
# core/signal_tracker.py
create_turbo_signal(symbol, asset_type, scan_data)  # Create signal
check_signals()                                      # Price refresh (every 30s)
close_signal(signal_id, reason)                     # Manual close
record_signal(scan_result, asset_type)              # Auto-record from scanner
get_all_signals()                                   # All active + closed + stats
get_signal_report(id)                               # Case report
_fetch_live_price(symbol, asset_type)               # Price with validation
_detect_gap_fill(signal, price, prev_close)         # Gap detection
```

---

## ADDING A NEW API ENDPOINT

```python
# 1. Add logic to core/*.py
# 2. Add endpoint to backend/main.py:
@app.get("/api/my-endpoint")
async def my_endpoint():
    from core.my_module import my_function
    return my_function()
# 3. Test: python -c "from backend.main import app; print('OK')"
# 4. Deploy
```

---

## ADDING A NEW AGENT

1. Create `agents/my_agent.py` extending `base_agent.py`
2. Add to chain in `core/orchestrator.py`
3. Add result section in `frontend/src/components/ResultCard.jsx`
4. Test: `python -c "from agents.my_agent import MyAgent; print('OK')"`
5. Deploy

---

*For extended docs see MASTER-KNOWLEDGE.md, COWORK-SKILLS.md, SIGNAL-TRACKER-V2.md, PRD.md*
*Superpowers skills: `.claude/skills/` — invoke via Skill tool before any task*
