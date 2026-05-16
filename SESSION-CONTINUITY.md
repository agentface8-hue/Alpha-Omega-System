# SESSION CONTINUITY - ALPHA-OMEGA
# READ THIS AT THE START OF EVERY DEVELOPMENT SESSION
# Fixes session amnesia - bridges the gap between sessions
# Last updated: 2026-05-16

---

## WHAT CHANGED MOST RECENTLY (2026-05-16)

### Fixed Today
- trade_log.py: calls Airtable on every trade close (was calling dead Google Sheets)
- price_feed.py: uses Finnhub (was using Alpha Vantage 25/day = always failing)
- SystemMonitor.jsx: Memory shows MB (was NaN), date separators in log
- Dream Log health check: /api/dreams/latest (was 404)
- AI health agent: 24h cooldown prevents repeat fixes
- Telegram: getMe not sendMessage (no spam)
- Health alerts: RED only, not every YELLOW

### Still Broken / Pending
- Dreaming Agent: 0 dreams ever produced - needs investigation or removal
- IBKR: Address doc REJECTED - needs Bank of Cyprus PDF at interactivebrokers.ie
- calibration_params.json: still ephemeral (not in Supabase yet)
- gspread/google-auth: still in requirements.txt (should be removed)
- SHEETS_TOKEN_JSON: dead env var on Render (should be deleted)
- Junk scripts in repo root (check_flow.py, council_test.py, etc.)

---

## CURRENT SYSTEM STATE

### Health (2026-05-16)
- Overall: YELLOW (only Alpha Vantage rate limit - non-critical)
- Portfolio: 4 open | Cash: $7531 | Total: $26750
- Signal Tracker: 0 active, 71 closed
- Performance: 53.5% win rate | 5.08 profit factor

### IBKR
- Account U25805425 | EUR 200 funded | Identity verified
- Address doc REJECTED - upload Bank of Cyprus PDF (file: bank_of_cyprus_account.pdf)
- Paper account DUQ966166 ($1M simulated) available

---

## ARCHITECTURE - NEVER CONFUSE THESE

### Two Separate Systems
1. Signal Tracker: signal_tracker.py -> /api/signals -> Supabase
2. Portfolio: portfolio_manager.py -> /api/portfolio -> Supabase

### Price Feed Order (everywhere)
1. Finnhub (FINNHUB_API_KEY) - real-time
2. yfinance - 15-20min fallback

### Trade Close Flow
signal_tracker.py -> trade_log.log_closed_signal(signal) -> Airtable + CSV

### Deploy
git add . && git commit -m "message" && git push origin main
(One push deploys both Render + Vercel)

---

## TOOLS AVAILABLE

### LLM Council (Cowork/Claude Code)
- Installed: ~/.claude/skills/llm-council
- Trigger: "council this: [question]"
- 5 agents parallel: Contrarian, First Principles, Expansionist, Outsider, Executor
- + peer review + Chairman synthesis
- Use for: architectural decisions, before significant changes

### 3-Agent Widget (this chat)
- Proposer / Skeptic / Verifier
- Use for: quick verification before calling something done

---

## SESSION RULES (learned from mistakes)
1. Before declaring any fix DONE - verify the actual production flow, not just the module
2. When replacing a dependency - grep ALL files that import it first
3. After every fix - check if other files do the same broken thing
4. Council says something -> take it seriously even if it contradicts my first answer
5. Render ephemeral: any fix in local files gets wiped on deploy
6. "Working" connection test != working in production close flow
