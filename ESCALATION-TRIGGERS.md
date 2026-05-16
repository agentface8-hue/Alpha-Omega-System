# ALPHA-OMEGA ESCALATION TRIGGERS
# Conditions that STOP automation and require human action
# Cowork reads this before any autonomous change
# Last updated: 2026-05-16

---

## TIER 1 - HALT EVERYTHING (Telegram alert + stop all signals)

| Condition | Threshold | Action |
|---|---|---|
| Daily portfolio loss | > 5% in one day | Stop all signals, alert Telegram |
| Consecutive stop-outs | 4 in a row | Pause autopilot, alert Telegram |
| Supabase RED | Any connection failure | Halt signal creation |
| Airtable fails on close | 3 consecutive | Alert Telegram with trade details |
| Server memory | > 1800 MB | Alert + restart background tasks |

## TIER 2 - ALERT ONLY (Telegram, don't stop)

| Condition | Threshold | Action |
|---|---|---|
| Win rate drops | < 40% last 20 trades | Alert with stats |
| Profit factor drops | < 1.5 last 20 trades | Alert with stats |
| Any integration RED | Health check | Alert (already implemented) |
| IBKR balance swing | > 10% unexpected | Alert immediately |

## TIER 3 - LOG ONLY (no alert)

| Condition | Action |
|---|---|
| Finnhub -> yfinance fallback | Log with timestamp |
| Calibration params wiped | Log, apply first-run fix |
| Council VETO on signal | Log veto reason |

## COWORK AUTONOMOUS LIMITS
Cowork must NOT autonomously:
- Change any calibration parameter > 10% from current value (run Council first)
- Add/remove stocks from watchlist
- Modify ATR multipliers or regime thresholds
- Touch the IBKR account in any way
- Edit core files: trade_log.py, signal_tracker.py, portfolio_manager.py

For any of the above: send Telegram message with proposed change, wait for human approval.
