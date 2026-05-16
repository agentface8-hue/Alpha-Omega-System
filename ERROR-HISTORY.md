# ALPHA-OMEGA ERROR HISTORY
# All silent failures discovered - when, root cause, how long undetected, fix
# RULE: Every time something is found broken, add it here BEFORE fixing

---

## 2026-05-16

### [CRITICAL] trade_log.py - Silent failure on every trade close
- **Broken since:** Google Sheets OAuth expired (weeks ago)
- **How long undetected:** Weeks - no error, no log, nothing
- **Root cause:** _append_sheet() called broken OAuth silently
- **Impact:** 71 trades had NO automatic Airtable record
- **Fix:** _log_to_airtable() with logger.warning on failure
- **Lesson:** Test the CLOSE FLOW not just the connection

### [CRITICAL] price_feed.py - Portfolio prices stale/wrong
- **Broken since:** Alpha Vantage reduced to 25 calls/day (late 2024)
- **How long undetected:** Months
- **Root cause:** portfolio_manager + printing_portfolio imported price_feed.py which used AV
  signal_tracker.py was already fixed but price_feed.py was missed
- **Fix:** price_feed.py now uses Finnhub
- **Lesson:** When replacing a dependency, grep ENTIRE codebase for all importers

### [HIGH] AI health agent - Same fixes applied every 30 minutes
- **Root cause:** Historical win rates never change -> conditions always true -> always re-applied
- **Fix:** 24h cooldown per fix in calibration_params.json
- **Lesson:** Cooldowns wiped on Render deploy. First run post-deploy re-applies once by design.

### [HIGH] Telegram spam - sendMessage on every health check
- **Root cause:** check_telegram() called sendMessage not getMe
- **Fix:** Changed to getMe (silent API test)

### [MEDIUM] Memory NaN MB in Live Monitor
- **Root cause:** API returns process_rss_mb, frontend looked for rss_mb
- **Fix:** SystemMonitor.jsx reads process_rss_mb

### [MEDIUM] Dream Log 404 in health check
- **Root cause:** Wrong endpoint in health check
- **Fix:** /api/dreams/latest, handles empty {dreams:[]} as GREEN

### [UNKNOWN] Dreaming Agent - 0 dreams ever logged
- **Status:** Agent reports running but no output ever produced
- **Fix:** TBD

---

## PATTERNS
1. Silent failures are the biggest risk - always log warnings not pass silently
2. Integration test pass != production flow working (test the actual close path)
3. When fixing one file always grep for all other importers
4. Render ephemeral storage means file-based fixes get wiped on deploy
