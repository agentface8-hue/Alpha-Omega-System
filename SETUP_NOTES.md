# Alpha-Omega Setup Notes

## ✅ Done

### Google Sheet — "Alpha-Omega Trade Log"
- Sheet ID: `1G5f1AePhWKJEMJKmfHj1genbr18LMdlCWPsoBJC2ZxM`
- Link: https://docs.google.com/spreadsheets/d/1G5f1AePhWKJEMJKmfHj1genbr18LMdlCWPsoBJC2ZxM/edit
- Columns: Date | Ticker | Direction | Entry | Exit | P&L$ | P&L% | Conviction% | Exit Reason | Regime

### Auto-logging wired up
- `core/trade_log.py` — central logger
- Hooks added to `core/portfolio_manager.py` (check_portfolio + close_position)
- Hooks added to `core/signal_tracker.py` (check_signals + close_signal)
- Local CSV backup: `data/trade_log.csv` (always written, no auth needed)
- Google Sheet sync: works once `setup_sheets_auth.py` has been run

### Daily summary script
- `cowork_daily_summary.py` — run to generate HTML email + stats JSON

---

## ⏳ One-time tasks still needed

### 1. Connect Google Sheet write access (optional but recommended)
Run this once to enable direct sheet appending:

```
cd C:\Users\asus\Alpha-Omega-System
python setup_sheets_auth.py
```

Requires `credentials.json` from Google Cloud Console:
1. https://console.cloud.google.com/ → APIs & Services → Credentials
2. Create OAuth 2.0 Client ID (Desktop app)
3. Download JSON → save as `C:\Users\asus\Alpha-Omega-System\credentials.json`
4. Run `setup_sheets_auth.py` → browser opens for Google auth

**Without this**: trades still log to `data/trade_log.csv` — the sheet stays empty until you do this step.

### 2. Create the 5 PM daily summary scheduled task
Cannot be created from within a scheduled task session.
**Open a regular Cowork chat and say:**

> "Create the alpha-omega-daily-summary scheduled task"

Cowork will create a task that runs weekdays at 5 PM Cyprus time, reads today's trades from `data/trade_log.csv`, and emails a summary to ipurchesinfo@gmail.com via Gmail.
