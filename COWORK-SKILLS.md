# ALPHA-OMEGA — COWORK SKILLS & OPERATIONS GUIDE
# Location: C:\Users\asus\Alpha-Omega-System\COWORK-SKILLS.md

## HOW TO USE THIS FILE
This file contains step-by-step instructions for common operations.
Reference this when performing any task on the Alpha-Omega system.

---

## SUPERPOWERS WORKFLOW (use for all new development)

This project uses the Superpowers development methodology. Any coding agent working
on this project should follow these steps for every new feature or significant change.
Skills are in `.claude/skills/` and are invoked via the agent's Skill tool.

### Step 1 — BRAINSTORM before any code
Invoke `brainstorming` skill. Refine the idea through questions. Get a design approved.
Never write code without an approved design. Even "simple" tasks need this.

### Step 2 — WRITE A PLAN
Invoke `writing-plans` skill. Break work into bite-sized tasks (2-5 min each).
Each task: exact files to touch, code to write, how to test.
Save plans to: `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`

### Step 3 — ISOLATED WORKSPACE
Invoke `using-git-worktrees` skill. Work on a fresh branch.
Never implement features directly on `main`.

### Step 4 — EXECUTE with TDD
Invoke `subagent-driven-development` (if subagents available) or `executing-plans`.
For every task: invoke `test-driven-development` — write failing test FIRST, then code.
RED → GREEN → REFACTOR. No exceptions.

### Step 5 — REVIEW
Invoke `requesting-code-review` between tasks.
Critical issues block progress.

### Step 6 — VERIFY before claiming done
Invoke `verification-before-completion`.
Run smoke tests. Check output. THEN say it's done.

### Step 7 — FINISH the branch
Invoke `finishing-a-development-branch`.
Verify all tests pass → merge / PR / keep / discard.

### Debugging? Use the right skill:
- Any bug or unexpected behavior → `systematic-debugging` (find root cause first)
- Multiple independent failures → `dispatching-parallel-agents`
- Receiving review feedback → `receiving-code-review`

---

---

## SKILL 1: DEPLOY CHANGES

### When: After modifying any file
```bash
# 1. Build frontend (if JSX/CSS changed)
cd C:\Users\asus\Alpha-Omega-System\frontend
npx vite build

# 2. Stage, commit, push to BOTH remotes
cd C:\Users\asus\Alpha-Omega-System
git add -A
git commit -m "descriptive message"
git push origin main    # Render + Vercel (same GitHub repo; Vercel team synapse-s)

# 3. Wait 30-60s for deploy, then verify
# Backend: https://alpha-omega-system.onrender.com/health
# Frontend: https://alpha-omega-ngfw.vercel.app  (Vercel: synapse-s / project alpha-omega-ngfw)
```

### Important:
- One push to `origin main` is enough (`vercel` remote is duplicate URL)
- Frontend build is required — Vercel builds from source
- Render may take 1-2 min on cold start (free tier)

## SKILL 2: MODIFY SIGNAL TRACKER

### Files involved:
1. `core/signal_tracker.py` — Backend logic (1046 lines)
2. `backend/main.py` — API endpoints (459 lines)
3. `frontend/src/components/SignalTracker.jsx` — UI (419 lines)

### Pattern for changes:
1. Edit `signal_tracker.py` (add/modify functions)
2. If new endpoint needed → add to `backend/main.py`
3. If UI change needed → edit `SignalTracker.jsx`
4. Test locally: `python -c "from core.signal_tracker import ...; print('OK')"`
5. Deploy (Skill 1)

### Key functions in signal_tracker.py:
- `create_turbo_signal(symbol, asset_type, scan_data)` — Create signal
- `check_signals()` — Price refresh loop (called every 30s)
- `close_signal(signal_id, reason)` — Manual close
- `record_signal(scan_result, asset_type)` — Auto-record from scanner
- `get_all_signals()` — Read active + closed + stats
- `get_signal_report(id)` — Get case report
- `get_regime_performance()` — Stats by regime
- `_fetch_live_price(symbol, asset_type)` — Price with validation
- `_fetch_indicator_snapshot(symbol, asset_type)` — 79 data points
- `_fetch_market_context()` — VIX/SPY/regime
- `_is_us_market_open()` — Market hours check
- `_detect_gap_fill(signal, price, prev_close)` — Gap detection
- `_save_case_report(signal)` — Generate close report

### Signal data files:
- `signals/active_signals.json` — Currently tracking
- `signals/closed_signals.json` — Completed trades
- `signals/reports/*.json` — Case reports

## SKILL 3: MODIFY FRONTEND COMPONENTS

### Pattern:
1. Edit `.jsx` file in `frontend/src/components/`
2. Test locally: `cd frontend && npm run dev`
3. Build: `npx vite build`
4. Deploy (Skill 1)

### Style guide:
- Dark theme: bg `#050810`, cards `#0a0f18`, borders `#1a2535`
- Green (profit): `#00ff88`
- Red (loss): `#ff4466`
- Purple (accent): `#c084fc`
- Blue (info): `#00d4ff`
- Yellow (warning): `#fbbf24`
- Orange (crypto): `#f7931a`
- Font: monospace for data, sans-serif for labels
- All inline styles (no CSS classes except Tailwind basics)

### Available React libraries:
- lucide-react (icons)
- No charting library yet (add recharts if needed)

## SKILL 4: ADD NEW API ENDPOINT

### Pattern:
1. Add function to appropriate `core/*.py` file
2. Add endpoint in `backend/main.py`:
```python
@app.get("/api/my-endpoint")
async def my_endpoint():
    from core.my_module import my_function
    return my_function()
```
3. If frontend needs it, add fetch call in component
4. Test: `python -c "from backend.main import app; print('OK')"`
5. Deploy (Skill 1)

## SKILL 5: DEBUGGING & TESTING

### Quick smoke test:
```bash
cd C:\Users\asus\Alpha-Omega-System

# Backend loads?
python -c "from backend.main import app; print('FastAPI OK')"

# Signal tracker works?
python -c "from core.signal_tracker import check_signals; print('Signal Tracker OK')"

# Scanner works?
python -c "from agents.swing_scanner import SwingScanner; print('Scanner OK')"

# Full test suite
python test_tracker_v2.py
```

### Check live signals on Render:
- GET https://alpha-omega-api.onrender.com/api/signals
- POST won't work from browser (use curl or frontend)

### Check if Render is awake:
- Visit https://alpha-omega-api.onrender.com/docs
- If 502/timeout → Render free tier is sleeping, wait 30s

### Common errors:
| Error | Cause | Fix |
|-------|-------|-----|
| ModuleNotFoundError | Missing pip package | `pip install <package>` |
| yfinance rate limit | Too many requests | Add sleep(1) between calls |
| CORS error in browser | Backend not running | Check Render status |
| "Not Found" on POST | Using GET for POST endpoint | Use correct HTTP method |
| Signals disappear | Render redeployed (ephemeral) | Re-run autopilot |

## SKILL 6: ADD NEW AGENT TO COUNCIL

### Pattern:
1. Create `agents/my_agent.py` (extend `base_agent.py`)
2. Add to orchestrator chain in `core/orchestrator.py`
3. Add result card section in `frontend/src/components/ResultCard.jsx`
4. Test: `python -c "from agents.my_agent import MyAgent; print('OK')"`

## SKILL 7: MODIFY SWING SCANNER

### Files:
- `agents/swing_scanner.py` — Scanner logic
- `core/conviction_engine.py` — 5-pillar scoring
- `core/watchlists.py` — Stock universes
- `frontend/src/components/ScanDashboard.jsx` — UI

### Watchlists (in core/watchlists.py):
- `full_scan` — 30 stocks (default for autopilot)
- `tech` — Tech sector only
- `crypto` — Built into autopilot/crypto endpoint

## SKILL 8: WORK WITH BACKTESTER

### Files:
- `core/backtester.py` — Backtest engine
- `core/calibrator.py` — Auto-calibrate thresholds
- `calibration/calibration_params.json` — Current params
- `backtest_results/*.json` — Saved runs
- `frontend/src/components/BacktestDashboard.jsx` — UI

### Run backtest from API:
POST /api/backtest with body:
```json
{"symbols": ["AAPL","MSFT"], "lookback_days": 90}
```

## SKILL 9: HANDLE RENDER ISSUES

### Render free tier limitations:
- Spins down after 15 min inactivity
- First request takes 30-60s (cold start)
- **Ephemeral filesystem** — files deleted on every deploy
- 750 free hours/month

### Wake up Render:
```bash
curl https://alpha-omega-api.onrender.com/
```

### If signals lost after deploy:
Just re-run autopilot from frontend. The system recreates everything.

### Future fix: Supabase storage
Migrate active_signals.json and closed_signals.json to Supabase tables.
This is the #1 infrastructure improvement needed.
