# ALPHA-OMEGA — CURSOR SYSTEM BRIEF

**System manager: Cursor only** (as of 2026-05-28). Claude does not run deploys, edits, or ops on this repo — it may answer questions and write briefs for Cursor. Do not duplicate health/monitor/learning logic elsewhere; extend AMA (`core/ama/`) instead.

---

## ⛔ DO NOT TOUCH (stability stack — deployed & verified)

These were fixed in **`9ec7893`** (`fix_parallel_health_checks`) and verified on Render. Do not revert, re-wrap, or re-implement parallel checks in other modules.

| File / surface | Why frozen |
|----------------|------------|
| `core/system_health.py` | Parallel 9-check health; executor timeouts |
| `core/live_monitor.py` | L1–L3 monitor loops; L3 uses **in-process** checks (not self-HTTP to public URL) |
| `backend/main.py` → `GET /api/health/full` | Full health via executor + timeout |
| `backend/main.py` → `GET /api/learning/summary` | Summary via executor + 10s cap |
| `backend/main.py` → `GET /api/trade-history` | Trade log fetch + enrichment |

**Before changing any row above:** reproduce the issue on production, confirm the fix is not already here, and run `POST /api/monitor/run` + `GET /api/monitor/status` after deploy.

**Safe to extend without duplicating:** `core/ama/*`, `backend/ama_routes.py`, frontend `AmaStatus.jsx` / `SystemMonitor.jsx`, operator skill `.claude/skills/alpha-omega-operator/SKILL.md`.

---

## READ FIRST
Before starting, read these files in this order:
1. `ALPHA-OMEGA-CURSOR-PRD.md` — full system architecture
2. `MASTER-KNOWLEDGE.md` — current system state
3. `core/live_monitor.py` — existing 3-level health monitor
4. `core/system_health.py` — existing 9-check health system
5. `core/learning_loop.py` — existing learning loop
6. `core/telegram_agent.py` — existing Telegram command handler
7. `backend/main.py` — all API endpoints

---

## WHAT YOU ARE BUILDING

An **Autonomous Management Agent (AMA)** — a self-running system that manages the
entire Alpha-Omega platform without human intervention.

Think of it as a site reliability engineer + trading desk manager + DevOps bot
running 24/7 inside the same Render process. It observes the system, makes
decisions, takes corrective actions, and reports everything to Telegram.

The closest reference: Anthropic's Cowork (Claude's computer-use agent) but
specialized entirely for Alpha-Omega's infrastructure and trading logic.

---

## AGENT ARCHITECTURE

### Core Design: Observe → Decide → Act → Report Loop

```
Every N minutes:
  1. OBSERVE   — collect system state (health, positions, prices, errors)
  2. DECIDE    — classify what needs action (rules + LLM judgment)
  3. ACT       — execute the action (fix, alert, trade, deploy)
  4. REPORT    — log result, send Telegram if significant
  5. LEARN     — update agent memory with what happened
```

### Two Layers

**Layer 1 — Rule Engine (fast, deterministic)**
Handles known conditions with hardcoded rules. No LLM call needed.
Examples: SL hit → close position. Health RED → restart service. Memory > 80% → gc.

**Layer 2 — LLM Agent (slow, intelligent)**
Handles novel or ambiguous situations. Uses Claude Sonnet 4.6.
Examples: "Health check has been YELLOW for 6 hours, what should I do?"
Triggered only when Layer 1 has no matching rule.

---

## FILE STRUCTURE TO CREATE

```
core/
  ama/
    __init__.py
    agent.py            ← Main AMA orchestrator (the brain)
    observer.py         ← System state collector
    decision_engine.py  ← Rule engine + LLM classifier
    action_runner.py    ← Executes all possible actions
    memory.py           ← Agent memory (Supabase-backed)
    scheduler.py        ← Task scheduler (replaces scattered threads)
    tools.py            ← All tools the agent can use
    rules.py            ← Hardcoded rule definitions
    report.py           ← Telegram + log reporting

backend/
  ama_routes.py         ← API routes for AMA control
```

Add to `backend/main.py`:
```python
from backend.ama_routes import router as ama_router
app.include_router(ama_router, prefix="/api/ama")
```

Add to `startup_all()` in `backend/main.py`:
```python
from core.ama.agent import start as start_ama
start_ama()
```

---

## DETAILED SPEC: EACH MODULE

---

### `core/ama/observer.py` — System State Collector

Collects a complete snapshot of system state. Called at the start of every agent cycle.

```python
class SystemSnapshot:
    timestamp: str
    
    # Health
    health_checks: Dict[str, str]   # check_name → GREEN/YELLOW/RED
    health_overall: str             # GREEN/YELLOW/RED
    
    # Portfolio
    open_positions: List[dict]      # from portfolio_store.load_positions("open")
    portfolio_state: dict           # cash, equity, drawdown
    positions_at_risk: List[str]    # tickers where price < SL + 1%
    
    # Signals
    active_signals: int
    stale_signals: List[str]        # signals not updated > 2h
    
    # Performance
    memory_mb: float                # process RSS
    memory_pct: float               # % of 2GB limit
    
    # External
    finnhub_ok: bool
    supabase_ok: bool
    telegram_ok: bool
    
    # Recent events
    recent_errors: List[dict]       # last 10 errors from logs
    failed_checks: List[str]        # currently failing health checks
    
    # Market
    market_open: bool
    spy_price: float
    vix: float
    regime: str                     # Bull/Bear/Neutral/Volatile

def collect_snapshot() -> SystemSnapshot:
    """Collect full system state. Never raises — all errors caught and noted in snapshot."""
    ...
```

---

### `core/ama/rules.py` — Rule Definitions

Define all deterministic rules. Format: condition function + action name + params.

```python
RULES = [
    # --- CRITICAL (always act immediately) ---
    Rule(
        name="memory_critical",
        condition=lambda s: s.memory_pct > 90,
        action="gc_collect",
        priority=1,
        cooldown_minutes=5,
        telegram=True,
        message="Memory {memory_mb:.0f}MB ({memory_pct:.0f}%) — forcing GC"
    ),
    Rule(
        name="supabase_down",
        condition=lambda s: not s.supabase_ok,
        action="alert_only",
        priority=1,
        cooldown_minutes=60,
        telegram=True,
        message="Supabase unreachable — positions using JSON fallback"
    ),
    
    # --- PORTFOLIO ---
    Rule(
        name="position_near_sl",
        condition=lambda s: len(s.positions_at_risk) > 0,
        action="check_portfolio_now",
        priority=2,
        cooldown_minutes=10,
        telegram=True,
        message="Position near SL: {positions_at_risk}"
    ),
    Rule(
        name="portfolio_check_overdue",
        condition=lambda s: s.market_open and _last_portfolio_check_age() > 35,
        action="check_portfolio_now",
        priority=2,
        cooldown_minutes=30,
        telegram=False,
        message="Portfolio check overdue — running now"
    ),
    
    # --- HEALTH ---
    Rule(
        name="health_red",
        condition=lambda s: s.health_overall == "RED",
        action="run_health_fix",
        priority=2,
        cooldown_minutes=120,
        telegram=True,
        message="Health RED: {failed_checks}"
    ),
    Rule(
        name="stale_signals",
        condition=lambda s: len(s.stale_signals) > 0,
        action="refresh_signals",
        priority=3,
        cooldown_minutes=30,
        telegram=False,
        message="Stale signals: {stale_signals}"
    ),
    
    # --- LEARNING ---
    Rule(
        name="learning_overdue",
        condition=lambda s: _last_learning_run_age() > 120,
        action="run_learning_fast",
        priority=4,
        cooldown_minutes=120,
        telegram=False,
        message="Learning loop overdue — running fast cycle"
    ),
    
    # --- MARKET ---
    Rule(
        name="market_opens_soon",
        condition=lambda s: _minutes_until_open() in range(5, 16),
        action="run_morning_scan",
        priority=3,
        cooldown_minutes=1440,  # once per day
        telegram=True,
        message="Market opens in {minutes_until_open} min — running morning scan"
    ),
    Rule(
        name="market_closed_cleanup",
        condition=lambda s: not s.market_open and _minutes_since_close() == 5,
        action="run_eod_summary",
        priority=3,
        cooldown_minutes=1440,
        telegram=True,
        message="Market closed — running EOD summary"
    ),
]
```

---

### `core/ama/action_runner.py` — Action Executor

Every action the agent can take. Each action is a function that returns an ActionResult.

```python
class ActionResult:
    action: str
    success: bool
    detail: str
    duration_ms: int
    side_effects: List[str]   # e.g., ["telegram_sent", "position_closed"]

# Available actions:

def gc_collect() -> ActionResult:
    """Force Python garbage collection."""

def alert_only(message: str) -> ActionResult:
    """Send Telegram alert, no other action."""

def check_portfolio_now() -> ActionResult:
    """Trigger portfolio price refresh + TP/SL check."""
    # Calls core.portfolio_manager.check_portfolio()

def run_health_fix(failed_checks: List[str]) -> ActionResult:
    """Attempt automatic fixes for failed health checks.
    
    Known fixes:
    - Supabase timeout → retry with exponential backoff
    - Finnhub rate limit → wait 60s, then retry
    - Memory > 85% → gc.collect() + clear all caches
    - Telegram → re-init bot connection
    """

def refresh_signals() -> ActionResult:
    """Re-run check_signals() for stale signals."""

def run_learning_fast() -> ActionResult:
    """Trigger fast learning cycle."""

def run_morning_scan() -> ActionResult:
    """Run momentum screener + conviction scan, send top picks to Telegram."""

def run_eod_summary() -> ActionResult:
    """Generate end-of-day P&L + position summary, send to Telegram."""

def clear_cache(cache_name: str) -> ActionResult:
    """Clear a specific cache file (momentum/sector/scan)."""

def restart_background_service(service_name: str) -> ActionResult:
    """Restart a named background thread (learning_loop, telegram_agent, etc.)."""

def escalate_to_llm(snapshot: SystemSnapshot, context: str) -> ActionResult:
    """Hand off to LLM agent for novel situations."""
```

---

### `core/ama/decision_engine.py` — Decide What to Do

```python
def decide(snapshot: SystemSnapshot, agent_memory: AgentMemory) -> List[PlannedAction]:
    """
    Returns ordered list of actions to take this cycle.
    
    Process:
    1. Run all RULES against snapshot
    2. Filter by cooldown (don't repeat recent actions)
    3. Sort by priority
    4. If no rules fire AND something looks wrong → escalate to LLM
    5. Return action list (empty = do nothing this cycle)
    """

def _should_escalate_to_llm(snapshot: SystemSnapshot, fired_rules: List[Rule]) -> bool:
    """
    Escalate to LLM when:
    - Health YELLOW for > 3 cycles with no improvement
    - Portfolio drawdown > 5% in one session
    - Unusual pattern not covered by any rule
    - Agent has been making the same fix repeatedly without success
    """

def _call_llm_agent(snapshot: SystemSnapshot, context: str) -> PlannedAction:
    """
    Uses Claude Sonnet 4.6.
    
    System prompt: "You are the Alpha-Omega Autonomous Management Agent.
    You manage a live paper trading system. You have access to the full
    system state. Your job is to decide what single action to take next.
    Be conservative — prefer observation over intervention."
    
    Returns: one PlannedAction with reasoning attached.
    """
```

---

### `core/ama/memory.py` — Agent Memory

Persistent memory stored in Supabase table `ama_memory`.

```python
class AgentMemory:
    # Action history
    recent_actions: List[ActionLog]        # last 100 actions taken
    action_cooldowns: Dict[str, datetime]  # action_name → last_run_time
    
    # Pattern tracking
    repeated_failures: Dict[str, int]      # check_name → consecutive_fail_count
    fix_attempts: Dict[str, int]           # fix_name → attempt_count_today
    
    # Daily context
    session_start: datetime
    actions_today: int
    alerts_today: int
    
    # Learning
    what_worked: List[str]                 # successful fix patterns
    what_failed: List[str]                 # failed fix patterns

class ActionLog:
    ts: str
    action: str
    trigger: str          # rule_name or "llm_agent"
    success: bool
    detail: str
    snapshot_summary: str  # compressed state at time of action
```

Supabase DDL (add to `migrations/`):
```sql
CREATE TABLE IF NOT EXISTS ama_memory (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMPTZ DEFAULT NOW(),
    action TEXT NOT NULL,
    trigger TEXT,
    success BOOLEAN,
    detail TEXT,
    snapshot_json JSONB,
    cycle_number INTEGER
);

CREATE TABLE IF NOT EXISTS ama_state (
    key TEXT PRIMARY KEY,
    value JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

### `core/ama/agent.py` — Main Orchestrator (The Brain)

```python
"""
Alpha-Omega Autonomous Management Agent (AMA)

Runs as a background thread inside the FastAPI process.
Cycle interval: 5 minutes (configurable).
Never blocks — all operations have timeouts.
"""

CYCLE_INTERVAL_SECONDS = 300   # 5 minutes
MAX_ACTIONS_PER_CYCLE  = 3     # safety limit
MAX_ACTIONS_PER_HOUR   = 12    # circuit breaker

class AMAAgent:
    def __init__(self):
        self.cycle_number   = 0
        self.memory         = AgentMemory()
        self.running        = False
        self._thread        = None
    
    def start(self):
        """Start the agent loop in a daemon thread."""
        self._thread = threading.Thread(
            target=self._run_loop,
            name="ama_agent",
            daemon=True
        )
        self._thread.start()
        log.info("[AMA] Agent started — cycle every 5 minutes")
    
    def _run_loop(self):
        """Main agent loop. Runs forever."""
        while True:
            try:
                self._run_cycle()
            except Exception as e:
                log.error(f"[AMA] Cycle {self.cycle_number} crashed: {e}")
            time.sleep(CYCLE_INTERVAL_SECONDS)
    
    def _run_cycle(self):
        """Single agent cycle: Observe → Decide → Act → Report."""
        self.cycle_number += 1
        t0 = time.time()
        
        # 1. OBSERVE
        snapshot = collect_snapshot()
        
        # 2. DECIDE
        actions = decide(snapshot, self.memory)
        actions = actions[:MAX_ACTIONS_PER_CYCLE]  # safety cap
        
        # 3. ACT
        results = []
        for action in actions:
            result = run_action(action, snapshot)
            results.append(result)
            self.memory.record(action, result, snapshot)
            if not result.success:
                log.warning(f"[AMA] Action failed: {action.name} — {result.detail}")
        
        # 4. REPORT (only if something happened)
        if results:
            _report_cycle(self.cycle_number, snapshot, results)
        
        elapsed = int((time.time() - t0) * 1000)
        log.debug(f"[AMA] Cycle {self.cycle_number} done in {elapsed}ms — {len(results)} actions")

# Module-level singleton
_agent = AMAAgent()

def start():
    _agent.start()

def get_status() -> dict:
    return {
        "running":       _agent.running,
        "cycle_number":  _agent.cycle_number,
        "actions_today": _agent.memory.actions_today,
        "last_cycle":    _agent.memory.last_cycle_ts,
    }

def run_cycle_now() -> dict:
    """Trigger an immediate cycle (for manual/API use)."""
    _agent._run_cycle()
    return get_status()
```

---

### `core/ama/report.py` — Telegram Reporting

```python
# Telegram message formats:

# Cycle summary (only sent if significant actions taken):
"""
🤖 AMA Cycle #142 — 14:30 UTC
━━━━━━━━━━━━━━━━━━━━━━
System: 🟢 GREEN
Portfolio: 3 open | +2.1% today
Actions taken: 2
  ✅ check_portfolio_now — TP1 hit on AAPL
  ✅ run_learning_fast — 84 trades analyzed
"""

# Alert (immediate, rule-triggered):
"""
⚡ AMA ACTION — 14:35 UTC
Rule: position_near_sl
NVDA within 0.8% of SL ($189.20)
Action: Portfolio check triggered
Result: ✅ Price held, SL not hit
"""

# LLM agent decision:
"""
🧠 AMA LLM DECISION — 16:00 UTC
Situation: Health YELLOW for 3 cycles (Finnhub slow)
Reasoning: Finnhub rate limit pattern — not a real outage.
Action: Wait 1 more cycle before escalating.
Confidence: HIGH
"""

# Daily summary (EOD):
"""
📊 AMA Daily Report — 22:00 UTC
━━━━━━━━━━━━━━━━━━━━━━
Cycles run: 96
Actions taken: 14
Alerts sent: 3
Positions managed: 5 open, 1 closed (AAPL +4.1%)
System uptime: 100%
Issues resolved: 2 (Finnhub rate limit ×2)
Issues unresolved: 0
"""
```

---

### `backend/ama_routes.py` — API Control Endpoints

```python
GET  /api/ama/status        → agent status, cycle count, actions today
GET  /api/ama/history       → last 50 action logs
POST /api/ama/run-now       → trigger immediate cycle
POST /api/ama/pause         → pause agent (owner only)
POST /api/ama/resume        → resume agent (owner only)
GET  /api/ama/memory        → full agent memory dump
POST /api/ama/clear-memory  → reset action history (owner only)
GET  /api/ama/snapshot      → current system snapshot (what agent sees)
```

Add AMA status card to frontend dashboard (optional but useful):
```
🤖 AMA  |  Cycle #142  |  14 actions today  |  🟢 Active
```

---

## IMPLEMENTATION ORDER

Build in this sequence — each step is testable independently:

### Phase 1 — Observer (Day 1)
1. Build `observer.py` — `collect_snapshot()` function
2. Add `/api/ama/snapshot` endpoint
3. Test: curl the endpoint, verify all fields populate correctly
4. Goal: full system visibility in one data structure

### Phase 2 — Rules + Actions (Day 1-2)
1. Build `rules.py` — all rule definitions
2. Build `action_runner.py` — all action functions (stubs OK initially)
3. Build `decision_engine.py` — rule evaluation + cooldown logic
4. Test: feed mock snapshots, verify correct rules fire
5. Goal: deterministic rule layer works correctly

### Phase 3 — Memory (Day 2)
1. Create Supabase tables (`ama_memory`, `ama_state`)
2. Build `memory.py` — load/save action logs, cooldowns
3. Test: run 3 cycles, verify history persists in Supabase
4. Goal: agent remembers what it did across restarts

### Phase 4 — Agent Loop (Day 2-3)
1. Build `agent.py` — main orchestrator
2. Add startup registration in `backend/main.py`
3. Build `ama_routes.py` — API endpoints
4. Test: start Render, watch logs for cycle messages
5. Goal: agent runs every 5 min, logs cycles

### Phase 5 — LLM Integration (Day 3)
1. Add `_call_llm_agent()` to `decision_engine.py`
2. Define escalation conditions
3. Test: force a YELLOW health state, verify LLM is called
4. Goal: novel situations handled by Claude

### Phase 6 — Reporting (Day 3-4)
1. Build `report.py` — Telegram message formatters
2. Add EOD summary action
3. Add morning briefing trigger
4. Test: verify Telegram messages arrive correctly
5. Goal: agent communicates clearly via Telegram

### Phase 7 — Frontend Widget (Day 4)
1. Add AMA status card to dashboard header
2. Add `/ama` tab or panel (history, snapshot, pause/resume)
3. Goal: Avi can see what the agent did from the UI

---

## CONSTRAINTS & SAFETY RULES

**The agent MUST follow these rules at all times:**

1. **Never open or close positions autonomously** unless Avi has explicitly enabled `AMA_AUTO_TRADE=true` in env vars. Default: observe and alert only.

2. **Never modify conviction thresholds** without explicit instruction. Read `calibration_params.json` but don't write to it autonomously.

3. **Hard rate limit:** max 12 actions per hour. If this limit is reached, send a single Telegram alert and stop until next hour.

4. **Never retry a failed fix more than 3 times in 24h.** After 3 failures, escalate to Telegram with "manual intervention required."

5. **All actions have timeouts.** No action can run for more than 30 seconds. Wrap everything in `asyncio.wait_for()` or `concurrent.futures` with explicit timeout.

6. **Agent crash must not crash FastAPI.** The agent runs in a daemon thread. All exceptions are caught at the cycle level.

7. **LLM calls are a last resort.** Rule engine handles > 95% of situations. LLM is only called when no rule matches AND something is clearly wrong.

8. **Full audit trail.** Every action is logged to Supabase `ama_memory` table with timestamp, trigger, result, and snapshot context.

---

## ENVIRONMENT VARIABLES TO ADD

```
AMA_ENABLED=true              # master on/off switch
AMA_CYCLE_INTERVAL=300        # seconds between cycles (default 300)
AMA_AUTO_TRADE=false          # allow agent to open/close positions
AMA_TELEGRAM_VERBOSE=false    # send Telegram on every cycle (debug)
AMA_MAX_ACTIONS_PER_HOUR=12   # circuit breaker
```

Add to Render dashboard when deploying.

---

## TESTING CHECKLIST

Before considering the AMA complete, verify all of these:

- [ ] `collect_snapshot()` returns complete snapshot with no exceptions
- [ ] All 8 rules evaluate correctly against mock snapshots
- [ ] Cooldown system prevents duplicate actions
- [ ] Actions don't crash when underlying services are slow/down
- [ ] Memory persists in Supabase across agent restarts
- [ ] LLM escalation fires correctly (test with forced YELLOW state)
- [ ] All Telegram messages arrive correctly formatted
- [ ] Agent thread doesn't block FastAPI event loop
- [ ] `/api/ama/status` returns correct data
- [ ] `/api/ama/run-now` triggers a cycle and returns results
- [ ] Max 12 actions/hour circuit breaker works
- [ ] EOD summary fires after market close
- [ ] Agent survives Render restart (reloads memory from Supabase)
- [ ] No memory leaks after 100 cycles (monitor via `/api/memory`)

---

## REFERENCE IMPLEMENTATIONS TO READ

Before writing any code, study these existing files for patterns:

| File | What to learn from it |
|------|----------------------|
| `core/live_monitor.py` | Background thread + check loops + Telegram alerts |
| `core/system_health.py` | Parallel check execution with timeouts |
| `core/portfolio_manager.py` | Threading lock pattern (`_CHECK_LOCK`) |
| `core/learning_loop.py` | Background service + cooldown logic |
| `core/telegram_alerts.py` | How to send Telegram messages |
| `core/ai_health_agent.py` | Existing AI-powered health agent (extend don't duplicate) |
| `core/signal_store.py` | Supabase-first storage pattern |

The AMA replaces the scattered background threads with one unified agent.
It does NOT delete the existing threads — it runs alongside them and coordinates them.

---

*Brief prepared 2026-05-28. Reference: ALPHA-OMEGA-CURSOR-PRD.md for full system context.*
