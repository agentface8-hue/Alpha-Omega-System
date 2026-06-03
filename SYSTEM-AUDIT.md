# Alpha-Omega System Audit
**Last updated:** 2026-05-14
**Capital:** $25,000 paper | **Max positions:** 10 | **Risk/trade:** $500

---

## 1. Installed Cowork Plugins

| Plugin | ID | Skills |
|--------|----|--------|
| **Data** | `data@knowledge-work-plugins` | analyze, build-dashboard, create-viz, data-visualization, explore-data, sql-queries, statistical-analysis, validate-data, write-query, data-context-extractor |
| **Daloopa** | `daloopa@knowledge-work-plugins` | build-model, bull-bear, capital-allocation, comp-sheet, comps, dcf, earnings, earnings-flash, earnings-prep, guidance-tracker, ib-deck, industry, inflection, initiate, precedent-transactions, research-note, setup, supply-chain, tearsheet, unit-economics, working-capital |

> **Note:** Daloopa MCP connector not yet authenticated. Skills are available but require a Daloopa account + API key to execute. Deferred until earnings-catalyst trading workflow is active.

---

## 2. Connected Connectors / MCP Servers

| Connector | Purpose for Alpha-Omega |
|-----------|------------------------|
| **Gmail** | Daily 5 PM summary email drafts; alert delivery to ipurchesinfo@gmail.com |
| **Google Drive** | Hosts Alpha-Omega Trade Log sheet (ID: `1G5f1AePhWKJEMJKmfHj1genbr18LMdlCWPsoBJC2ZxM`) |
| **Google Calendar** | Schedule earnings dates, trade reviews, market events |
| **GitHub** | Direct push to `github.com/agentface8-hue/Alpha-Omega-System` without manual git commands |
| **Notion** | Trade thesis documentation, playbooks, research notes |
| **Cloudflare** | Workers/KV/D1 for potential edge deployment |
| **Desktop Commander** | Run Python scripts on Windows (scoped to Alpha-Omega-System + Downloads) |
| **Computer Use** | Desktop automation, screenshot monitoring |

---

## 3. Scheduled Tasks

| Task ID | Description | Schedule (local Cyprus time) | Next Run | Status |
|---------|-------------|------------------------------|----------|--------|
| `alpha-omega-morning-briefing` | Regime fetch → dual scan → autopilot → 4 Telegram messages | Weekdays ~9 AM ET (3 PM UTC) | Daily | ✅ Enabled |
| `alpha-omega-market-check` | Refresh prices, alert on TP/SL hits | Weekdays every 30 min, 3–10 PM UTC | Every 30 min | ✅ Enabled |
| `alpha-omega-weekly-calibration` | Retune conviction thresholds from closed signals | Sundays 6 PM UTC | 2026-05-03 | ✅ Enabled |
| `alpha-omega-daily-summary` | Run cowork_daily_summary.py → Gmail draft + Telegram P&L report | Weekdays 5 PM Cyprus (`0 17 * * 1-5`) | Daily | ✅ Enabled |
| `alpha-omega-test-briefing` | One-time system health test (already fired 2026-04-30) | One-time | — | ⛔ Disabled |

---

## 4. Core Python Modules (`core/`)

| Module | Purpose |
|--------|---------|
| `regime_engine.py` | Detects current market regime (Bull/Bear/Neutral/Volatile) using SPY, VIX, breadth |
| `conviction_engine.py` | Scores signals 0–100% across 5 pillars; drives position sizing |
| `decision_matrix.py` | Final go/no-go gate: regime × conviction × risk checks |
| `decision_ledger.py` | Records every decision with reasoning for the learning loop |
| `decision_audit.py` | Replay-grade audit snapshots for council decisions, signal/portfolio actions, pipeline and safety events |
| `datahub.py` | Shared cache layer for high-traffic API reads with cached/age/source metadata |
| `trading_safety.py` | Global halt, per-symbol halt, live-mode acknowledgement, and execution guardrails |
| `ai_radar.py` | Observer-only scout that scans public AI/platform sources, compares candidates against Alpha-Omega, and marks benchmark/study/watch actions |
| `agent_platform_evaluator.py` | No-cost platform comparison and shadow adapter status aggregation |
| `langgraph_shadow.py` | Observer-only LangGraph research workflow shadow with checkpoints/replay |
| `vertex_research_runtime.py` | Observer-only Vertex shadow runtime for dream/radar/eval without trading mutation |
| `thinking_machines_benchmark.py` | Observer-only Thinking Machines/Tinker benchmark adapter for comparing model output against Alpha-Omega |
| `market_flow_agent.py` | Additive accumulation/distribution score using existing OHLCV metrics |
| `kelly_sizer.py` | Kelly Criterion position sizing capped at $500 risk/trade |
| `portfolio_manager.py` | Manages paper positions: entry, TP1/TP2/TP3 splits (50/30/20), trailing SL, close. Hooks into trade_log on every close. |
| `portfolio_store.py` | Supabase persistence layer for portfolio positions and state |
| `signal_tracker.py` | Tracks signals independently from positions; validates conviction scores. Hooks into trade_log on every close. |
| `signal_store.py` | Supabase persistence for signals and signal_reports |
| `market_data.py` | yfinance wrapper: OHLCV, indicators (RSI, MACD, ATR, MA50/150/200) |
| `futures_data.py` | Pre-market futures and index data (ES, NQ, RTY, SPY) |
| `backtester.py` | Walk-forward backtesting engine against historical signals |
| `calibrator.py` | Tunes conviction thresholds based on win-rate feedback |
| `learning_loop.py` | Post-trade analysis: compares prediction vs. outcome, updates weights |
| `attribution.py` | P&L attribution by regime, pillar, ticker, timeframe |
| `orchestrator.py` | Master coordinator: runs full pipeline (regime → scan → autopilot) |
| `smart_analyze.py` | Deep single-ticker analysis via Council of Experts agents |
| `watchlists.py` | Manages scan universe (S&P 500 + curated high-conviction watchlist) |
| `telegram_alerts.py` | Sends formatted Telegram messages to personal + group chats |
| `telegram_agent.py` | Telegram bot listener for commands from chat |
| `trade_journal.py` | Logs every scan result to Supabase `trade_journal` table (old project) |
| `trade_log.py` | Logs every **closed** position/signal to `data/trade_log.csv` + Google Sheet |
| `printing_portfolio.py` | Manages the "Printing Profits" high-frequency mini-portfolio |
| `printing_store.py` | Supabase persistence for printing_positions and printing_state |
| `printing_scanner.py` | Scanner tuned for short-duration printing trades |
| `keepalive.py` | Prevents process timeout during long scans |

---

## 5. AI Agents (`agents/`)

| Agent | Role |
|-------|------|
| `regime_detector.py` | Classifies current market regime via macro + technical signals |
| `swing_scanner.py` | Scans 500+ tickers for swing trade setups (v4.4) |
| `historian.py` | Analyzes price history, patterns, and historical precedents |
| `newsroom.py` | Fetches and interprets recent news and catalyst events |
| `macro_strategist.py` | Evaluates macro environment, sector rotation, and Fed impact |
| `portfolio_architect.py` | Sizes positions, manages correlation risk, portfolio construction |
| `risk_officer.py` | Hard-fail checks: max drawdown, position limits, sector concentration |
| `bear_case_advocate.py` | Devil's advocate — argues against every trade |
| `contrarian.py` | Tests contrarian hypothesis against consensus view |
| `executioner.py` | Final decision agent: synthesizes all inputs into buy/pass/avoid |
| `base_agent.py` | Base class: LLM integration, prompt formatting, response parsing |

---

## 6. Supabase Tables

**Active project:** `nchkslvakbcykpiizotn.supabase.co`

| Table | Contents | Used By |
|-------|----------|---------|
| `signals` | All active + closed signals (JSON blob per signal) | `signal_store.py`, `signal_tracker.py` |
| `signal_reports` | Per-signal detailed case reports and analysis | `signal_store.py` |
| `portfolio_positions` | Open paper positions (JSON blob per position) | `portfolio_store.py`, `portfolio_manager.py` |
| `portfolio_state` | Single-row portfolio-level state (capital, drawdown, etc.) | `portfolio_store.py` |
| `portfolio_state/id=decision_audit_recent` | Compact replay audit document store | `decision_audit.py` |
| `printing_positions` | Open printing profits positions | `printing_store.py` |
| `printing_state` | Printing profits portfolio state | `printing_store.py` |

> **Old project** (`gmepzeapdrnglgucgqop`): contains `trade_journal` table with historical scan results. Not migrated. New closed-trade logging uses `data/trade_log.csv` + Google Sheet instead.

---

## 7. API Keys Configured in `.env`

| Key | Status | Used For |
|-----|--------|---------|
| `SUPABASE_URL` | ✅ Set | Active Supabase project URL |
| `SUPABASE_ANON_KEY` | ✅ Set | Supabase auth |
| `TELEGRAM_TOKEN` | ✅ Set | Telegram bot alerts |
| `TELEGRAM_PERSONAL_CHAT_ID` | ✅ Set | Direct alerts to Avi |
| `TELEGRAM_GROUP_CHAT_ID` | ✅ Set | Group channel alerts |
| `ANTHROPIC_API_KEY` | ✅ Set | Claude API calls |
| `GITHUB_TOKEN` | ✅ Set | GitHub MCP direct push |
| `GOOGLE_API_KEY` | ⚠️ Empty | Not yet used (reserved for Google News / Gemini) |

---

## 8. Frontend Tabs

| # | Tab Label | Component | What It Does |
|---|-----------|-----------|-------------|
| 1 | **COUNCIL ANALYZE** | `App.jsx` + `ResultCard`, `Terminal`, `ChartPanel` | Enter a ticker → 6 AI agents analyze in sequence (Historian, Newsroom, Macro-Strategist, Contrarian, Executioner) → conviction score, trade params, entry/exit levels |
| 2 | **SWING SCAN v4.4** | `ScanDashboard.jsx` | Batch scan 500+ tickers; surfaces top setups ranked by heat and conviction |
| 3 | **BACKTESTER** | `BacktestDashboard.jsx` | Walk-forward backtests on historical signals; win rate and P&L curves |
| 4 | **SIGNAL TRACKER** | `SignalTracker.jsx` | Monitor all active signals: real-time price vs. TP/SL levels, status, conviction |
| 5 | **ALPHA-MEGA** | `AlphaMegaDashboard.jsx` | Combined view: regime + signals + portfolio in one dashboard |
| 6 | **ANALYTICS** | `Analytics.jsx` | Performance stats: win rate, avg R, P&L by regime / agent / pillar |
| 7 | **PORTFOLIO** | `PortfolioTab.jsx` | Live paper portfolio: open positions, unrealized P&L, split exit tracking |
| 8 | **PRINTING PROFITS** | `PrintingProfits.jsx` | High-frequency mini-portfolio for short-duration momentum trades |

---

## 9. Key Entry Points & Scripts

| File | Purpose |
|------|---------|
| `run_live.py` | **Main daily driver** — regime → scan → autopilot → Telegram. Called by morning briefing task. |
| `main.py` | FastAPI backend server (serves frontend at `:8000`) |
| `cowork_daily_summary.py` | 5 PM summary script: reads `data/trade_log.csv`, outputs JSON with HTML email + Telegram message |
| `cowork_hourly_check.py` | Hourly market check driver (used by market-check scheduled task) |
| `cowork_weekly_calib.py` | Weekly calibration driver (used by weekly-calibration scheduled task) |
| `setup_sheets_auth.py` | One-time OAuth setup for Google Sheets (already completed 2026-04-30) |

---

## 10. Trade Logging Pipeline

```
Position closes in portfolio_manager.py / signal_tracker.py
        ↓
core/trade_log.py
        ↓
  ┌─────────────────────┬──────────────────────────────────┐
  │  data/trade_log.csv │  Google Sheet (auto, OAuth token) │
  │  (always written)   │  1G5f1AePhWKJEMJKmfHj1genbr18LM… │
  └─────────────────────┴──────────────────────────────────┘
        ↓ (daily at 5 PM Cyprus)
  cowork_daily_summary.py → Gmail draft + Telegram message
```

---

## 11. Open Items

| Item | Priority | Notes |
|------|----------|-------|
| Daloopa MCP auth | Low | Deferred — requires paid plan. Activate when moving to earnings-catalyst trades. |
| Rotate GitHub token | Medium | Token `ghp_YVx...` briefly appeared in a commit (since reset). Rotate at github.com/settings/tokens for hygiene. |
| `GOOGLE_API_KEY` | Low | Empty in `.env`. Fill when adding Google News feed or Gemini analysis to agents. |
| Old Supabase project | Low | `trade_journal` data on `gmepzeapdrnglgucgqop` not migrated. Historical scan data lives there. |
