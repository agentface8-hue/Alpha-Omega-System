# Claude Managed Agents — Design Spec
Date: 2026-05-09
Status: Approved

## Three sub-projects, built in order

---

## ① Dreaming Agent

**What:** Scheduled background agent that monitors the market every 4h on trading days — no user trigger needed. Detects edge conditions and logs them.

**Trigger:** Wired into the existing scheduled task system (cowork_hourly_check.py or a new Render cron). Runs at 10:00, 14:00 ET on weekdays only.

**Flow:**
1. Fetch market context: VIX, SPY change, regime via `_fetch_market_context()`
2. Quick-scan top 10 tickers from the HOT watchlist via conviction engine
3. Send compact summary to Gemini Flash: "You are the Alpha-Omega Dreaming Agent. Given this market context and these setups, what is the single most interesting edge right now? Rate it: HIGH / MEDIUM / LOW."
4. Store result in Supabase `dream_log` table (fallback: JSON file)
5. Fire Telegram alert only if edge_level == "HIGH"

**New files:**
- `core/dreaming_agent.py` — `run_dream_cycle()` function
- Supabase table: `dream_log` (id, ts, regime, vix, spy_change, edge_level, top_ticker, analysis, model)

**New endpoint:** `GET /api/dreams/latest` — returns last 10 entries

**UI:** Dream Log widget at bottom of Signal Tracker tab (collapsible, shows last 3 dreams)

---

## ② Outcomes Grader

**What:** Fires automatically on every `close_signal()`. Opus reads the full closed signal and case report, grades the trade A–F, explains whether the conviction engine was correct, and extracts one lesson.

**Trigger:** Hook at end of `close_signal()` in `core/signal_tracker.py` — non-blocking (runs in background thread so it doesn't slow down the close).

**Flow:**
1. Read closed signal dict + case report JSON
2. Build compact prompt: entry/exit context, conviction, pillar scores, regime, P&L, MAE/MFE
3. Opus grades: A (excellent) / B (good) / C (acceptable) / D (poor) / F (should not have entered)
4. Returns: `{grade, was_conviction_right, lesson, improvement}`
5. Stores on closed signal object + Supabase `outcomes` table
6. Fires Telegram: "📊 TRADE GRADED — MRVL: B | Conviction was right, but entry was early"

**New files:**
- `core/outcomes_grader.py` — `grade_outcome(signal)` function

**Modified:** `core/signal_tracker.py` — add call in `close_signal()`

**New endpoint:** `GET /api/outcomes/summary` — grades distribution, top lessons

**UI:** Grade badge (A/B/C/D/F with color) on closed signal cards in Signal Tracker

---

## ③ Multi-Agent Council

**What:** For HOT signals (conviction ≥ 70%), replaces the single Sonnet screen with a structured debate: Bull Agent argues for the trade, Bear Agent argues against, Opus Moderator delivers the verdict.

**Trigger:** Called from `core/advisor.py` — if conviction ≥ 70%, run council instead of `screen_signal()`. Below 70%, keep existing Sonnet screen.

**Flow:**
1. **Bull Agent (Sonnet):** Given scan data, write the strongest possible bull case for this trade. Max 3 sentences. Focus on what's working.
2. **Bear Agent (Sonnet):** Same data. Write the strongest possible bear case / risks. Max 3 sentences.
3. **Moderator (Opus):** Read both cases + raw data. Verdict: PROCEED_STRONG / PROCEED_CAUTIOUS / HOLD / VETO + one-sentence reasoning.
4. Store: `council_bull_case`, `council_bear_case`, `council_verdict`, `council_reasoning` on signal
5. Advisor result updated: APPROVE (PROCEED_STRONG/CAUTIOUS) / FLAG / VETO maps from council verdict

**New files:**
- `core/agent_council.py` — `run_council(scan_data, market_context)` function

**Modified:** `core/advisor.py` — call `run_council()` for conviction ≥ 70%, else `screen_signal()`

**UI:** Council panel in expanded signal card — shows bull case, bear case, moderator verdict (replaces simple advisor panel for HOT signals)

---

## Shared infrastructure

- All three write to Supabase (non-blocking, JSON fallback)
- All three send Telegram alerts (using existing `core/telegram_alerts.py` — add new alert functions)
- All three are imported lazily in signal_tracker.py so failures are silent and never block trading

## Build order

① → ② → ③ (each is independent, ③ builds on Advisor which is already done)
